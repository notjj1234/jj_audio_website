"""Multi-stem audio isolation via Demucs (standalone feature).

Stage-1 guitar model (2026-08-24 research decision): keep ``htdemucs_6s`` as
the default first-stage separator whenever a dedicated ``guitar`` stem is
required. Do not swap the default to ``htdemucs`` / ``htdemucs_ft`` (no guitar
stem), vocal-SOTA RoFormer, or UVR. Lead vs rhythm remains a *post-process*
on that single guitar stem — see ``eval/lead_rhythm/RESEARCH.md``.

Bass/guitar bleed (2026-07-17): distorted/overdriven bass and electric guitar
share heavily overlapping spectral and timbral content, so Demucs (including
``htdemucs_6s``, the only supported model that produces a ``guitar`` stem)
does not always keep them cleanly separated — the ``guitar`` stem can carry
audible bass energy. This is a documented, model-level limitation (see
facebookresearch/demucs issue #291: "no easy solution... a hell of a
challenge" without training new per-instrument models on curated datasets,
which is out of scope here) — not a bug in this repo's post-processing, and
not something this module claims to fix. ``htdemucs_ft`` does not have this
specific failure mode because it is the fine-tuned *4-stem* model (vocals/
drums/bass/other) and never produces a ``guitar`` stem at all — "other" would
still contain guitar, unseparated. See ``eval/lead_rhythm/README.md`` for the
full writeup, the ``BassBleedDiagnostics`` dataclass below for the (diagnostic
-only-by-default) low-frequency-energy heuristic, and ``IsolateConfig.
bass_bleed_mitigation`` for the optional, opt-in, partial high-pass mitigation.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

import numpy as np

logger = logging.getLogger(__name__)

from audio_to_tab.ingest import normalize_audio
from audio_to_tab.lead_rhythm import LeadRhythmThresholds, resolve_lead_rhythm_mode
from audio_to_tab.hardware import ensure_cuda_available, separate_progress_message
from audio_to_tab.separate import (
    GUITAR_FT_CHECKPOINT_ID,
    SUPPORTED_GUITAR_CHECKPOINTS,
    is_demucs_available,
    run_demucs,
    run_demucs_guitar_ft_inprocess,
)
from audio_to_tab.subprocess_util import subprocess_run_kwargs

DEMUCS_INSTALL_HINT = (
    "Demucs is required for stem separation. Install with: make install-demucs "
    "or pip install -e \".[demucs]\""
)

ProgressCallback = Callable[[str, str], None]

SUPPORTED_MODELS = ("htdemucs_6s", "htdemucs", "htdemucs_ft")

QUALITY_SHIFTS = {"fast": "0", "balanced": "1", "high": "3", "extreme": "5"}
QUALITY_OVERLAP = {"fast": "0.25", "balanced": "0.25", "high": "0.5", "extreme": "0.75"}

# Demucs always writes the full stem set for a model, even when an instrument
# isn't actually present in the mix. These gate the auto-detection heuristic
# used to flag which produced stems are audibly real vs. near-silent filler.
STEM_PRESENCE_FLOOR_DB = -45.0
STEM_PRESENCE_ENERGY_SHARE_MIN = 0.02
_STEM_PRESENCE_MIN_RMS = 10.0 ** (-100.0 / 20.0)  # floor to avoid log(0)

# Bass-bleed diagnostic (see module docstring): a "guitar" stem where too much
# RMS energy sits below this band is unusually bass-heavy for a guitar and
# likely carries bled-in bass content, per the known Demucs limitation.
BASS_BLEED_LOW_BAND_HZ = 250.0
# Calibrated so a synthetic "clean guitar chord" fixture (~0.54 share, mostly
# 82-370 Hz content with a modest low-E fundamental) stays well under the
# floor while a fixture with added distorted-bass content (~0.85 share) is
# clearly flagged — see tests/test_isolate.py.
BASS_BLEED_ENERGY_SHARE_FLOOR = 0.65
# Opt-in mitigation cutoff: below the lowest fundamental of standard-tuned
# guitar (open low E ≈ 82.4 Hz) and Drop D (≈73.4 Hz), so it only removes
# sub-guitar-range rumble/bleed. Tunings dropped lower than this (Drop C
# ≈65.4 Hz, 7-string low B ≈61.7 Hz, Drop A, etc.) will have their own
# fundamental attenuated too — there is no cutoff that is safe for every
# tuning, so this is a deliberate, documented tradeoff, not a fix.
BASS_BLEED_HPF_CUTOFF_HZ = 60.0
BASS_BLEED_HPF_ORDER = 4

MIN_REGION_SEC = 5.0

_FFMPEG_DURATION_RE = re.compile(
    r"Duration:\s*(\d{2}):(\d{2}):(\d{2}\.\d+)",
    re.IGNORECASE,
)


class RegionError(ValueError):
    """Invalid audio region selection."""


def format_time_sec(sec: float) -> str:
    """Format seconds as M:SS."""
    if sec < 0:
        sec = 0
    m = int(sec // 60)
    s = int(sec % 60)
    return f"{m}:{s:02d}"


def format_region_label(start_sec: float, length_sec: float) -> str:
    """Human-readable region label, e.g. ``0:32–1:15``."""
    end_sec = start_sec + length_sec
    return f"{format_time_sec(start_sec)}–{format_time_sec(end_sec)}"


def format_region_label_filename(start_sec: float, length_sec: float) -> str:
    """Filename-safe region suffix, e.g. ``0m32-1m15``."""

    def _part(sec: float) -> str:
        m = int(sec // 60)
        s = int(sec % 60)
        return f"{m}m{s:02d}"

    end_sec = start_sec + length_sec
    return f"{_part(start_sec)}-{_part(end_sec)}"


def probe_duration_sec(path: str | Path) -> float | None:
    """
    Return audio duration in seconds, or None if it cannot be determined.

    Tries ffprobe, then ffmpeg stderr parsing, then soundfile.
    """
    src = Path(path)
    if not src.exists():
        return None

    ffprobe = shutil.which("ffprobe")
    if ffprobe:
        result = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(src),
            ],
            capture_output=True,
            text=True,
            check=False,
            **subprocess_run_kwargs(),
        )
        if result.returncode == 0:
            try:
                dur = float(result.stdout.strip())
                if dur > 0:
                    return dur
            except ValueError:
                pass

    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        result = subprocess.run(
            [ffmpeg, "-i", str(src)],
            capture_output=True,
            text=True,
            check=False,
            **subprocess_run_kwargs(),
        )
        match = _FFMPEG_DURATION_RE.search(result.stderr or "")
        if match:
            hours, minutes, seconds = match.groups()
            dur = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
            if dur > 0:
                return dur

    try:
        import soundfile as sf

        info = sf.info(str(src))
        if info.samplerate > 0 and info.frames > 0:
            return float(info.frames) / float(info.samplerate)
    except Exception:
        pass

    return None


def resolve_region(
    duration_sec: float | None,
    start_sec: float,
    end_sec: float | None,
    *,
    cap_sec: float | None = None,
) -> tuple[float, float, str | None]:
    """
    Validate and resolve a trim region.

    Returns ``(start_sec, length_sec, note)`` where ``note`` explains any cap
    shortening. Raises ``RegionError`` when the range is invalid.
    """
    if start_sec < 0:
        raise RegionError("start_sec must be >= 0")

    if end_sec is None:
        if duration_sec is None:
            raise RegionError("end_sec required when file duration is unknown")
        end_sec = duration_sec

    if start_sec >= end_sec:
        raise RegionError("start_sec must be less than end_sec")

    length = end_sec - start_sec
    if length < MIN_REGION_SEC:
        raise RegionError(f"region must be at least {MIN_REGION_SEC:.0f} seconds")

    if duration_sec is not None and end_sec > duration_sec + 0.05:
        raise RegionError("end_sec exceeds file duration")

    note: str | None = None
    if cap_sec is not None and length > cap_sec:
        length = cap_sec
        note = (
            f"Region shortened to {cap_sec:.0f}s for processing mode limit "
            f"({format_region_label(start_sec, length)})"
        )

    return start_sec, length, note


@dataclass
class DualGuitarDiagnostics:
    """Legacy stereo heuristic diagnostics (not used by live isolate path).

    Prefer ``LeadRhythmDiagnostics`` from ``audio_to_tab.lead_rhythm``.
    """

    attempted: bool
    split: bool
    reason: str
    correlation: float | None = None
    balance_ratio: float | None = None


@dataclass
class IsolateConfig:
    model: str = "htdemucs_6s"
    quality: str = "fast"
    device: str = "cpu"
    # Seconds from file start where isolation begins (default: 0 = beginning).
    start_sec: float = 0.0
    # Length of the section to process from start_sec. None = through end of file.
    max_duration_sec: float | None = None
    two_stems: str | None = None  # e.g. "vocals" for karaoke-style split
    # Emit policy for Lead/Rhythm post-process. Default confident-only emit.
    lead_rhythm_mode: str = "confident"  # confident | best_effort
    # Deprecated alias: True → best_effort for backward-compatible callers.
    lead_rhythm: bool = False
    dual_guitar: bool = False  # deprecated alias for lead_rhythm
    # Optional stage-1 guitar checkpoint (htdemucs_6s only). None = stock Demucs.
    guitar_checkpoint: str | None = None
    # Optional Lead/Rhythm gate overrides (CLI/eval); None → env + defaults.
    lead_rhythm_thresholds: LeadRhythmThresholds | None = None
    # Opt-in, partial mitigation only: high-pass the guitar stem below
    # BASS_BLEED_HPF_CUTOFF_HZ when BassBleedDiagnostics flags it. Default off
    # because it is a lossy tradeoff (see BASS_BLEED_HPF_CUTOFF_HZ docstring),
    # not a correction of the underlying Demucs separation.
    bass_bleed_mitigation: bool = False

    def __post_init__(self) -> None:
        # dual_guitar=True enables lead_rhythm for one-release backward compatibility.
        if self.dual_guitar and not self.lead_rhythm:
            self.lead_rhythm = True
        if self.lead_rhythm and self.lead_rhythm_mode == "confident":
            self.lead_rhythm_mode = "best_effort"
        if self.guitar_checkpoint and self.guitar_checkpoint not in SUPPORTED_GUITAR_CHECKPOINTS:
            raise ValueError(
                f"Unsupported guitar_checkpoint {self.guitar_checkpoint!r}. "
                f"Choose from: {', '.join(sorted(SUPPORTED_GUITAR_CHECKPOINTS))}"
            )


@dataclass
class StemPresence:
    """Whether a produced stem actually contains audible content.

    Demucs has no per-instrument "only compute what's present" mode — it
    always writes the full fixed stem set for whichever model is chosen.
    This is a lightweight post-hoc heuristic to flag near-silent stems.
    """

    present: bool
    confidence: float
    mean_dbfs: float
    energy_share: float
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def write_json(self, path: Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        return path


def _stem_rms(path: Path) -> float:
    try:
        import soundfile as sf

        data, _sr = sf.read(str(path), always_2d=True)
    except Exception:
        return 0.0
    if data.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(data.astype(np.float64)))))


def _rms_to_dbfs(rms: float) -> float:
    return 20.0 * float(np.log10(max(rms, _STEM_PRESENCE_MIN_RMS)))


def detect_present_stems(stem_paths: dict[str, Path]) -> dict[str, StemPresence]:
    """Estimate which produced stems are audibly present vs. near-silent filler.

    For each stem, computes mean RMS energy converted to dBFS plus that
    stem's RMS share of the total RMS across all stems passed in. A stem is
    considered present if either signal clears its threshold, since a
    quiet-but-real instrument can still have a low absolute level.
    """
    rms_by_stem = {name: _stem_rms(path) for name, path in stem_paths.items()}
    total_rms = sum(rms_by_stem.values())

    results: dict[str, StemPresence] = {}
    for name, rms in rms_by_stem.items():
        mean_dbfs = _rms_to_dbfs(rms)
        energy_share = (rms / total_rms) if total_rms > 1e-12 else 0.0

        level_margin = (mean_dbfs - STEM_PRESENCE_FLOOR_DB) / 20.0
        share_margin = (energy_share - STEM_PRESENCE_ENERGY_SHARE_MIN) / max(
            STEM_PRESENCE_ENERGY_SHARE_MIN, 1e-9
        )
        margin = max(level_margin, share_margin)
        present = margin >= 0.0
        confidence = float(max(0.0, min(1.0, 0.5 + 0.5 * margin)))

        state = "audibly present" if present else "near-silent/absent"
        reason = (
            f"mean level {mean_dbfs:.1f} dBFS (floor {STEM_PRESENCE_FLOOR_DB:.1f}), "
            f"energy share {energy_share:.3f} (min {STEM_PRESENCE_ENERGY_SHARE_MIN:.3f}) "
            f"— stem appears {state}"
        )

        results[name] = StemPresence(
            present=present,
            confidence=confidence,
            mean_dbfs=mean_dbfs,
            energy_share=energy_share,
            reason=reason,
        )
    return results


@dataclass
class BassBleedDiagnostics:
    """
    Diagnostic (not a fix) for the known Demucs bass/guitar low-end confusion
    described in the module docstring.

    Only measures low-frequency RMS energy share in the ``guitar`` stem and
    flags when it is anomalously high for a guitar — it cannot tell *why*
    (bled-in bass vs. a legitimately bass-heavy guitar tone), so the reason
    string is deliberately hedged. ``mitigation_applied`` records whether the
    optional, opt-in high-pass mitigation (``IsolateConfig.bass_bleed_mitigation``)
    ran — that mitigation only attenuates content below
    ``BASS_BLEED_HPF_CUTOFF_HZ``, it does not re-separate or relabel anything.
    """

    attempted: bool
    flagged: bool
    reason: str
    low_band_energy_share: float | None = None
    low_band_cutoff_hz: float = BASS_BLEED_LOW_BAND_HZ
    mitigation_applied: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def write_json(self, path: Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        return path


def _lowpass_rms(mono: np.ndarray, sr: int, cutoff_hz: float, order: int = 4) -> float:
    from scipy.signal import butter, sosfiltfilt

    nyquist = sr / 2.0
    normalized = min(0.99, max(1e-6, cutoff_hz / nyquist))
    sos = butter(order, normalized, btype="low", output="sos")
    low = sosfiltfilt(sos, mono)
    return float(np.sqrt(np.mean(np.square(low)) + 1e-12))


def analyze_bass_bleed(
    guitar_path: Path,
    *,
    low_band_hz: float = BASS_BLEED_LOW_BAND_HZ,
    energy_share_floor: float = BASS_BLEED_ENERGY_SHARE_FLOOR,
) -> BassBleedDiagnostics:
    """
    Measure the guitar stem's RMS energy share below ``low_band_hz`` and flag
    it as anomalously bass-heavy above ``energy_share_floor``.

    This is a heuristic diagnostic, not a classifier: it cannot distinguish
    bled-in bass from a guitar tone that is legitimately bass-heavy (e.g. a
    heavily palm-muted low riff). See module docstring.
    """
    if not guitar_path.exists():
        return BassBleedDiagnostics(attempted=False, flagged=False, reason="guitar stem missing")

    import soundfile as sf

    data, sr = sf.read(str(guitar_path), always_2d=True)
    if data.size == 0:
        return BassBleedDiagnostics(attempted=True, flagged=False, reason="guitar stem is empty")

    mono = data.mean(axis=1).astype(np.float64)
    total_rms = float(np.sqrt(np.mean(np.square(mono)) + 1e-12))
    if total_rms < 1e-9:
        return BassBleedDiagnostics(
            attempted=True, flagged=False, reason="guitar stem is near-silent"
        )

    share = _lowpass_rms(mono, sr, low_band_hz) / total_rms
    flagged = share >= energy_share_floor
    if flagged:
        outcome = (
            "anomalously bass-heavy for a guitar stem — likely partial bass bleed "
            "(known Demucs limitation; diagnostic only, not a corrected label — "
            "see eval/lead_rhythm/README.md)"
        )
    else:
        outcome = "within the normal range observed for a guitar stem"
    reason = (
        f"low-frequency (<{low_band_hz:.0f} Hz) RMS energy share {share:.2f} "
        f"({'>=' if flagged else '<'} floor {energy_share_floor:.2f}) — {outcome}"
    )
    return BassBleedDiagnostics(
        attempted=True,
        flagged=flagged,
        reason=reason,
        low_band_energy_share=share,
        low_band_cutoff_hz=low_band_hz,
    )


def apply_bass_bleed_mitigation(
    guitar_path: Path,
    output_path: Path,
    *,
    cutoff_hz: float = BASS_BLEED_HPF_CUTOFF_HZ,
    order: int = BASS_BLEED_HPF_ORDER,
) -> Path:
    """
    Opt-in, partial mitigation: high-pass the guitar stem below ``cutoff_hz``.

    This attenuates sub-guitar-range energy (see ``BASS_BLEED_HPF_CUTOFF_HZ``
    for the tuning tradeoff) — it does not remove bleed that overlaps the
    guitar's own playable range or harmonics of the bled bass above the
    cutoff, so it is a partial reduction, not a fix.
    """
    import soundfile as sf
    from scipy.signal import butter, sosfiltfilt

    data, sr = sf.read(str(guitar_path), always_2d=True)
    nyquist = sr / 2.0
    normalized = min(0.99, max(1e-6, cutoff_hz / nyquist))
    sos = butter(order, normalized, btype="high", output="sos")
    filtered = sosfiltfilt(sos, data, axis=0).astype(np.float32)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(output_path), filtered, sr, subtype="PCM_16")
    return output_path


def _noop_progress(stage: str, message: str) -> None:
    pass


def _load_stereo(path: Path) -> tuple[np.ndarray, int]:
    import soundfile as sf

    data, sr = sf.read(str(path), always_2d=True)
    if data.shape[1] == 1:
        data = np.repeat(data, 2, axis=1)
    return data.astype(np.float32), sr


def analyze_dual_guitar_candidate(guitar_path: Path) -> DualGuitarDiagnostics:
    """Legacy heuristic: stereo guitar stem with distinct L/R content may be two guitars.

    Not called by ``separate_stems``. Live Lead/Rhythm uses
    ``audio_to_tab.lead_rhythm.build_spatial_pair`` instead.
    """
    if not guitar_path.exists():
        return DualGuitarDiagnostics(False, False, "guitar stem missing")

    data, _sr = _load_stereo(guitar_path)
    if data.shape[1] < 2 or len(data) < 1024:
        return DualGuitarDiagnostics(True, False, "guitar stem is mono or too short")

    left = data[:, 0]
    right = data[:, 1]
    rms_l = float(np.sqrt(np.mean(left**2)))
    rms_r = float(np.sqrt(np.mean(right**2)))
    max_rms = max(rms_l, rms_r, 1e-9)
    balance = min(rms_l, rms_r) / max_rms

    if balance < 0.12:
        return DualGuitarDiagnostics(
            True,
            False,
            "stereo energy too imbalanced for dual-guitar split",
            balance_ratio=balance,
        )

    if np.std(left) < 1e-6 or np.std(right) < 1e-6:
        return DualGuitarDiagnostics(True, False, "near-silent channel", balance_ratio=balance)

    corr = float(np.corrcoef(left, right)[0, 1])
    if corr > 0.92:
        return DualGuitarDiagnostics(
            True,
            False,
            "L/R channels too similar (likely one guitar)",
            correlation=corr,
            balance_ratio=balance,
        )

    return DualGuitarDiagnostics(
        True,
        True,
        "stereo heuristic suggests two distinct guitar parts",
        correlation=corr,
        balance_ratio=balance,
    )


def split_dual_guitar_stem(
    guitar_path: Path,
    output_dir: Path,
) -> tuple[dict[str, Path], DualGuitarDiagnostics]:
    """
    Legacy: derive guitar1/guitar2 from stereo guitar stem (spatial labels only).

    Not called by ``separate_stems``. Prefer ``split_lead_rhythm_guitar`` for
    semantic Lead/Rhythm stems. Kept for tests and any external callers.
    """
    import warnings

    import soundfile as sf

    warnings.warn(
        "split_dual_guitar_stem is deprecated; use "
        "audio_to_tab.lead_rhythm.split_lead_rhythm_guitar",
        DeprecationWarning,
        stacklevel=2,
    )

    diag = analyze_dual_guitar_candidate(guitar_path)
    if not diag.split:
        return {}, diag

    data, sr = _load_stereo(guitar_path)
    left = data[:, 0]
    right = data[:, 1]

    # Soft dominance masks reduce bleed from the opposite channel.
    guitar1_mono = np.where(np.abs(left) >= np.abs(right), left, left - 0.5 * right)
    guitar2_mono = np.where(np.abs(right) >= np.abs(left), right, right - 0.5 * left)
    guitar1 = np.column_stack([guitar1_mono, guitar1_mono])
    guitar2 = np.column_stack([guitar2_mono, guitar2_mono])

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    p1 = out_dir / "guitar1.wav"
    p2 = out_dir / "guitar2.wav"
    sf.write(str(p1), guitar1, sr, subtype="PCM_16")
    sf.write(str(p2), guitar2, sr, subtype="PCM_16")
    return {"guitar1": p1, "guitar2": p2}, diag


def _trim_audio(
    input_path: Path,
    max_duration_sec: float | None,
    *,
    start_sec: float = 0.0,
) -> Path:
    """Trim normalized audio with ffmpeg ``-ss`` + ``-t`` (after normalize, before Demucs)."""
    if max_duration_sec is None and start_sec <= 0:
        return input_path
    length = max_duration_sec
    if length is None:
        return input_path
    out = input_path.parent / f"{input_path.stem}_trim.wav"
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return input_path
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-ss",
            str(start_sec),
            "-i",
            str(input_path),
            "-t",
            str(length),
            str(out),
        ],
        capture_output=True,
        check=False,
        **subprocess_run_kwargs(),
    )
    return out if out.exists() else input_path


def separate_stems(
    audio_path: str | Path,
    output_dir: str | Path,
    config: IsolateConfig | None = None,
    *,
    on_progress: ProgressCallback | None = None,
) -> dict[str, Path]:
    """
    Separate an audio file into instrument stems using Demucs.

    Returns a mapping of stem name -> wav path under output_dir.
    CPU separation is slow (~track length or longer); quality presets multiply time.
    CUDA (NVIDIA GPU) is used when ``config.device`` is ``cuda`` and Torch can see it.
    """
    if not is_demucs_available():
        raise RuntimeError(
            f"Demucs is not installed. {DEMUCS_INSTALL_HINT}"
        )

    cfg = config or IsolateConfig()
    if cfg.model not in SUPPORTED_MODELS:
        raise ValueError(
            f"Unsupported model {cfg.model!r}. Choose from: {', '.join(SUPPORTED_MODELS)}"
        )

    ensure_cuda_available(cfg.device)

    progress = on_progress or _noop_progress
    src = Path(audio_path)
    if not src.exists():
        raise FileNotFoundError(f"Audio file not found: {src}")

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    shifts = QUALITY_SHIFTS.get(cfg.quality, "0")
    overlap = QUALITY_OVERLAP.get(cfg.quality, "0.25")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        progress("ingest", "Normalizing audio")
        normalized = normalize_audio(src, tmp_path / "normalized.wav")
        trim_length = cfg.max_duration_sec
        trim_start = cfg.start_sec
        if trim_length is None and trim_start <= 0:
            trim_message = "Using full audio"
        else:
            if trim_length is None:
                file_dur = probe_duration_sec(normalized)
                if file_dur is not None and file_dur > trim_start:
                    trim_length = file_dur - trim_start
            if trim_length is not None and trim_length > 0:
                trim_message = f"Trimming to {format_region_label(trim_start, trim_length)}"
            else:
                trim_message = "Using full audio"
        progress("ingest", trim_message)
        trimmed = _trim_audio(normalized, trim_length, start_sec=trim_start)

        progress("separate", separate_progress_message(cfg.device))
        demucs_out = tmp_path / "demucs_out"
        use_guitar_ft = (
            cfg.guitar_checkpoint == GUITAR_FT_CHECKPOINT_ID
            and cfg.model == "htdemucs_6s"
            and not cfg.two_stems
        )
        if use_guitar_ft:
            try:
                progress("separate", "Running htdemucs_6s with guitar-focused weights")
                run_demucs_guitar_ft_inprocess(
                    trimmed,
                    demucs_out,
                    device=cfg.device,
                    quality=cfg.quality,
                )
            except Exception as exc:
                logger.warning("guitar-ft separation failed; falling back to stock 6s: %s", exc)
                progress(
                    "separate",
                    f"guitar-ft unavailable ({exc}); using stock htdemucs_6s",
                )
                use_guitar_ft = False

        if not use_guitar_ft:
            demucs_args = [
                "-n",
                cfg.model,
                "-d",
                cfg.device,
                "-o",
                str(demucs_out),
                "--shifts",
                shifts,
                "--overlap",
                overlap,
            ]
            if cfg.two_stems:
                demucs_args.extend(["--two-stems", cfg.two_stems])
            demucs_args.append(str(trimmed))
            run_demucs(demucs_args)

        progress("collect", "Collecting stem files")
        stem_files = list(demucs_out.rglob("*.wav"))
        if not stem_files:
            raise FileNotFoundError("Demucs did not produce any stem wav files.")

        artifacts: dict[str, Path] = {}
        for stem_path in stem_files:
            name = stem_path.stem  # e.g. vocals, drums
            dest = out_dir / f"{name}.wav"
            shutil.copy2(stem_path, dest)
            artifacts[name] = dest

        if not artifacts:
            raise FileNotFoundError("No stems could be collected from Demucs output.")

        if "guitar" in artifacts:
            progress("bass_bleed", "Checking guitar stem for likely bass bleed (diagnostic only)")
            bass_bleed_diag = analyze_bass_bleed(artifacts["guitar"])
            if bass_bleed_diag.flagged and cfg.bass_bleed_mitigation:
                mitigated_path = apply_bass_bleed_mitigation(artifacts["guitar"], artifacts["guitar"])
                artifacts["guitar"] = mitigated_path
                bass_bleed_diag = BassBleedDiagnostics(
                    attempted=bass_bleed_diag.attempted,
                    flagged=bass_bleed_diag.flagged,
                    reason=bass_bleed_diag.reason
                    + f"; partial high-pass mitigation applied (<{BASS_BLEED_HPF_CUTOFF_HZ:.0f} Hz "
                    "attenuated — does not remove bleed above the cutoff or fix the label)",
                    low_band_energy_share=bass_bleed_diag.low_band_energy_share,
                    low_band_cutoff_hz=bass_bleed_diag.low_band_cutoff_hz,
                    mitigation_applied=True,
                )
            bass_bleed_path = bass_bleed_diag.write_json(out_dir / "bass_bleed_diagnostics.json")
            artifacts["bass_bleed_diagnostics"] = bass_bleed_path
            progress("bass_bleed", bass_bleed_diag.reason)

        lead_rhythm_diag = None
        if "guitar" not in artifacts:
            progress(
                "guitar_split",
                "Lead/Rhythm skipped — no guitar stem (use htdemucs_6s)",
            )
        else:
            from audio_to_tab.lead_rhythm import split_lead_rhythm_guitar

            emit_mode = resolve_lead_rhythm_mode(
                cfg.lead_rhythm_mode,
                lead_rhythm=cfg.lead_rhythm,
            )
            progress("guitar_split", "Attempting Lead / Rhythm guitar split")
            extra, lead_rhythm_diag = split_lead_rhythm_guitar(
                artifacts["guitar"],
                out_dir,
                thresholds=cfg.lead_rhythm_thresholds,
                emit_mode=emit_mode,
            )
            artifacts.update(extra)
            lr_emitted = "lead_guitar" in extra and "rhythm_guitar" in extra
            if lead_rhythm_diag.outcome == "lead_rhythm" and lr_emitted:
                progress("guitar_split", lead_rhythm_diag.reason)
            elif lr_emitted:
                progress("guitar_split", lead_rhythm_diag.reason)
            else:
                progress(
                    "guitar_split",
                    f"Lead/Rhythm not separated: {lead_rhythm_diag.reason}",
                )

        progress("presence", "Detecting which stems are audibly present")
        stem_wav_paths = {
            name: path for name, path in artifacts.items() if not name.endswith("_diagnostics")
        }
        presence = detect_present_stems(stem_wav_paths)
        lr_emitted = "lead_guitar" in artifacts and "rhythm_guitar" in artifacts
        if (
            lead_rhythm_diag is not None
            and lead_rhythm_diag.outcome == "lead_rhythm"
            and lr_emitted
            and "guitar" in presence
        ):
            guitar_presence = presence["guitar"]
            presence["guitar"] = StemPresence(
                present=False,
                confidence=guitar_presence.confidence,
                mean_dbfs=guitar_presence.mean_dbfs,
                energy_share=guitar_presence.energy_share,
                reason="superseded by lead_guitar/rhythm_guitar",
            )
            for derived in ("lead_guitar", "rhythm_guitar"):
                if derived in presence:
                    sp = presence[derived]
                    presence[derived] = StemPresence(
                        present=True,
                        confidence=max(sp.confidence, 0.6),
                        mean_dbfs=sp.mean_dbfs,
                        energy_share=sp.energy_share,
                        reason=(
                            "Lead/Rhythm split emitted from guitar stem"
                            + (
                                " (best-effort, low confidence)"
                                if lead_rhythm_diag.low_confidence
                                else ""
                            )
                        ),
                    )

        presence_path = out_dir / "stem_presence.json"
        presence_path.write_text(
            json.dumps({name: sp.to_dict() for name, sp in presence.items()}, indent=2),
            encoding="utf-8",
        )
        artifacts["stem_presence_diagnostics"] = presence_path

        progress("done", f"Separated {len(artifacts)} stem(s)")
        return artifacts

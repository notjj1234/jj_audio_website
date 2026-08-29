"""Demucs stem separation for isolating guitar from full mixes."""

from __future__ import annotations

import hashlib
import importlib.util
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

from audio_to_tab.subprocess_util import subprocess_run_kwargs

logger = logging.getLogger(__name__)

GUITAR_FT_CHECKPOINT_ID = "htdemucs_6s_guitar_ft"
GUITAR_FT_HF_REPO = "adityalakhani/htdemucs-6s-guitar-ft"
GUITAR_FT_FILENAME = "guitar_htdemucs_6s.pt"
GUITAR_FT_URL = (
    f"https://huggingface.co/{GUITAR_FT_HF_REPO}/resolve/main/{GUITAR_FT_FILENAME}"
)
# Hugging Face blob SHA256 for guitar_htdemucs_6s.pt (330 MB / 329654071 bytes).
GUITAR_FT_SHA256 = "4fde369e41582ba5c2759b6ab926a44af467c64d4566bf914374ab267b19260e"
SUPPORTED_GUITAR_CHECKPOINTS = frozenset({GUITAR_FT_CHECKPOINT_ID})
GUITAR_FT_CACHE_HINT = (
    "guitar-ft weights are not in the torch cache; using stock htdemucs_6s. "
    "Download once from Audio Isolation Advanced "
    "(or audio-isolate --guitar-checkpoint htdemucs_6s_guitar_ft)."
)


def is_demucs_available() -> bool:
    """Return True if the Demucs package is installed.

    Uses ``find_spec`` so the desktop UI can paint without importing Demucs or
    Torch. Real separation still imports Demucs inside the job worker.
    """
    return importlib.util.find_spec("demucs") is not None


def _torch_cache_dir() -> Path:
    if env := os.environ.get("TORCH_HOME"):
        return Path(env)
    return Path.home() / ".cache" / "torch"


def guitar_ft_weights_path() -> Path:
    """Local cache path for the community guitar-ft HTDemucs-6s weights."""
    return _torch_cache_dir() / "checkpoints" / GUITAR_FT_FILENAME


def guitar_ft_weights_cached() -> bool:
    """True when pinned guitar-ft weights are already on disk. Does not download."""
    path = guitar_ft_weights_path()
    if not path.is_file():
        return False
    try:
        return guitar_ft_weights_sha256(path) == GUITAR_FT_SHA256
    except OSError:
        return False


def guitar_ft_weights_sha256(path: Path | None = None) -> str:
    """Return sha256 hex digest of cached guitar-ft weights (for pinning/tests)."""
    target = path or guitar_ft_weights_path()
    digest = hashlib.sha256()
    with target.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_guitar_ft_weights(path: Path | None = None) -> Path:
    """Raise if the cached file is missing or its SHA256 does not match the pin."""
    target = path or guitar_ft_weights_path()
    if not target.is_file():
        raise RuntimeError(f"guitar-ft weights not found at {target}")
    digest = guitar_ft_weights_sha256(target)
    if digest != GUITAR_FT_SHA256:
        target.unlink(missing_ok=True)
        raise RuntimeError(
            f"guitar-ft weights hash mismatch (got {digest}, expected {GUITAR_FT_SHA256})"
        )
    return target


def download_guitar_ft_weights(*, force: bool = False) -> Path:
    """Download guitar-ft weights into the torch cache (urllib, no huggingface_hub)."""
    path = guitar_ft_weights_path()
    if path.exists() and not force:
        try:
            return verify_guitar_ft_weights(path)
        except RuntimeError:
            logger.warning("Cached guitar-ft weights failed hash check; re-downloading")
            path.unlink(missing_ok=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".part")
    try:
        with urllib.request.urlopen(GUITAR_FT_URL, timeout=120) as resp:
            data = resp.read()
        tmp.write_bytes(data)
        tmp.replace(path)
    except (urllib.error.URLError, OSError) as exc:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        raise RuntimeError(f"Failed to download guitar-ft weights from {GUITAR_FT_URL}") from exc
    return verify_guitar_ft_weights(path)


def remap_guitar_ft_state_dict(
    state_dict: dict,
    wrapper_keys: set[str] | frozenset[str],
) -> dict:
    """Prefix inner HTDemucs keys with ``models.0.`` for Demucs BagOfModels.

    ``get_model("htdemucs_6s")`` wraps the network; the guitar-ft training
    checkpoint stores the inner module's ``state_dict`` without that prefix.
    """
    if not isinstance(state_dict, dict) or not state_dict:
        return state_dict
    sample = list(state_dict.keys())[:3]
    if any(key in wrapper_keys for key in sample):
        return state_dict
    return {f"models.0.{key}": value for key, value in state_dict.items()}


def load_guitar_ft_state_dict(weights_path: Path):
    """Load guitar-ft checkpoint state dict onto CPU."""
    import torch

    checkpoint = torch.load(weights_path, map_location="cpu", weights_only=True)
    if isinstance(checkpoint, dict):
        if "model_state_dict" in checkpoint:
            return checkpoint["model_state_dict"]
        if "state" in checkpoint:
            return checkpoint["state"]
    return checkpoint


def run_demucs_guitar_ft_inprocess(
    audio_path: Path,
    output_root: Path,
    *,
    device: str = "cpu",
    quality: str = "fast",
    segment: int | None = 7,
    jobs: int = 1,
) -> None:
    """
    Run official HTDemucs-6s with community guitar-ft weights in-process.

    Writes the same six stem filenames Demucs CLI would produce under
    ``output_root/htdemucs_6s/<track>/``.

    ``segment`` (seconds) and ``jobs`` match the CLI ``--segment`` / ``--jobs``
    path so CPU runs stay chunked instead of building a full-track tensor.
    """
    import torch
    import torchaudio
    from demucs.apply import apply_model
    from demucs.audio import convert_audio, save_audio
    from demucs.pretrained import get_model

    weights_path = download_guitar_ft_weights()
    model = get_model("htdemucs_6s")
    state_dict = remap_guitar_ft_state_dict(
        load_guitar_ft_state_dict(weights_path),
        set(model.state_dict().keys()),
    )
    model.load_state_dict(state_dict)
    model.eval()

    dev_name = device
    if dev_name == "cuda" and not torch.cuda.is_available():
        dev_name = "cpu"
    dev = torch.device(dev_name)
    model.to(dev)

    shifts = int({"fast": 0, "balanced": 1, "high": 3, "extreme": 5}.get(quality, 0))
    overlap = {"fast": 0.25, "balanced": 0.25, "high": 0.5, "extreme": 0.75}.get(
        quality, 0.25
    )

    wav, sr = torchaudio.load(str(audio_path))
    wav = convert_audio(wav, sr, model.samplerate, model.audio_channels)
    ref = wav.mean(0)
    wav = (wav - ref.mean()) / (ref.std() + 1e-8)

    apply_kwargs: dict = {
        "device": dev,
        "shifts": shifts,
        "overlap": overlap,
        "split": True,
        "progress": False,
        "num_workers": max(0, int(jobs)),
    }
    if segment is not None and int(segment) > 0:
        apply_kwargs["segment"] = float(segment)

    with torch.no_grad():
        sources = apply_model(model, wav[None], **apply_kwargs)[0]
    sources = sources * ref.std() + ref.mean()

    track_name = audio_path.stem
    out_dir = output_root / "htdemucs_6s" / track_name
    out_dir.mkdir(parents=True, exist_ok=True)
    for source, name in zip(sources, model.sources):
        save_audio(source, str(out_dir / f"{name}.wav"), samplerate=model.samplerate)


def run_demucs(demucs_args: list[str]) -> None:
    """
    Run Demucs with CLI-style args (everything after ``python -m demucs``).

    When frozen (PyInstaller), invokes ``demucs.separate.main`` in-process because
    ``sys.executable`` is the app binary and cannot run ``-m demucs``.
    Otherwise uses a subprocess so tests and local runs keep the same isolation.
    """
    if getattr(sys, "frozen", False):
        from demucs.separate import main as demucs_main

        try:
            demucs_main(demucs_args)
        except SystemExit as exc:
            code = exc.code
            if code not in (0, None):
                raise RuntimeError(f"Demucs failed with exit code {code}") from exc
        return

    cmd = [sys.executable, "-m", "demucs", *demucs_args]
    result = subprocess.run(cmd, capture_output=True, text=True, **subprocess_run_kwargs())
    if result.returncode != 0:
        raise RuntimeError(f"Demucs failed: {result.stderr or result.stdout}")


def _maybe_refine_guitar_stem(
    guitar_path: Path,
    residual_path: Path | None,
    *,
    device: str,
    guitar_refine: bool,
    model: str,
) -> None:
    """Run MelBand refine while ``residual_path`` (``other``) still exists."""
    if not guitar_refine or model == "melband_roformer_guitar":
        return
    from audio_to_tab.roformer import (
        ROFORMER_INSTALL_HINT,
        is_guitar_refine_available,
        run_guitar_refine,
    )

    if not is_guitar_refine_available():
        logger.warning(
            "guitar refine requested but no RoFormer extra is installed; skipping. %s",
            ROFORMER_INSTALL_HINT,
        )
        return
    residual = residual_path if residual_path is not None and residual_path.is_file() else None
    try:
        from audio_to_tab.isolate import ensure_guitar_prerefine_backup, save_guitar_refined_backup

        ensure_guitar_prerefine_backup(guitar_path)
        run_guitar_refine(guitar_path, guitar_path, residual_path=residual, device=device)
        save_guitar_refined_backup(guitar_path)
    except Exception as exc:
        logger.warning("guitar refine failed; keeping first-pass guitar stem: %s", exc)


def _run_demucs_guitar_cli(
    src: Path,
    tmp_path: Path,
    *,
    model: str,
    device: str,
    quality: str,
    demucs_segment: int | None,
    demucs_jobs: int,
) -> None:
    from audio_to_tab.isolate import effective_demucs_segment

    shifts = {"fast": "0", "balanced": "1", "high": "3", "extreme": "5"}.get(quality, "0")
    overlap = {"fast": "0.25", "balanced": "0.25", "high": "0.5", "extreme": "0.75"}.get(
        quality, "0.25"
    )
    demucs_args = [
        "-n",
        model,
        "-d",
        device,
        "-o",
        str(tmp_path),
        "--shifts",
        shifts,
        "--overlap",
        overlap,
        "--jobs",
        str(max(1, int(demucs_jobs))),
    ]
    segment = effective_demucs_segment(model, demucs_segment)
    if segment is not None:
        demucs_args.extend(["--segment", str(segment)])
    demucs_args.append(str(src))
    run_demucs(demucs_args)


def separate_guitar_stem(
    audio_path: str | Path,
    output_path: str | Path | None = None,
    *,
    model: str = "htdemucs_6s",
    device: str = "cpu",
    quality: str = "fast",
    demucs_segment: int | None = 8,
    demucs_jobs: int = 1,
    guitar_refine: bool = False,
    guitar_checkpoint: str | None = None,
    fold_other_mode: str | None = None,
    sub_bass_debleed: bool = False,
    low_end_restore_db: float = 0.0,
    recovery_diagnostics_path: Path | None = None,
) -> Path:
    """
    Extract guitar stem using Demucs CLI (or an opt-in RoFormer backend).

    quality presets mirror TabGrabber: fast | balanced | high | extreme.
    ``demucs_segment`` / ``demucs_jobs`` match the isolate path so this is not
    a full-track tensor (isolate defaults: segment 8s clamped per model, jobs 1).
    ``fold_other_mode`` is accepted for API parity; the tab path does not fold.
    """
    del fold_other_mode  # tab path keeps guitar only; isolate handles fold.
    from audio_to_tab.isolate import apply_guitar_low_end_recovery
    from audio_to_tab.isolate import DEMUCS_MODELS, effective_demucs_segment
    from audio_to_tab.roformer import (
        ROFORMER_INSTALL_HINT,
        ROFORMER_MODELS,
        collect_named_stems,
        is_roformer_backend_available,
        run_roformer_model,
    )

    src = Path(audio_path)
    if output_path is None:
        out = Path(tempfile.mkstemp(suffix="_guitar.wav", prefix="stem_")[1])
    else:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

    resolved_model = model
    if resolved_model in ROFORMER_MODELS and not is_roformer_backend_available():
        logger.warning(
            "RoFormer backend missing; falling back to htdemucs_6s. %s",
            ROFORMER_INSTALL_HINT,
        )
        resolved_model = "htdemucs_6s"
        guitar_refine = False

    def _apply_low_end_recovery(stems: dict[str, Path]) -> None:
        if not sub_bass_debleed and not low_end_restore_db:
            return
        recovery = apply_guitar_low_end_recovery(
            out,
            out,
            bass_path=stems.get("bass"),
            drums_path=stems.get("drums"),
            sub_bass_debleed=sub_bass_debleed,
            boost_db=low_end_restore_db,
        )
        if recovery.attempted:
            logger.debug("tab guitar low-end recovery: %s", recovery.reason)
            if recovery_diagnostics_path is not None:
                recovery.write_json(recovery_diagnostics_path)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        if resolved_model in ROFORMER_MODELS:
            run_roformer_model(src, tmp_path, model=resolved_model, device=device)
            found = collect_named_stems(tmp_path, ("guitar", "other", "bass", "drums"))
            if "guitar" not in found:
                raise FileNotFoundError(
                    f"Separator did not produce a guitar stem for model {resolved_model}."
                )
            shutil.copy2(found["guitar"], out)
            _maybe_refine_guitar_stem(
                out,
                found.get("other"),
                device=device,
                guitar_refine=guitar_refine,
                model=resolved_model,
            )
            _apply_low_end_recovery(found)
            return out

        if resolved_model not in DEMUCS_MODELS:
            raise ValueError(f"Unsupported model {resolved_model!r}")

        if not is_demucs_available():
            raise RuntimeError(
                "Demucs is not installed. Install with: pip install -r requirements-demucs.txt"
            )

        used_guitar_ft = False
        want_guitar_ft = (
            guitar_checkpoint == GUITAR_FT_CHECKPOINT_ID
            and resolved_model == "htdemucs_6s"
        )
        if want_guitar_ft and not guitar_ft_weights_cached():
            logger.warning(GUITAR_FT_CACHE_HINT)
        elif want_guitar_ft:
            try:
                run_demucs_guitar_ft_inprocess(
                    src,
                    tmp_path,
                    device=device,
                    quality=quality,
                    segment=effective_demucs_segment(resolved_model, demucs_segment),
                    jobs=max(1, int(demucs_jobs)),
                )
                used_guitar_ft = True
            except Exception as exc:
                logger.warning(
                    "guitar-ft separation failed; falling back to stock 6s: %s", exc
                )

        if not used_guitar_ft:
            _run_demucs_guitar_cli(
                src,
                tmp_path,
                model=resolved_model,
                device=device,
                quality=quality,
                demucs_segment=demucs_segment,
                demucs_jobs=demucs_jobs,
            )

        guitar_files = list(tmp_path.rglob("guitar.wav"))
        if not guitar_files:
            raise FileNotFoundError(
                "Demucs did not produce a guitar stem. "
                "Ensure model supports guitar separation (htdemucs_6s)."
            )
        other_files = list(tmp_path.rglob("other.wav"))
        bass_files = list(tmp_path.rglob("bass.wav"))
        drum_files = list(tmp_path.rglob("drums.wav"))
        shutil.copy2(guitar_files[0], out)
        _maybe_refine_guitar_stem(
            out,
            other_files[0] if other_files else None,
            device=device,
            guitar_refine=guitar_refine,
            model=resolved_model,
        )
        stem_refs = {
            "guitar": guitar_files[0],
            "other": other_files[0] if other_files else None,
            "bass": bass_files[0] if bass_files else None,
            "drums": drum_files[0] if drum_files else None,
        }
        _apply_low_end_recovery({k: v for k, v in stem_refs.items() if v is not None})

    return out

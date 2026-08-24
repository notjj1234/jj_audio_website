"""Pure helpers for isolate page upload/result state and separation progress."""

from __future__ import annotations

from collections.abc import MutableMapping
from pathlib import Path
from typing import Any

from audio_to_tab.hardware import HostProbe, resolve_desktop_speed

ISOLATION_STAGE_ORDER = (
    "ingest",
    "separate",
    "collect",
    "bass_bleed",
    "guitar_split",
    "presence",
    "done",
)

STAGE_WEIGHTS: dict[str, float] = {
    "ingest": 0.05,
    "separate": 0.75,
    "collect": 0.05,
    "bass_bleed": 0.05,
    "guitar_split": 0.05,
    "presence": 0.03,
    "done": 0.02,
}

# Checklist labels (short). Header copy for the current stage stays in isolate.py.
STAGE_CHECKLIST_LABELS: dict[str, str] = {
    "ingest": "Prepare audio",
    "separate": "Separate tracks",
    "collect": "Collect tracks",
    "bass_bleed": "Check guitar",
    "guitar_split": "Split lead / rhythm",
    "presence": "Check which tracks have sound",
    "done": "Finish",
}

_GUITAR_ONLY_STAGES = frozenset({"bass_bleed", "guitar_split"})

# Wall-clock vs audio length for the Demucs `separate` stage at quality=fast.
# Fast CPU is roughly 1× the clip (docs: about as long as the song).
_DEVICE_REALTIME = {"cpu": 1.0, "cuda": 0.25, "mps": 0.8}
# Extra work from Demucs --shifts (QUALITY_SHIFTS in isolate.py).
_QUALITY_TIME_FACTOR = {"fast": 1.0, "balanced": 2.0, "high": 4.0, "extreme": 6.0}
_INTRA_STAGE_CAP = 0.95
_GUITAR_MODEL_MARKERS = ("6s", "guitar")

# Plain-language separation presets → Demucs engine settings.
# Keys are stable UI ids; labels/descriptions are user-facing.
SEPARATION_PRESETS: dict[str, dict[str, Any]] = {
    # Stage-1 default stays htdemucs_6s (only official Demucs checkpoint with a
    # guitar stem). Do not swap to htdemucs_ft for Full band — see
    # eval/lead_rhythm/RESEARCH.md.
    "full_band": {
        "label": "Full band",
        "tracks": "Vocals, Drums, Bass, Guitar, Piano, Other",
        "track_count": 6,
        "model": "htdemucs_6s",
        "two_stems": None,
        "caveat": "Guitar/piano less accurate.",
    },
    "essential": {
        "label": "Essential tracks",
        "tracks": "Vocals, Drums, Bass, Other",
        "track_count": 4,
        "model": "htdemucs",
        "two_stems": None,
        "caveat": "",
    },
    "vocals_music": {
        "label": "Vocals & music",
        "tracks": "Vocals, Instrumental",
        "track_count": 2,
        "model": "htdemucs",
        "two_stems": "vocals",
        "caveat": "",
    },
    "custom": {
        "label": "Custom",
        "tracks": "Pick your own instruments",
        "track_count": None,
        "model": "htdemucs",
        "two_stems": None,
        "caveat": "",
    },
}

DEFAULT_SEPARATION_PRESET = "full_band"

# Instruments a Custom run can ask for → the stem files that satisfy each pick.
CUSTOM_STEM_CHOICES: dict[str, str] = {
    "vocals": "Vocals",
    "drums": "Drums",
    "bass": "Bass",
    "guitar": "Guitar",
    "piano": "Piano",
    "other": "Other",
}

CUSTOM_STEM_OUTPUTS: dict[str, tuple[str, ...]] = {
    "vocals": ("vocals",),
    "drums": ("drums",),
    "bass": ("bass",),
    "guitar": ("guitar", "lead_guitar", "rhythm_guitar"),
    "piano": ("piano",),
    "other": ("other",),
}

DEFAULT_CUSTOM_STEMS = ("vocals", "guitar")

CUSTOM_CAVEAT = ""

# Auto is the default: quality/device come from audio_to_tab.hardware on this PC.
SPEED_PRESETS: dict[str, dict[str, Any]] = {
    "auto": {
        "label": "Auto",
        "quality": "fast",
        "device": "cpu",
        "help": "",
    },
    "faster": {
        "label": "Faster",
        "quality": "fast",
        "device": "cpu",
        "help": "",
    },
    "balanced": {
        "label": "Balanced",
        "quality": "balanced",
        "device": "cpu",
        "help": "",
    },
    "best": {
        "label": "Best",
        "quality": "high",
        "device": "cpu",
        "help": "",
    },
}

DEFAULT_SPEED_PRESET = "auto"


def resolve_speed_preset(preset_id: str, probe=None, *, platform: str | None = None) -> dict[str, Any]:
    """Map a UI speed preset id to Demucs quality + device for this host."""
    host = probe if probe is not None else HostProbe(cuda=False, mps=False, ram_gb=None)
    resolved = resolve_desktop_speed(preset_id, host, platform=platform)
    known = preset_id if preset_id in SPEED_PRESETS else DEFAULT_SPEED_PRESET
    label = SPEED_PRESETS[known]["label"]
    return {
        "id": resolved["id"],
        "label": label,
        "quality": resolved["quality"],
        "device": resolved["device"],
        "help": resolved.get("help", ""),
    }


def default_region_end(duration_sec: float, *, min_length: float = 30.0) -> float:
    """Pick a sensible default section end for the region slider."""
    if duration_sec <= min_length:
        return duration_sec
    return min(duration_sec, min_length)


def clamp_region_bounds(
    start_sec: float,
    end_sec: float,
    duration_sec: float,
    *,
    min_length: float = 5.0,
) -> tuple[float, float]:
    """Clamp start/end to file bounds with minimum region length."""
    start = max(0.0, min(start_sec, duration_sec))
    end = max(start + min_length, min(end_sec, duration_sec))
    if end > duration_sec:
        end = duration_sec
        start = max(0.0, end - min_length)
    return start, end


def resolve_separation_preset(preset_id: str) -> dict[str, Any]:
    """
    Map a UI preset id to engine settings.

    Returns a dict with ``model`` and ``two_stems`` (possibly None), plus
    the preset's display metadata. Unknown ids fall back to the default.
    """
    preset = SEPARATION_PRESETS.get(preset_id) or SEPARATION_PRESETS[DEFAULT_SEPARATION_PRESET]
    return {
        "id": preset_id if preset_id in SEPARATION_PRESETS else DEFAULT_SEPARATION_PRESET,
        "label": preset["label"],
        "tracks": preset["tracks"],
        "track_count": preset["track_count"],
        "model": preset["model"],
        "two_stems": preset["two_stems"],
        "caveat": preset["caveat"],
    }


def resolve_custom_separation(stems: Any) -> dict[str, Any]:
    """
    Map Custom instrument picks to the smallest Demucs setup that covers them.

    Guitar or piano needs the 6-stem model; vocals alone can use the cheap
    two-stem split; anything else fits the 4-stem model. Raises ``ValueError``
    when nothing is picked.
    """
    wanted = {s for s in stems if s in CUSTOM_STEM_CHOICES}
    picked = [s for s in CUSTOM_STEM_CHOICES if s in wanted]
    if not picked:
        raise ValueError("Pick at least one instrument to separate.")

    if wanted == {"vocals"}:
        model, two_stems = "htdemucs", "vocals"
    elif wanted & {"guitar", "piano"}:
        model, two_stems = "htdemucs_6s", None
    else:
        model, two_stems = "htdemucs", None

    return {
        "id": "custom",
        "label": SEPARATION_PRESETS["custom"]["label"],
        "tracks": ", ".join(CUSTOM_STEM_CHOICES[s] for s in picked),
        "track_count": len(picked),
        "model": model,
        "two_stems": two_stems,
        "stems": picked,
        "caveat": CUSTOM_CAVEAT,
    }


def custom_selected_stems(
    produced_stem_names: Any,
    picked_stems: Any,
) -> dict[str, bool]:
    """
    Mixer/download selection after a Custom run: on for what the user asked for.

    Combined Guitar is dropped when the Lead/Rhythm split produced both halves,
    matching the default behaviour of the other presets.
    """
    produced = list(produced_stem_names)
    wanted: set[str] = set()
    for pick in picked_stems:
        wanted.update(CUSTOM_STEM_OUTPUTS.get(pick, ()))

    selected = {name: name in wanted for name in produced}
    if not any(selected.values()):
        return {name: True for name in produced}
    if selected.get("lead_guitar") and selected.get("rhythm_guitar"):
        if "guitar" in selected:
            selected["guitar"] = False
    return selected


def upload_fingerprint(uploaded: Any) -> str | None:
    """Fingerprint a Streamlit UploadedFile (name + size), or None if absent."""
    if uploaded is None:
        return None
    name = getattr(uploaded, "name", None)
    size = getattr(uploaded, "size", None)
    if not name:
        return None
    return f"{name}:{size}"


def sync_output_name_on_upload(
    uploaded: Any,
    *,
    last_fp: str | None,
    output_name: str,
) -> tuple[str | None, str, bool]:
    """
    When the user picks a new file, return updated fingerprint and output name.

    Returns ``(new_fp, output_name, changed)``.
    """
    fp = upload_fingerprint(uploaded)
    if fp is None or fp == last_fp:
        return fp, output_name, False
    new_name = Path(uploaded.name).stem
    return fp, new_name, True


ISOLATE_OUTPUT_NAME_KEY = "isolate_output_name"
ISOLATE_OUTPUT_NAME_PENDING_KEY = "isolate_output_name_pending"


def queue_reopen_output_name(session: MutableMapping[str, object], title: str) -> None:
    """Stash a Reopen title for the next run. MUST NOT write the widget-bound key."""
    session[ISOLATE_OUTPUT_NAME_PENDING_KEY] = title


def apply_pending_output_name(session: MutableMapping[str, object]) -> str | None:
    """Copy pending title onto the widget key. Call before ``st.text_input`` exists."""
    pending = session.pop(ISOLATE_OUTPUT_NAME_PENDING_KEY, None)
    if pending is None:
        return None
    name = str(pending)
    session[ISOLATE_OUTPUT_NAME_KEY] = name
    return name


def should_hide_stale_results(
    *,
    pending_upload_fp: str | None,
    has_artifacts: bool,
) -> bool:
    """True when a new upload is queued but prior separation results are still loaded."""
    return bool(has_artifacts and pending_upload_fp is not None)


def expects_guitar_stem(
    *,
    model: str,
    two_stems: str | None = None,
    custom_stems: Any = None,
) -> bool:
    """True when this job is expected to produce a guitar stem (bass/split stages)."""
    if two_stems:
        return False
    picked = [s for s in (custom_stems or []) if s]
    if picked:
        return "guitar" in picked
    lowered = (model or "").lower()
    return any(marker in lowered for marker in _GUITAR_MODEL_MARKERS)


def isolation_stages_for_job(*, expects_guitar: bool) -> tuple[str, ...]:
    """Stages that will actually run for this job."""
    if expects_guitar:
        return ISOLATION_STAGE_ORDER
    return tuple(s for s in ISOLATION_STAGE_ORDER if s not in _GUITAR_ONLY_STAGES)


def resolve_active_stage(stage: str, stages: tuple[str, ...]) -> str:
    """Map a pipeline stage onto the job's visible stage list."""
    if stage in stages:
        return stage
    if not stages:
        return "ingest"
    if stage not in ISOLATION_STAGE_ORDER:
        return stages[0]
    idx = ISOLATION_STAGE_ORDER.index(stage)
    for later in ISOLATION_STAGE_ORDER[idx + 1 :]:
        if later in stages:
            return later
    return stages[-1]


def stage_progress_percent(
    stage: str,
    *,
    weights: dict[str, float] | None = None,
    stages: tuple[str, ...] | None = None,
    intra: float = 0.0,
) -> float:
    """Weighted progress (0.0–1.0): prior stages + ``intra`` of the current stage.

    ``intra`` is 0 at the start of a stage and 1 when that stage has finished.
    """
    order = stages or ISOLATION_STAGE_ORDER
    w = weights or STAGE_WEIGHTS
    total = sum(w.get(s, 0.0) for s in order)
    if total <= 0:
        return 0.0
    active = resolve_active_stage(stage, order)
    if active not in order:
        return 0.0
    idx = order.index(active)
    prior = sum(w.get(order[i], 0.0) for i in range(idx))
    current = w.get(active, 0.0)
    frac = min(1.0, max(0.0, intra))
    return min(1.0, (prior + current * frac) / total)


def intra_stage_fraction(
    elapsed_in_stage_sec: float,
    estimated_stage_sec: float | None,
) -> tuple[float, bool]:
    """Progress within the current stage. Caps below 1 so we never invent completion.

    Returns ``(fraction, is_estimated)``. ``is_estimated`` is True when a duration
    guess was used. Without a guess, fraction stays 0.
    """
    if estimated_stage_sec is None or estimated_stage_sec <= 0:
        return 0.0, False
    if elapsed_in_stage_sec <= 0:
        return 0.0, True
    return min(_INTRA_STAGE_CAP, elapsed_in_stage_sec / estimated_stage_sec), True


def estimated_stage_seconds(
    stage: str,
    stages: tuple[str, ...],
    total_job_sec: float | None,
    *,
    weights: dict[str, float] | None = None,
) -> float | None:
    """Share of the job estimate that belongs to ``stage``."""
    if total_job_sec is None or total_job_sec <= 0:
        return None
    w = weights or STAGE_WEIGHTS
    total_w = sum(w.get(s, 0.0) for s in stages)
    if total_w <= 0:
        return None
    return total_job_sec * (w.get(stage, 0.0) / total_w)


def estimate_job_seconds(
    *,
    audio_duration_sec: float | None,
    quality: str,
    device: str,
    stages: tuple[str, ...],
    last_run: dict[str, Any] | None = None,
    model: str | None = None,
    expects_guitar: bool | None = None,
) -> tuple[float | None, str]:
    """Predicted wall time for the whole job.

    Uses a prior run when quality/device/model match (confidence ``high``),
    otherwise a clip-length × quality × device heuristic (``low``).
    """
    if last_run:
        same_setup = (
            last_run.get("quality") == quality
            and last_run.get("device") == device
            and (model is None or last_run.get("model") == model)
            and (expects_guitar is None or bool(last_run.get("expects_guitar")) == bool(expects_guitar))
        )
        last_audio = float(last_run.get("audio_sec") or 0.0)
        last_wall = float(last_run.get("wall_sec") or 0.0)
        if (
            same_setup
            and last_audio > 0.5
            and last_wall > 0.5
            and audio_duration_sec
            and audio_duration_sec > 0
        ):
            return last_wall * (audio_duration_sec / last_audio), "high"

    if not audio_duration_sec or audio_duration_sec <= 0:
        return None, "low"

    q = _QUALITY_TIME_FACTOR.get(quality, 1.0)
    d = _DEVICE_REALTIME.get(device, _DEVICE_REALTIME["cpu"])
    separate_sec = audio_duration_sec * q * d
    sep_w = STAGE_WEIGHTS["separate"]
    active_w = sum(STAGE_WEIGHTS.get(s, 0.0) for s in stages)
    if sep_w <= 0 or active_w <= 0:
        return separate_sec, "low"
    return separate_sec * (active_w / sep_w), "low"


def estimate_remaining_seconds(
    *,
    elapsed_sec: float,
    percent: float,
    total_estimate: float | None,
    confidence: str,
) -> tuple[float | None, str]:
    """Seconds left. Prefers observed rate once enough progress exists."""
    if percent >= 0.995:
        return 0.0, "high"
    observed: float | None = None
    if elapsed_sec >= 3.0 and percent >= 0.03:
        observed = elapsed_sec * (1.0 - percent) / percent
    planned: float | None = None
    if total_estimate is not None:
        planned = max(0.0, total_estimate - elapsed_sec)
    if observed is None and planned is None:
        return None, "low"
    if observed is None:
        return planned, confidence
    if planned is None:
        return observed, "high" if elapsed_sec >= 8 else "low"
    blend = min(1.0, elapsed_sec / 20.0)
    mixed = (1.0 - blend) * planned + blend * observed
    out_conf = "high" if confidence == "high" or elapsed_sec >= 8 else "low"
    return max(0.0, mixed), out_conf


def checklist_items(
    stages: tuple[str, ...],
    current_stage: str,
    *,
    labels: dict[str, str] | None = None,
    complete: bool = False,
) -> list[dict[str, str]]:
    """Per-stage rows with state ``done``, ``current``, or ``pending``."""
    names = labels or STAGE_CHECKLIST_LABELS
    active = resolve_active_stage(current_stage, stages)
    idx = stages.index(active) if active in stages else 0
    items: list[dict[str, str]] = []
    for i, stage in enumerate(stages):
        if complete or i < idx:
            state = "done"
        elif i == idx:
            state = "current"
        else:
            state = "pending"
        items.append(
            {
                "id": stage,
                "label": names.get(stage, stage),
                "state": state,
            }
        )
    return items


def format_checklist_markdown(items: list[dict[str, str]]) -> str:
    """Plain-text checklist that does not rely on clickable Streamlit widgets."""
    marks = {"done": "[done]", "current": "[now]", "pending": "[todo]"}
    lines = []
    for item in items:
        mark = marks.get(item["state"], "[todo]")
        label = item["label"]
        if item["state"] == "current":
            lines.append(f"{mark} **{label}**")
        else:
            lines.append(f"{mark} {label}")
    return "\n\n".join(lines)


def format_progress_label(
    percent: float, message: str, *, estimated: bool = False
) -> str:
    """Human-readable progress line, e.g. ``42% — Running Demucs…``."""
    pct = int(round(percent * 100))
    prefix = f"~{pct}%" if estimated else f"{pct}%"
    return f"{prefix} — {message}"


def format_elapsed(seconds: float) -> str:
    """Format elapsed seconds as M:SS."""
    if seconds < 0:
        seconds = 0
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m}:{s:02d}"


def format_eta_line(
    elapsed_sec: float,
    remaining_sec: float | None,
    *,
    confidence: str = "low",
) -> str:
    """Elapsed plus remaining, e.g. ``Elapsed 0:09 · ~2:40 left``."""
    elapsed = format_elapsed(elapsed_sec)
    if remaining_sec is None:
        return f"Elapsed {elapsed} · estimating…"
    if remaining_sec <= 0.5:
        return f"Elapsed {elapsed}"
    left = format_elapsed(remaining_sec)
    _ = confidence  # always ~ ; low confidence uses estimating… when remaining is None
    return f"Elapsed {elapsed} · ~{left} left"

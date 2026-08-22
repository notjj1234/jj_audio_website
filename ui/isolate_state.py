"""Pure helpers for isolate page upload/result state and separation progress."""

from __future__ import annotations

from pathlib import Path
from typing import Any

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

# Plain-language separation presets → Demucs engine settings.
# Keys are stable UI ids; labels/descriptions are user-facing.
SEPARATION_PRESETS: dict[str, dict[str, Any]] = {
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

# Plain-language speed presets for Streamlit (local; backend modes not bundled in desktop).
SPEED_PRESETS: dict[str, dict[str, Any]] = {
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

DEFAULT_SPEED_PRESET = "faster"


def resolve_speed_preset(preset_id: str) -> dict[str, Any]:
    """Map a UI speed preset id to Demucs quality + device settings."""
    preset = SPEED_PRESETS.get(preset_id) or SPEED_PRESETS[DEFAULT_SPEED_PRESET]
    return {
        "id": preset_id if preset_id in SPEED_PRESETS else DEFAULT_SPEED_PRESET,
        "label": preset["label"],
        "quality": preset["quality"],
        "device": preset["device"],
        "help": preset.get("help", ""),
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


def should_hide_stale_results(
    *,
    pending_upload_fp: str | None,
    has_artifacts: bool,
) -> bool:
    """True when a new upload is queued but prior separation results are still loaded."""
    return bool(has_artifacts and pending_upload_fp is not None)


def stage_progress_percent(stage: str, *, weights: dict[str, float] | None = None) -> float:
    """Cumulative weighted progress (0.0–1.0) through isolation stages."""
    w = weights or STAGE_WEIGHTS
    total = sum(w.get(s, 0.0) for s in ISOLATION_STAGE_ORDER)
    if total <= 0:
        return 0.0
    if stage not in ISOLATION_STAGE_ORDER:
        return 0.0
    idx = ISOLATION_STAGE_ORDER.index(stage)
    done = sum(w.get(ISOLATION_STAGE_ORDER[i], 0.0) for i in range(idx + 1))
    return min(1.0, done / total)


def format_progress_label(percent: float, message: str) -> str:
    """Human-readable progress line, e.g. ``42% — Running Demucs…``."""
    pct = int(round(percent * 100))
    return f"{pct}% — {message}"


def format_elapsed(seconds: float) -> str:
    """Format elapsed seconds as M:SS."""
    if seconds < 0:
        seconds = 0
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m}:{s:02d}"

"""Pure helpers for isolate page upload/result state and separation progress."""

from __future__ import annotations

import json
from collections.abc import MutableMapping
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from audio_to_tab.hardware import HostProbe, resolve_desktop_speed
from audio_to_tab.isolate import effective_isolation_quality

ISOLATION_STAGE_ORDER = (
    "ingest",
    "separate",
    "collect",
    "bass_bleed",
    "presence",
    "done",
)

STAGE_WEIGHTS: dict[str, float] = {
    "ingest": 0.05,
    "separate": 0.80,
    "collect": 0.05,
    "guitar_refine": 0.15,
    "bass_bleed": 0.05,
    "presence": 0.03,
    "done": 0.02,
}

# One-line user labels. Behind-the-scenes stages reuse "Separate tracks".
STAGE_CHECKLIST_LABELS: dict[str, str] = {
    "ingest": "Prepare audio",
    "separate": "Separate tracks",
    "collect": "Separate tracks",
    "guitar_refine": "Refine guitar",
    "bass_bleed": "Separate tracks",
    "presence": "Separate tracks",
    "done": "Finish",
}

_GUITAR_ONLY_STAGES = frozenset({"bass_bleed"})

# Wall-clock vs audio length for the Demucs `separate` stage at quality=fast.
# Fast CPU is roughly 1× the clip (docs: about as long as the song).
_DEVICE_REALTIME = {"cpu": 1.0, "cuda": 0.25, "mps": 0.8}
# Extra work from Demucs --shifts (QUALITY_SHIFTS in isolate.py).
_QUALITY_TIME_FACTOR = {"fast": 1.0, "balanced": 2.0, "high": 4.0, "extreme": 6.0}
_INTRA_STAGE_CAP = 0.95
_GUITAR_MODEL_MARKERS = ("6s", "guitar", "roformer")

# Labeled track picks → one resolved pipeline (see resolve_track_selection).
TRACK_OPTIONS: dict[str, dict[str, Any]] = {
    "vocals_demucs": {
        "label": "Vocals (Demucs)",
        "stem": "vocals",
    },
    "drums_demucs": {
        "label": "Drums (Demucs)",
        "stem": "drums",
    },
    "bass_demucs": {
        "label": "Bass (Demucs)",
        "stem": "bass",
    },
    "other_demucs": {
        "label": "Other (Demucs)",
        "stem": "other",
    },
    "piano_demucs": {
        "label": "Piano (Demucs 6-stem)",
        "stem": "piano",
    },
    "guitar_demucs_6s": {
        "label": "Guitar (Demucs 6-stem, weaker)",
        "stem": "guitar",
    },
    "guitar_roformer": {
        "label": "Guitar (BS-RoFormer, better, slower)",
        "stem": "guitar",
    },
    "guitar_roformer_refine": {
        "label": "Guitar (BS-RoFormer + MelBand refine, best, slowest)",
        "stem": "guitar",
    },
    "vocals_instrumental_demucs": {
        "label": "Vocals & instrumental (Demucs 2-stem)",
        "stem": "vocals",
    },
}

GUITAR_TRACK_OPTION_IDS = frozenset(
    {"guitar_demucs_6s", "guitar_roformer", "guitar_roformer_refine"}
)
GUITAR_TRACK_RADIO_ORDER = (
    "guitar_demucs_6s",
    "guitar_roformer",
    "guitar_roformer_refine",
)
DEMUCS_STEM_CHECKBOX_IDS = (
    "vocals_demucs",
    "drums_demucs",
    "bass_demucs",
    "piano_demucs",
    "other_demucs",
)
VOCALS_INSTRUMENTAL_OPTION_ID = "vocals_instrumental_demucs"
DEFAULT_TRACK_OPTIONS = ("vocals_demucs", "guitar_demucs_6s")

ROFORMER_DOWNLOAD_CAVEAT = (
    "Downloads ~700 MB BS-RoFormer-SW weights on first use, then a guitar "
    "specialist (~45 MB). Much slower on CPU. Community weights have no stated "
    "license — use accordingly."
)
ROFORMER_MIXED_STEMS_NOTE = (
    "All stems are separated in one BS-RoFormer pass; unselected stems are discarded."
)
TRACKS_PICKER_HELP = (
    "Pick the stems you want. Guitar can use Demucs (faster) or BS-RoFormer "
    "(better quality, much slower on CPU)."
)

ROFORMER_GUITAR_OPTION_IDS = frozenset({"guitar_roformer", "guitar_roformer_refine"})
ROFORMER_MODEL_IDS = frozenset({"bs_roformer_sw", "melband_roformer_guitar"})
ROFORMER_BACKEND_UI_HINT = (
    "BS-RoFormer guitar options need the optional runtime. "
    "In your app Python environment run: `pip install bs-roformer-infer`."
)


def guitar_track_radio_ids(*, roformer_available: bool) -> tuple[str, ...]:
    """Radio keys for the Guitar row: ``none`` plus engines available on this host."""
    if roformer_available:
        return ("none", *GUITAR_TRACK_RADIO_ORDER)
    return ("none", "guitar_demucs_6s")


def normalize_guitar_track_selection(guitar: str, *, roformer_available: bool) -> str:
    """Map persisted RoFormer picks to Demucs when the backend is missing."""
    pick = (guitar or "none").strip()
    if pick in ROFORMER_GUITAR_OPTION_IDS and not roformer_available:
        return "guitar_demucs_6s"
    if pick == "none" or pick in GUITAR_TRACK_OPTION_IDS:
        return pick
    return "none"


def tracks_picker_help(*, roformer_available: bool) -> str:
    if roformer_available:
        return TRACKS_PICKER_HELP
    return (
        "Pick the stems you want. Guitar uses Demucs only until BS-RoFormer is installed "
        "(pip install bs-roformer-infer in your app environment)."
    )


def job_requires_roformer_backend(model: str) -> bool:
    return (model or "").strip().lower() in ROFORMER_MODEL_IDS

# Legacy preset ids → track option ids (session migration / tests only).
LEGACY_PRESET_TRACK_OPTIONS: dict[str, tuple[str, ...]] = {
    "full_band": (
        "vocals_demucs",
        "drums_demucs",
        "bass_demucs",
        "guitar_roformer",
    ),
    "best_guitar": (
        "vocals_demucs",
        "drums_demucs",
        "bass_demucs",
        "guitar_roformer_refine",
    ),
    "essential": (
        "vocals_demucs",
        "drums_demucs",
        "bass_demucs",
        "other_demucs",
    ),
    "vocals_music": (VOCALS_INSTRUMENTAL_OPTION_ID,),
}

# Internal migration only — not shown in UI.
SEPARATION_PRESETS: dict[str, dict[str, Any]] = {
    "full_band": {"label": "Full band"},
    "essential": {"label": "Essential tracks"},
    "vocals_music": {"label": "Vocals & music"},
    "custom": {"label": "Custom"},
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
    "guitar": ("guitar",),
    "piano": ("piano",),
    "other": ("other",),
}

DEFAULT_CUSTOM_STEMS = ("vocals", "guitar")

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

DEFAULT_SPEED_PRESET = "balanced"


def resolve_isolate_user_id(session: MutableMapping[str, Any], stored: str | None) -> str:
    """Pick a library owner id without waiting on browser localStorage.

    Prefers an existing session id, then a stored browser id, else mints one.
    Never sleeps or reruns.
    """
    cached = session.get("isolate_user_id")
    if isinstance(cached, str) and cached.strip():
        return cached.strip()
    if isinstance(stored, str) and stored.strip():
        user_id = stored.strip()
        session["isolate_user_id"] = user_id
        return user_id
    user_id = uuid4().hex
    session["isolate_user_id"] = user_id
    return user_id


def resolve_speed_preset(
    preset_id: str,
    probe=None,
    *,
    platform: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """Map a UI speed preset id to Demucs quality + device for this host.

    Unknown ids fall back to Balanced. Faster keeps ``fast`` quality even on
    ``htdemucs_6s``; other speeds floor 6-stem jobs to Balanced.
    """
    host = probe if probe is not None else HostProbe(cuda=False, mps=False, ram_gb=None)
    resolved = resolve_desktop_speed(preset_id, host, platform=platform)
    known = resolved["id"] if resolved["id"] in SPEED_PRESETS else DEFAULT_SPEED_PRESET
    label = SPEED_PRESETS[known]["label"]
    quality = resolved["quality"]
    if model:
        quality = effective_isolation_quality(
            quality, model=model, speed_id=resolved["id"]
        )
    return {
        "id": known,
        "label": label,
        "quality": quality,
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


def custom_stems_to_track_options(stems: Any) -> list[str]:
    """Map legacy instrument ids to default track option ids."""
    wanted = {s for s in (stems or ()) if s in CUSTOM_STEM_CHOICES}
    if not wanted:
        raise ValueError("Pick at least one instrument to separate.")
    options: list[str] = []
    for stem_id in CUSTOM_STEM_CHOICES:
        if stem_id not in wanted:
            continue
        if stem_id == "guitar":
            options.append("guitar_demucs_6s")
        else:
            options.append(f"{stem_id}_demucs")
    return options or list(DEFAULT_TRACK_OPTIONS)


def migrate_track_options(session: MutableMapping[str, Any]) -> list[str]:
    """Resolve track option ids from session, migrating legacy preset keys."""
    current = session.get("isolate_track_options")
    if isinstance(current, (list, tuple)) and current:
        known = [str(x) for x in current if str(x) in TRACK_OPTIONS]
        if known:
            return known
    legacy_preset = session.get("isolate_separation_preset")
    if isinstance(legacy_preset, str):
        if legacy_preset == "best_guitar":
            legacy_preset = "full_band"
        mapped = LEGACY_PRESET_TRACK_OPTIONS.get(legacy_preset)
        if mapped:
            return list(mapped)
        if legacy_preset == "custom":
            return custom_stems_to_track_options(session.get("isolate_last_custom_stems"))
    return list(DEFAULT_TRACK_OPTIONS)


def _track_selection_caveat(option_ids: list[str], *, uses_roformer: bool) -> str:
    parts: list[str] = []
    if uses_roformer:
        parts.append(ROFORMER_DOWNLOAD_CAVEAT)
        non_guitar = [oid for oid in option_ids if oid not in GUITAR_TRACK_OPTION_IDS]
        if non_guitar:
            parts.append(ROFORMER_MIXED_STEMS_NOTE)
    return " ".join(parts)


def resolve_track_selection(option_ids: Any) -> dict[str, Any]:
    """Map labeled track picks to one engine config (model, emit_stems, guitar_refine)."""
    ids = [str(x) for x in (option_ids or ()) if str(x) in TRACK_OPTIONS]
    if not ids:
        raise ValueError("Pick at least one track to separate.")

    guitar_picks = [oid for oid in ids if oid in GUITAR_TRACK_OPTION_IDS]
    if len(guitar_picks) > 1:
        raise ValueError("Pick only one guitar option.")

    if VOCALS_INSTRUMENTAL_OPTION_ID in ids:
        if len(ids) > 1:
            raise ValueError("Vocals & instrumental cannot combine with other tracks.")
        return {
            "id": "custom",
            "label": "Custom",
            "tracks": TRACK_OPTIONS[VOCALS_INSTRUMENTAL_OPTION_ID]["label"],
            "track_count": 1,
            "model": "htdemucs",
            "two_stems": "vocals",
            "stems": ["vocals"],
            "emit_stems": ("vocals",),
            "track_options": list(ids),
            "fold_other_into_guitar": True,
            "fold_other_mode": "best_effort",
            "guitar_refine": False,
            "caveat": "",
        }

    emit: list[str] = []
    custom_stems: list[str] = []
    for oid in ids:
        stem = str(TRACK_OPTIONS[oid]["stem"])
        if stem not in emit:
            emit.append(stem)
        if stem in CUSTOM_STEM_CHOICES and stem not in custom_stems:
            custom_stems.append(stem)

    uses_roformer = bool(guitar_picks and guitar_picks[0] in {"guitar_roformer", "guitar_roformer_refine"})
    guitar_refine = guitar_picks == ["guitar_roformer_refine"]

    if uses_roformer:
        model = "bs_roformer_sw"
        two_stems = None
    elif {"guitar", "piano"} & set(custom_stems):
        model = "htdemucs_6s"
        two_stems = None
    else:
        model = "htdemucs"
        two_stems = None

    return {
        "id": "custom",
        "label": "Custom",
        "tracks": ", ".join(TRACK_OPTIONS[oid]["label"] for oid in ids),
        "track_count": len(ids),
        "model": model,
        "two_stems": two_stems,
        "stems": custom_stems,
        "emit_stems": tuple(emit),
        "track_options": list(ids),
        "fold_other_into_guitar": "other" not in custom_stems,
        "fold_other_mode": "best_effort",
        "guitar_refine": guitar_refine,
        "caveat": _track_selection_caveat(ids, uses_roformer=uses_roformer),
    }


def resolve_separation_preset(preset_id: str) -> dict[str, Any]:
    """Legacy preset id → engine settings via track option mapping."""
    option_ids = LEGACY_PRESET_TRACK_OPTIONS.get(preset_id)
    if option_ids is None:
        option_ids = DEFAULT_TRACK_OPTIONS
    resolved = resolve_track_selection(option_ids)
    resolved["id"] = preset_id if preset_id in SEPARATION_PRESETS else "custom"
    if preset_id in SEPARATION_PRESETS:
        resolved["label"] = SEPARATION_PRESETS[preset_id]["label"]
    return resolved


def resolve_custom_separation(stems: Any) -> dict[str, Any]:
    """Map legacy Custom instrument picks to engine settings."""
    return resolve_track_selection(custom_stems_to_track_options(stems))


def custom_selected_stems(
    produced_stem_names: Any,
    picked_stems: Any,
) -> dict[str, bool]:
    """
    Mixer/download selection after a Custom run: on for what the user asked for.

    Default path emits a single combined Guitar stem (no lead/rhythm).
    """
    produced = list(produced_stem_names)
    wanted: set[str] = set()
    for pick in picked_stems:
        wanted.update(CUSTOM_STEM_OUTPUTS.get(pick, ()))

    selected = {name: name in wanted for name in produced}
    if not any(selected.values()):
        return {name: True for name in produced}
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
ISOLATE_YOUTUBE_URL_KEY = "isolate_youtube_url"
ISOLATE_YOUTUBE_URL_PENDING_KEY = "isolate_youtube_url_pending"
ISOLATE_NAMED_YOUTUBE_URL_KEY = "isolate_named_youtube_url"
ISOLATE_AUTO_OUTPUT_NAME_KEY = "isolate_auto_output_name"


def youtube_video_id(url: str) -> str | None:
    """Video id from a watch / youtu.be / shorts / embed URL, else None."""
    parsed = urlparse((url or "").strip())
    if parsed.scheme not in {"http", "https"}:
        return None
    host = (parsed.hostname or "").lower().rstrip(".")
    if host in {"youtu.be", "www.youtu.be"}:
        vid = parsed.path.lstrip("/").split("/")[0]
        return vid or None
    if host == "youtube.com" or host.endswith(".youtube.com"):
        qs = parse_qs(parsed.query)
        if qs.get("v") and qs["v"][0]:
            return qs["v"][0]
        parts = [p for p in parsed.path.split("/") if p]
        if len(parts) >= 2 and parts[0] in {"shorts", "embed", "live"}:
            return parts[1]
    return None


def youtube_label_from_url(url: str) -> str:
    """Default Output name from a pasted URL (id until the file is downloaded)."""
    return youtube_video_id(url) or "youtube_audio"


def sync_output_name_on_youtube(
    *,
    youtube_url: str,
    last_named_url: str | None,
    output_name: str,
    auto_output_name: str | None,
    downloaded_stem: str | None = None,
) -> tuple[str, str, str, bool]:
    """When the YouTube URL changes, replace an auto Output name.

    Returns ``(name, named_url, auto_name, changed)``. A user-edited name is
    kept for the same URL; a new URL always takes the new label.
    """
    url = (youtube_url or "").strip()
    if not url:
        return output_name, last_named_url or "", auto_output_name or "", False
    label = (downloaded_stem or "").strip() or youtube_label_from_url(url)
    last = (last_named_url or "").strip()
    current = (output_name or "").strip()
    auto = (auto_output_name or "").strip()
    if last != url:
        return label, url, label, True
    if downloaded_stem and (not current or current == auto):
        stem = downloaded_stem.strip()
        return stem, url, stem, stem != current
    return output_name, last or url, auto, False


def apply_youtube_output_name_sync(
    session: MutableMapping[str, object],
    *,
    downloaded_stem: str | None = None,
    apply_now: bool = True,
) -> str | None:
    """Queue (and optionally apply) a YouTube Output name before the text_input."""
    if not session.get("isolate_youtube_enabled"):
        return None
    url = str(session.get(ISOLATE_YOUTUBE_URL_KEY) or "").strip()
    name, named_url, auto, changed = sync_output_name_on_youtube(
        youtube_url=url,
        last_named_url=(
            str(session.get(ISOLATE_NAMED_YOUTUBE_URL_KEY) or "")
            or None
        ),
        output_name=str(session.get(ISOLATE_OUTPUT_NAME_KEY) or ""),
        auto_output_name=(
            str(session.get(ISOLATE_AUTO_OUTPUT_NAME_KEY) or "") or None
        ),
        downloaded_stem=downloaded_stem,
    )
    session[ISOLATE_NAMED_YOUTUBE_URL_KEY] = named_url
    session[ISOLATE_AUTO_OUTPUT_NAME_KEY] = auto
    if not changed:
        return None
    queue_reopen_output_name(session, name)
    if apply_now:
        apply_pending_output_name(session)
    return name


def queue_reopen_output_name(session: MutableMapping[str, object], title: str) -> None:
    """Stash a Reopen title for the next run. MUST NOT write the widget-bound key."""
    session[ISOLATE_OUTPUT_NAME_PENDING_KEY] = title


def queue_output_name_if_empty(session: MutableMapping[str, object], title: str) -> None:
    """Queue a default name only when the Output name field is blank."""
    current = str(session.get(ISOLATE_OUTPUT_NAME_KEY) or "").strip()
    if current:
        return
    queue_reopen_output_name(session, title)


def apply_pending_output_name(session: MutableMapping[str, object]) -> str | None:
    """Copy pending title onto the widget key. Call before ``st.text_input`` exists."""
    pending = session.pop(ISOLATE_OUTPUT_NAME_PENDING_KEY, None)
    if pending is None:
        return None
    name = str(pending)
    session[ISOLATE_OUTPUT_NAME_KEY] = name
    return name


def queue_clear_youtube_url(session: MutableMapping[str, object]) -> None:
    """Clear the YouTube field on the next run. MUST NOT write the widget-bound key."""
    session[ISOLATE_YOUTUBE_URL_PENDING_KEY] = ""


def queue_youtube_url(session: MutableMapping[str, object], url: str) -> None:
    """Set the YouTube URL on the next run (e.g. after picking a search hit)."""
    session[ISOLATE_YOUTUBE_URL_PENDING_KEY] = (url or "").strip()


def apply_pending_youtube_url(session: MutableMapping[str, object]) -> str | None:
    """Copy pending URL onto the widget key. Call before ``st.text_input`` exists."""
    if ISOLATE_YOUTUBE_URL_PENDING_KEY not in session:
        return None
    pending = session.pop(ISOLATE_YOUTUBE_URL_PENDING_KEY)
    value = str(pending)
    session[ISOLATE_YOUTUBE_URL_KEY] = value
    return value


def reset_new_tab_source(session: MutableMapping[str, object]) -> None:
    """Remount the uploader and clear New-tab source after a job is queued.

    Does not delete staged audio on disk. Must not write widget-bound
    ``isolate_output_name`` / ``isolate_youtube_url`` keys — those go through
    pending keys so the next run can apply them before the widgets mount.
    """
    try:
        current = int(session.get("isolate_upload_key") or 0)
    except (TypeError, ValueError):
        current = 0
    session["isolate_upload_key"] = current + 1
    for key in (
        "isolate_upload_fp",
        "isolate_pending_audio_path",
        "isolate_pending_fp",
        "isolate_duration_sec",
        "isolate_duration_fp",
        "carry_over_audio_path",
        "carry_over_audio_name",
    ):
        session.pop(key, None)
    queue_clear_youtube_url(session)
    queue_reopen_output_name(session, "")


def should_hide_stale_results(
    *,
    pending_upload_fp: str | None,
    has_artifacts: bool,
    results_source_fp: str | None = None,
) -> bool:
    """True when a *new* source is queued that differs from the loaded run's source.

    Having any upload fingerprint while artifacts exist is not enough — after a
    finished run the fingerprint may still be set. Hide only when the pending
    source is different from the run that produced the current mixer.
    """
    if not has_artifacts or pending_upload_fp is None:
        return False
    if results_source_fp is None:
        # Legacy callers: treat any pending fp as a new source.
        return True
    return pending_upload_fp != results_source_fp


WORKSPACE_KEY = "isolate_workspace"
WORKSPACE_TABS = ("New", "Mixer", "Queue")
WORKSPACE_NEXT_KEY = "_isolate_workspace_next"
LISTEN_PICKER_KEY = "isolate_listen_picker"
LISTEN_PICKER_NEXT_KEY = "_isolate_listen_picker_next"
ISOLATE_EXPORT_DIR_KEY = "isolate_export_dir"


def apply_workspace_tab(session: MutableMapping[str, Any], *, has_artifacts: bool) -> str:
    """Resolve New/Mixer/Queue before ``st.tabs`` is instantiated.

    Launch always lands on New so the static form paints immediately. A finishing
    job sets ``WORKSPACE_NEXT_KEY`` then reruns so Mixer can open without fighting
    an already-mounted tab widget.
    """
    _ = has_artifacts
    nxt = session.pop(WORKSPACE_NEXT_KEY, None)
    if nxt in WORKSPACE_TABS:
        session[WORKSPACE_KEY] = nxt
        return str(nxt)
    current = session.get(WORKSPACE_KEY)
    if current not in WORKSPACE_TABS:
        session[WORKSPACE_KEY] = "New"
        return "New"
    return str(current)


QUEUE_IN_FLIGHT_STATUSES = frozenset(
    {"queued", "running", "failed", "cancelled", "paused", "pausing"}
)
ISOLATE_UI_STATE_FILENAME = "isolate_ui_state.json"


def stopping_previous_caption() -> str:
    return "Stopping previous job… next track starts when ready"


def is_stopping_previous_job(active_job_id: str | None, job_status: str | None) -> bool:
    """True when the worker is tearing down a cancelled/pausing job."""
    if not active_job_id:
        return False
    return job_status in {"cancelled", "pausing"}


def queued_wait_caption(
    job_id: str,
    queued_ids: list[str],
    *,
    stopping_previous: bool = False,
) -> str:
    """Waiting line with queue position; never a fake percent."""
    if stopping_previous and queued_ids and job_id in queued_ids:
        return "Up next — waiting for previous job to stop"
    try:
        n = queued_ids.index(job_id) + 1
    except ValueError:
        return "Waiting…"
    return f"Waiting — position {n} of {len(queued_ids)}"


def status_strip_waiting_caption(
    queued_ids: list[str],
    *,
    stopping_previous: bool,
) -> str:
    if stopping_previous:
        return stopping_previous_caption()
    if not queued_ids:
        return "Waiting…"
    return queued_wait_caption(queued_ids[0], queued_ids)


def paused_job_caption(completed_stages: Any = None) -> str:
    stages = list(completed_stages or [])
    if stages:
        return f"Paused — resume continues after {stages[-1]}"
    return "Paused — resume restarts from the beginning"


def partition_queue_jobs(jobs: list[dict[str, Any]]) -> dict[str, Any]:
    """Split jobs into in-flight first, then succeeded. Empty only when both are empty."""
    in_flight: list[dict[str, Any]] = []
    succeeded: list[dict[str, Any]] = []
    for job in jobs:
        status = job.get("status")
        if status in QUEUE_IN_FLIGHT_STATUSES:
            in_flight.append(job)
        elif status == "succeeded":
            succeeded.append(job)
    return {
        "in_flight": in_flight,
        "succeeded": succeeded,
        "empty": not in_flight and not succeeded,
    }


def recent_runs_with_owner_fallback(
    owned: list[dict[str, Any]],
    unfiltered: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Desktop library: use owner-scoped runs, else every isolate run on disk."""
    return owned if owned else unfiltered


def pick_library_row(
    rows: list[dict[str, Any]],
    preferred_run_dir: str | None,
) -> dict[str, Any] | None:
    """Newest row, unless preferred_run_dir still exists in the library."""
    if not rows:
        return None
    if preferred_run_dir:
        wanted = str(preferred_run_dir)
        for row in rows:
            if str(row.get("run_dir") or "") == wanted:
                return row
    return rows[0]


def listen_picker_default(
    options: list[str],
    loaded_run_dir: str | None,
    current: str | None,
) -> str | None:
    """Selectbox value: loaded mixer run, else current if still listed, else first option."""
    if not options:
        return None
    if loaded_run_dir and str(loaded_run_dir) in options:
        return str(loaded_run_dir)
    if current and str(current) in options:
        return str(current)
    return options[0]


def apply_listen_picker_pending(session: MutableMapping[str, Any]) -> None:
    """Apply a deferred picker reset before the selectbox is instantiated."""
    nxt = session.pop(LISTEN_PICKER_NEXT_KEY, None)
    if nxt:
        session[LISTEN_PICKER_KEY] = str(nxt)


def select_rehydrate_row(
    session: MutableMapping[str, Any],
    rows: list[dict[str, Any]],
    *,
    wav_exists,
) -> dict[str, Any] | None:
    """Library row to load when the session has no usable mixer wavs."""
    if session_mixer_artifacts_ok(session, wav_exists=wav_exists):
        return None
    preferred = session.get("isolate_viewing_run_dir") or session.get("isolate_run_dir")
    return pick_library_row(rows, str(preferred) if preferred else None)


def session_mixer_artifacts_ok(session: MutableMapping[str, Any], *, wav_exists) -> bool:
    """True when session already points at mixer wavs that still exist."""
    arts = session.get("isolate_artifacts")
    if not isinstance(arts, dict) or not arts:
        return False
    return any(
        str(path).endswith(".wav") and wav_exists(str(path))
        for path in arts.values()
    )


def isolate_ui_state_payload(session: MutableMapping[str, Any]) -> dict[str, Any]:
    nxt = session.get(WORKSPACE_NEXT_KEY)
    tab = nxt if nxt in WORKSPACE_TABS else session.get(WORKSPACE_KEY)
    workspace = tab if tab in WORKSPACE_TABS else "New"
    viewing = session.get("isolate_viewing_run_dir")
    run_dir = session.get("isolate_run_dir")
    export_dir = session.get(ISOLATE_EXPORT_DIR_KEY)
    return {
        "workspace": workspace,
        "viewing_run_dir": str(viewing) if viewing else None,
        "run_dir": str(run_dir) if run_dir else None,
        "export_dir": str(export_dir) if export_dir else None,
    }


def apply_stored_isolate_ui_state(
    session: MutableMapping[str, Any],
    stored: dict[str, Any] | None,
) -> None:
    """Fill missing session tab/run pointers from disk. Live session keys win."""
    if not stored:
        return
    tab = stored.get("workspace")
    if session.get(WORKSPACE_KEY) not in WORKSPACE_TABS and tab in WORKSPACE_TABS:
        session[WORKSPACE_KEY] = tab
    if not session.get("isolate_viewing_run_dir") and stored.get("viewing_run_dir"):
        session["isolate_viewing_run_dir"] = str(stored["viewing_run_dir"])
    if not session.get("isolate_run_dir") and stored.get("run_dir"):
        session["isolate_run_dir"] = str(stored["run_dir"])
    if not session.get(ISOLATE_EXPORT_DIR_KEY) and stored.get("export_dir"):
        session[ISOLATE_EXPORT_DIR_KEY] = str(stored["export_dir"])


def read_isolate_ui_state(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


def write_isolate_ui_state(path: Path, payload: dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload), encoding="utf-8")
        tmp.replace(path)
    except OSError:
        pass


def seed_consumed_job_ids(jobs: list[dict[str, Any]]) -> list[str]:
    """Succeeded job ids already on disk — treat as seen so launch does not rerun."""
    ids: list[str] = []
    for job in jobs:
        if job.get("status") != "succeeded":
            continue
        jid = str(job.get("id") or "").strip()
        if jid:
            ids.append(jid)
    return ids


_OS_NOTIFY_STATUSES = frozenset({"succeeded", "failed"})
_OS_NOTIFY_APP_TITLE = "Audio Isolation"


def seed_notified_job_ids(jobs: list[dict[str, Any]]) -> list[str]:
    """Succeeded/failed ids already on disk — treat as seen so launch does not toast."""
    ids: list[str] = []
    for job in jobs:
        if job.get("status") not in _OS_NOTIFY_STATUSES:
            continue
        jid = str(job.get("id") or "").strip()
        if jid:
            ids.append(jid)
    return ids


def os_notify_message(job: dict[str, Any]) -> tuple[str, str] | None:
    """App title and body for a terminal job, or None if it should not toast."""
    status = job.get("status")
    title = str(job.get("title") or "track").strip() or "track"
    if len(title) > 80:
        title = title[:77] + "..."
    if status == "succeeded":
        return _OS_NOTIFY_APP_TITLE, f"Separated: {title}"
    if status == "failed":
        return _OS_NOTIFY_APP_TITLE, f"Needs attention: {title} failed"
    return None


def jobs_needing_os_notify(
    jobs: list[dict[str, Any]],
    notified_ids: list[str] | None,
) -> tuple[list[str], list[dict[str, Any]]]:
    """Return ``(updated_ids, jobs_to_toast)``. First call (``None``) seeds without toasting."""
    if notified_ids is None:
        return seed_notified_job_ids(jobs), []
    seen = {str(item) for item in notified_ids if item}
    updated = [str(item) for item in notified_ids if item]
    pending: list[dict[str, Any]] = []
    for job in jobs:
        if job.get("status") not in _OS_NOTIFY_STATUSES:
            continue
        jid = str(job.get("id") or "").strip()
        if not jid or jid in seen:
            continue
        pending.append(job)
        seen.add(jid)
        updated.append(jid)
    return updated, pending


def next_unconsumed_succeeded_job(
    jobs: list[dict[str, Any]],
    consumed_ids: list[str],
    viewing_id: str | None,
) -> tuple[dict[str, Any] | None, bool]:
    """First succeeded job not yet consumed. Bool is True when the mixer may auto-load it."""
    seen = {str(item) for item in consumed_ids if item}
    for job in jobs:
        jid = str(job.get("id") or "").strip()
        if not jid or jid in seen or job.get("status") != "succeeded":
            continue
        return job, should_auto_apply_job(viewing_id, jid)
    return None, False


def plan_isolate_job_poll(
    jobs: list[dict[str, Any]],
    *,
    consumed_ids: list[str] | None,
    viewing_id: str | None,
    form_drawn: bool,
) -> dict[str, Any]:
    """Decide whether a job poll may apply a result or rerun the page.

    A fresh session (``consumed_ids is None``) records historical successes and
    never reruns — otherwise two finished jobs ping-pong ``st.rerun`` and the
    Isolate form never paints.
    """
    if consumed_ids is None:
        return {
            "consumed_ids": seed_consumed_job_ids(jobs),
            "apply_job": None,
            "notify_only": False,
            "rerun": False,
        }
    consumed = [str(item) for item in consumed_ids if item]
    job, auto = next_unconsumed_succeeded_job(jobs, consumed, viewing_id)
    if job is None or not form_drawn:
        return {
            "consumed_ids": consumed,
            "apply_job": None,
            "notify_only": False,
            "rerun": False,
        }
    jid = str(job.get("id") or "")
    return {
        "consumed_ids": consumed + [jid],
        "apply_job": job,
        "notify_only": not auto,
        "rerun": True,
    }


ISOLATE_USER_ID_FILENAME = "isolate_user_id"

SOURCE_KIND_FILE = "file"
SOURCE_KIND_YOUTUBE = "youtube"
_YOUTUBE_FINGERPRINT_PREFIX = "youtube:"


def infer_source_kind(
    *,
    source_kind: Any = None,
    source_fingerprint: Any = None,
    youtube_url: Any = None,
) -> str:
    """``youtube`` or ``file``. Explicit kind wins; else fingerprint/URL; else file."""
    kind = str(source_kind or "").strip().lower()
    if kind in {SOURCE_KIND_FILE, SOURCE_KIND_YOUTUBE}:
        return kind
    if str(youtube_url or "").strip():
        return SOURCE_KIND_YOUTUBE
    fingerprint = str(source_fingerprint or "")
    if fingerprint.startswith(_YOUTUBE_FINGERPRINT_PREFIX):
        return SOURCE_KIND_YOUTUBE
    return SOURCE_KIND_FILE


def format_source_title(title: str | None, kind: str) -> str:
    """Queue / Listening-to label, e.g. ``YouTube · Party Wadokoni_``."""
    name = (title or "tracks").strip() or "tracks"
    label = "YouTube" if infer_source_kind(source_kind=kind) == SOURCE_KIND_YOUTUBE else "File"
    return f"{label} · {name}"


def format_source_caption(
    title: str | None,
    kind: str,
    *,
    filename: str | None = None,
    region_label: str | None = None,
    clip_length: float | None = None,
) -> str:
    """Mixer caption, e.g. ``**Calm Like You** · File (`Calm Like You.wav`)``."""
    name = (title or "tracks").strip() or "tracks"
    parts = [f"**{name}**"]
    if region_label:
        length_note = f" ({float(clip_length):.0f} s)" if clip_length else ""
        parts.append(f"{region_label}{length_note}")
    if infer_source_kind(source_kind=kind) == SOURCE_KIND_YOUTUBE:
        parts.append("YouTube")
    elif filename:
        parts.append(f"File (`{filename}`)")
    else:
        parts.append("File")
    return " · ".join(parts)


def read_stored_user_id(path: Path) -> str | None:
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return text or None


def write_stored_user_id(path: Path, user_id: str) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(user_id, encoding="utf-8")
    except OSError:
        pass


def load_persist_isolate_user_id(session: MutableMapping[str, Any], path: Path) -> str:
    """Session UUID, persisted to a local file (never a blocking browser component)."""
    stored = read_stored_user_id(path)
    user_id = resolve_isolate_user_id(session, stored)
    if stored != user_id:
        write_stored_user_id(path, user_id)
    return user_id


def staged_audio_for_new_tab(
    *,
    uploaded: bool,
    youtube_url: str,
    pending_path: str | None,
    pending_fp: str | None,
    pending_exists: bool,
    carry_path: str | None,
    carry_exists: bool,
) -> str | None:
    """Path to preview on New, or None when there is nothing ready to play.

    A pasted YouTube URL does not preview until that URL has been downloaded
    (pending fingerprint ``youtube:{url}``). Uploads and Tab PDF carry-over
    preview immediately because the file is already on disk.
    """
    url = (youtube_url or "").strip()
    if url:
        if pending_exists and pending_fp == f"youtube:{url}":
            return pending_path
        return None
    if pending_exists:
        return pending_path
    if not uploaded and carry_exists:
        return carry_path
    return None


def pending_upload_fp_for_stale(session: MutableMapping[str, Any]) -> str | None:
    """Fingerprint of a staged isolate source, independent of the file_uploader widget.

    Used when the New tab is not mounted so ``uploaded`` is unavailable.
    """
    pending_fp = session.get("isolate_pending_fp") or session.get("isolate_upload_fp")
    pending_path = session.get("isolate_pending_audio_path")
    has_file = bool(pending_path and Path(str(pending_path)).exists())
    youtube_on = bool(session.get("isolate_youtube_enabled"))
    youtube_url = (session.get("isolate_youtube_url") or "").strip() if youtube_on else ""
    if (has_file or youtube_url) and pending_fp:
        return str(pending_fp)
    return None


def pending_audio_needs_resave(
    *,
    uploaded_fp: str | None,
    pending_fp: str | None,
    pending_path_exists: bool,
) -> bool:
    """True when the uploader's file is not yet mirrored on the pending path."""
    if uploaded_fp is None:
        return False
    if not pending_path_exists:
        return True
    return uploaded_fp != pending_fp


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


def isolation_stages_for_job(
    *,
    expects_guitar: bool,
    guitar_refine: bool = False,
) -> tuple[str, ...]:
    """Stages that will actually run for this job."""
    stages = ISOLATION_STAGE_ORDER
    if not expects_guitar:
        stages = tuple(s for s in stages if s not in _GUITAR_ONLY_STAGES)
    if guitar_refine and expects_guitar:
        out: list[str] = []
        for stage in stages:
            out.append(stage)
            if stage == "collect":
                out.append("guitar_refine")
        return tuple(out)
    return stages


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
    two_pass: bool = False,
    guitar_refine: bool = False,
) -> tuple[float | None, str]:
    """Predicted wall time for the whole job.

    Uses a prior run when quality/device/model match (confidence ``high``),
    otherwise a clip-length × quality × device heuristic (``low``).
    Two-pass isolation is about 2× the Demucs ``separate`` stage.
    Guitar refine and BS-RoFormer-SW add extra wall time.
    """
    if last_run:
        same_setup = (
            last_run.get("quality") == quality
            and last_run.get("device") == device
            and (model is None or last_run.get("model") == model)
            and (expects_guitar is None or bool(last_run.get("expects_guitar")) == bool(expects_guitar))
            and bool(last_run.get("two_pass")) == bool(two_pass)
            and bool(last_run.get("guitar_refine")) == bool(guitar_refine)
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
    pass_factor = 2.0 if two_pass else 1.0
    if (model or "").lower() in {"bs_roformer_sw", "melband_roformer_guitar"}:
        pass_factor *= 1.6
    separate_sec = audio_duration_sec * q * d * pass_factor
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


def user_progress_hint(stage: str, message: str = "") -> str | None:
    """Short user-facing caption for the status strip. Never the raw worker message."""
    if stage != "separate":
        return None
    if "NVIDIA GPU" in (message or ""):
        return "Separating tracks — this can take a while on NVIDIA GPU"
    return "Separating tracks — this can take a while on CPU"


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


def should_auto_apply_job(viewing_id: str | None, job_id: str) -> bool:
    """True when a finished job may replace the mixer (latest / unpinned / same id)."""
    if not job_id:
        return False
    if viewing_id in (None, "", "latest"):
        return True
    return viewing_id == job_id


def running_progress_view(status: dict[str, Any], now: float) -> dict[str, Any]:
    """Pure snapshot of running-job progress for the queue banner and row."""
    stages_raw = status.get("stages") or ISOLATION_STAGE_ORDER
    stages = tuple(str(s) for s in stages_raw)
    stage = str(status.get("stage") or "ingest")
    message = str(status.get("message") or "")
    started_at = float(status.get("started_at") or now)
    stage_started = float(status.get("stage_started_at") or started_at)
    try:
        total_est = float(status["job_estimate_sec"]) if status.get("job_estimate_sec") is not None else None
    except (TypeError, ValueError):
        total_est = None
    confidence = str(status.get("estimate_confidence") or "low")
    elapsed_in = max(0.0, now - stage_started)
    stage_est = estimated_stage_seconds(stage, stages, total_est)
    intra, intra_estimated = intra_stage_fraction(elapsed_in, stage_est)
    percent = stage_progress_percent(stage, stages=stages, intra=intra)
    elapsed = max(0.0, now - started_at)
    remaining, rem_conf = estimate_remaining_seconds(
        elapsed_sec=elapsed,
        percent=percent,
        total_estimate=total_est,
        confidence=confidence,
    )
    human = STAGE_CHECKLIST_LABELS.get(stage, "Separate tracks")
    label = format_progress_label(percent, human, estimated=intra_estimated and confidence == "low")
    items = checklist_items(stages, stage)
    return {
        "percent": percent,
        "label": label,
        "eta_line": format_eta_line(elapsed, remaining, confidence=rem_conf),
        "checklist_md": format_checklist_markdown(items),
        "hint": user_progress_hint(stage, message),
        "estimated": intra_estimated,
    }

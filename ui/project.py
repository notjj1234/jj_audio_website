"""Mutable per-run project state: mixer, practice settings, and artifact links.

``meta.json`` remains the immutable-ish run index. ``project.json`` is the
player state that changes while the user practises, so it is written separately
and never rewrites the run index.
"""

from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import Any

PROJECT_FILENAME = "project.json"
SCHEMA_VERSION = 1
DEFAULT_ANALYSIS = "analysis.json"
DEFAULT_TAB = "tab/tab.json"


def _now() -> float:
    return time.time()


def default_project(
    *,
    title: str = "",
    source_fingerprint: str | None = None,
) -> dict[str, Any]:
    """Return a valid project with every field the player reads."""
    now = _now()
    return {
        "schema_version": SCHEMA_VERSION,
        "title": str(title or ""),
        "source_fingerprint": str(source_fingerprint or ""),
        "created_at": now,
        "updated_at": now,
        "mixer": {
            "volumesDb": {},
            "pan": {},
            "muted": {},
            "soloed": {},
            "masterVolumeDb": 0.0,
        },
        "practice": {
            "rate": 1.0,
            "semitones": 0,
            "loop": None,
            "countInBars": 0,
        },
        "analysis": DEFAULT_ANALYSIS,
        "tab": DEFAULT_TAB,
        "stem_trims": {},
    }


def _finite(value: Any, fallback: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return fallback
    return number if math.isfinite(number) else fallback


def _clamp(value: Any, low: float, high: float, fallback: float) -> float:
    return max(low, min(high, _finite(value, fallback)))


def _dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _loop(value: Any) -> dict[str, float] | None:
    if not isinstance(value, dict):
        return None
    start = _finite(value.get("start"), math.nan)
    end = _finite(value.get("end"), math.nan)
    if not math.isfinite(start) or not math.isfinite(end):
        return None
    start = max(0.0, start)
    end = max(0.0, end)
    if end - start < 0.5:
        return None
    return {"start": start, "end": end}


def _coerce_mixer(raw: Any) -> dict[str, Any]:
    mixer = _dict(raw)
    volumes = {
        str(name): _clamp(db, -25.0, 25.0, 0.0)
        for name, db in _dict(mixer.get("volumesDb")).items()
    }
    pan = {
        str(name): int(_clamp(value, -100.0, 100.0, 0.0))
        for name, value in _dict(mixer.get("pan")).items()
    }
    muted = {str(name): bool(value) for name, value in _dict(mixer.get("muted")).items()}
    soloed = {str(name): bool(value) for name, value in _dict(mixer.get("soloed")).items()}
    return {
        "volumesDb": volumes,
        "pan": pan,
        "muted": muted,
        "soloed": soloed,
        "masterVolumeDb": _clamp(mixer.get("masterVolumeDb"), -25.0, 25.0, 0.0),
    }


def _coerce_practice(raw: Any) -> dict[str, Any]:
    practice = _dict(raw)
    rate = _clamp(practice.get("rate"), 0.5, 1.5, 1.0)
    # Keep the component's 0.05 grid so a restored value matches the slider.
    rate = round(rate / 0.05) * 0.05
    semitones = int(_clamp(practice.get("semitones"), -6.0, 6.0, 0.0))
    count_in = int(_clamp(practice.get("countInBars"), 0.0, 2.0, 0.0))
    return {
        "rate": round(rate, 2),
        "semitones": semitones,
        "loop": _loop(practice.get("loop")),
        "countInBars": count_in,
    }


def _normalise(raw: dict[str, Any], *, now: float | None = None) -> dict[str, Any]:
    stamp = _now() if now is None else now
    return {
        "schema_version": SCHEMA_VERSION,
        "title": str(raw.get("title") or ""),
        "source_fingerprint": str(raw.get("source_fingerprint") or ""),
        "created_at": _finite(raw.get("created_at"), stamp),
        "updated_at": stamp,
        "mixer": _coerce_mixer(raw.get("mixer")),
        "practice": _coerce_practice(raw.get("practice")),
        "analysis": str(raw.get("analysis") or DEFAULT_ANALYSIS),
        "tab": str(raw.get("tab") or DEFAULT_TAB),
        "stem_trims": _coerce_trims(raw.get("stem_trims")),
    }


def _coerce_trims(raw: Any) -> dict[str, dict[str, float]]:
    if not isinstance(raw, dict):
        return {}
    trims: dict[str, dict[str, float]] = {}
    for name, trim in raw.items():
        if not isinstance(trim, dict):
            continue
        try:
            start = float(trim.get("start"))
            end = float(trim.get("end"))
        except (TypeError, ValueError):
            continue
        if not math.isfinite(start) or not math.isfinite(end) or end < start:
            continue
        trims[str(name)] = {"start": start, "end": end}
    return trims


def load_project(run_dir: Path | str) -> tuple[dict[str, Any], str | None]:
    """Load ``project.json``; missing/corrupt/old files return defaults + warning."""
    run_dir = Path(run_dir)
    path = run_dir / PROJECT_FILENAME
    title = ""
    fingerprint = ""
    meta_path = run_dir / "meta.json"
    if meta_path.is_file():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if isinstance(meta, dict):
                title = str(meta.get("title") or "")
                fingerprint = str(meta.get("source_fingerprint") or "")
        except (OSError, ValueError):
            pass
    if not path.is_file():
        return default_project(title=title, source_fingerprint=fingerprint), None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return default_project(title=title, source_fingerprint=fingerprint), (
            f"project.json unreadable ({exc}); using defaults"
        )
    if not isinstance(raw, dict):
        return default_project(title=title, source_fingerprint=fingerprint), (
            "project.json is not an object; using defaults"
        )
    version = raw.get("schema_version")
    if version != SCHEMA_VERSION:
        return default_project(title=title, source_fingerprint=fingerprint), (
            f"project schema {version!r} is not supported; using defaults"
        )
    return _normalise(raw, now=_finite(raw.get("updated_at"), _now())), None


def _content(project: dict[str, Any]) -> str:
    payload = {
        "title": project.get("title", ""),
        "source_fingerprint": project.get("source_fingerprint", ""),
        "mixer": project.get("mixer", {}),
        "practice": project.get("practice", {}),
        "analysis": project.get("analysis", DEFAULT_ANALYSIS),
        "tab": project.get("tab", DEFAULT_TAB),
        "stem_trims": project.get("stem_trims", {}),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def save_project(
    run_dir: Path | str,
    project: dict[str, Any],
    *,
    force: bool = False,
) -> bool:
    """Atomically save only when the mutable player state changed.

    Returns True when a write happened. Timestamps alone never trigger a write.
    """
    run_dir = Path(run_dir)
    path = run_dir / PROJECT_FILENAME
    if path.is_file() and not force:
        existing, _warning = load_project(run_dir)
        if _content(existing) == _content(project):
            return False
    normalised = _normalise(project)
    if path.is_file():
        try:
            existing, _warning = load_project(run_dir)
            normalised["created_at"] = existing.get("created_at", normalised["created_at"])
        except Exception:
            pass
    run_dir.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(normalised, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)
    return True


def update_from_mixer(
    project: dict[str, Any],
    mixer_state: dict[str, Any] | None,
) -> dict[str, Any]:
    """Copy the mixer/practice subset from a component report into ``project``."""
    if not isinstance(mixer_state, dict):
        return project
    mixer = {
        "volumesDb": _dict(mixer_state.get("volumesDb")),
        "pan": _dict(mixer_state.get("pan")),
        "muted": _dict(mixer_state.get("muted")),
        "soloed": _dict(mixer_state.get("soloed")),
        "masterVolumeDb": mixer_state.get("masterVolumeDb", 0.0),
    }
    practice = dict(project.get("practice") or {})
    if "playbackRate" in mixer_state:
        practice["rate"] = mixer_state["playbackRate"]
    if "playbackSemitones" in mixer_state:
        practice["semitones"] = mixer_state["playbackSemitones"]
    if "loop" in mixer_state:
        practice["loop"] = _loop(mixer_state.get("loop"))
    if "countInBars" in mixer_state:
        practice["countInBars"] = mixer_state.get("countInBars")
    project["mixer"] = _coerce_mixer(mixer)
    project["practice"] = _coerce_practice(practice)
    project["updated_at"] = _now()
    return project


def seed_mixer(project: dict[str, Any]) -> dict[str, Any]:
    """The component's initial-state arguments, from a project manifest."""
    mixer = _coerce_mixer(project.get("mixer"))
    practice = _coerce_practice(project.get("practice"))
    return {
        "initial_volumes_db": mixer["volumesDb"],
        "initial_muted": mixer["muted"],
        "initial_soloed": mixer["soloed"],
        "initial_pan": mixer["pan"],
        "initial_master_volume_db": mixer["masterVolumeDb"],
        "playback_rate": practice["rate"],
        "playback_semitones": practice["semitones"],
        "initial_loop": practice["loop"],
        "count_in_bars": practice["countInBars"],
    }


def _artifact_path(run_dir: Path | str, raw_path: object) -> Path | None:
    """Resolve an artifact reference inside ``run_dir``; reject escapes/absolute paths."""
    root = Path(run_dir).resolve()
    path = Path(str(raw_path or ""))
    if path.is_absolute():
        return None
    candidate = (root / path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate


def load_analysis_for_run(
    run_dir: Path | str,
    project: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Return the run's analysis as a JSON-ready dict, or None when absent."""
    run_dir = Path(run_dir)
    manifest = project or load_project(run_dir)[0]
    raw_path = str(manifest.get("analysis") or DEFAULT_ANALYSIS)
    path = _artifact_path(run_dir, raw_path)
    if path is None:
        return None
    try:
        from audio_to_tab.analysis import load_analysis

        result = load_analysis(path)
    except Exception:
        return None
    return result.to_dict() if result is not None else None


def load_tab_for_run(
    run_dir: Path | str,
    project: dict[str, Any] | None = None,
    *,
    pdf_url: str | None = None,
) -> dict[str, Any] | None:
    """Return ``{document, measures, pdfUrl?}`` for the mixer panel, or None."""
    run_dir = Path(run_dir)
    manifest = project or load_project(run_dir)[0]
    raw_path = str(manifest.get("tab") or DEFAULT_TAB)
    path = _artifact_path(run_dir, raw_path)
    if path is None or not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    measures = payload.get("measures")
    if not isinstance(measures, list) or not measures:
        return None
    data = {"document": payload.get("document"), "measures": measures}
    if pdf_url:
        data["pdfUrl"] = pdf_url
    return data

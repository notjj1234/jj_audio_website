"""Phase 3 local products. No model, no network, no extra package."""

from __future__ import annotations

import json
import secrets
import shutil
import zipfile
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from audio_to_tab.mixer import STEM_ORDER

GENERATION_MESSAGE = "Generation needs a model that is not installed."
VOICE_MESSAGE = "Voice conversion is not installed."
_AUTHORS = {"Owner", "Listener"}
_SKIP_ARTIFACTS = {"analysis", "tab", "source", "mix", "meta", "project"}

CATALOGUE_27: tuple[str, ...] = (
    *STEM_ORDER,
    "kick",
    "snare",
    "hihat",
    "toms",
    "cymbals",
    "strings",
    "synth",
    "brass",
    "woodwinds",
    "backing_vocals",
)

AUTO_MIX_DB = {
    "vocals": 0.0,
    "guitar": -1.0,
    "lead_guitar": -1.0,
    "rhythm_guitar": -1.0,
    "drums": -6.0,
    "bass": -6.0,
    "other": -3.0,
}

INSTRUMENTS: tuple[dict[str, Any], ...] = (
    {"name": "Piano", "installed": False},
    {"name": "Bass", "installed": False},
    {"name": "Drums", "installed": False},
    {"name": "Strings", "installed": False},
    {"name": "Synth", "installed": False},
)


def remember_library_folder(state: dict[str, Any], folder: str) -> dict[str, Any]:
    copied = dict(state)
    copied["library_folder"] = str(folder)
    return copied


def remember_sync_folder(state: dict[str, Any], folder: str) -> dict[str, Any]:
    copied = dict(state)
    copied["sync_folder"] = str(folder)
    return copied


def stem_catalogue() -> list[dict[str, Any]]:
    installed = set(STEM_ORDER)
    return [{"name": name, "installed": name in installed} for name in CATALOGUE_27]


def set_stem_trim(project: dict[str, Any], stem: str, start: float, end: float) -> dict[str, Any]:
    trims = project.setdefault("stem_trims", {})
    trims[str(stem)] = {"start": float(start), "end": float(end)}
    return project


def write_musicxml(chords: list[Any], measures: list[Any], dest: Path) -> Path | None:
    symbols = _score_symbols(chords) + _score_symbols(measures)
    if not symbols:
        return None
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    measures_xml = []
    for index, symbol in enumerate(symbols, start=1):
        measures_xml.append(
            f'<measure number="{index}"><note><rest/>'
            f"<lyric><text>{escape(symbol)}</text></lyric></note></measure>"
        )
    dest.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<score-partwise version="3.1">'
        '<part-list><score-part id="P1"><part-name>Practice</part-name></score-part></part-list>'
        f"<part id=\"P1\">{''.join(measures_xml)}</part></score-partwise>",
        encoding="utf-8",
    )
    return dest


def write_dawproject(stem_files: list[str], dest: Path) -> Path:
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tracks = "".join(f'<Track name="{escape(name)}"/>' for name in stem_files)
    xml = f"<Project>{tracks}</Project>"
    with zipfile.ZipFile(dest, "w") as archive:
        archive.writestr("project.xml", xml)
    return dest


def write_daw_zip(stems: dict[str, Path], dest: Path) -> Path:
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    with zipfile.ZipFile(dest, "w") as archive:
        for name, path in stems.items():
            source = Path(path)
            archive.write(source, arcname=source.name)
            lines.append(f"{name}\t{source.name}")
        archive.writestr("tracks.txt", "\n".join(lines) + "\n")
    return dest


def sync_library(library: Path, remote: Path) -> int:
    return _copy_songs(Path(library), Path(remote))


def restore_library(remote: Path, library: Path) -> int:
    return _copy_songs(Path(remote), Path(library))


def save_song_to_library(run: Path, library: Path) -> Path:
    library = Path(library)
    library.mkdir(parents=True, exist_ok=True)
    dest = library / Path(run).name
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(run, dest)
    return dest


def open_library_song(library_song: Path, data_dir: Path) -> Path:
    source = Path(library_song)
    dest_root = Path(data_dir)
    dest_root.mkdir(parents=True, exist_ok=True)
    dest = dest_root / source.name
    if dest.resolve() == source.resolve():
        return dest
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(source, dest)
    return dest


def snapshot_project(run: Path) -> Path | None:
    src = Path(run) / "project.json"
    if not src.is_file():
        return None
    dest = Path(run) / "project.previous.json"
    dest.write_bytes(src.read_bytes())
    return dest


def restore_project(run: Path) -> bool:
    prev = Path(run) / "project.previous.json"
    if not prev.is_file():
        return False
    (Path(run) / "project.json").write_bytes(prev.read_bytes())
    return True


def create_share(run: Path) -> str:
    token = secrets.token_hex(8)
    (Path(run) / "share.json").write_text(json.dumps({"token": token}), encoding="utf-8")
    return token


def open_share(root: Path, token: str) -> Path | None:
    for path in Path(root).rglob("share.json"):
        data = _read_json(path)
        if data.get("token") == token:
            return path.parent
    return None


def save_session(run: Path) -> str:
    project = _read_json(Path(run) / "project.json")
    code = secrets.token_hex(4)
    (Path(run) / "session.json").write_text(
        json.dumps({"code": code, "project": project}),
        encoding="utf-8",
    )
    return code


def load_session(root: Path, code: str) -> dict[str, Any] | None:
    for path in Path(root).rglob("session.json"):
        data = _read_json(path)
        if data.get("code") == code and isinstance(data.get("project"), dict):
            return data["project"]
    return None


def add_note(studio: dict[str, Any], author: str, text: str) -> dict[str, Any]:
    if author not in _AUTHORS or not str(text or "").strip():
        return studio
    studio.setdefault("notes", []).append({"author": author, "text": str(text).strip()})
    return studio


def add_comment(studio: dict[str, Any], author: str, text: str, time_sec: float) -> dict[str, Any]:
    if author not in _AUTHORS or not str(text or "").strip():
        return studio
    studio.setdefault("comments", []).append(
        {"author": author, "text": str(text).strip(), "time": float(time_sec)}
    )
    return studio


def export_setlist(item: dict[str, Any]) -> dict[str, Any]:
    titles = []
    for title in item.get("titles") or []:
        text = str(title or "").strip()
        if text and "/" not in text and "\\" not in text:
            titles.append(text)
    return {
        "id": str(item.get("id") or ""),
        "name": str(item.get("name") or ""),
        "titles": titles,
    }


def import_setlist(payload: dict[str, Any], library_rows: list[dict[str, Any]]) -> list[str]:
    wanted = {str(title).casefold() for title in payload.get("titles") or []}
    matched: list[str] = []
    for row in library_rows:
        title = str(row.get("title") or "")
        if title.casefold() not in wanted:
            continue
        run_dir = str(row.get("run_dir") or row.get("id") or "")
        if run_dir:
            matched.append(run_dir)
    return matched


def save_prompt(studio: dict[str, Any], text: str) -> dict[str, Any]:
    cleaned = str(text or "").strip()
    if cleaned:
        studio.setdefault("prompts", []).append(cleaned)
    return studio


def generation_result() -> dict[str, Any]:
    return {"audio": None, "midi": None, "message": GENERATION_MESSAGE}


def name_voice(studio: dict[str, Any], name: str) -> str:
    studio["target_voice"] = str(name or "").strip()
    return VOICE_MESSAGE


def save_custom_voice(studio: dict[str, Any], name: str, reference: str) -> dict[str, Any]:
    studio["custom_voice"] = {"name": str(name or "").strip(), "reference": str(reference)}
    return studio


def peak_master(src: Path, dest: Path) -> Path:
    import numpy as np
    import soundfile as sf

    audio, rate = sf.read(src, always_2d=True)
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    if peak > 0:
        audio = audio * (0.89 / peak)
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    sf.write(dest, audio, rate, subtype="PCM_16")
    return dest


def auto_mix_volumes(current: dict[str, float], strength: float) -> dict[str, float]:
    amount = max(0.0, min(100.0, float(strength))) / 100.0
    names = set(current)
    if amount > 0:
        names.update(AUTO_MIX_DB)
    mixed: dict[str, float] = {}
    for name in names:
        start = float(current.get(name, AUTO_MIX_DB.get(name, 0.0)))
        target = float(AUTO_MIX_DB.get(name, start))
        mixed[name] = start + (target - start) * amount
    return mixed


def upsert_clip(studio: dict[str, Any], label: str, start: float, end: float) -> dict[str, Any]:
    clips = studio.setdefault("clips", [])
    row = {"label": str(label), "start": float(start), "end": float(end)}
    for index, clip in enumerate(clips):
        if clip.get("label") == label:
            if clip.get("automation"):
                row["automation"] = clip["automation"]
            clips[index] = row
            return studio
    clips.append(row)
    return studio


def remove_clip(studio: dict[str, Any], label: str) -> dict[str, Any]:
    studio["clips"] = [clip for clip in studio.get("clips") or [] if clip.get("label") != label]
    return studio


def set_bus(studio: dict[str, Any], name: str, stems: list[str], volume_db: float) -> dict[str, Any]:
    studio.setdefault("buses", {})[str(name)] = {
        "stems": [str(stem) for stem in stems],
        "volume_db": float(volume_db),
    }
    return studio


def apply_bus(project: dict[str, Any], studio: dict[str, Any], name: str) -> dict[str, Any]:
    bus = (studio.get("buses") or {}).get(name) or {}
    mixer = project.setdefault("mixer", {})
    volumes = mixer.get("volumesDb")
    if not isinstance(volumes, dict):
        volumes = {}
        mixer["volumesDb"] = volumes
    volume = float(bus.get("volume_db") or 0.0)
    for stem in bus.get("stems") or []:
        volumes[str(stem)] = volume
    return project


def set_clip_automation(
    studio: dict[str, Any], label: str, points: list[tuple[float, float]]
) -> dict[str, Any]:
    for clip in studio.get("clips") or []:
        if clip.get("label") == label:
            clip["automation"] = [{"time": float(t), "db": float(db)} for t, db in points]
    return studio


def add_midi_note(studio: dict[str, Any], pitch: int, start: float, length: float) -> dict[str, Any]:
    studio.setdefault("midi", []).append(
        {"pitch": int(pitch), "start": float(start), "length": float(length)}
    )
    return studio


def delete_midi_note(studio: dict[str, Any], index: int) -> dict[str, Any]:
    notes = studio.setdefault("midi", [])
    if 0 <= index < len(notes):
        del notes[index]
    return studio


def set_chosen_take(studio: dict[str, Any], extra_dir: Path, name: str) -> dict[str, Any]:
    safe = Path(name).name
    if (Path(extra_dir) / safe).is_file():
        studio["chosen_take"] = safe
    return studio


def load_studio(run: Path) -> dict[str, Any]:
    return _read_json(Path(run) / "studio.json")


def save_studio(run: Path, studio: dict[str, Any]) -> None:
    (Path(run) / "studio.json").write_text(json.dumps(studio), encoding="utf-8")


def stem_names_from_artifacts(kinds: list[str]) -> list[str]:
    return [kind for kind in kinds if kind not in _SKIP_ARTIFACTS and "/" not in kind]


def _score_symbols(rows: list[Any]) -> list[str]:
    symbols: list[str] = []
    for row in rows or []:
        if isinstance(row, dict):
            text = str(row.get("symbol") or row.get("text") or row.get("name") or "").strip()
        else:
            text = str(row or "").strip()
        if text:
            symbols.append(text)
    return symbols


def _copy_songs(source: Path, dest: Path) -> int:
    dest.mkdir(parents=True, exist_ok=True)
    count = 0
    if not source.is_dir():
        return 0
    for song in source.iterdir():
        if not song.is_dir() or not (song / "meta.json").is_file():
            continue
        target = dest / song.name
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(song, target)
        count += 1
    return count


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError, UnicodeError):
        return {}
    return data if isinstance(data, dict) else {}

"""Named lists of local songs. The file stays on this computer."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4


def load_setlists(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    items = raw.get("setlists") if isinstance(raw, dict) else None
    if not isinstance(items, list):
        return []
    loaded: list[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        ident = str(item.get("id") or "").strip()
        name = " ".join(str(item.get("name") or "").split())
        songs = item.get("songs")
        if not ident or not name or not isinstance(songs, list):
            continue
        clean_songs = [str(song) for song in songs if str(song or "").strip()]
        loaded.append({"id": ident, "name": name, "songs": clean_songs})
    return loaded


def save_setlists(path: Path, setlists: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": 1, "setlists": setlists}
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def create_setlist(setlists: list[dict], name: str) -> dict:
    cleaned = " ".join(str(name or "").split())
    item = {"id": uuid4().hex[:12], "name": cleaned or "Setlist", "songs": []}
    setlists.append(item)
    return item


def add_song(setlists: list[dict], setlist_id: str, run_dir: str) -> bool:
    song = str(run_dir or "").strip()
    if not song:
        return False
    for item in setlists:
        if str(item.get("id") or "") != setlist_id:
            continue
        songs = item.setdefault("songs", [])
        if song in songs:
            return False
        songs.append(song)
        return True
    return False


def remove_song(setlists: list[dict], setlist_id: str, run_dir: str) -> bool:
    song = str(run_dir or "").strip()
    for item in setlists:
        if str(item.get("id") or "") != setlist_id:
            continue
        songs = item.get("songs")
        if not isinstance(songs, list) or song not in songs:
            return False
        songs.remove(song)
        return True
    return False

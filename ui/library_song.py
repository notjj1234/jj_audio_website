"""Library filters, trash, extra tracks, chord chart text, and chrome strings."""

from __future__ import annotations

import json
from pathlib import Path

TRASH_DIR_NAME = "library_trash"
_EXTRA_SUFFIXES = frozenset({".mp3", ".wav", ".flac", ".m4a"})
_LOCALE = {
    "en": {
        "search": "Search",
        "title": "Title",
        "all": "All",
        "practice": "Ready to practice",
        "analyse": "Not analysed",
        "deleted": "Deleted",
        "delete": "Delete song",
        "recover": "Recover",
    },
    "ko": {
        "search": "검색",
        "title": "제목",
        "all": "전체",
        "practice": "연습 준비",
        "analyse": "분석 안 됨",
        "deleted": "삭제됨",
        "delete": "곡 삭제",
        "recover": "복구",
    },
}


def stage_extra_tracks(run_dir: Path, files: list[tuple[str, bytes]]) -> list[str]:
    """Copy local audio into the song. Other types are skipped. No separation."""
    extra = Path(run_dir) / "extra_tracks"
    extra.mkdir(parents=True, exist_ok=True)
    saved: list[str] = []
    for name, data in files:
        safe = Path(str(name)).name
        if Path(safe).suffix.lower() not in _EXTRA_SUFFIXES:
            continue
        dest = extra / safe
        dest.write_bytes(data)
        saved.append(str(dest))
    return saved


def chord_chart_text(chords: list[dict]) -> str:
    """One line per chord. Silence markers are left out."""
    lines = ["Chord chart"]
    for chord in chords:
        symbol = str(chord.get("symbol") or "").strip()
        if not symbol or symbol.upper() == "N":
            continue
        try:
            start = float(chord.get("start") or 0)
        except (TypeError, ValueError):
            start = 0.0
        if start < 0:
            start = 0.0
        minutes = int(start // 60)
        seconds = int(start % 60)
        lines.append(f"{minutes}:{seconds:02d}  {symbol}")
    return "\n".join(lines) + "\n"


def filter_library_rows(rows: list[dict], kind: str) -> list[dict]:
    """Filter beyond the search box. ``all`` keeps every row."""
    wanted = str(kind or "all")
    if wanted == "all":
        return list(rows)
    return [row for row in rows if str(row.get("action") or "") == wanted]


def delete_library_song(run_dir: Path, data_dir: Path) -> Path | None:
    """Move one song folder into the trash. The setlist store is not touched."""
    root = Path(data_dir).resolve()
    try:
        source = Path(run_dir).resolve()
    except OSError:
        return None
    if not source.is_dir():
        return None
    if source.parent == root / TRASH_DIR_NAME:
        return None
    try:
        source.relative_to(root)
    except ValueError:
        return None
    trash = root / TRASH_DIR_NAME
    trash.mkdir(parents=True, exist_ok=True)
    dest = trash / source.name
    if dest.exists():
        return None
    source.rename(dest)
    return dest


def recover_library_song(trashed: Path, data_dir: Path) -> Path | None:
    """Move a trashed song back to its library folder."""
    root = Path(data_dir).resolve()
    try:
        source = Path(trashed).resolve()
    except OSError:
        return None
    if source.parent != root / TRASH_DIR_NAME or not source.is_dir():
        return None
    dest = root / source.name
    if dest.exists():
        return None
    source.rename(dest)
    return dest


def list_trashed_songs(data_dir: Path) -> list[Path]:
    trash = Path(data_dir) / TRASH_DIR_NAME
    if not trash.is_dir():
        return []
    found = [path for path in trash.iterdir() if path.is_dir() and (path / "meta.json").is_file()]
    found.sort(key=lambda path: path.name)
    return found


def locale_text(locale: str, key: str) -> str:
    """English is the default. Korean is the first extra language."""
    table = _LOCALE.get(str(locale or "en"), _LOCALE["en"])
    if key not in table:
        return _LOCALE["en"].get(key, key)
    return table[key]


def trashed_row(path: Path) -> dict:
    title = path.name
    meta = path / "meta.json"
    try:
        data = json.loads(meta.read_text(encoding="utf-8"))
        title = str(data.get("title") or title)
    except (OSError, json.JSONDecodeError):
        pass
    return {"run_dir": str(path), "title": title, "action": "recover", "deleted": True}

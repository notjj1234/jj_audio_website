"""Local setlists: named song lists on this computer. No sharing."""

from __future__ import annotations

import json
from pathlib import Path


def test_setlist_keeps_songs_in_order_and_ignores_duplicates(tmp_path: Path):
    from ui.setlists import add_song, create_setlist, load_setlists, remove_song, save_setlists

    path = tmp_path / "setlists.json"
    lists = load_setlists(path)
    assert lists == []
    created = create_setlist(lists, "  Friday gig  ")
    assert created["name"] == "Friday gig"
    assert add_song(lists, created["id"], "/songs/a") is True
    assert add_song(lists, created["id"], "/songs/b") is True
    assert add_song(lists, created["id"], "/songs/a") is False
    assert add_song(lists, "missing", "/songs/a") is False
    save_setlists(path, lists)
    loaded = load_setlists(path)
    assert loaded[0]["songs"] == ["/songs/a", "/songs/b"]
    assert remove_song(loaded, created["id"], "/songs/a") is True
    assert loaded[0]["songs"] == ["/songs/b"]
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["version"] == 1


def test_blank_setlist_name_is_setlist():
    from ui.setlists import create_setlist

    created = create_setlist([], "   ")
    assert created["name"] == "Setlist"
    assert created["songs"] == []


def test_home_props_list_setlist_tokens_without_paths():
    import json

    from ui.pages.home import build_home_props

    secret = "/tmp/secret/song"
    props = build_home_props(
        rows=[{"run_dir": secret, "title": "x"}],
        setlists=[{"id": "friday", "name": "Friday", "songs": [secret, "/tmp/other"]}],
    )
    encoded = json.dumps(props)
    assert secret not in encoded
    assert "/tmp/other" not in encoded
    assert "run_dir" not in encoded
    listed = props["setlists"]
    assert listed[0]["id"] == "friday"
    assert listed[0]["name"] == "Friday"
    assert listed[0]["tokens"] == [props["rows"][0]["token"]]


def test_home_event_saves_setlist_by_token(tmp_path: Path, monkeypatch):
    import ui.pages.home as home
    from ui.setlists import load_setlists

    monkeypatch.setattr(home, "DATA_DIR", tmp_path)
    monkeypatch.setattr(home.st, "rerun", lambda: None)
    song = str(tmp_path / "song")
    home._handle_home_event({"type": "new_setlist", "id": "Friday"}, {})
    lists = load_setlists(tmp_path / "setlists.json")
    assert home.st.session_state["home_v2_setlist"] == lists[0]["id"]
    props = home.build_home_props(
        rows=[{"run_dir": song, "title": "x"}],
        setlists=lists,
    )
    token = props["rows"][0]["token"]
    home._handle_home_event(
        {"type": "add_to_setlist", "id": f"{lists[0]['id']}|{token}"},
        dict(home._TOKEN_MAP),
    )
    loaded = load_setlists(tmp_path / "setlists.json")
    assert loaded[0]["songs"] == [song]
    assert home.st.session_state["home_v2_setlist"] == lists[0]["id"]
    assert home.active_setlist_id(loaded) == lists[0]["id"]
    home._handle_home_event({"type": "select_setlist", "id": ""}, {})
    assert home.active_setlist_id(loaded) == ""
    encoded = json.dumps(
        home.build_home_props(rows=[{"run_dir": song, "title": "x"}], setlists=loaded)
    )
    assert song not in encoded
    assert "run_dir" not in encoded


def test_home_screen_offers_setlists():
    root = Path(__file__).resolve().parents[1]
    frontend = (root / "ui" / "home_component" / "frontend" / "src" / "main.ts").read_text(
        encoding="utf-8"
    )
    assert "New setlist" in frontend
    assert "Add to setlist" in frontend
    assert "No songs in this setlist." in frontend
    assert "select_setlist" in frontend
    assert "activeSetlist" in frontend
    assert "run_dir" not in frontend
    component = (root / "ui" / "home_component" / "__init__.py").read_text(encoding="utf-8")
    assert 'setlists=list(props.get("setlists") or [])' in component
    built = "".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in (root / "ui" / "home_component" / "frontend" / "build" / "assets").glob(
            "index-*.js"
        )
    )
    assert "New setlist" in built
    assert "No songs in this setlist." in built
    assert "select_setlist" in built

"""Phase 3 local products. No model, no worker, no network."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import soundfile as sf

from audio_to_tab.phase3 import (
    AUTO_MIX_DB,
    CATALOGUE_27,
    GENERATION_MESSAGE,
    INSTRUMENTS,
    VOICE_MESSAGE,
    add_comment,
    add_midi_note,
    add_note,
    auto_mix_volumes,
    create_share,
    delete_midi_note,
    export_setlist,
    generation_result,
    import_setlist,
    load_session,
    name_voice,
    open_share,
    peak_master,
    remember_library_folder,
    remove_clip,
    restore_library,
    restore_project,
    save_custom_voice,
    save_prompt,
    save_session,
    set_bus,
    set_chosen_take,
    set_clip_automation,
    set_stem_trim,
    snapshot_project,
    stem_catalogue,
    sync_library,
    upsert_clip,
    write_daw_zip,
    write_dawproject,
    write_musicxml,
)


def test_library_folder_is_remembered_on_this_computer():
    state = remember_library_folder({}, "/tmp/library")
    assert state["library_folder"] == "/tmp/library"


def test_catalogue_has_27_names_and_marks_missing_ones():
    rows = stem_catalogue()
    assert len(rows) == 27
    assert len(CATALOGUE_27) == 27
    installed = {row["name"] for row in rows if row["installed"]}
    assert "vocals" in installed
    assert "kick" not in installed
    assert any(not row["installed"] for row in rows)


def test_stem_trim_is_stored_on_the_project():
    project = set_stem_trim({}, "vocals", 1.5, 8.0)
    assert project["stem_trims"]["vocals"] == {"start": 1.5, "end": 8.0}


def test_musicxml_uses_chords_and_writes_nothing_when_empty(tmp_path: Path):
    dest = tmp_path / "score.musicxml"
    written = write_musicxml([{"symbol": "Am"}], [], dest)
    assert written == dest
    text = dest.read_text(encoding="utf-8")
    assert "Am" in text
    assert "score-partwise" in text
    assert write_musicxml([], [], tmp_path / "empty.musicxml") is None


def test_dawproject_zip_lists_stem_files(tmp_path: Path):
    dest = write_dawproject(["vocals.wav", "drums.wav"], tmp_path / "song.dawproject")
    import zipfile

    with zipfile.ZipFile(dest) as archive:
        xml = archive.read("project.xml").decode("utf-8")
    assert "vocals.wav" in xml
    assert "drums.wav" in xml


def test_sync_copies_and_restore_copies_back(tmp_path: Path):
    library = tmp_path / "library"
    song = library / "song"
    song.mkdir(parents=True)
    (song / "meta.json").write_text("{}", encoding="utf-8")
    remote = tmp_path / "remote"
    assert sync_library(library, remote) == 1
    assert (remote / "song" / "meta.json").is_file()
    (song / "meta.json").write_text('{"title":"local"}', encoding="utf-8")
    assert restore_library(remote, library) == 1
    assert "local" not in (song / "meta.json").read_text(encoding="utf-8")


def test_one_project_undo(tmp_path: Path):
    project = tmp_path / "project.json"
    project.write_text('{"title":"first"}', encoding="utf-8")
    snapshot_project(tmp_path)
    project.write_text('{"title":"second"}', encoding="utf-8")
    assert restore_project(tmp_path) is True
    assert json.loads(project.read_text(encoding="utf-8"))["title"] == "first"


def test_share_token_opens_the_run_without_putting_the_path_in_the_token(tmp_path: Path):
    run = tmp_path / "run-a"
    run.mkdir()
    token = create_share(run)
    assert "/" not in token
    assert str(run) not in token
    assert open_share(tmp_path, token) == run
    assert open_share(tmp_path, "missing") is None


def test_session_code_loads_the_saved_mix(tmp_path: Path):
    run = tmp_path / "run"
    run.mkdir()
    (run / "project.json").write_text('{"mixer":{"volumesDb":{"vocals":-2}}}', encoding="utf-8")
    code = save_session(run)
    loaded = load_session(tmp_path, code)
    assert loaded is not None
    assert loaded["mixer"]["volumesDb"]["vocals"] == -2


def test_notes_comments_and_setlist_exchange():
    studio: dict = {}
    add_note(studio, "Owner", "count the verse")
    add_note(studio, "nope", "no")
    assert studio["notes"][0]["author"] == "Owner"
    assert len(studio["notes"]) == 1
    add_comment(studio, "Listener", "chorus", 12.5)
    assert studio["comments"][0]["time"] == 12.5
    payload = export_setlist({"id": "s1", "name": "Gig", "songs": ["/a/waltz"]})
    assert payload["titles"] == []
    matched = import_setlist(
        {"id": "s1", "name": "Gig", "titles": ["Waltz"]},
        [{"title": "Waltz", "run_dir": "/songs/waltz"}],
    )
    assert matched == ["/songs/waltz"]


def test_generation_saves_a_prompt_and_returns_nothing():
    studio: dict = {}
    save_prompt(studio, "a roomier vocal")
    save_prompt(studio, "a drier vocal")
    assert studio["prompts"] == ["a roomier vocal", "a drier vocal"]
    result = generation_result()
    assert result["audio"] is None
    assert result["midi"] is None
    assert result["message"] == GENERATION_MESSAGE


def test_voice_names_are_stored_and_conversion_is_not_installed():
    studio: dict = {}
    assert name_voice(studio, "Alto") == VOICE_MESSAGE
    assert studio["target_voice"] == "Alto"
    save_custom_voice(studio, "Mine", "/tmp/ref.wav")
    assert studio["custom_voice"] == {"name": "Mine", "reference": "/tmp/ref.wav"}


def test_peak_master_lowers_a_hot_file(tmp_path: Path):
    src = tmp_path / "hot.wav"
    sf.write(src, np.ones((100, 1)), 44100, subtype="PCM_16")
    dest = peak_master(src, tmp_path / "master.wav")
    audio, _rate = sf.read(dest)
    assert abs(float(np.max(np.abs(audio))) - 0.89) < 0.02


def test_auto_mix_strength_blends_toward_the_balance():
    current = {"vocals": -12.0, "drums": 0.0}
    untouched = auto_mix_volumes(current, 0)
    assert untouched["vocals"] == -12.0
    full = auto_mix_volumes(current, 100)
    assert full["vocals"] == AUTO_MIX_DB["vocals"]
    assert full["drums"] == AUTO_MIX_DB["drums"]
    mid = auto_mix_volumes(current, 50)
    assert mid["vocals"] == -6.0


def test_studio_clips_buses_automation_and_notes(tmp_path: Path):
    studio: dict = {}
    upsert_clip(studio, "verse", 0.0, 8.0)
    upsert_clip(studio, "verse", 1.0, 9.0)
    assert studio["clips"] == [{"label": "verse", "start": 1.0, "end": 9.0}]
    set_bus(studio, "Band", ["drums", "bass"], -3.0)
    assert studio["buses"]["Band"]["volume_db"] == -3.0
    set_clip_automation(studio, "verse", [(0.0, -6.0), (4.0, 0.0)])
    assert studio["clips"][0]["automation"][1]["db"] == 0.0
    remove_clip(studio, "verse")
    assert studio["clips"] == []
    add_midi_note(studio, 60, 0.0, 0.5)
    delete_midi_note(studio, 0)
    assert studio["midi"] == []
    assert all(item["installed"] is False for item in INSTRUMENTS)


def test_chosen_take_keeps_the_other_files(tmp_path: Path):
    extra = tmp_path / "extra_tracks"
    extra.mkdir()
    (extra / "a.wav").write_bytes(b"a")
    (extra / "b.wav").write_bytes(b"b")
    studio: dict = {}
    set_chosen_take(studio, extra, "b.wav")
    assert studio["chosen_take"] == "b.wav"
    assert (extra / "a.wav").is_file()


def test_daw_zip_contains_the_stem_and_a_track_list(tmp_path: Path):
    stem = tmp_path / "vocals.wav"
    stem.write_bytes(b"wav")
    dest = write_daw_zip({"vocals": stem}, tmp_path / "daw.zip")
    import zipfile

    with zipfile.ZipFile(dest) as archive:
        names = set(archive.namelist())
    assert "vocals.wav" in names
    assert "tracks.txt" in names


def test_social_login_is_not_added_and_email_login_stays():
    source = Path("backend/main.py").read_text(encoding="utf-8")
    assert "/v1/auth/login" in source or "def login" in source
    assert "accounts.google.com" not in source
    assert "facebook.com" not in source
    assert "appleid.apple.com" not in source
    assert "/v1/jobs/{job_id}/stems" in source


def test_ui_state_keeps_the_library_folder():
    from ui.isolate_state import UI_MODES, apply_stored_isolate_ui_state, isolate_ui_state_payload

    payload = isolate_ui_state_payload(
        {"library_folder": "/tmp/songs", "sync_folder": "/tmp/sync"}
    )
    assert payload["library_folder"] == "/tmp/songs"
    assert payload["sync_folder"] == "/tmp/sync"
    session: dict = {}
    apply_stored_isolate_ui_state(session, payload)
    assert session["library_folder"] == "/tmp/songs"
    assert session["sync_folder"] == "/tmp/sync"
    assert UI_MODES == ("Lite", "Pro")


def test_plugin_route_lists_stem_names_only():
    from audio_to_tab.phase3 import stem_names_from_artifacts

    assert stem_names_from_artifacts(["vocals", "analysis", "drums"]) == ["vocals", "drums"]


def test_player_sources_have_the_local_controls():
    mixer = Path("ui/stem_mixer_component/frontend/src/main.ts").read_text(encoding="utf-8")
    assert 'class="primary live-play"' in mixer
    assert 'type = "lowshelf"' in mixer
    assert 'type = "highshelf"' in mixer
    assert "setStemTrims" in mixer
    web = Path("web/src/components/StemMixer.tsx").read_text(encoding="utf-8")
    assert "MediaRecorder" in web
    assert "confirm(" in web
    assert "live-play" in web


def test_song_studio_stays_below_the_mixer():
    source = Path("ui/pages/isolate.py").read_text(encoding="utf-8")
    workspace = source.split("def _render_mixer_workspace", 1)[1].split("\ndef ", 1)[0]
    assert workspace.index("_mixer_and_downloads_fragment(") < workspace.index("render_song_studio(")
    assert "expanded=False" in workspace


def test_skips_are_recorded_for_native_products():
    text = Path("docs/plans/moises-parity/18-AGENT-FIRST.md").read_text(encoding="utf-8")
    for phrase in (
        "native apps are skipped",
        "VST / AU / AAX",
        "WASAPI/ASIO",
        "Google, Facebook, Apple, or X",
    ):
        assert phrase in text

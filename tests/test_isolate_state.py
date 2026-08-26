"""Tests for ui.isolate_state helpers."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from ui.isolate_state import (
    DEFAULT_SEPARATION_PRESET,
    DEFAULT_SPEED_PRESET,
    ISOLATE_OUTPUT_NAME_KEY,
    ISOLATE_OUTPUT_NAME_PENDING_KEY,
    ISOLATE_YOUTUBE_URL_KEY,
    ISOLATE_YOUTUBE_URL_PENDING_KEY,
    SPEED_PRESETS,
    apply_listen_picker_pending,
    apply_pending_output_name,
    apply_pending_youtube_url,
    apply_stored_isolate_ui_state,
    checklist_items,
    clamp_region_bounds,
    custom_selected_stems,
    default_region_end,
    estimate_job_seconds,
    estimate_remaining_seconds,
    estimated_stage_seconds,
    expects_guitar_stem,
    format_checklist_markdown,
    format_elapsed,
    format_eta_line,
    format_progress_label,
    format_source_caption,
    format_source_title,
    infer_source_kind,
    intra_stage_fraction,
    isolation_stages_for_job,
    isolate_ui_state_payload,
    listen_picker_default,
    load_persist_isolate_user_id,
    partition_queue_jobs,
    pending_upload_fp_for_stale,
    pick_library_row,
    plan_isolate_job_poll,
    queue_clear_youtube_url,
    queue_reopen_output_name,
    read_isolate_ui_state,
    recent_runs_with_owner_fallback,
    resolve_custom_separation,
    resolve_isolate_user_id,
    resolve_separation_preset,
    resolve_speed_preset,
    running_progress_view,
    seed_consumed_job_ids,
    select_rehydrate_row,
    session_mixer_artifacts_ok,
    should_auto_apply_job,
    should_hide_stale_results,
    stage_progress_percent,
    sync_output_name_on_upload,
    upload_fingerprint,
    write_isolate_ui_state,
    WORKSPACE_KEY,
    WORKSPACE_NEXT_KEY,
    LISTEN_PICKER_KEY,
    LISTEN_PICKER_NEXT_KEY,
)


def test_upload_fingerprint():
    f = SimpleNamespace(name="song.mp3", size=12345)
    assert upload_fingerprint(f) == "song.mp3:12345"
    assert upload_fingerprint(None) is None


def test_sync_output_name_on_upload_new_file():
    f = SimpleNamespace(name="new_track.wav", size=999)
    fp, name, changed = sync_output_name_on_upload(
        f, last_fp="old.wav:1", output_name="old"
    )
    assert fp == "new_track.wav:999"
    assert name == "new_track"
    assert changed is True


def test_sync_output_name_on_upload_same_file():
    f = SimpleNamespace(name="same.wav", size=100)
    fp, name, changed = sync_output_name_on_upload(
        f, last_fp="same.wav:100", output_name="same"
    )
    assert fp == "same.wav:100"
    assert name == "same"
    assert changed is False


def test_reopen_queues_output_name_without_touching_widget_key():
    """Reopen must not write isolate_output_name after the text_input exists."""
    session: dict[str, object] = {ISOLATE_OUTPUT_NAME_KEY: "old-name"}
    queue_reopen_output_name(session, "Past run title")
    assert session[ISOLATE_OUTPUT_NAME_KEY] == "old-name"
    assert session[ISOLATE_OUTPUT_NAME_PENDING_KEY] == "Past run title"
    applied = apply_pending_output_name(session)
    assert applied == "Past run title"
    assert session[ISOLATE_OUTPUT_NAME_KEY] == "Past run title"
    assert ISOLATE_OUTPUT_NAME_PENDING_KEY not in session


def test_apply_pending_output_name_noop_without_pending():
    session: dict[str, object] = {ISOLATE_OUTPUT_NAME_KEY: "keep"}
    assert apply_pending_output_name(session) is None
    assert session[ISOLATE_OUTPUT_NAME_KEY] == "keep"


def test_queue_clear_youtube_url_does_not_write_widget_key():
    session: dict[str, object] = {ISOLATE_YOUTUBE_URL_KEY: "https://youtu.be/abc"}
    queue_clear_youtube_url(session)
    assert session[ISOLATE_YOUTUBE_URL_KEY] == "https://youtu.be/abc"
    assert session[ISOLATE_YOUTUBE_URL_PENDING_KEY] == ""
    applied = apply_pending_youtube_url(session)
    assert applied == ""
    assert session[ISOLATE_YOUTUBE_URL_KEY] == ""
    assert ISOLATE_YOUTUBE_URL_PENDING_KEY not in session


def test_apply_pending_youtube_url_noop_without_pending():
    session: dict[str, object] = {ISOLATE_YOUTUBE_URL_KEY: "keep"}
    assert apply_pending_youtube_url(session) is None
    assert session[ISOLATE_YOUTUBE_URL_KEY] == "keep"


def test_isolate_reopen_handler_uses_pending_not_direct_widget_write():
    page = Path(__file__).resolve().parents[1] / "ui" / "pages" / "isolate.py"
    source = page.read_text(encoding="utf-8")
    assert "queue_reopen_output_name(st.session_state" in source
    assert 'st.session_state["isolate_output_name"] = title' not in source
    assert "apply_pending_output_name(st.session_state)" in source
    assert "apply_pending_youtube_url(st.session_state)" in source
    assert "queue_clear_youtube_url(st.session_state)" in source
    assert "this is not parallel" not in source
    assert "isolate_queue_expanded" not in source
    assert "_open_mixer_workspace()" in source
    assert "_open_queue_workspace()" in source
    assert 'WORKSPACE_NEXT_KEY] = "Queue"' in source
    assert "delete_library_run" in source
    assert "_confirm_separate_dialog" not in source
    assert "Confirm separation" not in source
    assert "Live mixer and downloads are on Mixer." in source
    assert "time.sleep" not in source
    assert "tab_new.open" not in source
    assert "streamlit_local_storage" not in source
    assert "plan_isolate_job_poll" in source
    assert "isolate_refresh" in source
    assert "partition_queue_jobs" in source
    assert 'vertical_alignment="center"' in source
    assert 'key="isolate_delete_all_finished"' in source
    assert "delete_finished_" in source
    assert "stop_job_" in source
    assert "_rehydrate_artifacts_from_disk(browser_id)" in source
    assert "_restore_isolate_ui_state()" in source
    assert "key=LISTEN_PICKER_KEY" in source
    assert 'key="isolate_viewing_run_dir"' not in source
    assert 'vertical_alignment="bottom"' in source
    assert "LISTEN_PICKER_NEXT_KEY" in source
    sep_src = source[source.find("def _render_separation_controls") : source.find("def _ffmpeg_install_hint")]
    yt_apply_at = sep_src.find("apply_pending_youtube_url(st.session_state)")
    yt_input_at = sep_src.find('key="isolate_youtube_url"')
    assert yt_apply_at != -1 and yt_input_at != -1 and yt_apply_at < yt_input_at
    main_src = source[source.find("def main()") :]
    uid_at = main_src.find("browser_id = _get_browser_user_id()")
    rehydrate_at = main_src.find("_rehydrate_artifacts_from_disk(browser_id)")
    assert uid_at != -1 and rehydrate_at != -1 and uid_at < rehydrate_at


def test_resolve_isolate_user_id_mints_without_stored():
    session: dict = {}
    first = resolve_isolate_user_id(session, None)
    assert len(first) == 32
    assert session["isolate_user_id"] == first
    assert resolve_isolate_user_id(session, "from-browser") == first


def test_resolve_isolate_user_id_uses_stored_when_session_empty():
    session: dict = {}
    assert resolve_isolate_user_id(session, "  abc123  ") == "abc123"
    assert session["isolate_user_id"] == "abc123"


def test_pending_upload_fp_for_stale_uses_disk_not_uploader(tmp_path):
    staged = tmp_path / "song.wav"
    staged.write_bytes(b"x")
    session = {
        "isolate_pending_fp": "song.wav:1",
        "isolate_pending_audio_path": str(staged),
        "isolate_youtube_enabled": False,
    }
    assert pending_upload_fp_for_stale(session) == "song.wav:1"
    session["isolate_pending_audio_path"] = str(tmp_path / "missing.wav")
    assert pending_upload_fp_for_stale(session) is None
    session["isolate_youtube_enabled"] = True
    session["isolate_youtube_url"] = "https://youtu.be/abc"
    assert pending_upload_fp_for_stale(session) == "song.wav:1"


def test_infer_source_kind_from_fingerprint_and_url():
    assert infer_source_kind(source_fingerprint="youtube:https://youtu.be/abc") == "youtube"
    assert infer_source_kind(source_fingerprint="song.mp3:123") == "file"
    assert infer_source_kind(youtube_url="https://youtu.be/abc") == "youtube"
    assert infer_source_kind() == "file"


def test_infer_source_kind_explicit_wins():
    assert (
        infer_source_kind(
            source_kind="file",
            source_fingerprint="youtube:https://youtu.be/abc",
            youtube_url="https://youtu.be/abc",
        )
        == "file"
    )
    assert infer_source_kind(source_kind="youtube", source_fingerprint="song.mp3:1") == "youtube"


def test_format_source_title_and_caption():
    assert format_source_title("Party Wadokoni_", "youtube") == "YouTube · Party Wadokoni_"
    assert format_source_title("Calm Like You", "file") == "File · Calm Like You"
    assert format_source_title("  ", "youtube") == "YouTube · tracks"
    assert format_source_caption("Party Wadokoni_", "youtube") == "**Party Wadokoni_** · YouTube"
    assert (
        format_source_caption("Calm Like You", "file", filename="Calm Like You.wav")
        == "**Calm Like You** · File (`Calm Like You.wav`)"
    )
    assert (
        format_source_caption(
            "Party Wadokoni_",
            "youtube",
            region_label="0:10–0:40",
            clip_length=30,
        )
        == "**Party Wadokoni_** · 0:10–0:40 (30 s) · YouTube"
    )


def test_apply_workspace_tab_defaults_and_mixer_pin():
    from ui.isolate_state import apply_workspace_tab

    session: dict = {}
    assert apply_workspace_tab(session, has_artifacts=False) == "New"
    session = {}
    assert apply_workspace_tab(session, has_artifacts=True) == "New"
    session = {WORKSPACE_KEY: "New", WORKSPACE_NEXT_KEY: "Mixer"}
    assert apply_workspace_tab(session, has_artifacts=False) == "Mixer"
    assert session[WORKSPACE_KEY] == "Mixer"
    assert WORKSPACE_NEXT_KEY not in session
    session = {WORKSPACE_KEY: "Queue"}
    assert apply_workspace_tab(session, has_artifacts=True) == "Queue"


def test_partition_queue_jobs_includes_succeeded():
    jobs = [
        {"id": "s1", "status": "succeeded"},
        {"id": "r1", "status": "running"},
        {"id": "q1", "status": "queued"},
    ]
    parts = partition_queue_jobs(jobs)
    assert [j["id"] for j in parts["in_flight"]] == ["r1", "q1"]
    assert [j["id"] for j in parts["succeeded"]] == ["s1"]
    assert parts["empty"] is False
    assert partition_queue_jobs([])["empty"] is True


def test_recent_runs_with_owner_fallback():
    owned = [{"run_dir": "/mine"}]
    all_runs = [{"run_dir": "/mine"}, {"run_dir": "/other"}]
    assert recent_runs_with_owner_fallback(owned, all_runs) == owned
    assert recent_runs_with_owner_fallback([], all_runs) == all_runs


def test_pick_library_row_prefers_last_viewed():
    rows = [
        {"run_dir": "/runs/new", "title": "New"},
        {"run_dir": "/runs/old", "title": "Old"},
    ]
    assert pick_library_row(rows, "/runs/old")["title"] == "Old"
    assert pick_library_row(rows, None)["title"] == "New"
    assert pick_library_row([], "/runs/old") is None


def test_listen_picker_default_prefers_loaded_run():
    options = ["/runs/new", "/runs/loaded", "/runs/old"]
    assert listen_picker_default(options, "/runs/loaded", "/runs/new") == "/runs/loaded"
    assert listen_picker_default(options, "/runs/gone", "/runs/old") == "/runs/old"
    assert listen_picker_default(options, None, "/runs/missing") == "/runs/new"
    assert listen_picker_default([], "/runs/loaded", "/runs/old") is None


def test_apply_listen_picker_pending_sets_widget_key():
    session = {LISTEN_PICKER_NEXT_KEY: "/runs/keep"}
    apply_listen_picker_pending(session)
    assert session[LISTEN_PICKER_KEY] == "/runs/keep"
    assert LISTEN_PICKER_NEXT_KEY not in session
    apply_listen_picker_pending(session)
    assert session[LISTEN_PICKER_KEY] == "/runs/keep"


def test_select_rehydrate_row_loads_latest_when_session_empty():
    rows = [{"run_dir": "/runs/new", "title": "New"}, {"run_dir": "/runs/old", "title": "Old"}]
    assert select_rehydrate_row({}, rows, wav_exists=lambda _: True)["title"] == "New"


def test_select_rehydrate_row_skips_when_session_wavs_ok():
    session = {"isolate_artifacts": {"vocals": "/a.wav"}}
    rows = [{"run_dir": "/runs/new"}]
    assert select_rehydrate_row(session, rows, wav_exists=lambda _: True) is None
    assert session_mixer_artifacts_ok(session, wav_exists=lambda _: True) is True


def test_select_rehydrate_row_prefers_last_viewed():
    session = {"isolate_viewing_run_dir": "/runs/old"}
    rows = [{"run_dir": "/runs/new"}, {"run_dir": "/runs/old"}]
    assert select_rehydrate_row(session, rows, wav_exists=lambda _: False)["run_dir"] == "/runs/old"


def test_owner_filter_miss_rehydrates_via_jobs():
    from ui.isolate_jobs import merge_library_runs

    recent = recent_runs_with_owner_fallback([], [])
    jobs = [
        {
            "status": "succeeded",
            "run_dir": "/runs/job",
            "created_at": 2,
            "title": "From job",
        }
    ]
    merged = merge_library_runs(recent, jobs)
    row = select_rehydrate_row({}, merged, wav_exists=lambda _: True)
    assert row is not None
    assert row["title"] == "From job"


def test_isolate_ui_state_payload_prefers_next_tab():
    payload = isolate_ui_state_payload(
        {
            WORKSPACE_KEY: "New",
            WORKSPACE_NEXT_KEY: "Mixer",
            "isolate_viewing_run_dir": "/runs/a",
        }
    )
    assert payload["workspace"] == "Mixer"
    assert payload["viewing_run_dir"] == "/runs/a"


def test_isolate_ui_state_round_trip(tmp_path):
    path = tmp_path / "isolate_ui_state.json"
    session = {
        WORKSPACE_KEY: "Mixer",
        "isolate_viewing_run_dir": "/runs/a",
        "isolate_run_dir": "/runs/a",
    }
    payload = isolate_ui_state_payload(session)
    write_isolate_ui_state(path, payload)
    stored = read_isolate_ui_state(path)
    assert stored["workspace"] == "Mixer"
    assert stored["viewing_run_dir"] == "/runs/a"
    empty: dict = {}
    apply_stored_isolate_ui_state(empty, stored)
    assert empty[WORKSPACE_KEY] == "Mixer"
    assert empty["isolate_viewing_run_dir"] == "/runs/a"
    live = {WORKSPACE_KEY: "Queue"}
    apply_stored_isolate_ui_state(live, stored)
    assert live[WORKSPACE_KEY] == "Queue"


def test_fresh_session_poll_does_not_rerun_for_historical_jobs():
    jobs = [
        {"id": "a", "status": "succeeded"},
        {"id": "b", "status": "succeeded"},
        {"id": "c", "status": "succeeded"},
    ]
    assert seed_consumed_job_ids(jobs) == ["a", "b", "c"]
    plan = plan_isolate_job_poll(
        jobs, consumed_ids=None, viewing_id=None, form_drawn=False
    )
    assert plan["apply_job"] is None
    assert plan["rerun"] is False
    assert plan["consumed_ids"] == ["a", "b", "c"]
    again = plan_isolate_job_poll(
        jobs,
        consumed_ids=plan["consumed_ids"],
        viewing_id=None,
        form_drawn=True,
    )
    assert again["apply_job"] is None
    assert again["rerun"] is False


def test_poll_defers_new_success_until_form_is_drawn():
    jobs = [
        {"id": "old", "status": "succeeded"},
        {"id": "new", "status": "succeeded"},
    ]
    seeded = plan_isolate_job_poll(
        [{"id": "old", "status": "succeeded"}],
        consumed_ids=None,
        viewing_id=None,
        form_drawn=False,
    )["consumed_ids"]
    deferred = plan_isolate_job_poll(
        jobs, consumed_ids=seeded, viewing_id=None, form_drawn=False
    )
    assert deferred["apply_job"] is None
    assert deferred["rerun"] is False
    assert deferred["consumed_ids"] == ["old"]
    ready = plan_isolate_job_poll(
        jobs, consumed_ids=seeded, viewing_id=None, form_drawn=True
    )
    assert ready["apply_job"]["id"] == "new"
    assert ready["rerun"] is True
    assert ready["consumed_ids"] == ["old", "new"]
    settled = plan_isolate_job_poll(
        jobs, consumed_ids=ready["consumed_ids"], viewing_id=None, form_drawn=True
    )
    assert settled["apply_job"] is None
    assert settled["rerun"] is False


def test_load_persist_isolate_user_id_round_trip(tmp_path):
    path = tmp_path / "isolate_user_id"
    first = load_persist_isolate_user_id({}, path)
    assert path.read_text(encoding="utf-8") == first
    again = load_persist_isolate_user_id({}, path)
    assert again == first


def test_should_hide_stale_results():
    assert not should_hide_stale_results(pending_upload_fp=None, has_artifacts=True)
    assert not should_hide_stale_results(pending_upload_fp="x:1", has_artifacts=False)
    assert should_hide_stale_results(pending_upload_fp="new.mp3:500", has_artifacts=True)
    # Same fingerprint as the run that produced results → do not hide mixer.
    assert not should_hide_stale_results(
        pending_upload_fp="same.mp3:1",
        has_artifacts=True,
        results_source_fp="same.mp3:1",
    )
    assert should_hide_stale_results(
        pending_upload_fp="new.mp3:2",
        has_artifacts=True,
        results_source_fp="old.mp3:1",
    )


def test_pending_audio_needs_resave():
    from ui.isolate_state import pending_audio_needs_resave

    assert pending_audio_needs_resave(
        uploaded_fp="a.wav:1", pending_fp=None, pending_path_exists=False
    )
    assert not pending_audio_needs_resave(
        uploaded_fp="a.wav:1", pending_fp="a.wav:1", pending_path_exists=True
    )
    assert pending_audio_needs_resave(
        uploaded_fp="b.wav:2", pending_fp="a.wav:1", pending_path_exists=True
    )


def test_stage_progress_percent_weighted():
    # Current stage counts only via ``intra`` (0 = just started, 1 = finished).
    assert stage_progress_percent("ingest", intra=0.0) == pytest.approx(0.0)
    assert stage_progress_percent("ingest", intra=1.0) == pytest.approx(0.05)
    assert stage_progress_percent("separate", intra=0.0) == pytest.approx(0.05)
    assert stage_progress_percent("separate", intra=1.0) == pytest.approx(0.85)
    assert stage_progress_percent("done", intra=1.0) == pytest.approx(1.0)
    assert stage_progress_percent("unknown") == 0.0


def test_stage_progress_first_mid_last_and_guitar_skipped():
    full = isolation_stages_for_job(expects_guitar=True)
    assert stage_progress_percent("ingest", stages=full, intra=0.0) == pytest.approx(0.0)

    mid = stage_progress_percent("separate", stages=full, intra=0.0)
    assert mid == pytest.approx(0.05)
    assert 0.0 < mid < 1.0

    assert stage_progress_percent("done", stages=full, intra=1.0) == pytest.approx(1.0)

    full = isolation_stages_for_job(expects_guitar=True)
    assert "guitar_split" not in full
    assert "bass_bleed" in full

    skipped = isolation_stages_for_job(expects_guitar=False)
    assert "guitar_split" not in skipped
    assert "bass_bleed" not in skipped
    # Weights without bass_bleed: 0.05+0.80+0.05+0.03+0.02 = 0.95
    assert stage_progress_percent("separate", stages=skipped, intra=0.0) == pytest.approx(
        0.05 / 0.95
    )


def test_checklist_first_mid_last_and_guitar_skipped():
    full = isolation_stages_for_job(expects_guitar=True)
    first = checklist_items(full, "ingest")
    assert first[0]["state"] == "current"
    assert first[0]["id"] == "ingest"
    assert all(row["state"] == "pending" for row in first[1:])

    mid = checklist_items(full, "separate")
    assert mid[0]["state"] == "done"
    assert mid[1]["state"] == "current"
    assert mid[1]["id"] == "separate"
    assert all(row["state"] == "pending" for row in mid[2:])

    last = checklist_items(full, "done", complete=True)
    assert all(row["state"] == "done" for row in last)

    skipped = isolation_stages_for_job(expects_guitar=False)
    ids = [row["id"] for row in checklist_items(skipped, "ingest")]
    assert "guitar_split" not in ids
    assert "bass_bleed" not in ids
    text = format_checklist_markdown(checklist_items(skipped, "separate"))
    assert "[now]" in text
    assert "[done]" in text
    assert "[todo]" in text
    assert "Split lead / rhythm" not in text


def test_expects_guitar_stem():
    assert expects_guitar_stem(model="htdemucs_6s") is True
    assert expects_guitar_stem(model="htdemucs", two_stems="vocals") is False
    assert expects_guitar_stem(model="htdemucs") is False
    assert expects_guitar_stem(model="htdemucs", custom_stems=["guitar", "vocals"]) is True
    assert expects_guitar_stem(model="htdemucs_6s", custom_stems=["vocals"]) is False


def test_intra_stage_fraction_caps_and_unestimated():
    frac, estimated = intra_stage_fraction(30.0, 60.0)
    assert estimated is True
    assert frac == pytest.approx(0.5)
    capped, _ = intra_stage_fraction(1000.0, 60.0)
    assert capped == pytest.approx(0.95)
    none, is_est = intra_stage_fraction(10.0, None)
    assert none == 0.0
    assert is_est is False


def test_estimate_job_and_remaining_eta():
    stages = isolation_stages_for_job(expects_guitar=True)
    heuristic, conf = estimate_job_seconds(
        audio_duration_sec=60.0,
        quality="fast",
        device="cpu",
        stages=stages,
    )
    assert heuristic is not None and heuristic > 0
    assert conf == "low"

    scaled, high = estimate_job_seconds(
        audio_duration_sec=90.0,
        quality="fast",
        device="cpu",
        stages=stages,
        model="htdemucs_6s",
        expects_guitar=True,
        last_run={
            "wall_sec": 80.0,
            "audio_sec": 60.0,
            "quality": "fast",
            "device": "cpu",
            "model": "htdemucs_6s",
            "expects_guitar": True,
        },
    )
    assert high == "high"
    assert scaled == pytest.approx(120.0)

    remaining, _ = estimate_remaining_seconds(
        elapsed_sec=10.0,
        percent=0.25,
        total_estimate=80.0,
        confidence="low",
    )
    assert remaining is not None and remaining > 0

    none_left, none_conf = estimate_remaining_seconds(
        elapsed_sec=0.5,
        percent=0.0,
        total_estimate=None,
        confidence="low",
    )
    assert none_left is None
    assert none_conf == "low"

    stage_share = estimated_stage_seconds("separate", stages, 100.0)
    # separate is 0.80 of active weights (no guitar_split stage).
    assert stage_share == pytest.approx(80.0)

    assert format_eta_line(9, None).endswith("estimating…")
    assert "~2:40 left" in format_eta_line(9, 160)
    assert format_eta_line(80, 0.2) == "Elapsed 1:20"


def test_format_progress_label():
    assert format_progress_label(0.42, "Running Demucs") == "42% — Running Demucs"
    assert format_progress_label(0.42, "Running Demucs", estimated=True) == (
        "~42% — Running Demucs"
    )


def test_format_elapsed():
    assert format_elapsed(65) == "1:05"
    assert format_elapsed(0) == "0:00"


def test_running_progress_view_has_label_elapsed_eta_and_checklist():
    stages = isolation_stages_for_job(expects_guitar=True)
    started = 1_000.0
    view = running_progress_view(
        {
            "status": "running",
            "stage": "separate",
            "message": "Running Demucs…",
            "started_at": started,
            "stage_started_at": started,
            "job_estimate_sec": 120.0,
            "estimate_confidence": "low",
            "stages": list(stages),
            "progress": 0.1,
        },
        now=started + 12.0,
    )
    assert view["percent"] > 0
    assert view["percent"] < 1
    assert "Separate tracks" in view["label"] or "%" in view["label"]
    assert "Elapsed" in view["eta_line"]
    assert "[now]" in view["checklist_md"]
    assert "Prepare audio" in view["checklist_md"]


def test_running_progress_view_estimating_without_job_estimate():
    view = running_progress_view(
        {
            "status": "running",
            "stage": "ingest",
            "message": "Preparing audio…",
            "started_at": 10.0,
            "stage_started_at": 10.0,
            "job_estimate_sec": None,
            "stages": ["ingest", "separate", "collect", "presence", "done"],
        },
        now=11.0,
    )
    assert "estimating…" in view["eta_line"]


def test_should_auto_apply_job_respects_pin():
    assert should_auto_apply_job(None, "job-a") is True
    assert should_auto_apply_job("latest", "job-a") is True
    assert should_auto_apply_job("job-a", "job-a") is True
    assert should_auto_apply_job("job-old", "job-a") is False


def test_resolve_separation_preset_full_band():
    resolved = resolve_separation_preset("full_band")
    assert resolved["model"] == "htdemucs_6s"
    assert resolved["two_stems"] is None
    assert resolved["track_count"] == 6
    assert "Guitar" in resolved["tracks"]


def test_resolve_separation_preset_essential():
    resolved = resolve_separation_preset("essential")
    assert resolved["model"] == "htdemucs"
    assert resolved["two_stems"] is None
    assert resolved["track_count"] == 4


def test_resolve_separation_preset_vocals_music():
    resolved = resolve_separation_preset("vocals_music")
    assert resolved["model"] == "htdemucs"
    assert resolved["two_stems"] == "vocals"
    assert resolved["track_count"] == 2
    assert "Instrumental" in resolved["tracks"]


def test_resolve_separation_preset_unknown_falls_back():
    resolved = resolve_separation_preset("not_a_real_preset")
    assert resolved["id"] == DEFAULT_SEPARATION_PRESET
    assert resolved["model"] == "htdemucs_6s"


def test_resolve_custom_separation_vocals_only_uses_two_stem_split():
    resolved = resolve_custom_separation(["vocals"])
    assert resolved["model"] == "htdemucs"
    assert resolved["two_stems"] == "vocals"
    assert resolved["stems"] == ["vocals"]


def test_resolve_custom_separation_piano_and_vocals_needs_six_stem_model():
    resolved = resolve_custom_separation(["piano", "vocals"])
    assert resolved["model"] == "htdemucs_6s"
    assert resolved["two_stems"] is None
    assert resolved["stems"] == ["vocals", "piano"]
    assert resolved["tracks"] == "Vocals, Piano"


def test_resolve_custom_separation_guitar_needs_six_stem_model():
    resolved = resolve_custom_separation(["guitar"])
    assert resolved["model"] == "htdemucs_6s"
    assert resolved["two_stems"] is None


def test_resolve_custom_separation_drums_and_bass_use_four_stem_model():
    resolved = resolve_custom_separation(["bass", "drums"])
    assert resolved["model"] == "htdemucs"
    assert resolved["two_stems"] is None
    assert resolved["stems"] == ["drums", "bass"]


def test_resolve_custom_separation_ignores_unknown_picks():
    resolved = resolve_custom_separation(["drums", "kazoo", "drums"])
    assert resolved["stems"] == ["drums"]


def test_resolve_custom_separation_requires_a_pick():
    with pytest.raises(ValueError):
        resolve_custom_separation([])
    with pytest.raises(ValueError):
        resolve_custom_separation(["kazoo"])


def test_resolve_custom_separation_has_no_caveat():
    assert resolve_custom_separation(["vocals"])["caveat"] == ""


def test_custom_selected_stems_only_turns_on_requested_instruments():
    selected = custom_selected_stems(
        ["vocals", "drums", "bass", "guitar", "piano", "other"],
        ["vocals", "piano"],
    )
    assert selected == {
        "vocals": True,
        "drums": False,
        "bass": False,
        "guitar": False,
        "piano": True,
        "other": False,
    }


def test_custom_selected_stems_combined_guitar_only():
    selected = custom_selected_stems(
        ["guitar", "lead_guitar", "rhythm_guitar", "vocals"],
        ["guitar"],
    )
    # Default path maps guitar → guitar only (no lead/rhythm ids).
    assert selected["guitar"] is True
    assert selected["lead_guitar"] is False
    assert selected["rhythm_guitar"] is False
    assert selected["vocals"] is False


def test_custom_selected_stems_keeps_combined_guitar_without_a_split():
    selected = custom_selected_stems(["guitar", "vocals"], ["guitar"])
    assert selected["guitar"] is True


def test_custom_selected_stems_falls_back_to_all_when_nothing_matches():
    selected = custom_selected_stems(["vocals", "no_vocals"], ["drums"])
    assert selected == {"vocals": True, "no_vocals": True}


def test_resolve_speed_preset_faster():
    resolved = resolve_speed_preset("faster")
    assert resolved["quality"] == "fast"
    assert resolved["device"] == "cpu"
    assert resolved["id"] == "faster"


def test_resolve_speed_preset_balanced():
    resolved = resolve_speed_preset("balanced")
    assert resolved["quality"] == "balanced"
    assert resolved["device"] == "cpu"


def test_resolve_speed_preset_best():
    resolved = resolve_speed_preset("best")
    assert resolved["quality"] == "high"
    assert resolved["device"] == "cpu"


def test_resolve_speed_preset_unknown_falls_back():
    resolved = resolve_speed_preset("unknown")
    assert resolved["id"] == DEFAULT_SPEED_PRESET


def test_default_speed_preset_is_auto():
    assert DEFAULT_SPEED_PRESET == "auto"
    assert "auto" in SPEED_PRESETS


def test_resolve_speed_preset_auto_uses_cuda_probe_on_windows():
    from audio_to_tab.hardware import HostProbe

    probe = HostProbe(cuda=True, mps=False, ram_gb=24.0)
    resolved = resolve_speed_preset("auto", probe, platform="win32")
    assert resolved["id"] == "auto"
    assert resolved["device"] == "cuda"
    assert resolved["quality"] == "balanced"


def test_resolve_speed_preset_best_uses_cuda_probe_on_windows():
    from audio_to_tab.hardware import HostProbe

    probe = HostProbe(cuda=True, mps=False, ram_gb=24.0)
    resolved = resolve_speed_preset("best", probe, platform="win32")
    assert resolved["device"] == "cuda"
    assert resolved["quality"] == "high"


def test_default_region_end():
    assert default_region_end(120.0) == 30.0
    assert default_region_end(10.0) == 10.0


def test_clamp_region_bounds():
    start, end = clamp_region_bounds(0, 3, 120.0, min_length=5.0)
    assert end - start >= 5.0


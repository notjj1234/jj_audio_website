"""Tests for ui.isolate_state helpers."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from ui.isolate_state import (
    DEFAULT_SEPARATION_PRESET,
    DEFAULT_SPEED_PRESET,
    DEFAULT_TRACK_OPTIONS,
    CUSTOM_STEM_CHOICES,
    ISOLATE_OUTPUT_NAME_KEY,
    ISOLATE_OUTPUT_NAME_PENDING_KEY,
    ISOLATE_AUTO_OUTPUT_NAME_KEY,
    ISOLATE_NAMED_YOUTUBE_URL_KEY,
    ISOLATE_YOUTUBE_URL_KEY,
    ISOLATE_YOUTUBE_URL_PENDING_KEY,
    SPEED_PRESETS,
    apply_listen_picker_pending,
    apply_pending_output_name,
    apply_pending_youtube_url,
    apply_stored_isolate_ui_state,
    apply_youtube_output_name_sync,
    checklist_items,
    clamp_region_bounds,
    custom_selected_stems,
    default_guitar_track_option,
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
    guitar_track_radio_ids,
    infer_source_kind,
    job_requires_roformer_backend,
    intra_stage_fraction,
    isolation_stages_for_job,
    isolate_ui_state_payload,
    listen_picker_default,
    load_persist_isolate_user_id,
    partition_queue_jobs,
    pending_upload_fp_for_stale,
    pick_library_row,
    plan_isolate_job_poll,
    promote_default_guitar_option,
    queue_clear_youtube_url,
    queue_output_name_if_empty,
    queue_reopen_output_name,
    queue_youtube_url,
    read_isolate_ui_state,
    recent_runs_with_owner_fallback,
    reset_new_tab_source,
    resolve_custom_separation,
    resolve_isolate_user_id,
    resolve_separation_preset,
    resolve_speed_preset,
    resolve_track_selection,
    resolve_youtube_job_name,
    running_progress_view,
    normalize_guitar_track_selection,
    tracks_picker_help,
    seed_consumed_job_ids,
    seed_notified_job_ids,
    os_notify_message,
    jobs_needing_os_notify,
    select_rehydrate_row,
    session_mixer_artifacts_ok,
    should_auto_apply_job,
    staged_audio_for_new_tab,
    should_hide_stale_results,
    stage_progress_percent,
    user_progress_hint,
    youtube_label_from_url,
    youtube_video_id,
    sync_output_name_on_upload,
    sync_output_name_on_youtube,
    upload_fingerprint,
    write_isolate_ui_state,
    WORKSPACE_KEY,
    WORKSPACE_NEXT_KEY,
    LISTEN_PICKER_KEY,
    LISTEN_PICKER_NEXT_KEY,
)


@pytest.fixture(autouse=True)
def _cpu_edition_by_default(monkeypatch):
    monkeypatch.delenv("AUDIO_TOOLS_EDITION", raising=False)


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


def test_queue_output_name_if_empty_skips_when_name_set():
    session: dict[str, object] = {ISOLATE_OUTPUT_NAME_KEY: "keep-me"}
    queue_output_name_if_empty(session, "from-youtube")
    assert session[ISOLATE_OUTPUT_NAME_KEY] == "keep-me"
    assert ISOLATE_OUTPUT_NAME_PENDING_KEY not in session


def test_queue_output_name_if_empty_queues_pending_when_blank():
    session: dict[str, object] = {ISOLATE_OUTPUT_NAME_KEY: "  "}
    queue_output_name_if_empty(session, "yt-stem")
    assert session[ISOLATE_OUTPUT_NAME_KEY] == "  "
    assert session[ISOLATE_OUTPUT_NAME_PENDING_KEY] == "yt-stem"
    applied = apply_pending_output_name(session)
    assert applied == "yt-stem"
    assert session[ISOLATE_OUTPUT_NAME_KEY] == "yt-stem"


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


def test_queue_youtube_url_fills_widget_on_apply():
    session: dict[str, object] = {}
    queue_youtube_url(session, "https://www.youtube.com/watch?v=BaW_jenozKc")
    assert ISOLATE_YOUTUBE_URL_KEY not in session
    applied = apply_pending_youtube_url(session)
    assert applied == "https://www.youtube.com/watch?v=BaW_jenozKc"
    assert session[ISOLATE_YOUTUBE_URL_KEY] == applied
    assert ISOLATE_YOUTUBE_URL_PENDING_KEY not in session


def test_apply_pending_youtube_url_noop_without_pending():
    session: dict[str, object] = {ISOLATE_YOUTUBE_URL_KEY: "keep"}
    assert apply_pending_youtube_url(session) is None
    assert session[ISOLATE_YOUTUBE_URL_KEY] == "keep"


def test_reset_new_tab_source_remounts_uploader_without_touching_widget_keys():
    session: dict[str, object] = {
        "isolate_upload_key": 3,
        "isolate_upload_fp": "a.wav:1",
        "isolate_pending_audio_path": "/tmp/a.wav",
        "isolate_pending_fp": "a.wav:1",
        "isolate_duration_sec": 12.0,
        "isolate_duration_fp": "a.wav:1",
        "carry_over_audio_path": "/tmp/c.wav",
        "carry_over_audio_name": "c.wav",
        ISOLATE_OUTPUT_NAME_KEY: "Song A",
        ISOLATE_YOUTUBE_URL_KEY: "https://youtu.be/abc",
    }
    reset_new_tab_source(session)
    assert session["isolate_upload_key"] == 4
    assert "isolate_pending_audio_path" not in session
    assert "isolate_pending_fp" not in session
    assert "isolate_upload_fp" not in session
    assert "isolate_duration_sec" not in session
    assert "carry_over_audio_path" not in session
    assert "carry_over_audio_name" not in session
    assert session[ISOLATE_OUTPUT_NAME_KEY] == "Song A"
    assert session[ISOLATE_YOUTUBE_URL_KEY] == "https://youtu.be/abc"
    assert session[ISOLATE_YOUTUBE_URL_PENDING_KEY] == ""
    assert session[ISOLATE_OUTPUT_NAME_PENDING_KEY] == ""
    apply_pending_output_name(session)
    apply_pending_youtube_url(session)
    assert session[ISOLATE_OUTPUT_NAME_KEY] == ""
    assert session[ISOLATE_YOUTUBE_URL_KEY] == ""


def test_youtube_video_id_from_common_urls():
    assert youtube_video_id("https://www.youtube.com/watch?v=BaW_jenozKc") == "BaW_jenozKc"
    assert youtube_video_id("https://youtu.be/abc123XYZ_-") == "abc123XYZ_-"
    assert youtube_video_id("https://www.youtube.com/shorts/shortId99") == "shortId99"
    assert youtube_video_id("https://example.com/watch?v=abc") is None
    assert youtube_label_from_url("https://youtu.be/abc") == "abc"
    assert youtube_label_from_url("not-a-url") == "youtube_audio"


def test_resolve_youtube_job_name_empty_prefers_downloaded_stem():
    assert (
        resolve_youtube_job_name("", "https://youtu.be/BaW_jenozKc", "ACDC - Back in Black")
        == "ACDC - Back in Black"
    )


def test_resolve_youtube_job_name_upgrades_video_id_default_to_real_title():
    assert (
        resolve_youtube_job_name("BaW_jenozKc", "https://youtu.be/BaW_jenozKc", "ACDC - Back in Black")
        == "ACDC - Back in Black"
    )


def test_resolve_youtube_job_name_keeps_user_edited_name():
    assert (
        resolve_youtube_job_name("My custom mix", "https://youtu.be/BaW_jenozKc", "ACDC - Back in Black")
        == "My custom mix"
    )


def test_resolve_youtube_job_name_non_youtube_falls_back_to_stem():
    assert resolve_youtube_job_name("", "https://example.com/song.wav", "song") == "song"
    assert resolve_youtube_job_name("my song", "", "song") == "my song"


def test_sync_output_name_on_youtube_new_url_replaces_old_title():
    name, named, auto, changed = sync_output_name_on_youtube(
        youtube_url="https://youtu.be/newvid",
        last_named_url="https://youtu.be/oldvid",
        output_name="Megadeth - Holy Wars",
        auto_output_name="Megadeth - Holy Wars",
    )
    assert changed is True
    assert name == "newvid"
    assert named == "https://youtu.be/newvid"
    assert auto == "newvid"


def test_sync_output_name_on_youtube_download_upgrades_auto_label():
    url = "https://youtu.be/newvid"
    name, named, auto, changed = sync_output_name_on_youtube(
        youtube_url=url,
        last_named_url=url,
        output_name="newvid",
        auto_output_name="newvid",
        downloaded_stem="Other Band - Other Song",
    )
    assert changed is True
    assert name == "Other Band - Other Song"
    assert named == url
    assert auto == "Other Band - Other Song"


def test_sync_output_name_on_youtube_keeps_user_edit_on_same_url():
    url = "https://youtu.be/newvid"
    name, named, auto, changed = sync_output_name_on_youtube(
        youtube_url=url,
        last_named_url=url,
        output_name="My custom mix",
        auto_output_name="newvid",
        downloaded_stem="Other Band - Other Song",
    )
    assert changed is False
    assert name == "My custom mix"
    assert named == url
    assert auto == "newvid"


def test_apply_youtube_output_name_sync_queues_before_widget():
    session: dict[str, object] = {
        "isolate_youtube_enabled": True,
        ISOLATE_YOUTUBE_URL_KEY: "https://youtu.be/newvid",
        ISOLATE_OUTPUT_NAME_KEY: "Megadeth - Holy Wars",
        ISOLATE_NAMED_YOUTUBE_URL_KEY: "https://youtu.be/oldvid",
        ISOLATE_AUTO_OUTPUT_NAME_KEY: "Megadeth - Holy Wars",
    }
    applied = apply_youtube_output_name_sync(session)
    assert applied == "newvid"
    assert session[ISOLATE_OUTPUT_NAME_KEY] == "newvid"
    assert ISOLATE_OUTPUT_NAME_PENDING_KEY not in session


def test_stem_presence_selector_uses_fixed_three_columns():
    page = Path(__file__).resolve().parents[1] / "ui" / "pages" / "isolate.py"
    source = page.read_text(encoding="utf-8")
    fn_src = source[
        source.find("def _render_stem_presence_selector") : source.find("def _build_current_mix")
    ]
    assert "cols_per_row = 3" in fn_src
    assert "st.columns(cols_per_row)" in fn_src
    assert "st.columns(len(row_names))" not in fn_src


def test_running_progress_renderer_is_barebones():
    page = Path(__file__).resolve().parents[1] / "ui" / "pages" / "isolate.py"
    source = page.read_text(encoding="utf-8")
    fn_src = source[
        source.find("def _render_running_progress") : source.find("def _job_source_title")
    ]
    assert 'st.caption(view["message"])' not in fn_src
    assert "checklist_md" not in fn_src
    assert 'view.get("hint")' in fn_src


def test_mixer_picker_lives_in_fragment_with_stable_run_key():
    page = Path(__file__).resolve().parents[1] / "ui" / "pages" / "isolate.py"
    source = page.read_text(encoding="utf-8")
    frag = source[
        source.find("def _mixer_and_downloads_fragment") : source.find(
            "def _resolve_audio_for_job"
        )
    ]
    assert "_render_stem_presence_selector" in frag
    assert "stem_mixer_run_" in source
    assert 'key=f"stem_mixer_{fingerprint}"' not in source
    mixer_ws = source[
        source.find("def _render_mixer_workspace") : source.find("def _render_file_ready_banner")
    ]
    assert "_render_stem_presence_selector" not in mixer_ws
    assert "Save all tracks" in frag
    assert "Open folder" in frag
    assert "Download finished" in frag
    assert "ISOLATE_EXPORT_DIR_KEY" in frag
    panel = source[
        source.find("def _render_downloads_panel") : source.find("def _resolve_audio_for_job")
    ]
    assert "st.container(border=True" in panel
    assert 'width="stretch"' in panel
    assert 'key="isolate_choose_export_dir"' in panel
    assert 'key="isolate_open_export_dir"' in panel
    assert 'key="isolate_save_tracks"' in panel
    assert "Browser download (zip)" not in panel
    assert "st.download_button" not in panel
    assert "isolate_save_as" not in panel
    assert "Make a tab PDF from this" not in panel
    assert "Make a tab PDF from this" in mixer_ws
    assert 'st.caption("Other tools")' in mixer_ws
    assert "st.divider()" in mixer_ws


def test_isolate_reopen_handler_uses_pending_not_direct_widget_write():
    page = Path(__file__).resolve().parents[1] / "ui" / "pages" / "isolate.py"
    source = page.read_text(encoding="utf-8")
    assert "queue_reopen_output_name(st.session_state" in source
    assert "apply_youtube_output_name_sync(st.session_state)" in source
    assert "queue_output_name_if_empty(st.session_state" not in source
    assert 'st.session_state["isolate_output_name"] = title' not in source
    assert 'st.session_state["isolate_output_name"] = path.stem' not in source
    assert "apply_pending_output_name(st.session_state)" in source
    assert "apply_pending_youtube_url(st.session_state)" in source
    assert "reset_new_tab_source(st.session_state)" in source
    assert "job_requires_roformer_backend(choice[\"model\"])" in source
    assert "is_roformer_backend_available()" in source
    assert "guitar_track_radio_ids" in source
    assert "normalize_guitar_track_selection" in source
    assert "queue_youtube_url(st.session_state" in source
    assert '@st.dialog("Search YouTube"' in source
    assert "st.form(" in source
    assert "st.form_submit_button(" in source
    assert "st.video(" in source
    assert "Open on YouTube" in source
    assert "desktop_notify(" in source
    assert "jobs_needing_os_notify" in source
    assert "_increment_upload_key" not in source
    assert "st.popover(" not in source
    assert "search_youtube_videos" in source
    assert "thumbnail_url" in source
    assert "st.image(" in source
    assert "ISOLATE_YOUTUBE_SEARCH_OPEN_KEY" in source
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
    assert 'key="isolate_custom_other"' not in source
    sep_src = source[source.find("def _render_separation_controls") : source.find("def _ffmpeg_install_hint")]
    yt_apply_at = sep_src.find("apply_pending_youtube_url(st.session_state)")
    yt_name_at = sep_src.find("apply_youtube_output_name_sync(st.session_state)")
    yt_input_at = sep_src.find('key="isolate_youtube_url"')
    assert yt_apply_at != -1 and yt_name_at != -1 and yt_input_at != -1
    assert yt_apply_at < yt_name_at < yt_input_at
    assert "queue_output_name_if_empty" not in sep_src
    resolve_src = source[
        source.find("def _resolve_audio_for_job") : source.find("def _enqueue_confirmed_job")
    ]
    assert "apply_now=False" in resolve_src
    assert "choice[\"output_name\"]" in resolve_src or "choice['output_name']" in resolve_src
    assert "queue_output_name_if_empty" not in resolve_src
    enqueue_src = source[
        source.find("def _enqueue_confirmed_job") : source.find("def _library_status_row")
    ]
    enq_at = enqueue_src.find("enqueue_job(spec)")
    reset_at = enqueue_src.find("reset_new_tab_source(st.session_state)")
    assert enq_at != -1 and reset_at != -1 and enq_at < reset_at
    yt_dlg = source[
        source.find("def _youtube_search_dialog") : source.find("def _stateful_expander")
    ]
    form_at = yt_dlg.find("st.form(")
    submit_at = yt_dlg.find("st.form_submit_button(")
    clear_at = yt_dlg.find("isolate_youtube_search_clear")
    video_at = yt_dlg.find("st.video(")
    assert form_at != -1 and submit_at != -1 and form_at < submit_at < clear_at
    assert video_at != -1 and video_at > submit_at
    poll_src = source[
        source.find("def _poll_running_jobs") : source.find("def _queue_tab_fragment")
    ]
    assert "jobs_needing_os_notify" in poll_src
    assert "desktop_notify(" in poll_src
    main_src = source[source.find("def main()") :]
    uid_at = main_src.find("browser_id = _get_browser_user_id()")
    rehydrate_at = main_src.find("_rehydrate_artifacts_from_disk(browser_id)")
    assert uid_at != -1 and rehydrate_at != -1 and uid_at < rehydrate_at
    tabs_at = main_src.find("st.tabs(")
    selected_at = main_src.find("selected = st.session_state.get(WORKSPACE_KEY")
    assert tabs_at != -1 and selected_at != -1 and tabs_at < selected_at
    tab_new_src = main_src[main_src.find("with tab_new:") : main_src.find("with tab_mixer:")]
    assert "_render_new_workspace(demucs_ok)" in tab_new_src
    assert "if show_new" not in tab_new_src
    assert "Could not draw New. Click Refresh." in tab_new_src
    mixer_src = main_src[main_src.find("with tab_mixer:") : main_src.find("with tab_queue:")]
    assert 'if selected == "Mixer"' in mixer_src
    assert "_render_mixer_workspace(" in mixer_src
    queue_src = main_src[main_src.find("with tab_queue:") :]
    assert "_queue_tab_fragment()" in queue_src
    assert "if show_queue" not in queue_src


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


def test_staged_audio_for_new_tab_hides_preview_until_youtube_download(tmp_path):
    leftover = tmp_path / "old.wav"
    leftover.write_bytes(b"x")
    downloaded = tmp_path / "yt.wav"
    downloaded.write_bytes(b"y")
    url = "https://youtu.be/abc"
    assert (
        staged_audio_for_new_tab(
            uploaded=False,
            youtube_url=url,
            pending_path=None,
            pending_fp=None,
            pending_exists=False,
            carry_path=None,
            carry_exists=False,
        )
        is None
    )
    assert (
        staged_audio_for_new_tab(
            uploaded=False,
            youtube_url=url,
            pending_path=str(downloaded),
            pending_fp=f"youtube:{url}",
            pending_exists=True,
            carry_path=None,
            carry_exists=False,
        )
        == str(downloaded)
    )
    assert (
        staged_audio_for_new_tab(
            uploaded=False,
            youtube_url=url,
            pending_path=str(leftover),
            pending_fp="old.wav:1",
            pending_exists=True,
            carry_path=None,
            carry_exists=False,
        )
        is None
    )


def test_staged_audio_for_new_tab_previews_upload_and_carry_over(tmp_path):
    uploaded = tmp_path / "song.wav"
    uploaded.write_bytes(b"x")
    carry = tmp_path / "from_tab.wav"
    carry.write_bytes(b"z")
    assert (
        staged_audio_for_new_tab(
            uploaded=True,
            youtube_url="",
            pending_path=str(uploaded),
            pending_fp="song.wav:1",
            pending_exists=True,
            carry_path=None,
            carry_exists=False,
        )
        == str(uploaded)
    )
    assert (
        staged_audio_for_new_tab(
            uploaded=False,
            youtube_url="",
            pending_path=None,
            pending_fp=None,
            pending_exists=False,
            carry_path=str(carry),
            carry_exists=True,
        )
        == str(carry)
    )


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


def test_isolate_ui_state_payload_includes_export_dir():
    payload = isolate_ui_state_payload(
        {
            WORKSPACE_KEY: "Mixer",
            "isolate_export_dir": "/Users/me/Downloads",
        }
    )
    assert payload["export_dir"] == "/Users/me/Downloads"


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


def test_os_notify_seeds_historical_jobs_and_fires_for_new_terminal():
    jobs = [
        {"id": "old-ok", "status": "succeeded", "title": "A"},
        {"id": "old-fail", "status": "failed", "title": "B"},
        {"id": "run", "status": "running", "title": "C"},
        {"id": "wait", "status": "queued", "title": "D"},
    ]
    assert seed_notified_job_ids(jobs) == ["old-ok", "old-fail"]
    ids, pending = jobs_needing_os_notify(jobs, None)
    assert pending == []
    assert ids == ["old-ok", "old-fail"]
    later = jobs + [{"id": "new-ok", "status": "succeeded", "title": "Hangar 18"}]
    ids, pending = jobs_needing_os_notify(later, ids)
    assert [row["id"] for row in pending] == ["new-ok"]
    later = later + [{"id": "new-fail", "status": "failed", "title": "Nope"}]
    ids, pending = jobs_needing_os_notify(later, ids)
    assert [row["id"] for row in pending] == ["new-fail"]
    later = later + [{"id": "gone", "status": "cancelled", "title": "Z"}]
    ids, pending = jobs_needing_os_notify(later, ids)
    assert pending == []


def test_os_notify_message_copy():
    assert os_notify_message({"status": "succeeded", "title": "Hangar 18"}) == (
        "Audio Isolation",
        "Separated: Hangar 18",
    )
    assert os_notify_message({"status": "failed", "title": "Nope"}) == (
        "Audio Isolation",
        "Needs attention: Nope failed",
    )
    assert os_notify_message({"status": "queued", "title": "Soon"}) is None
    assert os_notify_message({"status": "running", "title": "Soon"}) is None


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
    assert view["hint"] == "Separating tracks — this can take a while on CPU"
    assert "Check guitar" not in view["checklist_md"]
    assert "Check which tracks have sound" not in view["checklist_md"]


def test_user_progress_hint_never_echoes_raw_worker_text():
    assert user_progress_hint("ingest", "libtorchcodec exploded") is None
    assert "libtorchcodec" not in (user_progress_hint("separate", "libtorchcodec exploded") or "")
    assert "NVIDIA GPU" in (user_progress_hint("separate", "Separating tracks — this can take a while on NVIDIA GPU") or "")


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
    assert resolved["model"] == "bs_roformer_sw"
    assert resolved["guitar_refine"] is False
    assert resolved["two_stems"] is None
    assert resolved["track_count"] == 4
    assert "Guitar" in resolved["tracks"]
    assert "Piano" not in resolved["tracks"]
    assert "Other" not in resolved["tracks"]
    assert resolved["emit_stems"] == ("vocals", "drums", "bass", "guitar")
    assert resolved["fold_other_into_guitar"] is True


def test_resolve_separation_preset_best_guitar_uses_refine():
    legacy = resolve_separation_preset("best_guitar")
    current = resolve_separation_preset("full_band")
    assert legacy["model"] == "bs_roformer_sw"
    assert legacy["guitar_refine"] is True
    assert current["guitar_refine"] is False
    assert legacy["emit_stems"] == current["emit_stems"]
    assert legacy["id"] == "custom"


def test_resolve_separation_preset_essential():
    resolved = resolve_separation_preset("essential")
    assert resolved["model"] == "htdemucs"
    assert resolved["two_stems"] is None
    assert resolved["track_count"] == 4
    assert resolved["emit_stems"] == ("vocals", "drums", "bass", "other")


def test_resolve_separation_preset_vocals_music():
    resolved = resolve_separation_preset("vocals_music")
    assert resolved["model"] == "htdemucs"
    assert resolved["two_stems"] == "vocals"
    assert resolved["track_count"] == 1
    assert "instrumental" in resolved["tracks"].lower()


def test_resolve_separation_preset_unknown_falls_back():
    resolved = resolve_separation_preset("not_a_real_preset")
    assert resolved["id"] == "custom"
    assert resolved["model"] == "htdemucs_6s"
    assert resolved["track_options"] == list(DEFAULT_TRACK_OPTIONS)


def test_resolve_track_selection_default_demucs_guitar():
    resolved = resolve_track_selection(DEFAULT_TRACK_OPTIONS)
    assert resolved["model"] == "htdemucs_6s"
    assert resolved["guitar_refine"] is False
    assert resolved["emit_stems"] == ("vocals", "guitar")
    assert resolved["caveat"] == ""


def test_resolve_track_selection_roformer_guitar_refine():
    resolved = resolve_track_selection(
        ["vocals_demucs", "drums_demucs", "guitar_roformer_refine"]
    )
    assert resolved["model"] == "bs_roformer_sw"
    assert resolved["guitar_refine"] is True
    assert resolved["caveat"]
    assert "BS-RoFormer" in resolved["caveat"]


def test_resolve_track_selection_roformer_with_demucs_stems_notes_mixed_pass():
    resolved = resolve_track_selection(["vocals_demucs", "guitar_roformer"])
    assert resolved["model"] == "bs_roformer_sw"
    assert "one BS-RoFormer pass" in resolved["caveat"]


def test_resolve_track_selection_rejects_two_guitar_options():
    with pytest.raises(ValueError, match="one guitar"):
        resolve_track_selection(["guitar_demucs_6s", "guitar_roformer"])


def test_guitar_track_radio_ids_without_roformer():
    assert guitar_track_radio_ids(roformer_available=False) == ("none", "guitar_demucs_6s")
    assert guitar_track_radio_ids(roformer_available=True) == (
        "none",
        "guitar_demucs_6s",
        "guitar_roformer",
        "guitar_roformer_refine",
    )


def test_normalize_guitar_track_selection_downgrades_roformer_when_unavailable():
    assert (
        normalize_guitar_track_selection("guitar_roformer_refine", roformer_available=False)
        == "guitar_demucs_6s"
    )
    assert normalize_guitar_track_selection("guitar_roformer", roformer_available=True) == "guitar_roformer"
    assert normalize_guitar_track_selection("none", roformer_available=False) == "none"


def test_tracks_picker_help_mentions_install_when_roformer_missing():
    missing = tracks_picker_help(roformer_available=False)
    assert "bs-roformer-infer" in missing
    assert tracks_picker_help(roformer_available=True) != missing


def test_default_guitar_track_option_promotes_roformer_when_available():
    assert default_guitar_track_option(roformer_available=True) == "guitar_roformer"
    assert default_guitar_track_option(roformer_available=False) == "guitar_demucs_6s"


def test_promote_default_guitar_option_swaps_only_fresh_defaults():
    base = ["vocals_demucs", "guitar_demucs_6s"]
    assert promote_default_guitar_option(
        base, roformer_available=True
    ) == ["vocals_demucs", "guitar_roformer"]
    assert promote_default_guitar_option(
        base, roformer_available=False
    ) == ["vocals_demucs", "guitar_demucs_6s"]
    kept = ["guitar_demucs_6s"]
    assert promote_default_guitar_option(kept, roformer_available=False) == [
        "guitar_demucs_6s"
    ]
    explicit = ["guitar_roformer_refine"]
    assert promote_default_guitar_option(
        explicit, roformer_available=True
    ) == ["guitar_roformer_refine"]


def test_job_requires_roformer_backend():
    assert job_requires_roformer_backend("bs_roformer_sw") is True
    assert job_requires_roformer_backend("melband_roformer_guitar") is True
    assert job_requires_roformer_backend("htdemucs_6s") is False


def test_resolve_track_selection_vocals_instrumental_exclusive():
    resolved = resolve_track_selection(["vocals_instrumental_demucs"])
    assert resolved["model"] == "htdemucs"
    assert resolved["two_stems"] == "vocals"
    with pytest.raises(ValueError, match="cannot combine"):
        resolve_track_selection(["vocals_instrumental_demucs", "drums_demucs"])


def test_resolve_custom_separation_vocals_only_uses_four_stem_demucs():
    resolved = resolve_custom_separation(["vocals"])
    assert resolved["model"] == "htdemucs"
    assert resolved["two_stems"] is None
    assert resolved["stems"] == ["vocals"]


def test_resolve_custom_separation_piano_and_vocals_needs_six_stem_model():
    resolved = resolve_custom_separation(["piano", "vocals"])
    assert resolved["model"] == "htdemucs_6s"
    assert resolved["two_stems"] is None
    assert resolved["stems"] == ["vocals", "piano"]
    assert "Vocals (Demucs)" in resolved["tracks"]
    assert "Piano (Demucs 6-stem)" in resolved["tracks"]


def test_resolve_custom_separation_guitar_needs_six_stem_model():
    resolved = resolve_custom_separation(["guitar"])
    assert resolved["model"] == "htdemucs_6s"
    assert resolved["two_stems"] is None
    assert resolved["emit_stems"] == ("guitar",)
    assert resolved["fold_other_into_guitar"] is True


def test_resolve_custom_separation_guitar_and_other_keeps_other():
    resolved = resolve_custom_separation(["guitar", "other"])
    assert resolved["model"] == "htdemucs_6s"
    assert resolved["emit_stems"] == ("guitar", "other")
    assert resolved["fold_other_into_guitar"] is False


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


def test_custom_stem_choices_include_other():
    assert "other" in CUSTOM_STEM_CHOICES
    assert "guitar" in CUSTOM_STEM_CHOICES
    assert "piano" in CUSTOM_STEM_CHOICES


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


def test_resolve_speed_preset_unknown_and_auto_become_balanced():
    from audio_to_tab.hardware import HostProbe

    probe = HostProbe(cuda=False, mps=False, ram_gb=16.0)
    six = resolve_speed_preset("auto", probe, platform="darwin", model="htdemucs_6s")
    four = resolve_speed_preset("auto", probe, platform="darwin", model="htdemucs")
    faster = resolve_speed_preset("faster", probe, platform="darwin", model="htdemucs_6s")
    assert six["id"] == "balanced"
    assert six["quality"] == "balanced"
    assert four["id"] == "balanced"
    assert four["quality"] == "balanced"
    assert faster["quality"] == "fast"


def test_estimate_job_seconds_two_pass_is_double_separate():
    stages = isolation_stages_for_job(expects_guitar=True)
    one, _ = estimate_job_seconds(
        audio_duration_sec=60.0,
        quality="fast",
        device="cpu",
        stages=stages,
    )
    two, _ = estimate_job_seconds(
        audio_duration_sec=60.0,
        quality="fast",
        device="cpu",
        stages=stages,
        two_pass=True,
    )
    assert one is not None and two is not None
    assert two == pytest.approx(one * 2.0)


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


def test_default_speed_preset_is_balanced():
    assert DEFAULT_SPEED_PRESET == "balanced"
    assert "auto" not in SPEED_PRESETS
    assert "balanced" in SPEED_PRESETS


def test_resolve_speed_preset_balanced_uses_cuda_probe_on_windows():
    from audio_to_tab.hardware import HostProbe

    probe = HostProbe(cuda=True, mps=False, ram_gb=24.0)
    resolved = resolve_speed_preset("balanced", probe, platform="win32")
    assert resolved["id"] == "balanced"
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


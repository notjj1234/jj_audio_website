"""Tests for ui.isolate_state helpers."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import soundfile as sf

from ui.isolate_state import (
    CUSTOM_STEM_CHOICES,
    CUSTOM_STEM_TILE_ORDER,
    DEFAULT_OUTCOME_CARD,
    DEFAULT_UI_MODE,
    FAILED_JOB_STRIP_TTL_SEC,
    MIXER_COMPONENT_KEY_PREFIX,
    OUTCOME_CARDS,
    OUTCOME_CARD_ORDER,
    dismiss_failed_job,
    outcome_card_for_options,
    custom_stems_from_options,
    outcome_icon_markdown,
    stem_icon_markdown,
    toggle_custom_stem_options,
    resolve_outcome_card,
    DEFAULT_LITE_GUITAR_ENGINE,
    LITE_GUITAR_ENGINE_LABELS,
    LITE_GUITAR_ENGINE_ORDER,
    apply_lite_guitar_engine,
    effective_clip_seconds,
    lite_guitar_engine_allowed,
    lite_guitar_engine_disabled_reason,
    lite_roformer_enqueue_block_reason,
    resolve_lite_guitar_engine,
    should_show_failed_job,
    UI_MODE_KEY,
    UI_MODES,
    apply_persisted_settings,
    is_pro_mode,
    load_ui_mode,
    persisted_settings_payload,
    resolve_ui_mode,
    roformer_speed_note,
    write_ui_mode,
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
    ISOLATE_YOUTUBE_TITLE_PENDING_KEY,
    SPEED_PRESETS,
    apply_listen_picker_pending,
    apply_pending_output_name,
    apply_pending_youtube_url,
    apply_stored_isolate_ui_state,
    apply_workspace_tab,
    apply_youtube_output_name_sync,
    checklist_items,
    LITE_MAX_DURATION_SEC,
    clamp_lite_clip,
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
    isolate_poll_requires_full_rerun,
    isolate_ui_state_payload,
    listen_picker_default,
    load_persist_isolate_user_id,
    mixer_component_key,
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
    request_isolate_scroll_top,
    consume_isolate_scroll_top,
    consume_mix_tab_event,
    isolate_scroll_top_token,
    should_request_isolate_scroll_top,
    ISOLATE_SCROLL_TOP_KEY,
    reset_new_tab_source,
    adopt_audio_into_run,
    discard_youtube_staging,
    is_youtube_staging_path,
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
    children_from_outputs,
    merge_reseparate,
    stem_label_for_id,
)


@pytest.fixture(autouse=True)
def _cpu_edition_by_default(monkeypatch):
    monkeypatch.delenv("AUDIO_TOOLS_EDITION", raising=False)


def test_failed_job_leaves_the_strip_once_dismissed():
    job = {"id": "job-1", "status": "failed", "updated_at": 1_000.0}
    assert should_show_failed_job(job, now=1_010.0) is True
    session: dict = {}
    dismiss_failed_job(session, "job-1")
    assert (
        should_show_failed_job(
            job, now=1_010.0, dismissed_ids=session["isolate_dismissed_job_ids"]
        )
        is False
    )


def test_failed_job_stops_owning_the_strip_after_its_ttl():
    job = {"id": "job-1", "status": "failed", "updated_at": 1_000.0}
    assert should_show_failed_job(job, now=1_000.0 + FAILED_JOB_STRIP_TTL_SEC - 1) is True
    assert should_show_failed_job(job, now=1_000.0 + FAILED_JOB_STRIP_TTL_SEC + 1) is False


def test_failed_job_without_a_timestamp_still_shows():
    """Missing metadata must not hide a real failure."""
    assert should_show_failed_job({"id": "j", "status": "failed"}, now=5.0) is True
    assert should_show_failed_job({"id": "j", "updated_at": "junk"}, now=5.0) is True
    assert should_show_failed_job(None, now=5.0) is False
    assert should_show_failed_job({"status": "failed"}, now=5.0) is False


def test_dismissing_twice_does_not_duplicate_the_id():
    session: dict = {}
    dismiss_failed_job(session, "job-1")
    dismiss_failed_job(session, "job-1")
    assert session["isolate_dismissed_job_ids"] == ["job-1"]


def test_lite_outcomes_use_the_best_engine_available():
    """Lite is presentation only — it must not quietly pick a weaker model."""
    with_ro = resolve_outcome_card("guitar", roformer_available=True)
    without_ro = resolve_outcome_card("guitar", roformer_available=False)
    assert with_ro == ["guitar_roformer"]
    assert without_ro == ["guitar_demucs_6s"]

    band = resolve_outcome_card("band", roformer_available=True)
    assert "guitar_roformer" in band
    assert {"vocals_demucs", "drums_demucs", "bass_demucs"} <= set(band)


def test_lite_outcomes_all_resolve_to_a_runnable_pipeline():
    for card in OUTCOME_CARD_ORDER:
        for roformer in (True, False):
            options = resolve_outcome_card(card, roformer_available=roformer)
            assert options, card
            resolved = resolve_track_selection(options)
            assert resolved["model"]
            assert resolved["emit_stems"]


def test_unknown_outcome_falls_back_to_the_default():
    assert resolve_outcome_card("nonsense", roformer_available=True) == resolve_outcome_card(
        DEFAULT_OUTCOME_CARD, roformer_available=True
    )


def test_outcome_card_round_trips_so_switching_modes_keeps_the_selection():
    for card in OUTCOME_CARD_ORDER:
        options = resolve_outcome_card(card, roformer_available=True)
        assert outcome_card_for_options(options, roformer_available=True) == card


def test_a_pro_only_selection_is_reported_as_custom_not_silently_replaced():
    # Piano has no Lite outcome; Lite must recognise it cannot describe this.
    custom = ["vocals_demucs", "piano_demucs"]
    assert outcome_card_for_options(custom, roformer_available=True) is None
    assert outcome_card_for_options([], roformer_available=True) is None


def test_outcome_cards_carry_stem_list_and_track_count():
    expected = {
        "band": ("Vocals · Drums · Bass · Guitar", 4),
        "karaoke": ("Vocals · Instrumental", 2),
        "guitar": ("Guitar", 1),
        "vocals": ("Vocals", 1),
    }
    assert set(OUTCOME_CARDS) == set(OUTCOME_CARD_ORDER)
    for card_id, (stems, n_tracks) in expected.items():
        assert OUTCOME_CARDS[card_id]["stems_line"] == stems
        assert OUTCOME_CARDS[card_id]["n_tracks"] == n_tracks
        assert OUTCOME_CARDS[card_id]["label"]
        assert OUTCOME_CARDS[card_id]["help"]


def test_toggle_custom_stem_exits_karaoke_and_uses_best_guitar():
    karaoke = resolve_outcome_card("karaoke", roformer_available=True)
    added = toggle_custom_stem_options(karaoke, "drums", roformer_available=True)
    assert added == ["drums_demucs"]
    assert custom_stems_from_options(karaoke) == []

    band = resolve_outcome_card("band", roformer_available=True)
    with_piano = toggle_custom_stem_options(band, "piano", roformer_available=True)
    assert "piano_demucs" in with_piano
    assert outcome_card_for_options(with_piano, roformer_available=True) is None

    no_guitar = toggle_custom_stem_options(band, "guitar", roformer_available=True)
    assert custom_stems_from_options(no_guitar) == ["vocals", "bass", "drums"]
    again = toggle_custom_stem_options([], "guitar", roformer_available=True)
    assert again == ["guitar_roformer"]
    demucs = toggle_custom_stem_options([], "guitar", roformer_available=False)
    assert demucs == ["guitar_demucs_6s"]


def test_effective_clip_seconds_prefers_section_then_file():
    assert effective_clip_seconds(
        file_duration_sec=280.0, start_sec=10.0, max_duration_sec=90.0
    ) == 90.0
    assert effective_clip_seconds(
        file_duration_sec=280.0, start_sec=10.0, max_duration_sec=None
    ) == 270.0
    assert (
        effective_clip_seconds(
            file_duration_sec=None, start_sec=0.0, max_duration_sec=None
        )
        is None
    )


def _allow_kwargs(**overrides):
    base = dict(
        effective_sec=120.0,
        cap_sec=180.0,
        duration_known=True,
        roformer_available=True,
    )
    base.update(overrides)
    return base


def test_lite_guitar_engine_demucs_always_allowed():
    for kwargs in (
        _allow_kwargs(),
        _allow_kwargs(effective_sec=280.0, cap_sec=180.0),
        _allow_kwargs(effective_sec=None, duration_known=False),
        _allow_kwargs(roformer_available=False),
    ):
        assert lite_guitar_engine_allowed(DEFAULT_LITE_GUITAR_ENGINE, **kwargs) is True
        assert lite_guitar_engine_allowed("guitar_demucs_6s", **kwargs) is True
        assert lite_guitar_engine_disabled_reason("guitar_demucs_6s", **kwargs) is None


def test_lite_guitar_engine_roformer_disabled_until_length_known_or_over_cap():
    unknown = _allow_kwargs(effective_sec=None, duration_known=False)
    assert lite_guitar_engine_allowed("guitar_roformer", **unknown) is False
    assert lite_guitar_engine_allowed("guitar_roformer_refine", **unknown) is False
    reason = lite_guitar_engine_disabled_reason("guitar_roformer", **unknown)
    assert reason is not None
    assert "length is known" in reason

    over = _allow_kwargs(effective_sec=277.0, cap_sec=180.0)
    assert lite_guitar_engine_allowed("guitar_roformer", **over) is False
    assert lite_guitar_engine_allowed("guitar_roformer_refine", **over) is False
    over_reason = lite_guitar_engine_disabled_reason("guitar_roformer", **over)
    assert over_reason is not None
    assert "180" in over_reason
    assert "277" in over_reason

    short = _allow_kwargs(effective_sec=90.0, cap_sec=180.0)
    assert lite_guitar_engine_allowed("guitar_roformer", **short) is True
    assert lite_guitar_engine_allowed("guitar_roformer_refine", **short) is True
    assert lite_guitar_engine_disabled_reason("guitar_roformer", **short) is None

    at_cap = _allow_kwargs(effective_sec=180.0, cap_sec=180.0)
    assert lite_guitar_engine_allowed("guitar_roformer", **at_cap) is True

    missing = _allow_kwargs(roformer_available=False, effective_sec=90.0)
    assert lite_guitar_engine_allowed("guitar_roformer", **missing) is False
    missing_reason = lite_guitar_engine_disabled_reason("guitar_roformer", **missing)
    assert missing_reason is not None
    assert "BS-RoFormer" in missing_reason


def test_lite_guitar_engine_falls_back_to_demucs_when_illegal():
    over = _allow_kwargs(effective_sec=282.0, cap_sec=180.0)
    engine, fell_back = resolve_lite_guitar_engine("guitar_roformer", **over)
    assert engine == DEFAULT_LITE_GUITAR_ENGINE
    assert fell_back is True

    refine, refine_fell = resolve_lite_guitar_engine("guitar_roformer_refine", **over)
    assert refine == DEFAULT_LITE_GUITAR_ENGINE
    assert refine_fell is True

    unknown = _allow_kwargs(effective_sec=None, duration_known=False)
    engine, fell_back = resolve_lite_guitar_engine("guitar_roformer", **unknown)
    assert engine == DEFAULT_LITE_GUITAR_ENGINE
    assert fell_back is True

    short = _allow_kwargs(effective_sec=90.0, cap_sec=180.0)
    engine, fell_back = resolve_lite_guitar_engine("guitar_roformer_refine", **short)
    assert engine == "guitar_roformer_refine"
    assert fell_back is False

    engine, fell_back = resolve_lite_guitar_engine("not-an-engine", **short)
    assert engine == DEFAULT_LITE_GUITAR_ENGINE
    assert fell_back is False

    engine, fell_back = resolve_lite_guitar_engine(None, **over)
    assert engine == DEFAULT_LITE_GUITAR_ENGINE
    assert fell_back is False


def test_apply_lite_guitar_engine_swaps_guitar_and_leaves_karaoke():
    band = ["vocals_demucs", "drums_demucs", "bass_demucs", "guitar_demucs_6s"]
    assert apply_lite_guitar_engine(band, "guitar_roformer") == [
        "vocals_demucs",
        "drums_demucs",
        "bass_demucs",
        "guitar_roformer",
    ]
    assert apply_lite_guitar_engine(["vocals_instrumental_demucs"], "guitar_roformer") == [
        "vocals_instrumental_demucs"
    ]
    assert apply_lite_guitar_engine(["guitar_roformer"], "guitar_demucs_6s") == [
        "guitar_demucs_6s"
    ]


def test_lite_outcomes_honor_explicit_guitar_engine():
    assert LITE_GUITAR_ENGINE_ORDER == (
        "guitar_demucs_6s",
        "guitar_roformer",
        "guitar_roformer_refine",
    )
    assert LITE_GUITAR_ENGINE_LABELS["guitar_demucs_6s"] == "Faster (Demucs)"
    assert LITE_GUITAR_ENGINE_LABELS["guitar_roformer"] == "Better guitar (BS-RoFormer)"
    assert (
        LITE_GUITAR_ENGINE_LABELS["guitar_roformer_refine"]
        == "Best / slower (BS-RoFormer + MelBand)"
    )
    guitar = resolve_outcome_card(
        "guitar",
        roformer_available=True,
        guitar_option="guitar_demucs_6s",
    )
    assert guitar == ["guitar_demucs_6s"]
    band = resolve_outcome_card(
        "band",
        roformer_available=True,
        guitar_option="guitar_roformer_refine",
    )
    assert "guitar_roformer_refine" in band
    assert outcome_card_for_options(
        band,
        roformer_available=True,
        guitar_option="guitar_roformer_refine",
    ) == "band"
    added = toggle_custom_stem_options(
        [],
        "guitar",
        roformer_available=True,
        guitar_option="guitar_roformer_refine",
    )
    assert added == ["guitar_roformer_refine"]


def test_lite_roformer_enqueue_is_blocked_when_over_cap_or_unknown():
    over = _allow_kwargs(effective_sec=277.0, cap_sec=180.0)
    reason = lite_roformer_enqueue_block_reason("bs_roformer_sw", **over)
    assert reason is not None
    assert "180" in reason
    assert "277" in reason
    assert lite_roformer_enqueue_block_reason("htdemucs_6s", **over) is None
    assert lite_roformer_enqueue_block_reason("htdemucs", **over) is None

    short = _allow_kwargs(effective_sec=90.0, cap_sec=180.0)
    assert lite_roformer_enqueue_block_reason("bs_roformer_sw", **short) is None
    assert lite_roformer_enqueue_block_reason("melband_roformer_guitar", **short) is None

    unknown = _allow_kwargs(effective_sec=None, duration_known=False)
    unknown_reason = lite_roformer_enqueue_block_reason("bs_roformer_sw", **unknown)
    assert unknown_reason is not None
    assert "length is known" in unknown_reason


def test_custom_stem_tile_order_is_this_apps_stems_not_moises_extras():
    assert set(CUSTOM_STEM_TILE_ORDER) == set(CUSTOM_STEM_CHOICES)
    assert CUSTOM_STEM_TILE_ORDER == (
        "vocals",
        "guitar",
        "bass",
        "drums",
        "piano",
        "other",
    )
    for banned in ("keys", "wind", "strings", "multimedia", "dialogue"):
        assert banned not in CUSTOM_STEM_CHOICES


def test_lite_outcome_picker_uses_card_keys_not_pro_track_picker():
    page = Path(__file__).resolve().parents[1] / "ui" / "pages" / "isolate.py"
    source = page.read_text(encoding="utf-8")
    tile = source[
        source.find("def _render_outcome_tile") : source.find("def _render_stem_tile")
    ]
    picker = source[
        source.find("def _render_outcome_picker") : source.find("def _render_engine_panel")
    ]
    grid = source[
        source.find("def _render_custom_stem_grid") : source.find("def _render_outcome_picker")
    ]
    track = source[
        source.find("def _render_track_picker") : source.find("def _outcome_tile_label")
    ]
    controls = source[
        source.find("def _render_separation_controls") : source.find("def _ffmpeg_install_hint")
    ]
    assert "OUTCOME_CARD_KEY" in picker
    assert 'key=f"isolate_outcome_pick_{card_id}"' in tile
    for card_id in ("band", "karaoke"):
        assert f'"{card_id}"' in picker
    assert "**One track**" not in picker
    assert '"guitar"' not in picker.split("_render_custom_stem_grid")[0]
    assert '"vocals"' not in picker.split("_render_custom_stem_grid")[0]
    assert "CUSTOM_STEM_TILE_ORDER" in grid
    assert 'key=f"isolate_stem_pick_{stem_id}"' in source
    assert "icon=STEM_TILE_EMOJI" not in source
    assert "icon=OUTCOME_TILE_EMOJI" not in source
    assert "icon=" not in tile
    assert "stem_icon_markdown(stem_id, selected=selected)" in source
    assert "outcome_icon_markdown(card_id, selected=selected)" in source
    label_fn = source[
        source.find("def _outcome_tile_label") : source.find("def _render_outcome_tile")
    ]
    assert r"\u00a0track" in label_fn
    assert "stems_line']} · {tracks}" in label_fn
    assert "flex-direction: column" in (
        Path(__file__).resolve().parents[1] / "ui" / "app.py"
    ).read_text(encoding="utf-8")
    assert "_render_custom_stem_grid" in picker
    assert "_render_track_picker(persist=persist)" in picker
    assert "st.checkbox" not in track
    assert 'key="isolate_guitar_track"' in track
    assert "resolve_outcome_card(" in tile
    branch = controls[controls.find("pro = is_pro_mode") : controls.find("custom_stems =")]
    assert "_render_section_and_outcomes(" in branch
    assert "prefer_roformer=prefer_roformer" in branch
    assert "get_desktop_probe()" in controls
    assert "lite_auto_speed_id(probe)" in controls
    assert "lite_detected_caption(probe)" in picker
    assert "lite_using_caption(" in picker
    assert 'key="isolate_lite_run_on"' in picker
    assert "lite_device_choice_ids(probe)" in picker
    assert "_render_machine_panel(" in picker
    assert "_render_machine_panel(" not in controls
    assert controls.count("_render_machine_panel(") == 0
    assert source.count("_render_machine_panel(") == 2  # def + one Pro call site
    assert "get_desktop_probe_without_torch" not in controls
    assert "_render_track_picker(persist=persist)" not in branch
    for banned in ("keys", "wind", "strings", "multimedia"):
        assert f"isolate_stem_pick_{banned}" not in source


def test_pro_machine_panel_is_inside_outcome_fragment_only():
    """Device expander must not sit after the fragment — that duplicated it."""
    page = Path(__file__).resolve().parents[1] / "ui" / "pages" / "isolate.py"
    source = page.read_text(encoding="utf-8")
    picker = source[
        source.find("def _render_outcome_picker") : source.find("def _render_engine_panel")
    ]
    machine = source[
        source.find("def _render_machine_panel") : source.find("def _speed_preset_radio_label")
    ]
    assert "_render_machine_panel(" in picker
    assert "_render_engine_panel(" in picker
    assert picker.find("_render_engine_panel(") < picker.find("_render_machine_panel(")
    assert "_isolate_machine_panel_drawn" in machine
    assert 'key="isolate_machine_expanded"' in machine


def test_persisted_settings_include_lite_run_on():
    from ui.isolate_state import PERSISTED_SETTING_KEYS

    assert "isolate_lite_run_on" in PERSISTED_SETTING_KEYS
    assert "isolate_lite_guitar_engine" in PERSISTED_SETTING_KEYS
    assert "isolate_device" in PERSISTED_SETTING_KEYS
    assert "isolate_demucs_shifts" in PERSISTED_SETTING_KEYS
    assert "isolate_fold_other_mode" in PERSISTED_SETTING_KEYS
    assert "isolate_guitar_ensemble" in PERSISTED_SETTING_KEYS
    assert "isolate_bass_bleed_mitigation" in PERSISTED_SETTING_KEYS
    assert "isolate_htdemucs_ft" in PERSISTED_SETTING_KEYS


def _lite_engine_kwargs(**overrides):
    base = dict(
        is_pro=False,
        model="htdemucs_6s",
        quality="fast",
        two_stems=None,
        two_pass=False,
        fold_other_into_guitar=True,
        fold_other_mode="best_effort",
        roformer_available=True,
    )
    base.update(overrides)
    return base


def test_lite_engine_job_fields_ignore_pro_session_and_keep_defaults():
    from ui.isolate_state import resolve_pro_engine_job_fields

    session = {
        "isolate_demucs_shifts": "5",
        "isolate_demucs_overlap": "0.75",
        "isolate_demucs_segment": 0,
        "isolate_demucs_jobs": 4,
        "isolate_sub_bass_debleed": True,
        "isolate_bleed_gate": True,
        "isolate_bass_bleed_mitigation": True,
        "isolate_adaptive_fold_gain": True,
        "isolate_guitar_ensemble": True,
        "isolate_low_end_restore_db": 6.0,
        "isolate_fold_other_mode": "full",
        "isolate_htdemucs_ft": True,
    }
    fields = resolve_pro_engine_job_fields(session, **_lite_engine_kwargs())
    assert fields["demucs_shifts"] is None
    assert fields["demucs_overlap"] is None
    assert fields["demucs_segment"] == 8
    assert fields["demucs_jobs"] == 1
    assert fields["fold_other_mode"] == "best_effort"
    assert fields["adaptive_fold_gain"] is False
    assert fields["bleed_gate"] is False
    assert fields["bass_bleed_mitigation"] is False
    assert fields["sub_bass_debleed"] is False
    assert fields["low_end_restore_db"] == 0.0
    assert fields["guitar_ensemble"] is False
    assert fields["model"] == "htdemucs_6s"


def test_pro_engine_job_fields_map_compute_and_guitar_post():
    from ui.isolate_state import resolve_pro_engine_job_fields

    session = {
        "isolate_demucs_shifts": "5",
        "isolate_demucs_overlap": "0.75",
        "isolate_demucs_segment": 0,
        "isolate_demucs_jobs": 2,
        "isolate_fold_other_mode": "band_limited",
        "isolate_adaptive_fold_gain": True,
        "isolate_bleed_gate": True,
        "isolate_bass_bleed_mitigation": True,
        "isolate_sub_bass_debleed": True,
        "isolate_low_end_restore_db": 4.0,
        "isolate_guitar_ensemble": True,
    }
    fields = resolve_pro_engine_job_fields(
        session, **_lite_engine_kwargs(is_pro=True, quality="fast")
    )
    assert fields["demucs_shifts"] == 5
    assert fields["demucs_overlap"] == pytest.approx(0.75)
    assert fields["demucs_segment"] is None
    assert fields["demucs_jobs"] == 2
    assert fields["fold_other_mode"] == "band_limited"
    assert fields["adaptive_fold_gain"] is True
    assert fields["bleed_gate"] is True
    assert fields["bass_bleed_mitigation"] is True
    assert fields["sub_bass_debleed"] is True
    assert fields["low_end_restore_db"] == 4.0
    assert fields["guitar_ensemble"] is True


def test_pro_engine_matching_quality_map_does_not_send_shift_overrides():
    from ui.isolate_state import resolve_pro_engine_job_fields

    session = {"isolate_demucs_shifts": "0", "isolate_demucs_overlap": "0.25"}
    fields = resolve_pro_engine_job_fields(
        session, **_lite_engine_kwargs(is_pro=True, quality="fast")
    )
    assert fields["demucs_shifts"] is None
    assert fields["demucs_overlap"] is None


def test_sync_demucs_compute_defaults_resets_unless_overridden():
    from ui.isolate_state import sync_demucs_compute_defaults

    session: dict = {"isolate_demucs_shifts": "0", "isolate_demucs_overlap": "0.25"}
    sync_demucs_compute_defaults(session, quality="fast")
    assert session["isolate_demucs_shifts"] == "0"
    sync_demucs_compute_defaults(session, quality="extreme")
    assert session["isolate_demucs_shifts"] == "5"
    assert session["isolate_demucs_overlap"] == "0.75"

    session["isolate_demucs_shifts"] = "1"
    sync_demucs_compute_defaults(session, quality="fast")
    assert session["isolate_demucs_shifts"] == "1"
    assert session["isolate_demucs_overlap"] == "0.25"


def test_pro_htdemucs_ft_only_for_four_stem_and_ensemble_guards():
    from ui.isolate_state import resolve_pro_engine_job_fields

    session = {"isolate_htdemucs_ft": True, "isolate_guitar_ensemble": True}
    four = resolve_pro_engine_job_fields(
        session, **_lite_engine_kwargs(is_pro=True, model="htdemucs")
    )
    assert four["model"] == "htdemucs_ft"
    assert four["guitar_ensemble"] is True

    six = resolve_pro_engine_job_fields(
        session, **_lite_engine_kwargs(is_pro=True, model="htdemucs_6s")
    )
    assert six["model"] == "htdemucs_6s"

    blocked = resolve_pro_engine_job_fields(
        session,
        **_lite_engine_kwargs(is_pro=True, model="htdemucs_6s", two_pass=True),
    )
    assert blocked["guitar_ensemble"] is False

    no_ro = resolve_pro_engine_job_fields(
        session,
        **_lite_engine_kwargs(is_pro=True, model="htdemucs_6s", roformer_available=False),
    )
    assert no_ro["guitar_ensemble"] is False


def test_fold_mode_ignored_when_custom_keeps_other():
    from ui.isolate_state import resolve_pro_engine_job_fields

    session = {"isolate_fold_other_mode": "full", "isolate_adaptive_fold_gain": True}
    fields = resolve_pro_engine_job_fields(
        session,
        **_lite_engine_kwargs(
            is_pro=True, fold_other_into_guitar=False, fold_other_mode="best_effort"
        ),
    )
    assert fields["fold_other_mode"] == "best_effort"
    assert fields["adaptive_fold_gain"] is False


def test_isolate_job_spec_carries_pro_engine_fields_into_config_kwargs():
    from ui.isolate_jobs import IsolateJobSpec, isolate_config_kwargs_from_spec

    default = IsolateJobSpec(
        id="j", audio_path="a.wav", output_dir="out", title="t"
    )
    kwargs = isolate_config_kwargs_from_spec(default)
    assert kwargs["demucs_shifts"] is None
    assert kwargs["demucs_overlap"] is None
    assert kwargs["demucs_segment"] == 8
    assert kwargs["demucs_jobs"] == 1
    assert kwargs["bleed_gate"] is False
    assert kwargs["bass_bleed_mitigation"] is False
    assert kwargs["guitar_ensemble"] is False
    assert kwargs["lead_rhythm"] is False

    spec = IsolateJobSpec(
        id="j2",
        audio_path="a.wav",
        output_dir="out",
        title="t",
        demucs_shifts=5,
        demucs_overlap=0.75,
        demucs_segment=None,
        demucs_jobs=2,
        bleed_gate=True,
        bass_bleed_mitigation=True,
        adaptive_fold_gain=True,
        guitar_ensemble=True,
        fold_other_mode="band_limited",
        low_end_restore_db=3.0,
        sub_bass_debleed=True,
    )
    restored = IsolateJobSpec.from_dict(spec.to_dict())
    mapped = isolate_config_kwargs_from_spec(restored)
    assert mapped["demucs_shifts"] == 5
    assert mapped["demucs_overlap"] == pytest.approx(0.75)
    assert mapped["demucs_segment"] is None
    assert mapped["demucs_jobs"] == 2
    assert mapped["bleed_gate"] is True
    assert mapped["bass_bleed_mitigation"] is True
    assert mapped["adaptive_fold_gain"] is True
    assert mapped["guitar_ensemble"] is True
    assert mapped["fold_other_mode"] == "band_limited"
    assert mapped["low_end_restore_db"] == pytest.approx(3.0)
    assert mapped["sub_bass_debleed"] is True


def test_isolate_headings_disable_anchors_and_tiles_use_fragment_rerun():
    """Permalink chain-links scroll the page; help= + fragment-scope replace that."""
    page = Path(__file__).resolve().parents[1] / "ui" / "pages" / "isolate.py"
    source = page.read_text(encoding="utf-8")
    app_css = (
        Path(__file__).resolve().parents[1] / "ui" / "app.py"
    ).read_text(encoding="utf-8")
    assert 'anchor=False, help=PAGE_TITLE_HELP' in source
    assert "SEPARATE_TRACKS_HELP" in source
    assert 'st.subheader("Downloads", anchor=False, help=DOWNLOADS_HELP)' in source
    assert "SECTION_OPTIONAL_HELP" in source
    assert "@st.fragment" in source
    assert 'st.rerun(scope="fragment")' in source
    assert "def _rerun_after_tile_pick" in source
    assert "stHeaderActionElements" in app_css
    assert 'markdown("### Separate tracks")' not in source
    picker = source[
        source.find("def _render_outcome_picker") : source.find("def _render_engine_panel")
    ]
    assert "_render_engine_panel(" in picker
    assert 'key="isolate_speed_preset"' in picker
    section_head = source[
        max(0, source.find("def _render_section_and_outcomes") - 40) : source.find(
            "def _render_section_and_outcomes"
        )
        + 40
    ]
    assert "@st.fragment" in section_head
    rerun_fn = source[
        source.find("def _rerun_preserve_scroll") : source.find("def _render_custom_stem_grid")
    ]
    assert 'st.rerun(scope="fragment")' in rerun_fn
    assert "is_pro_mode" not in rerun_fn
    assert "def _rerun_scroll_top" in rerun_fn
    assert "_rerun_after_tile_pick()" in source[
        source.find("def _render_outcome_tile") : source.find("def _render_custom_stem_grid")
    ]


def test_lite_new_cta_captions_chosen_outcome_and_source():
    page = Path(__file__).resolve().parents[1] / "ui" / "pages" / "isolate.py"
    source = page.read_text(encoding="utf-8")
    new_ws = source[
        source.find("def _render_new_workspace") : source.find("def _render_mixer_region_caption")
    ]
    assert 'key="isolate_separate"' in new_ws
    assert "_enqueue_confirmed_job(choice, audio_path)" in new_ws
    assert "OUTCOME_CARD_KEY" in new_ws
    assert "_has_source_for_job(choice)" in new_ws
    assert "Custom ·" in new_ws
    css = (
        Path(__file__).resolve().parents[1] / "ui" / "app.py"
    ).read_text(encoding="utf-8")
    assert "st-key-isolate_outcome_pick_" in css
    assert "st-key-isolate_stem_pick_" in css
    assert "white-space: pre-line" in css
    assert "flex-direction: column" in css
    assert "display: block !important" in css
    assert "margin-left: auto !important" in css
    assert "overflow-wrap: normal" in css
    assert "2.35rem" in css
    assert "Apple Color Emoji" not in css
    assert "stIconEmoji" not in css
    assert "mask-image" not in css
    for banned in ("keys", "wind", "strings", "multimedia"):
        assert f"st-key-isolate_stem_pick_{banned}" not in css


def test_tile_icons_are_markdown_data_uris_not_emoji():
    import base64

    def svg_body(md: str) -> str:
        uri = md[md.index("](") + 2 : -1]
        return base64.standard_b64decode(uri.split(",", 1)[1]).decode("utf-8")

    for stem_id in CUSTOM_STEM_TILE_ORDER:
        md = stem_icon_markdown(stem_id)
        assert md.startswith("![")
        assert "data:image/svg+xml;base64," in md
        assert not any(ord(ch) > 127 for ch in md)
        assert "#ff4b4b" in svg_body(md)
        selected = stem_icon_markdown(stem_id, selected=True)
        assert "#ffffff" in svg_body(selected)
        assert "#ff4b4b" not in svg_body(selected)
    for card_id in OUTCOME_CARD_ORDER:
        md = outcome_icon_markdown(card_id)
        assert md.startswith("![")
        assert "data:image/svg+xml;base64," in md
        assert not any(ord(ch) > 127 for ch in md)
        assert "#ffffff" in svg_body(outcome_icon_markdown(card_id, selected=True))


def test_roformer_speed_note_names_the_gpu_this_host_actually_has():
    mac = roformer_speed_note(platform="darwin")
    win = roformer_speed_note(platform="win32")
    linux = roformer_speed_note(platform="linux")
    assert "Apple GPU (MPS)" in mac
    # Windows users were previously told to look for an Apple setting.
    assert "Apple" not in win
    assert "NVIDIA GPU (CUDA)" in win
    assert "Apple" not in linux
    assert "CUDA" in linux
    for note in (mac, win, linux):
        assert "Speed only tunes Demucs" in note


def test_resolve_ui_mode_defaults_to_lite_and_rejects_junk():
    assert resolve_ui_mode("Pro") == "Pro"
    assert resolve_ui_mode("pro") == "Pro"
    assert resolve_ui_mode("Lite") == "Lite"
    assert resolve_ui_mode(None) == "Lite"
    assert resolve_ui_mode("") == "Lite"
    assert resolve_ui_mode("expert") == "Lite"
    assert DEFAULT_UI_MODE == "Lite"


def test_is_pro_mode_reads_the_session():
    assert is_pro_mode({}) is False
    assert is_pro_mode({UI_MODE_KEY: "Pro"}) is True
    assert is_pro_mode({UI_MODE_KEY: "Lite"}) is False


def test_settings_survive_a_restart_round_trip():
    session = {
        "isolate_quality": "extreme",
        "isolate_device": "cpu",
        "isolate_guitar_ft": True,
        "isolate_guitar_track": "guitar_roformer",
        "unrelated_key": "dropped",
    }
    payload = persisted_settings_payload(session)
    assert "unrelated_key" not in payload
    assert payload["isolate_quality"] == "extreme"

    fresh: dict = {}
    apply_persisted_settings(fresh, payload)
    assert fresh["isolate_quality"] == "extreme"
    assert fresh["isolate_guitar_ft"] is True
    assert fresh["isolate_guitar_track"] == "guitar_roformer"


def test_restoring_settings_never_overwrites_a_live_choice():
    live = {"isolate_quality": "fast"}
    apply_persisted_settings(live, {"isolate_quality": "extreme"})
    assert live["isolate_quality"] == "fast"


def test_ui_state_payload_carries_mode_and_settings(tmp_path):
    session = {UI_MODE_KEY: "Pro", "isolate_quality": "high"}
    payload = isolate_ui_state_payload(session)
    assert payload["mode"] == "Pro"
    assert payload["settings"]["isolate_quality"] == "high"

    restored: dict = {}
    apply_stored_isolate_ui_state(restored, payload)
    assert restored[UI_MODE_KEY] == "Pro"
    assert restored["isolate_quality"] == "high"


def test_mode_survives_relaunch_via_disk(tmp_path):
    path = tmp_path / "isolate_ui_state.json"
    assert load_ui_mode({}, path) == "Lite"
    write_ui_mode(path, "Pro")
    assert load_ui_mode({}, path) == "Pro"


def test_writing_mode_does_not_erase_the_rest_of_the_ui_state(tmp_path):
    path = tmp_path / "isolate_ui_state.json"
    write_isolate_ui_state(path, {"workspace": "Mixer", "run_dir": "/runs/abc"})
    write_ui_mode(path, "Pro")
    stored = read_isolate_ui_state(path)
    assert stored["mode"] == "Pro"
    assert stored["workspace"] == "Mixer"
    assert stored["run_dir"] == "/runs/abc"


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


def test_adopt_audio_into_run_copies_into_output_dir(tmp_path):
    src_dir = tmp_path / "stage"
    src_dir.mkdir()
    src = src_dir / "song.wav"
    src.write_bytes(b"RIFF")
    out = tmp_path / "run"
    out.mkdir()
    adopted = adopt_audio_into_run(src, out)
    assert adopted == out / "song.wav"
    assert adopted.read_bytes() == b"RIFF"
    assert src.exists()
    assert adopt_audio_into_run(adopted, out) == adopted


def test_is_youtube_staging_path_requires_data_dir_child(tmp_path, monkeypatch):
    import ui.isolate_state as state
    import ui.common as common

    monkeypatch.setattr(common, "DATA_DIR", tmp_path)
    monkeypatch.setattr(state, "DATA_DIR", tmp_path)
    run = tmp_path / "abcd"
    run.mkdir()
    wav = run / "clip.wav"
    wav.write_bytes(b"x")
    assert is_youtube_staging_path(wav, "youtube:https://youtu.be/a")
    assert not is_youtube_staging_path(wav, "file.wav:1")
    outside = tmp_path.parent / "outside.wav"
    outside.write_bytes(b"y")
    assert not is_youtube_staging_path(outside, "youtube:https://youtu.be/a")


def test_discard_youtube_staging_deletes_run_dir(tmp_path, monkeypatch):
    import ui.isolate_state as state
    import ui.common as common

    monkeypatch.setattr(common, "DATA_DIR", tmp_path)
    monkeypatch.setattr(state, "DATA_DIR", tmp_path)
    run = tmp_path / "stage1"
    run.mkdir()
    wav = run / "clip.wav"
    wav.write_bytes(b"x")
    fp = "youtube:https://youtu.be/a"
    assert discard_youtube_staging(wav, fingerprint=fp) is True
    assert not run.exists()


def test_discard_youtube_staging_skips_retain_and_in_flight(tmp_path, monkeypatch):
    import ui.isolate_state as state
    import ui.common as common

    monkeypatch.setattr(common, "DATA_DIR", tmp_path)
    monkeypatch.setattr(state, "DATA_DIR", tmp_path)
    run = tmp_path / "stage2"
    run.mkdir()
    wav = run / "clip.wav"
    wav.write_bytes(b"x")
    fp = "youtube:https://youtu.be/b"
    assert (
        discard_youtube_staging(wav, fingerprint=fp, retain_paths=(wav,)) is False
    )
    assert run.exists()

    monkeypatch.setattr(state, "staging_paths_still_needed", lambda _p: True)
    assert discard_youtube_staging(wav, fingerprint=fp) is False
    assert run.exists()


def test_reset_new_tab_source_discards_youtube_staging(tmp_path, monkeypatch):
    import ui.isolate_state as state
    import ui.common as common

    monkeypatch.setattr(common, "DATA_DIR", tmp_path)
    monkeypatch.setattr(state, "DATA_DIR", tmp_path)
    run = tmp_path / "ytstage"
    run.mkdir()
    wav = run / "clip.wav"
    wav.write_bytes(b"x")
    session: dict[str, object] = {
        "isolate_upload_key": 1,
        "isolate_pending_audio_path": str(wav),
        "isolate_pending_fp": "youtube:https://youtu.be/z",
        "isolate_upload_fp": "youtube:https://youtu.be/z",
    }
    reset_new_tab_source(session)
    assert "isolate_pending_audio_path" not in session
    assert not run.exists()


def test_enqueue_confirmed_job_adopts_youtube_staging_before_enqueue():
    page = Path(__file__).resolve().parents[1] / "ui" / "pages" / "isolate.py"
    source = page.read_text(encoding="utf-8")
    enqueue = source[
        source.find("def _enqueue_confirmed_job") : source.find("def _library_status_row")
    ]
    assert "adopt_audio_into_run(" in enqueue
    assert "discard_youtube_staging(" in enqueue
    assert 'startswith("youtube:")' in enqueue
    stage = source[
        source.find("def _stage_youtube_audio") : source.find("def _youtube_search_dialog")
    ]
    assert "discard_youtube_staging(" in stage


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


def test_sync_output_name_on_youtube_preferred_label_beats_video_id():
    name, named, auto, changed = sync_output_name_on_youtube(
        youtube_url="https://youtu.be/YFMF4ZFmtnU",
        last_named_url="https://youtu.be/oldvid",
        output_name="old title",
        auto_output_name="old title",
        preferred_label="AC/DC - Girls Got Rhythm (Official Audio)",
    )
    assert changed is True
    assert name == "AC/DC - Girls Got Rhythm (Official Audio)"
    assert named == "https://youtu.be/YFMF4ZFmtnU"
    assert auto == name


def test_queue_youtube_url_with_title_syncs_output_name():
    session: dict[str, object] = {
        "isolate_youtube_enabled": True,
        ISOLATE_OUTPUT_NAME_KEY: "Megadeth - Holy Wars",
        ISOLATE_NAMED_YOUTUBE_URL_KEY: "https://youtu.be/oldvid",
        ISOLATE_AUTO_OUTPUT_NAME_KEY: "Megadeth - Holy Wars",
    }
    queue_youtube_url(
        session,
        "https://youtu.be/YFMF4ZFmtnU",
        title="AC/DC - Girls Got Rhythm (Official Audio)",
    )
    assert session[ISOLATE_YOUTUBE_TITLE_PENDING_KEY] == (
        "AC/DC - Girls Got Rhythm (Official Audio)"
    )
    apply_pending_youtube_url(session)
    applied = apply_youtube_output_name_sync(session)
    assert applied == "AC/DC - Girls Got Rhythm (Official Audio)"
    assert session[ISOLATE_OUTPUT_NAME_KEY] == applied
    assert ISOLATE_YOUTUBE_TITLE_PENDING_KEY not in session


def test_youtube_search_use_queues_hit_title():
    page = Path(__file__).resolve().parents[1] / "ui" / "pages" / "isolate.py"
    source = page.read_text(encoding="utf-8")
    dialog = source[
        source.find("def _youtube_search_dialog") : source.find("def _stateful_expander")
    ]
    assert "queue_youtube_url(st.session_state, url, title=title)" in dialog
    assert "_download_youtube_with_status(" in dialog
    assert "st.status(" in source[
        source.find("def _download_youtube_with_status") : source.find(
            "def _youtube_search_dialog"
        )
    ]
    assert "Downloading" in dialog or "Downloading" in source[
        source.find("def _download_youtube_with_status") : source.find(
            "def _youtube_search_dialog"
        )
    ]
    # Use downloads in-dialog; do not close-first + silent auto-download.
    use_block = dialog[dialog.find('key=f"isolate_youtube_pick_') :]
    assert "_close_youtube_search_dialog()" in use_block
    assert use_block.find("_download_youtube_with_status(") < use_block.find(
        "_close_youtube_search_dialog()"
    )
    controls = source[
        source.find("def _render_separation_controls") : source.find("def _ffmpeg_install_hint")
    ]
    assert "_download_youtube_with_status(" in controls
    assert 'key="isolate_youtube_download"' in controls


def test_enqueue_confirmed_job_opens_queue_with_loading_overlay():
    page = Path(__file__).resolve().parents[1] / "ui" / "pages" / "isolate.py"
    source = page.read_text(encoding="utf-8")
    enqueue = source[
        source.find("def _enqueue_confirmed_job") : source.find("def _library_status_row")
    ]
    # Overlay first; draft-origin jobs stay on that tab instead of jumping Home.
    assert '["_isolate_pending_queue"] = True' in enqueue
    assert "_request_loading_overlay()" in enqueue
    assert "_rerun_scroll_top()" in enqueue
    assert "origin_tab=" in enqueue
    assert "mark_draft_tab_processing" in enqueue
    assert '["_isolate_keep_draft_tab"]' in enqueue
    assert 'WORKSPACE_NEXT_KEY] = "Queue"' not in enqueue
    main_tail = source[source.find('st.session_state["_isolate_form_drawn"]') :]
    assert 'pop("_isolate_pending_queue"' in main_tail
    assert 'pop("_isolate_keep_draft_tab"' in main_tail
    assert "open_home_shell" in main_tail
    assert "_rerun_scroll_top()" in main_tail
    assert "def _scroll_main_to_top" in source
    assert "isolate_scroll_top_token" in source
    assert "_scroll_main_to_top(" in source
    assert source.count("components.html") == 1
    poll = source[
        source.find("def _poll_running_jobs") : source.find("def _queue_tab_fragment")
    ]
    assert "promote_job_origin_tab" in poll
    tabs = source[
        source.find("def _render_moises_tab_strip") : source.find("def _has_source_for_job")
    ]
    assert "draft_tab_job_overlays" in tabs
    assert 'item["busy"]' in tabs or '"busy"' in tabs
    css = (
        Path(__file__).resolve().parents[1] / "ui" / "app.py"
    ).read_text(encoding="utf-8")
    assert "pointer-events: auto !important" in css
    assert "audiotools-global-loading-root" in css


def test_apply_youtube_output_name_sync_queues_before_widget():
    session: dict[str, object] = {
        ISOLATE_YOUTUBE_URL_KEY: "https://youtu.be/newvid",
        ISOLATE_OUTPUT_NAME_KEY: "Megadeth - Holy Wars",
        ISOLATE_NAMED_YOUTUBE_URL_KEY: "https://youtu.be/oldvid",
        ISOLATE_AUTO_OUTPUT_NAME_KEY: "Megadeth - Holy Wars",
    }
    applied = apply_youtube_output_name_sync(session)
    assert applied == "newvid"
    assert session[ISOLATE_OUTPUT_NAME_KEY] == "newvid"
    assert ISOLATE_OUTPUT_NAME_PENDING_KEY not in session


def test_running_progress_view_keeps_raw_worker_text_out_of_the_label():
    view = running_progress_view(
        {
            "status": "running",
            "stage": "separate",
            "message": "demucs.apply: segment 4/9 shifts=1 device=cpu",
            "progress": 0.5,
        },
        now=0.0,
    )
    assert "demucs.apply" not in view["label"]
    assert "device=cpu" not in view["label"]
    assert view["hint"]
    assert "demucs.apply" not in view["hint"]


def test_running_progress_view_exposes_checklist_separately_from_the_label():
    view = running_progress_view(
        {"status": "running", "stage": "separate", "message": "", "progress": 0.5},
        now=0.0,
    )
    # The checklist is Pro-only detail: available on the view, never folded
    # into the one-line label that Lite shows.
    assert view["checklist_md"]
    assert view["checklist_md"] not in view["label"]
    assert view["checklist_md"].count("**") >= 2


def test_mixer_component_key_is_stable_for_the_same_run():
    first = mixer_component_key("/runs/abc")
    assert first == mixer_component_key("/runs/abc")
    assert first != mixer_component_key("/runs/def")
    assert first.startswith(MIXER_COMPONENT_KEY_PREFIX)


def test_mixer_component_key_survives_a_streamlit_key_roundtrip():
    # Streamlit keys must be plain identifiers; a path with separators would
    # otherwise leak into the DOM id and remount the iframe.
    key = mixer_component_key("C:\\Users\\me\\runs\\my song (live)")
    assert key.replace("_", "").isalnum()


def test_finishing_a_job_sends_the_user_to_the_mixer_not_the_queue():
    session: dict = {WORKSPACE_NEXT_KEY: "Mixer"}
    assert apply_workspace_tab(session, has_artifacts=True) == "Mixer"
    assert session[WORKSPACE_KEY] == "Mixer"
    assert WORKSPACE_NEXT_KEY not in session


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


def test_youtube_search_preview_does_not_use_st_video_embed():
    """Official uploads often refuse youtube.com/embed; st.video shows 'unavailable'."""
    page = Path(__file__).resolve().parents[1] / "ui" / "pages" / "isolate.py"
    source = page.read_text(encoding="utf-8")
    dialog = source[
        source.find("def _youtube_search_dialog") : source.find("def _stateful_expander")
    ]
    assert "st.video(" not in dialog
    assert "Open on YouTube" in dialog
    assert "isolate_youtube_preview_" in dialog
    assert "In-app YouTube playback is often blocked" in dialog


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
    }
    assert pending_upload_fp_for_stale(session) == "song.wav:1"
    session["isolate_pending_audio_path"] = str(tmp_path / "missing.wav")
    assert pending_upload_fp_for_stale(session) is None
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


def test_apply_shell_view_home_and_mix():
    from ui.isolate_state import (
        SHELL_VIEW_KEY,
        SHELL_VIEW_NEXT_KEY,
        apply_shell_view,
        open_home_shell,
        open_mix_shell,
    )

    session: dict = {}
    assert apply_shell_view(session) == "home"
    open_mix_shell(session)
    assert apply_shell_view(session) == "mix"
    assert session[SHELL_VIEW_KEY] == "mix"
    assert SHELL_VIEW_NEXT_KEY not in session
    open_home_shell(session)
    assert apply_shell_view(session) == "home"


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


def test_open_mix_tabs_add_close_and_cap(tmp_path: Path):
    from ui.isolate_state import (
        OPEN_MIX_TABS_KEY,
        OPEN_MIX_TABS_MAX,
        add_open_mix_tab,
        close_open_mix_tab,
        normalize_open_mix_tabs,
    )

    dirs = []
    for i in range(OPEN_MIX_TABS_MAX + 2):
        d = tmp_path / f"run{i}"
        d.mkdir()
        dirs.append(str(d))
    session: dict = {}
    for d in dirs:
        add_open_mix_tab(session, d, cap=OPEN_MIX_TABS_MAX)
    assert len(session[OPEN_MIX_TABS_KEY]) == OPEN_MIX_TABS_MAX
    assert session[OPEN_MIX_TABS_KEY][0] == dirs[2]
    assert session[OPEN_MIX_TABS_KEY][-1] == dirs[OPEN_MIX_TABS_MAX + 1]

    # Focusing an already-open tab must not move it to the end.
    before = list(session[OPEN_MIX_TABS_KEY])
    add_open_mix_tab(session, dirs[2], cap=OPEN_MIX_TABS_MAX)
    assert session[OPEN_MIX_TABS_KEY] == before
    assert session[OPEN_MIX_TABS_KEY].count(dirs[2]) == 1
    assert session[OPEN_MIX_TABS_KEY][0] == dirs[2]

    neighbor = close_open_mix_tab(session, dirs[2])
    assert dirs[2] not in session[OPEN_MIX_TABS_KEY]
    assert neighbor in session[OPEN_MIX_TABS_KEY]

    capped = normalize_open_mix_tabs(dirs, existing={dirs[0], dirs[1]}, cap=8)
    assert capped == [dirs[0], dirs[1]]


def test_plus_opens_distinct_new_draft_tabs(tmp_path: Path):
    from ui.isolate_state import (
        DRAFT_SOURCES_KEY,
        NEW_DRAFT_TAB_ID,
        OPEN_MIX_TABS_KEY,
        SHELL_TAB_KEY,
        add_open_mix_tab,
        apply_shell_view,
        close_open_mix_tab,
        draft_tab_title,
        focus_new_draft_tab,
        is_new_draft_tab,
        open_home_shell,
        open_mix_tabs_for_session,
        open_new_draft_tab,
    )

    run = tmp_path / "mix"
    run.mkdir()
    session: dict = {OPEN_MIX_TABS_KEY: [str(run)]}
    first = open_new_draft_tab(session, fresh=False)
    assert is_new_draft_tab(first)
    assert first != NEW_DRAFT_TAB_ID
    assert session[OPEN_MIX_TABS_KEY][-1] == first
    assert session[SHELL_TAB_KEY] == first
    assert apply_shell_view(session) == "home"

    session["isolate_pending_audio_path"] = str(tmp_path / "song_a.wav")
    session["isolate_output_name"] = "Song A"
    second = open_new_draft_tab(session, fresh=True)
    assert second != first
    assert session[OPEN_MIX_TABS_KEY].count(first) == 1
    assert session[OPEN_MIX_TABS_KEY].count(second) == 1
    assert session[SHELL_TAB_KEY] == second
    assert not session.get("isolate_pending_audio_path")
    assert draft_tab_title(session, first) == "Song A"
    assert draft_tab_title(session, second) == "New"

    focus_new_draft_tab(session, first)
    assert session[SHELL_TAB_KEY] == first
    assert session.get("isolate_output_name") == "Song A"
    assert "song_a" in str(session.get("isolate_pending_audio_path") or "")

    tabs = open_mix_tabs_for_session(session, library_dirs=[str(run)])
    assert first in tabs and second in tabs and str(run) in tabs

    open_home_shell(session)
    assert session[SHELL_TAB_KEY] == "home"
    assert first in session[OPEN_MIX_TABS_KEY]

    neighbor = close_open_mix_tab(session, first)
    assert first not in session[OPEN_MIX_TABS_KEY]
    assert first not in (session.get(DRAFT_SOURCES_KEY) or {})
    assert neighbor in session[OPEN_MIX_TABS_KEY]

    # Legacy __new__ id still counts as a draft.
    add_open_mix_tab(session, NEW_DRAFT_TAB_ID)
    assert is_new_draft_tab(NEW_DRAFT_TAB_ID)
    assert NEW_DRAFT_TAB_ID in session[OPEN_MIX_TABS_KEY]


def test_promote_draft_tab_to_run_keeps_slot(tmp_path: Path):
    from ui.isolate_state import (
        DRAFT_SOURCES_KEY,
        OPEN_MIX_TABS_KEY,
        SHELL_TAB_KEY,
        draft_tab_job_overlays,
        mark_draft_tab_processing,
        open_new_draft_tab,
        promote_job_origin_tab,
        replace_open_mix_tab,
    )

    other = tmp_path / "other"
    other.mkdir()
    run = tmp_path / "finished"
    run.mkdir()
    session: dict = {OPEN_MIX_TABS_KEY: [str(other)]}
    draft = open_new_draft_tab(session, fresh=True)
    mark_draft_tab_processing(session, draft, title="My Song")
    assert session[SHELL_TAB_KEY] == draft
    assert session[DRAFT_SOURCES_KEY][draft]["isolate_output_name"] == "My Song"

    overlays = draft_tab_job_overlays(
        [
            {
                "id": "j1",
                "status": "running",
                "progress": 0.42,
                "title": "My Song",
                "origin_tab": draft,
            },
            {
                "id": "j2",
                "status": "queued",
                "progress": 0.0,
                "title": "Other",
                "origin_tab": "__new__:gone",
            },
            {"id": "j3", "status": "succeeded", "origin_tab": draft},
        ]
    )
    assert overlays[draft]["progress"] == pytest.approx(0.42)
    assert overlays[draft]["busy"] is True
    assert "__new__:gone" in overlays
    assert overlays["__new__:gone"]["progress"] is None

    promoted = promote_job_origin_tab(
        session,
        {"run_dir": str(run), "origin_tab": draft},
    )
    assert promoted == str(run)
    assert session[OPEN_MIX_TABS_KEY] == [str(other), str(run)]
    assert draft not in session[OPEN_MIX_TABS_KEY]
    assert draft not in session.get(DRAFT_SOURCES_KEY, {})
    assert session.get(SHELL_TAB_KEY) != draft

    session2: dict = {OPEN_MIX_TABS_KEY: [str(other)]}
    assert promote_job_origin_tab(session2, {"run_dir": str(run)}) == str(run)
    assert session2[OPEN_MIX_TABS_KEY] == [str(other), str(run)]

    session3: dict = {OPEN_MIX_TABS_KEY: [str(other)]}
    replace_open_mix_tab(session3, "__new__:missing", str(run))
    assert session3[OPEN_MIX_TABS_KEY] == [str(other), str(run)]


def test_normalize_prefers_dropping_mixes_before_drafts(tmp_path: Path):
    from ui.isolate_state import (
        NEW_DRAFT_TAB_PREFIX,
        normalize_open_mix_tabs,
    )

    mixes = []
    for i in range(10):
        d = tmp_path / f"m{i}"
        d.mkdir()
        mixes.append(str(d))
    drafts = [f"{NEW_DRAFT_TAB_PREFIX}:{i}" for i in range(3)]
    tabs = drafts + mixes
    out = normalize_open_mix_tabs(
        tabs, cap=8, require_dir=False, protect=[drafts[0]]
    )
    assert drafts[0] in out
    assert all(d in out for d in drafts)
    assert len(out) == 8
    assert sum(1 for p in out if not p.startswith(NEW_DRAFT_TAB_PREFIX)) == 5


def test_isolate_ui_state_roundtrips_open_mix_tabs():
    from ui.isolate_state import OPEN_MIX_TABS_KEY, apply_stored_isolate_ui_state, isolate_ui_state_payload

    session = {OPEN_MIX_TABS_KEY: ["/a", "/b"], "isolate_workspace": "Mixer"}
    payload = isolate_ui_state_payload(session)
    assert payload["open_mix_tabs"] == ["/a", "/b"]
    restored: dict = {}
    apply_stored_isolate_ui_state(restored, payload)
    assert restored[OPEN_MIX_TABS_KEY] == ["/a", "/b"]


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


def test_scroll_policy_preserves_poll_and_jumps_on_nav():
    assert should_request_isolate_scroll_top("poll_progress") is False
    assert should_request_isolate_scroll_top("poll_failed") is False
    assert should_request_isolate_scroll_top("tile_pick") is False
    assert should_request_isolate_scroll_top("engine_widget") is False
    assert should_request_isolate_scroll_top("region") is False
    assert should_request_isolate_scroll_top("status_control") is False
    assert should_request_isolate_scroll_top("mixer_fader") is False
    assert should_request_isolate_scroll_top("unknown_widget") is False
    assert should_request_isolate_scroll_top("enqueue_separate") is True
    assert should_request_isolate_scroll_top("shell_nav") is True
    assert should_request_isolate_scroll_top("open_mixer") is True
    assert should_request_isolate_scroll_top("poll_apply_mixer") is True
    session: dict = {}
    request_isolate_scroll_top(session)
    assert session[ISOLATE_SCROLL_TOP_KEY] is True
    assert isolate_scroll_top_token(session) == 1
    request_isolate_scroll_top(session)
    assert isolate_scroll_top_token(session) == 2
    assert consume_isolate_scroll_top(session) is True
    assert consume_isolate_scroll_top(session) is False


def test_consume_mix_tab_event_applies_once_per_seq():
    last, action, tab_id = consume_mix_tab_event(None, 0)
    assert last == 0 and action is None and tab_id == ""
    last, action, tab_id = consume_mix_tab_event({"action": "plus"}, 0)
    assert last == 1 and action == "plus"
    last, action, tab_id = consume_mix_tab_event({"action": "plus", "seq": 10}, 0)
    assert last == 10 and action == "plus" and tab_id == ""
    last, action, tab_id = consume_mix_tab_event({"action": "plus", "seq": 10}, 10)
    assert last == 10 and action is None
    last, action, tab_id = consume_mix_tab_event(
        {"action": "focus", "id": "/runs/a", "seq": 11}, 10
    )
    assert last == 11 and action == "focus" and tab_id == "/runs/a"
    last, action, tab_id = consume_mix_tab_event({"action": "home", "seq": 12}, 11)
    assert action == "home"
    last, action, tab_id = consume_mix_tab_event(
        {"action": "close", "id": "__new__", "seq": 13}, 12
    )
    assert action == "close" and tab_id == "__new__"
    last, action, tab_id = consume_mix_tab_event({"action": "nope", "seq": 14}, 13)
    assert last == 13 and action is None
    # Missing seq still applies once (older iframe builds).
    last, action, tab_id = consume_mix_tab_event({"action": "plus"}, 20)
    assert last == 21 and action == "plus"


def test_running_poll_does_not_full_rerun_or_scroll_top():
    jobs = [
        {"id": "run", "status": "running"},
        {"id": "wait", "status": "queued"},
    ]
    seeded = plan_isolate_job_poll(
        jobs, consumed_ids=None, viewing_id=None, form_drawn=False
    )
    plan = plan_isolate_job_poll(
        jobs,
        consumed_ids=seeded["consumed_ids"],
        viewing_id=None,
        form_drawn=True,
    )
    assert plan["apply_job"] is None
    assert plan["rerun"] is False
    assert isolate_poll_requires_full_rerun(applied=False, plan_rerun=plan["rerun"]) is False
    assert should_request_isolate_scroll_top("poll_progress") is False
    assert isolate_poll_requires_full_rerun(applied=False, plan_rerun=True) is False
    assert isolate_poll_requires_full_rerun(applied=True, plan_rerun=True) is True


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


def test_os_notify_empty_seed_does_not_toast_stale_failures():
    """First poll with no jobs stored []; later history must not all re-toast."""
    now = 1_700_000_000.0
    stale = {
        "id": "old-fail",
        "status": "failed",
        "title": "Yesterday",
        "finished_at": now - 3600,
        "updated_at": now - 3600,
    }
    fresh_ok = {
        "id": "new-ok",
        "status": "succeeded",
        "title": "Hangar 18",
        "finished_at": now - 5,
        "updated_at": now - 5,
    }
    ids, pending = jobs_needing_os_notify([stale, fresh_ok], [], now=now)
    assert set(ids) == {"old-fail", "new-ok"}
    assert [row["id"] for row in pending] == ["new-ok"]
    ids, pending = jobs_needing_os_notify([stale, fresh_ok], ids, now=now)
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
    assert capped == pytest.approx(0.98)
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


def test_listening_picker_uses_moises_top_strip_not_inline_buttons():
    page = Path(__file__).resolve().parents[1] / "ui" / "pages" / "isolate.py"
    source = page.read_text(encoding="utf-8")
    picker = source[source.find("def _render_listening_switcher") : source.find("def _has_source_for_job")]
    assert "Open mixes" not in picker
    assert "mix_tab_focus_" not in picker
    assert '"Change mix"' not in picker
    assert 'label="Listening to"' in picker
    assert "_render_moises_tab_strip" in source
    assert "st.tabs(" not in source[source.find("def main") :]
    assert "mix_tabs(" in source
    assert 'action == "plus"' in source
    assert "open_new_draft_tab" in source
    assert 'action == "home"' in source


def test_listening_switcher_renames_current_mix_from_editable_name():
    page = Path(__file__).resolve().parents[1] / "ui" / "pages" / "isolate.py"
    source = page.read_text(encoding="utf-8")
    switcher = source[source.find("def _render_listening_switcher") : source.find("def _has_source_for_job")]
    assert 'label="Listening to"' in switcher
    assert 'key="isolate_listen_name"' in switcher
    assert "on_change=_rename_listen_run" in switcher
    assert "def _rename_listen_run" in source
    assert "rename_run_title(Path(run_dir), new_name)" in source
    assert 'label="Mix name"' not in switcher
    assert "isolate_rename_mix" not in switcher
    assert "isolate_mix_name_input" not in switcher


def test_poll_and_queue_fragments_run_every_one_second():
    page = Path(__file__).resolve().parents[1] / "ui" / "pages" / "isolate.py"
    source = page.read_text(encoding="utf-8")
    assert source.count("@st.fragment(run_every=1.0)") == 2
    assert "run_every=2.0" not in source
    poll = source[
        source.find("def _poll_running_jobs") : source.find("def _queue_tab_fragment")
    ]
    assert "isolate_poll_requires_full_rerun" in poll
    assert "_rerun_scroll_top()" in poll
    assert "failed_flash" not in poll
    queue_row = source[
        source.find("def _render_queue_job_row") : source.find("def _render_failed_strip")
    ]
    assert "_rerun_preserve_scroll()" in queue_row
    assert "_rerun_scroll_top()" in queue_row
    assert "open_mixer_" in queue_row
    tabs = source[
        source.find("def _render_moises_tab_strip") : source.find("def _has_source_for_job")
    ]
    assert tabs.count("_rerun_scroll_top()") >= 4
    assert "st.rerun()" not in tabs
    assert 'key="isolate_moises_tabs"' in tabs
    assert "_mix_tabs_nonce" not in tabs
    assert "isolate_moises_tabs_{nonce}" not in tabs
    assert "consume_mix_tab_event" in tabs
    status = source[
        source.find("def _render_status_strip") : source.find("def _poll_running_jobs")
    ]
    assert 'key="isolate_status_strip"' in status
    assert "st.empty()" in status
    assert "if not (running or failed or show_queued or stopping_previous):" not in status
    main = source[source.find("def main") :]
    assert "isolate_scroll_top_token" in main
    assert "consume_isolate_scroll_top" not in main
    css = (
        Path(__file__).resolve().parents[1] / "ui" / "app.py"
    ).read_text(encoding="utf-8")
    assert "st-key-isolate_status_strip" in css
    assert "st-key-isolate_status_running" in css
    assert "min-height: 6.5rem" in css
    assert ":not(:last-of-type)" in css
    assert 'iframe[title*="mix_tabs"]' not in css


def test_new_tab_section_and_output_name_prominent_before_advanced():
    """Name and trim stay above Advanced, so the fields people edit aren't buried.

    Anchored on widget keys and call sites rather than label copy, so rewording
    does not fail the test but reordering does.
    """
    page = Path(__file__).resolve().parents[1] / "ui" / "pages" / "isolate.py"
    source = page.read_text(encoding="utf-8")
    controls = source[
        source.find("def _render_separation_controls") : source.find("def _ffmpeg_install_hint")
    ]
    block_at = controls.find("_render_section_and_outcomes(")
    output_at = controls.find('key="isolate_output_name"')
    assert block_at != -1 and output_at != -1
    assert output_at < block_at
    section = source[
        source.find("def _render_section_and_outcomes") : source.find("def _persist_kwargs")
    ]
    region_at = section.find("_render_region_controls(")
    picker_at = section.find("_render_outcome_picker(")
    assert region_at != -1 and picker_at != -1
    assert region_at < picker_at
    picker = source[
        source.find("def _render_outcome_picker") : source.find("def _render_engine_panel")
    ]
    assert "_render_engine_panel(" in picker


def test_isolate_youtube_paste_and_search_are_always_visible():
    page = Path(__file__).resolve().parents[1] / "ui" / "pages" / "isolate.py"
    source = page.read_text(encoding="utf-8")
    controls = source[
        source.find("def _render_separation_controls") : source.find("def _ffmpeg_install_hint")
    ]
    assert 'key="isolate_youtube_enabled"' not in controls
    assert 'key="isolate_youtube_url"' in controls
    assert 'key="isolate_youtube_search_open_btn"' in controls
    assert "YOUTUBE_DISCLAIMER" in controls
    assert "Off until you paste a URL or search" in controls
    assert "off in this installer build" not in source


def test_mixer_builds_current_mix_on_save_click():
    page = Path(__file__).resolve().parents[1] / "ui" / "pages" / "isolate.py"
    source = page.read_text(encoding="utf-8")
    fragment = source[
        source.find("def _mixer_and_downloads_fragment") : source.find("def _save_all_tracks")
    ]
    assert "_build_current_mix(" not in fragment
    panel = source[
        source.find("def _render_downloads_panel") : source.find("def _resolve_audio_for_job")
    ]
    assert "_build_current_mix(" in panel
    assert 'key="isolate_save_mix"' in panel


def test_mixer_workspace_lite_shares_fixup_and_tab_pdf_carry_over():
    page = Path(__file__).resolve().parents[1] / "ui" / "pages" / "isolate.py"
    source = page.read_text(encoding="utf-8")
    mixer_ws = source[
        source.find("def _render_mixer_workspace") : source.find("def _render_file_ready_banner")
    ]
    assert "Fix the guitar track" not in mixer_ws
    assert "_render_guitar_fixup_panel(" in mixer_ws
    assert "Make a tab PDF from this" in mixer_ws
    assert "if pro and source_audio_path" not in mixer_ws


def test_desktop_mixer_renders_stem_hint_captions():
    frontend = (
        Path(__file__).resolve().parents[1]
        / "ui"
        / "stem_mixer_component"
        / "frontend"
        / "src"
        / "main.ts"
    )
    source = frontend.read_text(encoding="utf-8")
    assert 'class="stem-hint"' in source
    assert "stem.hint" in source


def test_lite_region_defaults_full_file_with_safer_warn():
    page = Path(__file__).resolve().parents[1] / "ui" / "pages" / "isolate.py"
    source = page.read_text(encoding="utf-8")
    region = source[
        source.find("def _render_region_controls") : source.find("def _render_section_preview")
    ]
    enqueue = source[source.find("def _enqueue_confirmed_job") :]
    assert "Safer: first" in region
    assert "LITE_MAX_DURATION_SEC" in region
    assert "float(duration)" in region
    assert "clamp_lite_clip" not in enqueue
    assert "is_pro_mode" in region
    assert "no silent clamp" in region or "never a silent clamp" in region


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
    assert (
        default_guitar_track_option(
            roformer_available=True, prefer_roformer=False
        )
        == "guitar_demucs_6s"
    )


def test_promote_default_guitar_option_respects_prefer_roformer():
    base = ["vocals_demucs", "guitar_demucs_6s"]
    assert promote_default_guitar_option(
        base, roformer_available=True, prefer_roformer=False
    ) == ["vocals_demucs", "guitar_demucs_6s"]
    assert promote_default_guitar_option(
        base, roformer_available=True, prefer_roformer=True
    ) == ["vocals_demucs", "guitar_roformer"]


def test_resolve_outcome_card_lite_cpu_keeps_demucs_when_roformer_installed():
    band = resolve_outcome_card(
        "band", roformer_available=True, prefer_roformer=False
    )
    assert "guitar_demucs_6s" in band
    assert "guitar_roformer" not in band
    guitar = resolve_outcome_card(
        "guitar", roformer_available=True, prefer_roformer=False
    )
    assert guitar == ["guitar_demucs_6s"]
    strong = resolve_outcome_card(
        "guitar", roformer_available=True, prefer_roformer=True
    )
    assert strong == ["guitar_roformer"]


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
    assert "Piano (Demucs 6-stem" in resolved["tracks"]


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


def test_custom_selected_stems_keeps_metronome_on():
    selected = custom_selected_stems(
        ["vocals", "guitar", "metronome"],
        ["vocals"],
    )
    assert selected["vocals"] is True
    assert selected["guitar"] is False
    assert selected["metronome"] is True


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


def test_estimate_roformer_ignores_demucs_quality():
    stages = isolation_stages_for_job(expects_guitar=True)
    fast, _ = estimate_job_seconds(
        audio_duration_sec=100.0,
        quality="fast",
        device="cpu",
        stages=stages,
        model="bs_roformer_sw",
    )
    balanced, _ = estimate_job_seconds(
        audio_duration_sec=100.0,
        quality="balanced",
        device="cpu",
        stages=stages,
        model="bs_roformer_sw",
    )
    assert fast is not None and balanced is not None
    assert fast == pytest.approx(balanced)
    assert estimated_stage_seconds("separate", stages, fast) == pytest.approx(
        100.0 * 2.2, rel=0.02
    )


def test_estimate_roformer_scales_by_cores_and_device():
    stages = isolation_stages_for_job(expects_guitar=True)
    m1, _ = estimate_job_seconds(
        audio_duration_sec=100.0,
        quality="balanced",
        device="cpu",
        stages=stages,
        model="bs_roformer_sw",
        cpu_threads=4,
    )
    assert estimated_stage_seconds("separate", stages, m1) == pytest.approx(
        100.0 * 2.2 * (8.0 / 4.0), rel=0.02
    )
    mps, _ = estimate_job_seconds(
        audio_duration_sec=100.0,
        quality="balanced",
        device="mps",
        stages=stages,
        model="bs_roformer_sw",
    )
    assert estimated_stage_seconds("separate", stages, mps) == pytest.approx(
        100.0 * 1.0, rel=0.02
    )


def test_estimate_roformer_refine_adds_a_pass():
    stages = isolation_stages_for_job(expects_guitar=True)
    plain, _ = estimate_job_seconds(
        audio_duration_sec=100.0,
        quality="balanced",
        device="cpu",
        stages=stages,
        model="bs_roformer_sw",
    )
    refined, _ = estimate_job_seconds(
        audio_duration_sec=100.0,
        quality="balanced",
        device="cpu",
        stages=stages,
        model="bs_roformer_sw",
        guitar_refine=True,
    )
    assert plain is not None and refined is not None
    assert refined > plain
    assert estimated_stage_seconds("separate", stages, refined) == pytest.approx(
        100.0 * (2.2 + 1.0), rel=0.02
    )


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
    assert default_region_end(120.0, min_length=90) == 90.0
    assert default_region_end(60.0, min_length=90) == 60.0
    assert default_region_end(90.0, min_length=LITE_MAX_DURATION_SEC) == 90.0


def test_clamp_lite_clip():
    start, length, clamped = clamp_lite_clip(0.0, None, 200.0)
    assert start == 0.0
    assert length == LITE_MAX_DURATION_SEC
    assert clamped is True

    start, length, clamped = clamp_lite_clip(0.0, None, 60.0)
    assert length == 60.0
    assert clamped is False

    start, length, clamped = clamp_lite_clip(10.0, 45.0, 200.0)
    assert start == 10.0
    assert length == 45.0
    assert clamped is False

    start, length, clamped = clamp_lite_clip(0.0, 200.0, 200.0)
    assert length == LITE_MAX_DURATION_SEC
    assert clamped is True

    start, length, clamped = clamp_lite_clip(0.0, None, None)
    assert length == LITE_MAX_DURATION_SEC
    assert clamped is False


def test_clamp_region_bounds():
    start, end = clamp_region_bounds(0, 3, 120.0, min_length=5.0)
    assert end - start >= 5.0


def test_stem_label_for_id():
    assert stem_label_for_id("other::guitar") == "Guitar (from Other)"
    assert stem_label_for_id("guitar") == "Guitar"
    assert stem_label_for_id("lead_guitar") == "Lead Guitar"


def _write_wav(path: Path, amplitude: float):
    t = np.linspace(0, 0.5, 22050, endpoint=False)
    tone = (amplitude * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    sf.write(str(path), tone, 44100)


def test_children_from_outputs_filters_silent(tmp_path):
    _write_wav(tmp_path / "guitar.wav", amplitude=0.5)
    _write_wav(tmp_path / "empty.wav", amplitude=0.0)
    out = children_from_outputs(tmp_path)
    assert set(out.keys()) == {"guitar"}
    assert out["guitar"] == tmp_path / "guitar.wav"


def test_children_from_outputs_skips_diagnostics(tmp_path):
    _write_wav(tmp_path / "guitar.wav", amplitude=0.5)
    _write_wav(tmp_path / "guitar_diagnostic.wav", amplitude=0.5)
    out = children_from_outputs(tmp_path)
    assert set(out.keys()) == {"guitar"}


def test_children_from_outputs_skips_metronome(tmp_path):
    _write_wav(tmp_path / "guitar.wav", amplitude=0.5)
    _write_wav(tmp_path / "metronome.wav", amplitude=0.5)
    out = children_from_outputs(tmp_path)
    assert set(out.keys()) == {"guitar"}


def test_children_from_outputs_empty_or_missing(tmp_path):
    assert children_from_outputs(tmp_path / "nope") == {}
    empty = tmp_path / "empty"
    empty.mkdir()
    assert children_from_outputs(empty) == {}


def test_merge_reseparate_removes_source_and_adds_children():
    artifacts = {"other": Path("/a/other.wav"), "vocals": Path("/a/vocals.wav")}
    children = {"other::guitar": Path("/a/other::guitar.wav"), "other::synth": Path("/a/other::synth.wav")}
    merged = merge_reseparate(artifacts, "other", children)
    assert artifacts == {"other": Path("/a/other.wav"), "vocals": Path("/a/vocals.wav")}
    assert "other" not in merged
    assert merged["other::guitar"] == Path("/a/other::guitar.wav")
    assert merged["other::synth"] == Path("/a/other::synth.wav")
    assert merged["vocals"] == Path("/a/vocals.wav")


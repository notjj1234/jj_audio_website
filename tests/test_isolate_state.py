"""Tests for ui.isolate_state helpers."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from ui.isolate_state import (
    DEFAULT_SEPARATION_PRESET,
    DEFAULT_SPEED_PRESET,
    SPEED_PRESETS,
    clamp_region_bounds,
    custom_selected_stems,
    default_region_end,
    format_elapsed,
    format_progress_label,
    resolve_custom_separation,
    resolve_separation_preset,
    resolve_speed_preset,
    should_hide_stale_results,
    stage_progress_percent,
    sync_output_name_on_upload,
    upload_fingerprint,
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


def test_should_hide_stale_results():
    assert not should_hide_stale_results(pending_upload_fp=None, has_artifacts=True)
    assert not should_hide_stale_results(pending_upload_fp="x:1", has_artifacts=False)
    assert should_hide_stale_results(pending_upload_fp="new.mp3:500", has_artifacts=True)


def test_stage_progress_percent_weighted():
    assert stage_progress_percent("ingest") == pytest.approx(0.05)
    assert stage_progress_percent("separate") == pytest.approx(0.80)
    assert stage_progress_percent("done") == pytest.approx(1.0)
    assert stage_progress_percent("unknown") == 0.0


def test_format_progress_label():
    assert format_progress_label(0.42, "Running Demucs") == "42% — Running Demucs"


def test_format_elapsed():
    assert format_elapsed(65) == "1:05"
    assert format_elapsed(0) == "0:00"


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


def test_custom_selected_stems_prefers_lead_rhythm_over_combined_guitar():
    selected = custom_selected_stems(
        ["guitar", "lead_guitar", "rhythm_guitar", "vocals"],
        ["guitar"],
    )
    assert selected["lead_guitar"] is True
    assert selected["rhythm_guitar"] is True
    assert selected["guitar"] is False
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


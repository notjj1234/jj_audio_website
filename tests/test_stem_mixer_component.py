"""Smoke tests for the live stem mixer Streamlit component packaging."""

from __future__ import annotations

import inspect
from pathlib import Path


def test_stem_mixer_build_present():
    from ui.stem_mixer_component import mixer_build_is_complete

    build = (
        Path(__file__).resolve().parents[1]
        / "ui"
        / "stem_mixer_component"
        / "frontend"
        / "build"
    )
    assert mixer_build_is_complete(build), (
        "Mixer frontend is incomplete. Run scripts/dev.ps1 mixer-build "
        "(or npm run build in ui/stem_mixer_component/frontend)"
    )


def test_mixer_build_is_complete_rejects_html_without_assets(tmp_path):
    from ui.stem_mixer_component import mixer_build_is_complete

    (tmp_path / "index.html").write_text(
        '<script type="module" src="./assets/index-missing.js"></script>',
        encoding="utf-8",
    )
    assert mixer_build_is_complete(tmp_path) is False


def test_stem_mixer_import():
    from ui.stem_mixer_component import component_build_available, stem_mixer

    assert component_build_available()
    assert callable(stem_mixer)


def test_stem_mixer_accepts_track_title():
    from ui.stem_mixer_component import stem_mixer

    params = inspect.signature(stem_mixer).parameters
    assert "track_title" in params
    assert params["track_title"].default == ""


def test_stem_mixer_accepts_master_volume():
    from ui.stem_mixer_component import stem_mixer

    params = inspect.signature(stem_mixer).parameters
    assert "initial_master_volume_db" in params
    assert params["initial_master_volume_db"].default == 0.0


def test_stem_mixer_accepts_metronome():
    from ui.stem_mixer_component import stem_mixer

    params = inspect.signature(stem_mixer).parameters
    assert "metronome" in params
    assert params["metronome"].default is None


def _mixer_main_ts() -> str:
    return (
        Path(__file__).resolve().parents[1]
        / "ui"
        / "stem_mixer_component"
        / "frontend"
        / "src"
        / "main.ts"
    ).read_text(encoding="utf-8")


def test_load_stems_creates_context_without_resume():
    text = _mixer_main_ts()
    load = text[text.find("async loadStems(") : text.find("applyGains(gains")]
    assert "createContextForDecode" in load
    assert "ensureContext()" not in load
    assert ".resume()" not in load
    assert "createContextForDecode(): AudioContext" in text


def test_restore_transport_does_not_auto_play():
    text = _mixer_main_ts()
    restore = text[text.find("function restoreTransport") : text.find("function statePayload")]
    assert "applyTransport" not in restore
    assert "wantPlaying" not in restore
    assert "engine.seek" in restore


def _waveform_bar_layout(n: int, width: float) -> tuple[float, float]:
    """Mirror of waveformBarLayout in the mixer frontend."""
    slot = width / max(1, n)
    bar_w = slot * 0.85
    return slot, bar_w


def test_waveform_bars_fit_viewbox_for_512_peaks():
    """512 bars + a 1px gap overflowed viewBox 400 and clipped ~half the wave."""
    text = _mixer_main_ts()
    layout = text[
        text.find("function waveformBarLayout") : text.find("function waveformSeekHtml")
    ]
    draw = text[
        text.find("function waveformSeekHtml") : text.find("function isTypingTarget")
    ]
    assert "width / Math.max(1, n)" in layout
    assert "slot * 0.85" in layout
    assert "const gap = 1" not in draw
    assert "Math.max(0.5," not in draw
    assert "i * slot" in draw

    width = 400.0
    n = 512
    slot, bar_w = _waveform_bar_layout(n, width)
    last_x = (n - 1) * slot + (slot - bar_w) / 2
    assert last_x + bar_w <= width + 1e-9
    first_x = (slot - bar_w) / 2
    assert first_x >= 0
    # Peak index i starts at i/n of the row — same mapping as playhead %.
    assert abs((256 * slot) / width - 0.5) < 1e-9


def test_mixer_live_metronome_hot_swap_without_full_reload():
    text = _mixer_main_ts()
    assert "replaceStemBuffer" in text
    assert "metronomeOptions" in text
    assert "buildMetronomeAudioBuffer" in text
    assert 's.id === "metronome" && metro && metro.times1x.length > 0' in text
    clicks = (
        Path(__file__).resolve().parents[1]
        / "ui"
        / "stem_mixer_component"
        / "frontend"
        / "src"
        / "metronomeClicks.ts"
    ).read_text(encoding="utf-8")
    assert "export function applyClickRate" in clicks
    assert "export function buildMetronomeAudioBuffer" in clicks
    assert "hi_tick" in clicks
    assert "data-follow=\"smart\"" in text
    assert "data-follow=\"steady\"" in text
    assert "Follows the song's tempo changes" in text
    assert "Even clicks at one tempo" in text
    assert "steadyTimes1x" in clicks
    assert 'follow === "steady"' in clicks


def test_mixer_playback_presets_and_youtube_frame_are_wired():
    text = _mixer_main_ts()
    assert 'data-preset="all"' in text
    assert 'data-preset="karaoke"' in text
    assert 'data-preset="acapella"' in text
    assert 'data-preset="drumsBass"' in text
    assert "Drums + Bass" in text
    assert "presetSoloMap" in text
    assert 'id !== "vocals" && id !== "metronome"' in text
    assert "function videoNeedsSeek" in text
    assert "youtubeVideoId" in text
    assert "Hide video" in text
    assert "Show video" in text
    assert "Open on YouTube" in text
    assert "controls: 1" in text
    assert "fs: 1" in text
    assert "localVideoUrl" in text
    assert "mixer-video-wrap" in text
    assert "wrap.hidden = !hasVideo || hideYoutubeVideo" in text
    helper = text[text.find("const VIDEO_DRIFT_SEC") : text.find("function presetSoloMap")]
    assert "0.4" in helper
    assert "2000" in helper
    assert "function videoNeedsSeek" in helper

    def video_needs_seek(audio: float, video: float, now_ms: float, last_ms: float) -> bool:
        if now_ms - last_ms < 2000:
            return False
        return abs(video - audio) > 0.4

    assert video_needs_seek(10.0, 10.2, 5000, 0) is False
    assert video_needs_seek(10.0, 10.5, 5000, 0) is True
    assert video_needs_seek(10.0, 12.0, 1000, 0) is False


def test_stem_mixer_accepts_optional_youtube_id():
    from ui.stem_mixer_component import stem_mixer

    params = inspect.signature(stem_mixer).parameters
    assert "youtube_video_id" in params
    assert params["youtube_video_id"].default is None
    assert "hide_youtube_video" in params
    assert params["hide_youtube_video"].default is False
    assert "local_video_url" in params
    assert params["local_video_url"].default is None
    assert "video_offset_sec" in params
    assert params["video_offset_sec"].default == 0.0


def test_mixer_remounts_picture_after_paint_and_offsets_seek():
    text = _mixer_main_ts()
    render = text[text.find("function renderUI") : text.find("function updateTrackTitleDisplay")]
    inner = render.find("root.innerHTML")
    assert inner > 0
    assert render.find("destroyYoutubePlayer()") < inner
    assert render.find("destroyLocalVideo()") < inner
    assert render.rfind("mountPicture();") > inner
    assert "function pictureTimeForMixer" in text
    assert "function mixerTimeForPicture" in text
    assert 'syncOrigin = "audio"' in text
    assert 'syncOrigin = "video"' in text

    def picture_time(mixer: float, offset: float) -> float:
        offset = offset if offset > 0 else 0
        mixer = mixer if mixer > 0 else 0
        return mixer + offset

    def mixer_time(picture: float, offset: float, dur: float) -> float:
        offset = offset if offset > 0 else 0
        raw = picture - offset
        if not dur > 0:
            return max(0.0, raw)
        return max(0.0, min(dur, raw))

    assert picture_time(0, 12.5) == 12.5
    assert picture_time(3, 12.5) == 15.5
    assert mixer_time(15.5, 12.5, 30) == 3
    assert mixer_time(0, 12.5, 30) == 0
    assert mixer_time(100, 12.5, 30) == 30


def test_mixer_video_size_and_position_stay_inside_frame():
    text = _mixer_main_ts()
    assert "function clampVideoWidth" in text
    assert "function clampVideoBox" in text
    assert 'id="btn-drag-video"' in text
    assert 'id="btn-resize-video"' in text
    assert "is-placed" in text
    assert "VIDEO_MIN_WIDTH = 160" in text
    assert "VIDEO_STEM_GUTTER = 160" in text
    assert "videoLayout" in text

    def clamp_video_width(width: float, frame_width: float) -> float:
        min_w = 160.0
        max_w = max(min_w, frame_width - 160.0)
        w = width if width == width else min_w  # NaN check
        return max(min_w, min(max_w, w))

    def clamp_video_box(
        x: float,
        y: float,
        width: float,
        frame_width: float,
        frame_height: float,
        box_height: float,
    ) -> tuple[float, float, float]:
        w = clamp_video_width(width, frame_width)
        h = box_height if box_height > 0 else w * 9 / 16
        max_x = max(0.0, frame_width - w)
        max_y = max(0.0, frame_height - h)
        return (
            max(0.0, min(max_x, x)),
            max(0.0, min(max_y, y)),
            w,
        )

    assert clamp_video_width(80, 800) == 160
    assert clamp_video_width(900, 800) == 640
    assert clamp_video_width(320, 800) == 320
    x, y, w = clamp_video_box(700, 500, 200, 800, 400, 112.5)
    assert w == 200
    assert x == 600
    assert y == 287.5
    x2, y2, _w2 = clamp_video_box(-20, -10, 200, 800, 400, 112.5)
    assert x2 == 0
    assert y2 == 0


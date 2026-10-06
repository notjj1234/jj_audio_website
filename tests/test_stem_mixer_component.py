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


def test_mixer_keeps_playing_when_the_context_suspends():
    text = _mixer_main_ts()
    bind = text[text.find("private bindContextState") : text.find("private rebuildGraphKeepingBuffers")]
    assert "softPauseFromInterrupt" not in bind
    assert "continueAfterInterrupt" in bind
    play = text[text.find("async play()") : text.find("async pause()")]
    assert "this.keepPlaying = true" in play
    assert "startStreamOutput" in play
    pause = text[text.find("async pause()") : text.find("async seek(")]
    assert "this.keepPlaying = false" in pause
    assert "stopStreamOutput" in pause
    hooks = text[text.find("installWakeHooks(): void") : text.find("getDuration()")]
    assert 'addEventListener("focus"' in hooks
    wake = text[text.find("async handleWake()") : text.find("private async continueAfterInterrupt")]
    assert "softPauseFromInterrupt" not in wake
    assert "this.keepPlaying" in wake
    soft = text[
        text.find("engine.setSoftPauseCallback") : text.find("function mediaSessionArtwork")
    ]
    assert "wantPlaying = false" not in soft
    assert "SLEEP_RESUME_HINT" not in soft
    assert "function publishMediaSession" in text
    assert "navigator.mediaSession" in text
    assert 'artist: "Audio Tools"' in text
    assert "hqdefault.jpg" in text
    assert "setActionHandler(\"play\"" in text or 'setActionHandler("play"' in text
    assert "setPositionState" in text
    assert "createMediaStreamDestination" in text
    assert "claimAudioSessionPlayback" in text
    assert 'audioSession.type = "playback"' in text
    ensure = text[text.find("async ensureContext()") : text.find("private ensureMasterBus")]
    assert "if (!this.keepPlaying)" in ensure
    bus = text[text.find("private ensureMasterBus") : text.find("private ensureOutputElement")]
    assert "createMediaStreamDestination" in bus
    assert "this.ctx.destination" not in bus or bus.find("createMediaStreamDestination") < bus.find(
        "this.ctx.destination"
    )


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


def test_mixer_video_dock_and_snaps():
    text = _mixer_main_ts()
    assert 'id="btn-dock-video"' in text
    assert 'data-snap="left"' in text
    assert 'data-snap="right"' in text
    assert 'data-snap="above"' in text
    assert 'data-snap="below"' in text
    assert "function dockedVideoLayout" in text
    assert "function videoSnap" in text
    dock = text[text.find("function dockedVideoLayout") : text.find("let videoLayout")]
    assert "placed: false" in dock
    snap = text[text.find("function videoSnap") : text.find("function dockedVideoLayout")]
    assert 'return "left"' in snap
    handler = text[text.find('id="btn-dock-video"') :]
    assert "dockedVideoLayout(videoLayout)" in handler
    assert "videoLayout.placed = false" in handler
    layout = text[text.find("function applyVideoLayout") : text.find("function trackVideoPointer")]
    docked_at = layout.find("if (!videoLayout.placed)")
    docked = layout[docked_at : layout.find("return;", docked_at)]
    assert "scheduleFrameHeight()" in docked
    render = text[text.find("function renderUI") : text.find("function updateTrackTitleDisplay")]
    assert render.rfind("applyVideoLayout()") < render.rfind("scheduleFrameHeight()")
    assert render.rfind("mountPicture()") < render.rfind("scheduleFrameHeight()")

    def docked_video_layout(layout: dict) -> dict:
        snap_name = layout["snap"] if layout["snap"] in {"right", "above", "below"} else "left"
        return {
            "placed": False,
            "snap": snap_name,
            "width": layout["width"],
            "x": layout["x"],
            "y": layout["y"],
        }

    docked = docked_video_layout(
        {"placed": True, "snap": "right", "width": 240, "x": 12, "y": 8}
    )
    assert docked["placed"] is False
    assert docked["snap"] == "right"
    assert docked["width"] == 240
    unknown = docked_video_layout(
        {"placed": True, "snap": "floating", "width": 180, "x": 1, "y": 2}
    )
    assert unknown["snap"] == "left"
    assert unknown["width"] == 180


def test_mixer_picture_play_starts_stems_after_metadata():
    text = _mixer_main_ts()
    play = text[
        text.find('video.addEventListener("play"') : text.find('video.addEventListener("pause"')
    ]
    assert "video.pause()" not in play
    assert "localPlayFromUs" in play
    assert "startStemsFromPicture()" in play

    start = text[
        text.find("function startStemsFromPicture") : text.find("function playLocalVideo")
    ]
    assert "wantPlaying = true" in start
    assert 'transportPending = "play"' in start
    assert "applyTransport()" in start

    write = text[text.find("function writePictureTo") : text.find("function nudgeYoutubeToAudio")]
    assert "HAVE_METADATA" in write
    assert "readyState < HAVE_METADATA" in write
    assert "loadedmetadata" in write
    assert write.find("readyState < HAVE_METADATA") < write.find("video.currentTime = pictureT")

    local_play = text[text.find("function playLocalVideo") : text.find("function playYoutubeVideo")]
    assert ".catch(" in local_play
    assert "video.pause()" not in local_play

    yt = text[text.find("onStateChange:") : text.find("onError:")]
    assert "pauseVideo()" not in yt
    assert "youtubePlayFromUsUntil" in yt
    assert "startStemsFromPicture()" in yt

    def picture_action(ready_state: int, playing: bool) -> str:
        if ready_state < 1:
            return "wait"
        return "play" if playing else "pause"

    assert picture_action(0, True) == "wait"
    assert picture_action(1, True) == "play"
    assert picture_action(1, False) == "pause"


def test_mixer_local_preview_error_mounts_youtube():
    text = _mixer_main_ts()
    apply = text[text.find("function applyYoutubeArgs") : text.find("const SLEEP_RESUME_HINT")]
    assert 'nextId ? ""' not in apply
    assert "localVideoFailedUrl" in apply
    mount = text[text.find("function mountPicture") : text.find("function applyYoutubeArgs")]
    assert mount.find("mountLocalVideo()") < mount.find("mountYoutubePlayer()")
    local = text[text.find("function mountLocalVideo") : text.find("function mountYoutubePlayer")]
    guard_at = local.find("if (!slot")
    guard = local[guard_at : local.find("{", guard_at)]
    assert "youtubeVideoId" not in guard
    assert 'video.addEventListener("error"' in local
    abandon = text[
        text.find("function abandonUnplayableLocalVideo") : text.find("function mountLocalVideo")
    ]
    assert "localVideoFailedUrl = localVideoUrl" in abandon
    assert "mountYoutubePlayer()" in abandon
    assert "!youtubeVideoId" in abandon


def test_mixer_floating_video_is_an_opaque_panel():
    css = (
        Path(__file__).resolve().parents[1]
        / "ui"
        / "stem_mixer_component"
        / "frontend"
        / "src"
        / "style.css"
    ).read_text(encoding="utf-8")
    placed = css[css.find(".mixer-video-wrap.is-placed {") : css.find(".mixer-video-toolbar {")]
    assert "background: var(--bg)" in placed
    assert "padding:" in placed
    assert "border:" in placed or "box-shadow:" in placed
    assert "z-index: 20" in placed
    assert "overflow: hidden" not in placed
    toolbar = css[
        css.find(".mixer-video-wrap.is-placed .mixer-video-toolbar") : css.find(
            ".mixer-video-wrap.is-placed .mixer-video-resize"
        )
    ]
    assert "z-index: 2" in toolbar
    assert "background: var(--bg)" in toolbar
    picture_at = css.find(".mixer-video-wrap.is-placed .mixer-video {")
    picture = css[picture_at : css.find(".mixer-video-toolbar {", picture_at)]
    assert "overflow: hidden" in picture


def test_mixer_stem_wave_height_when_video_present():
    text = _mixer_main_ts()
    assert "STEM_WAVE_DEFAULT = 52" in text
    assert "STEM_WAVE_MIN = 32" in text
    assert "STEM_WAVE_MAX = 120" in text
    assert "function clampStemWaveHeight" in text
    assert "function applyStemWaveHeight" in text
    assert 'id="btn-resize-stems"' in text
    assert "function bindStemWaveGestures" in text
    assert "pictureIsVisible()" in text
    chrome = text[text.find("function updateYoutubeChrome") : text.find("function mountPicture")]
    assert "applyStemWaveHeight()" in chrome
    apply = text[text.find("function applyStemWaveHeight") : text.find("function presetSoloMap")]
    assert "--stem-wave-height" in apply
    assert "handle.hidden = !pictureIsVisible()" in apply

    def clamp_stem_wave_height(height: float) -> float:
        return max(32.0, min(120.0, height if height == height else 52.0))

    assert clamp_stem_wave_height(20) == 32
    assert clamp_stem_wave_height(200) == 120
    assert clamp_stem_wave_height(64) == 64

    css = (
        Path(__file__).resolve().parents[1]
        / "ui"
        / "stem_mixer_component"
        / "frontend"
        / "src"
        / "style.css"
    ).read_text(encoding="utf-8")
    wave = css[css.find(".waveform-svg {") : css.find(".waveform-svg .wave-baseline")]
    assert "var(--stem-wave-height" in wave
    assert "mixer-stems-resize" in css
    assert "ns-resize" in css


def test_paused_picture_seek_moves_stems_and_ignores_our_echo():
    text = _mixer_main_ts()
    assert "function pictureSeekDecision" in text
    assert "function seekStemsFromPicture" in text
    assert "function applyPictureSeek" in text

    seeked = text[
        text.find('video.addEventListener("seeked"') : text.find("nudgeYoutubeToAudio();")
    ]
    assert "applyPictureSeek(" in seeked
    assert "VIDEO_RESYNC_COOLDOWN_MS" not in seeked
    assert "video.controls = true" in text
    assert "video.muted = true" in text

    sync = text[
        text.find("function syncPictureToStems") : text.find("function abandonUnplayableLocalVideo")
    ]
    assert "applyPictureSeek(" in sync
    assert "startPicturePoll" in text

    apply = text[text.find("function applyPictureSeek") : text.find("function syncPictureToStems")]
    assert "pictureSeekDecision(" in apply
    defer = apply[apply.find('decision === "defer"') : apply.find('decision === "seek-stems"')]
    assert "lastPictureObserved" not in defer
    assert "deferredPictureSec = picture" in defer

    stems = text[text.find("function seekStemsFromPicture") : text.find("function applyPictureSeek")]
    assert "engine.seek(" in stems
    assert "writePictureTo" not in stems
    assert ".play(" not in stems
    assert "startStemsFromPicture" not in stems

    drift = 0.4
    cooldown_ms = 2000
    stable_sec = 0.05

    def picture_time(mixer: float, offset: float) -> float:
        offset = offset if offset > 0 else 0.0
        mixer = mixer if mixer > 0 else 0.0
        return mixer + offset

    def video_needs_seek(audio: float, video: float, now_ms: float, last_ms: float) -> bool:
        if now_ms - last_ms < cooldown_ms:
            return False
        return abs(video - audio) > drift

    def picture_seek_decision(inp: dict) -> str:
        echo_window = inp["now_ms"] - inp["video_sync_at_ms"] < cooldown_ms
        commanded = inp["commanded_picture_sec"]
        near_command = commanded is not None and abs(inp["picture_sec"] - commanded) <= drift
        if inp["sync_origin"] == "audio" or inp["now_ms"] < inp["suppress_until_ms"]:
            return "echo"
        if echo_window and near_command:
            return "echo"
        user_jump = inp["from_seeked_event"]
        if not user_jump and inp["last_picture_sec"] >= 0 and inp["last_mixer_sec"] >= 0:
            picture_moved = inp["picture_sec"] - inp["last_picture_sec"]
            mixer_moved = inp["mixer_sec"] - inp["last_mixer_sec"]
            user_jump = abs(picture_moved - mixer_moved) > drift
        if user_jump:
            if inp["from_seeked_event"]:
                return "seek-stems"
            if echo_window and not near_command:
                expected = picture_time(inp["mixer_sec"], inp["offset_sec"])
                away_from_mixer = abs(inp["picture_sec"] - expected) > drift
                away_from_command = commanded is None or abs(inp["picture_sec"] - commanded) > drift
                deferred = inp["deferred_picture_sec"]
                stable = deferred is not None and abs(inp["picture_sec"] - deferred) <= stable_sec
                if stable and away_from_mixer and away_from_command:
                    return "seek-stems"
                return "defer"
            return "seek-stems"
        if (
            inp["playing"]
            and inp["sync_origin"] != "video"
            and video_needs_seek(
                picture_time(inp["mixer_sec"], inp["offset_sec"]),
                inp["picture_sec"],
                inp["now_ms"],
                inp["video_sync_at_ms"],
            )
        ):
            return "pull-picture"
        return "hold"

    base = {
        "playing": False,
        "sync_origin": None,
        "now_ms": 10_000.0,
        "suppress_until_ms": 0.0,
        "video_sync_at_ms": 0.0,
        "picture_sec": 25.0,
        "mixer_sec": 0.0,
        "offset_sec": 0.0,
        "last_picture_sec": 10.0,
        "last_mixer_sec": 0.0,
        "commanded_picture_sec": None,
        "deferred_picture_sec": None,
        "from_seeked_event": False,
    }
    assert picture_seek_decision(base) == "seek-stems"
    small = dict(base, picture_sec=10.2, mixer_sec=10.0, last_picture_sec=10.0, last_mixer_sec=10.0)
    assert picture_seek_decision(small) == "hold"
    echo = dict(base, sync_origin="audio")
    assert picture_seek_decision(echo) == "echo"
    both = dict(base, picture_sec=15.0, mixer_sec=5.0, last_picture_sec=10.0, last_mixer_sec=0.0)
    assert picture_seek_decision(both) == "hold"
    first = dict(
        base,
        now_ms=500.0,
        video_sync_at_ms=0.0,
        commanded_picture_sec=10.0,
        deferred_picture_sec=None,
    )
    assert picture_seek_decision(first) == "defer"
    stable = dict(first, deferred_picture_sec=25.0)
    assert picture_seek_decision(stable) == "seek-stems"
    drifting = dict(
        base,
        playing=True,
        picture_sec=12.0,
        mixer_sec=0.0,
        last_picture_sec=12.0,
        last_mixer_sec=0.0,
        now_ms=1_000.0,
        video_sync_at_ms=0.0,
    )
    assert picture_seek_decision(drifting) == "hold"
    assert picture_seek_decision(dict(drifting, now_ms=2_500.0)) == "pull-picture"
    section = dict(base, offset_sec=12.5, picture_sec=27.5, last_picture_sec=12.5)
    assert picture_seek_decision(section) == "seek-stems"


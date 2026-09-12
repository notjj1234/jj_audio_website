"""Smoke tests for the waveform region picker Streamlit component packaging."""

from __future__ import annotations

import inspect
from pathlib import Path


def test_region_picker_build_present():
    from ui.region_picker_component import region_picker_build_is_complete

    build = (
        Path(__file__).resolve().parents[1]
        / "ui"
        / "region_picker_component"
        / "frontend"
        / "build"
    )
    assert region_picker_build_is_complete(build), (
        "Region picker frontend is incomplete. Run make region-picker-build "
        "(or npm run build in ui/region_picker_component/frontend)"
    )


def test_region_picker_build_is_complete_rejects_html_without_assets(tmp_path):
    from ui.region_picker_component import region_picker_build_is_complete

    (tmp_path / "index.html").write_text(
        '<script type="module" src="./assets/index-missing.js"></script>',
        encoding="utf-8",
    )
    assert region_picker_build_is_complete(tmp_path) is False


def test_region_picker_import():
    from ui.region_picker_component import component_build_available, region_picker

    assert component_build_available()
    assert callable(region_picker)


def test_region_picker_accepts_bounds_props():
    from ui.region_picker_component import region_picker

    params = inspect.signature(region_picker).parameters
    assert "audio_url" in params
    assert "start_sec" in params
    assert "end_sec" in params
    assert "min_length_sec" in params
    assert "max_hint_sec" in params


def test_region_picker_source_uses_wavesurfer_regions():
    main = (
        Path(__file__).resolve().parents[1]
        / "ui"
        / "region_picker_component"
        / "frontend"
        / "src"
        / "main.ts"
    ).read_text(encoding="utf-8")
    assert "wavesurfer.js" in main
    assert "RegionsPlugin" in main
    assert "startSec" in main
    assert "endSec" in main
    assert "wantPlaying" in main
    assert "playSelection" in main
    assert "resolvePlayableUrl" in main
    assert "REPORT_DEBOUNCE_MS" in main
    assert "dropBlobCache" in main
    assert "createObjectURL" in main


def test_mixer_waveform_uses_bar_rects():
    main = (
        Path(__file__).resolve().parents[1]
        / "ui"
        / "stem_mixer_component"
        / "frontend"
        / "src"
        / "main.ts"
    ).read_text(encoding="utf-8")
    wave = main[main.find("function waveformSeekHtml") : main.find("function escapeHtml")]
    assert "<rect" in wave
    assert "polygon" not in wave
    assert "wave-baseline" in wave
    assert "waveformNorm" in main
    assert "peakPercentile" in main
    assert "peaksFromBuffer" in main
    assert "applyDecodedPeaks" in main
    assert "waveformBarLayout" in main
    assert "silenceEps" not in main
    assert "if (peak <= 0) continue" in wave
    assert "const gap = 1" not in wave
    assert "Math.max(0.5, (width - gap" not in wave
    assert "width / Math.max(1, n)" in main
    assert "i * slot" in wave
    assert 'code !== "Space"' in main or 'e.code !== "Space"' in main
    assert "installWakeHooks" in main
    assert "handleWake" in main
    assert "Tap Play to resume after sleep" in main
    isolate = (
        Path(__file__).resolve().parents[1] / "ui" / "pages" / "isolate.py"
    ).read_text(encoding="utf-8")
    assert "num_points: int = 512" in isolate

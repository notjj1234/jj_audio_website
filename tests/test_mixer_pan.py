"""Stem pan: one law shared by the desktop mixer iframe and the hosted mixer.

The math itself is executed by vitest (`web/src/mixer/pan.test.ts`, run with
`cd web && npm test`). These tests keep the two copies of `pan.ts` from drifting
and pin the hosted wiring that vitest cannot see (markup and CSS).
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP_PAN = ROOT / "ui" / "stem_mixer_component" / "frontend" / "src" / "pan.ts"
HOSTED_PAN = ROOT / "web" / "src" / "mixer" / "pan.ts"
HOSTED_ENGINE = ROOT / "web" / "src" / "mixer" / "engine.ts"
HOSTED_MIXER = ROOT / "web" / "src" / "components" / "StemMixer.tsx"
HOSTED_CSS = ROOT / "web" / "src" / "styles.css"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_desktop_and_hosted_pan_ts_are_identical():
    assert _read(DESKTOP_PAN) == _read(HOSTED_PAN), (
        "pan.ts drifted. It is the one written-down pan law; edit both copies "
        "(ui/stem_mixer_component/frontend/src/pan.ts and web/src/mixer/pan.ts)."
    )
    header = _read(HOSTED_PAN)[:1600]
    assert "ui/stem_mixer_component/frontend/src/pan.ts" in header
    assert "web/src/mixer/pan.ts" in header


def test_hosted_engine_routes_every_stem_through_a_panner_and_pans_the_download():
    engine = _read(HOSTED_ENGINE)
    assert 'import { PAN_DEFAULT, createStemPanner, panToUnit } from "./pan";' in engine
    # One helper builds every stem bus (load, hot rebuild, reattach): gain -> panner -> master.
    assert engine.count("this.addStemBus(") == 3
    assert "gain.connect(panner);" in engine and "panner.connect(this.masterGain!);" in engine
    assert "pan?: Record<string, number>;" in engine
    # Pan survives a context rebuild and resets on a new mix.
    assert engine.count("this.applyPans(this.lastPans);") == 2
    assert "this.lastPans = {};" in engine
    # Gains are untouched by pan.
    assert "gains[id] = audible ? dbToLinear(db) * masterLin : 0;" in engine
    # The download uses the same law, only for panned stems.
    bounce = engine[engine.find("async bounceMix") : engine.find("private clearMediaSession")]
    assert "createStemPanner(offline)" in bounce
    assert "panOf(id) !== 0" in bounce
    assert "anyPanned ? 2 : 1" in bounce


def test_hosted_mixer_has_a_labelled_pan_slider_that_snaps_only_on_drag():
    tsx = _read(HOSTED_MIXER)
    assert 'className="pan-slider"' in tsx
    assert "min={PAN_MIN}" in tsx and "max={PAN_MAX}" in tsx and "step={1}" in tsx
    assert "aria-valuetext={panSpoken(pan)}" in tsx
    assert "{stem.label} pan</span>" in tsx
    assert "{formatPan(pan)}" in tsx
    # Pointer drag snaps to center, keys never do, double-click centers.
    assert "snap: panDragRef.current === stem.id" in tsx
    assert "onKeyDown={endPanDrag}" in tsx
    assert "onDoubleClick={() => setPan(stem.id, PAN_DEFAULT)}" in tsx
    # Pan goes to the engine without touching gains, and the page says what Download does.
    assert "engineRef.current.applyPans(pan);" in tsx
    assert "Download current mix includes your pan." in tsx
    # Mute and solo handlers keep pan by spreading the state they were given.
    toggle_mute = tsx[tsx.find("const toggleMute") : tsx.find("const toggleSolo")]
    assert "...state," in toggle_mute


def test_hosted_pan_css_has_a_44px_target_and_puts_the_value_under_the_slider_when_narrow():
    css = _read(HOSTED_CSS)
    pan_input = css[css.find(".mixer .stem-pan input"):]
    pan_input = pan_input[: pan_input.find("}")]
    assert "min-height: 44px" in pan_input
    pan_val = css[css.find(".mixer .stem-pan .pan-val {"):]
    pan_val = pan_val[: pan_val.find("}")]
    assert "font-size: 0.82rem" in pan_val and "opacity" not in pan_val
    narrow = css[css.find("/* Narrow: the value goes under the slider"):]
    narrow = narrow[: narrow.find(".artifacts")]
    assert "grid-row: 2;" in narrow and "grid-column: 2;" in narrow

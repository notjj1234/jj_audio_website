import { afterEach, describe, expect, it } from "vitest";
import { StemMixerEngine } from "./engine";
import {
  PAN_DEFAULT,
  PAN_DETENT,
  PAN_MAX,
  PAN_MIN,
  clampPan,
  createStemPanner,
  formatPan,
  panMatrix,
  panSpoken,
  panToUnit,
  snapPanToCenter,
} from "./pan";

describe("pan values", () => {
  it("is a whole number from -100 to 100 and anything else is center", () => {
    expect([PAN_MIN, PAN_DEFAULT, PAN_MAX]).toEqual([-100, 0, 100]);
    expect(clampPan(37)).toBe(37);
    expect(clampPan(12.6)).toBe(13);
    expect(clampPan("42")).toBe(42);
    expect(clampPan(250)).toBe(100);
    expect(clampPan(-250)).toBe(-100);
    for (const junk of [undefined, null, "", "left", NaN, Infinity, -Infinity, {}]) {
      expect(clampPan(junk)).toBe(0);
    }
    expect(panToUnit(100)).toBe(1);
    expect(panToUnit(-50)).toBe(-0.5);
    expect(panToUnit(999)).toBe(1);
  });

  it("reads as C / L n / R n on screen and Center / Left n / Right n aloud", () => {
    expect(formatPan(0)).toBe("C");
    expect(formatPan(-30)).toBe("L 30");
    expect(formatPan(30)).toBe("R 30");
    expect(formatPan(-1000)).toBe("L 100");
    expect(panSpoken(0)).toBe("Center");
    expect(panSpoken(-30)).toBe("Left 30");
    expect(panSpoken(30)).toBe("Right 30");
  });

  it("detent snaps close drags to center and leaves everything else alone", () => {
    expect(PAN_DETENT).toBe(4);
    expect(snapPanToCenter(4)).toBe(0);
    expect(snapPanToCenter(-4)).toBe(0);
    expect(snapPanToCenter(5)).toBe(5);
    expect(snapPanToCenter(-5)).toBe(-5);
    expect(snapPanToCenter(-100)).toBe(-100);
  });
});

describe("pan law (Web Audio StereoPannerNode, stereo input)", () => {
  const apply = (pan: number, inL: number, inR: number) => {
    const m = panMatrix(pan);
    return { l: m.ll * inL + m.lr * inR, r: m.rl * inL + m.rr * inR };
  };

  it("center passes the stem through unchanged", () => {
    const m = panMatrix(0);
    expect(m.ll).toBe(1);
    expect(m.lr).toBeCloseTo(0, 12); // cos(pi/2) is 6e-17 in floating point
    expect(m.rl).toBe(0);
    expect(m.rr).toBe(1);
    const out = apply(0, 0.6, 0.3);
    expect(out.l).toBeCloseTo(0.6, 12);
    expect(out.r).toBeCloseTo(0.3, 12);
  });

  it("hard left puts both channels in the left ear, hard right in the right", () => {
    const left = apply(-100, 0.6, 0.3);
    expect(left.l).toBeCloseTo(0.9, 10);
    expect(left.r).toBeCloseTo(0, 10);
    const right = apply(100, 0.6, 0.3);
    expect(right.l).toBeCloseTo(0, 10);
    expect(right.r).toBeCloseTo(0.9, 10);
  });

  it("matches the numbers measured from a real browser StereoPannerNode", () => {
    // OfflineAudioContext, input L=0.6 R=0.3, read in Chromium while writing pan.ts.
    const measured: Array<[number, number, number]> = [
      [-60, 0.84271, 0.17634],
      [-4, 0.61884, 0.29941],
      [4, 0.59882, 0.33767],
      [37, 0.50148, 0.62941],
    ];
    for (const [pan, l, r] of measured) {
      const out = apply(pan, 0.6, 0.3);
      expect(out.l).toBeCloseTo(l, 4);
      expect(out.r).toBeCloseTo(r, 4);
    }
  });

  it("is mirror-symmetric", () => {
    for (const pan of [10, 33, 70, 100]) {
      const a = apply(pan, 0.6, 0.3);
      const b = apply(-pan, 0.3, 0.6);
      expect(b.l).toBeCloseTo(a.r, 10);
      expect(b.r).toBeCloseTo(a.l, 10);
    }
  });
});

type Call = string;

class FakeParam {
  value = 0;
  targets: Array<{ value: number; time: number; tc: number }> = [];
  setTargetAtTime(value: number, time: number, tc: number) {
    this.targets.push({ value, time, tc });
  }
}

function makeCtx(calls: Call[], opts: { panner: boolean }) {
  let n = 0;
  const node = (kind: string) => {
    const id = `${kind}${n++}`;
    return {
      id,
      connect(dest: { id?: string } | string) {
        calls.push(`${id}->${typeof dest === "string" ? dest : (dest.id ?? "?")}`);
        return dest;
      },
      disconnect() {
        calls.push(`${id} x`);
      },
    };
  };
  const ctx: Record<string, unknown> = {
    currentTime: 2,
    destination: "destination",
    createGain: () => ({ ...node("gain"), gain: new FakeParam() }),
  };
  if (opts.panner) {
    ctx.createStereoPanner = () => ({ ...node("panner"), pan: new FakeParam() });
  }
  return ctx as unknown as AudioContext;
}

type EngineInternals = {
  ctx: AudioContext;
  masterGain: { id: string };
  stemIds: string[];
  panners: Map<string, { id: string; pan: FakeParam }>;
  gains: Map<string, { id: string }>;
  addStemBus(ctx: AudioContext, id: string): void;
  lastPans: Record<string, number>;
};

function engineWith(calls: Call[], opts: { panner: boolean }) {
  const engine = new StemMixerEngine();
  const internal = engine as unknown as EngineInternals;
  internal.ctx = makeCtx(calls, opts);
  internal.masterGain = { id: "master" };
  internal.stemIds = ["a", "b"];
  return { engine, internal };
}

describe("engine pan routing", () => {
  it("builds every stem as gain -> panner -> master", () => {
    const calls: Call[] = [];
    const { internal } = engineWith(calls, { panner: true });
    internal.addStemBus(internal.ctx, "a");
    expect(calls).toEqual(["gain0->panner1", "panner1->master"]);
    expect(internal.gains.get("a")?.id).toBe("gain0");
    expect(internal.panners.get("a")?.id).toBe("panner1");
  });

  it("falls back to gain -> master where the browser has no StereoPannerNode", () => {
    const calls: Call[] = [];
    const { engine, internal } = engineWith(calls, { panner: false });
    expect(createStemPanner(internal.ctx)).toBeNull();
    internal.addStemBus(internal.ctx, "a");
    expect(calls).toEqual(["gain0->master"]);
    expect(internal.panners.size).toBe(0);
    expect(() => engine.applyPans({ a: -50 })).not.toThrow();
  });

  it("applyPans smooths each panner to pan/100 and remembers the values", () => {
    const calls: Call[] = [];
    const { engine, internal } = engineWith(calls, { panner: true });
    internal.addStemBus(internal.ctx, "a");
    internal.addStemBus(internal.ctx, "b");
    engine.applyPans({ a: -50, b: 400 });
    expect(internal.panners.get("a")!.pan.targets).toEqual([
      { value: -0.5, time: 2, tc: 0.015 },
    ]);
    expect(internal.panners.get("b")!.pan.targets[0].value).toBe(1);
    expect(internal.lastPans).toEqual({ a: -50, b: 400 });
    // A stem with no entry is centered, not left where it was.
    engine.applyPans({ a: 20 });
    expect(internal.panners.get("b")!.pan.targets[1].value).toBe(0);
  });

  it("a stem bus created after the pan was set starts at that pan", () => {
    const calls: Call[] = [];
    const { engine, internal } = engineWith(calls, { panner: true });
    engine.applyPans({ a: 25 });
    internal.addStemBus(internal.ctx, "a");
    expect(internal.panners.get("a")!.pan.value).toBe(0.25);
  });
});

describe("bounceMix pan", () => {
  const realOffline = (globalThis as { OfflineAudioContext?: unknown }).OfflineAudioContext;
  afterEach(() => {
    (globalThis as { OfflineAudioContext?: unknown }).OfflineAudioContext = realOffline;
  });

  function setup(opts: { channels: number; pans: Record<string, number> }) {
    const calls: Call[] = [];
    const made: { channels: number }[] = [];
    class FakeOffline {
      destination = "destination";
      constructor(channels: number) {
        made.push({ channels });
      }
      createBufferSource() {
        const id = `src${calls.length}`;
        return {
          buffer: null as unknown,
          connect(dest: { id: string }) {
            calls.push(`${id}->${dest.id}`);
          },
          start() {},
        };
      }
      private n = 0;
      createGain() {
        const id = `gain${this.n++}`;
        return {
          id,
          gain: { value: 0 },
          connect(dest: { id?: string } | string) {
            calls.push(`${id}->${typeof dest === "string" ? dest : dest.id}`);
          },
        };
      }
      createStereoPanner() {
        const id = `panner${this.n++}`;
        return {
          id,
          pan: { value: 0 },
          connect(dest: string) {
            calls.push(`${id}->${dest}`);
          },
        };
      }
      async startRendering() {
        return {
          numberOfChannels: made[0].channels,
          sampleRate: 44100,
          length: 4,
          getChannelData: () => new Float32Array(4),
        };
      }
    }
    (globalThis as { OfflineAudioContext?: unknown }).OfflineAudioContext = FakeOffline;

    const engine = new StemMixerEngine();
    const internal = engine as unknown as {
      buffers: Map<string, { duration: number; sampleRate: number; numberOfChannels: number }>;
      stemIds: string[];
      duration: number;
    };
    internal.stemIds = ["a", "b"];
    internal.duration = 1;
    internal.buffers = new Map(
      ["a", "b"].map((id) => [
        id,
        { duration: 1, sampleRate: 44100, numberOfChannels: opts.channels },
      ])
    );
    const state = {
      volumesDb: { a: 0, b: 0 },
      muted: {},
      soloed: {},
      pan: opts.pans,
    };
    return { engine, state, calls, made };
  }

  it("a mix with every stem centered renders exactly as before: no panner, mono stays mono", async () => {
    const { engine, state, calls, made } = setup({ channels: 1, pans: { a: 0, b: 0 } });
    await engine.bounceMix(state);
    expect(made[0].channels).toBe(1);
    expect(calls.filter((c) => c.includes("panner"))).toEqual([]);
    expect(calls.filter((c) => c.endsWith("->destination")).length).toBe(2);
  });

  it("only panned stems get a panner, with the live pan value", async () => {
    const { engine, state, calls } = setup({ channels: 2, pans: { a: -50, b: 0 } });
    await engine.bounceMix(state);
    expect(calls).toContain("gain0->panner1");
    expect(calls).toContain("panner1->destination");
    // Stem b is centered: straight to the destination.
    expect(calls.filter((c) => c.endsWith("->destination")).length).toBe(2);
    expect(calls.filter((c) => c.includes("panner")).length).toBe(2);
  });

  it("a panned mono mix renders in stereo so pan has two ears to land in", async () => {
    const { engine, state, made } = setup({ channels: 1, pans: { a: 100 } });
    await engine.bounceMix(state);
    expect(made[0].channels).toBe(2);
  });

  it("a muted stem is left out whatever its pan", async () => {
    const { engine, state, calls } = setup({ channels: 2, pans: { a: -100, b: 100 } });
    await engine.bounceMix({ ...state, muted: { a: true } });
    expect(calls.filter((c) => c.includes("panner")).length).toBe(2); // only b's bus
    expect(calls.filter((c) => c.endsWith("->destination")).length).toBe(1);
  });
});

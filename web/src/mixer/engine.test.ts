import { describe, expect, it } from "vitest";
import {
  allMuted,
  anySoloed,
  clearSolo,
  dbToLinear,
  effectiveGains,
  ensureAudioContext,
  isAudible,
  resetMuteSolo,
  setAllMuted,
  StemMixerEngine,
  DB_MIN,
} from "./engine";

describe("mixer helpers", () => {
  it("maps silence floor to zero gain", () => {
    expect(dbToLinear(DB_MIN)).toBe(0);
  });

  it("clamps volumes to the -25 / +25 slider range", () => {
    const high = effectiveGains(["a"], {
      volumesDb: { a: 40 },
      muted: {},
      soloed: {},
    });
    expect(high.a).toBeCloseTo(Math.pow(10, 25 / 20));
    const low = effectiveGains(["a"], {
      volumesDb: { a: -80 },
      muted: {},
      soloed: {},
    });
    expect(low.a).toBe(0);
  });

  it("applies mute and solo", () => {
    const gains = effectiveGains(["a", "b"], {
      volumesDb: { a: 0, b: 0 },
      muted: { a: true, b: false },
      soloed: { a: false, b: false },
    });
    expect(gains.a).toBe(0);
    expect(gains.b).toBeCloseTo(1);

    const solo = effectiveGains(["a", "b"], {
      volumesDb: { a: 0, b: 0 },
      muted: {},
      soloed: { a: true, b: false },
    });
    expect(solo.a).toBeCloseTo(1);
    expect(solo.b).toBe(0);
  });

  it("scales stem gains by master volume", () => {
    const gains = effectiveGains(["a"], {
      volumesDb: { a: 0 },
      muted: {},
      soloed: {},
      masterVolumeDb: 6,
    });
    expect(gains.a).toBeCloseTo(Math.pow(10, 6 / 20));
  });

  it("solo overrides an all-muted mix", () => {
    const ids = ["a", "b", "c"];
    const state = {
      volumesDb: { a: 0, b: 0, c: 0 },
      muted: { a: true, b: true, c: true },
      soloed: { b: true },
    };
    expect(allMuted(ids, state)).toBe(true);
    expect(anySoloed(ids, state)).toBe(true);
    const gains = effectiveGains(ids, state);
    expect(gains.a).toBe(0);
    expect(gains.b).toBeCloseTo(1);
    expect(gains.c).toBe(0);
    expect(isAudible("b", ids, state)).toBe(true);
    expect(isAudible("a", ids, state)).toBe(false);
  });

  it("setAllMuted and clearSolo build new state without mutating", () => {
    const ids = ["a", "b"];
    const base = {
      volumesDb: { a: 0, b: 0 },
      muted: { a: false, b: false },
      soloed: { a: true },
    };
    const muted = setAllMuted(ids, base, true);
    expect(muted.muted).toEqual({ a: true, b: true });
    expect(base.muted).toEqual({ a: false, b: false });
    expect(allMuted(ids, muted)).toBe(true);

    const cleared = clearSolo(base);
    expect(cleared.soloed).toEqual({});
    expect(base.soloed).toEqual({ a: true });

    const reset = resetMuteSolo(ids, {
      ...base,
      muted: { a: true, b: true },
      soloed: { a: true, b: false },
    });
    expect(reset.muted).toEqual({ a: false, b: false });
    expect(reset.soloed).toEqual({ a: false, b: false });
    expect(reset.volumesDb).toEqual({ a: 0, b: 0 });

    const withClick = resetMuteSolo(["vocals", "metronome"], {
      volumesDb: { vocals: 0, metronome: 0 },
      muted: { vocals: true, metronome: false },
      soloed: {},
    });
    expect(withClick.muted).toEqual({ vocals: false, metronome: true });
  });

  it("ensureAudioContext resumes suspended contexts", async () => {
    class FakeCtx {
      state: AudioContextState = "suspended";
      resume = async () => {
        this.state = "running";
      };
    }
    const ctx = (await ensureAudioContext(new FakeCtx() as unknown as AudioContext)) as unknown as FakeCtx;
    expect(ctx.state).toBe("running");
  });

  it("ensureAudioContext replaces a closed context", async () => {
    class ClosedCtx {
      state: AudioContextState = "closed";
      resume = async () => {
        /* */
      };
    }
    const RealAudioContext = globalThis.AudioContext;
    class FreshCtx {
      state: AudioContextState = "suspended";
      resume = async () => {
        this.state = "running";
      };
      createGain() {
        return {
          gain: { value: 1, setTargetAtTime() {} },
          connect() {
            return this;
          },
          disconnect() {},
        };
      }
      createDynamicsCompressor() {
        return {
          threshold: { value: 0 },
          knee: { value: 0 },
          ratio: { value: 0 },
          attack: { value: 0 },
          release: { value: 0 },
          connect() {
            return this;
          },
        };
      }
      get destination() {
        return {};
      }
    }
    (globalThis as unknown as { AudioContext: unknown }).AudioContext = FreshCtx;
    try {
      const next = await ensureAudioContext(new ClosedCtx() as unknown as AudioContext);
      expect(next).toBeInstanceOf(FreshCtx);
    } finally {
      (globalThis as unknown as { AudioContext: unknown }).AudioContext = RealAudioContext;
    }
  });

  it("play restarts when playing flag is stale with no sources", async () => {
    class FakeParam {
      value = 0;
      setTargetAtTime() {}
    }
    class FakeNode {
      constructor(readonly kind: string) {}
      connect() {
        return this;
      }
      disconnect() {}
    }
    class FakeGain extends FakeNode {
      gain = new FakeParam();
      constructor() {
        super("gain");
      }
    }
    class FakeCompressor extends FakeNode {
      threshold = new FakeParam();
      knee = new FakeParam();
      ratio = new FakeParam();
      attack = new FakeParam();
      release = new FakeParam();
      constructor() {
        super("compressor");
      }
    }
    class FakeSource extends FakeNode {
      buffer: unknown = null;
      onended: (() => void) | null = null;
      start() {}
      stop() {}
      constructor() {
        super("source");
      }
    }
    class FakeCtx {
      state: AudioContextState = "running";
      currentTime = 1;
      destination = "destination";
      resume = async () => {
        this.state = "running";
      };
      createGain = () => new FakeGain();
      createDynamicsCompressor = () => new FakeCompressor();
      createBufferSource = () => new FakeSource();
    }

    const engine = new StemMixerEngine();
    const fake = new FakeCtx();
    const internal = engine as unknown as {
      ctx: FakeCtx;
      playing: boolean;
      sources: Map<string, FakeSource>;
      buffers: Map<string, { duration: number }>;
      gains: Map<string, FakeGain>;
      stemIds: string[];
      duration: number;
      offset: number;
      masterGain: FakeGain | null;
      limiter: FakeCompressor | null;
    };
    internal.ctx = fake;
    internal.playing = true;
    internal.sources = new Map();
    internal.stemIds = ["a"];
    internal.duration = 10;
    internal.offset = 2;
    internal.buffers = new Map([["a", { duration: 10 }]]);
    internal.gains = new Map([["a", new FakeGain()]]);
    internal.masterGain = new FakeGain();
    internal.limiter = new FakeCompressor();

    await engine.play();
    expect(internal.playing).toBe(true);
    expect(internal.sources.size).toBe(1);
  });

  it("wires a master DynamicsCompressor near −1 dBTP for solo peaks", async () => {
    const connected: string[] = [];
    class FakeParam {
      value = 0;
    }
    class FakeNode {
      constructor(readonly kind: string) {}
      connect(dest: FakeNode | string) {
        connected.push(`${this.kind}->${typeof dest === "string" ? dest : dest.kind}`);
        return dest;
      }
    }
    class FakeCompressor extends FakeNode {
      threshold = new FakeParam();
      knee = new FakeParam();
      ratio = new FakeParam();
      attack = new FakeParam();
      release = new FakeParam();
      constructor() {
        super("compressor");
      }
    }
    class FakeGain extends FakeNode {
      gain = new FakeParam();
      constructor() {
        super("gain");
        this.gain.value = 1;
      }
    }
    class FakeCtx {
      state: AudioContextState = "running";
      destination = "destination";
      resume = async () => {
        this.state = "running";
      };
      createGain = () => new FakeGain();
      createDynamicsCompressor = () => new FakeCompressor();
    }

    const engine = new StemMixerEngine();
    const fake = new FakeCtx();
    // Inject context the same way ensureContext would after a gesture.
    (engine as unknown as { ctx: FakeCtx }).ctx = fake;
    await engine.ensureContext();

    const limiter = (engine as unknown as { limiter: FakeCompressor }).limiter;
    const master = (engine as unknown as { masterGain: FakeGain }).masterGain;
    expect(master).toBeTruthy();
    expect(limiter).toBeTruthy();
    expect(limiter.threshold.value).toBe(-1);
    expect(limiter.ratio.value).toBe(20);
    expect(connected).toContain("gain->compressor");
    expect(connected).toContain("compressor->destination");
  });
});

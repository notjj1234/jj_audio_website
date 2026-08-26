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

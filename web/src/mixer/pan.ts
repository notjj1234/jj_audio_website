/**
 * Stem pan: one law, written down once.
 *
 * Range: whole numbers from -100 (hard left) through 0 (center) to +100 (hard right).
 *
 * Law: the Web Audio `StereoPannerNode` (equal-power) fed with the stem's two
 * channels, where `unit = pan / 100`:
 *
 *   unit <= 0:  x = unit + 1;  outL = inL + inR * cos(x * pi/2);  outR = inR * sin(x * pi/2)
 *   unit  > 0:  x = unit;      outL = inL * cos(x * pi/2);        outR = inR + inL * sin(x * pi/2)
 *
 * So center passes the stem through unchanged, hard left puts both channels in
 * the left ear, and hard right puts both in the right ear. Pan does not change
 * stem volume, mute, solo, or the system volume.
 *
 * `panMatrix` is the same law as plain math. The engines use the node itself;
 * the tests pin the matrix so these words and the numbers cannot drift.
 *
 * Kept identical in `ui/stem_mixer_component/frontend/src/pan.ts` and
 * `web/src/mixer/pan.ts` (a pytest compares the two files). Edit both.
 */

export const PAN_MIN = -100;
export const PAN_MAX = 100;
export const PAN_DEFAULT = 0;
/** A mouse drag within this many steps of center snaps to center. Keys never snap. */
export const PAN_DETENT = 4;

/** Whole number in [-100, 100]. Anything that is not a number is center. */
export function clampPan(value: unknown): number {
  const n = Number(value);
  if (!Number.isFinite(n)) return PAN_DEFAULT;
  return Math.max(PAN_MIN, Math.min(PAN_MAX, Math.round(n)));
}

/** Value for `StereoPannerNode.pan` (-1 .. 1). */
export function panToUnit(pan: number): number {
  return clampPan(pan) / 100;
}

/** Short visible readout: "C", "L 30", "R 30". */
export function formatPan(pan: number): string {
  const p = clampPan(pan);
  if (p === 0) return "C";
  return p < 0 ? `L ${-p}` : `R ${p}`;
}

/** Spoken value for screen readers: "Center", "Left 30", "Right 30". */
export function panSpoken(pan: number): string {
  const p = clampPan(pan);
  if (p === 0) return "Center";
  return p < 0 ? `Left ${-p}` : `Right ${p}`;
}

/** Pointer drags land on center when they get close to it. */
export function snapPanToCenter(pan: number, detent: number = PAN_DETENT): number {
  const p = clampPan(pan);
  return Math.abs(p) <= detent ? PAN_DEFAULT : p;
}

/** The law above: out = [[ll, lr], [rl, rr]] * [inL, inR]. */
export function panMatrix(pan: number): { ll: number; lr: number; rl: number; rr: number } {
  const unit = panToUnit(pan);
  if (unit <= 0) {
    const x = unit + 1;
    return { ll: 1, lr: Math.cos((x * Math.PI) / 2), rl: 0, rr: Math.sin((x * Math.PI) / 2) };
  }
  return {
    ll: Math.cos((unit * Math.PI) / 2),
    lr: 0,
    rl: Math.sin((unit * Math.PI) / 2),
    rr: 1,
  };
}

/** Null where the browser has no StereoPannerNode; the stem then stays centered. */
export function createStemPanner(ctx: BaseAudioContext): StereoPannerNode | null {
  return typeof ctx.createStereoPanner === "function" ? ctx.createStereoPanner() : null;
}

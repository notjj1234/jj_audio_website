/** Practice tempo / key clamps shared by the desktop mixer UI and engine. */

export const PRACTICE_RATE_MIN = 0.5;
export const PRACTICE_RATE_MAX = 1.5;
export const PRACTICE_RATE_DEFAULT = 1;
export const PRACTICE_RATE_STEP = 0.05;

export const PRACTICE_KEY_MIN = -6;
export const PRACTICE_KEY_MAX = 6;
export const PRACTICE_KEY_DEFAULT = 0;

export const PRACTICE_STORAGE_KEY = "att-mixer-practice";

export type PracticeSettings = {
  rate: number;
  semitones: number;
};

export function clampPracticeRate(value: number): number {
  if (!Number.isFinite(value)) return PRACTICE_RATE_DEFAULT;
  const stepped = Math.round(value / PRACTICE_RATE_STEP) * PRACTICE_RATE_STEP;
  return Math.max(
    PRACTICE_RATE_MIN,
    Math.min(PRACTICE_RATE_MAX, Number(stepped.toFixed(2)))
  );
}

export function clampPracticeSemitones(value: number): number {
  if (!Number.isFinite(value)) return PRACTICE_KEY_DEFAULT;
  return Math.max(
    PRACTICE_KEY_MIN,
    Math.min(PRACTICE_KEY_MAX, Math.round(value))
  );
}

export function formatPracticeSpeedLabel(rate: number): string {
  return `Speed ${clampPracticeRate(rate).toFixed(2)}×`;
}

export function formatPracticeKeyLabel(semitones: number): string {
  const n = clampPracticeSemitones(semitones);
  if (n > 0) return `Key +${n}`;
  return `Key ${n}`;
}

export function loadPracticeSettings(): PracticeSettings {
  try {
    const raw = sessionStorage.getItem(PRACTICE_STORAGE_KEY);
    if (!raw) {
      return { rate: PRACTICE_RATE_DEFAULT, semitones: PRACTICE_KEY_DEFAULT };
    }
    const data = JSON.parse(raw) as Partial<PracticeSettings>;
    return {
      rate: clampPracticeRate(Number(data.rate)),
      semitones: clampPracticeSemitones(Number(data.semitones)),
    };
  } catch {
    return { rate: PRACTICE_RATE_DEFAULT, semitones: PRACTICE_KEY_DEFAULT };
  }
}

export function savePracticeSettings(settings: PracticeSettings): void {
  try {
    sessionStorage.setItem(
      PRACTICE_STORAGE_KEY,
      JSON.stringify({
        rate: clampPracticeRate(settings.rate),
        semitones: clampPracticeSemitones(settings.semitones),
      })
    );
  } catch {
    /* private mode / quota */
  }
}

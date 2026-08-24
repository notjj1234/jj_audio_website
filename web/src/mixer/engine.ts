/** Standalone Web Audio stem mixer (ported from Streamlit component). */

export const DB_MIN = -60;
export const DB_MAX = 24;
export const DB_DEFAULT = 0;

export type StemInfo = { id: string; label: string; url: string };

export type MixerState = {
  volumesDb: Record<string, number>;
  muted: Record<string, boolean>;
  soloed: Record<string, boolean>;
};

export function dbToLinear(db: number): number {
  if (db <= DB_MIN) return 0;
  return Math.pow(10, db / 20);
}

export function effectiveGains(
  stemIds: string[],
  state: MixerState
): Record<string, number> {
  const anySolo = stemIds.some((id) => state.soloed[id]);
  const gains: Record<string, number> = {};
  for (const id of stemIds) {
    const db = Math.max(DB_MIN, Math.min(DB_MAX, state.volumesDb[id] ?? DB_DEFAULT));
    // Solo always wins: a soloed track is audible even if every track is muted.
    const audible = anySolo ? !!state.soloed[id] : !state.muted[id];
    gains[id] = audible ? dbToLinear(db) : 0;
  }
  return gains;
}

export function allMuted(stemIds: string[], state: MixerState): boolean {
  return stemIds.length > 0 && stemIds.every((id) => !!state.muted[id]);
}

export function anySoloed(stemIds: string[], state: MixerState): boolean {
  return stemIds.some((id) => !!state.soloed[id]);
}

/** Whether a stem will actually produce sound given the full mixer state. */
export function isAudible(
  stemId: string,
  stemIds: string[],
  state: MixerState
): boolean {
  const anySolo = anySoloed(stemIds, state);
  return anySolo ? !!state.soloed[stemId] : !state.muted[stemId];
}

export function setAllMuted(
  stemIds: string[],
  state: MixerState,
  muted: boolean
): MixerState {
  const next: Record<string, boolean> = { ...state.muted };
  for (const id of stemIds) next[id] = muted;
  return { ...state, muted: next };
}

export function clearSolo(state: MixerState): MixerState {
  return { ...state, soloed: {} };
}

/** Clear all mute and solo flags (volumes unchanged). */
export function resetMuteSolo(stemIds: string[], state: MixerState): MixerState {
  const muted: Record<string, boolean> = {};
  const soloed: Record<string, boolean> = {};
  for (const id of stemIds) {
    muted[id] = false;
    soloed[id] = false;
  }
  return { ...state, muted, soloed };
}

/** Create/resume AudioContext only on user gesture (mobile-safe). */
export async function ensureAudioContext(
  existing: AudioContext | null
): Promise<AudioContext> {
  const ctx = existing ?? new AudioContext();
  if (ctx.state === "suspended") {
    await ctx.resume();
  }
  return ctx;
}

export class StemMixerEngine {
  private ctx: AudioContext | null = null;
  private buffers = new Map<string, AudioBuffer>();
  private gains = new Map<string, GainNode>();
  private sources = new Map<string, AudioBufferSourceNode>();
  private stemIds: string[] = [];
  private playing = false;
  private startedAt = 0;
  private offset = 0;
  private duration = 0;
  private onTimeUpdate: ((t: number, dur: number, playing: boolean) => void) | null =
    null;
  private raf = 0;

  setTimeCallback(cb: (t: number, dur: number, playing: boolean) => void): void {
    this.onTimeUpdate = cb;
  }

  getDuration(): number {
    return this.duration;
  }

  isPlaying(): boolean {
    return this.playing;
  }

  currentTime(): number {
    if (!this.ctx) return this.offset;
    if (!this.playing) return this.offset;
    return Math.min(this.duration, this.offset + (this.ctx.currentTime - this.startedAt));
  }

  async ensureContext(): Promise<AudioContext> {
    this.ctx = await ensureAudioContext(this.ctx);
    return this.ctx;
  }

  async loadStems(
    stems: StemInfo[],
    onProgress: (loaded: number, total: number, message: string) => void,
    options?: { createContext?: boolean }
  ): Promise<{ errors: string[] }> {
    await this.stopSources(false);
    this.buffers.clear();
    this.gains.clear();
    this.sources.clear();
    this.stemIds = stems.map((s) => s.id);
    this.offset = 0;
    this.playing = false;
    this.duration = 0;

    // Decode without starting playback; create context lazily unless asked.
    // Some browsers need a context to decode — create but don't resume until Play.
    if (!this.ctx && (options?.createContext ?? true)) {
      this.ctx = new AudioContext();
    }
    if (!this.ctx) {
      return { errors: ["AudioContext unavailable"] };
    }

    const errors: string[] = [];
    let loaded = 0;
    const total = stems.length;

    for (const stem of stems) {
      onProgress(loaded, total, `Loading ${stem.label}…`);
      try {
        const res = await fetch(stem.url);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const arr = await res.arrayBuffer();
        const buf = await this.ctx.decodeAudioData(arr.slice(0));
        this.buffers.set(stem.id, buf);
        this.duration = Math.max(this.duration, buf.duration);
        const gain = this.ctx.createGain();
        gain.connect(this.ctx.destination);
        this.gains.set(stem.id, gain);
      } catch (e) {
        errors.push(`${stem.label}: ${e instanceof Error ? e.message : String(e)}`);
      }
      loaded += 1;
      onProgress(loaded, total, `Loaded ${loaded}/${total}`);
    }

    this.applyGains(
      effectiveGains(this.stemIds, {
        volumesDb: Object.fromEntries(this.stemIds.map((id) => [id, DB_DEFAULT])),
        muted: {},
        soloed: {},
      })
    );
    this.tick();
    return { errors };
  }

  applyGains(gains: Record<string, number>): void {
    for (const id of this.stemIds) {
      const node = this.gains.get(id);
      if (!node || !this.ctx) continue;
      const g = gains[id] ?? 0;
      node.gain.setTargetAtTime(g, this.ctx.currentTime, 0.015);
    }
  }

  private async stopSources(preserveOffset: boolean): Promise<void> {
    if (preserveOffset && this.playing && this.ctx) {
      this.offset = this.currentTime();
    }
    for (const src of this.sources.values()) {
      try {
        src.onended = null;
        src.stop();
      } catch {
        /* already stopped */
      }
      try {
        src.disconnect();
      } catch {
        /* */
      }
    }
    this.sources.clear();
    this.playing = false;
    cancelAnimationFrame(this.raf);
  }

  private startSources(offset: number): void {
    if (!this.ctx) return;
    const startAt = this.ctx.currentTime + 0.03;
    this.startedAt = startAt;
    this.offset = offset;
    this.playing = true;

    for (const id of this.stemIds) {
      const buf = this.buffers.get(id);
      const gain = this.gains.get(id);
      if (!buf || !gain) continue;
      if (offset >= buf.duration) continue;
      const src = this.ctx.createBufferSource();
      src.buffer = buf;
      src.connect(gain);
      src.start(startAt, offset);
      this.sources.set(id, src);
    }
    this.tick();
  }

  async play(): Promise<void> {
    await this.ensureContext();
    if (this.playing) return;
    if (this.offset >= this.duration) this.offset = 0;
    this.startSources(this.offset);
  }

  async pause(): Promise<void> {
    await this.stopSources(true);
    this.tick();
  }

  async seek(seconds: number): Promise<void> {
    const t = Math.max(0, Math.min(this.duration, seconds));
    const wasPlaying = this.playing;
    await this.stopSources(false);
    this.offset = t;
    if (wasPlaying) {
      this.startSources(this.offset);
    } else {
      this.tick();
    }
  }

  async restart(): Promise<void> {
    await this.seek(0);
    await this.play();
  }

  private tick = (): void => {
    const t = this.currentTime();
    if (this.playing && t >= this.duration - 0.02) {
      void this.stopSources(false);
      this.offset = this.duration;
    }
    this.onTimeUpdate?.(this.currentTime(), this.duration, this.playing);
    if (this.playing) {
      this.raf = requestAnimationFrame(this.tick);
    }
  };
}

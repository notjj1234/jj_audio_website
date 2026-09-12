/** Standalone Web Audio stem mixer (ported from Streamlit component). */

export const DB_MIN = -25;
export const DB_MAX = 25;
export const DB_DEFAULT = 0;

export type StemInfo = { id: string; label: string; url: string };

export type MixerState = {
  volumesDb: Record<string, number>;
  muted: Record<string, boolean>;
  soloed: Record<string, boolean>;
  masterVolumeDb?: number;
};

function clampDb(db: number): number {
  return Math.max(DB_MIN, Math.min(DB_MAX, db));
}

export function dbToLinear(db: number): number {
  if (db <= DB_MIN) return 0;
  return Math.pow(10, db / 20);
}

export function effectiveGains(
  stemIds: string[],
  state: MixerState
): Record<string, number> {
  const anySolo = stemIds.some((id) => state.soloed[id]);
  const masterLin = dbToLinear(clampDb(state.masterVolumeDb ?? DB_DEFAULT));
  const gains: Record<string, number> = {};
  for (const id of stemIds) {
    const db = clampDb(state.volumesDb[id] ?? DB_DEFAULT);
    // Solo always wins: a soloed track is audible even if every track is muted.
    const audible = anySolo ? !!state.soloed[id] : !state.muted[id];
    gains[id] = audible ? dbToLinear(db) * masterLin : 0;
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
  if (!existing || existing.state === "closed") {
    return new AudioContext();
  }
  const state = existing.state as string;
  if (state === "suspended" || state === "interrupted") {
    try {
      await existing.resume();
    } catch {
      return new AudioContext();
    }
  }
  if (existing.state === "closed") {
    return new AudioContext();
  }
  return existing;
}

export class StemMixerEngine {
  private ctx: AudioContext | null = null;
  private buffers = new Map<string, AudioBuffer>();
  private gains = new Map<string, GainNode>();
  private sources = new Map<string, AudioBufferSourceNode>();
  private masterGain: GainNode | null = null;
  private limiter: DynamicsCompressorNode | null = null;
  private stemIds: string[] = [];
  private playing = false;
  private startedAt = 0;
  private offset = 0;
  private duration = 0;
  private lastGains: Record<string, number> = {};
  private onTimeUpdate: ((t: number, dur: number, playing: boolean) => void) | null =
    null;
  private onSoftPause: (() => void) | null = null;
  private raf = 0;
  private wakeHooked = false;

  setTimeCallback(cb: (t: number, dur: number, playing: boolean) => void): void {
    this.onTimeUpdate = cb;
  }

  setSoftPauseCallback(cb: () => void): void {
    this.onSoftPause = cb;
  }

  /** Soft-pause + zombie/closed recovery after sleep/idle. No auto-resume. */
  installWakeHooks(): void {
    if (this.wakeHooked || typeof window === "undefined") return;
    this.wakeHooked = true;
    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "visible") {
        void this.handleWake();
      } else if (this.playing) {
        void this.softPauseFromInterrupt();
      }
    });
    window.addEventListener("pageshow", () => {
      void this.handleWake();
    });
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
    const next = await ensureAudioContext(this.ctx);
    if (next !== this.ctx) {
      this.ctx = next;
      this.masterGain = null;
      this.limiter = null;
      this.reattachGainsToBus();
    } else {
      this.ctx = next;
    }
    this.ensureMasterBus();
    this.bindContextState();
    return this.ctx;
  }

  private ensureMasterBus(): void {
    if (!this.ctx) return;
    if (this.masterGain && this.limiter) return;
    this.masterGain = this.ctx.createGain();
    this.masterGain.gain.value = 1;
    this.limiter = this.ctx.createDynamicsCompressor();
    this.limiter.threshold.value = -1;
    this.limiter.knee.value = 0;
    this.limiter.ratio.value = 20;
    this.limiter.attack.value = 0.003;
    this.limiter.release.value = 0.1;
    this.masterGain.connect(this.limiter);
    this.limiter.connect(this.ctx.destination);
  }

  private bindContextState(): void {
    if (!this.ctx) return;
    this.ctx.onstatechange = () => {
      const st = this.ctx?.state as string | undefined;
      if (st === "interrupted" || st === "closed" || st === "suspended") {
        if (this.playing) {
          void this.softPauseFromInterrupt();
        }
      }
    };
  }

  private reattachGainsToBus(): void {
    if (!this.ctx) return;
    this.ensureMasterBus();
    for (const gain of this.gains.values()) {
      try {
        gain.disconnect();
      } catch {
        /* */
      }
    }
    this.gains.clear();
    for (const id of this.stemIds) {
      if (!this.buffers.has(id)) continue;
      const gain = this.ctx.createGain();
      gain.connect(this.masterGain!);
      this.gains.set(id, gain);
    }
    this.applyGains(this.lastGains);
  }

  private rebuildGraphKeepingBuffers(): void {
    const savedOffset = this.playing && this.ctx ? this.currentTime() : this.offset;
    for (const src of this.sources.values()) {
      try {
        src.onended = null;
        src.stop();
      } catch {
        /* */
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
    for (const gain of this.gains.values()) {
      try {
        gain.disconnect();
      } catch {
        /* */
      }
    }
    this.gains.clear();
    this.masterGain = null;
    this.limiter = null;
    const old = this.ctx;
    this.ctx = null;
    if (old) {
      try {
        void old.close();
      } catch {
        /* */
      }
    }
    this.ctx = new AudioContext();
    this.ensureMasterBus();
    this.bindContextState();
    for (const id of this.stemIds) {
      if (!this.buffers.has(id)) continue;
      const gain = this.ctx.createGain();
      gain.connect(this.masterGain!);
      this.gains.set(id, gain);
    }
    this.offset = savedOffset;
    this.applyGains(this.lastGains);
  }

  private async softPauseFromInterrupt(): Promise<void> {
    await this.stopSources(true);
    this.tick();
    this.onSoftPause?.();
  }

  private async contextLooksZombie(): Promise<boolean> {
    if (!this.ctx || this.ctx.state !== "running") return false;
    const t0 = this.ctx.currentTime;
    await new Promise((r) => window.setTimeout(r, 150));
    if (!this.ctx || this.ctx.state !== "running") return false;
    return this.ctx.currentTime === t0;
  }

  async handleWake(): Promise<void> {
    if (this.playing) {
      await this.softPauseFromInterrupt();
    }
    if (!this.ctx) return;
    if (this.ctx.state === "closed") {
      this.rebuildGraphKeepingBuffers();
      return;
    }
    if (await this.contextLooksZombie()) {
      this.rebuildGraphKeepingBuffers();
    }
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
    if ((!this.ctx || this.ctx.state === "closed") && (options?.createContext ?? true)) {
      this.ctx = new AudioContext();
      this.masterGain = null;
      this.limiter = null;
    }
    if (!this.ctx) {
      return { errors: ["AudioContext unavailable"] };
    }
    this.ensureMasterBus();
    this.bindContextState();

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
        gain.connect(this.masterGain!);
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
        masterVolumeDb: DB_DEFAULT,
      })
    );
    this.tick();
    return { errors };
  }

  applyGains(gains: Record<string, number>): void {
    this.lastGains = { ...gains };
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
    if (this.playing) {
      const healthy = this.ctx?.state === "running" && this.sources.size > 0;
      if (healthy) return;
      await this.stopSources(true);
    }
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

  async bounceMix(state: MixerState): Promise<Blob> {
    if (this.buffers.size === 0 || this.stemIds.length === 0) {
      throw new Error("No stems loaded");
    }
    const Offline =
      typeof OfflineAudioContext !== "undefined" ? OfflineAudioContext : undefined;
    if (!Offline) {
      throw new Error("Mix download is not available in this browser");
    }
    const sampleRate = [...this.buffers.values()][0]?.sampleRate ?? 44100;
    const duration = this.duration || Math.max(
      ...[...this.buffers.values()].map((b) => b.duration),
      0
    );
    if (!(duration > 0)) {
      throw new Error("Stems have no audio");
    }
    const channels = Math.max(
      1,
      ...[...this.buffers.values()].map((b) => b.numberOfChannels)
    );
    const frameCount = Math.max(1, Math.ceil(duration * sampleRate));
    const offline = new Offline(channels, frameCount, sampleRate);
    const gains = effectiveGains(this.stemIds, state);
    for (const id of this.stemIds) {
      const buf = this.buffers.get(id);
      const gLin = gains[id] ?? 0;
      if (!buf || gLin <= 0) continue;
      const src = offline.createBufferSource();
      src.buffer = buf;
      const gain = offline.createGain();
      gain.gain.value = gLin;
      src.connect(gain);
      gain.connect(offline.destination);
      src.start(0);
    }
    const rendered = await offline.startRendering();
    return audioBufferToWav(rendered);
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

export function audioBufferToWav(buffer: AudioBuffer): Blob {
  const numCh = buffer.numberOfChannels;
  const sr = buffer.sampleRate;
  const len = buffer.length;
  const dataLen = len * numCh * 2;
  const out = new ArrayBuffer(44 + dataLen);
  const view = new DataView(out);
  const writeStr = (off: number, s: string) => {
    for (let i = 0; i < s.length; i++) view.setUint8(off + i, s.charCodeAt(i));
  };
  writeStr(0, "RIFF");
  view.setUint32(4, 36 + dataLen, true);
  writeStr(8, "WAVE");
  writeStr(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, numCh, true);
  view.setUint32(24, sr, true);
  view.setUint32(28, sr * numCh * 2, true);
  view.setUint16(32, numCh * 2, true);
  view.setUint16(34, 16, true);
  writeStr(36, "data");
  view.setUint32(40, dataLen, true);
  const channels: Float32Array[] = [];
  for (let c = 0; c < numCh; c++) channels.push(buffer.getChannelData(c));
  let offset = 44;
  for (let i = 0; i < len; i++) {
    for (let c = 0; c < numCh; c++) {
      const sample = Math.max(-1, Math.min(1, channels[c][i]));
      view.setInt16(offset, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true);
      offset += 2;
    }
  }
  return new Blob([out], { type: "audio/wav" });
}

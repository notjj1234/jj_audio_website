import {
  Streamlit,
  RenderData,
  Theme,
} from "streamlit-component-lib";
import "./style.css";
import {
  METRONOME_RATE_CHOICES,
  METRONOME_SOUND_LABELS,
  MetronomeConfig,
  MetronomeOptions,
  MetronomeSoundId,
  buildMetronomeAudioBuffer,
  coerceMetronomeFollow,
  coerceMetronomeOptions,
  coerceMetronomeRate,
  coerceMetronomeSound,
  metronomeClickTimes,
  metronomePeaksFromTimes,
} from "./metronomeClicks";

const DB_MIN = -25;
const DB_MAX = 25;
const DB_DEFAULT = 0;

function clampDb(db: number): number {
  return Math.max(DB_MIN, Math.min(DB_MAX, db));
}

type StemInfo = {
  id: string;
  label: string;
  url: string;
  downloadUrl?: string;
  downloadFilename?: string;
  peaks?: number[];
  hint?: string;
};

type MixerState = {
  volumesDb: Record<string, number>;
  muted: Record<string, boolean>;
  soloed: Record<string, boolean>;
  masterVolumeDb: number;
};

function dbToLinear(db: number): number {
  if (db <= DB_MIN) return 0;
  return Math.pow(10, db / 20);
}

function effectiveGains(
  stemIds: string[],
  state: MixerState
): Record<string, number> {
  const anySolo = stemIds.some((id) => state.soloed[id]);
  const masterLin = dbToLinear(
    Math.max(DB_MIN, Math.min(DB_MAX, state.masterVolumeDb ?? DB_DEFAULT))
  );
  const gains: Record<string, number> = {};
  for (const id of stemIds) {
    const db = Math.max(
      DB_MIN,
      Math.min(DB_MAX, state.volumesDb[id] ?? DB_DEFAULT)
    );
    const audible = anySolo ? !!state.soloed[id] : !state.muted[id];
    gains[id] = audible ? dbToLinear(db) * masterLin : 0;
  }
  return gains;
}

class StemMixerEngine {
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

  setTimeCallback(
    cb: (t: number, dur: number, playing: boolean) => void
  ): void {
    this.onTimeUpdate = cb;
  }

  setSoftPauseCallback(cb: () => void): void {
    this.onSoftPause = cb;
  }

  /**
   * Recover zombie/closed AudioContext after sleep/idle. No auto-resume.
   * Do not soft-pause on document hide — keep playing across app/window switches.
   * Some browsers still suspend Web Audio while fully backgrounded; that surfaces
   * via AudioContext statechange, not visibility alone.
   */
  installWakeHooks(): void {
    if (this.wakeHooked || typeof window === "undefined") return;
    this.wakeHooked = true;
    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "visible") {
        void this.handleWake();
      }
    });
    window.addEventListener("pageshow", () => {
      void this.handleWake();
    });
  }

  getDuration(): number {
    return this.duration;
  }

  getBuffer(id: string): AudioBuffer | undefined {
    return this.buffers.get(id);
  }

  isPlaying(): boolean {
    return this.playing;
  }

  currentTime(): number {
    if (!this.ctx) return this.offset;
    if (!this.playing) return this.offset;
    return Math.min(
      this.duration,
      this.offset + (this.ctx.currentTime - this.startedAt)
    );
  }

  /** Create a context for decode only. Never resume — pywebview blocks that without a click. */
  createContextForDecode(): AudioContext {
    if (!this.ctx || this.ctx.state === "closed") {
      this.ctx = new AudioContext();
      this.masterGain = null;
      this.limiter = null;
    }
    this.ensureMasterBus();
    this.bindContextState();
    return this.ctx;
  }

  async ensureContext(): Promise<AudioContext> {
    if (!this.ctx || this.ctx.state === "closed") {
      this.rebuildGraphKeepingBuffers();
    }
    const state = this.ctx!.state as string;
    if (state === "suspended" || state === "interrupted") {
      try {
        await this.ctx!.resume();
      } catch {
        this.rebuildGraphKeepingBuffers();
      }
    }
    if (this.ctx!.state === "closed") {
      this.rebuildGraphKeepingBuffers();
    }
    this.ensureMasterBus();
    this.bindContextState();
    return this.ctx!;
  }

  /** Master gain → DynamicsCompressor (−1 dBTP-ish) → destination. */
  private ensureMasterBus(): void {
    if (!this.ctx) return;
    if (this.masterGain && this.limiter) return;
    this.masterGain = this.ctx.createGain();
    this.masterGain.gain.value = 1;
    this.limiter = this.ctx.createDynamicsCompressor();
    // Soft ceiling near −1 dBFS true-peak proxy (matches mixer.py TRUE_PEAK_CEILING).
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

  /** Recreate AudioContext + bus; keep decoded buffers (wake recovery). */
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
    if (!this.ctx) return;
    // Only repair dead graphs. Healthy background playback must keep running.
    if (this.ctx.state === "closed") {
      if (this.playing) {
        await this.softPauseFromInterrupt();
      }
      this.rebuildGraphKeepingBuffers();
      return;
    }
    if (await this.contextLooksZombie()) {
      if (this.playing) {
        await this.softPauseFromInterrupt();
      }
      this.rebuildGraphKeepingBuffers();
    }
  }

  async loadStems(
    stems: StemInfo[],
    onProgress: (loaded: number, total: number, message: string) => void,
    liveBuffers?: Record<string, (ctx: AudioContext, durationSec: number) => AudioBuffer>
  ): Promise<{ errors: string[] }> {
    await this.stopSources(false);
    for (const gain of this.gains.values()) gain.disconnect();
    this.buffers.clear();
    this.gains.clear();
    this.sources.clear();
    this.stemIds = stems.map((s) => s.id);
    this.offset = 0;
    this.playing = false;
    this.duration = 0;

    // Decode without starting playback. Create context but don't resume until Play —
    // pywebview/WKWebView leaves output silent if resume() runs without a user gesture.
    const ctx = this.createContextForDecode();
    const errors: string[] = [];
    let loaded = 0;
    const total = stems.length;
    const deferred: StemInfo[] = [];

    for (const stem of stems) {
      if (liveBuffers?.[stem.id]) {
        deferred.push(stem);
        continue;
      }
      onProgress(loaded, total, `Loading ${stem.label}…`);
      try {
        const res = await fetch(stem.url);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const arr = await res.arrayBuffer();
        const buf = await ctx.decodeAudioData(arr.slice(0));
        this.buffers.set(stem.id, buf);
        this.duration = Math.max(this.duration, buf.duration);
        const gain = ctx.createGain();
        gain.connect(this.masterGain!);
        this.gains.set(stem.id, gain);
      } catch (e) {
        errors.push(`${stem.label}: ${e instanceof Error ? e.message : String(e)}`);
      }
      loaded += 1;
      onProgress(loaded, total, `Loaded ${loaded}/${total}`);
    }

    for (const stem of deferred) {
      onProgress(loaded, total, `Loading ${stem.label}…`);
      try {
        const synth = liveBuffers![stem.id]!;
        const buf = synth(ctx, this.duration);
        this.buffers.set(stem.id, buf);
        this.duration = Math.max(this.duration, buf.duration);
        const gain = ctx.createGain();
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

  /** Hot-swap one stem buffer without stopping the rest of the mix. */
  replaceStemBuffer(id: string, buf: AudioBuffer): void {
    this.buffers.set(id, buf);
    this.duration = 0;
    for (const b of this.buffers.values()) {
      this.duration = Math.max(this.duration, b.duration);
    }
    if (!this.ctx || !this.masterGain) return;
    if (!this.gains.has(id)) {
      const gain = this.ctx.createGain();
      gain.connect(this.masterGain);
      this.gains.set(id, gain);
      if (!this.stemIds.includes(id)) this.stemIds.push(id);
    }
    if (!this.playing) {
      this.tick();
      return;
    }
    const offset = this.currentTime();
    const old = this.sources.get(id);
    if (old) {
      try {
        old.onended = null;
        old.stop();
      } catch {
        /* */
      }
      try {
        old.disconnect();
      } catch {
        /* */
      }
      this.sources.delete(id);
    }
    const gain = this.gains.get(id);
    if (gain && offset < buf.duration) {
      const src = this.ctx.createBufferSource();
      src.buffer = buf;
      src.connect(gain);
      src.start(this.ctx.currentTime, offset);
      this.sources.set(id, src);
    }
    this.tick();
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
      src.onended = () => {
        /* individual stem end — transport ends when timeline hits duration */
      };
      this.sources.set(id, src);
    }
    this.tick();
  }

  async play(): Promise<void> {
    await this.ensureContext();
    // After sleep, playing may stay true with dead sources — force restart.
    if (this.playing) {
      const healthy =
        this.ctx?.state === "running" && this.sources.size > 0;
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

  async stop(): Promise<void> {
    await this.pause();
    await this.seek(0);
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

const engine = new StemMixerEngine();
engine.installWakeHooks();
let lastStemKey = "";
let state: MixerState = {
  volumesDb: {},
  muted: {},
  soloed: {},
  masterVolumeDb: DB_DEFAULT,
};
let stemInfos: StemInfo[] = [];
let trackTitle = "";
let metroConfig: MetronomeConfig | null = null;
let metroOptions: MetronomeOptions = coerceMetronomeOptions({
  accent: true,
  rate: 1,
  sound: "classic",
  follow: "smart",
});

let wantPlaying = false;
let transportBusy = false;
let transportPending: "play" | "pause" | "stop" | null = null;

let reportTimer: number | null = null;
let lastPublished = "";

const SLEEP_RESUME_HINT = "Tap Play to resume after sleep";

engine.setSoftPauseCallback(() => {
  wantPlaying = false;
  setPlayPauseLabel(false);
  const el = document.getElementById("status");
  if (el) el.textContent = SLEEP_RESUME_HINT;
  saveTransport();
});

const TRANSPORT_STORAGE_KEY = "audiotools_stem_mixer_transport";

function saveTransport(): void {
  try {
    sessionStorage.setItem(
      TRANSPORT_STORAGE_KEY,
      JSON.stringify({
        stemKey: lastStemKey,
        offset: engine.currentTime(),
        playing: engine.isPlaying(),
      })
    );
  } catch {
    /* ignore quota / private mode */
  }
}

function restoreTransport(): void {
  try {
    const raw = sessionStorage.getItem(TRANSPORT_STORAGE_KEY);
    if (!raw) return;
    const data = JSON.parse(raw) as {
      stemKey?: string;
      offset?: number;
      playing?: boolean;
    };
    if (data.stemKey !== lastStemKey) return;
    const offset = Number(data.offset) || 0;
    if (offset > 0) {
      void engine.seek(offset);
    }
  } catch {
    /* ignore */
  }
}

function statePayload(): string {
  return JSON.stringify({
    volumesDb: state.volumesDb,
    muted: state.muted,
    soloed: state.soloed,
    masterVolumeDb: state.masterVolumeDb,
    metronomeOptions: metroConfig ? metroOptions : null,
  });
}

function scheduleFrameHeight(): void {
  Streamlit.setFrameHeight();
  window.requestAnimationFrame(() => {
    Streamlit.setFrameHeight();
  });
}

function reportState(immediate = false): void {
  const publish = () => {
    const payload = statePayload();
    if (payload === lastPublished) return;
    lastPublished = payload;
    const value: Record<string, unknown> = {
      volumesDb: { ...state.volumesDb },
      muted: { ...state.muted },
      soloed: { ...state.soloed },
      masterVolumeDb: state.masterVolumeDb,
    };
    if (metroConfig) {
      value.metronomeOptions = { ...metroOptions };
    }
    Streamlit.setComponentValue(value);
  };
  if (immediate) {
    if (reportTimer !== null) window.clearTimeout(reportTimer);
    reportTimer = null;
    publish();
    return;
  }
  if (reportTimer !== null) window.clearTimeout(reportTimer);
  // Debounce parent Streamlit reruns while dragging / toggling.
  reportTimer = window.setTimeout(publish, 400);
}

function setPlayPauseLabel(playing: boolean): void {
  const playBtn = document.getElementById("btn-playpause");
  if (!playBtn) return;
  playBtn.textContent = playing ? "Pause" : "Play";
  playBtn.setAttribute("aria-pressed", playing ? "true" : "false");
}

function clearSleepResumeHint(): void {
  const el = document.getElementById("status");
  if (el && el.textContent === SLEEP_RESUME_HINT) {
    el.textContent = "";
  }
}

function applyTransport(): void {
  if (transportBusy) return;
  const pending = transportPending;
  transportPending = null;
  if (pending === "stop") {
    wantPlaying = false;
    setPlayPauseLabel(false);
    transportBusy = true;
    void engine
      .stop()
      .finally(() => {
        transportBusy = false;
        if (transportPending) applyTransport();
        else saveTransport();
      });
    return;
  }
  if (wantPlaying === engine.isPlaying()) {
    saveTransport();
    return;
  }
  transportBusy = true;
  const op = wantPlaying ? engine.play() : engine.pause();
  void op
    .then(() => {
      const playingNow = engine.isPlaying();
      wantPlaying = playingNow;
      setPlayPauseLabel(playingNow);
      if (playingNow) clearSleepResumeHint();
    })
    .catch(() => {
      wantPlaying = engine.isPlaying();
      setPlayPauseLabel(wantPlaying);
      const el = document.getElementById("status");
      if (el && wantPlaying === false) {
        el.textContent = "Tap Play again to start audio";
      }
    })
    .finally(() => {
      transportBusy = false;
      if (transportPending) {
        applyTransport();
        return;
      }
      saveTransport();
    });
}

function togglePlayPause(): void {
  wantPlaying = !wantPlaying;
  setPlayPauseLabel(wantPlaying);
  transportPending = wantPlaying ? "play" : "pause";
  applyTransport();
}

function stopPlayback(): void {
  wantPlaying = false;
  setPlayPauseLabel(false);
  transportPending = "stop";
  applyTransport();
}

function applyStateGains(): void {
  engine.applyGains(effectiveGains(stemInfos.map((s) => s.id), state));
}

function formatTime(sec: number): string {
  if (!isFinite(sec) || sec < 0) sec = 0;
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function renderUI(theme?: Theme): void {
  const root = document.getElementById("root");
  if (!root) return;

  const textColor = theme?.textColor ?? "#31333F";
  const bg = theme?.backgroundColor ?? "#ffffff";
  const secondary = theme?.secondaryBackgroundColor ?? "#f0f2f6";
  const primary = theme?.primaryColor ?? "#ff4b4b";

  root.innerHTML = `
    <div class="mixer" tabindex="-1" style="--text:${textColor};--bg:${bg};--secondary:${secondary};--primary:${primary}">
      <header class="mixer-header">
        <div class="track-title" id="track-title"></div>
        <p class="mixer-status" id="status" aria-live="polite">Ready</p>
      </header>
      <div class="mixer-transport">
        <div class="mixer-transport-controls">
          <button type="button" class="primary" id="btn-playpause" aria-pressed="false">Play</button>
          <button type="button" class="ghost" id="btn-stop">Stop</button>
          <button type="button" class="ghost" id="btn-restart">Restart</button>
          <span class="mixer-time" id="time" aria-label="Playback time">
            <span id="time-current">0:00</span>
            <span class="mixer-time-sep" aria-hidden="true">/</span>
            <span id="time-duration">0:00</span>
          </span>
        </div>
        <label class="mixer-seek">
          <span class="visually-hidden">Seek</span>
          <input type="range" id="seek" min="0" max="1000" value="0" step="1" disabled />
        </label>
        <label class="master-vol">
          <span class="master-vol-label">Master</span>
          <span class="visually-hidden">Master volume in decibels</span>
          <input type="range" id="master-vol" class="vol-slider"
            min="${DB_MIN}" max="${DB_MAX}" step="0.5" value="${state.masterVolumeDb}" />
          <span id="master-vol-val" class="stem-db">${state.masterVolumeDb.toFixed(1)}</span>
        </label>
      </div>
      <div class="mixer-master">
        <button type="button" class="ghost" id="btn-muteall">Mute all</button>
        <button type="button" class="ghost" id="btn-reset">Reset mix</button>
        <button type="button" class="ghost" id="btn-clearsolo" hidden>Clear solo</button>
      </div>
      <div class="mixer-stems" id="stems"></div>
    </div>
  `;

  const mixerRoot = root.querySelector<HTMLElement>(".mixer");
  mixerRoot?.addEventListener("pointerdown", () => {
    mixerRoot.focus({ preventScroll: true });
  });

  const stemsEl = document.getElementById("stems")!;
  stemsEl.innerHTML = stemInfos
    .map((stem) => {
      const db = clampDb(state.volumesDb[stem.id] ?? DB_DEFAULT);
      const muted = !!state.muted[stem.id];
      const soloed = !!state.soloed[stem.id];
      const liveMetro = stem.id === "metronome" && metroConfig != null;
      const wave = waveformSeekHtml(stem.peaks, stem.label, {
        variant: liveMetro ? "metro" : "default",
      });
      const download = stem.downloadUrl
        ? `<a class="download-link" href="${stem.downloadUrl}" download="${escapeHtml(
            stem.downloadFilename || `${stem.label}.wav`
          )}">Download</a>`
        : "";
      const preview = liveMetro
        ? metronomePreviewHtml(wave, download)
        : wave || download
          ? `<div class="stem-preview">${wave}${download}</div>`
          : "";
      // Metronome: keep a short title tooltip only — no body hint clutter.
      const nameTitle =
        stem.hint && !liveMetro ? ` title="${escapeHtml(stem.hint)}"` : "";
      const hint =
        stem.hint && !liveMetro
          ? `<span class="stem-hint">${escapeHtml(stem.hint)}</span>`
          : "";
      return `
        <div class="stem-row${liveMetro ? " is-metro" : ""}" data-id="${escapeHtml(stem.id)}">
          <button type="button" class="toggle mute${muted ? " active" : ""}" data-id="${escapeHtml(stem.id)}"
            aria-label="${muted ? "Unmute" : "Mute"} ${escapeHtml(stem.label)}"
            aria-pressed="${muted ? "true" : "false"}">M</button>
          <button type="button" class="toggle solo${soloed ? " active" : ""}" data-id="${escapeHtml(stem.id)}"
            aria-label="${soloed ? "Unsolo" : "Solo"} ${escapeHtml(stem.label)}"
            aria-pressed="${soloed ? "true" : "false"}">S</button>
          <div class="stem-name-block">
            <strong class="stem-name"${nameTitle}>${escapeHtml(stem.label)}</strong>
            ${hint}
          </div>
          <label class="stem-vol">
            <span class="visually-hidden">${escapeHtml(stem.label)} volume in decibels</span>
            <input type="range" class="vol-slider" data-id="${escapeHtml(stem.id)}"
              min="${DB_MIN}" max="${DB_MAX}" step="0.5" value="${db}" />
            <span class="vol-val stem-db">${db.toFixed(1)}</span>
          </label>
          ${preview}
        </div>`;
    })
    .join("");

  document.getElementById("btn-playpause")!.onpointerdown = (event) => {
    event.preventDefault();
    togglePlayPause();
  };
  document.getElementById("btn-stop")!.onpointerdown = (event) => {
    event.preventDefault();
    stopPlayback();
  };
  document.getElementById("btn-restart")!.onclick = () => {
    wantPlaying = true;
    setPlayPauseLabel(true);
    void engine.restart().then(() => {
      if (engine.isPlaying()) clearSleepResumeHint();
      saveTransport();
    });
  };

  document.getElementById("btn-muteall")!.onclick = () => {
    // If every stem is already muted, Unmute All; otherwise Mute All.
    const target = !allMuted();
    for (const stem of stemInfos) {
      state.muted[stem.id] = target;
      // Mute and solo are mutually exclusive per stem.
      if (target) state.soloed[stem.id] = false;
    }
    applyStateGains();
    reportState();
    updateStemChrome();
    updateMuteAllLabel();
  };

  document.getElementById("btn-reset")!.onclick = () => {
    for (const stem of stemInfos) {
      state.muted[stem.id] = stem.id === "metronome";
      state.soloed[stem.id] = false;
      state.volumesDb[stem.id] = DB_DEFAULT;
    }
    state.masterVolumeDb = DB_DEFAULT;
    stemsEl.querySelectorAll<HTMLInputElement>(".vol-slider").forEach((el) => {
      el.value = String(DB_DEFAULT);
      const label = el.parentElement?.querySelector(".vol-val");
      if (label) label.textContent = DB_DEFAULT.toFixed(1);
    });
    const masterEl = document.getElementById("master-vol") as HTMLInputElement | null;
    const masterVal = document.getElementById("master-vol-val");
    if (masterEl) masterEl.value = String(DB_DEFAULT);
    if (masterVal) masterVal.textContent = DB_DEFAULT.toFixed(1);
    applyStateGains();
    reportState();
    updateStemChrome();
    updateMuteAllLabel();
  };

  document.getElementById("btn-clearsolo")!.onclick = () => {
    for (const stem of stemInfos) {
      state.soloed[stem.id] = false;
    }
    applyStateGains();
    reportState();
    updateStemChrome();
    updateMuteAllLabel();
  };
  updateMuteAllLabel();
  updateStemChrome();

  const seek = document.getElementById("seek") as HTMLInputElement;
  seek.oninput = () => {
    const dur = engine.getDuration() || 1;
    const t = (Number(seek.value) / 1000) * dur;
    void engine.seek(t);
    updatePlayheads(t, dur);
  };

  stemsEl.querySelectorAll<HTMLElement>(".wave-seek").forEach((el) => {
    el.onpointerdown = (event) => {
      if (event.button !== 0) return;
      event.preventDefault();
      seekFromWavePointer(el, event.clientX);
    };
  });

  const masterVol = document.getElementById("master-vol") as HTMLInputElement;
  masterVol.oninput = () => {
    const db = Number(masterVol.value);
    state.masterVolumeDb = db;
    const label = document.getElementById("master-vol-val");
    if (label) label.textContent = db.toFixed(1);
    applyStateGains();
  };
  masterVol.onchange = () => {
    reportState(true);
  };

  stemsEl.querySelectorAll<HTMLInputElement>(".vol-slider").forEach((el) => {
    el.oninput = () => {
      const id = el.dataset.id!;
      const db = Number(el.value);
      state.volumesDb[id] = db;
      const label = el.parentElement?.querySelector(".vol-val");
      if (label) label.textContent = db.toFixed(1);
      applyStateGains();
      // Live audio only while dragging — report to Streamlit on release.
    };
    el.onchange = () => {
      reportState(true);
    };
  });

  stemsEl.querySelectorAll<HTMLButtonElement>("button.toggle.mute").forEach((el) => {
    el.onclick = () => {
      const id = el.dataset.id!;
      const muted = !state.muted[id];
      state.muted[id] = muted;
      if (muted) state.soloed[id] = false;
      applyStateGains();
      reportState();
      updateStemChrome();
      updateMuteAllLabel();
    };
  });

  stemsEl.querySelectorAll<HTMLButtonElement>("button.toggle.solo").forEach((el) => {
    el.onclick = () => {
      const id = el.dataset.id!;
      const soloed = !state.soloed[id];
      state.soloed[id] = soloed;
      if (soloed) state.muted[id] = false;
      applyStateGains();
      reportState();
      updateStemChrome();
      updateMuteAllLabel();
    };
  });

  bindMetronomeOptionControls();

  engine.setTimeCallback((t, dur, playing) => {
    const currentEl = document.getElementById("time-current");
    const durationEl = document.getElementById("time-duration");
    const seekEl = document.getElementById("seek") as HTMLInputElement | null;
    if (currentEl) currentEl.textContent = formatTime(t);
    if (durationEl) durationEl.textContent = formatTime(dur);
    if (seekEl) {
      seekEl.disabled = dur <= 0;
      seekEl.setAttribute("aria-valuetext", formatTime(t));
      if (document.activeElement !== seekEl) {
        seekEl.value = String(dur > 0 ? Math.round((t / dur) * 1000) : 0);
      }
    }
    updatePlayheads(t, dur);
    if (playing) clearSleepResumeHint();
    if (!transportBusy && transportPending === null) {
      wantPlaying = playing;
      setPlayPauseLabel(playing);
    }
    saveTransport();
  });

  updateTrackTitleDisplay();
  scheduleFrameHeight();
}

function updateTrackTitleDisplay(): void {
  const el = document.getElementById("track-title");
  if (!el) return;
  if (trackTitle.trim()) {
    el.textContent = trackTitle.trim();
    el.style.display = "block";
  } else {
    el.textContent = "";
    el.style.display = "none";
  }
}

function allMuted(): boolean {
  return stemInfos.length > 0 && stemInfos.every((s) => !!state.muted[s.id]);
}

function anySoloed(): boolean {
  return stemInfos.some((s) => !!state.soloed[s.id]);
}

function isAudible(stemId: string): boolean {
  return anySoloed() ? !!state.soloed[stemId] : !state.muted[stemId];
}

function updateMuteAllLabel(): void {
  const btn = document.getElementById("btn-muteall");
  if (btn) btn.textContent = allMuted() ? "Unmute all" : "Mute all";
}

function updateStemChrome(): void {
  const clearBtn = document.getElementById("btn-clearsolo");
  if (clearBtn) clearBtn.hidden = !anySoloed();

  document.querySelectorAll<HTMLElement>(".stem-row").forEach((row) => {
    const id = row.dataset.id!;
    const stem = stemInfos.find((s) => s.id === id);
    const label = stem?.label ?? id;
    const muted = !!state.muted[id];
    const soloed = !!state.soloed[id];
    const audible = isAudible(id);
    const silencedBySolo = !audible && !muted && !soloed;
    row.classList.toggle("silent", !audible);
    if (silencedBySolo) {
      row.title = "Silent because another stem is soloed";
    } else if (stem?.hint) {
      row.title = stem.hint;
    } else {
      row.removeAttribute("title");
    }

    const muteBtn = row.querySelector<HTMLButtonElement>("button.toggle.mute");
    if (muteBtn) {
      muteBtn.classList.toggle("active", muted);
      muteBtn.setAttribute("aria-pressed", muted ? "true" : "false");
      muteBtn.setAttribute("aria-label", `${muted ? "Unmute" : "Mute"} ${label}`);
    }
    const soloBtn = row.querySelector<HTMLButtonElement>("button.toggle.solo");
    if (soloBtn) {
      soloBtn.classList.toggle("active", soloed);
      soloBtn.setAttribute("aria-pressed", soloed ? "true" : "false");
      soloBtn.setAttribute("aria-label", `${soloed ? "Unsolo" : "Solo"} ${label}`);
    }

    const nameEl = row.querySelector(".stem-name");
    if (nameEl) {
      const hidden = nameEl.querySelector(".visually-hidden");
      if (silencedBySolo && !hidden) {
        const note = document.createElement("span");
        note.className = "visually-hidden";
        note.textContent = " Silent because another stem is soloed";
        nameEl.appendChild(note);
      } else if (!silencedBySolo && hidden) {
        hidden.remove();
      }
    }
  });
  scheduleFrameHeight();
}

function updatePlayheads(t: number, dur: number): void {
  const pct = dur > 0 ? Math.min(100, Math.max(0, (t / dur) * 100)) : 0;
  document.querySelectorAll<HTMLElement>(".wave-playhead").forEach((el) => {
    el.style.left = `${pct}%`;
    el.hidden = dur <= 0;
  });
  document.querySelectorAll<HTMLElement>(".wave-seek").forEach((el) => {
    el.setAttribute("aria-valuenow", String(Math.round(pct * 10)));
    el.setAttribute("aria-valuetext", formatTime(t));
  });
}

function seekFromWavePointer(el: HTMLElement, clientX: number): void {
  const dur = engine.getDuration();
  if (!(dur > 0)) return;
  const rect = el.getBoundingClientRect();
  const ratio = rect.width > 0 ? (clientX - rect.left) / rect.width : 0;
  const t = Math.max(0, Math.min(1, ratio)) * dur;
  void engine.seek(t);
  updatePlayheads(t, dur);
}

function peakPercentile(peaks: number[], p: number): number {
  if (peaks.length === 0) return 0;
  const sorted = [...peaks].sort((a, b) => a - b);
  const idx = Math.min(
    sorted.length - 1,
    Math.max(0, Math.ceil(p * sorted.length) - 1)
  );
  return sorted[idx];
}

/** Display normalize: 98th percentile so one crash doesn't bury the groove. */
function waveformNorm(peaks: number[]): number {
  const absMax = Math.max(...peaks, 0.0001);
  const p98 = peakPercentile(peaks, 0.98);
  return Math.max(p98, absMax * 0.05, 0.0001);
}

/** Peak envelope from the same AudioBuffer used for playback. */
function peaksFromBuffer(buf: AudioBuffer, numPoints = 512): number[] {
  const nCh = buf.numberOfChannels;
  const length = buf.length;
  if (length <= 0 || nCh <= 0) return new Array(numPoints).fill(0);
  const chans: Float32Array[] = [];
  for (let c = 0; c < nCh; c++) chans.push(buf.getChannelData(c));
  const peakAt = (i: number): number => {
    let m = 0;
    for (const ch of chans) {
      const v = Math.abs(ch[i] ?? 0);
      if (v > m) m = v;
    }
    return m;
  };
  if (length <= numPoints) {
    const out = new Array(length);
    for (let i = 0; i < length; i++) out[i] = peakAt(i);
    return out;
  }
  const chunk = Math.max(1, Math.floor(length / numPoints));
  const peaks = new Array(numPoints);
  for (let i = 0; i < numPoints; i++) {
    const start = i * chunk;
    const end = i === numPoints - 1 ? length : Math.min(length, start + chunk);
    let m = 0;
    for (let s = start; s < end; s++) {
      const v = peakAt(s);
      if (v > m) m = v;
    }
    peaks[i] = m;
  }
  return peaks;
}

function applyDecodedPeaks(): void {
  for (const stem of stemInfos) {
    if (stem.id === "metronome" && metroConfig) {
      stem.peaks = metronomePeaksFromTimes(
        metronomeClickTimes(metroConfig, metroOptions.follow),
        metroConfig.durationSec || engine.getDuration(),
        metroOptions,
        metroConfig.refSec
      );
      continue;
    }
    const buf = engine.getBuffer(stem.id);
    if (!buf) continue;
    stem.peaks = peaksFromBuffer(buf);
  }
}

function metronomeToolbarHtml(): string {
  const rateBtns = METRONOME_RATE_CHOICES.map((r) => {
    const active = Math.abs(metroOptions.rate - r) < 1e-9;
    return `<button type="button" class="metro-rate-btn${active ? " active" : ""}" data-rate="${r}" aria-pressed="${active ? "true" : "false"}">${r}x</button>`;
  }).join("");
  const soundIds = Object.keys(METRONOME_SOUND_LABELS) as MetronomeSoundId[];
  const soundOpts = soundIds
    .map(
      (id) =>
        `<option value="${id}"${metroOptions.sound === id ? " selected" : ""}>${escapeHtml(
          METRONOME_SOUND_LABELS[id]
        )}</option>`
    )
    .join("");
  return `
    <div class="metro-toolbar" role="group" aria-label="Click track options">
      <div class="metro-rate-seg" role="group" aria-label="Click rate">${rateBtns}</div>
      <div class="metro-rate-seg" role="group" aria-label="Metronome mode">
        <button type="button" class="metro-follow-btn${metroOptions.follow === "smart" ? " active" : ""}" data-follow="smart" aria-pressed="${metroOptions.follow === "smart" ? "true" : "false"}">Smart</button>
        <button type="button" class="metro-follow-btn${metroOptions.follow === "steady" ? " active" : ""}" data-follow="steady" aria-pressed="${metroOptions.follow === "steady" ? "true" : "false"}">Steady</button>
      </div>
      <button type="button" class="metro-chip${metroOptions.accent ? " active" : ""}" id="metro-accent"
        aria-pressed="${metroOptions.accent ? "true" : "false"}">Accent</button>
      <label class="metro-sound-wrap">
        <span class="visually-hidden">Click sound</span>
        <select id="metro-sound" aria-label="Click sound">${soundOpts}</select>
      </label>
    </div>`;
}

function metronomePreviewHtml(wave: string, download: string): string {
  return `<div class="stem-preview metro-preview">
    <div class="metro-wave">
      ${metronomeToolbarHtml()}
      ${wave}
    </div>
    ${download}
  </div>`;
}

function applyLiveMetronomeBuffer(): void {
  if (!metroConfig) return;
  const ctx = engine.createContextForDecode();
  const buf = buildMetronomeAudioBuffer(ctx, metroConfig, metroOptions);
  engine.replaceStemBuffer("metronome", buf);
  applyDecodedPeaks();
  const row = document.querySelector<HTMLElement>('.stem-row[data-id="metronome"]');
  if (!row) return;
  const preview = row.querySelector(".stem-preview");
  const stem = stemInfos.find((s) => s.id === "metronome");
  if (!stem || !preview) return;
  const wave = waveformSeekHtml(stem.peaks, stem.label, { variant: "metro" });
  const download = stem.downloadUrl
    ? `<a class="download-link" href="${stem.downloadUrl}" download="${escapeHtml(
        stem.downloadFilename || `${stem.label}.wav`
      )}">Download</a>`
    : "";
  preview.outerHTML = metronomePreviewHtml(wave, download);
  const nextPreview = row.querySelector(".stem-preview");
  nextPreview?.querySelectorAll<HTMLElement>(".wave-seek").forEach((el) => {
    el.onpointerdown = (event) => {
      if (event.button !== 0) return;
      event.preventDefault();
      seekFromWavePointer(el, event.clientX);
    };
  });
  bindMetronomeOptionControls();
  updatePlayheads(engine.currentTime(), engine.getDuration());
  scheduleFrameHeight();
}

function bindMetronomeOptionControls(): void {
  if (!metroConfig) return;
  const apply = (next: Partial<MetronomeOptions>) => {
    metroOptions = coerceMetronomeOptions({ ...metroOptions, ...next });
    applyLiveMetronomeBuffer();
    applyStateGains();
    reportState(true);
  };
  document.querySelectorAll<HTMLButtonElement>(".metro-rate-btn").forEach((btn) => {
    btn.onclick = (event) => {
      event.stopPropagation();
      apply({ rate: coerceMetronomeRate(btn.dataset.rate) });
    };
  });
  document.querySelectorAll<HTMLButtonElement>(".metro-follow-btn").forEach((btn) => {
    btn.onclick = (event) => {
      event.stopPropagation();
      apply({ follow: coerceMetronomeFollow(btn.dataset.follow) });
    };
  });
  const accent = document.getElementById("metro-accent") as HTMLButtonElement | null;
  if (accent) {
    accent.onclick = (event) => {
      event.stopPropagation();
      apply({ accent: !metroOptions.accent });
    };
  }
  const sound = document.getElementById("metro-sound") as HTMLSelectElement | null;
  if (sound) {
    sound.onchange = () => {
      apply({ sound: coerceMetronomeSound(sound.value) });
    };
    sound.onpointerdown = (event) => event.stopPropagation();
  }
}

/** Peak i of n maps to the same 0–100% axis as the playhead (slot = width / n). */
function waveformBarLayout(n: number, width: number): { slot: number; barW: number } {
  const slot = width / Math.max(1, n);
  const barW = slot * 0.85;
  return { slot, barW };
}

function waveformSeekHtml(
  peaks: number[] | undefined,
  label: string,
  opts?: { variant?: "default" | "metro" }
): string {
  if (!peaks || peaks.length === 0) return "";
  const width = 400;
  const height = opts?.variant === "metro" ? 44 : 52;
  const mid = height / 2;
  const n = peaks.length;
  const norm = waveformNorm(peaks);
  const { slot, barW } = waveformBarLayout(n, width);
  const bars: string[] = [
    `<line class="wave-baseline" x1="0" y1="${mid}" x2="${width}" y2="${mid}" />`,
  ];
  const metro = opts?.variant === "metro";
  for (let i = 0; i < n; i++) {
    const peak = peaks[i] ?? 0;
    if (peak <= 0) continue;
    const amp = Math.sqrt(Math.min(1, peak / norm)) * (mid - 2);
    const h = Math.max(metro ? 4 : 3, amp * 2 * (metro ? 0.85 : 1));
    const x = i * slot + (slot - (metro ? Math.min(barW, 1.6) : barW)) / 2;
    const y = mid - h / 2;
    const w = metro ? Math.min(barW, 1.6) : barW;
    bars.push(
      `<rect x="${x.toFixed(2)}" y="${y.toFixed(2)}" width="${w.toFixed(2)}" ` +
        `height="${h.toFixed(2)}" rx="0.8" ry="0.8" />`
    );
  }
  const svg =
    `<svg class="waveform-svg" viewBox="0 0 ${width} ${height}" ` +
    `preserveAspectRatio="none" aria-hidden="true">${bars.join("")}</svg>`;
  return (
    `<div class="wave-seek" role="slider" tabindex="0" ` +
    `aria-label="Seek ${escapeHtml(label)}" aria-valuemin="0" aria-valuemax="1000" aria-valuenow="0">` +
    `${svg}<span class="wave-playhead" aria-hidden="true" hidden></span></div>`
  );
}

function isTypingTarget(el: EventTarget | null): boolean {
  if (!(el instanceof HTMLElement)) return false;
  const tag = el.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return true;
  if (el.isContentEditable) return true;
  return false;
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function stemKey(stems: StemInfo[], metro: MetronomeConfig | null): string {
  const stemPart = stems
    .map((s) => {
      if (s.id === "metronome" && metro && metro.times1x.length > 0) {
        return `${s.id}|live`;
      }
      return `${s.id}|${s.url}`;
    })
    .join(";");
  if (!metro || metro.times1x.length === 0) return stemPart;
  const first = metro.times1x[0] ?? 0;
  const last = metro.times1x[metro.times1x.length - 1] ?? 0;
  return `${stemPart}|m:${metro.times1x.length}:${first.toFixed(3)}:${last.toFixed(3)}:${metro.durationSec.toFixed(3)}`;
}

function parseMetronomeArg(raw: unknown): MetronomeConfig | null {
  if (!raw || typeof raw !== "object") return null;
  const obj = raw as Record<string, unknown>;
  const timesRaw = obj.times1x ?? obj.click_times_1x;
  const times1x = Array.isArray(timesRaw)
    ? timesRaw.map((t) => Number(t)).filter((t) => Number.isFinite(t))
    : [];
  if (times1x.length === 0) return null;
  const steadyRaw = obj.steadyTimes1x ?? obj.steady_times_1x;
  const steadyTimes1x = Array.isArray(steadyRaw)
    ? steadyRaw.map((t) => Number(t)).filter((t) => Number.isFinite(t))
    : [];
  const options = coerceMetronomeOptions(
    (obj.options as Partial<MetronomeOptions> | undefined) ?? {
      accent: obj.accent as boolean | undefined,
      rate: obj.rate as number | undefined,
      sound: obj.sound as string | undefined,
    }
  );
  return {
    times1x,
    steadyTimes1x,
    refSec: Number(obj.refSec ?? obj.body_start_sec ?? obj.first_detected_sec ?? times1x[0] ?? 0) || 0,
    beatsPerMeasure: Math.max(1, Math.floor(Number(obj.beatsPerMeasure ?? obj.beats_per_measure ?? 4) || 4)),
    durationSec: Math.max(0.05, Number(obj.durationSec ?? obj.duration_sec ?? 0) || 0),
    options,
  };
}

function softUpdateStemDownloads(stems: StemInfo[]): void {
  stemInfos = stems.map((next) => {
    const prev = stemInfos.find((s) => s.id === next.id);
    return {
      ...next,
      peaks: prev?.peaks ?? next.peaks,
    };
  });
  for (const stem of stemInfos) {
    const row = document.querySelector(`.stem-row[data-id="${CSS.escape(stem.id)}"]`);
    if (!row || !stem.downloadUrl) continue;
    const link = row.querySelector<HTMLAnchorElement>("a.download-link");
    if (!link) continue;
    link.href = stem.downloadUrl;
    if (stem.downloadFilename) {
      link.setAttribute("download", stem.downloadFilename);
    }
  }
}

async function onRender(event: Event): Promise<void> {
  const data = (event as CustomEvent<RenderData>).detail;
  const args = data.args as {
    stems?: StemInfo[];
    initialVolumesDb?: Record<string, number>;
    initialMuted?: Record<string, boolean>;
    initialSoloed?: Record<string, boolean>;
    initialMasterVolumeDb?: number;
    trackTitle?: string;
    metronome?: unknown;
  };

  const stems = args.stems ?? [];
  const nextMetro = parseMetronomeArg(args.metronome);
  const key = stemKey(stems, nextMetro);
  const status = () => document.getElementById("status");
  const nextTitle = args.trackTitle ?? "";
  if (nextTitle !== trackTitle) {
    trackTitle = nextTitle;
    updateTrackTitleDisplay();
  }

  if (key === lastStemKey) {
    softUpdateStemDownloads(stems);
    scheduleFrameHeight();
    return;
  }

  try {
    const raw = sessionStorage.getItem(TRANSPORT_STORAGE_KEY);
    if (raw) {
      const stored = JSON.parse(raw) as { stemKey?: string };
      if (stored.stemKey !== key) {
        sessionStorage.removeItem(TRANSPORT_STORAGE_KEY);
      }
    }
  } catch {
    /* ignore */
  }
  lastStemKey = key;
  wantPlaying = false;
  transportBusy = false;
  transportPending = null;
  stemInfos = stems;
  metroConfig = nextMetro;
  metroOptions = nextMetro
    ? coerceMetronomeOptions(nextMetro.options)
    : coerceMetronomeOptions({ accent: true, rate: 1, sound: "classic", follow: "smart" });
  const masterInit = Number(args.initialMasterVolumeDb);
  const volumesIn = { ...(args.initialVolumesDb ?? {}) };
  for (const id of Object.keys(volumesIn)) {
    volumesIn[id] = clampDb(Number(volumesIn[id]));
  }
  state = {
    volumesDb: volumesIn,
    muted: { ...(args.initialMuted ?? {}) },
    soloed: { ...(args.initialSoloed ?? {}) },
    masterVolumeDb: Number.isFinite(masterInit) ? clampDb(masterInit) : DB_DEFAULT,
  };
  for (const s of stems) {
    if (state.volumesDb[s.id] === undefined) state.volumesDb[s.id] = DB_DEFAULT;
    else state.volumesDb[s.id] = clampDb(state.volumesDb[s.id]);
    if (state.muted[s.id] === undefined) state.muted[s.id] = s.id === "metronome";
    if (state.soloed[s.id] === undefined) state.soloed[s.id] = false;
  }
  renderUI(data.theme);
  const st = status();
  if (st) st.textContent = "Loading stems…";
  const liveBuffers: Record<string, (ctx: AudioContext, durationSec: number) => AudioBuffer> =
    {};
  if (metroConfig) {
    liveBuffers.metronome = (ctx, durationSec) => {
      const cfg: MetronomeConfig = {
        ...metroConfig!,
        durationSec: Math.max(metroConfig!.durationSec, durationSec, 0.05),
      };
      metroConfig = cfg;
      return buildMetronomeAudioBuffer(ctx, cfg, metroOptions);
    };
  }
  const { errors } = await engine.loadStems(
    stems,
    (loaded, total, msg) => {
      const el = status();
      if (el) el.textContent = msg || `${loaded}/${total}`;
      scheduleFrameHeight();
    },
    liveBuffers
  );
  applyStateGains();
  applyDecodedPeaks();
  // Do not reportState(true) on load — that remounts the iframe via a parent
  // Streamlit rerun. Only publish when the user changes mute/solo/volume.
  lastPublished = statePayload();
  const el = status();
  if (el) {
    el.textContent = errors.length
      ? `Loaded with errors: ${errors.join("; ")}`
      : `Loaded ${stems.length} stem(s). Adjust levels while playing — playback will not restart.`;
  }
  renderUI(data.theme);
  applyStateGains();
  restoreTransport();

  scheduleFrameHeight();
}

Streamlit.events.addEventListener(Streamlit.RENDER_EVENT, onRender);
Streamlit.setComponentReady();
scheduleFrameHeight();

window.addEventListener("keydown", (e) => {
  if (e.code !== "Space" && e.key !== " ") return;
  if (e.repeat || e.altKey || e.ctrlKey || e.metaKey || e.shiftKey) return;
  if (isTypingTarget(e.target)) return;
  e.preventDefault();
  togglePlayPause();
});

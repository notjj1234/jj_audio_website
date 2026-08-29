import {
  Streamlit,
  RenderData,
  Theme,
} from "streamlit-component-lib";
import "./style.css";

const DB_MIN = -60;
const DB_MAX = 24;
const DB_DEFAULT = 0;

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
  private onTimeUpdate: ((t: number, dur: number, playing: boolean) => void) | null =
    null;
  private raf = 0;

  setTimeCallback(
    cb: (t: number, dur: number, playing: boolean) => void
  ): void {
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
    return Math.min(
      this.duration,
      this.offset + (this.ctx.currentTime - this.startedAt)
    );
  }

  /** Create a context for decode only. Never resume — pywebview blocks that without a click. */
  createContextForDecode(): AudioContext {
    if (!this.ctx) {
      this.ctx = new AudioContext();
    }
    this.ensureMasterBus();
    return this.ctx;
  }

  async ensureContext(): Promise<AudioContext> {
    if (!this.ctx) {
      this.ctx = new AudioContext();
    }
    if (this.ctx.state === "suspended") {
      await this.ctx.resume();
    }
    this.ensureMasterBus();
    return this.ctx;
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

  async loadStems(
    stems: StemInfo[],
    onProgress: (loaded: number, total: number, message: string) => void
  ): Promise<{ errors: string[] }> {
    await this.stopSources(false);
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

    for (const stem of stems) {
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
let lastStemKey = "";
let state: MixerState = {
  volumesDb: {},
  muted: {},
  soloed: {},
  masterVolumeDb: DB_DEFAULT,
};
let stemInfos: StemInfo[] = [];
let trackTitle = "";

let wantPlaying = false;
let transportBusy = false;
let transportPending: "play" | "pause" | "stop" | null = null;

let reportTimer: number | null = null;
let lastPublished = "";

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
    Streamlit.setComponentValue({
      volumesDb: { ...state.volumesDb },
      muted: { ...state.muted },
      soloed: { ...state.soloed },
      masterVolumeDb: state.masterVolumeDb,
    });
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
  if (playBtn) playBtn.textContent = playing ? "Pause" : "Play";
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
    <div class="mixer" style="--text:${textColor};--bg:${bg};--secondary:${secondary};--primary:${primary}">
      <div class="track-title" id="track-title"></div>
      <div class="status" id="status">Ready</div>
      <div class="transport">
        <button type="button" class="primary" id="btn-playpause">Play</button>
        <button type="button" class="secondary" id="btn-stop">Stop</button>
        <button type="button" class="secondary" id="btn-restart">Restart</button>
        <button type="button" class="secondary" id="btn-muteall">Mute All</button>
        <button type="button" class="secondary" id="btn-reset">Reset</button>
        <span class="time" id="time">0:00 / 0:00</span>
      </div>
      <input type="range" id="seek" min="0" max="1000" value="0" step="1" />
      <label class="master-vol">
        Master volume (dB)
        <input type="range" id="master-vol" class="vol-slider"
          min="${DB_MIN}" max="${DB_MAX}" step="0.5" value="${state.masterVolumeDb}" />
        <span id="master-vol-val">${state.masterVolumeDb.toFixed(1)} dB</span>
      </label>
      <div class="stems" id="stems"></div>
    </div>
  `;

  const stemsEl = document.getElementById("stems")!;
  stemsEl.innerHTML = stemInfos
    .map((stem) => {
      const db = state.volumesDb[stem.id] ?? DB_DEFAULT;
      const muted = !!state.muted[stem.id];
      const soloed = !!state.soloed[stem.id];
      return `
        <div class="stem-row" data-id="${stem.id}">
          <div class="stem-head">
            <strong${stem.hint ? ` title="${escapeHtml(stem.hint)}"` : ""}>${escapeHtml(
        stem.label
      )}</strong>
            <span class="badges">${soloed ? "SOLO" : muted ? "MUTED" : ""}</span>
          </div>
          <label class="vol">
            Volume (dB)
            <input type="range" class="vol-slider" data-id="${stem.id}"
              min="${DB_MIN}" max="${DB_MAX}" step="0.5" value="${db}" />
            <span class="vol-val">${db.toFixed(1)} dB</span>
          </label>
          <div class="toggles">
            <label><input type="checkbox" class="mute" data-id="${stem.id}" ${muted ? "checked" : ""}/> Mute</label>
            <label><input type="checkbox" class="solo" data-id="${stem.id}" ${soloed ? "checked" : ""}/> Solo</label>
          </div>
          <div class="stem-preview">
            ${waveformSvg(stem.peaks)}
            ${
              stem.downloadUrl
                ? `<a class="download-link" href="${stem.downloadUrl}" download="${escapeHtml(
                    stem.downloadFilename || `${stem.label}.wav`
                  )}">Download ${escapeHtml(stem.label)}</a>`
                : ""
            }
          </div>
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
    void engine.restart().then(() => saveTransport());
  };

  document.getElementById("btn-muteall")!.onclick = () => {
    // If every stem is already muted, Unmute All; otherwise Mute All.
    const target = !allMuted();
    for (const stem of stemInfos) {
      state.muted[stem.id] = target;
      // Mute and solo are mutually exclusive per stem.
      if (target) state.soloed[stem.id] = false;
    }
    stemsEl.querySelectorAll<HTMLInputElement>(".mute").forEach((el) => {
      el.checked = !!state.muted[el.dataset.id!];
    });
    stemsEl.querySelectorAll<HTMLInputElement>(".solo").forEach((el) => {
      el.checked = !!state.soloed[el.dataset.id!];
    });
    applyStateGains();
    reportState();
    updateBadges();
    updateMuteAllLabel();
  };

  document.getElementById("btn-reset")!.onclick = () => {
    for (const stem of stemInfos) {
      state.muted[stem.id] = false;
      state.soloed[stem.id] = false;
      state.volumesDb[stem.id] = DB_DEFAULT;
    }
    state.masterVolumeDb = DB_DEFAULT;
    stemsEl.querySelectorAll<HTMLInputElement>(".mute").forEach((el) => {
      el.checked = false;
    });
    stemsEl.querySelectorAll<HTMLInputElement>(".solo").forEach((el) => {
      el.checked = false;
    });
    stemsEl.querySelectorAll<HTMLInputElement>(".vol-slider").forEach((el) => {
      el.value = String(DB_DEFAULT);
      const label = el.parentElement?.querySelector(".vol-val");
      if (label) label.textContent = `${DB_DEFAULT.toFixed(1)} dB`;
    });
    const masterEl = document.getElementById("master-vol") as HTMLInputElement | null;
    const masterVal = document.getElementById("master-vol-val");
    if (masterEl) masterEl.value = String(DB_DEFAULT);
    if (masterVal) masterVal.textContent = `${DB_DEFAULT.toFixed(1)} dB`;
    applyStateGains();
    reportState();
    updateBadges();
    updateMuteAllLabel();
  };
  updateMuteAllLabel();

  const seek = document.getElementById("seek") as HTMLInputElement;
  seek.oninput = () => {
    const dur = engine.getDuration() || 1;
    const t = (Number(seek.value) / 1000) * dur;
    void engine.seek(t);
  };

  const masterVol = document.getElementById("master-vol") as HTMLInputElement;
  masterVol.oninput = () => {
    const db = Number(masterVol.value);
    state.masterVolumeDb = db;
    const label = document.getElementById("master-vol-val");
    if (label) label.textContent = `${db.toFixed(1)} dB`;
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
      if (label) label.textContent = `${db.toFixed(1)} dB`;
      applyStateGains();
      // Live audio only while dragging — report to Streamlit on release.
    };
    el.onchange = () => {
      reportState(true);
    };
  });

  stemsEl.querySelectorAll<HTMLInputElement>(".mute").forEach((el) => {
    el.onchange = () => {
      const id = el.dataset.id!;
      state.muted[id] = el.checked;
      if (el.checked) {
        state.soloed[id] = false;
        const soloEl = stemsEl.querySelector<HTMLInputElement>(`.solo[data-id="${CSS.escape(id)}"]`);
        if (soloEl) soloEl.checked = false;
      }
      applyStateGains();
      reportState();
      updateBadges();
      updateMuteAllLabel();
    };
  });

  stemsEl.querySelectorAll<HTMLInputElement>(".solo").forEach((el) => {
    el.onchange = () => {
      const id = el.dataset.id!;
      state.soloed[id] = el.checked;
      if (el.checked) {
        state.muted[id] = false;
        const muteEl = stemsEl.querySelector<HTMLInputElement>(`.mute[data-id="${CSS.escape(id)}"]`);
        if (muteEl) muteEl.checked = false;
      }
      applyStateGains();
      reportState();
      updateBadges();
      updateMuteAllLabel();
    };
  });

  engine.setTimeCallback((t, dur, playing) => {
    const timeEl = document.getElementById("time");
    const seekEl = document.getElementById("seek") as HTMLInputElement | null;
    if (timeEl) timeEl.textContent = `${formatTime(t)} / ${formatTime(dur)}`;
    if (seekEl && document.activeElement !== seekEl) {
      seekEl.value = String(dur > 0 ? Math.round((t / dur) * 1000) : 0);
    }
    const playBtn = document.getElementById("btn-playpause");
    if (playBtn && !transportBusy && transportPending === null) {
      wantPlaying = playing;
      playBtn.textContent = playing ? "Pause" : "Play";
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

function updateMuteAllLabel(): void {
  const btn = document.getElementById("btn-muteall");
  if (btn) btn.textContent = allMuted() ? "Unmute All" : "Mute All";
}

function updateBadges(): void {
  document.querySelectorAll<HTMLElement>(".stem-row").forEach((row) => {
    const id = row.dataset.id!;
    const badge = row.querySelector(".badges");
    if (!badge) return;
    if (state.soloed[id]) badge.textContent = "SOLO";
    else if (state.muted[id]) badge.textContent = "MUTED";
    else badge.textContent = "";
  });
}

function waveformSvg(peaks: number[] | undefined): string {
  if (!peaks || peaks.length === 0) return "";
  const width = 200;
  const height = 48;
  const mid = height / 2;
  const n = peaks.length;
  const step = n > 1 ? width / (n - 1) : width;
  const max = Math.max(...peaks, 0.0001);
  const top: string[] = [];
  const bottom: string[] = [];
  for (let i = 0; i < n; i++) {
    const x = i * step;
    const amp = Math.min(1, peaks[i] / max) * (mid - 2);
    top.push(`${x.toFixed(1)},${(mid - amp).toFixed(1)}`);
    bottom.push(`${x.toFixed(1)},${(mid + amp).toFixed(1)}`);
  }
  const points = [...top, ...bottom.reverse()].join(" ");
  return (
    `<svg class="waveform-svg" viewBox="0 0 ${width} ${height}" ` +
    `preserveAspectRatio="none" aria-hidden="true"><polygon points="${points}" /></svg>`
  );
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function stemKey(stems: StemInfo[]): string {
  return stems.map((s) => `${s.id}|${s.url}`).join(";");
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
  };

  const stems = args.stems ?? [];
  const key = stemKey(stems);
  const status = () => document.getElementById("status");
  const nextTitle = args.trackTitle ?? "";
  if (nextTitle !== trackTitle) {
    trackTitle = nextTitle;
    updateTrackTitleDisplay();
  }

  if (key !== lastStemKey) {
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
    const masterInit = Number(args.initialMasterVolumeDb);
    state = {
      volumesDb: { ...(args.initialVolumesDb ?? {}) },
      muted: { ...(args.initialMuted ?? {}) },
      soloed: { ...(args.initialSoloed ?? {}) },
      masterVolumeDb: Number.isFinite(masterInit) ? masterInit : DB_DEFAULT,
    };
    for (const s of stems) {
      if (state.volumesDb[s.id] === undefined) state.volumesDb[s.id] = DB_DEFAULT;
      if (state.muted[s.id] === undefined) state.muted[s.id] = false;
      if (state.soloed[s.id] === undefined) state.soloed[s.id] = false;
    }
    renderUI(data.theme);
    const st = status();
    if (st) st.textContent = "Loading stems…";
    const { errors } = await engine.loadStems(stems, (loaded, total, msg) => {
      const el = status();
      if (el) el.textContent = msg || `${loaded}/${total}`;
      scheduleFrameHeight();
    });
    applyStateGains();
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
  }

  scheduleFrameHeight();
}

Streamlit.events.addEventListener(Streamlit.RENDER_EVENT, onRender);
Streamlit.setComponentReady();
scheduleFrameHeight();

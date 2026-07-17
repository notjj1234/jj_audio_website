import {
  Streamlit,
  RenderData,
  Theme,
} from "streamlit-component-lib";
import "./style.css";

const DB_MIN = -60;
const DB_MAX = 24;
const DB_DEFAULT = 0;

type StemInfo = { id: string; label: string; url: string };

type MixerState = {
  volumesDb: Record<string, number>;
  muted: Record<string, boolean>;
  soloed: Record<string, boolean>;
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
  const gains: Record<string, number> = {};
  for (const id of stemIds) {
    const db = Math.max(
      DB_MIN,
      Math.min(DB_MAX, state.volumesDb[id] ?? DB_DEFAULT)
    );
    const audible = anySolo ? !!state.soloed[id] : !state.muted[id];
    gains[id] = audible ? dbToLinear(db) : 0;
  }
  return gains;
}

class StemMixerEngine {
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

  async ensureContext(): Promise<AudioContext> {
    if (!this.ctx) {
      this.ctx = new AudioContext();
    }
    if (this.ctx.state === "suspended") {
      await this.ctx.resume();
    }
    return this.ctx;
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

    const ctx = await this.ensureContext();
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
        gain.connect(ctx.destination);
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
let state: MixerState = { volumesDb: {}, muted: {}, soloed: {} };
let stemInfos: StemInfo[] = [];

let reportTimer: number | null = null;

function reportState(immediate = false): void {
  const publish = () => {
    Streamlit.setComponentValue({
      volumesDb: { ...state.volumesDb },
      muted: { ...state.muted },
      soloed: { ...state.soloed },
    });
  };
  if (immediate) {
    if (reportTimer !== null) window.clearTimeout(reportTimer);
    reportTimer = null;
    publish();
    return;
  }
  if (reportTimer !== null) window.clearTimeout(reportTimer);
  reportTimer = window.setTimeout(publish, 250);
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
      <div class="status" id="status">Ready</div>
      <div class="transport">
        <button type="button" id="btn-play">Play</button>
        <button type="button" id="btn-pause">Pause</button>
        <button type="button" id="btn-restart">Restart</button>
        <span class="time" id="time">0:00 / 0:00</span>
      </div>
      <input type="range" id="seek" min="0" max="1000" value="0" step="1" />
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
            <strong>${escapeHtml(stem.label)}</strong>
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
        </div>`;
    })
    .join("");

  document.getElementById("btn-play")!.onclick = () => void engine.play();
  document.getElementById("btn-pause")!.onclick = () => void engine.pause();
  document.getElementById("btn-restart")!.onclick = () => void engine.restart();

  const seek = document.getElementById("seek") as HTMLInputElement;
  seek.oninput = () => {
    const dur = engine.getDuration() || 1;
    const t = (Number(seek.value) / 1000) * dur;
    void engine.seek(t);
  };

  stemsEl.querySelectorAll<HTMLInputElement>(".vol-slider").forEach((el) => {
    el.oninput = () => {
      const id = el.dataset.id!;
      const db = Number(el.value);
      state.volumesDb[id] = db;
      const label = el.parentElement?.querySelector(".vol-val");
      if (label) label.textContent = `${db.toFixed(1)} dB`;
      applyStateGains();
      reportState();
    };
  });

  stemsEl.querySelectorAll<HTMLInputElement>(".mute").forEach((el) => {
    el.onchange = () => {
      state.muted[el.dataset.id!] = el.checked;
      applyStateGains();
      reportState(true);
      updateBadges();
    };
  });

  stemsEl.querySelectorAll<HTMLInputElement>(".solo").forEach((el) => {
    el.onchange = () => {
      state.soloed[el.dataset.id!] = el.checked;
      applyStateGains();
      reportState(true);
      updateBadges();
    };
  });

  engine.setTimeCallback((t, dur, playing) => {
    const timeEl = document.getElementById("time");
    const seekEl = document.getElementById("seek") as HTMLInputElement | null;
    if (timeEl) timeEl.textContent = `${formatTime(t)} / ${formatTime(dur)}`;
    if (seekEl && document.activeElement !== seekEl) {
      seekEl.value = String(dur > 0 ? Math.round((t / dur) * 1000) : 0);
    }
    const playBtn = document.getElementById("btn-play");
    if (playBtn) playBtn.textContent = playing ? "Playing…" : "Play";
  });

  Streamlit.setFrameHeight();
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
  };

  const stems = args.stems ?? [];
  const key = stemKey(stems);
  const status = () => document.getElementById("status");

  if (key !== lastStemKey) {
    lastStemKey = key;
    stemInfos = stems;
    state = {
      volumesDb: { ...(args.initialVolumesDb ?? {}) },
      muted: { ...(args.initialMuted ?? {}) },
      soloed: { ...(args.initialSoloed ?? {}) },
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
      Streamlit.setFrameHeight();
    });
    applyStateGains();
    reportState();
    const el = status();
    if (el) {
      el.textContent = errors.length
        ? `Loaded with errors: ${errors.join("; ")}`
        : `Loaded ${stems.length} stem(s). Adjust levels while playing — playback will not restart.`;
    }
    renderUI(data.theme);
    applyStateGains();
  }

  Streamlit.setFrameHeight();
}

Streamlit.events.addEventListener(Streamlit.RENDER_EVENT, onRender);
Streamlit.setComponentReady();
Streamlit.setFrameHeight();

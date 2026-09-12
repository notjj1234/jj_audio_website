import { Streamlit, RenderData, Theme } from "streamlit-component-lib";
import WaveSurfer from "wavesurfer.js";
import RegionsPlugin from "wavesurfer.js/dist/plugins/regions.esm.js";
import type { Region } from "wavesurfer.js/dist/plugins/regions.js";
import "./style.css";

type Args = {
  audioUrl?: string;
  startSec?: number;
  endSec?: number;
  minLengthSec?: number;
  durationSec?: number | null;
  maxHintSec?: number | null;
};

type PlayResume = {
  url: string;
  startSec: number;
  endSec: number;
  wantPlaying: boolean;
};

const PLAY_STORAGE_KEY = "audiotools_region_picker_play";
const BLOB_STORAGE_PREFIX = "audiotools_region_picker_blob:";
const REPORT_DEBOUNCE_MS = 250;

/** In-memory blob URLs keyed by the Streamlit media URL string. */
const blobCache = new Map<string, string>();

function formatTime(sec: number): string {
  const s = Math.max(0, Math.floor(sec));
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${m}:${r.toString().padStart(2, "0")}`;
}

function applyTheme(theme?: Theme): void {
  if (!theme) return;
  const root = document.documentElement;
  if (theme.textColor) root.style.setProperty("--rp-fg", theme.textColor);
  if (theme.secondaryBackgroundColor) {
    root.style.setProperty("--rp-btn-bg", theme.secondaryBackgroundColor);
  }
  if (theme.primaryColor) {
    root.style.setProperty("--rp-accent", theme.primaryColor);
    root.style.setProperty("--rp-wave", theme.primaryColor);
    root.style.setProperty("--rp-progress", theme.primaryColor);
  }
}

function scheduleFrameHeight(): void {
  requestAnimationFrame(() => Streamlit.setFrameHeight());
}

function writePlayResume(payload: PlayResume): void {
  try {
    sessionStorage.setItem(PLAY_STORAGE_KEY, JSON.stringify(payload));
  } catch {
    /* ignore */
  }
}

function readPlayResume(): PlayResume | null {
  try {
    const raw = sessionStorage.getItem(PLAY_STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as PlayResume;
  } catch {
    return null;
  }
}

function clearWantPlaying(): void {
  const cur = readPlayResume();
  if (!cur) return;
  writePlayResume({ ...cur, wantPlaying: false });
}

function dropBlobCache(sourceUrl: string): void {
  const blob = blobCache.get(sourceUrl);
  if (blob) {
    try {
      URL.revokeObjectURL(blob);
    } catch {
      /* ignore */
    }
    blobCache.delete(sourceUrl);
  }
  try {
    sessionStorage.removeItem(BLOB_STORAGE_PREFIX + sourceUrl);
  } catch {
    /* ignore */
  }
}

/**
 * Resolve a durable audio URL for wavesurfer. Streamlit /media/ URLs can be
 * GC'd after remount; blob: URLs from a successful fetch survive.
 */
async function resolvePlayableUrl(sourceUrl: string): Promise<string> {
  const cached = blobCache.get(sourceUrl);
  if (cached) return cached;

  const res = await fetch(sourceUrl);
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`);
  }
  const blob = await res.blob();
  const objectUrl = URL.createObjectURL(blob);
  blobCache.set(sourceUrl, objectUrl);
  return objectUrl;
}

let wavesurfer: WaveSurfer | null = null;
let regionsPlugin: ReturnType<typeof RegionsPlugin.create> | null = null;
let activeRegion: Region | null = null;
let lastSourceUrl = "";
let suppressingReport = false;
let userPaused = false;
let lastReported = { startSec: -1, endSec: -1 };
let reportTimer: ReturnType<typeof setTimeout> | null = null;
let loadGeneration = 0;
let playBtn: HTMLButtonElement | null = null;
let metaEl: HTMLElement | null = null;
let statusEl: HTMLElement | null = null;
let hintEl: HTMLElement | null = null;

function ensureDom(): void {
  const root = document.getElementById("root");
  if (!root || root.dataset.ready === "1") return;
  root.dataset.ready = "1";
  root.innerHTML = `
    <div class="toolbar">
      <button type="button" id="rp-play" disabled>Play selection</button>
      <span class="meta" id="rp-meta"></span>
      <span class="hint" id="rp-hint"></span>
    </div>
    <div id="waveform"></div>
    <div class="status" id="rp-status">Loading waveform…</div>
  `;
  playBtn = document.getElementById("rp-play") as HTMLButtonElement;
  metaEl = document.getElementById("rp-meta");
  statusEl = document.getElementById("rp-status");
  hintEl = document.getElementById("rp-hint");
  playBtn.addEventListener("click", () => {
    if (!activeRegion || !wavesurfer) return;
    if (wavesurfer.isPlaying()) {
      userPaused = true;
      clearWantPlaying();
      wavesurfer.pause();
      playBtn!.textContent = "Play selection";
      return;
    }
    userPaused = false;
    playSelection(activeRegion, /* persist */ true);
  });
}

function updateMeta(start: number, end: number): void {
  if (!metaEl) return;
  const len = Math.max(0, end - start);
  metaEl.innerHTML = `<strong>${formatTime(start)}–${formatTime(end)}</strong> (${len.toFixed(0)} s)`;
}

function playSelection(region: Region, persist: boolean): void {
  userPaused = false;
  if (persist) {
    writePlayResume({
      url: lastSourceUrl,
      startSec: region.start,
      endSec: region.end,
      wantPlaying: true,
    });
  }
  region.play(true);
  if (playBtn) playBtn.textContent = "Pause";
}

function flushReportRegion(start: number, end: number): void {
  const startSec = Math.round(start * 10) / 10;
  const endSec = Math.round(end * 10) / 10;
  if (
    Math.abs(startSec - lastReported.startSec) < 0.05 &&
    Math.abs(endSec - lastReported.endSec) < 0.05
  ) {
    return;
  }
  lastReported = { startSec, endSec };
  updateMeta(startSec, endSec);
  Streamlit.setComponentValue({ startSec, endSec });
}

/** Debounce setComponentValue so drag-end does not remount mid-blob-fetch. */
function reportRegion(start: number, end: number): void {
  updateMeta(start, end);
  if (reportTimer != null) clearTimeout(reportTimer);
  reportTimer = setTimeout(() => {
    reportTimer = null;
    flushReportRegion(start, end);
  }, REPORT_DEBOUNCE_MS);
}

function onUserRegionUpdated(region: Region): void {
  if (suppressingReport || region.id !== "selection") return;
  reportRegion(region.start, region.end);
  playSelection(region, /* persist */ true);
}

function maybeResumePlayAfterReady(): void {
  if (!activeRegion || userPaused) return;
  const stored = readPlayResume();
  if (!stored || !stored.wantPlaying || stored.url !== lastSourceUrl) return;
  playSelection(activeRegion, /* persist */ true);
}

function syncRegion(start: number, end: number, minLength: number): void {
  if (!regionsPlugin || !wavesurfer) return;
  const dur = wavesurfer.getDuration() || end;
  let s = Math.max(0, Math.min(start, dur));
  let e = Math.max(s + minLength, Math.min(end, dur));
  if (e > dur) {
    e = dur;
    s = Math.max(0, e - minLength);
  }
  suppressingReport = true;
  try {
    if (activeRegion) {
      activeRegion.setOptions({ start: s, end: e });
    } else {
      activeRegion = regionsPlugin.addRegion({
        id: "selection",
        start: s,
        end: e,
        color: "rgba(42, 111, 106, 0.28)",
        drag: true,
        resize: true,
        minLength,
      });
      activeRegion.on("update", () => {
        if (!activeRegion) return;
        updateMeta(activeRegion.start, activeRegion.end);
      });
    }
    updateMeta(s, e);
  } finally {
    suppressingReport = false;
  }
}

function destroyWave(clearSource = true): void {
  activeRegion = null;
  regionsPlugin = null;
  if (wavesurfer) {
    wavesurfer.destroy();
    wavesurfer = null;
  }
  if (clearSource) lastSourceUrl = "";
}

async function loadWave(
  sourceUrl: string,
  start: number,
  end: number,
  minLength: number,
  maxHint: number | null,
  isRetry = false
): Promise<void> {
  const waveEl = document.getElementById("waveform");
  if (!waveEl) return;
  const gen = ++loadGeneration;
  destroyWave(false);
  lastSourceUrl = sourceUrl;
  if (statusEl) statusEl.textContent = "Loading waveform…";
  if (playBtn) playBtn.disabled = true;

  let playable: string;
  try {
    playable = await resolvePlayableUrl(sourceUrl);
  } catch (err) {
    if (gen !== loadGeneration) return;
    dropBlobCache(sourceUrl);
    if (!isRetry) {
      if (statusEl) statusEl.textContent = "Retrying audio load…";
      await loadWave(sourceUrl, start, end, minLength, maxHint, true);
      return;
    }
    lastSourceUrl = "";
    if (statusEl) statusEl.textContent = `Could not load audio: ${String(err)}`;
    scheduleFrameHeight();
    return;
  }
  if (gen !== loadGeneration) return;

  regionsPlugin = RegionsPlugin.create();
  wavesurfer = WaveSurfer.create({
    container: waveEl,
    url: playable,
    height: 96,
    waveColor: getComputedStyle(document.documentElement)
      .getPropertyValue("--rp-wave")
      .trim() || "#4a8f8a",
    progressColor: getComputedStyle(document.documentElement)
      .getPropertyValue("--rp-progress")
      .trim() || "#2a6f6a",
    cursorColor: getComputedStyle(document.documentElement)
      .getPropertyValue("--rp-accent")
      .trim() || "#2a6f6a",
    barWidth: 2,
    barGap: 1,
    barRadius: 1,
    interact: true,
    plugins: [regionsPlugin],
  });

  wavesurfer.on("ready", () => {
    if (gen !== loadGeneration) return;
    const dur = wavesurfer!.getDuration();
    const endBound = Number.isFinite(end) && end > 0 ? end : dur;
    syncRegion(start, Math.min(endBound, dur), minLength);
    if (playBtn) playBtn.disabled = false;
    if (statusEl) statusEl.textContent = "Drag the handles or the region to trim.";
    if (hintEl) {
      hintEl.textContent =
        maxHint != null && dur > maxHint
          ? `Long file — Safer: first ${maxHint.toFixed(0)} s is available above.`
          : "";
    }
    maybeResumePlayAfterReady();
    scheduleFrameHeight();
  });

  wavesurfer.on("finish", () => {
    clearWantPlaying();
    if (playBtn) playBtn.textContent = "Play selection";
  });
  wavesurfer.on("pause", () => {
    if (userPaused) clearWantPlaying();
    if (playBtn) playBtn.textContent = "Play selection";
  });
  wavesurfer.on("play", () => {
    if (playBtn) playBtn.textContent = "Pause";
  });
  wavesurfer.on("error", (err) => {
    if (gen !== loadGeneration) return;
    dropBlobCache(sourceUrl);
    destroyWave(false);
    lastSourceUrl = "";
    if (!isRetry) {
      if (statusEl) statusEl.textContent = "Retrying audio load…";
      void loadWave(sourceUrl, start, end, minLength, maxHint, true);
      return;
    }
    if (statusEl) statusEl.textContent = `Could not load audio: ${String(err)}`;
    scheduleFrameHeight();
  });

  regionsPlugin.on("region-updated", (region) => {
    onUserRegionUpdated(region);
  });
}

async function onRender(event: Event): Promise<void> {
  const data = (event as CustomEvent<RenderData>).detail;
  const args = (data.args || {}) as Args;
  applyTheme(data.theme);
  ensureDom();

  const url = String(args.audioUrl || "");
  const minLength = Math.max(0.5, Number(args.minLengthSec) || 5);
  const start = Math.max(0, Number(args.startSec) || 0);
  const end = Math.max(start + minLength, Number(args.endSec) || start + minLength);
  const maxHint =
    args.maxHintSec == null || !Number.isFinite(Number(args.maxHintSec))
      ? null
      : Number(args.maxHintSec);

  if (!url) {
    destroyWave();
    if (statusEl) statusEl.textContent = "No audio URL.";
    scheduleFrameHeight();
    return;
  }

  if (url !== lastSourceUrl || !wavesurfer) {
    await loadWave(url, start, end, minLength, maxHint);
  } else if (activeRegion) {
    const close =
      Math.abs(activeRegion.start - start) < 0.15 &&
      Math.abs(activeRegion.end - end) < 0.15;
    if (!close) {
      syncRegion(start, end, minLength);
    }
    if (hintEl && wavesurfer) {
      const dur = wavesurfer.getDuration();
      hintEl.textContent =
        maxHint != null && dur > maxHint
          ? `Long file — Safer: first ${maxHint.toFixed(0)} s is available above.`
          : "";
    }
  }

  scheduleFrameHeight();
}

Streamlit.events.addEventListener(Streamlit.RENDER_EVENT, onRender);
Streamlit.setComponentReady();
Streamlit.setFrameHeight();

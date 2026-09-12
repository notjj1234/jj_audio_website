import { useEffect, useRef } from "react";
import WaveSurfer from "wavesurfer.js";
import RegionsPlugin from "wavesurfer.js/dist/plugins/regions.esm.js";
import type { Region } from "wavesurfer.js/dist/plugins/regions.js";

type Props = {
  audioUrl: string;
  startSec: number;
  endSec: number;
  minLengthSec?: number;
  onChange: (startSec: number, endSec: number) => void;
};

function formatTime(sec: number): string {
  const s = Math.max(0, Math.floor(sec));
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${m}:${r.toString().padStart(2, "0")}`;
}

export function RegionPicker({
  audioUrl,
  startSec,
  endSec,
  minLengthSec = 5,
  onChange,
}: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const wsRef = useRef<WaveSurfer | null>(null);
  const regionRef = useRef<Region | null>(null);
  const onChangeRef = useRef(onChange);
  const boundsRef = useRef({ startSec, endSec, minLengthSec });
  const playBtnRef = useRef<HTMLButtonElement | null>(null);
  const metaRef = useRef<HTMLSpanElement | null>(null);
  const suppressingRef = useRef(false);

  onChangeRef.current = onChange;
  boundsRef.current = { startSec, endSec, minLengthSec };

  useEffect(() => {
    const el = containerRef.current;
    if (!el || !audioUrl) return;

    let cancelled = false;
    const regions = RegionsPlugin.create();
    const ws = WaveSurfer.create({
      container: el,
      url: audioUrl,
      height: 96,
      waveColor: "#4a8f8a",
      progressColor: "#2f6b4f",
      cursorColor: "#1e4533",
      barWidth: 2,
      barGap: 1,
      barRadius: 1,
      interact: true,
      plugins: [regions],
    });
    wsRef.current = ws;

    const updateMeta = (start: number, end: number) => {
      if (!metaRef.current) return;
      const len = Math.max(0, end - start);
      metaRef.current.textContent = `${formatTime(start)}–${formatTime(end)} (${len.toFixed(0)} s)`;
    };

    const syncRegion = (start: number, end: number) => {
      const dur = ws.getDuration() || end;
      const minLen = boundsRef.current.minLengthSec;
      let s = Math.max(0, Math.min(start, dur));
      let e = Math.max(s + minLen, Math.min(end, dur));
      if (e > dur) {
        e = dur;
        s = Math.max(0, e - minLen);
      }
      suppressingRef.current = true;
      try {
        if (regionRef.current) {
          regionRef.current.setOptions({ start: s, end: e });
        } else {
          const region = regions.addRegion({
            id: "selection",
            start: s,
            end: e,
            color: "rgba(47, 107, 79, 0.28)",
            drag: true,
            resize: true,
            minLength: minLen,
          });
          regionRef.current = region;
          region.on("update", () => updateMeta(region.start, region.end));
        }
        updateMeta(s, e);
      } finally {
        suppressingRef.current = false;
      }
    };

    ws.on("ready", () => {
      if (cancelled) return;
      const { startSec: s, endSec: e } = boundsRef.current;
      syncRegion(s, e);
      if (playBtnRef.current) playBtnRef.current.disabled = false;
    });

    ws.on("play", () => {
      if (playBtnRef.current) playBtnRef.current.textContent = "Pause";
    });
    ws.on("pause", () => {
      if (playBtnRef.current) playBtnRef.current.textContent = "Play selection";
    });
    ws.on("finish", () => {
      if (playBtnRef.current) playBtnRef.current.textContent = "Play selection";
    });

    regions.on("region-updated", (region) => {
      if (suppressingRef.current || region.id !== "selection") return;
      onChangeRef.current(region.start, region.end);
      region.play(true);
    });

    return () => {
      cancelled = true;
      regionRef.current = null;
      ws.destroy();
      wsRef.current = null;
    };
  }, [audioUrl]);

  useEffect(() => {
    const region = regionRef.current;
    const ws = wsRef.current;
    if (!region || !ws || !ws.getDuration()) return;
    const close =
      Math.abs(region.start - startSec) < 0.15 && Math.abs(region.end - endSec) < 0.15;
    if (close) return;
    suppressingRef.current = true;
    try {
      region.setOptions({
        start: startSec,
        end: endSec,
      });
      if (metaRef.current) {
        const len = Math.max(0, endSec - startSec);
        metaRef.current.textContent = `${formatTime(startSec)}–${formatTime(endSec)} (${len.toFixed(0)} s)`;
      }
    } finally {
      suppressingRef.current = false;
    }
  }, [startSec, endSec, minLengthSec]);

  function togglePlay() {
    const ws = wsRef.current;
    const region = regionRef.current;
    if (!ws || !region) return;
    if (ws.isPlaying()) {
      ws.pause();
      return;
    }
    region.play(true);
  }

  return (
    <div className="region-picker">
      <div className="region-picker-toolbar">
        <button
          type="button"
          className="secondary"
          ref={playBtnRef}
          disabled
          onClick={togglePlay}
        >
          Play selection
        </button>
        <span className="hint" ref={metaRef} />
      </div>
      <div className="region-picker-wave" ref={containerRef} />
      <span className="hint">Drag the handles or the region to trim.</span>
    </div>
  );
}

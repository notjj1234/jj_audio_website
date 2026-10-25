import { useEffect, useMemo, useRef, useState } from "react";
import { chartTimeSeconds, type AnalysisData, type TabData } from "../mixer/analysis";
import { PracticeSheet } from "./PracticeSheet";
import {
  DB_DEFAULT,
  DB_MAX,
  DB_MIN,
  StemMixerEngine,
  allMuted,
  anySoloed,
  applyPlaybackPreset,
  clearSolo,
  defaultMuted,
  effectiveGains,
  isAudible,
  playbackPresetAvailable,
  resetMuteSolo,
  setAllMuted,
  type MixerState,
  type PlaybackPreset,
  type StemInfo,
} from "../mixer/engine";
import {
  PAN_DEFAULT,
  PAN_MAX,
  PAN_MIN,
  clampPan,
  formatPan,
  panSpoken,
  snapPanToCenter,
} from "../mixer/pan";
import {
  PRACTICE_KEY_DEFAULT,
  PRACTICE_KEY_MAX,
  PRACTICE_KEY_MIN,
  PRACTICE_RATE_DEFAULT,
  PRACTICE_RATE_MAX,
  PRACTICE_RATE_MIN,
  PRACTICE_RATE_STEP,
  clampPracticeRate,
  clampPracticeSemitones,
  formatPracticeKeyLabel,
  formatPracticeSpeedLabel,
  loadPracticeSettings,
  savePracticeSettings,
} from "../mixer/practice";

function formatTime(sec: number): string {
  if (!isFinite(sec) || sec < 0) sec = 0;
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function rangeFillPct(value: number, min: number, max: number): string {
  const span = max - min;
  if (!Number.isFinite(span) || span <= 0 || !Number.isFinite(value)) return "0%";
  const pct = Math.max(0, Math.min(100, ((value - min) / span) * 100));
  return `${pct}%`;
}

export function StemMixer({
  stems,
  analysis = null,
  tab = null,
}: {
  stems: StemInfo[];
  analysis?: AnalysisData | null;
  tab?: TabData | null;
}) {
  const engineRef = useRef(new StemMixerEngine());
  const recorderRef = useRef<MediaRecorder | null>(null);
  const [status, setStatus] = useState("Ready");
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [seek, setSeek] = useState(0);
  const [state, setState] = useState<MixerState>({
    volumesDb: {},
    muted: {},
    soloed: {},
    masterVolumeDb: DB_DEFAULT,
    pan: {},
  });
  /** Stem whose pan slider is being dragged with a pointer (keys never snap). */
  const panDragRef = useRef<string | null>(null);
  const [mixError, setMixError] = useState<string | null>(null);
  const [mixBusy, setMixBusy] = useState(false);
  const [preset, setPreset] = useState<PlaybackPreset | "custom">("all");
  const initialPractice = loadPracticeSettings();
  const [practiceRate, setPracticeRate] = useState(initialPractice.rate);
  const [practiceSemitones, setPracticeSemitones] = useState(
    initialPractice.semitones
  );
  const [practiceStatus, setPracticeStatus] = useState<string | null>(null);
  const [mixOpen, setMixOpen] = useState(false);
  const [speedOpen, setSpeedOpen] = useState(false);
  const [sheetOpen, setSheetOpen] = useState(true);
  const mixBtnRef = useRef<HTMLButtonElement>(null);
  const speedBtnRef = useRef<HTMLButtonElement>(null);

  const stemIds = useMemo(() => stems.map((s) => s.id), [stems]);
  const stemKey = useMemo(
    () => stems.map((s) => `${s.id}|${s.url}`).join(";"),
    [stems]
  );

  const SLEEP_RESUME_HINT = "Tap Play to resume after sleep";

  useEffect(() => {
    const engine = engineRef.current;
    engine.installWakeHooks();
    engine.setSoftPauseCallback(() => {
      /* Blur and sleep are not a user Pause — keepPlaying recovery handles them. */
    });
    const practice = loadPracticeSettings();
    setPracticeRate(practice.rate);
    setPracticeSemitones(practice.semitones);
    void engine.setPracticeRate(practice.rate);
    void engine.setPracticeSemitones(practice.semitones);
    engine.setMediaInfo(
      stems.map((s) => s.label).filter(Boolean).join(" · ") || "Stem mix"
    );
    const next: MixerState = {
      volumesDb: {},
      muted: {},
      soloed: {},
      masterVolumeDb: DB_DEFAULT,
      pan: {},
    };
    for (const s of stems) {
      next.volumesDb[s.id] = DB_DEFAULT;
      next.muted[s.id] = defaultMuted(s.id);
      next.soloed[s.id] = false;
      next.pan![s.id] = PAN_DEFAULT;
    }
    setPreset("all");
    setState(next);
    setStatus("Loading stems…");
    let cancelled = false;
    void engine
      .loadStems(stems, (_l, _t, msg) => {
        if (!cancelled) setStatus(msg);
      })
      .then(({ errors }) => {
        if (cancelled) return;
        setStatus(
          errors.length
            ? `Loaded with errors: ${errors.join("; ")}`
            : `Loaded ${stems.length} stem(s)`
        );
        engine.applyGains(effectiveGains(stems.map((s) => s.id), next));
      });
    engine.setTimeCallback((t, dur, isPlaying) => {
      setCurrentTime(chartTimeSeconds(t, engine.chartLatencyMs()));
      setDuration(dur);
      setPlaying(isPlaying || engine.isKeepPlaying());
      setSeek(dur > 0 ? Math.round((t / dur) * 1000) : 0);
      if (isPlaying || engine.isKeepPlaying()) {
        setStatus((prev) => (prev === SLEEP_RESUME_HINT ? "Playing" : prev));
      }
    });
    return () => {
      cancelled = true;
      void engine.pause();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stemKey]);

  const apply = (next: MixerState) => {
    setState(next);
    engineRef.current.applyGains(effectiveGains(stemIds, next));
  };

  /** Pan never changes mute, solo, or level, so it skips `apply` (gains). */
  const setPan = (id: string, raw: number, opts?: { snap?: boolean }) => {
    const value = opts?.snap ? snapPanToCenter(raw) : clampPan(raw);
    const pan = { ...(state.pan ?? {}), [id]: value };
    setState({ ...state, pan });
    engineRef.current.applyPans(pan);
  };

  const beginPanDrag = (id: string) => {
    panDragRef.current = id;
    window.addEventListener("pointerup", endPanDrag, { once: true });
    window.addEventListener("pointercancel", endPanDrag, { once: true });
  };

  const endPanDrag = () => {
    panDragRef.current = null;
  };

  const anyPanned = stemIds.some((id) => (state.pan?.[id] ?? PAN_DEFAULT) !== PAN_DEFAULT);
  const everyMuted = allMuted(stemIds, state);
  const soloActive = anySoloed(stemIds, state);
  const canSeek = duration > 0;

  const togglePlayback = () => {
    if (playing) {
      void engineRef.current.pause().then(() => setPlaying(false));
      return;
    }
    void engineRef.current.play().then(() => {
      setPlaying(true);
      setStatus((prev) => (prev === SLEEP_RESUME_HINT ? "Playing" : prev));
    });
  };

  const recordTake = async () => {
    const current = recorderRef.current;
    if (current && current.state === "recording") {
      current.stop();
      return;
    }
    if (!window.confirm("Start the microphone and record this take?")) return;
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const recorder = new MediaRecorder(stream);
    const chunks: BlobPart[] = [];
    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) chunks.push(event.data);
    };
    recorder.onstop = () => {
      stream.getTracks().forEach((track) => track.stop());
      const blob = new Blob(chunks, { type: recorder.mimeType || "audio/webm" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "practice-take.webm";
      link.click();
      URL.revokeObjectURL(url);
      recorderRef.current = null;
    };
    recorderRef.current = recorder;
    recorder.start();
  };

  const toggleMute = (id: string) => {
    setPreset("custom");
    const muted = !state.muted[id];
    apply({
      ...state,
      muted: { ...state.muted, [id]: muted },
      soloed: muted ? { ...state.soloed, [id]: false } : state.soloed,
    });
  };

  const toggleSolo = (id: string) => {
    setPreset("custom");
    const soloed = !state.soloed[id];
    apply({
      ...state,
      soloed: { ...state.soloed, [id]: soloed },
      muted: soloed ? { ...state.muted, [id]: false } : state.muted,
    });
  };

  const applyPreset = (nextPreset: PlaybackPreset) => {
    const next = applyPlaybackPreset(stemIds, state, nextPreset);
    if (!next) return;
    setPreset(nextPreset);
    apply(next);
  };

  const hasVocals = playbackPresetAvailable(stemIds, "karaoke");
  const presetButtons: { id: PlaybackPreset; label: string }[] = [
    { id: "all", label: "All" },
    { id: "karaoke", label: "Karaoke" },
    { id: "acapella", label: "Acapella" },
    { id: "drumsBass", label: "Drums + Bass" },
  ];

  const muteAll = () => {
    setPreset("custom");
    apply(setAllMuted(stemIds, clearSolo(state), true));
  };
  const unmuteAll = () => {
    setPreset("custom");
    apply(setAllMuted(stemIds, state, false));
  };
  const masterDb = state.masterVolumeDb ?? DB_DEFAULT;

  const persistPractice = (rate: number, semitones: number) => {
    setPracticeRate(rate);
    setPracticeSemitones(semitones);
    savePracticeSettings({ rate, semitones });
  };

  const applyPracticeRate = (raw: number) => {
    const next = clampPracticeRate(raw);
    void engineRef.current.setPracticeRate(next).then((r) => {
      if (!r.ok && r.message) setPracticeStatus(r.message);
      else setPracticeStatus(null);
      const settings = engineRef.current.getPracticeSettings();
      persistPractice(settings.rate, settings.semitones);
    });
  };

  const applyPracticeKey = (raw: number) => {
    const next = clampPracticeSemitones(raw);
    void engineRef.current.setPracticeSemitones(next).then((r) => {
      if (!r.ok && r.message) setPracticeStatus(r.message);
      else setPracticeStatus(null);
      const settings = engineRef.current.getPracticeSettings();
      persistPractice(settings.rate, settings.semitones);
    });
  };

  const resetPractice = () => {
    void engineRef.current.resetPractice().then((r) => {
      if (!r.ok && r.message) setPracticeStatus(r.message);
      else setPracticeStatus(null);
      persistPractice(PRACTICE_RATE_DEFAULT, PRACTICE_KEY_DEFAULT);
    });
  };

  useEffect(() => {
    const inside = (panelId: string, button: HTMLButtonElement | null, target: Node | null) => {
      if (!target) return false;
      const panel = document.getElementById(panelId);
      return Boolean((panel && panel.contains(target)) || (button && button.contains(target)));
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      const target = event.target;
      if (target instanceof Element && target.closest("input, textarea, select")) return;
      if (!mixOpen && !speedOpen) return;
      event.preventDefault();
      const focusMix = mixOpen;
      setMixOpen(false);
      setSpeedOpen(false);
      (focusMix ? mixBtnRef : speedBtnRef).current?.focus();
    };
    const onPointer = (event: PointerEvent) => {
      const target = event.target as Node | null;
      if (mixOpen && !inside("mix-menu", mixBtnRef.current, target)) setMixOpen(false);
      if (speedOpen && !inside("practice-speed-popover", speedBtnRef.current, target)) {
        setSpeedOpen(false);
      }
    };
    const onBlur = () => {
      setMixOpen(false);
      setSpeedOpen(false);
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onPointer, true);
    window.addEventListener("blur", onBlur);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("pointerdown", onPointer, true);
      window.removeEventListener("blur", onBlur);
    };
  }, [mixOpen, speedOpen]);

  const downloadMix = async () => {
    setMixError(null);
    setMixBusy(true);
    try {
      const blob = await engineRef.current.bounceMix(state);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "current_mix.wav";
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setMixError(
        err instanceof Error ? err.message : "Could not build the current mix."
      );
    } finally {
      setMixBusy(false);
    }
  };

  return (
    <div className="mixer">
      <header className="mixer-header">
        <h2 className="section-heading">Mix &amp; preview</h2>
        <p className="mixer-status" aria-live="polite">
          {status}
        </p>
      </header>

      <div className="mixer-transport transport-sticky">
        <div className="mixer-transport-controls">
          <button
            type="button"
            className="primary live-play"
            onClick={togglePlayback}
            aria-pressed={playing}
          >
            {playing ? "Pause" : "Play"}
          </button>
          <button type="button" className="ghost" onClick={() => void recordTake()}>
            Record
          </button>
          <button
            type="button"
            className="ghost"
            onClick={() => void engineRef.current.restart()}
          >
            Restart
          </button>
          <span className="mixer-time" aria-label="Playback time">
            <span>{formatTime(currentTime)}</span>
            <span className="mixer-time-sep" aria-hidden="true">
              /
            </span>
            <span>{formatTime(duration)}</span>
          </span>
        </div>

        <label className="mixer-seek">
          <span className="visually-hidden">Seek</span>
          <input
            type="range"
            className="slider-seek"
            min={0}
            max={1000}
            value={seek}
            disabled={!canSeek}
            aria-valuetext={formatTime(currentTime)}
            style={{ ["--range-fill" as string]: rangeFillPct(seek, 0, 1000) }}
            onChange={(e) => {
              const dur = engineRef.current.getDuration() || 1;
              const t = (Number(e.target.value) / 1000) * dur;
              void engineRef.current.seek(t);
            }}
          />
        </label>
        <button
          type="button"
          className="ghost"
          aria-expanded={sheetOpen}
          aria-controls="practice-panel"
          onClick={() => setSheetOpen((open) => !open)}
        >Practice</button>
        <button
          type="button"
          className="ghost"
          ref={mixBtnRef}
          aria-expanded={mixOpen}
          aria-controls="mix-menu"
          onClick={() => setMixOpen((open) => !open)}
        >Mix</button>
        <button
          type="button"
          className="ghost"
          ref={speedBtnRef}
          aria-expanded={speedOpen}
          aria-controls="practice-speed-popover"
          onClick={() => setSpeedOpen((open) => !open)}
        >
          Speed &amp; Key
        </button>
      </div>

      <div id="mix-menu" className="mixer-master" hidden={!mixOpen}>
        <div className="mixer-presets">
          {presetButtons.map((item) => {
            const disabled =
              (item.id === "karaoke" || item.id === "acapella") && !hasVocals;
            return (
              <button
                key={item.id}
                type="button"
                className={`ghost${preset === item.id ? " active" : ""}`}
                disabled={disabled}
                aria-pressed={preset === item.id}
                onClick={() => applyPreset(item.id)}
              >
                {item.label}
              </button>
            );
          })}
        </div>
        <button
          type="button"
          className="ghost"
          onClick={everyMuted ? unmuteAll : muteAll}
        >
          {everyMuted ? "Unmute all" : "Mute all"}
        </button>
        <button
          type="button"
          className="ghost"
          onClick={() => {
            setPreset("all");
            apply(resetMuteSolo(stemIds, state));
          }}
        >
          Reset mute &amp; solo
        </button>
        {soloActive && (
          <button
            type="button"
            className="ghost"
            onClick={() => {
              setPreset("all");
              apply(clearSolo(state));
            }}
          >
            Clear solo
          </button>
        )}
        <button
          type="button"
          className="ghost"
          onClick={() => void downloadMix()}
          disabled={mixBusy || !canSeek}
        >
          {mixBusy ? "Building mix…" : "Download current mix"}
        </button>
      </div>
      <div
        id="practice-speed-popover"
        className="mixer-practice"
        hidden={!speedOpen}
        role="group"
        aria-label="Speed and Key"
        onDoubleClick={(e) => {
          if ((e.target as HTMLElement).closest("button, input")) return;
          resetPractice();
        }}
      >
        <div className="practice-heading">Speed &amp; Key</div>
        <div className="practice-row">
          <span className="practice-label">{formatPracticeSpeedLabel(practiceRate)}</span>
          <button
            type="button"
            className="ghost practice-nudge"
            aria-label="Slower"
            onClick={() => applyPracticeRate(practiceRate - PRACTICE_RATE_STEP)}
          >
            −
          </button>
          <input
            type="range"
            className="slider-speed"
            min={PRACTICE_RATE_MIN}
            max={PRACTICE_RATE_MAX}
            step={PRACTICE_RATE_STEP}
            value={practiceRate}
            style={{
              ["--range-fill" as string]: rangeFillPct(
                practiceRate,
                PRACTICE_RATE_MIN,
                PRACTICE_RATE_MAX
              ),
            }}
            onChange={(e) => applyPracticeRate(Number(e.target.value))}
          />
          <button
            type="button"
            className="ghost practice-nudge"
            aria-label="Faster"
            onClick={() => applyPracticeRate(practiceRate + PRACTICE_RATE_STEP)}
          >
            +
          </button>
        </div>
        <div className="practice-row">
          <span className="practice-label">{formatPracticeKeyLabel(practiceSemitones)}</span>
          <button
            type="button"
            className="ghost practice-nudge"
            aria-label="Lower key"
            onClick={() => applyPracticeKey(practiceSemitones - 1)}
          >
            −
          </button>
          <input
            type="range"
            className="slider-key"
            min={PRACTICE_KEY_MIN}
            max={PRACTICE_KEY_MAX}
            step={1}
            value={practiceSemitones}
            style={{
              ["--range-fill" as string]: rangeFillPct(
                practiceSemitones,
                PRACTICE_KEY_MIN,
                PRACTICE_KEY_MAX
              ),
            }}
            onChange={(e) => applyPracticeKey(Number(e.target.value))}
          />
          <button
            type="button"
            className="ghost practice-nudge"
            aria-label="Raise key"
            onClick={() => applyPracticeKey(practiceSemitones + 1)}
          >
            +
          </button>
        </div>
        <button type="button" className="ghost practice-reset" onClick={resetPractice}>
          Reset
        </button>
        {practiceStatus && (
          <p className="practice-status" aria-live="polite">
            {practiceStatus}
          </p>
        )}
      </div>
      {mixError && <p className="error">{mixError}</p>}

      <div className="mixer-stage">
        <label className="master-vol">
          <span className="master-vol-label">Master</span>
          <span className="visually-hidden">Master volume in decibels</span>
          <input
            type="range"
            className="vol-slider slider-master"
            min={DB_MIN}
            max={DB_MAX}
            step={0.5}
            value={masterDb}
            style={{
              ["--range-fill" as string]: rangeFillPct(masterDb, DB_MIN, DB_MAX),
            }}
            onChange={(e) => apply({ ...state, masterVolumeDb: Number(e.target.value) })}
          />
          <span className="stem-db" aria-hidden="true">
            {masterDb.toFixed(1)}
          </span>
        </label>
      <div className="mixer-stems">
        {stems.map((stem) => {
          const db = state.volumesDb[stem.id] ?? DB_DEFAULT;
          const pan = clampPan(state.pan?.[stem.id] ?? PAN_DEFAULT);
          const muted = !!state.muted[stem.id];
          const soloed = !!state.soloed[stem.id];
          const audible = isAudible(stem.id, stemIds, state);
          const silencedBySolo = !audible && !muted && !soloed;
          return (
            <div
              className={`stem-row${audible ? "" : " silent"}`}
              key={stem.id}
              title={
                silencedBySolo
                  ? "Silent because another stem is soloed"
                  : undefined
              }
            >
              <button
                type="button"
                className={`toggle mute${muted ? " active" : ""}`}
                aria-label={`${muted ? "Unmute" : "Mute"} ${stem.label}`}
                aria-pressed={muted}
                onClick={() => toggleMute(stem.id)}
              >
                M
              </button>
              <button
                type="button"
                className={`toggle solo${soloed ? " active" : ""}`}
                aria-label={`${soloed ? "Unsolo" : "Solo"} ${stem.label}`}
                aria-pressed={soloed}
                onClick={() => toggleSolo(stem.id)}
              >
                S
              </button>
              <strong className="stem-name">
                {stem.label}
                {silencedBySolo && (
                  <span className="visually-hidden">
                    {" "}
                    Silent because another stem is soloed
                  </span>
                )}
              </strong>
              <a
                className="stem-download"
                href={stem.url}
                download={`${stem.id}.wav`}
              >
                Download
              </a>
              <label className="stem-vol">
                <span className="visually-hidden">
                  {stem.label} volume in decibels
                </span>
                <input
                  type="range"
                  min={DB_MIN}
                  max={DB_MAX}
                  step={0.5}
                  value={db}
                  onChange={(e) =>
                    apply({
                      ...state,
                      volumesDb: {
                        ...state.volumesDb,
                        [stem.id]: Number(e.target.value),
                      },
                    })
                  }
                />
                <span className="stem-db" aria-hidden="true">
                  {db.toFixed(1)}
                </span>
              </label>
              <label
                className="stem-pan"
                title="Pan: drag, use arrow keys, or double-click to center"
              >
                <span className="pan-name" aria-hidden="true">
                  Pan
                </span>
                <span className="visually-hidden">{stem.label} pan</span>
                <input
                  type="range"
                  className="pan-slider"
                  min={PAN_MIN}
                  max={PAN_MAX}
                  step={1}
                  value={pan}
                  aria-valuetext={panSpoken(pan)}
                  onPointerDown={() => beginPanDrag(stem.id)}
                  onKeyDown={endPanDrag}
                  onBlur={endPanDrag}
                  onChange={(e) =>
                    setPan(stem.id, Number(e.target.value), {
                      snap: panDragRef.current === stem.id,
                    })
                  }
                  onDoubleClick={() => setPan(stem.id, PAN_DEFAULT)}
                />
                <span className="pan-val" aria-hidden="true">
                  {formatPan(pan)}
                </span>
              </label>
            </div>
          );
        })}
      </div>
      {anyPanned && (
        <p className="hint">Download current mix includes your pan.</p>
      )}
      </div>
      <PracticeSheet
        id="practice-panel"
        hidden={!sheetOpen}
        analysis={analysis}
        tab={tab}
        currentTime={currentTime}
        playing={playing}
        onSeek={(time) => {
          void engineRef.current.seek(time);
        }}
      />
    </div>
  );
}

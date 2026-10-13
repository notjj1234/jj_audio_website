import { useEffect, useMemo, useRef, useState } from "react";
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

export function StemMixer({ stems }: { stems: StemInfo[] }) {
  const engineRef = useRef(new StemMixerEngine());
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
  });
  const [mixError, setMixError] = useState<string | null>(null);
  const [mixBusy, setMixBusy] = useState(false);
  const [preset, setPreset] = useState<PlaybackPreset | "custom">("all");
  const initialPractice = loadPracticeSettings();
  const [practiceRate, setPracticeRate] = useState(initialPractice.rate);
  const [practiceSemitones, setPracticeSemitones] = useState(
    initialPractice.semitones
  );
  const [practiceStatus, setPracticeStatus] = useState<string | null>(null);

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
    };
    for (const s of stems) {
      next.volumesDb[s.id] = DB_DEFAULT;
      next.muted[s.id] = defaultMuted(s.id);
      next.soloed[s.id] = false;
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
      setCurrentTime(t);
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
            className="primary"
            onClick={togglePlayback}
            aria-pressed={playing}
          >
            {playing ? "Pause" : "Play"}
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
            onChange={(e) =>
              apply({ ...state, masterVolumeDb: Number(e.target.value) })
            }
          />
          <span className="stem-db" aria-hidden="true">
            {masterDb.toFixed(1)}
          </span>
        </label>
        <div
          className="mixer-practice"
          role="group"
          aria-label="Practice"
          onDoubleClick={(e) => {
            if ((e.target as HTMLElement).closest("button, input")) return;
            resetPractice();
          }}
        >
          <div className="practice-row">
            <span className="practice-label">
              {formatPracticeSpeedLabel(practiceRate)}
            </span>
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
              min={PRACTICE_RATE_MIN}
              max={PRACTICE_RATE_MAX}
              step={PRACTICE_RATE_STEP}
              value={practiceRate}
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
            <span className="practice-label">
              {formatPracticeKeyLabel(practiceSemitones)}
            </span>
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
              min={PRACTICE_KEY_MIN}
              max={PRACTICE_KEY_MAX}
              step={1}
              value={practiceSemitones}
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
          <button type="button" className="ghost" onClick={resetPractice}>
            Reset practice
          </button>
          {practiceStatus && (
            <p className="practice-status" aria-live="polite">
              {practiceStatus}
            </p>
          )}
        </div>
      </div>

      <div className="mixer-master">
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
      {mixError && <p className="error">{mixError}</p>}

      <div className="mixer-stems">
        {stems.map((stem) => {
          const db = state.volumesDb[stem.id] ?? DB_DEFAULT;
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
            </div>
          );
        })}
      </div>
    </div>
  );
}

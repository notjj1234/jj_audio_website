import { useEffect, useMemo, useRef, useState } from "react";
import {
  DB_DEFAULT,
  DB_MAX,
  DB_MIN,
  StemMixerEngine,
  allMuted,
  anySoloed,
  clearSolo,
  effectiveGains,
  isAudible,
  resetMuteSolo,
  setAllMuted,
  type MixerState,
  type StemInfo,
} from "../mixer/engine";

function formatTime(sec: number): string {
  if (!isFinite(sec) || sec < 0) sec = 0;
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
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

  const stemIds = useMemo(() => stems.map((s) => s.id), [stems]);
  const stemKey = useMemo(
    () => stems.map((s) => `${s.id}|${s.url}`).join(";"),
    [stems]
  );

  useEffect(() => {
    const engine = engineRef.current;
    engine.installWakeHooks();
    engine.setSoftPauseCallback(() => {
      setPlaying(false);
      setStatus("Tap Play to resume after sleep");
    });
    const next: MixerState = {
      volumesDb: {},
      muted: {},
      soloed: {},
      masterVolumeDb: DB_DEFAULT,
    };
    for (const s of stems) {
      next.volumesDb[s.id] = DB_DEFAULT;
      next.muted[s.id] = false;
      next.soloed[s.id] = false;
    }
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
      setPlaying(isPlaying);
      setSeek(dur > 0 ? Math.round((t / dur) * 1000) : 0);
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
      void engineRef.current.pause();
      return;
    }
    void engineRef.current.play();
  };

  const toggleMute = (id: string) => {
    const muted = !state.muted[id];
    apply({
      ...state,
      muted: { ...state.muted, [id]: muted },
      soloed: muted ? { ...state.soloed, [id]: false } : state.soloed,
    });
  };

  const toggleSolo = (id: string) => {
    const soloed = !state.soloed[id];
    apply({
      ...state,
      soloed: { ...state.soloed, [id]: soloed },
      muted: soloed ? { ...state.muted, [id]: false } : state.muted,
    });
  };

  const muteAll = () => apply(setAllMuted(stemIds, clearSolo(state), true));
  const unmuteAll = () => apply(setAllMuted(stemIds, state, false));
  const masterDb = state.masterVolumeDb ?? DB_DEFAULT;

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
          <button type="button" onClick={togglePlayback} aria-pressed={playing}>
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
            min={0}
            max={1000}
            value={seek}
            disabled={!canSeek}
            aria-valuetext={formatTime(currentTime)}
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
            min={DB_MIN}
            max={DB_MAX}
            step={0.5}
            value={masterDb}
            onChange={(e) =>
              apply({ ...state, masterVolumeDb: Number(e.target.value) })
            }
          />
          <span className="stem-db" aria-hidden="true">
            {masterDb.toFixed(1)}
          </span>
        </label>
      </div>

      <div className="mixer-master">
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
          onClick={() => apply(resetMuteSolo(stemIds, state))}
        >
          Reset mute &amp; solo
        </button>
        {soloActive && (
          <button
            type="button"
            className="ghost"
            onClick={() => apply(clearSolo(state))}
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

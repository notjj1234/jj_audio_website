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
  const [timeLabel, setTimeLabel] = useState("0:00 / 0:00");
  const [playing, setPlaying] = useState(false);
  const [seek, setSeek] = useState(0);
  const [state, setState] = useState<MixerState>({
    volumesDb: {},
    muted: {},
    soloed: {},
  });

  const stemIds = useMemo(() => stems.map((s) => s.id), [stems]);
  const stemKey = useMemo(
    () => stems.map((s) => `${s.id}|${s.url}`).join(";"),
    [stems]
  );

  useEffect(() => {
    const engine = engineRef.current;
    const next: MixerState = { volumesDb: {}, muted: {}, soloed: {} };
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
      setTimeLabel(`${formatTime(t)} / ${formatTime(dur)}`);
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

  return (
    <div className="mixer">
      <h2 className="section-heading">Mix &amp; preview</h2>
      <div className="status">{status}</div>

      <div className="transport-sticky">
        <div className="transport">
          <button type="button" onClick={() => void engineRef.current.play()}>
            {playing ? "Playing…" : "Play"}
          </button>
          <button
            type="button"
            className="secondary"
            onClick={() => void engineRef.current.pause()}
          >
            Pause
          </button>
          <button
            type="button"
            className="secondary"
            onClick={() => void engineRef.current.restart()}
          >
            Restart
          </button>
          <span className="time">{timeLabel}</span>
        </div>

        <input
          type="range"
          min={0}
          max={1000}
          value={seek}
          onChange={(e) => {
            const dur = engineRef.current.getDuration() || 1;
            const t = (Number(e.target.value) / 1000) * dur;
            void engineRef.current.seek(t);
          }}
        />
      </div>

      <div className="master">
        <button
          type="button"
          className="secondary"
          onClick={everyMuted ? unmuteAll : muteAll}
        >
          {everyMuted ? "Unmute All" : "Mute All"}
        </button>
        <button
          type="button"
          className="secondary"
          onClick={() => apply(resetMuteSolo(stemIds, state))}
        >
          Reset mix
        </button>
        <button
          type="button"
          className="secondary"
          onClick={() => apply(clearSolo(state))}
          disabled={!soloActive}
        >
          Clear solo
        </button>
        <span
          className="master-hint"
          style={{ visibility: soloActive ? "visible" : "hidden" }}
        >
          Solo active — only soloed stems play (mutes ignored)
        </span>
      </div>

      <div className="stems">
        {stems.map((stem) => {
          const db = state.volumesDb[stem.id] ?? DB_DEFAULT;
          const muted = !!state.muted[stem.id];
          const soloed = !!state.soloed[stem.id];
          const audible = isAudible(stem.id, stemIds, state);
          return (
            <div
              className={`stem-row${audible ? "" : " silent"}`}
              key={stem.id}
            >
              <div className="stem-head">
                <strong>{stem.label}</strong>
                <span className="badges">
                  {soloed && <span className="badge solo">SOLO</span>}
                  {muted && <span className="badge muted">MUTED</span>}
                  {!audible && !muted && !soloed && (
                    <span className="badge muted">SILENT</span>
                  )}
                </span>
              </div>
              <label className="field">
                Volume (dB) — {db.toFixed(1)}
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
              </label>
              <div className="toggles">
                <button
                  type="button"
                  className={`toggle mute${muted ? " active" : ""}`}
                  aria-pressed={muted}
                  onClick={() => toggleMute(stem.id)}
                >
                  {muted ? "Muted" : "Mute"}
                </button>
                <button
                  type="button"
                  className={`toggle solo${soloed ? " active" : ""}`}
                  aria-pressed={soloed}
                  onClick={() => toggleSolo(stem.id)}
                >
                  {soloed ? "Soloed" : "Solo"}
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

# Third-party SDK / dependency audit

**Last updated:** 17 October 2026  
**Operator:** Orallo John James Dalton Alvarez · orallojohnjames@gmail.com  

Re-audit this file when adding trackers, payment SDKs, crash reporters, or email providers.

## Website (`web/package.json`)

| Package | Role | Network / privacy notes |
|---------|------|-------------------------|
| `react`, `react-dom`, `react-router-dom` | UI / routing | No phone-home |
| `wavesurfer.js` | Waveform UI | Runs in the browser on your audio |
| `@soundtouchjs/audio-worklet` | Playback pitch/tempo | Local in browser |
| Vite, Vitest, TypeScript (dev) | Build / test | Development only |

**Not present in this demo:** Google Analytics, Meta Pixel, Stripe, Intercom, Sentry, marketing pixels.

## Backend

Typical stack: FastAPI, SQLAlchemy, Redis/arq workers, optional MinIO/S3-compatible storage, ML libraries (e.g. Demucs / torch) for jobs. Uploads and artifacts live in configured object storage. There is **no** marketing email provider in-repo today (unsubscribe in email is Future if email is added).

## Desktop

Streamlit + local engine; bundled Satoshi fonts (no CDN). Mixer / region / mix-tabs iframe frontends ship committed Vite builds; `node_modules` are not shipped to end users. A native wrapper (e.g. pywebview) may use the system webview (OS-managed).

## Fonts and images

See [NOTICES.md](./NOTICES.md).

## Contact

Questions about this inventory: orallojohnjames@gmail.com

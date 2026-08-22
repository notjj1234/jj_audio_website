# Audio Tools

Local tools for **audio isolation** (Demucs stems + mixer) and **guitar tab PDFs**. Processing runs on your computer. Isolation is slow on CPU — start with clips ≤90 s and Quality **fast**.

Python **3.10–3.12** (3.11 recommended), **ffmpeg** on PATH, **16 GB RAM** preferred (8 GB minimum). **Desktop demo:** install the `.pkg` or Windows zip below (or run `./scripts/dev.sh tester`). **Mobile demo:** no native app — use the [hosted website](#website) in Safari or Chrome.

After the UI opens: sidebar → **Audio Isolation** → upload a short clip → **Separate tracks**.

---

## Demo testing

| Platform | How testers try it |
|----------|-------------------|
| **Apple Silicon Mac** | `AudioTools-macos-arm64.pkg` (macOS 12+) |
| **Intel Mac** | `AudioTools-macos-x64.pkg` (macOS 12+) |
| **Windows 10 / 11** | `AudioTools-windows-x64.zip` → `AudioTools.exe` (x64 only) |
| **Linux** | Run from source only — no installer ([Linux install](#linux-install)) |
| **iOS / Android** | No APK or IPA — open your deployed website URL in a mobile browser ([Mobile](#mobile-ios--android)) |

Tester runbook: [`DESKTOP.md`](DESKTOP.md). Website deploy: [`DEPLOY.md`](DEPLOY.md).

### Download & install (terminal)

Pick **one** block for your machine. Requires macOS **12+** or Windows **10/11 x64**. Builds are unsigned — see Gatekeeper / SmartScreen notes inside each block.

**Apple Silicon Mac (M1/M2/M3/M4)**

```bash
# Download (GitHub Release — or use a .pkg a maintainer sent you)
curl -fL -o ~/Downloads/AudioTools-macos-arm64.pkg \
  "https://github.com/notjj1234/jj_audio_website/releases/latest/download/AudioTools-macos-arm64.pkg"

# Install into /Applications (prompts for password)
sudo installer -pkg ~/Downloads/AudioTools-macos-arm64.pkg -target /

# First launch (right-click → Open in Finder if Gatekeeper blocks)
xattr -dr com.apple.quarantine /Applications/AudioTools.app 2>/dev/null || true
open /Applications/AudioTools.app
```

In Finder: double-click the `.pkg` → **Install** → open **AudioTools** from Applications. No disk image is mounted.

**Intel Mac**

```bash
curl -fL -o ~/Downloads/AudioTools-macos-x64.pkg \
  "https://github.com/notjj1234/jj_audio_website/releases/latest/download/AudioTools-macos-x64.pkg"

sudo installer -pkg ~/Downloads/AudioTools-macos-x64.pkg -target /

xattr -dr com.apple.quarantine /Applications/AudioTools.app 2>/dev/null || true
open /Applications/AudioTools.app
```

**Windows 10 / 11 (PowerShell)**

```powershell
# Download
curl.exe -fL -o "$env:USERPROFILE\Downloads\AudioTools-windows-x64.zip" `
  "https://github.com/notjj1234/jj_audio_website/releases/latest/download/AudioTools-windows-x64.zip"

# Unzip (keep the whole folder — AudioTools.exe needs _internal next to it)
Expand-Archive -Path "$env:USERPROFILE\Downloads\AudioTools-windows-x64.zip" `
  -DestinationPath "$env:USERPROFILE\Downloads\AudioTools" -Force

# Launch (SmartScreen: More info → Run anyway if prompted)
Start-Process "$env:USERPROFILE\Downloads\AudioTools\AudioTools.exe"
```

If the window is blank, install [WebView2](https://go.microsoft.com/fwlink/p/?LinkId=2124703) and try again.

---

## macOS install

### Run from source

```bash
brew install python@3.11 ffmpeg
chmod +x scripts/dev.sh
./scripts/dev.sh tester
```

Opens http://127.0.0.1:8501. This is a **local demo only** — it does **not** create a `.pkg` installer.

### Put the installer in Downloads

**From a published GitHub Release** (`desktop-v*` — see [GitHub Release](#github-release)):

```bash
# Apple Silicon (M1/M2/M3/M4)
curl -fL -o ~/Downloads/AudioTools-macos-arm64.pkg \
  "https://github.com/notjj1234/jj_audio_website/releases/latest/download/AudioTools-macos-arm64.pkg"

# Intel Mac
# curl -fL -o ~/Downloads/AudioTools-macos-x64.pkg \
#   "https://github.com/notjj1234/jj_audio_website/releases/latest/download/AudioTools-macos-x64.pkg"
```

**From a local PyInstaller build** (no GitHub Release required). `make_pkg.sh` does **not** run PyInstaller; it wraps `dist/AudioTools/` and writes the `.pkg` to **Downloads**:

```bash
chmod +x packaging/make_pkg.sh
./packaging/make_pkg.sh
```

If `dist/AudioTools/` is missing or stale, run the full [Build the `.pkg`](#build-the-pkg) block first.

Then confirm the file:

```bash
open ~/Downloads
ls -lh ~/Downloads/AudioTools-*-macos-*.pkg
```

### Install the `.pkg`

Requires **macOS 12 or later**. Apple Silicon and Intel are **separate** files — an arm64 `.pkg` will not run on an Intel Mac.

1. Open the matching installer from **Downloads**: `AudioTools-…-macos-arm64.pkg` (M1/M2/M3/M4) or `AudioTools-…-macos-x64.pkg` (Intel). GitHub Releases use the unversioned names `AudioTools-macos-arm64.pkg` / `AudioTools-macos-x64.pkg`.
2. Double-click → follow **Installer** → **Install** (may ask for your password). The app lands in **Applications**.
3. Launch **AudioTools** from Applications / Spotlight.
4. If Gatekeeper blocks: right-click → **Open**. Builds are **unsigned / not notarized**.

The installed app opens in its own **Audio Tools** window — no browser tab and no `127.0.0.1` URL to paste; clicking the icon again focuses that window instead of starting a second copy, and closing it shuts the local server down.

First launch downloads Demucs weights (needs network once). Stems save under `~/Library/Application Support/AudioTools/runs`.

### Build the `.pkg`

**Prerequisites**

- macOS build machine matching the chip you want to ship (Apple Silicon → `arm64` pkg; Intel Mac → `x64` pkg). There is no universal `.pkg`.
- Python 3.11, ~5 GB free disk, network on first build (PyTorch / ffmpeg download)
- App icon assets are in repo (`packaging/icon.png`, `.icns`, `.ico`). To replace the logo, update `packaging/icon.png` and run `./packaging/generate_icons.sh`.

```bash
python3.11 -m venv .venv-desktop
source .venv-desktop/bin/activate
pip install -U pip
pip install -e ".[demucs,desktop]"

make mixer-build   # if ui/stem_mixer_component/frontend/build/ is missing
make desktop-bundle-ffmpeg
make desktop-build
make desktop-pkg
```

Or the same steps without Make: `python packaging/bundle_ffmpeg.py`, `pyinstaller packaging/audio_tools.spec --noconfirm --clean`, `./packaging/make_pkg.sh`.

**Output:** `~/Downloads/AudioTools-1.0.0-macos-arm64.pkg` or `~/Downloads/AudioTools-1.0.0-macos-x64.pkg` (default version **1.0.0**). Then follow [Install the `.pkg`](#install-the-pkg).

To re-wrap an existing `dist/` into Downloads without rebuilding PyInstaller: `./packaging/make_pkg.sh`. Override the destination with `AUDIO_TOOLS_OUTPUT_DIR=/path ./packaging/make_pkg.sh`. Override the version in the filename / Info.plist with `AUDIO_TOOLS_VERSION=0.6 ./packaging/make_pkg.sh`.

Maintainer fallback (disk image, leaves a volume until ejected): `make desktop-dmg` / `./packaging/make_dmg.sh`.

---

## Windows install

### Run from source

```powershell
# Python 3.11 from python.org (not 3.13)
winget install Gyan.FFmpeg
.\scripts\dev.ps1 tester
```

If PowerShell blocks the script: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

Opens http://127.0.0.1:8501. This is a **local demo only** — it does **not** create a zip or `.exe` installer.

### Put the installer in Downloads

**From a published GitHub Release:**

```powershell
curl.exe -fL -o "$env:USERPROFILE\Downloads\AudioTools-windows-x64.zip" `
  "https://github.com/notjj1234/jj_audio_website/releases/latest/download/AudioTools-windows-x64.zip"

explorer "$env:USERPROFILE\Downloads"
```

If there is no release yet, [build the package](#build-the-windows-package-portable-exe) instead — that command already writes the zip to **Downloads**.

### Install the `.exe`

One zip covers **Windows 10 and Windows 11** (64-bit Intel/AMD). There is no Windows ARM build.

1. Unzip **`%USERPROFILE%\Downloads\AudioTools-windows-x64.zip`**.
2. Run `AudioTools.exe` from the extracted folder (keep `_internal` next to the exe).
3. If SmartScreen appears: **More info → Run anyway**.
4. If the window is blank or the app falls back to a browser: install [Microsoft Edge WebView2 Runtime](https://go.microsoft.com/fwlink/p/?LinkId=2124703) (already included on Windows 11 and recent Windows 10).

First launch downloads Demucs weights. Stems save under `%LOCALAPPDATA%\AudioTools\runs`.

### Build the Windows package (portable `.exe`)

This is a **portable zip**, not an MSI or Setup wizard — same layout as CI.

**Prerequisites**

- Windows build machine (x64)
- Python 3.11, ffmpeg, ~5 GB free disk, network on first build (PyTorch / ffmpeg download)
- App icon assets are in repo (`packaging/icon.ico`). To replace the logo, update `packaging/icon.png` and run `./packaging/generate_icons.sh` on macOS (or regenerate `.ico` separately on Windows).

```powershell
py -3.11 -m venv .venv-desktop
.\.venv-desktop\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install --upgrade torch torchaudio --index-url https://download.pytorch.org/whl/cpu
pip install -e ".[demucs,desktop]"

python packaging/bundle_ffmpeg.py
pyinstaller packaging/audio_tools.spec --noconfirm --clean
Compress-Archive -Path dist\AudioTools\* -DestinationPath "$env:USERPROFILE\Downloads\AudioTools-windows-x64.zip" -Force

explorer "$env:USERPROFILE\Downloads"
```

**Output:** `%USERPROFILE%\Downloads\AudioTools-windows-x64.zip`. Unzip in Downloads and run `AudioTools.exe`.

---

## Linux install

Desktop `.dmg` / `.exe` are not built for Linux. Run from source:

```bash
sudo apt install python3.11 python3.11-venv ffmpeg
chmod +x scripts/dev.sh
./scripts/dev.sh tester
```

Opens http://127.0.0.1:8501.

---

## Mobile (iOS / Android)

**No native mobile builds.** This project does not produce Android APK/AAB or iOS IPA/TestFlight packages — there is no Gradle, Capacitor, React Native, or Xcode project in the repo.

Demucs isolation needs desktop or server CPU and RAM (8–16 GB). It does not run on phones in this stack.

**Mobile demo alternative:** deploy the [website](#website) stack and share the public URL. Testers open it in Safari (iOS) or Chrome (Android). Processing runs on your server, not on the device.

---

## GitHub Release

To ship desktop builds to testers:

```bash
git tag desktop-v1.0.0
git push origin desktop-v1.0.0
```

CI ([`.github/workflows/desktop-release.yml`](.github/workflows/desktop-release.yml)) builds and attaches **three** artifacts:

- `AudioTools-macos-arm64.pkg` — Apple Silicon (CI: `macos-14`)
- `AudioTools-macos-x64.pkg` — Intel Mac (CI: `macos-15-intel`; `macos-13` is retired)
- `AudioTools-windows-x64.zip` — Windows 10/11 x64

Download each file from the release page (browser saves to **Downloads**), or from a terminal:

```bash
# macOS Apple Silicon
curl -fL -o ~/Downloads/AudioTools-macos-arm64.pkg \
  "https://github.com/notjj1234/jj_audio_website/releases/latest/download/AudioTools-macos-arm64.pkg"
```

```powershell
# Windows
curl.exe -fL -o "$env:USERPROFILE\Downloads\AudioTools-windows-x64.zip" `
  "https://github.com/notjj1234/jj_audio_website/releases/latest/download/AudioTools-windows-x64.zip"
```

You can also run **desktop-release** via workflow_dispatch without a tag. The release is created as a **draft** — publish manually after smoke-testing on each platform.

More tester notes: [`DESKTOP.md`](DESKTOP.md).

---

## Website

Hosted stack is FastAPI + React + Caddy — not the Streamlit desktop app. Use this path for mobile browser demos and multi-user hosting.

```bash
cp .env.example .env    # set ATT_SECRET_KEY, admin password, ATT_SITE_ADDRESS
docker compose up -d --build
```

Details: [`DEPLOY.md`](DEPLOY.md). Local SPA: `make backend` and `cd web && npm install && npm run dev`.

---

## CLI (optional)

```bash
pip install -e ".[demucs]"
export PYTHONPATH=src

audio-isolate --audio song.wav --output ./output/stems --quality fast
audio-pipeline --audio song.wav --output ./output --no-separate   # solo guitar tab PDF
```

Tab PDFs work best on solo acoustic guitar (draft, not a finished transcription). YouTube: `audio-pipeline --url "…" --output ./output` — you are responsible for rights.

---

## Known limits

- Isolation is CPU-bound and often takes about as long as the track
- `htdemucs_6s` piano often bleeds; Lead/Rhythm split is best-effort
- Tab v1: standard tuning only; no bends/slides/HOs
- Desktop builds are unsigned / not notarized — Gatekeeper (Mac) and SmartScreen (Windows) will warn. Not on the App Store or Play Store (see [Mobile](#mobile-ios--android) for why there is no phone app)
- Three separate builds (arm64 Mac, x64 Mac, x64 Windows) — not one universal installer

MIT

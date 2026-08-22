# Desktop / local tester runbook

Run **Audio Isolation** and **Tab PDF** on your own computer at $0 hosting.
Processing uses your CPU (Demucs). No cloud VM, no Docker, no accounts.

**Installer testers** (`.pkg` / Windows zip): skip the Python/ffmpeg table below — see [Which installer to download](#which-installer-to-download).

For the website stack (FastAPI + React + Caddy), see [`DEPLOY.md`](DEPLOY.md) — that is a different product path.

## Requirements

| Item | Notes |
|------|--------|
| RAM | **16 GB preferred**. **8 GB minimum** — use short clips (≤90 s) and Quality **fast**. |
| Python | **3.10–3.12 only** (3.11 recommended). Not 3.13. |
| ffmpeg | Full/shared build on PATH (Homebrew, apt, or Windows Gyan.FFmpeg — not essentials-only). |
| Disk | ~5 GB free for venv + PyTorch; more for Demucs weights on first run. |
| Node | **Not required** for testers — the stem mixer frontend is already built in-repo. |

## One-command start

### macOS

```bash
brew install python@3.11 ffmpeg
chmod +x scripts/dev.sh
./scripts/dev.sh tester
```

### Linux

```bash
# Ubuntu/Debian example:
sudo apt install python3.11 python3.11-venv ffmpeg
chmod +x scripts/dev.sh
./scripts/dev.sh tester
```

### Windows (PowerShell)

```powershell
# One-time: Python 3.11 from https://www.python.org/downloads/ (not 3.13)
# One-time: winget install Gyan.FFmpeg
.\scripts\dev.ps1 tester
```

If PowerShell blocks scripts: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

`tester` runs: preflight → create `.venv311` + install Demucs if needed → download models once → open Streamlit at **http://127.0.0.1:8501**.

Contributor install (tests/eval extras): `make install` / `./scripts/dev.sh install` / `.\scripts\dev.ps1 install`.

## First run

1. **pip / PyTorch** — first install can download ~2 GB (CPU wheels on Windows/Linux).
2. **Demucs weights** — `tester` prewarms `htdemucs_6s` (default 6-stem model). Extra models download if you pick other track presets.
3. Open **Audio Isolation**, upload a **≤90 s** clip first, leave Quality on **fast**, click **Separate tracks**.
4. Use the live mixer; download stems or a mix.

CPU separation often takes about as long as the song (or longer). Streamlit **Stop** may abort the page run, but a heavy Demucs child process can keep running until it finishes.

## Which installer to download

These are **three separate builds**. Send testers only the file that matches their machine.

| Tester machine | File | Notes |
|----------------|------|--------|
| Apple Silicon Mac (M1–M4) | `AudioTools-macos-arm64.pkg` | macOS **12+**. Double-click → **Install**. Open from Applications (right-click → **Open** if Gatekeeper blocks). |
| Intel Mac | `AudioTools-macos-x64.pkg` | Same install steps. An arm64 pkg will not launch here. |
| Windows 10 or 11 (x64) | `AudioTools-windows-x64.zip` | Unzip → run `AudioTools.exe`. SmartScreen: **More info → Run anyway**. Needs [WebView2](https://go.microsoft.com/fwlink/p/?LinkId=2124703) (already on Windows 11 and recent Windows 10). |

Builds are **unsigned / not notarized**. No Windows ARM build. No App Store.

Published under a `desktop-v*` GitHub Release (draft until a maintainer publishes). `workflow_dispatch` also produces the three artifacts without a tag.

## Download & install (terminal)

Use the file that matches your OS. Versioned local builds look like `AudioTools-0.6-macos-arm64.pkg`; GitHub Release assets use the unversioned names below.

### Apple Silicon Mac (M1–M4)

```bash
curl -fL -o ~/Downloads/AudioTools-macos-arm64.pkg \
  "https://github.com/notjj1234/jj_audio_website/releases/latest/download/AudioTools-macos-arm64.pkg"

sudo installer -pkg ~/Downloads/AudioTools-macos-arm64.pkg -target /

xattr -dr com.apple.quarantine /Applications/AudioTools.app 2>/dev/null || true
open /Applications/AudioTools.app
```

Finder: double-click the `.pkg` → **Install**. No disk image is mounted (nothing to eject).

If Gatekeeper still blocks: Finder → Applications → **AudioTools** → right-click → **Open** once.

### Intel Mac

```bash
curl -fL -o ~/Downloads/AudioTools-macos-x64.pkg \
  "https://github.com/notjj1234/jj_audio_website/releases/latest/download/AudioTools-macos-x64.pkg"

sudo installer -pkg ~/Downloads/AudioTools-macos-x64.pkg -target /

xattr -dr com.apple.quarantine /Applications/AudioTools.app 2>/dev/null || true
open /Applications/AudioTools.app
```

### Windows 10 / 11 (PowerShell)

```powershell
curl.exe -fL -o "$env:USERPROFILE\Downloads\AudioTools-windows-x64.zip" `
  "https://github.com/notjj1234/jj_audio_website/releases/latest/download/AudioTools-windows-x64.zip"

Expand-Archive -Path "$env:USERPROFILE\Downloads\AudioTools-windows-x64.zip" `
  -DestinationPath "$env:USERPROFILE\Downloads\AudioTools" -Force

Start-Process "$env:USERPROFILE\Downloads\AudioTools\AudioTools.exe"
```

SmartScreen: **More info → Run anyway**. Missing window? Install [WebView2](https://go.microsoft.com/fwlink/p/?LinkId=2124703).

## Installer first run

1. First launch needs internet once to download Demucs weights (several minutes). Later runs reuse the cache.
2. Open **Audio Isolation**, upload a **≤90 s** clip, leave speed on **Faster**, click **Separate tracks**.
3. Confirm the live mixer stays open when you mute/solo; try **Custom** under “What to separate”; download a stem or zip.

CPU separation often takes about as long as the song (or longer).

Installer data dirs (not the same as `make tester`):

| | macOS app | Windows exe |
|--|-----------|-------------|
| Stems / runs | `~/Library/Application Support/AudioTools/runs` | `%LOCALAPPDATA%\AudioTools\runs` |
| Demucs weights | `~/Library/Caches/AudioTools/torch` | `%LOCALAPPDATA%\AudioTools\models` |
| Logs | `~/Library/Application Support/AudioTools/logs` | `%LOCALAPPDATA%\AudioTools\logs` |

## Smoke test matrix (expected)

| Platform | Build | Must pass |
|----------|-------|-----------|
| M-series Mac | arm64 pkg | Native window opens; upload ≤90 s; Separate tracks; mixer stays open; Custom preset; downloads work |
| Intel Mac | x64 pkg | Same as above |
| Win10 x64 | zip/exe | Same; SmartScreen bypass documented; WebView2 present or Evergreen installer linked |
| Win11 x64 | zip/exe | Same |

Known limitations to tell testers: unsigned binaries, first-run model download, **16 GB RAM preferred** (8 GB: short clips + Faster).

## Model cache path (run from source)

When using `./scripts/dev.sh tester` / `.\scripts\dev.ps1 tester` (not the installer), weights land under Torch’s default cache unless you set `TORCH_HOME`:

- macOS / Linux: `~/.cache/torch` (or `$TORCH_HOME`)
- Windows: `%USERPROFILE%\.cache\torch` (or `%TORCH_HOME%`)

UI run folders default to `data/ui_runs/` in the repo. Override with `AUDIO_TOOLS_DATA_DIR`.

## Maintainer: build desktop packages

macOS (this repo’s Makefile targets):

```bash
python3.11 -m venv .venv-desktop
source .venv-desktop/bin/activate
pip install -e ".[demucs,desktop]"
make mixer-build          # if frontend/build is missing
make desktop-bundle-ffmpeg
make desktop-build
make desktop-pkg          # writes ~/Downloads/AudioTools-*-macos-arm64.pkg or -x64.pkg
# Version in filename: AUDIO_TOOLS_VERSION=0.6 make desktop-pkg
# Maintainer fallback disk image: make desktop-dmg
```

Windows (PowerShell, x64 machine):

```powershell
py -3.11 -m venv .venv-desktop
.\.venv-desktop\Scripts\Activate.ps1
python -m pip install --upgrade torch torchaudio --index-url https://download.pytorch.org/whl/cpu
pip install -e ".[demucs,desktop]"
python packaging/bundle_ffmpeg.py
pyinstaller packaging/audio_tools.spec --noconfirm --clean
Compress-Archive -Path dist\AudioTools\* -DestinationPath "$env:USERPROFILE\Downloads\AudioTools-windows-x64.zip" -Force
```

CI: tag `desktop-v*` or run **desktop-release** via `workflow_dispatch`. Intel Mac job uses `macos-15-intel` (`macos-13` is retired).

# Desktop / local tester runbook

Run **Audio Isolation** and **Tab PDF** on your own computer at $0 hosting.
Processing uses your **CPU**, or **NVIDIA CUDA** on Windows when a compatible GPU and drivers are present (not AMD/Intel/Apple GPUs). No cloud VM, no Docker, no accounts.

**Installer testers** (`.pkg` / Windows zip): skip the Python/ffmpeg table below — see [Which installer to download](#which-installer-to-download).

For the website stack (FastAPI + React + Caddy), see [`DEPLOY.md`](DEPLOY.md) — that is a different product path.

## Requirements

| Item | Notes |
|------|--------|
| RAM | **16 GB preferred**. **8 GB minimum** — use short clips (≤90 s) and speed **Balanced** or **Faster**. |
| GPU | Optional **NVIDIA CUDA** on Windows. Download the **NVIDIA** Setup only if you have an NVIDIA GPU. Mac isolation is CPU-only. |
| Python | **3.10–3.12 only** (3.11 recommended). Not 3.13. |
| ffmpeg | Full/shared build on PATH (Homebrew, apt, or Windows Gyan.FFmpeg — not essentials-only). Installer builds bundle ffmpeg. |
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
2. **Demucs weights** — `tester` prewarms `htdemucs_6s` (default 6-stem model). Extra models download if you pick other track presets. Optional **guitar-ft** weights (~330 MB) download on first use when that Advanced checkbox is on; they cache as `$TORCH_HOME/checkpoints/guitar_htdemucs_6s.pt`. Meta’s pretrained Demucs weights are provided for scientific/research use (code is MIT; see facebookresearch/demucs#327).
3. Open **Audio Isolation**, upload a **≤90 s** clip first, leave speed on **Balanced**, click **Separate tracks**. Full band emits 4 tracks (Vocals, Drums, Bass, Guitar). Piano and Other are available under Custom.
4. Use the live mixer; download stems or a mix.

CPU separation often takes about as long as the song (or longer). Streamlit **Stop** may abort the page run, but a heavy Demucs child process can keep running until it finishes.

## YouTube downloads

Public YouTube URLs only (no login, no age-restricted / private / members-only). The UI already shows a ToS disclaimer; you are responsible for having rights to the audio.

Testers do **not** install extra tools for YouTube. Paste a public URL and click **Download audio** (or **Separate tracks**). The app uses bundled ffmpeg + yt-dlp with a retry ladder. If YouTube still rejects the URL, **upload the audio file** instead.

Maintainers: keep yt-dlp current (`.venv-desktop/bin/pip install -U yt-dlp`). Frozen testers need a rebuilt installer. The app retries after clearing yt-dlp’s player cache on 403.

## Which installer to download

These are **four separate builds**. Send testers only the file that matches their machine. Windows testers pick **CPU or NVIDIA** (or install both; they sit side by side).

| Tester machine | File | Notes |
|----------------|------|--------|
| Apple Silicon Mac (M1–M4) | `AudioTools-macos-arm64-silicon.pkg` | macOS **12+**. Double-click → **Install**. The app launches when install finishes. If Finder blocks: Terminal `xattr -cr` + `sudo installer`, or **System Settings → Privacy & Security → Open Anyway**. |
| Intel Mac | `AudioTools-macos-x64-intel.pkg` | Same install steps. An arm64 pkg will not launch here. |
| Windows 10 or 11 (x64), no NVIDIA GPU | `AudioTools-0.1.0-windows-x64-cpu-setup.exe` | **64-bit only.** Small Setup. Start Menu: **Audio Tools (CPU)**. Needs [WebView2](https://go.microsoft.com/fwlink/p/?LinkId=2124703). |
| Windows 10 or 11 (x64) with NVIDIA GPU | `AudioTools-0.1.0-windows-x64-cuda-setup.exe` | **64-bit only.** Large Setup. Start Menu: **Audio Tools (NVIDIA)**. Isolation is faster on NVIDIA + drivers. Can be installed next to the CPU edition. |

This is a **0.1.0 demo**. macOS builds are signed and notarized when Developer ID certificates are available on the build Mac. Windows SmartScreen will warn. The PyInstaller onedir is not obfuscated (Python is extractable); the freeze ships **no** hosted-site code, `.env`, or cloud credentials. No 32-bit Windows 10 build. No native Windows ARM build. No App Store.

The previous unlabeled `AudioTools-0.1.0-windows-x64-setup.exe` (all-in-one CUDA) used the CPU AppId and `C:\Program Files\AudioTools`. Installing the new **CPU** Setup **replaces** that tree. Uninstall it first if you want a clean split, then install CPU and/or NVIDIA.

Published under a `desktop-v*` GitHub Release (draft until a maintainer publishes). `workflow_dispatch` also produces the four artifacts without a tag.

## Download & install (terminal)

Use the file that matches your OS. Windows has two 0.1.0 Setups: **`AudioTools-0.1.0-windows-x64-cpu-setup.exe`** (default) and **`AudioTools-0.1.0-windows-x64-cuda-setup.exe`** (NVIDIA). GitHub Release assets use the unversioned names `AudioTools-windows-x64-cpu-setup.exe` and `AudioTools-windows-x64-cuda-setup.exe`.

### Apple Silicon Mac (M1–M4)

```bash
curl -fL -o ~/Downloads/AudioTools-macos-arm64-silicon.pkg \
  "https://github.com/notjj1234/jj_audio_website/releases/latest/download/AudioTools-macos-arm64-silicon.pkg"

xattr -cr ~/Downloads/AudioTools-macos-arm64-silicon.pkg
sudo installer -pkg ~/Downloads/AudioTools-macos-arm64-silicon.pkg -target /
open /Applications/AudioTools.app
```

Finder: double-click the `.pkg` → **Install**. The app should launch when install finishes.

If Finder shows “Apple could not verify…”, use the Terminal block above, or **System Settings → Privacy & Security → Open Anyway**.

### Intel Mac

```bash
curl -fL -o ~/Downloads/AudioTools-macos-x64-intel.pkg \
  "https://github.com/notjj1234/jj_audio_website/releases/latest/download/AudioTools-macos-x64-intel.pkg"

xattr -cr ~/Downloads/AudioTools-macos-x64-intel.pkg
sudo installer -pkg ~/Downloads/AudioTools-macos-x64-intel.pkg -target /
open /Applications/AudioTools.app
```

### Windows 10 / 11 CPU (PowerShell)

```powershell
curl.exe -fL -o "$env:USERPROFILE\Downloads\AudioTools-0.1.0-windows-x64-cpu-setup.exe" `
  "https://github.com/notjj1234/jj_audio_website/releases/latest/download/AudioTools-windows-x64-cpu-setup.exe"

Start-Process "$env:USERPROFILE\Downloads\AudioTools-0.1.0-windows-x64-cpu-setup.exe"
```

### Windows 10 / 11 NVIDIA CUDA (PowerShell)

```powershell
curl.exe -fL -o "$env:USERPROFILE\Downloads\AudioTools-0.1.0-windows-x64-cuda-setup.exe" `
  "https://github.com/notjj1234/jj_audio_website/releases/latest/download/AudioTools-windows-x64-cuda-setup.exe"

Start-Process "$env:USERPROFILE\Downloads\AudioTools-0.1.0-windows-x64-cuda-setup.exe"
```

**Windows 10 and 11 (x64):** `MinVersion` is 10.0. Not 32-bit, not native ARM. **WebView2** is required (built into Windows 11 and recent 10; older 10 must install Evergreen). CPU Setup is the small default. NVIDIA Setup is large and only speeds isolation on an NVIDIA GPU + drivers; the wizard warns if no NVIDIA adapter is seen (install still allowed).

SmartScreen: **More info → Run anyway**. Finish the wizard, then launch **Audio Tools (CPU)** or **Audio Tools (NVIDIA)** from the Start Menu. Native Edge WebView2 window, not a browser tab. Apps & Features shows **0.1.0**. Both editions may be installed at once.

Missing window? Install [WebView2](https://go.microsoft.com/fwlink/p/?LinkId=2124703), then check `%LOCALAPPDATA%\AudioTools\logs\launcher.log` (CPU) or `%LOCALAPPDATA%\AudioToolsNVIDIA\logs\launcher.log` (NVIDIA) — a healthy launch logs `Native window shown (hwnds=[...])`.

## Installer first run

1. First launch needs internet once to download Demucs weights (several minutes). Later runs reuse the cache.
2. Open **Audio Isolation**, upload a **≤90 s** clip, leave speed on **Balanced**, click **Separate tracks**.
3. Confirm the live mixer stays open when you mute/solo; try **Custom** under “What to separate”; download a stem or zip.

CPU separation often takes about as long as the song (or longer). The **NVIDIA** Windows edition is typically faster on a compatible GPU.

Installer data dirs (not the same as `make tester`):

| | macOS app | Windows CPU | Windows NVIDIA |
|--|-----------|-------------|----------------|
| Stems / runs | `~/Library/Application Support/AudioTools/runs` | `%LOCALAPPDATA%\AudioTools\runs` | `%LOCALAPPDATA%\AudioToolsNVIDIA\runs` |
| Demucs weights | `~/Library/Caches/AudioTools/torch` (`checkpoints/guitar_htdemucs_6s.pt` ~330 MB if guitar-ft is on) | `%LOCALAPPDATA%\AudioTools\models` (shared) | `%LOCALAPPDATA%\AudioTools\models` (shared) |
| Logs | `~/Library/Application Support/AudioTools/logs` | `%LOCALAPPDATA%\AudioTools\logs` | `%LOCALAPPDATA%\AudioToolsNVIDIA\logs` |

## Smoke test matrix (expected)

| Platform | Build | Must pass |
|----------|-------|-----------|
| M-series Mac | arm64 pkg | Native window opens; upload ≤90 s; Separate tracks; mixer stays open; Custom preset; downloads work |
| Intel Mac | x64 pkg | Same as above |
| Win10 x64 | cpu-setup.exe | Native window **Audio Tools (CPU)**; default speed is Balanced/CPU; SmartScreen; WebView2 |
| Win10 x64 NVIDIA | cuda-setup.exe | Native window **Audio Tools (NVIDIA)**; Balanced can use CUDA; wizard may warn if no NVIDIA adapter |
| Win11 x64 | cpu-setup.exe and/or cuda-setup.exe | Same as Win10 rows |

Known limitations to tell testers: macOS Gatekeeper blocks a downloaded `.pkg` unless it was Developer ID signed and notarized; first-run model download; **16 GB RAM preferred** (8 GB: short clips + Balanced/Faster). GPU acceleration is **NVIDIA-only** (Windows).

## Model cache path (run from source)

When using `./scripts/dev.sh tester` / `.\scripts\dev.ps1 tester` (not the installer), weights land under Torch’s default cache unless you set `TORCH_HOME`:

- macOS / Linux: `~/.cache/torch` (or `$TORCH_HOME`)
- Windows: `%USERPROFILE%\.cache\torch` (or `%TORCH_HOME%`)

Optional guitar-ft: `$TORCH_HOME/checkpoints/guitar_htdemucs_6s.pt` (~330 MB). Meta Demucs weights are research-purpose; the guitar-ft fine-tune is Apache-2.0 and does not change that.

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
make desktop-pkg          # writes ~/Downloads/AudioTools-*-macos-arm64-silicon.pkg or *-macos-x64-intel.pkg
# Version in filename: AUDIO_TOOLS_VERSION=0.6 make desktop-pkg
# Maintainer fallback disk image: make desktop-dmg
```

Windows (PowerShell, x64 machine — needs [Inno Setup](https://jrsoftware.org/isinfo.php)):

```powershell
# CPU edition (~300 MB class)
py -3.11 -m venv .venv-desktop-cpu
.\.venv-desktop-cpu\Scripts\Activate.ps1
python -m pip install --upgrade torch torchaudio
pip install -e ".[demucs,desktop]"
python packaging/bundle_ffmpeg.py
$env:AUDIO_TOOLS_EDITION = "cpu"
pyinstaller packaging/audio_tools.spec --noconfirm --clean
powershell -ExecutionPolicy Bypass -File packaging/make_windows_installer.ps1 -AppVersion 0.1.0 -Flavor cpu -CopyToDownloads

# NVIDIA edition (large CUDA freeze) — separate venv
py -3.11 -m venv .venv-desktop
.\.venv-desktop\Scripts\Activate.ps1
python -m pip install --upgrade torch torchaudio --index-url https://download.pytorch.org/whl/cu126
pip install -e ".[demucs,desktop]"
$env:AUDIO_TOOLS_EDITION = "cuda"
pyinstaller packaging/audio_tools.spec --noconfirm --clean
powershell -ExecutionPolicy Bypass -File packaging/make_windows_installer.ps1 -AppVersion 0.1.0 -Flavor cuda -CopyToDownloads
```

Writes `%USERPROFILE%\Downloads\AudioTools-0.1.0-windows-x64-cpu-setup.exe` and `AudioTools-0.1.0-windows-x64-cuda-setup.exe`.

CI: tag `desktop-v*` or run **desktop-release** via `workflow_dispatch`. Intel Mac job uses `macos-15-intel` (`macos-13` is retired).

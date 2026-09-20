# Audio Tools

Local desktop and hosted website for **audio isolation** (split a song into stems), a **live mixer** with an optional **metronome click track**, **YouTube audio save** (desktop), and a **Tab PDF** demo. Both products share the `src/audio_to_tab/` engine (Demucs / RoFormer / SCNet, mixer math, ingest, tab pipeline).

| Product | Stack | Runbook |
|---------|--------|---------|
| **Desktop** | Streamlit `ui/` + `packaging/launcher.py` (native window) | [`DESKTOP.md`](DESKTOP.md) |
| **Website** | FastAPI `backend/` + React `web/` + Caddy | [`DEPLOY.md`](DEPLOY.md) |

Agents / contributors: start at [`PROJECT_TREE.md`](PROJECT_TREE.md) and [`AGENTS.md`](AGENTS.md). Design history: [`docs/issues.md`](docs/issues.md), [`docs/ui-issues.md`](docs/ui-issues.md).

### Desktop (local)

- **Audio Isolation** — separate/mix stems; Lite auto-profiles speed/device from RAM/GPU; Pro exposes every control. Sticky **Home | mix | +** strip; mix tab is the live Web Audio mixer.
- **Metronome** — adaptive (“floating”) click track follows local pulse (e.g. sung intros) via a librosa tempo curve; Mixer Accent / rate / sound hot-swap without reloading stems. Rebake uses stored `click_times_1x`.
- **Mixer playback** — keeps playing when you switch to another app/window (does not soft-pause on document hide). Sleep / dead `AudioContext` still recovers without auto-resuming if you had paused.
- **YouTube Audio** — save a public link to a folder (MP3 default); not separate/mix. Ignores Lite/Pro.
- **Tab PDF** — unfinished demo; Pro gates engine/advanced options.

### Website (hosted)

- File-upload Isolate + Tab PDF (no YouTube on the public stack by default).
- Same mixer engine policy: background playback across focus loss; metronome stem when the job attaches one.
- Processing modes Auto / Low RAM / etc. live in `backend/capabilities.py` (not the same as desktop Interface Lite).

License: [MIT](LICENSE)

---

## Tester

**Windows CPU**
```powershell
$env:AUDIO_TOOLS_EDITION = "cpu"
.\.venv311\Scripts\python.exe packaging/launcher.py
```

**Windows GPU**
```powershell
$env:AUDIO_TOOLS_EDITION = "cuda"
.\.venv-desktop\Scripts\python.exe packaging/launcher.py
```

**macOS (Apple Silicon / Intel)**
`./scripts/dev.sh tester` runs Streamlit in the browser. To open the same UI as a **native app window** (pywebview, title "Audio Tools Demo"), use the launcher:

```bash
# First time only — desktop venv with the native-window (pywebview) support
python3.11 -m venv .venv-desktop
source .venv-desktop/bin/activate
python -m pip install --upgrade pip
pip install -e ".[demucs,desktop,roformer,separator]"

# Opens a native macOS window (port 8501, or 8502–8505 if taken)
.venv-desktop/bin/python packaging/launcher.py
```

## Build installers (0.1.4)

### Windows CPU

Small installer. CPU torch only — no NVIDIA acceleration. Start Menu: **Audio Tools (CPU)**.

```powershell
cd <repo>
py -3.11 -m venv .venv-desktop-cpu          # first time only
.\.venv-desktop-cpu\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install --upgrade "torch>=2.2,<2.14" "torchaudio>=2.2,<2.12"
pip install -e ".[demucs,desktop,roformer,separator]"
.\scripts\dev.ps1 mixer-build                   # skip if frontend/build is committed
python packaging/bundle_ffmpeg.py
$env:AUDIO_TOOLS_EDITION = "cpu"
pyinstaller packaging/audio_tools.spec --noconfirm --clean
powershell -ExecutionPolicy Bypass -File packaging/make_windows_installer.ps1 -Flavor cpu -CopyToDownloads
```
→ `%USERPROFILE%\Downloads\AudioTools-0.1.4-windows-x64-cpu-setup.exe`

### Windows combined (CPU + NVIDIA GPU)

One large installer. Ships **CUDA PyTorch** and offers **CPU or NVIDIA GPU** in the UI. Start Menu: **Audio Tools**. Prefer this for a single tester download.

```powershell
cd <repo>
py -3.11 -m venv .venv-desktop                # first time only
.\.venv-desktop\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install --upgrade "torch>=2.2,<2.14" "torchaudio>=2.2,<2.12" --index-url https://download.pytorch.org/whl/cu126
pip install "bs-roformer-infer>=0.1.5"
pip install -e ".[demucs,desktop,separator]"
.\scripts\dev.ps1 mixer-build                   # skip if frontend/build is committed
python packaging/bundle_ffmpeg.py
$env:AUDIO_TOOLS_EDITION = "both"
pyinstaller packaging/audio_tools.spec --noconfirm --clean
powershell -ExecutionPolicy Bypass -File packaging/make_windows_installer.ps1 -Flavor both -CopyToDownloads
```
→ `%USERPROFILE%\Downloads\AudioTools-0.1.4-windows-x64-both-setup.exe`

### Windows GPU (CUDA) only

Same large CUDA torch freeze as combined, but the UI targets **NVIDIA GPU** (Start Menu: **Audio Tools (NVIDIA)**). Needs an NVIDIA GPU + drivers for isolation.

```powershell
cd <repo>
# Reuse .venv-desktop from the combined section (CUDA torch already installed)
.\.venv-desktop\Scripts\Activate.ps1
python packaging/bundle_ffmpeg.py
$env:AUDIO_TOOLS_EDITION = "cuda"
pyinstaller packaging/audio_tools.spec --noconfirm --clean
powershell -ExecutionPolicy Bypass -File packaging/make_windows_installer.ps1 -Flavor cuda -CopyToDownloads
```
→ `%USERPROFILE%\Downloads\AudioTools-0.1.4-windows-x64-cuda-setup.exe`

### macOS Apple Silicon (M1–M4)

Run on an M-series Mac. Uses `.venv-desktop` (native arm64 Python).

```bash
cd <repo>

# First time only
python3.11 -m venv .venv-desktop
source .venv-desktop/bin/activate
python -m pip install --upgrade pip
python -m pip install --upgrade "torch>=2.2,<2.14" "torchaudio>=2.2,<2.12"
pip install -e ".[demucs,desktop,roformer,separator]"

# Build (skip mixer-build if frontend/build is already committed)
make mixer-build
make desktop-bundle-ffmpeg
make desktop-build
make desktop-pkg
```

→ `~/Downloads/AudioTools-0.1.4-macos-arm64-silicon.pkg`

Optional: bump version in the filename — `AUDIO_TOOLS_VERSION=0.1.4 make desktop-pkg`

### macOS Intel (x64)

**On an Intel Mac:** same steps as Apple Silicon above (native x64 `.venv-desktop`).

**On an Apple Silicon Mac:** use a separate Rosetta (x86_64) venv — PyInstaller must freeze an x64 binary.

```bash
cd <repo>

# First time only — x86_64 Python under Rosetta
arch -x86_64 python3.11 -m venv .venv-desktop-x64
source .venv-desktop-x64/bin/activate
python -m pip install --upgrade pip
python -m pip install --upgrade "torch>=2.2,<2.14" "torchaudio>=2.2,<2.12"
pip install -e ".[demucs,desktop,roformer,separator]"

# Build (skip mixer-build if frontend/build is already committed)
make mixer-build
.venv-desktop-x64/bin/python packaging/bundle_ffmpeg.py
.venv-desktop-x64/bin/python -m PyInstaller packaging/audio_tools.spec --noconfirm --clean
./packaging/make_pkg.sh
```

→ `~/Downloads/AudioTools-0.1.4-macos-x64-intel.pkg`

No Intel Mac or Rosetta venv? Trigger the **desktop-release** GitHub Action (`workflow_dispatch`) — it builds the Intel pkg on `macos-15-intel`.

Unsigned pkg unless you have Developer ID certs (see DESKTOP.md). Gatekeeper will complain — right-click → Open, or `xattr -cr` + `sudo installer`.

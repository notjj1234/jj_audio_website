# Audio Tools

Desktop installers and local tester commands. Full runbook: [`DESKTOP.md`](DESKTOP.md). Hosted website: [`DEPLOY.md`](DEPLOY.md).

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
```bash
# First time only — desktop venv with native-window (pywebview) support
python3.11 -m venv .venv-desktop
source .venv-desktop/bin/activate
python -m pip install --upgrade pip
pip install -e ".[demucs,desktop,roformer,separator]"

# Opens a native macOS window (port 8501, or 8502–8505 if taken)
.venv-desktop/bin/python packaging/launcher.py
```

Browser-only (no native window): `./scripts/dev.sh tester` (macOS/Linux) or `.\scripts\dev.ps1 tester` (Windows).

---

## Build installers (0.1.4)

### Windows CPU

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

Optional: `AUDIO_TOOLS_VERSION=0.1.4 make desktop-pkg`

### macOS Intel (x64)

**On an Intel Mac:** same steps as Apple Silicon above.

**On an Apple Silicon Mac** (Rosetta x86_64 freeze):

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

No Intel Mac? Trigger **desktop-release** (`workflow_dispatch`) for the Intel pkg on `macos-15-intel`.

Unsigned pkg: right-click → Open, or `xattr -cr` + `sudo installer` (see [`DESKTOP.md`](DESKTOP.md)).

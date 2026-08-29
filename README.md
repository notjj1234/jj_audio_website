# Audio Tools

Audio splitter app (for now) made with Demucs. More stuff will be added later.

The following is for JJs bs, feel free to ignore

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

**macOS**
```bash
./scripts/dev.sh tester
```

## Build installers (0.1.2)

### Windows CPU

```powershell
cd C:\Users\orall\Documents\GitHub\jj_audio_website
py -3.11 -m venv .venv-desktop-cpu          # first time only
.\.venv-desktop-cpu\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install --upgrade torch torchaudio
pip install -e ".[demucs,desktop,roformer,separator]"
.\scripts\dev.ps1 mixer-build                   # skip if frontend/build is committed
python packaging/bundle_ffmpeg.py
$env:AUDIO_TOOLS_EDITION = "cpu"
pyinstaller packaging/audio_tools.spec --noconfirm --clean
powershell -ExecutionPolicy Bypass -File packaging/make_windows_installer.ps1 -Flavor cpu -CopyToDownloads
```
→ `%USERPROFILE%\Downloads\AudioTools-0.1.2-windows-x64-cpu-setup.exe`

### Windows GPU (CUDA)

```powershell
cd C:\Users\orall\Documents\GitHub\jj_audio_website
py -3.11 -m venv .venv-desktop                # first time only
.\.venv-desktop\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install --upgrade torch torchaudio --index-url https://download.pytorch.org/whl/cu126
pip install "bs-roformer-infer>=0.1.5"
pip install -e ".[demucs,desktop,separator]"
.\scripts\dev.ps1 mixer-build
python packaging/bundle_ffmpeg.py
$env:AUDIO_TOOLS_EDITION = "cuda"
pyinstaller packaging/audio_tools.spec --noconfirm --clean
powershell -ExecutionPolicy Bypass -File packaging/make_windows_installer.ps1 -Flavor cuda -CopyToDownloads
```
→ `%USERPROFILE%\Downloads\AudioTools-0.1.2-windows-x64-cuda-setup.exe`

### macOS Apple Silicon (M1–M4)

Run on an M-series Mac. Uses `.venv-desktop` (native arm64 Python).

```bash
cd ~/Documents/-\ PERSONAL\ PROJECTS\ GITHUB\ -/jj_audio_website

# First time only
python3.11 -m venv .venv-desktop
source .venv-desktop/bin/activate
python -m pip install --upgrade pip
python -m pip install --upgrade torch torchaudio
pip install -e ".[demucs,desktop,roformer,separator]"

# Build (skip mixer-build if frontend/build is already committed)
make mixer-build
make desktop-bundle-ffmpeg
make desktop-build
make desktop-pkg
```

→ `~/Downloads/AudioTools-0.1.2-macos-arm64-silicon.pkg`

Optional: bump version in the filename — `AUDIO_TOOLS_VERSION=0.1.3 make desktop-pkg`

### macOS Intel (x64)

**On an Intel Mac:** same steps as Apple Silicon above (native x64 `.venv-desktop`).

**On an Apple Silicon Mac:** use a separate Rosetta (x86_64) venv — PyInstaller must freeze an x64 binary.

```bash
cd ~/Documents/-\ PERSONAL\ PROJECTS\ GITHUB\ -/jj_audio_website

# First time only — x86_64 Python under Rosetta
arch -x86_64 python3.11 -m venv .venv-desktop-x64
source .venv-desktop-x64/bin/activate
python -m pip install --upgrade pip
python -m pip install --upgrade torch torchaudio
pip install -e ".[demucs,desktop,roformer,separator]"

# Build (skip mixer-build if frontend/build is already committed)
make mixer-build
.venv-desktop-x64/bin/python packaging/bundle_ffmpeg.py
.venv-desktop-x64/bin/python -m PyInstaller packaging/audio_tools.spec --noconfirm --clean
./packaging/make_pkg.sh
```

→ `~/Downloads/AudioTools-0.1.2-macos-x64-intel.pkg`

No Intel Mac or Rosetta venv? Trigger the **desktop-release** GitHub Action (`workflow_dispatch`) — it builds the Intel pkg on `macos-15-intel`.

Unsigned pkg unless you have Developer ID certs (see DESKTOP.md). Gatekeeper will complain — right-click → Open, or `xattr -cr` + `sudo installer`.

License: [MIT](LICENSE)

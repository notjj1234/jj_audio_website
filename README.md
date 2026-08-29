# Audio Tools

Audio splitter app (for now) made with Demucs. More stuff will be added later.

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

Run on an M-series Mac only — produces the arm64 pkg.

```bash
cd ~/Documents/GitHub/jj_audio_website
python3.11 -m venv .venv-desktop              # first time only
source .venv-desktop/bin/activate
python -m pip install --upgrade pip
python -m pip install --upgrade torch torchaudio
pip install -e ".[demucs,desktop,roformer,separator]"
make mixer-build                              # skip if frontend/build is committed
make desktop-bundle-ffmpeg
make desktop-build
make desktop-pkg
```
→ `~/Downloads/AudioTools-0.1.2-macos-arm64-silicon.pkg`

### macOS Intel (x64)

Run on an Intel Mac only — produces the x64 pkg.

```bash
cd ~/Documents/GitHub/jj_audio_website
python3.11 -m venv .venv-desktop              # first time only
source .venv-desktop/bin/activate
python -m pip install --upgrade pip
python -m pip install --upgrade torch torchaudio
pip install -e ".[demucs,desktop,roformer,separator]"
make mixer-build                              # skip if frontend/build is committed
make desktop-bundle-ffmpeg
make desktop-build
make desktop-pkg
```
→ `~/Downloads/AudioTools-0.1.2-macos-x64-intel.pkg`

Unsigned pkg unless you have Developer ID certs (see DESKTOP.md). Gatekeeper will complain — right-click → Open, or `xattr -cr` + `sudo installer`.

License: [MIT](LICENSE)

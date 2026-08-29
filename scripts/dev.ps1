# Windows runner for audio-to-tab-pdf (PowerShell equivalent of make / scripts/dev.sh)
# Usage:
#   .\scripts\dev.ps1 install
#   .\scripts\dev.ps1 tester
#   .\scripts\dev.ps1 ui
#   .\scripts\dev.ps1 backend
#   .\scripts\dev.ps1 test
param(
    [Parameter(Position = 0)]
    [ValidateSet(
        "install", "install-demucs", "fixtures", "test", "eval", "eval-lead-rhythm",
        "ui", "backend", "mixer-build", "preflight", "tester", "help"
    )]
    [string]$Command = "help"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Venv = Join-Path $Root ".venv311"
$VenvPython = Join-Path $Venv "Scripts\python.exe"
$env:PYTHONPATH = "src;."

function Get-HostPython {
    foreach ($launcher in @(
        @{ Exe = "py"; Args = @("-3.11") },
        @{ Exe = "py"; Args = @("-3.12") },
        @{ Exe = "py"; Args = @("-3.10") }
    )) {
        try {
            $code = "import sys; print(sys.executable); raise SystemExit(0 if (3,10)<=sys.version_info[:2]<(3,13) else 1)"
            $out = & $launcher.Exe @($launcher.Args + @("-c", $code)) 2>$null
            if ($LASTEXITCODE -eq 0 -and $out) {
                return ($out | Select-Object -Last 1).Trim()
            }
        } catch { }
    }
    foreach ($name in @("python3.11", "python3.12", "python3.10", "python")) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if (-not $cmd) { continue }
        try {
            $ok = & $cmd.Source -c "import sys; raise SystemExit(0 if (3,10)<=sys.version_info[:2]<(3,13) else 1)"
            if ($LASTEXITCODE -eq 0) { return $cmd.Source }
        } catch { }
    }
    throw "Need Python 3.10-3.12 (3.11 recommended). Install from https://www.python.org/downloads/"
}

function Get-ProjectPython {
    if (Test-Path $VenvPython) { return $VenvPython }
    return Get-HostPython
}

function Invoke-Preflight {
    $py = Get-HostPython
    $ver = & $py -c "import sys; print(sys.version.split()[0])"
    Write-Host "Python OK: $py ($ver)"

    $ffmpeg = Get-Command ffmpeg -ErrorAction SilentlyContinue
    if (-not $ffmpeg) {
        throw "ffmpeg not found on PATH. Install: winget install Gyan.FFmpeg  (full/shared build, not essentials-only)"
    }
    Write-Host "ffmpeg OK: $($ffmpeg.Source)"

    try {
        $cs = Get-CimInstance Win32_ComputerSystem -ErrorAction SilentlyContinue
        if ($cs -and $cs.TotalPhysicalMemory) {
            $memGb = [math]::Round($cs.TotalPhysicalMemory / 1GB, 0)
            Write-Host "RAM: ~${memGb} GB (16 GB preferred; 8 GB min + short clips + fast quality)"
            if ($memGb -lt 8) {
                Write-Warning "Under 8 GB RAM — use <=90 s clips and Quality fast."
            } elseif ($memGb -lt 16) {
                Write-Warning "Under 16 GB RAM — prefer short clips and Quality fast."
            }
        }
    } catch { }

    try {
        $drive = (Get-Item $Root).PSDrive
        if ($drive -and $drive.Free) {
            $freeGb = [math]::Round($drive.Free / 1GB, 0)
            Write-Host "Free disk: ~${freeGb} GB (need ~5 GB for venv + models)"
            if ($freeGb -lt 5) {
                Write-Warning "Less than ~5 GB free disk."
            }
        }
    } catch { }

    Write-Host "Preflight OK."
}

function Install-TorchCpu {
    param([string]$PythonExe)
    Write-Host "Installing PyTorch CPU wheels…"
    & $PythonExe -m pip install --upgrade torch torchaudio --index-url https://download.pytorch.org/whl/cpu
}

function Install-TesterDeps {
    $py = Get-HostPython
    Write-Host "Creating $Venv with $py..."
    & $py -m venv $Venv
    & $VenvPython -m pip install -U pip
    Install-TorchCpu -PythonExe $VenvPython
    & $VenvPython -m pip install -e ".[demucs,roformer,separator]"
    Write-Host "Done. Run: .\scripts\dev.ps1 ui   (or .\scripts\dev.ps1 tester)"
}

function Start-Ui {
    if (-not (Test-Path $VenvPython)) {
        throw "Run .\scripts\dev.ps1 install (or tester) first"
    }
    Write-Host "Starting UI at http://127.0.0.1:8501"
    $env:CI = "1"
    & $VenvPython -m streamlit run ui/app.py `
        --server.address=127.0.0.1 `
        --server.port=8501 `
        --server.headless=false `
        --browser.gatherUsageStats=false
}

switch ($Command) {
    "help" {
        @"
Targets:
  .\scripts\dev.ps1 preflight        Check Python 3.10-3.12, ffmpeg, RAM/disk hints
  .\scripts\dev.ps1 tester           Preflight + install (if needed) + prewarm + UI
  .\scripts\dev.ps1 install          Create .venv311 and install contributor deps
  .\scripts\dev.ps1 install-demucs   Install Demucs + PyTorch into the venv
  .\scripts\dev.ps1 fixtures         Generate eval MIDI fixtures
  .\scripts\dev.ps1 test             Run pytest
  .\scripts\dev.ps1 eval             Run transcription eval harness
  .\scripts\dev.ps1 eval-lead-rhythm Score Lead/Rhythm vs local manifest
  .\scripts\dev.ps1 ui               Start Streamlit UI (http://127.0.0.1:8501)
  .\scripts\dev.ps1 backend          Start FastAPI server (http://localhost:8000)
  .\scripts\dev.ps1 mixer-build      Build live stem mixer frontend (Node 18+)
"@
    }
    "preflight" {
        Invoke-Preflight
    }
    "tester" {
        Invoke-Preflight
        if (-not (Test-Path $VenvPython)) {
            Install-TesterDeps
        }
        Write-Host "Prewarming models (first run may download weights)…"
        try {
            & (Get-ProjectPython) scripts/prewarm.py
        } catch {
            Write-Warning "Prewarm reported an error; continuing to UI."
        }
        Start-Ui
    }
    "mixer-build" {
        Push-Location (Join-Path $Root "ui\stem_mixer_component\frontend")
        try {
            npm install
            npm run build
        } finally {
            Pop-Location
        }
        Write-Host "Stem mixer frontend built."
    }
    "install" {
        $py = Get-HostPython
        Write-Host "Creating $Venv with $py..."
        & $py -m venv $Venv
        & $VenvPython -m pip install -U pip
        Install-TorchCpu -PythonExe $VenvPython
        & $VenvPython -m pip install -e ".[dev,eval,demucs,roformer,separator]"
        Write-Host "Done. Run: .\scripts\dev.ps1 ui   (or .\scripts\dev.ps1 tester)"
    }
    "install-demucs" {
        & (Get-ProjectPython) -m pip install -r requirements-demucs.txt
    }
    "fixtures" {
        & (Get-ProjectPython) eval/generate_fixtures.py
    }
    "test" {
        & (Get-ProjectPython) -m pytest tests/ -q
    }
    "eval" {
        & (Get-ProjectPython) eval/generate_fixtures.py
        & (Get-ProjectPython) eval/score_transcription.py -o eval/results.json
    }
    "eval-lead-rhythm" {
        & (Get-ProjectPython) eval/lead_rhythm/score_lead_rhythm.py
    }
    "ui" {
        Start-Ui
    }
    "backend" {
        if (-not (Test-Path $VenvPython)) {
            throw "Run .\scripts\dev.ps1 install first"
        }
        Write-Host "Starting API at http://localhost:8000/docs"
        & $VenvPython -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
    }
}

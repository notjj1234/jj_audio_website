# Windows runner for audio-to-tab-pdf (PowerShell equivalent of make / scripts/dev.sh)
# Usage:
#   .\scripts\dev.ps1 install
#   .\scripts\dev.ps1 ui
#   .\scripts\dev.ps1 backend
#   .\scripts\dev.ps1 test
param(
    [Parameter(Position = 0)]
    [ValidateSet("install", "install-demucs", "fixtures", "test", "eval", "eval-lead-rhythm", "ui", "backend", "mixer-build", "help")]
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

switch ($Command) {
    "help" {
        @"
Targets:
  .\scripts\dev.ps1 install          Create .venv311 and install dependencies
  .\scripts\dev.ps1 install-demucs   Install Demucs + PyTorch into the venv
  .\scripts\dev.ps1 fixtures         Generate eval MIDI fixtures
  .\scripts\dev.ps1 test             Run pytest
  .\scripts\dev.ps1 eval             Run transcription eval harness
  .\scripts\dev.ps1 eval-lead-rhythm Score Lead/Rhythm vs local manifest
  .\scripts\dev.ps1 ui               Start Streamlit web UI (http://localhost:8501)
  .\scripts\dev.ps1 backend          Start FastAPI server (http://localhost:8000)
  .\scripts\dev.ps1 mixer-build      Build live stem mixer frontend (Node 18+)
"@
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
        & $VenvPython -m pip install -e ".[dev,eval,demucs]"
        Write-Host "Done. Run: .\scripts\dev.ps1 ui"
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
        if (-not (Test-Path $VenvPython)) {
            throw "Run .\scripts\dev.ps1 install first"
        }
        Write-Host "Starting UI at http://localhost:8501"
        & $VenvPython -m streamlit run ui/app.py --server.port 8501
    }
    "backend" {
        if (-not (Test-Path $VenvPython)) {
            throw "Run .\scripts\dev.ps1 install first"
        }
        Write-Host "Starting API at http://localhost:8000/docs"
        & $VenvPython -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
    }
}

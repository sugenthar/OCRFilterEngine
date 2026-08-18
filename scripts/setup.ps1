[CmdletBinding()]
param()

$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCommand) {
    throw 'Python 3.11+ was not found. Install it, select "Add Python to PATH", then run this script again.'
}

& $pythonCommand.Source --version
if ($LASTEXITCODE -ne 0) {
    throw 'Python could not be started.'
}

$venvPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $venvPython)) {
    & $pythonCommand.Source -m venv (Join-Path $projectRoot '.venv')
    if ($LASTEXITCODE -ne 0) {
        throw 'Unable to create the .venv virtual environment.'
    }
}

& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r (Join-Path $projectRoot 'requirements.txt')
if ($LASTEXITCODE -ne 0) {
    throw 'Python packages could not be installed. Check your internet connection and run setup again.'
}

foreach ($relativePath in @('images\inbox', 'images\archive\hd', 'output')) {
    New-Item -ItemType Directory -Force -Path (Join-Path $projectRoot $relativePath) | Out-Null
}

$tesseractCandidates = @(
    $env:TESSERACT_CMD,
    'C:\Program Files\Tesseract-OCR\tesseract.exe',
    (Get-Command tesseract -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -ErrorAction SilentlyContinue)
) | Where-Object { $_ }

if ($tesseractCandidates | Where-Object { Test-Path -LiteralPath $_ }) {
    Write-Host 'Tesseract OCR: found.' -ForegroundColor Green
} else {
    Write-Warning 'Tesseract OCR was not found. Install it, then set TESSERACT_CMD if it is not in the default folder.'
}

$ahkCandidates = @(
    'C:\Program Files\AutoHotkey\v2\AutoHotkey64.exe',
    'C:\Program Files\AutoHotkey\v2\AutoHotkey.exe'
) | Where-Object { Test-Path -LiteralPath $_ }

if ($ahkCandidates) {
    Write-Host 'AutoHotkey v2: found.' -ForegroundColor Green
} else {
    Write-Warning 'AutoHotkey v2 was not found. Install it before using F6 data entry.'
}

Write-Host "Setup complete. Start the watcher with .\scripts\start-watcher.ps1" -ForegroundColor Green

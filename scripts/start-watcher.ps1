[CmdletBinding()]
param()

$projectRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $venvPython)) {
    throw 'Run .\scripts\setup.ps1 once before starting the watcher.'
}

Set-Location $projectRoot
& $venvPython 'run_pipeline.py' '--watch' '--continue-session'

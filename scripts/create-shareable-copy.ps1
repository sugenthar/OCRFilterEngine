[CmdletBinding()]
param(
    [string]$Destination = (Join-Path (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)) 'OCR-Shareable')
)

$projectRoot = Split-Path -Parent $PSScriptRoot
if (Test-Path -LiteralPath $Destination) {
    throw "Destination already exists: $Destination. Choose another -Destination path."
}

$excludedDirectories = @('.git', '.venv', '__pycache__', 'output', 'images', 'OCRFilterEngine', 'OCRscaner')
$copyResult = & robocopy $projectRoot $Destination /E /XD $excludedDirectories /XF '*.pyc' '*.pyo' '*.log' '*.db' '*.ahk' '*.lnk'
if ($LASTEXITCODE -ge 8) {
    throw "Unable to create clean shareable copy. Robocopy exit code: $LASTEXITCODE"
}

foreach ($relativePath in @('images\inbox', 'images\archive\hd', 'output')) {
    New-Item -ItemType Directory -Force -Path (Join-Path $Destination $relativePath) | Out-Null
}

Write-Host "Clean copy created: $Destination" -ForegroundColor Green
Write-Host 'Next: cd to that folder, run git init, git add ., then commit and push.' -ForegroundColor Green

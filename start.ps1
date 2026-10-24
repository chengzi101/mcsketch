$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$taskPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) {
    Write-Host 'Please follow README.md to install dependencies first.'
    exit 1
}
if (-not (Test-Path -LiteralPath 'frontend\dist\index.html')) {
    Write-Host 'Build frontend first: cd frontend; pnpm install; pnpm build'
    exit 1
}
& $taskPython -X utf8 -m backend.app

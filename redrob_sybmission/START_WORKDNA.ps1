$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

$bundledPython = "C:\Users\Aarya\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$python = if (Test-Path -LiteralPath $bundledPython) { $bundledPython } else { "python" }

Write-Host "Starting WorkDNA offline candidate intelligence..." -ForegroundColor Cyan
Write-Host "Open http://127.0.0.1:8765" -ForegroundColor Green

Start-Process "http://127.0.0.1:8765"
& $python ".\app\server.py"

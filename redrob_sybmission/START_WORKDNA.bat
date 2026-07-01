@echo off
setlocal
cd /d "%~dp0"

set "PYTHON=C:\Users\Aarya\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

if not exist "%PYTHON%" (
  set "PYTHON=python"
)

echo Starting WorkDNA offline candidate intelligence...
echo.
echo The app will be available at:
echo http://127.0.0.1:8765
echo.

start "" "http://127.0.0.1:8765"
"%PYTHON%" ".\app\server.py"

endlocal

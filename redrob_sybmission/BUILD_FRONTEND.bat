@echo off
setlocal
cd /d "%~dp0web"
npm install
npm run build
endlocal

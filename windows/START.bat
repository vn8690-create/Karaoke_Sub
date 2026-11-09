@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1"
set "karaoke_exit=%ERRORLEVEL%"
if not "%karaoke_exit%"=="0" pause
exit /b %karaoke_exit%

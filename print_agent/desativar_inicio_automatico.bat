@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0configurar_inicio.ps1" -DisableStartup
if errorlevel 1 pause
endlocal

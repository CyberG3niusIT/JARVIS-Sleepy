@echo off
setlocal
for /f %%C in ('powershell.exe -NoProfile -Command "[Console]::InputEncoding.CodePage"') do set "JARVIS_OLD_CODEPAGE=%%C"
if not defined JARVIS_OLD_CODEPAGE exit /b 1
chcp 65001 >nul
if errorlevel 1 exit /b 1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0JARVIS-Start.ps1"
set "JARVIS_EXIT=%ERRORLEVEL%"
chcp %JARVIS_OLD_CODEPAGE% >nul
if errorlevel 1 exit /b 1
if not "%JARVIS_EXIT%"=="0" pause
exit /b %JARVIS_EXIT%

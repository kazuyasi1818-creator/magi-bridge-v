@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0keiba_jvlink_first_capture.ps1"
set RC=%ERRORLEVEL%
echo.
if "%RC%"=="0" (
  echo [PASS] Capture completed. Check the HANDOFF path shown above.
) else if "%RC%"=="3" (
  echo [WAIT] Plumbing worked but no usable realtime records were available. Retry on a JRA race date.
) else (
  echo [FAIL] Exit code %RC%. Keep this window open and send the displayed error.
)
echo.
pause
exit /b %RC%

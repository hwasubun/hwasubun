@echo off
rem Register the Dalio signal monitor in Windows Task Scheduler (daily 09:00, local time)
setlocal
set TASK_NAME=DalioSignalMonitor
set APP_DIR=%~dp0

if not exist "%APP_DIR%logs" mkdir "%APP_DIR%logs"

schtasks /Create /F /TN "%TASK_NAME%" /TR "\"%APP_DIR%run_daily.bat\"" /SC DAILY /ST 09:00
if errorlevel 1 (
    echo.
    echo [ERROR] Task registration failed. Try running this file as Administrator.
    exit /b 1
)

echo.
echo [OK] Task "%TASK_NAME%" registered - runs daily at 09:00 (PC local time).
echo      Log file: %APP_DIR%logs\scheduler.log
echo.
echo Run now (test) : schtasks /Run /TN "%TASK_NAME%"
echo Check status   : schtasks /Query /TN "%TASK_NAME%"
echo Remove task    : schtasks /Delete /TN "%TASK_NAME%" /F
endlocal

@echo off
rem Daily signal check - invoked by Windows Task Scheduler (see setup_scheduler.bat)
cd /d "%~dp0"
if not exist logs mkdir logs
".venv\Scripts\python.exe" -X utf8 scheduler.py --once >> "logs\scheduler.log" 2>&1

@echo off
:: Explicitly set working directory to this script's location
pushd "%~dp0"
set PYTHONIOENCODING=utf-8
set PYTHONUNBUFFERED=1

echo [INFO] Performing Pre-Startup Cleanup... >> startup_log.txt
:: Create clean shutdown flag to indicate this is a manual restart
echo. > clean_shutdown.flag
:: Kill any existing python processes and remove lock file to avoid conflict
taskkill /F /IM python.exe /T 2>nul
if exist bot.lock del bot.lock
timeout /t 2 >nul

echo Starting Bot at %date% %time% >> startup_log.txt
".venv\Scripts\python.exe" "telegram_command_bot.py" >> startup_log.txt 2>&1
popd

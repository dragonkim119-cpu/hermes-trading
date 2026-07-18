@echo off
setlocal

echo ===============================================
echo   Hermes Trading - Startup
echo ===============================================

echo.
echo [1/4] Checking worker...
wsl -e bash -lc "pgrep -f '[h]ermes_trading\.run' >/dev/null 2>&1"
if %errorlevel%==0 (
    echo   -^> already running
) else (
    wsl -e bash -lc "cd ~/hermes-trading && nohup uv run python -u -m hermes_trading.run > state/worker.log 2>&1 & disown; sleep 3"
    wsl -e bash -lc "for i in 1 2 3 4 5; do pgrep -f '[h]ermes_trading\.run' >/dev/null 2>&1 && exit 0; sleep 1; done; exit 1"
    if %errorlevel%==0 (
        echo   -^> started
    ) else (
        echo   -^> FAILED to start, check state\worker.log
    )
)

echo.
echo [2/4] Checking dashboard...
wsl -e bash -lc "pgrep -f '[h]ermes_trading\.dashboard' >/dev/null 2>&1"
if %errorlevel%==0 (
    echo   -^> already running
) else (
    wsl -e bash -lc "cd ~/hermes-trading && nohup uv run python -u -m hermes_trading.dashboard > state/dashboard.log 2>&1 & disown; sleep 3"
    wsl -e bash -lc "for i in 1 2 3 4 5; do pgrep -f '[h]ermes_trading\.dashboard' >/dev/null 2>&1 && exit 0; sleep 1; done; exit 1"
    if %errorlevel%==0 (
        echo   -^> started
    ) else (
        echo   -^> FAILED to start, check state\dashboard.log
    )
)

echo.
echo [3/4] Opening dashboard in browser (http://localhost:8787)...
start "" "http://localhost:8787"

echo.
echo [4/4] Opening Hermes chat in a new window...
where wt.exe >nul 2>&1
if %errorlevel%==0 (
    start "" wt.exe wsl.exe -e bash /home/chamsae/hermes-trading/open-hermes.sh
) else (
    start "" wsl.exe -e bash /home/chamsae/hermes-trading/open-hermes.sh
)

echo.
echo ===============================================
echo   Done.
echo   - Dashboard: http://localhost:8787
echo   - Hermes chat should have opened in a new window.
echo     If it did not appear, run manually:
echo       wsl -e bash /home/chamsae/hermes-trading/open-hermes.sh
echo ===============================================
echo.
pause

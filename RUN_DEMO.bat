@echo off
setlocal
cd /d "%~dp0"
set "PYTHON=python"
where py >nul 2>nul
if not errorlevel 1 set "PYTHON=py"
start "Harbour Trust demo server" /D "%~dp0" %PYTHON% -m demo.local_server
timeout /t 2 /nobreak >nul
start "" http://127.0.0.1:8765/
echo The Harbour Trust demo is opening in your browser.
echo Keep the server window open while you present. Press Ctrl+C there to stop it.

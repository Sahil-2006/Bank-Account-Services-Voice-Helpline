@echo off
setlocal
cd /d "%~dp0"
set "PYTHON=python"
where py >nul 2>nul
if not errorlevel 1 set "PYTHON=py"

echo Running transcript replay...
%PYTHON% -m evaluation.run
if errorlevel 1 goto :failed

echo.
echo Running guardrail probes...
%PYTHON% -m evaluation.guards
if errorlevel 1 goto :failed

echo.
echo Verifying both Studio packages...
%PYTHON% -m evaluation.verify_packages
if errorlevel 1 goto :failed

echo.
echo Running invariant checks...
%PYTHON% -m unittest -v evaluation.test_invariants
if errorlevel 1 goto :failed

echo.
echo All local checks passed.
pause
exit /b 0

:failed
echo.
echo A check failed. Read the output above, then send it to the project team.
pause
exit /b 1

@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo First run: creating the local MusicReader environment...
    py -3 -m venv .venv
    if errorlevel 1 goto :error
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    if errorlevel 1 goto :error
    ".venv\Scripts\python.exe" -m pip install -e .
    if errorlevel 1 goto :error
)

".venv\Scripts\python.exe" -m musicreader --gui
exit /b %errorlevel%

:error
echo.
echo MusicReader setup failed. Confirm that Python 3.10 or newer is installed.
pause
exit /b 1

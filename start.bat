@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_CMD="
where py >nul 2>nul
if not errorlevel 1 (
    set "PYTHON_CMD=py -3"
)

if not defined PYTHON_CMD (
    where python >nul 2>nul
    if not errorlevel 1 (
        set "PYTHON_CMD=python"
    )
)

if not defined PYTHON_CMD (
    if exist "%~dp0tools\launcher\python_missing.ps1" (
        powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\launcher\python_missing.ps1"
    ) else (
        echo.
        echo Python was not found.
        echo Please install Python 3.10 or newer, then run start.bat again.
        echo Download: https://www.python.org/downloads/
        echo.
        pause
    )
    exit /b 1
)

call %PYTHON_CMD% "%~dp0tools\launcher\start_helper.py"
if errorlevel 1 (
    echo.
    echo ShapeYourPhoto could not start. Please keep this window open and read the message above.
    pause
    exit /b 1
)

exit /b 0

@echo off
setlocal
cd /d "%~dp0..\.."

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
    echo.
    echo Python was not found. Please install Python 3.10 or newer.
    pause
    exit /b 1
)

call %PYTHON_CMD% "%CD%\tools\launcher\start_helper.py" --install-only
if errorlevel 1 (
    echo.
    echo Dependency installation failed.
    pause
    exit /b 1
)

echo.
echo Dependencies are ready.
pause

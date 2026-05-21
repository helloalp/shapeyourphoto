@echo off
setlocal
set "ROOT=%~dp0..\.."
cd /d "%ROOT%"
set "WAIT_FOR_EXIT=0"
if /I "%~1"=="--check-only" set "WAIT_FOR_EXIT=1"
if /I "%~1"=="--install-only" set "WAIT_FOR_EXIT=1"

set "NATIVE_LAUNCHER=%ROOT%\ShapeYourPhoto.exe"
if exist "%NATIVE_LAUNCHER%" (
    if "%WAIT_FOR_EXIT%"=="0" (
        start "" "%NATIVE_LAUNCHER%" %*
        exit /b 0
    )
    "%NATIVE_LAUNCHER%" %*
    if errorlevel 1 (
        echo.
        echo ShapeYourPhoto could not start. Please keep this window open and read the message above.
        pause
        exit /b 1
    )
    exit /b 0
)

set "BUILT_LAUNCHER=%ROOT%\native\launcher\target\release\ShapeYourPhoto.exe"
if exist "%BUILT_LAUNCHER%" (
    if "%WAIT_FOR_EXIT%"=="0" (
        start "" "%BUILT_LAUNCHER%" %*
        exit /b 0
    )
    "%BUILT_LAUNCHER%" %*
    if errorlevel 1 (
        echo.
        echo ShapeYourPhoto could not start. Please keep this window open and read the message above.
        pause
        exit /b 1
    )
    exit /b 0
)

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
    if exist "%ROOT%\tools\launcher\python_missing.ps1" (
        powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\tools\launcher\python_missing.ps1"
    ) else (
        echo.
        echo Python was not found.
        echo Please install Python 3.10 or newer, then run ShapeYourPhoto.exe again.
        echo Download: https://www.python.org/downloads/
        echo.
        pause
    )
    exit /b 1
)

call %PYTHON_CMD% "%ROOT%\tools\launcher\start_helper.py" %*
if errorlevel 1 (
    echo.
    echo ShapeYourPhoto could not start. Please keep this window open and read the message above.
    pause
    exit /b 1
)

exit /b 0

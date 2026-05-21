@echo off
setlocal
cd /d "%~dp0..\.."

echo [INFO] start_app.bat is a compatibility entry.
echo [INFO] Regular users should run ShapeYourPhoto.exe in a release package.
call "%CD%\tools\launcher\start.bat"

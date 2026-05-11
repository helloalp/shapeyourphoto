@echo off
setlocal
cd /d "%~dp0..\.."

echo [INFO] start_app.bat is a compatibility entry.
echo [INFO] Regular users should run start.bat in the project root.
call "%CD%\start.bat"

@echo off
cd /d "%~dp0"
if not exist "data\map\map.json" goto setup
if not exist "data\map\sketch\0\0_0.webp" goto setup
goto run
:setup
echo First run: downloading map data and artwork. This may take a few minutes.
py -m pip install -r requirements-build.txt || goto failed
py tools\build_map.py || goto failed
:run
py -m silksongtracker
if errorlevel 1 goto failed
exit /b 0
:failed
echo Setup or launch failed. Read README.md for troubleshooting.
pause
exit /b 1

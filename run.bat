@echo off
REM Launch screen-draw without a console window.
REM Falls back to python.exe if pythonw.exe is not on PATH.
setlocal
cd /d "%~dp0"

where pythonw.exe >nul 2>&1
if %errorlevel%==0 (
    start "" pythonw.exe -m screendraw
) else (
    start "" python.exe -m screendraw
)
endlocal

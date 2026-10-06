@echo off
setlocal enabledelayedexpansion

:: ============================================================================
:: end.bat - Double-click this to close the PCB-QA Desktop app that was
:: started with start.bat (in this same folder).
:: ============================================================================

cd /d "%~dp0"

set RUN_DIR=run
set PID_FILE=%RUN_DIR%\app.pid

if not exist "%PID_FILE%" (
    echo No record of a running PCB-QA Desktop started by start.bat was found.
    echo If it's still open, just close its window directly.
    pause
    exit /b 0
)

set "APP_PID="
set /p APP_PID=<"%PID_FILE%"

if not defined APP_PID (
    echo "%PID_FILE%" was empty or unreadable. Nothing to stop.
    del "%PID_FILE%" >NUL 2>&1
    pause
    exit /b 0
)

tasklist /FI "PID eq %APP_PID%" 2>NUL | find /I "%APP_PID%" >NUL
if errorlevel 1 (
    echo PCB-QA Desktop ^(PID %APP_PID%^) isn't running anymore.
    del "%PID_FILE%" >NUL 2>&1
    pause
    exit /b 0
)

echo Stopping PCB-QA Desktop ^(PID %APP_PID%^)...
:: /T kills the whole process tree, not just this one PID. This matters
:: here: on current Python/Windows, ".venv\Scripts\python.exe" is a small
:: launcher stub that spawns a separate CHILD process to actually run
:: main.py (confirmed via Get-CimInstance Win32_Process: the child's
:: ParentProcessId was the stub's PID) -- that child is the one that
:: actually owns the visible Tkinter window. Killing only the captured
:: (parent/stub) PID leaves that child, and the window, still running.
taskkill /PID %APP_PID% /T /F >NUL 2>&1

del "%PID_FILE%" >NUL 2>&1
echo Done.
pause
endlocal

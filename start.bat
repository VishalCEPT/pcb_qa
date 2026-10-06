@echo off
setlocal enabledelayedexpansion

:: ============================================================================
:: start.bat - Double-click this to set up (first run only) and launch the
:: PCB-QA Desktop app. No Docker required -- just a local Python install.
:: See visual_manual_guide_user_testing.md for what to expect once it opens,
:: and end.bat (in this same folder) to close the app later.
:: ============================================================================

cd /d "%~dp0"

set VENV_DIR=.venv
set REQ_STAMP=%VENV_DIR%\.requirements.installed.txt
set RUN_DIR=run
set PID_FILE=%RUN_DIR%\app.pid
set LOG_FILE=%RUN_DIR%\app.log
set ERR_LOG_FILE=%RUN_DIR%\app.err.log

if not exist "%RUN_DIR%" mkdir "%RUN_DIR%"

:: ----------------------------------------------------------------------
:: 1. Don't start a second copy if one is already running.
:: ----------------------------------------------------------------------
if exist "%PID_FILE%" (
    set "OLD_PID="
    set /p OLD_PID=<"%PID_FILE%"
    if defined OLD_PID (
        tasklist /FI "PID eq !OLD_PID!" 2>NUL | find /I "!OLD_PID!" >NUL
        if not errorlevel 1 (
            echo PCB-QA Desktop already appears to be running ^(PID !OLD_PID!^).
            echo If you don't see its window, run end.bat first, then try again.
            pause
            exit /b 0
        )
    )
    del "%PID_FILE%" >NUL 2>&1
)

:: ----------------------------------------------------------------------
:: 2. Find a Python launcher on this machine.
:: ----------------------------------------------------------------------
set "PY_LAUNCHER="
py -3 --version >NUL 2>&1
if not errorlevel 1 set "PY_LAUNCHER=py -3"
if not defined PY_LAUNCHER (
    python --version >NUL 2>&1
    if not errorlevel 1 set "PY_LAUNCHER=python"
)
if not defined PY_LAUNCHER (
    echo [ERROR] Python was not found on PATH.
    echo Install Python 3.10 or newer from https://python.org/downloads/
    echo ^(tick "Add python.exe to PATH" during install^), then run start.bat again.
    pause
    exit /b 1
)

:: ----------------------------------------------------------------------
:: 3. Create/repair the virtual environment if needed.
::
:: A .venv copied in from another machine (e.g. cloned/zipped from a
:: colleague's repo) won't work here -- it's pinned to their exact Python
:: install path, so python.exe inside it simply fails to start. Detect
:: that (rather than just checking the folder exists) and rebuild it
:: automatically instead of leaving you with a confusing crash.
:: ----------------------------------------------------------------------
set NEED_VENV=0
if not exist "%VENV_DIR%\Scripts\python.exe" (
    set NEED_VENV=1
) else (
    "%VENV_DIR%\Scripts\python.exe" --version >NUL 2>&1
    if errorlevel 1 set NEED_VENV=1
)

if "!NEED_VENV!"=="1" (
    echo Setting up a Python environment for this machine ^(first run only^)...
    if exist "%VENV_DIR%" rmdir /s /q "%VENV_DIR%"
    %PY_LAUNCHER% -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [ERROR] Could not create the virtual environment.
        pause
        exit /b 1
    )
)

:: ----------------------------------------------------------------------
:: 4. Install/refresh dependencies, but only when requirements.txt has
:: actually changed since the last successful install (so every later
:: launch is fast, not a multi-minute reinstall every time).
:: ----------------------------------------------------------------------
set NEED_INSTALL=0
if "!NEED_VENV!"=="1" set NEED_INSTALL=1
if not exist "%REQ_STAMP%" set NEED_INSTALL=1
if exist "%REQ_STAMP%" (
    fc /b requirements.txt "%REQ_STAMP%" >NUL 2>&1
    if errorlevel 1 set NEED_INSTALL=1
)

if "!NEED_INSTALL!"=="1" (
    echo Installing dependencies ^(this can take a few minutes the first time^)...
    "%VENV_DIR%\Scripts\python.exe" -m pip install --upgrade pip >>"%LOG_FILE%" 2>&1
    "%VENV_DIR%\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Installing dependencies failed. See "%LOG_FILE%" for details.
        pause
        exit /b 1
    )
    copy /y requirements.txt "%REQ_STAMP%" >NUL
)

:: ----------------------------------------------------------------------
:: 5. Make sure a .env file exists (holds the Gemini API key).
:: ----------------------------------------------------------------------
if not exist ".env" (
    if exist ".env.example" (
        copy ".env.example" ".env" >NUL
        echo A new .env file was created from .env.example.
        echo Open it in Notepad and set GEMINI_API_KEY before using the Q&A/Benchmark tabs
        echo ^(the Board and SPICE Simulation tabs work fine without it^).
        echo.
    )
)

:: ----------------------------------------------------------------------
:: 6. Check ngspice is on PATH. Not fatal -- only the SPICE Simulation
:: tab needs it; the app still opens and every other tab works without it.
:: ----------------------------------------------------------------------
where ngspice >NUL 2>&1
if errorlevel 1 (
    echo [WARNING] ngspice was not found on PATH - the SPICE Simulation tab
    echo won't work until it's installed. Get it from:
    echo   https://ngspice.sourceforge.net/download.html
    echo.
)

:: ----------------------------------------------------------------------
:: 7. Launch the app in the background and remember its process ID so
:: end.bat can stop it later.
::
:: Uses python.exe (not pythonw.exe): several modules in this codebase
:: (core/tool_caller.py, core/kicad_cli_helpers.py, etc.) call plain
:: print() during normal operation. Under pythonw.exe, stdout/stderr
:: don't exist at all, so the very first such print() crashes the whole
:: app with "OSError: [WinError 6] The handle is invalid" -- a well-known
:: Windows+Tkinter gotcha. Redirecting python.exe's own output to log
:: files (instead) keeps a valid stdout/stderr, and this redirection
:: alone is also what keeps python.exe's console window from appearing
:: at all (no separate -WindowStyle needed/wanted here: -WindowStyle
:: Hidden was tried and confirmed, via a real side-by-side screenshot
:: test, to also hide the actual Tkinter window itself, not just a
:: console -- Windows propagates that hidden "show state" hint to the
:: first top-level window the process creates, whatever it is).
:: ----------------------------------------------------------------------
echo Starting PCB-QA Desktop...
powershell -NoProfile -Command ^
    "$p = Start-Process -FilePath '%VENV_DIR%\Scripts\python.exe' -ArgumentList 'main.py'" ^
    "-WorkingDirectory '%cd%'" ^
    "-RedirectStandardOutput '%LOG_FILE%' -RedirectStandardError '%ERR_LOG_FILE%' -PassThru;" ^
    "$p.Id | Out-File -Encoding ascii '%PID_FILE%'"

:: A short settling delay before checking the app is still alive (so an
:: immediate startup crash is reported clearly instead of a false
:: "started successfully"). Uses ping instead of `timeout`: the latter
:: fails outright with "Input redirection is not supported" whenever
:: stdin isn't a real interactive console (seen e.g. when this script is
:: run from some automation/remote contexts) -- ping has no such
:: dependency and reliably takes ~2 seconds for 3 pings to localhost.
ping -n 3 127.0.0.1 >NUL

if exist "%PID_FILE%" (
    set /p APP_PID=<"%PID_FILE%"
    tasklist /FI "PID eq !APP_PID!" 2>NUL | find /I "!APP_PID!" >NUL
    if errorlevel 1 (
        echo [ERROR] PCB-QA Desktop started but exited almost immediately.
        echo Check "%LOG_FILE%" and "%ERR_LOG_FILE%" for the reason.
        del "%PID_FILE%" >NUL 2>&1
    ) else (
        echo PCB-QA Desktop started ^(PID !APP_PID!^). Its window should appear shortly.
        echo Run end.bat to close it later.
    )
) else (
    echo [WARNING] Started the app but couldn't confirm its process ID.
    echo If no window appears within ~10 seconds, check "%LOG_FILE%" and "%ERR_LOG_FILE%" for errors.
)

pause
endlocal

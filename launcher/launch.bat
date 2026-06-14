@echo off
SETLOCAL ENABLEDELAYEDEXPANSION

REM ============================================================
REM  RetailMS Launcher — Double-click RetailMS.vbs to start
REM ============================================================

REM ---------- Configuration ----------
SET "APP_DIR=C:\RetailMS"
SET "PORT=8000"
SET "VENV_DIR=%APP_DIR%\venv"
SET "APP_URL=http://127.0.0.1:%PORT%"
SET "LOG_FILE=%APP_DIR%\server.log"
SET "DJANGO_SETTINGS_MODULE=mrms.settings"
REM -----------------------------------

REM Check if app directory exists
if not exist "%APP_DIR%" (
    echo ERROR: Application directory "%APP_DIR%" not found.
    echo Please run setup.bat first.
    pause
    exit /b 1
)

cd /d "%APP_DIR%"

REM Activate virtual environment
if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo ERROR: Virtual environment not found at "%VENV_DIR%".
    echo Please run setup.bat first.
    pause
    exit /b 1
)
call "%VENV_DIR%\Scripts\activate.bat" >nul 2>&1
if errorlevel 1 (
    echo ERROR: Failed to activate virtual environment.
    pause
    exit /b 1
)

REM ---------- Auto-update check ----------
echo Checking for updates...
ping -n 1 8.8.8.8 >nul 2>&1
if errorlevel 1 (
    echo No internet connection — skipping update check.
    goto START_SERVER
)

REM Capture git hash before pull
for /f "delims=" %%i in ('git rev-parse HEAD 2^>nul') do set "BEFORE_HASH=%%i"

REM Try git pull
git pull origin main >nul 2>&1
if errorlevel 1 (
    echo Update check failed — continuing with current version.
    goto START_SERVER
)

REM Capture git hash after pull
for /f "delims=" %%i in ('git rev-parse HEAD 2^>nul') do set "AFTER_HASH=%%i"

REM If hashes differ, an update was pulled
if not "!BEFORE_HASH!"=="!AFTER_HASH!" (
    echo Update detected. Installing dependencies...
    pip install -r requirements.txt --quiet >nul 2>&1
    python manage.py makemigrations --noinput >nul 2>&1
    python manage.py migrate --run-syncdb >nul 2>&1
    python manage.py collectstatic --noinput >nul 2>&1
    echo Update complete.
) else (
    echo Already up to date.
)

:START_SERVER
REM ---------- Start Django ----------
echo Starting RetailMS server on port %PORT%...
START /B "" "%VENV_DIR%\Scripts\python.exe" manage.py runserver %PORT% > "%LOG_FILE%" 2>&1

REM ---------- Wait for server to be ready ----------
echo Waiting for server to start...
set "READY=0"
for /l %%i in (1,1,15) do (
    powershell -Command "try { $r = Invoke-WebRequest -Uri '%APP_URL%' -TimeoutSec 2 -UseBasicParsing; if ($r.StatusCode) { exit 0 } } catch { exit 1 }" >nul 2>&1
    if !errorlevel! equ 0 (
        set "READY=1"
        goto BROWSER
    )
    REM Sleep 1 second between attempts
    powershell -Command "Start-Sleep -Seconds 1" >nul 2>&1
)

:BROWSER
if "!READY!"=="1" (
    echo Server ready — opening browser.
    start "" "%APP_URL%"
) else (
    echo WARNING: Server may not have started yet. Attempting to open browser anyway...
    start "" "%APP_URL%"
)

REM ---------- Watch for browser close ----------
echo Checking for browser window...
:WATCH_LOOP
powershell -Command "Start-Sleep -Seconds 3" >nul 2>&1

REM Check if a browser window with localhost or 127.0.0.1 in title is still open
powershell -Command "$running = Get-Process | Where-Object { $_.MainWindowTitle -match '127\.0\.0\.1|localhost' }; if ($running) { exit 0 } else { exit 1 }" >nul 2>&1

if !errorlevel! equ 0 (
    goto WATCH_LOOP
)

REM Browser closed — kill Django server
echo Browser closed. Shutting down server...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":!PORT!.*LISTENING" 2^>nul') do (
    taskkill /PID %%a /F >nul 2>&1
)

ENDLOCAL
exit /b 0

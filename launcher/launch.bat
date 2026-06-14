@echo off
setlocal enabledelayedexpansion

REM ============================================================
REM  RetailMS Launcher — Double-click RetailMS.vbs to start
REM ============================================================

REM ---------- Configuration ----------
set "APP_DIR=C:\RetailMS"
set "PORT=8000"
set "VENV_DIR=%APP_DIR%env"
set "APP_URL=http://127.0.0.1:%PORT%"
set "LOG_FILE=%APP_DIR%\server.log"
set "DJANGO_SETTINGS_MODULE=mrms.settings"
REM -----------------------------------

if not exist "%APP_DIR%" (
    echo ERROR: Application directory "%APP_DIR%" not found.
    echo Please run setup.bat first.
    pause
    exit /b 1
)

cd /d "%APP_DIR%"

if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo ERROR: Virtual environment not found.
    echo Please run setup.bat first.
    pause
    exit /b 1
)
call "%VENV_DIR%\Scriptsctivate.bat" >nul 2>&1
if errorlevel 1 (
    echo ERROR: Failed to activate virtual environment.
    pause
    exit /b 1
)

if not exist "%APP_DIR%\logs" mkdir "%APP_DIR%\logs"
if not exist "%APP_DIR%\media" mkdir "%APP_DIR%\media"

REM ---------- Auto-update check ----------
ping -n 1 8.8.8.8 >nul 2>&1
if errorlevel 1 goto START_SERVER

for /f "delims=" %%i in ('git rev-parse HEAD 2^>nul') do set "BEFORE_HASH=%%i"

git pull origin main >nul 2>&1
if errorlevel 1 goto START_SERVER

for /f "delims=" %%i in ('git rev-parse HEAD 2^>nul') do set "AFTER_HASH=%%i"

if not "!BEFORE_HASH!"=="!AFTER_HASH!" (
    pip install -r requirements.txt --quiet >nul 2>&1
    python manage.py migrate --run-syncdb >nul 2>&1
    python manage.py collectstatic --noinput >nul 2>&1
)

:START_SERVER
echo Starting RetailMS on port %PORT%...
START /B "" "%VENV_DIR%\Scripts\python.exe" manage.py runserver %PORT% > "%LOG_FILE%" 2>&1

echo Waiting for server ...
set "READY=0"
for /l %%i in (1,1,15) do (
    powershell -Command "try { Invoke-WebRequest -Uri '%APP_URL%' -TimeoutSec 2 -UseBasicParsing | Out-Null; exit 0 } catch { exit 1 }" >nul 2>&1
    if !errorlevel! equ 0 (
        set "READY=1"
        goto BROWSER
    )
    powershell -Command "Start-Sleep -Seconds 1" >nul 2>&1
)

:BROWSER
if "!READY!"=="1" (
    start "" "%APP_URL%"
)

echo Checking for browser window ...
:WATCH_LOOP
powershell -Command "Start-Sleep -Seconds 3" >nul 2>&1

powershell -Command "if (Get-Process | Where-Object { /home/breezy/Documents/dev/Retail_Management_System.MainWindowTitle -match '127\.0\.0\.1|localhost' }) { exit 0 } else { exit 1 }" >nul 2>&1

if !errorlevel! equ 0 goto WATCH_LOOP

echo Shutting down ...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":!PORT!.*LISTENING" 2^>nul') do (
    taskkill /PID %%a /F >nul 2>&1
)

endlocal
exit /b 0

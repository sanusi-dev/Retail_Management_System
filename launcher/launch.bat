@echo off
setlocal enabledelayedexpansion

REM ============================================================
REM  RetailMS Launcher
REM ============================================================

set "APP_DIR=C:\RetailMS"
set "PORT=8000"
set "VENV_DIR=%APP_DIR%\venv"
set "APP_URL=http://127.0.0.1:%PORT%"
set "LOG_FILE=%APP_DIR%\server.log"
set "DJANGO_SETTINGS_MODULE=mrms.settings"

if not exist "%APP_DIR%" (
    echo ERROR: Application directory not found.
    pause
    exit /b 1
)

cd /d "%APP_DIR%"

if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo ERROR: Virtual environment not found.
    pause
    exit /b 1
)
call "%VENV_DIR%\Scripts\activate.bat" >nul 2>&1

if not exist "%APP_DIR%\logs" mkdir "%APP_DIR%\logs"
if not exist "%APP_DIR%\media" mkdir "%APP_DIR%\media"

REM Auto-update check
ping -n 1 8.8.8.8 >nul 2>&1
if not errorlevel 1 (
    for /f "delims=" %%i in ('git rev-parse HEAD 2^>nul') do set "BEFORE=%%i"
    git pull origin main >nul 2>&1
    if not errorlevel 1 (
        for /f "delims=" %%i in ('git rev-parse HEAD 2^>nul') do set "AFTER=%%i"
        if not "!BEFORE!"=="!AFTER!" (
            pip install -r requirements.txt --quiet >nul 2>&1
            python manage.py migrate --run-syncdb >nul 2>&1
            python manage.py collectstatic --noinput >nul 2>&1
        )
    )
)

REM Start Django
start "RetailMS" "%VENV_DIR%\Scripts\python.exe" manage.py runserver %PORT% > "%LOG_FILE%" 2>&1

REM Wait for server
set "READY=0"
for /l %%i in (1,1,20) do (
    powershell -Command "try { Invoke-WebRequest -Uri '%APP_URL%' -TimeoutSec 2 -UseBasicParsing | Out-Null; exit 0 } catch { exit 1 }" >nul 2>&1
    if !errorlevel! equ 0 (
        set "READY=1"
        goto DONE
    )
    timeout /t 1 /nobreak >nul
)

:DONE
start "" "%APP_URL%"
endlocal
exit /b 0

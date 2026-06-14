@echo off
setlocal enabledelayedexpansion

REM ============================================================
REM  RetailMS — One-Time Setup Script
REM  Run this ONCE. After setup, use the desktop shortcut.
REM ============================================================

REM ---------- Configuration ----------
set "APP_DIR=C:\RetailMS"
set "REPO_URL=https://github.com/sanusi-dev/Retail_Management_System.git"
set "SETUP_DIR=%~dp0"
REM -----------------------------------

title RetailMS Setup

echo ========================================================
echo   Retail Management System — SETUP
echo ========================================================
echo.

REM ---------- Step 1: Check prerequisites ----------
echo [1/9] Checking prerequisites...

echo   Checking Git ...
call :run git --version
if errorlevel 1 (
    echo   FAILED - Git is not installed or not in PATH.
    echo   Download: https://git-scm.com/download/win
    goto :fail
)
echo   Git OK.

echo   Checking Python ...
call :run python --version
if errorlevel 1 (
    echo   FAILED - Python is not installed or not in PATH.
    echo   Download: https://www.python.org/downloads/
    echo   IMPORTANT: Check "Add Python to PATH" during install.
    goto :fail
)
echo   Python OK.

echo.

REM ---------- Step 2: Clone the repo ----------
echo [2/9] Installing application files ...

if exist "%APP_DIR%\.git" (
    echo   Already installed — skipping clone.
) else (
    if not exist "%APP_DIR%" mkdir "%APP_DIR%"
    echo   Cloning from GitHub ...
    call :run git clone "%REPO_URL%" "%APP_DIR%"
    if errorlevel 1 (
        echo   FAILED - Could not clone. Check internet connection.
        echo   If this is a private repo, you may need to install
        echo   GitHub CLI and authenticate first: https://cli.github.com
        goto :fail
    )
    echo   Clone successful.
)

echo.

REM ---------- Step 3: Create virtual environment ----------
echo [3/9] Creating Python virtual environment ...

if exist "%APP_DIR%\venv\Scripts\python.exe" (
    echo   Already exists — skipping.
) else (
    call :run python -m venv "%APP_DIR%\venv"
    if errorlevel 1 (
        echo   FAILED - Could not create virtual environment.
        goto :fail
    )
    echo   Created.
)

echo.

REM ---------- Step 4: Install Python packages ----------
echo [4/9] Installing Python packages (may take a few minutes) ...

call :run "%APP_DIR%\venv\Scripts\pip.exe" install -r "%APP_DIR%\requirements.txt" --quiet
if errorlevel 1 (
    echo   WARNING: Some packages may have failed. The app may still work.
) else (
    echo   Packages installed.
)

echo.

REM ---------- Step 5: Database ----------
echo [5/9] Setting up database ...

if exist "%SETUP_DIR%db.sqlite3" (
    echo   Found database — copying ...
    copy /y "%SETUP_DIR%db.sqlite3" "%APP_DIR%\db.sqlite3" >nul
    echo   Copied.
) else if exist "%APP_DIR%\backups\db_safety_backup_20260210_050520.sqlite3" (
    echo   Found backup database — copying ...
    copy /y "%APP_DIR%\backups\db_safety_backup_20260210_050520.sqlite3" "%APP_DIR%\db.sqlite3" >nul
    echo   Copied.
) else (
    echo   No database found — creating new empty database.
)

cd /d "%APP_DIR%"
call "%APP_DIR%\venv\Scripts\activate.bat" >nul

REM Create required directories that are gitignored
if not exist "%APP_DIR%\logs" mkdir "%APP_DIR%\logs"
if not exist "%APP_DIR%\media" mkdir "%APP_DIR%\media"

call :run python manage.py makemigrations --noinput
call :run python manage.py migrate --run-syncdb
if errorlevel 1 (
    echo   FAILED - Database migration failed.
    goto :fail
)
echo   Database ready.

echo.

REM ---------- Step 6: Static files ----------
echo [6/9] Collecting static files ...

call :run python manage.py collectstatic --noinput
if errorlevel 1 (
    echo   WARNING: collectstatic failed. App may still work.
) else (
    echo   Done.
)

echo.

REM ---------- Step 7: Admin account ----------
echo [7/9] Creating admin account ...
echo   Enter a username, email, and password for your admin login.
echo.

python manage.py createsuperuser

if errorlevel 1 (
    echo   WARNING: Could not create admin account.
    echo   You can create one later by running:
    echo     %APP_DIR%\venv\Scripts\python.exe %APP_DIR%\manage.py createsuperuser
    echo   in a Command Prompt.
)

echo.

REM ---------- Step 8: Launcher files ----------
echo [8/9] Copying launcher files ...

copy /y "%SETUP_DIR%launch.bat" "%APP_DIR%\launch.bat" >nul
copy /y "%SETUP_DIR%RetailMS.vbs" "%APP_DIR%\RetailMS.vbs" >nul

echo   Done.

echo.

REM ---------- Step 9: Desktop shortcut ----------
echo [9/9] Creating desktop shortcut ...

powershell -NoProfile -Command ^
    "$ws = New-Object -ComObject WScript.Shell; ^
     $desktop = [Environment]::GetFolderPath('Desktop'); ^
     $shortcut = $ws.CreateShortcut(\"$desktop\RetailMS.lnk\"); ^
     $shortcut.TargetPath = '%APP_DIR%\RetailMS.vbs'; ^
     $shortcut.WorkingDirectory = '%APP_DIR%'; ^
     $shortcut.Description = 'Launch Retail Management System'; ^
     $shortcut.Save(); ^
     Write-Host 'Shortcut created on Desktop.'"

if errorlevel 1 (
    echo   WARNING: Could not create desktop shortcut.
    echo   Manually: right-click %APP_DIR%\RetailMS.vbs ^> Send to Desktop.
) else (
    echo   Desktop shortcut ready.
)

echo.

echo ========================================================
echo   SETUP COMPLETE!
echo ========================================================
echo.
echo   Double-click "RetailMS" on your desktop to launch.
echo   Login with the admin account you just created.
echo   The app runs at: http://127.0.0.1:8000
echo.
pause
exit /b 0

:fail
echo.
echo   Setup failed. Please check the messages above.
echo   If you need help, contact your developer.
echo.
pause
exit /b 1

:run
echo   Running: %*
%* 2>&1
exit /b %errorlevel%

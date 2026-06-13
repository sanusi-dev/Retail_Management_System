@echo off
SETLOCAL ENABLEDELAYEDEXPANSION

REM ============================================================
REM  RetailMS — One-Time Setup Script
REM  The client runs this ONCE. After setup, they use the
REM  desktop shortcut to launch the app.
REM ============================================================

REM ---------- Configuration ----------
SET "APP_DIR=C:\RetailMS"
SET "REPO_URL=https://github.com/sanusi-dev/Retail_Management_System.git"
REM -----------------------------------

title RetailMS Setup

echo ========================================================
echo   Retail Management System — SETUP
echo ========================================================
echo.

REM ---------- Step 1: Check prerequisites ----------
echo [1/9] Checking prerequisites...

git --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo ERROR: Git is not installed or not in your PATH.
    echo.
    echo Please download Git from: https://git-scm.com/download/win
    echo During installation, accept all default options.
    echo.
    pause
    exit /b 1
)
echo   Git is installed.

python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo ERROR: Python is not installed or not in your PATH.
    echo.
    echo Please download Python from: https://www.python.org/downloads/
    echo.
    echo IMPORTANT: On the first screen of the installer,
    echo check the box that says "Add Python to PATH"
    echo (at the bottom of the window) before clicking Install.
    echo.
    pause
    exit /b 1
)
echo   Python is installed.

echo.

REM ---------- Step 2: Clone the repo ----------
echo [2/9] Installing application files...

if exist "%APP_DIR%\.git" (
    echo   Application directory already exists — skipping clone.
) else (
    if not exist "%APP_DIR%" (
        mkdir "%APP_DIR%"
    )
    echo   Cloning repository to %APP_DIR% ...
    git clone "%REPO_URL%" "%APP_DIR%" >nul 2>&1
    if errorlevel 1 (
        echo.
        echo ERROR: Failed to clone the repository.
        echo Check your internet connection and try again.
        echo.
        pause
        exit /b 1
    )
    echo   Clone successful.
)

echo.

REM ---------- Step 3: Create virtual environment ----------
echo [3/9] Creating Python virtual environment...

if exist "%APP_DIR%\venv\Scripts\python.exe" (
    echo   Virtual environment already exists — skipping.
) else (
    python -m venv "%APP_DIR%\venv" >nul 2>&1
    if errorlevel 1 (
        echo.
        echo ERROR: Failed to create virtual environment.
        echo Please check your Python installation.
        echo.
        pause
        exit /b 1
    )
    echo   Virtual environment created.
)

echo.

REM ---------- Step 4: Install requirements ----------
echo [4/9] Installing Python packages (this may take a few minutes)...

"%APP_DIR%\venv\Scripts\pip.exe" install -r "%APP_DIR%\requirements.txt" --quiet >nul 2>&1
if errorlevel 1 (
    echo.
    echo WARNING: Some packages may have failed to install.
    echo The app may still work. Check server.log if you see errors.
)

echo   Packages installed.

echo.

REM ---------- Step 5: Database setup ----------
echo [5/9] Setting up database...

cd /d "%APP_DIR%"
call "%APP_DIR%\venv\Scripts\activate.bat" >nul 2>&1

REM If a database was provided alongside setup.bat, use it
if exist "%SETUP_DIR%db.sqlite3" (
    echo   Found existing database — copying to application folder...
    copy /y "%SETUP_DIR%db.sqlite3" "%APP_DIR%\db.sqlite3" >nul 2>&1
    echo   Database copied.
) else if exist "%APP_DIR%\backups\db_safety_backup_20260210_050520.sqlite3" (
    echo   Found backup database — copying to application folder...
    copy /y "%APP_DIR%\backups\db_safety_backup_20260210_050520.sqlite3" "%APP_DIR%\db.sqlite3" >nul 2>&1
    echo   Database copied.
)

python manage.py makemigrations --noinput >nul 2>&1
python manage.py migrate --run-syncdb >nul 2>&1
if errorlevel 1 (
    echo.
    echo ERROR: Database migration failed.
    echo Check "%APP_DIR%\server.log" for details.
    echo.
    pause
    exit /b 1
)

echo   Database ready.

echo.

REM ---------- Step 6: Collect static files ----------
echo [6/9] Collecting static files...

python manage.py collectstatic --noinput >nul 2>&1
if errorlevel 1 (
    echo   WARNING: collectstatic failed. The app may still work.
) else (
    echo   Static files collected.
)

echo.

REM ---------- Step 7: Create admin account ----------
echo [7/9] Creating admin account...
echo.
echo   You need an admin account to log into the app.
echo   Please enter a username, email, and password below.
echo.

python manage.py createsuperuser

if errorlevel 1 (
    echo.
    echo   WARNING: Could not create admin account automatically.
    echo   You can create one later by opening a Command Prompt
    echo   in %APP_DIR% and running:
    echo     venv\Scripts\python.exe manage.py createsuperuser
    echo.
)

echo.

REM ---------- Step 8: Copy launcher files ----------
echo [8/9] Copying launcher files...

set "SETUP_DIR=%~dp0"
copy /y "%SETUP_DIR%launch.bat" "%APP_DIR%\launch.bat" >nul 2>&1
copy /y "%SETUP_DIR%RetailMS.vbs" "%APP_DIR%\RetailMS.vbs" >nul 2>&1

echo   Launcher files copied.

echo.

REM ---------- Step 9: Create desktop shortcut ----------
echo [9/9] Creating desktop shortcut...

powershell -NoProfile -Command ^
    "$ws = New-Object -ComObject WScript.Shell; ^
     $desktop = [Environment]::GetFolderPath('Desktop'); ^
     $shortcut = $ws.CreateShortcut(\"$desktop\RetailMS.lnk\"); ^
     $shortcut.TargetPath = '%APP_DIR%\RetailMS.vbs'; ^
     $shortcut.WorkingDirectory = '%APP_DIR%'; ^
     $shortcut.Description = 'Launch Retail Management System'; ^
     $shortcut.Save()" >nul 2>&1

if errorlevel 1 (
    echo   WARNING: Could not create desktop shortcut automatically.
    echo   You can create one manually: right-click on RetailMS.vbs
    echo   in %APP_DIR% and select "Create shortcut", then
    echo   drag it to your desktop.
) else (
    echo   Desktop shortcut created: RetailMS.lnk
)

echo.

echo ========================================================
echo   SETUP COMPLETE!
echo ========================================================
echo.
echo   A "RetailMS" shortcut has been placed on your desktop.
echo   Double-click it to launch the app.
echo.
echo   What happens each time you launch:
echo     - The app checks for updates automatically
echo     - If an update is found, it installs it
echo     - Your web browser opens to the app
echo     - The app closes when you close the browser tab
echo.
echo   Login with the admin account you just created.
echo   The app runs at: http://127.0.0.1:8000
echo.
echo   If you ever need help, check the README in the
echo   %APP_DIR% folder.
echo.
pause

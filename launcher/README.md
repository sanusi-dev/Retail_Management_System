# RetailMS — Windows Desktop Launcher

## For the Developer

### What to send to the client

Put these 4 files on a USB drive:

```
USB Drive:
└── launcher/
    ├── setup.bat
    ├── launch.bat
    ├── RetailMS.vbs
    └── db.sqlite3       ← the real database (renamed backup)
```

The client copies the entire `launcher/` folder to their Desktop and runs `setup.bat` once. After that, they use the desktop shortcut daily.

### Before handing off

1. Confirm `APP_DIR` in both `launch.bat` and `setup.bat` is set to the
   desired install path (default: `C:\RetailMS`).

2. Confirm `REPO_URL` in `setup.bat` matches your GitHub repository
   (currently: `https://github.com/sanusi-dev/Retail_Management_System.git`).

3. Make sure the `launcher/db.sqlite3` file is the correct database with the
   admin password set (default: `admin` / `admin123`).

4. Push the latest code to GitHub — the setup script clones from there.

### How to test locally on a Windows VM

1. Copy the `launcher/` folder to the Windows machine.
2. Right-click `setup.bat` → Run as administrator.
3. Verify the app launches and the dashboard loads.
4. Verify key pages: Customers, Sales, Inventory, Transformations.
5. Close the browser — the server stays running (intentional for single-user use).
6. To stop the server, press Ctrl+C in the RetailMS command window, or restart.

### How the auto-update works

Each launch, `launch.bat`:
1. Checks for internet (pings 8.8.8.8).
2. Runs `git pull origin main`.
3. If new commits were pulled: runs `pip install`, `migrate`, and `collectstatic`.
4. If no update: skips everything to keep startup fast.

The client never needs to run commands manually. To deploy an update, just
push to GitHub — the client gets it on their next launch.

---

## For the Client

### One-time setup (do this ONCE)

**Step 1 — Install Python**
- Download: https://www.python.org/downloads/
- **Important:** Check "Add Python to PATH" on the first screen, then click Install.

**Step 2 — Install Git**
- Download: https://git-scm.com/download/win
- Accept all defaults and click through.

**Step 3 — Run setup**
- Right-click `setup.bat` → **Run as administrator**.
- The setup installs the app, sets up the database, and creates a desktop shortcut.
- Close the window when it says "SETUP COMPLETE".

**Step 4 — Launch**
- Double-click the **RetailMS** icon on your desktop.
- The app opens in your browser at http://127.0.0.1:8000.
- Login with the credentials provided by your developer.

### Everyday use

1. Double-click the **RetailMS** desktop icon.
2. The app opens in your browser.
3. Close the browser when finished — the server stays running in the background.
4. To stop the server: restart your computer, or open Task Manager,
   find "python.exe", and click End Task.

The app checks for updates automatically each time you launch.

---

## Troubleshooting

### The app doesn't open

1. Check the log: open `C:\RetailMS\server.log` in Notepad, look for errors.
2. Make sure Python and Git are installed — open Command Prompt and type:
   ```
   python --version
   git --version
   ```

### "This site can't be reached" / connection refused

- Wait 15 seconds and refresh — the server is still starting.
- Check `C:\RetailMS\server.log` for errors.
- Make sure no other program is using port 8000.

### Port already in use

1. Open `C:\RetailMS\launch.bat` in Notepad.
2. Change `SET "PORT=8000"` to a different number (e.g. `8080`).
3. Save and try again.

### Forgot password

Ask your developer for the login credentials, or create a new admin account:
```
C:\RetailMS\venv\Scripts\python.exe C:\RetailMS\manage.py createsuperuser
```

### Setup fails — can't clone from GitHub

- Check your internet connection.
- If the repository is private, you may need GitHub CLI installed.
  Download from https://cli.github.com and run `gh auth login` first.
- If you still can't connect, ask your developer for help.

### Updates aren't working

- Make sure your computer is connected to the internet.
- If you see "Permission denied", contact your developer.

### Server log shows errors

Open `C:\RetailMS\server.log` in Notepad and send the last 20 lines to your developer.

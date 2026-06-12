# RetailMS — Windows Desktop Launcher

## For the Developer

### Before handing the project to the client:

1. **Update `APP_DIR`** — Open `launch.bat` and `setup.bat` and change the
   `APP_DIR` variable if the client will install to a different location
   (default: `C:\RetailMS`).

2. **Update `REPO_URL`** — Open `setup.bat` and confirm `REPO_URL` matches the
   actual GitHub repository URL (currently:
   `https://github.com/sanusi-dev/Retail_Management_System.git`).

3. **Test the launcher locally** — On a Windows machine, run `launch.bat`
   directly from a Command Prompt to confirm it works before handing off.
   You can also test individual steps:
   ```
   cd launcher
   launch.bat
   ```

### How the auto-update works

Each time the client launches the app, `launch.bat`:
1. Checks for an internet connection
2. Runs `git pull origin main`
3. If new commits were pulled: runs `pip install -r requirements.txt` and
   `python manage.py migrate --run-syncdb`
4. If no update: skips steps to keep startup fast

The client never needs to run `pip` or `migrate` manually.

---

## For the Client

### First-time setup (do this ONCE):

**Step 1 — Install Python**
- Go to https://www.python.org/downloads/ and download the latest version
- **Important:** On the first screen of the installer, check the box that says
  **"Add Python to PATH"** (near the bottom of the window)
- Then click Install Now

**Step 2 — Install Git**
- Go to https://git-scm.com/download/win and download Git
- Run the installer and accept all default options
- Click through to finish

**Step 3 — Run setup**
- Right-click `setup.bat` and select **Run as administrator**
- A window will open and guide you through the setup
- Partway through, you'll be asked to create an admin account —
  enter a username, email, and password of your choice
- The setup installs the app, creates the database, and puts a shortcut on
  your desktop
- Close the window when it says "SETUP COMPLETE"

**Step 4 — Launch the app**
- Double-click the **RetailMS** icon on your desktop
- Your web browser will open to the app
- Log in with the admin account you created during setup
- When you close the browser tab, the app shuts down automatically

### Everyday use

Just double-click the desktop icon. The app will:
- Check for updates automatically
- Open in your browser
- Close when you close your browser

You don't need to do anything else.

---

## Troubleshooting

### The app doesn't open

1. Check the log file: open `C:\RetailMS\server.log` in Notepad and look for
   errors near the bottom.
2. Make sure Python and Git are installed (try typing `python --version` and
   `git --version` in a Command Prompt).

### Setup fails at the Git step

- Reinstall Git from https://git-scm.com/download/win
- Accept all default options during installation
- Run `setup.bat` again

### Setup fails at the Python step

- Reinstall Python from https://www.python.org/downloads/
- **Make sure you check "Add Python to PATH"** on the first installer screen
- Run `setup.bat` again

### Page not found / connection refused

- The server might still be starting; wait 10 seconds and refresh
- Check the log file: `C:\RetailMS\server.log`
- Make sure no other program is using port 8000

### Port is already in use

If another program is using port 8000:
1. Open `C:\RetailMS\launch.bat` in Notepad
2. Find the line that says `SET "PORT=8000"` and change `8000` to a different
   number (e.g. `8080`)
3. Save the file and try again

### Updates aren't working

- Make sure you have internet access
- Try running `git pull origin main` manually in `C:\RetailMS`
- If you see "Permission denied", contact your developer

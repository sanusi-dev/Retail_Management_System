import os
import shutil
import sys
from pathlib import Path
import subprocess

# Configuration
BASE_DIR = Path(__file__).resolve().parent.parent
DIST_DIR = BASE_DIR / "dist_build"
BACKUP_DB_PATH = BASE_DIR / "backups" / "db_original_backup_2026-02-05_05:06:04.sqlite3"
import fnmatch

def custom_ignore(src, names):
    # Standard patterns to ignore everywhere
    ignore_patterns = [
        "*.git*",
        "venv",
        "virtualenv",
        "__pycache__",
        "*.pyc",
        "dist_build",
        "node_modules",
        "backups",
        "logs",
        "*.log",
        ".vscode",
        ".idea",
        "db.sqlite3",  # Exclude current DB
        "tests",
        "*.zip",
    ]
    
    ignored = set()
    for name in names:
        for pattern in ignore_patterns:
            if fnmatch.fnmatch(name, pattern):
                ignored.add(name)
    
    # Only ignore 'dist' at the root level
    if src == str(BASE_DIR) and "dist" in names:
        ignored.add("dist")
        
    return list(ignored)

def build_dist():
    print(f"Building distribution in {DIST_DIR}...")
    
    # Clean previous build
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    
    # Copy project files
    print("Copying project files...")
    shutil.copytree(BASE_DIR, DIST_DIR, ignore=custom_ignore)
    
    # Copy Production DB
    print(f"Restoring production database from {BACKUP_DB_PATH}...")
    if not BACKUP_DB_PATH.exists():
        print(f"ERROR: Backup database not found at {BACKUP_DB_PATH}")
        return
    
    shutil.copy2(BACKUP_DB_PATH, DIST_DIR / "db.sqlite3")
    
    # Create production .env
    print("Creating production .env...")
    env_content = (
        "DEBUG=False\n"
        "SECRET_KEY=django-insecure-production-key-change-this\n"  # Ideally should be random or from prompt
        "ALLOWED_HOSTS=*\n"
    )
    with open(DIST_DIR / ".env", "w") as f:
        f.write(env_content)
        
    # Create logs directory
    (DIST_DIR / "logs").mkdir(exist_ok=True)
    
    # Collect Static
    print("Collecting static files...")
    # We run collectstatic using the CURRENT environment but targeting the DIST_DIR
    # We need to set STATIC_ROOT in the environment for this command to work effectively
    # OR we can just run it in the dist folder if the current env has django installed (which it does)
    
    # We will use the Manage.py in the DIST dir, but with the current python executable
    # We need to force STATIC_ROOT to be inside DIST_DIR/staticfiles
    
    env = os.environ.copy()
    # We might need to adjust settings or pass a flag, but standard collectstatic consults settings.
    # The settings.py in DIST_DIR is the same as source.
    # STATIC_ROOT there defaults to BASE_DIR / "staticfiles".
    # So if we run manage.py inside DIST_DIR, it should collect to DIST_DIR/staticfiles.
    
    try:
        subprocess.run(
            [sys.executable, str(DIST_DIR / "manage.py"), "collectstatic", "--noinput", "--clear"],
            cwd=DIST_DIR,
            env=env,
            check=True
        )
    except subprocess.CalledProcessError as e:
        print(f"Error collecting static files: {e}")
        return

    print("Build complete!")
    print(f"Distribution ready at: {DIST_DIR}")

if __name__ == "__main__":
    build_dist()

import os
import sys
import shutil
import subprocess
import time
import tempfile

def kill_process_by_name(name):
    """Kill a process by name using taskkill."""
    try:
        subprocess.run(
            ['taskkill', '/F', '/IM', name], 
            stdout=subprocess.DEVNULL, 
            stderr=subprocess.DEVNULL
        )
    except Exception:
        pass

def uninstall():
    print("=" * 50)
    print("Insta Outreach Logger - Uninstaller")
    print("=" * 50)
    
    confirm = input("\nAre you sure you want to completely remove the application and all data? (yes/no): ").strip().lower()
    if confirm != 'yes':
        print("Uninstall cancelled.")
        sys.exit(0)

    print("\n[1/3] Closing application processes...")
    # Kill common processes if running
    kill_process_by_name("InstaLogger.exe")
    kill_process_by_name("launcher.exe")
    kill_process_by_name("python.exe") # Be careful with this one in dev, but standard for uninstallers

    # Define paths
    docs_dir = os.path.join(os.path.expanduser("~"), "Documents")
    app_data_dir = os.path.join(docs_dir, "Insta Logger Remastered")
    
    # Current script directory (Project Root)
    if getattr(sys, 'frozen', False):
        project_root = os.path.dirname(sys.executable)
    else:
        project_root = os.path.dirname(os.path.abspath(__file__))

    # 2. Delete Documents Data
    if os.path.exists(app_data_dir):
        print(f"[2/3] Removing data directory: {app_data_dir}")
        try:
            shutil.rmtree(app_data_dir)
            print("      Data removed successfully.")
        except Exception as e:
            print(f"      Error removing data: {e}")
    else:
        print("[2/3] Data directory not found (already removed).")

    # 3. Create Self-Destruct Script
    print(f"[3/3] preparing to remove application files from: {project_root}")
    
    batch_script = os.path.join(tempfile.gettempdir(), "iol_cleanup.bat")
    
    with open(batch_script, "w") as f:
        f.write("@echo off\n")
        f.write("timeout /t 3 /nobreak > NUL\n") # Wait for python to exit
        f.write(f'rmdir /s /q "{project_root}"\n')
        f.write(f'del "%~f0"\n') # Delete script itself
    
    print("\nUninstallation complete. The remaining files will be removed in 3 seconds.")
    print("Goodbye!")
    
    # Launch cleanup script detached
    subprocess.Popen(batch_script, shell=True)
    sys.exit(0)

if __name__ == "__main__":
    uninstall()


import os
import sys
import shutil
import json
import subprocess
import winreg
import argparse
import traceback

"""
Dev Launcher for Insta Outreach Logger
--------------------------------------
Simulates the installation process for Development Mode:
1. Deploys the Chrome Extension to 'Documents/Insta Logger Remastered/extension'
   (while searching for it in 'src/extension' or 'src/extension').
2. Registers the Native Messaging Host to point to the SOURCE 'src/core/bridge.bat'.
3. Launches the main 'launcher.py'.

Usage:
    python dev_launcher.py
"""

APP_NAME = "Insta Outreach Logger"
DOCS_DIR = os.path.join(os.path.expanduser("~"), "Documents", "Insta Logger Remastered")
EXT_TARGET_DIR = os.path.join(DOCS_DIR, "extension")
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

def log(msg, level="INFO"):
    print(f"[{level}] {msg}")

def deploy_extension():
    """Copy extension files to Documents, preserving source."""
    log(f"Deploying extension to: {EXT_TARGET_DIR}")
    
    # 1. Find Source
    source_path = os.path.join(PROJECT_ROOT, 'src', 'extension')
    if not os.path.exists(source_path):
        # Try local fallback
        if os.path.exists(os.path.join(PROJECT_ROOT, 'extension')):
            source_path = os.path.join(PROJECT_ROOT, 'extension')
    
    if not os.path.exists(source_path):
        log(f"Extension source not found at {source_path}", "ERROR")
        return False

    # 2. Clear Target
    if os.path.exists(EXT_TARGET_DIR):
        try:
            shutil.rmtree(EXT_TARGET_DIR)
        except Exception as e:
            log(f"Failed to clear target dir: {e}. Chrome might be locking files.", "ERROR")
            return False

    # 3. Copy (Preserve Source)
    try:
        shutil.copytree(source_path, EXT_TARGET_DIR)
        log("Extension files deployed successfully.")
        return True
    except Exception as e:
        log(f"Copy failed: {e}", "ERROR")
        return False

def register_native_host():
    """Register the Native Host Manifest in Registry to point to dev bridge."""
    try:
        bridge_bat = os.path.join(PROJECT_ROOT, 'src', 'core', 'bridge.bat')
        manifest_src = os.path.join(PROJECT_ROOT, 'src', 'core', 'com.instaoutreach.logger.json')
        
        if not os.path.exists(bridge_bat):
            log(f"bridge.bat not found at {bridge_bat}", "ERROR")
            return

        # If Manifest doesn't exist, create it from scratch
        if not os.path.exists(manifest_src):
            log(f"Manifest not found. Creating new at {manifest_src}")
            data = {
                "name": "com.instaoutreach.logger",
                "description": "Native Host",
                "path": bridge_bat,
                "type": "stdio",
                "allowed_origins": [
                    "chrome-extension://clbpjppnmamfdkglgkhdldofpcfljilc/" 
                ]
            }
        else:
            # Update Manifest Path
            with open(manifest_src, 'r') as f:
                data = json.load(f)
        
        data['path'] = bridge_bat
        
        # Write back to source (or should we write to documents??)
        # For dev mode, writing to source is fine as it keeps it in sync.
        # But `launcher.py` might try to overwrite it.
        # Let's ensure the Registry points to THIS manifest.

        with open(manifest_src, 'w') as f:
            json.dump(data, f, indent=4)
        
        # Registry
        key_path = r"Software\Google\Chrome\NativeMessagingHosts\com.instaoutreach.logger"
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path)
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, manifest_src)
        winreg.CloseKey(key)
        
        log(f"Success: Registry set to {manifest_src}")
        log(f"Success: Manifest points to {bridge_bat}")
        
    except Exception as e:
        log(f"Registration failed: {e}", "ERROR")

def cleanup_environment():
    """Reset local configuration for a fresh start."""
    print("--- Cleaning Environment ---")
    files_to_remove = [
        "operator_config.json",
        "update_config.json",
        "user_preferences.json"
    ]
    
    for filename in files_to_remove:
        path = os.path.join(PROJECT_ROOT, filename)
        if os.path.exists(path):
            try:
                os.remove(path)
                log(f"Removed: {filename}")
            except Exception as e:
                log(f"Failed to remove {filename}: {e}", "WARNING")
    
    # We DO NOT remove .env or key.pem as those are dev assets


def main():
    parser = argparse.ArgumentParser(description="Insta Outreach Logger Dev Launcher")
    parser.add_argument("--freshrun", action="store_true", help="Fresh start: Wipe config files before launch")
    args = parser.parse_args()

    print(f"--- {APP_NAME} Dev Launcher ---")
    
    # 0. Fresh Start Cleanup
    if args.freshrun:
        cleanup_environment()
    else:
        print("[Dev] Skipping environment cleanup (Use --freshrun to wipe configs)")

    # 1. Deploy
    if not deploy_extension():
        print("Extension deployment failed. Check logs.")
        # We continue anyway? No, typical dev flow.
    
    # 2. Register
    register_native_host()
    
    # 3. Launch
    print("\nStarting Launcher...")
    cmd = [sys.executable, "launcher.py", "--skip-update"]
    subprocess.run(cmd)

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Insta Outreach Logger - Launcher (Bootstrapper)

This is the main entry point for the compiled application.
It handles:
1. First-run setup (launches Setup Wizard if credentials missing)
2. Auto-update from GitHub Releases
3. Launching the main IPC server

Usage:
    python launcher.py [--skip-update] [--debug]
"""

import os
import sys
import json
import urllib.request
import urllib.error
import tempfile
import shutil
import subprocess
import argparse
import traceback
import datetime

# --- Crash Log Setup ---
# Log crashes to a file for debugging compiled exe issues
if getattr(sys, 'frozen', False):
    CRASH_LOG_PATH = os.path.join(os.path.dirname(sys.executable), 'crash_log.txt')
else:
    CRASH_LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'crash_log.txt')


def log_crash(error_msg, exc_info=None):
    """Write crash information to a log file."""
    try:
        with open(CRASH_LOG_PATH, 'a', encoding='utf-8') as f:
            f.write(f"\n{'='*60}\n")
            f.write(f"CRASH LOG - {datetime.datetime.now().isoformat()}\n")
            f.write(f"{'='*60}\n")
            f.write(f"Error: {error_msg}\n")
            if exc_info:
                f.write(f"\nTraceback:\n")
                f.write(traceback.format_exc())
            f.write(f"\nPython: {sys.version}\n")
            f.write(f"Frozen: {getattr(sys, 'frozen', False)}\n")
            f.write(f"Executable: {sys.executable}\n")
            f.write(f"\n")
    except Exception as e:
        print(f"Could not write crash log: {e}")


def show_error_message(title, message):
    """Show an error message dialog, handling potential Tkinter state issues."""
    try:
        import tkinter as tk
        from tkinter import messagebox as mb
        root = tk.Tk()
        root.withdraw()
        mb.showerror(title, message)
        root.destroy()
    except Exception:
        # Fallback to console if GUI fails
        print(f"\n[ERROR] {title}: {message}")


def show_warning_message(title, message):
    """Show a warning message dialog, handling potential Tkinter state issues."""
    try:
        import tkinter as tk
        from tkinter import messagebox as mb
        root = tk.Tk()
        root.withdraw()
        mb.showwarning(title, message)
        root.destroy()
    except Exception:
        # Fallback to console if GUI fails
        print(f"\n[WARNING] {title}: {message}")

# --- Path Setup ---
# Handle both frozen (PyInstaller) and development environments
if getattr(sys, 'frozen', False):
    # Running as compiled exe
    SCRIPT_DIR = os.path.dirname(sys.executable)
    PROJECT_ROOT = SCRIPT_DIR
else:
    # Running as script
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = SCRIPT_DIR

sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'src'))
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'src', 'core'))

# Import version info
try:
    from src.core.version import __version__, __app_name__, GITHUB_OWNER, GITHUB_REPO, compare_versions
except ImportError:
    __version__ = "0.0.0"
    __app_name__ = "Insta Outreach Logger"
    GITHUB_OWNER = "hashaam101"
    GITHUB_REPO = "Insta-Outreach-Logger-Remastered"

    def compare_versions(v1, v2):
        v1_parts = [int(x) for x in v1.lstrip('v').split('.')]
        v2_parts = [int(x) for x in v2.lstrip('v').split('.')]
        for a, b in zip(v1_parts, v2_parts):
            if a < b:
                return -1
            elif a > b:
                return 1
        return 0


class Launcher:
    """
    Application bootstrapper that handles setup and auto-updates.
    """

    def __init__(self, skip_update=False, debug=False):
        self.skip_update = skip_update
        self.debug = debug
        self.config_path = os.path.join(PROJECT_ROOT, 'local_config.py')
        self.wallet_path = os.path.join(PROJECT_ROOT, 'assets', 'wallet', 'cwallet.sso')

    def log(self, message, level="INFO"):
        """Print log message with level prefix."""
        if self.debug or level in ["ERROR", "WARNING"]:
            print(f"[{level}] {message}")

    def check_credentials(self):
        """Check if required credentials exist."""
        config_exists = os.path.exists(self.config_path)
        wallet_exists = os.path.exists(self.wallet_path)

        self.log(f"Config exists: {config_exists} ({self.config_path})")
        self.log(f"Wallet exists: {wallet_exists} ({self.wallet_path})")

        return config_exists and wallet_exists

    def run_setup_wizard(self):
        """Launch the setup wizard for first-time configuration."""
        self.log("Launching Setup Wizard...")
        print("[Launcher] Starting setup wizard import...")

        try:
            from src.gui.setup_wizard import run_setup_wizard
            print("[Launcher] Setup wizard imported successfully")

            print("[Launcher] Running setup wizard...")
            success = run_setup_wizard()
            print(f"[Launcher] Setup wizard returned: {success}")

            if not success:
                self.log("Setup wizard was cancelled or failed.", "WARNING")
                return False

            print("[Launcher] Checking credentials after setup...")
            result = self.check_credentials()
            print(f"[Launcher] Credentials check result: {result}")
            return result

        except ImportError as e:
            self.log(f"Failed to import setup wizard: {e}", "ERROR")
            log_crash(f"Setup wizard import error: {e}", exc_info=True)
            show_error_message(
                "Setup Error",
                f"Could not load the Setup Wizard.\n\n"
                f"Please ensure all dependencies are installed.\n\n"
                f"Error: {e}"
            )
            return False

        except Exception as e:
            self.log(f"Setup wizard error: {e}", "ERROR")
            log_crash(f"Setup wizard error: {e}", exc_info=True)
            traceback.print_exc()
            return False

    def check_for_updates(self):
        """
        Check GitHub Releases for a newer version.
        Returns (update_available, latest_version, download_url) or (False, None, None) on error.
        """
        if self.skip_update:
            self.log("Update check skipped (--skip-update flag)")
            return False, None, None

        self.log(f"Checking for updates... (current: v{__version__})")

        api_url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"

        try:
            request = urllib.request.Request(
                api_url,
                headers={
                    'Accept': 'application/vnd.github.v3+json',
                    'User-Agent': f'{__app_name__}/{__version__}'
                }
            )

            with urllib.request.urlopen(request, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))

            latest_tag = data.get('tag_name', '')
            latest_version = latest_tag.lstrip('v')

            self.log(f"Latest release: {latest_tag}")

            # Compare versions
            if compare_versions(__version__, latest_version) < 0:
                # Find the .exe asset
                download_url = None
                for asset in data.get('assets', []):
                    if asset['name'].lower().endswith('.exe'):
                        download_url = asset['browser_download_url']
                        break

                if download_url:
                    self.log(f"Update available: v{__version__} -> v{latest_version}")
                    return True, latest_version, download_url
                else:
                    self.log("Update available but no .exe asset found.")
                    return False, latest_version, None
            else:
                self.log("Already up to date.")
                return False, None, None

        except urllib.error.HTTPError as e:
            if e.code == 404:
                self.log("No releases found on GitHub.", "WARNING")
            else:
                self.log(f"GitHub API error: {e}", "WARNING")
            return False, None, None

        except urllib.error.URLError as e:
            self.log(f"Network error checking updates: {e}", "WARNING")
            return False, None, None

        except Exception as e:
            self.log(f"Error checking updates: {e}", "WARNING")
            return False, None, None

    def download_update(self, download_url, new_version):
        """
        Download the update from the given URL.
        Returns the path to the downloaded file or None on failure.
        """
        self.log(f"Downloading update from: {download_url}")

        try:
            # Create temp file for download
            temp_dir = tempfile.mkdtemp(prefix="instalogger_update_")
            temp_file = os.path.join(temp_dir, f"InstaLogger_v{new_version}.exe")

            request = urllib.request.Request(
                download_url,
                headers={'User-Agent': f'{__app_name__}/{__version__}'}
            )

            with urllib.request.urlopen(request, timeout=120) as response:
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                chunk_size = 8192

                with open(temp_file, 'wb') as f:
                    while True:
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)

                        if total_size > 0:
                            percent = (downloaded / total_size) * 100
                            print(f"\rDownloading... {percent:.1f}%", end='', flush=True)

                print()  # New line after progress

            self.log(f"Download complete: {temp_file}")
            return temp_file

        except Exception as e:
            self.log(f"Download failed: {e}", "ERROR")
            return None

    def apply_update(self, update_path):
        """
        Apply the downloaded update.
        This renames the current exe, moves in the new one, and restarts.
        """
        if not getattr(sys, 'frozen', False):
            self.log("Cannot apply update in development mode.", "WARNING")
            return False

        try:
            current_exe = sys.executable
            backup_exe = current_exe + ".old"

            self.log(f"Applying update...")
            self.log(f"  Current: {current_exe}")
            self.log(f"  New: {update_path}")

            # Remove old backup if exists
            if os.path.exists(backup_exe):
                os.remove(backup_exe)

            # Rename current exe to .old
            os.rename(current_exe, backup_exe)

            # Move new exe into place
            shutil.move(update_path, current_exe)

            self.log("Update applied successfully!")
            self.log("Restarting application...")

            # Restart the application
            subprocess.Popen([current_exe] + sys.argv[1:])
            sys.exit(0)

        except Exception as e:
            self.log(f"Failed to apply update: {e}", "ERROR")

            # Try to restore backup
            if os.path.exists(backup_exe) and not os.path.exists(current_exe):
                os.rename(backup_exe, current_exe)
                self.log("Restored backup executable.")

            return False

    def prompt_for_update(self, new_version, download_url):
        """Ask user if they want to update."""
        try:
            import tkinter as tk
            from tkinter import messagebox as mb

            root = tk.Tk()
            root.withdraw()

            result = mb.askyesno(
                "Update Available",
                f"A new version is available!\n\n"
                f"Current: v{__version__}\n"
                f"Latest: v{new_version}\n\n"
                f"Would you like to update now?"
            )

            root.destroy()
            return result

        except Exception:
            # If GUI fails, skip update
            return False

    def launch_main_app(self):
        """Launch the main IPC server."""
        self.log("Launching main application...")
        print("[Launcher] Preparing to launch main app...")

        try:
            # Change to project root directory
            print(f"[Launcher] Changing directory to: {PROJECT_ROOT}")
            os.chdir(PROJECT_ROOT)

            # Import and run the IPC server
            print("[Launcher] Importing IPC server...")
            from src.core.ipc_server import IPCServer
            print("[Launcher] IPC server imported successfully")

            print("=" * 50)
            print(f"  {__app_name__}")
            print(f"  Version {__version__}")
            print("=" * 50)

            print("[Launcher] Creating IPCServer instance...")
            server = IPCServer()
            print("[Launcher] IPCServer created, starting...")

            try:
                server.start()
            except KeyboardInterrupt:
                print("\n[Launcher] Shutdown requested...")
            finally:
                server.stop()

        except ImportError as e:
            self.log(f"Failed to import main application: {e}", "ERROR")
            log_crash(f"IPC Server import error: {e}", exc_info=True)
            traceback.print_exc()
            show_error_message(
                "Launch Error",
                f"Could not start the application.\n\n"
                f"Please ensure all dependencies are installed.\n\n"
                f"Error: {e}"
            )
            sys.exit(1)

        except Exception as e:
            self.log(f"Application error: {e}", "ERROR")
            log_crash(f"Application error: {e}", exc_info=True)
            traceback.print_exc()
            sys.exit(1)

    def ensure_native_host_registration(self):
        """
        Self-Repair: Ensures the Native Messaging Host is correctly registered
        for the current file path. Critical for when the app is moved or run on a new VM.
        """
        try:
            import winreg

            # 1. Locate bridge.bat and manifest
            # Logic: We are in PROJECT_ROOT. bridge.bat should be in src/core/
            bridge_path = os.path.join(PROJECT_ROOT, 'src', 'core', 'bridge.bat')
            
            # If running frozen (PyInstaller), it might be in _internal
            if getattr(sys, 'frozen', False):
                 bridge_path = os.path.join(PROJECT_ROOT, '_internal', 'src', 'core', 'bridge.bat')
            
            if not os.path.exists(bridge_path):
                 # Fallback search
                 if os.path.exists(os.path.join(PROJECT_ROOT, 'src', 'core', 'bridge.bat')):
                     bridge_path = os.path.join(PROJECT_ROOT, 'src', 'core', 'bridge.bat')
                 else:
                    self.log(f"Could not find bridge.bat at {bridge_path}", "WARNING")
                    return

            bridge_path = os.path.abspath(bridge_path)
            manifest_path = os.path.join(os.path.dirname(bridge_path), 'com.instaoutreach.logger.json')

            if not os.path.exists(manifest_path):
                self.log(f"Manifest json not found at {manifest_path}. Skipping registration repair.", "WARNING")
                return

            # 2. Update Manifest 'path' to current location
            with open(manifest_path, 'r') as f:
                manifest_data = json.load(f)

            current_json_path = manifest_data.get('path', '')
            if current_json_path != bridge_path:
                self.log(f"Repairing manifest path: {bridge_path}")
                manifest_data['path'] = bridge_path
                with open(manifest_path, 'w') as f:
                    json.dump(manifest_data, f, indent=4)

            # 3. Update Windows Registry
            reg_path = r"Software\Google\Chrome\NativeMessagingHosts\com.instaoutreach.logger"
            try:
                key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, reg_path)
                winreg.SetValueEx(key, "", 0, winreg.REG_SZ, manifest_path)
                winreg.CloseKey(key)
                self.log(f"Registry key verified/updated: {reg_path}")
            except Exception as e:
                self.log(f"Failed to update registry: {e}", "ERROR")

        except Exception as e:
            self.log(f"Registration repair failed: {e}", "ERROR")

    def run(self):
        """
        Main launcher workflow:
        1. Check credentials -> Run setup wizard if missing
        2. Check for updates -> Download and apply if available
        3. Launch main application
        """
        print(f"\n{__app_name__} v{__version__}")
        print("-" * 40)

        # Step 1: Check credentials
        print("[Launcher] Step 1: Checking credentials...")
        if not self.check_credentials():
            self.log("Credentials not found. Starting setup wizard...")

            if not self.run_setup_wizard():
                self.log("Setup incomplete. Exiting.", "ERROR")
                show_warning_message(
                    "Setup Required",
                    "The application cannot start without credentials.\n\n"
                    "Please run the setup wizard and provide your Setup_Pack.zip file."
                )
                sys.exit(1)

            self.log("Setup complete!")
            print("[Launcher] Setup wizard completed successfully")

        print("[Launcher] Credentials verified")

        # Step 1.5: Ensure Native Host is Registered (Self-Repair)
        print("[Launcher] Step 1.5: Verifying Native Host Registration...")
        self.ensure_native_host_registration()

        # Step 2: Check for updates
        print("[Launcher] Step 2: Checking for updates...")
        update_available, new_version, download_url = self.check_for_updates()

        if update_available and download_url:
            if self.prompt_for_update(new_version, download_url):
                update_path = self.download_update(download_url, new_version)
                if update_path:
                    self.apply_update(update_path)
                    # If we get here, apply_update failed
                    self.log("Update failed. Continuing with current version.", "WARNING")
            else:
                self.log("User declined update.")

        print("[Launcher] Update check completed")

        # Step 3: Launch main application
        print("[Launcher] Step 3: Launching main application...")
        self.launch_main_app()


def main():
    """Entry point with argument parsing."""
    parser = argparse.ArgumentParser(
        description=f"{__app_name__} Launcher"
    )
    parser.add_argument(
        '--skip-update',
        action='store_true',
        help='Skip the automatic update check'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )
    parser.add_argument(
        '--version',
        action='version',
        version=f'{__app_name__} v{__version__}'
    )
    parser.add_argument(
        '--bridge',
        action='store_true',
        help='Run in Native Messaging Bridge mode'
    )

    args = parser.parse_args()

    # Special Mode: Bridge
    if args.bridge:
        try:
            from src.core.bridge import main as bridge_main
            bridge_main()
        except ImportError as e:
            # Fallback logging if imports fail in bridge mode
            with open('bridge_startup_error.log', 'w') as f:
                f.write(f"Failed to start bridge: {e}")
        return

    launcher = Launcher(
        skip_update=args.skip_update,
        debug=args.debug
    )
    launcher.run()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log_crash(f"Unhandled exception in main: {e}", exc_info=True)
        
        # In bridge mode, DO NOT print to stdout as it breaks Chrome communication
        if '--bridge' in sys.argv:
            sys.exit(1)

        print(f"\n[FATAL ERROR] {e}")
        print(f"Crash log written to: {CRASH_LOG_PATH}")
        input("Press Enter to exit...")  # Keep console open
        sys.exit(1)

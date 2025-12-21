import os
import sys
import glob
import re
import shutil
import tempfile
import pyzipper
from src.core.security import get_zip_password

# Default location for the secure zip
DOCUMENTS_DIR = os.path.join(os.path.expanduser("~"), "Documents")
SECRETS_DIR = os.path.join(DOCUMENTS_DIR, "Insta Logger Remastered", "secrets")

class SecretsManager:
    """
    Context manager to securely handle credentials.
    1. Finds encrypted Setup Pack in Documents.
    2. Decrypts to a RAM-disk like temporary directory (or standard temp).
    3. Sets up environment for the application to use them.
    4. Wipes traces on exit.
    """
    
    def __init__(self):
        self.temp_dir = None
        self.wallet_dir = None
        self.zip_path = self._find_secure_zip()
        
    def _find_secure_zip(self):
        """Find the Setup_Pack_TOKEN.zip in the secrets directory."""
        if not os.path.exists(SECRETS_DIR):
            return None
            
        # Look for pattern
        files = glob.glob(os.path.join(SECRETS_DIR, "Setup_Pack_*.zip"))
        if not files:
            return None
            
        # Return the newest one if multiple
        return max(files, key=os.path.getmtime)

    def _get_password_from_filename(self, zip_path):
        """Derive password from token in filename."""
        filename = os.path.basename(zip_path)
        match = re.search(r'Setup_Pack_([a-fA-F0-9]+)\.zip', filename)
        if match:
            return get_zip_password(match.group(1))
        return None

    def __enter__(self):
        if not self.zip_path:
            # Fallback for dev environment or unconfigured state
            # The app might fail later if it needs real creds, but we don't crash here.
            print("[SecretsManager] No secure zip found. Using local environment if available.")
            return self

        try:
            password = self._get_password_from_filename(self.zip_path)
            if not password:
                raise ValueError("Could not derive password from zip filename")

            # Create secure temp directory
            self.temp_dir = tempfile.mkdtemp(prefix="iol_sec_")
            self.wallet_dir = os.path.join(self.temp_dir, 'wallet')
            
            print(f"[SecretsManager] Unlocking credentials from {os.path.basename(self.zip_path)}...")

            with pyzipper.AESZipFile(self.zip_path, 'r') as zf:
                zf.setpassword(password)
                
                # Extract all files
                zf.extractall(self.temp_dir)

            # 1. Setup Wallet Path (Environment Variable)
            # This allows DatabaseManager to find it
            if os.path.exists(self.wallet_dir):
                os.environ['DB_WALLET_DIR'] = self.wallet_dir
                print(f"[SecretsManager] Wallet mounted at temporary location.")
            
            # 2. Setup Config Module (sys.path)
            # This allows 'import local_config' to work
            if os.path.exists(os.path.join(self.temp_dir, 'local_config.py')):
                sys.path.insert(0, self.temp_dir)
                print(f"[SecretsManager] Config module loaded.")

            return self

        except Exception as e:
            # Cleanup immediately on failure
            self._cleanup()
            print(f"[SecretsManager] Failed to unlock secrets: {e}")
            raise

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._cleanup()

    def _cleanup(self):
        """Remove temporary files and environment changes."""
        # Restore sys.path
        if self.temp_dir and self.temp_dir in sys.path:
            sys.path.remove(self.temp_dir)
        
        # Unset env var
        if 'DB_WALLET_DIR' in os.environ:
            del os.environ['DB_WALLET_DIR']

        # Wipe temp dir
        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
                print("[SecretsManager] Secure session closed. Temporary files wiped.")
            except Exception as e:
                print(f"[SecretsManager] Warning: Could not fully wipe temp dir: {e}")
        
        self.temp_dir = None

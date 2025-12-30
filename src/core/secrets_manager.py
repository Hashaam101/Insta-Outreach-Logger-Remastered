import os
import sys
import glob
import re
import shutil
import tempfile
import pyzipper
from src.core.security import get_zip_password
from dotenv import load_dotenv

# Default location for the secure zip
DOCUMENTS_DIR = os.path.join(os.path.expanduser("~"), "Documents")
SECRETS_DIR = os.path.join(DOCUMENTS_DIR, "Insta Logger Remastered", "secrets")

class SecretsManager:
    """
    Context manager to securely handle credentials.
    
    Oracle Wallet has been replaced with TLS connection strings.
    This manager now only:
    1. Finds encrypted Setup Pack in Documents (or uses local .env)
    2. Extracts .env file to temporary directory
    3. Loads environment variables for database connection
    4. Wipes traces on exit
    
    Note: DB_DSN should contain a TLS connection string like:
    (description=(retry_count=3)(address=(protocol=tcps)(port=1522)(host=...))...)
    """
    
    def __init__(self):
        self.temp_dir = None
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
        # Load .env file from project root
        if getattr(sys, 'frozen', False):
            project_root = os.path.dirname(sys.executable)
        else:
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        
        env_path = os.path.join(project_root, '.env')
        if os.path.exists(env_path):
            load_dotenv(env_path)
        
        if not self.zip_path:
            # Fallback for dev environment or unconfigured state
            print("[SecretsManager] No secure zip found. Using .env configuration.")
            return self

        try:
            password = self._get_password_from_filename(self.zip_path)
            if not password:
                raise ValueError("Could not derive password from zip filename")

            # Create secure temp directory
            self.temp_dir = tempfile.mkdtemp(prefix="iol_sec_")
            
            print(f"[SecretsManager] Unlocking credentials from {os.path.basename(self.zip_path)}...")

            with pyzipper.AESZipFile(self.zip_path, 'r') as zf:
                zf.setpassword(password)
                
                # Extract only .env file (wallet files no longer needed)
                for member in zf.namelist():
                    if os.path.basename(member) == '.env':
                        zf.extract(member, self.temp_dir)
                        break

            # Load .env from extracted zip
            env_file = os.path.join(self.temp_dir, '.env')
            if os.path.exists(env_file):
                load_dotenv(env_file)
                print(f"[SecretsManager] Environment variables loaded from zip.")
            else:
                print(f"[SecretsManager] Warning: .env not found in Setup Pack.")

            return self

        except Exception as e:
            # Cleanup immediately on failure
            self._cleanup()
            print(f"[SecretsManager] Failed to unlock secrets: {e}")
            raise

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._cleanup()

    def _cleanup(self):
        """Remove temporary files."""
        # Wipe temp dir
        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
                print("[SecretsManager] Secure session closed. Temporary files wiped.")
            except Exception as e:
                print(f"[SecretsManager] Warning: Could not fully wipe temp dir: {e}")
        
        self.temp_dir = None

"""
Authentication Module for InstaCRM Desktop Agent.
Handles Google OAuth 2.0 Flow and Token Management.
"""

import os
import json
import pickle
import base64
import threading
import webbrowser
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import sys

# Define scopes required
SCOPES = [
    'openid',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile'
]

# Paths
if getattr(sys, 'frozen', False):
    PROJECT_ROOT = os.path.dirname(sys.executable)
else:
    PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

CREDENTIALS_PATH = os.path.join(PROJECT_ROOT, 'assets', 'client_secret.json')
TOKEN_PATH = os.path.join(PROJECT_ROOT, 'token.pickle')
SECURE_TOKEN_PATH = os.path.join(PROJECT_ROOT, 'token.enc')

def _get_encryption_key():
    """
    Generate a machine-specific encryption key for token storage.
    Uses a combination of machine-specific data and a salt.
    """
    # Use machine-specific identifier (hostname + username)
    import platform
    import getpass
    machine_id = f"{platform.node()}-{getpass.getuser()}".encode()
    
    # Salt stored locally (not secret, just prevents rainbow tables)
    salt = b'IOL_TOKEN_SALT_v1'
    
    # Derive key using PBKDF2HMAC
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(machine_id))
    return key

class AuthManager:
    def __init__(self):
        self.creds = None
        self.user_info = None
        self._encryption_key = _get_encryption_key()
        self._fernet = Fernet(self._encryption_key)

    def _migrate_from_pickle(self):
        """Migrate from old pickle format to new encrypted format."""
        if os.path.exists(TOKEN_PATH) and not os.path.exists(SECURE_TOKEN_PATH):
            try:
                with open(TOKEN_PATH, 'rb') as token:
                    creds = pickle.load(token)
                    # Convert to new format
                    self.creds = creds
                    self.save_token()
                    print("[Auth] Migrated token from pickle to encrypted format.")
                    # Keep old file as backup for now
                    os.rename(TOKEN_PATH, TOKEN_PATH + '.backup')
                    return True
            except Exception as e:
                print(f"[Auth] Failed to migrate token: {e}")
                return False
        return False

    def load_token(self):
        """Load existing token if valid. Supports migration from pickle format."""
        # Try to migrate from old format first
        if os.path.exists(TOKEN_PATH):
            self._migrate_from_pickle()
        
        # Load from encrypted format
        if os.path.exists(SECURE_TOKEN_PATH):
            try:
                with open(SECURE_TOKEN_PATH, 'rb') as token_file:
                    encrypted_data = token_file.read()
                    decrypted_data = self._fernet.decrypt(encrypted_data)
                    token_dict = json.loads(decrypted_data.decode('utf-8'))
                    
                    # Reconstruct credentials object
                    self.creds = Credentials(
                        token=token_dict.get('token'),
                        refresh_token=token_dict.get('refresh_token'),
                        token_uri=token_dict.get('token_uri'),
                        client_id=token_dict.get('client_id'),
                        client_secret=token_dict.get('client_secret'),
                        scopes=token_dict.get('scopes')
                    )
            except Exception as e:
                print(f"[Auth] Token load failed: {e}")
                self.creds = None
        
        if self.creds and self.creds.expired and self.creds.refresh_token:
            try:
                self.creds.refresh(Request())
                self.save_token()
            except Exception as e:
                print(f"[Auth] Token refresh failed: {e}")
                self.creds = None

    def save_token(self):
        """Save credentials to disk in encrypted format."""
        if not self.creds:
            return
        
        try:
            # Convert credentials to dictionary
            token_dict = {
                'token': self.creds.token,
                'refresh_token': self.creds.refresh_token,
                'token_uri': self.creds.token_uri,
                'client_id': self.creds.client_id,
                'client_secret': self.creds.client_secret,
                'scopes': self.creds.scopes,
                'expiry': self.creds.expiry.isoformat() if self.creds.expiry else None
            }
            
            # Encrypt and save
            json_data = json.dumps(token_dict).encode('utf-8')
            encrypted_data = self._fernet.encrypt(json_data)
            
            with open(SECURE_TOKEN_PATH, 'wb') as token_file:
                token_file.write(encrypted_data)
                
        except Exception as e:
            print(f"[Auth] Token save failed: {e}")
            raise

    def logout(self):
        """Sign out by deleting the local token file."""
        try:
            if os.path.exists(SECURE_TOKEN_PATH):
                os.remove(SECURE_TOKEN_PATH)
            self.creds = None
            self.user_info = None
            return True
        except Exception as e:
            print(f"[Auth] Logout failed: {e}")
            return False

    def login(self):
        """
        Initiates the Google OAuth 2.0 flow.
        Returns: (user_info_dict, error_message)
        """
        # Try to load from .env if file is missing
        client_config = None
        
        if not os.path.exists(CREDENTIALS_PATH):
            # Check for env vars
            from dotenv import load_dotenv
            load_dotenv()
            cid = os.getenv('GOOGLE_CLIENT_ID')
            csecret = os.getenv('GOOGLE_CLIENT_SECRET')
            
            if cid and csecret:
                client_config = {
                    "installed": {
                        "client_id": cid,
                        "project_id": "instacrm-desktop", # Placeholder
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                        "client_secret": csecret,
                        "redirect_uris": ["http://localhost"]
                    }
                }
            else:
                return None, f"Missing 'client_secret.json' in assets/ AND missing GOOGLE_CLIENT_ID/SECRET in .env."

        try:
            # 2. Run Flow
            if client_config:
                flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
            else:
                flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
                
            self.creds = flow.run_local_server(port=0, open_browser=True)
            
            # 3. Save Token
            self.save_token()
            
            # 4. Fetch Profile
            return self.fetch_user_info(), None

        except Exception as e:
            return None, str(e)

    def fetch_user_info(self):
        """Fetches email and name using the current credentials."""
        if not self.creds or not self.creds.valid:
            return None

        from googleapiclient.discovery import build
        service = build('oauth2', 'v2', credentials=self.creds)
        self.user_info = service.userinfo().get().execute()
        return self.user_info

    def logout(self):
        """Clear local session."""
        if os.path.exists(SECURE_TOKEN_PATH):
            os.remove(SECURE_TOKEN_PATH)
        # Also remove old pickle file if it exists
        if os.path.exists(TOKEN_PATH):
            os.remove(TOKEN_PATH)
        self.creds = None
        self.user_info = None
        return True

    def get_authenticated_user(self):
        """
        Checks if a user is already logged in and token is valid.
        Returns user_info or None.
        """
        self.load_token()
        if self.creds and self.creds.valid:
            try:
                return self.fetch_user_info()
            except Exception as e:
                print(f"[Auth] Failed to fetch user info: {e}")
                return None
        return None

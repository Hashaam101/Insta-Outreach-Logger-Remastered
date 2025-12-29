"""
Authentication Module for InstaCRM Desktop Agent.
Handles Google OAuth 2.0 Flow and Token Management.
"""

import os
import json
import pickle
import threading
import webbrowser
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
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

class AuthManager:
    def __init__(self):
        self.creds = None
        self.user_info = None

    def load_token(self):
        """Load existing token if valid."""
        if os.path.exists(TOKEN_PATH):
            with open(TOKEN_PATH, 'rb') as token:
                self.creds = pickle.load(token)
        
        if self.creds and self.creds.expired and self.creds.refresh_token:
            try:
                self.creds.refresh(Request())
                self.save_token()
            except Exception as e:
                print(f"[Auth] Token refresh failed: {e}")
                self.creds = None

    def save_token(self):
        """Save credentials to disk."""
        with open(TOKEN_PATH, 'wb') as token:
            pickle.dump(self.creds, token)

    def login(self):
        """
        Initiates the Google OAuth 2.0 flow.
        Returns: (user_info_dict, error_message)
        """
        # 1. Check for client_secret.json
        if not os.path.exists(CREDENTIALS_PATH):
            return None, f"Missing 'client_secret.json' in {os.path.join(PROJECT_ROOT, 'assets')}. Please download it from Google Cloud Console."

        try:
            # 2. Run Flow
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
        if os.path.exists(TOKEN_PATH):
            os.remove(TOKEN_PATH)
        self.creds = None
        self.user_info = None

    def get_authenticated_user(self):
        """
        Checks if a user is already logged in and token is valid.
        Returns user_info or None.
        """
        self.load_token()
        if self.creds and self.creds.valid:
            try:
                return self.fetch_user_info()
            except:
                return None
        return None

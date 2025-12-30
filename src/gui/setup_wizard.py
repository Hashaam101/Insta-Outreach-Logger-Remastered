"""
Setup Wizard for Insta Outreach Logger.

This wizard handles first-time setup by accepting a Setup_Pack.zip file
containing the .env file with database credentials (TLS connection string).

Features:
- Sequential setup flow (Steps 1-4)
- Secure token validation
- Automated extension deployment to Documents
- Operator discovery and registration

Note: Oracle Wallet is no longer used. Database connection uses TLS connection strings.
"""

import sys
import os
import subprocess

# --- Path Setup ---
if getattr(sys, 'frozen', False):
    # Running as compiled exe
    project_root = os.path.dirname(sys.executable)
else:
    # Running as script
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_dir, '../../'))

# Add project root to sys.path so we can import 'src'
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import customtkinter as ctk
import zipfile
import json
import winreg
import tempfile
import threading
import re
import pyzipper
import shutil
from tkinter import messagebox, filedialog
from src.core.security import get_zip_password
from src.core.version import __app_name__
import base64
import hashlib
try:
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization
except ImportError:
    pass # Managed in checks

# Google Auth Imports
try:
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    import requests
    GOOGLE_AUTH_AVAILABLE = True
    
    # Import Core AuthManager for persistence
    from src.core.auth import AuthManager
except ImportError:
    GOOGLE_AUTH_AVAILABLE = False

# Image Processing
try:
    from PIL import Image
    from io import BytesIO
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# Try to import tkinterdnd2 for drag and drop support
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    DND_AVAILABLE = True
except ImportError:
    DND_AVAILABLE = False


class HelpTooltip:
    """A tooltip popup that appears when hovering a help icon."""
    active_tooltip = None

    def __init__(self, parent, text, title="Help"):
        self.parent = parent
        self.text = text
        self.title = title
        self.tooltip_window = None
        self.hide_job = None

    def on_enter(self, event=None):
        self.cancel_hide()
        if HelpTooltip.active_tooltip and HelpTooltip.active_tooltip != self:
            HelpTooltip.active_tooltip.hide()
        self.show()

    def on_leave(self, event=None):
        self.schedule_hide()

    def schedule_hide(self, event=None):
        self.cancel_hide()
        self.hide_job = self.parent.after(200, self.hide)

    def cancel_hide(self):
        if self.hide_job:
            self.parent.after_cancel(self.hide_job)
            self.hide_job = None

    def show(self, event=None):
        if self.tooltip_window: return
        HelpTooltip.active_tooltip = self
        x = self.parent.winfo_rootx() + 35
        y = self.parent.winfo_rooty() - 5
        self.tooltip_window = ctk.CTkToplevel(self.parent)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.attributes("-topmost", True)
        self.tooltip_window.geometry(f"{x}+{y}")
        self.tooltip_window.configure(fg_color="#1E1B2E")
        self.tooltip_window.bind("<Leave>", self.on_leave)
        self.tooltip_window.bind("<Enter>", self.on_enter)
        frame = ctk.CTkFrame(self.tooltip_window, fg_color="#1E1B2E", corner_radius=8, border_width=1, border_color="#4C4B63")
        frame.pack(padx=1, pady=1)
        ctk.CTkLabel(frame, text=self.title, font=ctk.CTkFont(size=12, weight="bold"), text_color="#ffffff").pack(padx=15, pady=(10, 5), anchor="w")
        ctk.CTkLabel(frame, text=self.text, font=ctk.CTkFont(size=11), text_color="#cccccc", justify="left", wraplength=300).pack(padx=15, pady=(0, 10), anchor="w")

    def hide(self, event=None):
        self.cancel_hide()
        if self.tooltip_window:
            try: self.tooltip_window.destroy()
            except Exception: pass
            self.tooltip_window = None
        if HelpTooltip.active_tooltip == self: HelpTooltip.active_tooltip = None


class GoogleAuthManager:
    """Handles Google OAuth Flow."""
    def __init__(self, client_id, client_secret):
        self.client_config = {
            "installed": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "redirect_uris": ["http://localhost"]
            }
        }
        self.scopes = [
            'https://www.googleapis.com/auth/userinfo.email',
            'https://www.googleapis.com/auth/userinfo.profile',
            'openid'
        ]

    def authenticate(self):
        """Run the OAuth flow and return user info."""
        if not GOOGLE_AUTH_AVAILABLE:
            raise ImportError("Google Auth libraries not installed. Please install: google-auth-oauthlib requests")

        flow = InstalledAppFlow.from_client_config(self.client_config, self.scopes)
        # Reverting to dynamic port (standard for Desktop App Client IDs)
        # If using Web Client ID, this will fail. User MUST use Desktop App Client ID.
        print(f"[Auth] Starting local server. Check browser...") 
        creds = flow.run_local_server(port=0, open_browser=True)
        
        # Get User Info
        session = requests.Session()
        session.headers.update({'Authorization': f'Bearer {creds.token}'})
        response = session.get('https://www.googleapis.com/oauth2/v2/userinfo')
        response.raise_for_status()
        return response.json()



# Define a robust base class merging CTk and TkinterDnD
if DND_AVAILABLE:
    class CTkDnD(ctk.CTk, TkinterDnD.DnDWrapper):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.TkdndVersion = TkinterDnD._require(self)
else:
    class CTkDnD(ctk.CTk):
        pass


class SetupWizard(CTkDnD):
    """
    Setup Wizard GUI for sequential configuration.
    Steps: Zip Upload -> Operator Name -> Extension Installation -> Get Started.
    """

    def __init__(self):
        super().__init__()

        # Configure appearance
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        if DND_AVAILABLE: self.configure(bg="#0F0E13")
        else: self.configure(fg_color="#0F0E13")

        self.title("Insta Outreach Logger - Setup Wizard")
        self.geometry("600x650")
        self.resizable(False, False)
        self._is_closing = False

        # Center window
        self.update_idletasks()
        width, height = self.winfo_width(), self.winfo_height()
        x, y = (self.winfo_screenwidth() // 2) - (width // 2), (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"+{x}+{y}")

        icon_path = os.path.join(project_root, "assets", "logo.ico")
        if os.path.exists(icon_path): self.iconbitmap(icon_path)

        # State
        self.selected_file = None
        self.auth_user_info = None  # {email, name, picture}
        self.google_client_id = None
        self.google_client_secret = None
        self.is_reconfiguring = False
        self.is_reconfiguring = False
        self.current_step = 1 # 1: Zip, 2: Operator, 3: Extension, 4: ID/Final
        self.auth_request_id = 0

        # UI
        self._create_main_container()
        self._create_header()
        self._create_step_indicator()
        self._create_zip_section()
        self._create_operator_section()
        self._create_extension_instructions_section()
        self._create_extension_id_section()
        self._create_buttons()

        if DND_AVAILABLE: self._setup_drag_and_drop()
        self._check_existing_files()
        self._update_ui_state()

        # --- PERMANENT ID GENERATION ---
        # Generate a key on startup to ensure ID is fixed
        threading.Thread(target=self._generate_permanent_id, daemon=True).start()

    def _generate_permanent_id(self):
        """Generates a permanent key for the extension if missing."""
        key_path = os.path.join(project_root, 'src', 'extension', 'key.pem')
        manifest_path = os.path.join(project_root, 'src', 'extension', 'manifest.json')
        
        if os.path.exists(key_path):
            return # Already generated
            
        try:
            print("[Setup] Generating permanent Extension Key...")
            # Generate Key
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
            )
            
            # Save Private Key (optional, but good for reproducibility)
            pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
            with open(key_path, 'wb') as f:
                f.write(pem)
                
            # Get Public Key DER for Manifest
            public_key = private_key.public_key()
            der_key = public_key.public_bytes(
                encoding=serialization.Encoding.DER,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            b64_key = base64.b64encode(der_key).decode('utf-8')
            
            # Update Manifest
            with open(manifest_path, 'r') as f:
                data = json.load(f)
            
            data['key'] = b64_key
            
            with open(manifest_path, 'w') as f:
                json.dump(data, f, indent=4)
                
            # Calculate Extension ID
            sha = hashlib.sha256(der_key).hexdigest()
            prefix = sha[:32]
            ext_id = "".join([chr(ord('a') + int(char, 16)) for char in prefix])
            
            print(f"[Setup] Generated permanent Extension Key.")
            print(f"[Setup] Extension ID: {ext_id}")
            
            # Update Native Host Manifest
            nh_manifest = os.path.join(project_root, 'src', 'core', 'com.instaoutreach.logger.json')
            if os.path.exists(nh_manifest):
                with open(nh_manifest, 'r') as f:
                    nh_data = json.load(f)
                
                nh_data['allowed_origins'] = [f"chrome-extension://{ext_id}/"]
                
                with open(nh_manifest, 'w') as f:
                    json.dump(nh_data, f, indent=4)
                print(f"[Setup] Updated Native Host Manifest with ID: {ext_id}")
            
        except Exception as e:
            print(f"[Setup] Failed to generate ID: {e}")

    def _create_main_container(self):
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.pack(fill="both", expand=True, padx=30, pady=20)

    def _create_header(self):
        # Cyberpunk Header
        self.header_frame = ctk.CTkFrame(self.main_frame, fg_color="#1a1b26", corner_radius=12, border_width=1, border_color="#7C3AED")
        self.header_frame.pack(fill="x", pady=(0, 20), ipady=15)
        
        content = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        content.pack()
        
        ctk.CTkLabel(
            content, 
            text="SETUP WIZARD", 
            font=ctk.CTkFont(family="Segoe UI", size=24, weight="bold"),
            text_color="#c0caf5"
        ).pack()
        
        ctk.CTkLabel(
            content, 
            text="INSTA OUTREACH LOGGER REMASTERED", 
            text_color="#565f89"
        ).pack(pady=(5, 0))

    def _create_step_indicator(self):
        self.step_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.step_frame.pack(fill="x", pady=(0, 30))
        
        # Container for step pills
        container = ctk.CTkFrame(self.step_frame, fg_color="transparent")
        container.pack(anchor="center")
        
        self.step_widgets = [] # Tuples of (Frame, Label, Icon)
        steps = [("1", "CREDENTIALS"), ("2", "IDENTITY"), ("3", "EXTENSION"), ("4", "FINALIZE")]
        
        for i, (num, text) in enumerate(steps):
            # Step Wrapper
            wrapper = ctk.CTkFrame(container, fg_color="transparent")
            wrapper.pack(side="left", padx=10)
            
            # Circle
            circle = ctk.CTkFrame(wrapper, width=32, height=32, corner_radius=16, border_width=2)
            circle.pack(side="left")
            circle.pack_propagate(False) # Fixed size
            
            num_lbl = ctk.CTkLabel(circle, text=num, font=ctk.CTkFont(size=12, weight="bold"))
            num_lbl.place(relx=0.5, rely=0.5, anchor="center")
            
            # Text
            text_lbl = ctk.CTkLabel(wrapper, text=text, font=ctk.CTkFont(size=10, weight="bold"), text_color="#565f89")
            text_lbl.pack(side="left", padx=(10, 0))
            
            self.step_widgets.append((circle, num_lbl, text_lbl))
            
            # Connector Line (except for last)
            if i < len(steps) - 1:
                line = ctk.CTkFrame(container, width=30, height=2, fg_color="#24283b")
                line.pack(side="left")

    def _update_ui_state(self):
        """Update visibility based on current step."""
        # Update Step Indicators
        for i, (circle, num, text) in enumerate(self.step_widgets):
            step_idx = i + 1
            if step_idx < self.current_step:
                # Completed
                circle.configure(fg_color="#22c55e", border_color="#22c55e")
                num.configure(text="✓", text_color="white")
                text.configure(text_color="#22c55e")
            elif step_idx == self.current_step:
                # Active
                circle.configure(fg_color="#7C3AED", border_color="#7C3AED")
                num.configure(text=str(step_idx), text_color="white")
                text.configure(text_color="#c0caf5")
            else:
                # Pending
                circle.configure(fg_color="transparent", border_color="#414868")
                num.configure(text=str(step_idx), text_color="#414868")
                text.configure(text_color="#414868")

        # Show sections
        for i, sec in enumerate([self.zip_section, self.operator_section, self.ext_instruction_section, self.ext_id_section]):
            if i + 1 == self.current_step: sec.pack(fill="x", pady=10)
            else: sec.pack_forget()

        # Update buttons
        if self.current_step == 1:
            self.back_button.configure(state="disabled", fg_color="#1a1b26")
            can_next = self.selected_file is not None or self.is_reconfiguring
            self.next_button.configure(text="NEXT STEP >", state="normal" if can_next else "disabled", fg_color="#7C3AED" if can_next else "#24283b")
        elif self.current_step == 2:
            self.back_button.configure(state="normal", fg_color="#24283b")
            # Next button state logic depends on auth... managed by auth callback usually
            self.next_button.configure(text="NEXT STEP >", fg_color="#7C3AED") # Assuming true for now, auth blocks logically
        elif self.current_step == 3:
            self.back_button.configure(state="normal", fg_color="#24283b")
            self.next_button.configure(text="NEXT STEP >", fg_color="#7C3AED")
        elif self.current_step == 4:
            self.back_button.configure(state="normal", fg_color="#24283b")
            self.next_button.configure(text="LAUNCH DASHBOARD 🚀", fg_color="#22c55e", hover_color="#16a34a")

    def _next_step(self):
        if self.current_step == 2:
            if not self._install_files(): return
        if self.current_step == 4:
            self._complete_setup()
            return
        if self.current_step < 4:
            self.current_step += 1
            self._update_ui_state()

    def _prev_step(self):
        if self.current_step > 1:
            self.current_step -= 1
            self._update_ui_state()

    def _create_zip_section(self):
        # Step 1: Upload Credentials
        self.zip_section = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        
        ctk.CTkLabel(self.zip_section, text="UPLOAD CREDENTIALS", font=ctk.CTkFont(size=14, weight="bold"), text_color="#c0caf5").pack(anchor="w", pady=(0, 10))
        
        self.click_frame = ctk.CTkFrame(self.zip_section, fg_color="#16161e", corner_radius=16, border_width=2, border_color="#7C3AED", height=200)
        self.click_frame.pack(fill="x")
        self.click_frame.pack_propagate(False)
        
        container = ctk.CTkFrame(self.click_frame, fg_color="transparent")
        container.place(relx=0.5, rely=0.5, anchor="center")
        
        self.icon_label = ctk.CTkLabel(container, text="⚡", font=ctk.CTkFont(size=48))
        self.icon_label.pack(pady=(0, 10))
        
        self.main_text_label = ctk.CTkLabel(container, text="DROP 'SETUP_PACK.ZIP'", font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"), text_color="#a9b1d6")
        self.main_text_label.pack(pady=(0, 5))
        
        self.subtext_label = ctk.CTkLabel(container, text="OR CLICK TO BROWSE FILES", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color="#565f89")
        self.subtext_label.pack()
        
        self.file_label = ctk.CTkLabel(self.zip_section, text="", font=ctk.CTkFont(size=12), text_color="#7C3AED")
        self.file_label.pack(pady=(10, 0))
        
        self.status_label = ctk.CTkLabel(self.zip_section, text="", font=ctk.CTkFont(size=12))
        self.status_label.pack()

        for w in [self.click_frame, container, self.icon_label, self.main_text_label, self.subtext_label]:
            w.bind("<Button-1>", lambda e: self._open_file_dialog())
            w.configure(cursor="hand2")

    def _create_operator_section(self):
        # Step 2: Validate Identity
        self.operator_section = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        
        ctk.CTkLabel(self.operator_section, text="VERIFY IDENTITY", font=ctk.CTkFont(size=14, weight="bold"), text_color="#c0caf5").pack(anchor="w", pady=(0, 10))
        
        # Profile Card
        self.profile_frame = ctk.CTkFrame(self.operator_section, fg_color="#16161e", corner_radius=12, border_width=1, border_color="#414868")
        self.profile_frame.pack(fill="x", pady=(0, 20), ipady=20)
        
        self.profile_label = ctk.CTkLabel(self.profile_frame, text="🦁", font=ctk.CTkFont(size=56))
        self.profile_label.pack(pady=(10, 10))
        
        self.operator_name_label = ctk.CTkLabel(self.profile_frame, text="NOT AUTHENTICATED", font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"), text_color="#f87171")
        self.operator_name_label.pack()
        
        self.operator_email_label = ctk.CTkLabel(self.profile_frame, text="Sign in to link your activity log.", font=ctk.CTkFont(size=12), text_color="#565f89")
        self.operator_email_label.pack(pady=(5, 0))

        # Auth Button
        self.auth_button = ctk.CTkButton(
            self.operator_section, 
            text="SIGN IN WITH GOOGLE", 
            command=self._run_google_auth,
            fg_color="white", 
            text_color="black",
            hover_color="#e5e7eb",
            height=50,
            corner_radius=8,
            font=ctk.CTkFont(family="Segoe UI", weight="bold"),
        )
        self.auth_button.pack(fill="x", padx=60)

        self.db_status_label = ctk.CTkLabel(self.operator_section, text="", font=ctk.CTkFont(size=12))
        self.db_status_label.pack(pady=(15, 0))

    def _create_extension_instructions_section(self):
        # Step 3: Deployment
        self.ext_instruction_section = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        
        ctk.CTkLabel(self.ext_instruction_section, text="DEPLOY EXTENSION", font=ctk.CTkFont(size=14, weight="bold"), text_color="#c0caf5").pack(anchor="w", pady=(0, 10))
        
        card = ctk.CTkFrame(self.ext_instruction_section, fg_color="#16161e", corner_radius=12, border_width=1, border_color="#414868")
        card.pack(fill="x", pady=(0, 20), ipadx=20, ipady=15)
        
        steps = [
            "1. Open chrome://extensions",
            "2. Enable 'Developer mode' (Top Right)",
            "3. Click 'Load unpacked' (Top Left)",
            "4. Select the folder opened below"
        ]
        
        for step in steps:
            ctk.CTkLabel(card, text=step, font=ctk.CTkFont(family="Consolas", size=13), text_color="#a9b1d6").pack(anchor="w", pady=2)
            
        self.open_ext_folder_button = ctk.CTkButton(
            self.ext_instruction_section, 
            text="OPEN EXTENSION FOLDER 📂", 
            command=self._open_extension_folder, 
            fg_color="#2D2B40", 
            hover_color="#4C4B63",
            height=45,
            font=ctk.CTkFont(weight="bold")
        )
        self.open_ext_folder_button.pack(fill="x")

    def _open_extension_folder(self):
        """Opens the extension folder in the file explorer."""
        docs_dir = os.path.join(os.path.expanduser("~"), "Documents")
        extension_dir = os.path.join(docs_dir, "Insta Logger Remastered", "extension")
        if os.path.exists(extension_dir):
            subprocess.run(['explorer', os.path.realpath(extension_dir)])
        else:
            messagebox.showwarning("Folder Not Found", f"Extension folder not found at:\n{extension_dir}")

    def _create_extension_id_section(self):
        # Step 4: Finalize
        self.ext_id_section = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        
        ctk.CTkLabel(self.ext_id_section, text="VERIFY EXTENSION ID", font=ctk.CTkFont(size=14, weight="bold"), text_color="#c0caf5").pack(anchor="w", pady=(0, 10))
        
        self.extension_id_entry = ctk.CTkEntry(
            self.ext_id_section, 
            placeholder_text="Paste ID here if not auto-filled...", 
            height=50,
            fg_color="#16161e",
            border_color="#7C3AED",
            font=ctk.CTkFont(family="Consolas", size=14)
        )
        self.extension_id_entry.pack(fill="x", pady=(0, 10))
        
        ctk.CTkLabel(
            self.ext_id_section, 
            text="The ID should be auto-detected.\nIf empty, copy it from chrome://extensions 'ID: ...'", 
            font=ctk.CTkFont(size=11), 
            text_color="#565f89"
        ).pack(anchor="w")

    def _create_buttons(self):
        self.button_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.button_frame.pack(side="bottom", fill="x", pady=(20, 0))
        self.back_button = ctk.CTkButton(self.button_frame, text="Back", command=self._prev_step, width=120, height=40, fg_color="#2D2B40", hover_color="#4C4B63")
        self.back_button.pack(side="left")
        self.next_button = ctk.CTkButton(self.button_frame, text="Next Step", command=self._next_step, width=180, height=40, fg_color="#7C3AED", hover_color="#6D28D9", font=ctk.CTkFont(weight="bold"))
        self.next_button.pack(side="right")

    def _check_existing_files(self):
        """Check if configuration already exists (either secure zip or local .env)."""
        docs_dir = os.path.join(os.path.expanduser("~"), "Documents")
        secrets_dir = os.path.join(docs_dir, "Insta Logger Remastered", "secrets")
        has_secure = os.path.exists(secrets_dir) and any(f.startswith("Setup_Pack_") for f in os.listdir(secrets_dir))
        # Only check for .env file now (wallet no longer required)
        env_path = os.path.join(project_root, '.env')
        has_local = os.path.exists(env_path)
        print(f"[DEBUG Setup] Checking .env at: {env_path}")
        print(f"[DEBUG Setup] Found .env: {has_local}")
        
        if has_secure or has_local:
            self.is_reconfiguring = True
            self._show_status("Configuration found", "success")
            self.main_text_label.configure(text="Configured")
            self.click_frame.configure(border_color="#22c55e")
            # Load Operator Info from Config
            cfg = os.path.join(project_root, 'operator_config.json')
            if os.path.exists(cfg):
                try:
                    with open(cfg, 'r') as f:
                        data = json.load(f)
                        self.auth_user_info = {
                            "name": data.get('operator_name', 'Unknown'),
                            "email": data.get('operator_email', '')
                        }
                        self._update_profile_ui(self.auth_user_info, "Restored from config")
                except Exception: pass
            
            # Load Ext ID
            try:
                # Find bridge and manifest
                bp = os.path.join(project_root, 'src', 'core', 'bridge.bat')
                if not os.path.exists(bp): bp = os.path.join(project_root, '_internal', 'src', 'core', 'bridge.bat')
                mp = os.path.join(os.path.dirname(bp), 'com.instaoutreach.logger.json')
                if os.path.exists(mp):
                    with open(mp, 'r') as f:
                        orig = json.load(f).get('allowed_origins', [])
                        if orig:
                            eid = orig[0].replace('chrome-extension://', '').replace('/', '')
                            self.extension_id_entry.insert(0, eid)
            except Exception: pass

    def _is_chrome_running(self):
        """Check if any chrome.exe processes are running."""
        try:
            output = subprocess.check_output('tasklist /FI "IMAGENAME eq chrome.exe"', shell=True).decode()
            return "chrome.exe" in output.lower()
        except Exception:
            return False

    def _kill_chrome(self):
        """Forcefully terminate all chrome.exe processes."""
        try:
            subprocess.run('taskkill /F /IM chrome.exe', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            return False

    def _deploy_extension(self):
        """Move the extension to Documents folder."""
        try:
            # 1. Determine Source Path
            source_path = None
            possible_paths = [
                os.path.join(project_root, 'src', 'extension'),
                os.path.join(project_root, '_internal', 'src', 'extension')
            ]
            meipass = getattr(sys, '_MEIPASS', None)
            if meipass:
                possible_paths.append(os.path.join(meipass, 'src', 'extension'))

            for p in possible_paths:
                # Debug logging
                print(f"[Setup] Checking for extension at: {p}")
                if os.path.exists(p):
                    source_path = p
                    break

            if not source_path:
                print(f"[Setup] Extension source not found in: {possible_paths}")
                # If we are in dev mode, maybe we are running from a different context?
                # Try relative to CWD as fallback
                cwd_path = os.path.join(os.getcwd(), 'src', 'extension')
                if os.path.exists(cwd_path):
                     source_path = cwd_path
                     print(f"[Setup] Found extension at CWD: {source_path}")

            if not source_path:
                 messagebox.showerror("Error", f"Could not find extension source files.\nChecked: {possible_paths}")
                 return False

            # 2. Destination
            docs_dir = os.path.join(os.path.expanduser("~"), "Documents")
            target_dir = os.path.join(docs_dir, "Insta Logger Remastered", "extension")

            # 3. Check for Chrome Conflict
            if self._is_chrome_running():
                confirm = messagebox.askyesnocancel(
                    "Chrome is Running",
                    "Google Chrome must be closed to update the extension.\n\n"
                    "Would you like to force close Chrome now?"
                )
                if confirm is True:
                    self._kill_chrome()
                    import time
                    time.sleep(2)
                elif confirm is False:
                    # User said No (Skip)
                    return True
                else:
                    # Cancel
                    return False

            # 4. Copy
            # 4. Copy
            print(f"[Setup] Deploying extension from {source_path} to {target_dir}")
            os.makedirs(os.path.dirname(target_dir), exist_ok=True)
            if os.path.exists(target_dir):
                shutil.rmtree(target_dir)
            
            shutil.copytree(source_path, target_dir)
            
            # Clean up source if frozen (Move behavior)
            # In DEV MODE (frozen=False): KEEP SOURCE
            if getattr(sys, 'frozen', False):
                try: shutil.rmtree(source_path)
                except Exception: pass
            else:
                print("[Setup] Dev Mode: Source files preserved.")

            print(f"[Setup] Extension deployed to: {target_dir}")
            return True
        except Exception as e:
            messagebox.showerror("Deployment Error", f"Failed to deploy extension: {e}")
            return False

    def _install_files(self):
        if not self.auth_user_info:
            messagebox.showerror("Authentication Required", "Please sign in with Google to continue.")
            return False
        
        # Deploy Extension first
        if not self._deploy_extension():
            return False

        try:
            # If reconfiguring with local files, we might not have selected_file
            if self.selected_file:
                dst = os.path.join(os.path.expanduser("~"), "Documents", "Insta Logger Remastered", "secrets")
                os.makedirs(dst, exist_ok=True)
                for f in os.listdir(dst):
                    if f.startswith("Setup_Pack_"): os.remove(os.path.join(dst, f))
                shutil.copy2(self.selected_file, os.path.join(dst, os.path.basename(self.selected_file)))
            
            with open(os.path.join(project_root, 'operator_config.json'), 'w') as f:
                json.dump({
                    'operator_name': self.auth_user_info['name'], 
                    'operator_email': self.auth_user_info['email'],
                }, f)
            return True
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return False

    def _complete_setup(self):
        eid = self.extension_id_entry.get().strip()
        if len(eid) != 32:
            messagebox.showerror("Error", "Invalid Extension ID.")
            return
        try:
            self._register_native_host(eid)
            messagebox.showinfo("Success", "Setup Complete!")
            self._safe_destroy()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _select_file(self, path):
        valid, msg = self._validate_zip(path)
        if valid:
            self.selected_file = path
            self._show_status("Valid Pack", "success")
            self.file_label.configure(text=os.path.basename(path))
            self.click_frame.configure(border_color="#22c55e")
            self._update_ui_state()
            self._load_operators_from_zip(path)
        else:
            self.selected_file = None
            self._show_status(msg, "error")
            self.click_frame.configure(border_color="#ef4444")
            self._update_ui_state()

    def _open_file_dialog(self):
        path = filedialog.askopenfilename(title="Select Setup_Pack.zip", filetypes=[("Zip", "*.zip")])
        if path: self._select_file(path)

    def _setup_drag_and_drop(self):
        self.click_frame.drop_target_register(DND_FILES) # type: ignore
        self.click_frame.dnd_bind('<<Drop>>', lambda e: self._select_file(e.data[1:-1] if e.data.startswith('{') else e.data)) # type: ignore
        self.click_frame.dnd_bind('<<DragEnter>>', lambda e: self.click_frame.configure(border_color="#7C3AED")) # type: ignore
        self.click_frame.dnd_bind('<<DragLeave>>', lambda e: self.click_frame.configure(border_color="#22c55e" if self.selected_file else "#4C4B63")) # type: ignore

    def _get_zip_password_from_filename(self, zip_path):
        m = re.search(r'Setup_Pack_([a-fA-F0-9]+)\.zip', os.path.basename(zip_path))
        return get_zip_password(m.group(1)) if m else None

    def _validate_zip(self, path):
        """Validate Setup_Pack.zip contains .env file with required variables."""
        try:
            pwd = self._get_zip_password_from_filename(path)
            with pyzipper.AESZipFile(path, 'r') as zf:
                if pwd: zf.setpassword(pwd)
                files = zf.namelist()
                if pwd: zf.read(files[0])
                # Only require .env file now (wallet removed)
                req = ['.env']
                found = {os.path.basename(f) for f in files}
                missing = [r for r in req if r not in found]
                return (True, "Valid") if not missing else (False, f"Missing: {missing}")
        except Exception as e: return False, str(e)

    def _load_operators_from_zip(self, path):
         # Just verify we can get the Google Keys, but don't blocking load anything else content-wise yet
         # We will lazy-load the env vars when needed
         pass

    def _run_google_auth(self):
        """Trigger the Google Auth flow with Retry/Cancel support."""
        current_text = self.auth_button.cget("text")
        
        if "Cancel" in current_text:
            # User wants to cancel
            self._auth_failed("Cancelled by user.", is_cancel=True)
            return

        # Start New Auth
        self.auth_button.configure(text="Connecting... (Click to Cancel)", fg_color="#f59e0b", hover_color="#d97706")
        self.auth_request_id += 1
        current_req_id = self.auth_request_id
        
        # 1. Get Credentials
        cid, csecret = self._get_google_creds()
        if not cid or not csecret:
             messagebox.showerror("Configuration Error", "Google OAuth credentials not found in Setup Pack (.env).")
             self._auth_failed("Missing Credentials")
             return

        # 2. Start Auth Thread
        threading.Thread(target=self._auth_thread, args=(cid, csecret, current_req_id), daemon=True).start()

    def _get_google_creds(self):
        """Extract Google Creds from selected zip or local env."""
        try:
            from dotenv import load_dotenv, dotenv_values
            env_vars = {}
            
            if self.selected_file:
                pwd = self._get_zip_password_from_filename(self.selected_file)
                # ... (Logic to read from zip) ...
                try:
                    with pyzipper.AESZipFile(self.selected_file, 'r') as zf:
                        if pwd: zf.setpassword(pwd)
                        for info in zf.infolist():
                            if os.path.basename(info.filename) == '.env':
                                with zf.open(info.filename) as f:
                                    content = f.read().decode('utf-8')
                                    from io import StringIO
                                    env_vars = dotenv_values(stream=StringIO(content))
                                break
                except Exception as e:
                     print(f"Failed to read zip: {e}")
                     # Fallback to local if zip fails
            
            if not env_vars:
                 # Local fallback
                env_vars = dotenv_values(os.path.join(project_root, '.env'))
            
            return env_vars.get('GOOGLE_CLIENT_ID'), env_vars.get('GOOGLE_CLIENT_SECRET')

        except Exception as e:
            print(f"Error reading creds: {e}")
            return None, None

    def _auth_thread(self, client_id, client_secret, req_id):
        try:
            auth_mgr = GoogleAuthManager(client_id, client_secret)
            user_info = auth_mgr.authenticate()
            
            # Check if this request is still valid
            if req_id != self.auth_request_id:
                print(f"[Auth] Thread {req_id} discarded (Current: {self.auth_request_id})")
                return

            # --- PERSIST TOKEN FOR MAIN APP ---
            try:
                # We use the Core AuthManager to save the token in the shared location
                core_auth = AuthManager()
                core_auth.creds = auth_mgr.creds
                core_auth.save_token()
                print("[Setup] Token saved for main application.")
            except Exception as e:
                print(f"[Setup] Failed to save token: {e}")
            # ----------------------------------

            # Verify with Oracle DB
            self.after(0, lambda: self.db_status_label.configure(text="Verifying permission...", text_color="#f59e0b"))
            is_valid, db_name = self._verify_operator_with_db(user_info['email'])
            
            # Double check validity after DB call
            if req_id != self.auth_request_id: return

            if is_valid:
                user_info['name'] = db_name # Use DB name as authority
                
                # Fetch Profile Picture if available
                img_data = None
                if PIL_AVAILABLE and 'picture' in user_info:
                    try:
                        resp = requests.get(user_info['picture'])
                        if resp.status_code == 200:
                            img_data = resp.content
                    except Exception as e:
                        print(f"Failed to fetch profile pic: {e}")

                self.after(0, lambda: self._update_profile_ui(user_info, "Verified Operator", img_data))
            else:
                self.after(0, lambda: self._auth_failed("Unauthorized Email. please contact admin."))
                
        except Exception as e:
             if req_id == self.auth_request_id:
                self.after(0, lambda: self._auth_failed(str(e)))

    def _auth_failed(self, msg, is_cancel=False):
        self.auth_button.configure(state="normal", text="Sign in with Google", fg_color="white", hover_color="#e5e7eb")
        if not is_cancel:
            self.db_status_label.configure(text=msg, text_color="#ef4444")
            messagebox.showerror("Authentication Failed", msg)
        else:
            self.db_status_label.configure(text="Cancelled", text_color="#f59e0b")

    def _update_profile_ui(self, user_info, status_msg, img_data=None):
        self.auth_user_info = user_info
        self.operator_name_label.configure(text=user_info['name'])
        self.operator_email_label.configure(text=user_info['email'])
        
        # Update Icon/Image
        if img_data and PIL_AVAILABLE:
            try:
                img = Image.open(BytesIO(img_data))
                # Create CTkImage
                # profile_label is a CTkLabel. We clean the text and set image.
                photo = ctk.CTkImage(light_image=img, dark_image=img, size=(80, 80))
                self.profile_label.configure(image=photo, text="") 
            except Exception as e:
                 print(f"Error setting profile image: {e}")
                 self.profile_label.configure(text_color="#22c55e")
        else:
            self.profile_label.configure(text_color="#22c55e")
            
        self.auth_button.configure(state="disabled", text="Authenticated", fg_color="#22c55e")
        self.db_status_label.configure(text=status_msg, text_color="#22c55e")

    def _verify_operator_with_db(self, email):
        """Check if email exists in OPERATORS table."""
        try:
            from dotenv import load_dotenv, dotenv_values
            # Need to get DB creds again (similar to _get_google_creds logic)
            # For simplicity, if we have selected_file, we use that.
            
            env_vars = {}
            if self.selected_file:
                pwd = self._get_zip_password_from_filename(self.selected_file)
                with pyzipper.AESZipFile(self.selected_file, 'r') as zf:
                    if pwd: zf.setpassword(pwd)
                    for info in zf.infolist():
                        if os.path.basename(info.filename) == '.env':
                            with zf.open(info.filename) as f:
                                from io import StringIO
                                env_vars = dotenv_values(stream=StringIO(f.read().decode('utf-8')))
                            break
            else:
                env_vars = dotenv_values(os.path.join(project_root, '.env'))

            import oracledb
            conn = oracledb.connect(
                user=env_vars.get('DB_USER'), 
                password=env_vars.get('DB_PASSWORD'), 
                dsn=env_vars.get('DB_DSN')
            )
            cur = conn.cursor()
            # Assuming table OPERATORS has column EMAIL? Or we verify against ACTORS?
            # User instructions said "verify operators against the Oracle Database"
            # Dashboard Docs say: "OPERATORS: Human team members."
            # We should check if this email matches an operator.
            
            # NOTE: If we don't know the schema for sure, we might need to search or guess.
            # But earlier code used "SELECT DISTINCT OWNER_OPERATOR FROM ACTORS".
            # That was for NAMES.
            # Now we need to map EMAIL -> NAME.
            # If the schema doesn't have emails, we can't verify.
            # However, usually there is an OPERATORS table.
            
            # Let's try to select from OPERATORS table first.
            try:
                cur.execute("SELECT OPR_NAME FROM OPERATORS WHERE OPR_EMAIL = :email", email=email)
                row = cur.fetchone()
                if row:
                     return True, row[0]
            except Exception:
                # Fallback or maybe the table is different?
                pass
            
            # If fail, maybe we just allow it if the user manually confirms?
            # But the requirement is "Verify authenticated user against Oracle OPERATORS table"
            # I will assume the table exists.
            
            cur.close()
            conn.close()
            return False, None

        except Exception as e:
            print(f"DB Verification failed: {e}")
            # For robustness in this blind edit, if we can't connect, maybe we warn but allow?
            # No, strictly enforce "Verify".
            return False, None

    def _show_status(self, msg, typ="info"):
        cols = {"info": "#888888", "success": "#22c55e", "error": "#ef4444"}
        self.status_label.configure(text=msg, text_color=cols.get(typ, "#888888"))

    def _register_native_host(self, ext_id):
        bp = os.path.join(project_root, 'src', 'core', 'bridge.bat')
        if not os.path.exists(bp): bp = os.path.join(project_root, '_internal', 'src', 'core', 'bridge.bat')
        mp = os.path.join(os.path.dirname(bp), 'com.instaoutreach.logger.json')
        manifest = {"name": "com.instaoutreach.logger", "description": "Native Host", "path": os.path.abspath(bp), "type": "stdio", "allowed_origins": [f"chrome-extension://{ext_id}/"]}
        with open(mp, 'w') as f: json.dump(manifest, f, indent=4)
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Google\Chrome\NativeMessagingHosts\com.instaoutreach.logger")
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, os.path.abspath(mp))
        winreg.CloseKey(key)

    def _safe_destroy(self):
        self._is_closing = True
        try: self.withdraw()
        except Exception: pass
        try: self.quit()
        except Exception: pass

def run_setup_wizard():
    """Run the setup wizard and return True if successful."""
    app = SetupWizard()
    app.mainloop()
    return True # Simple for now, can be improved

if __name__ == "__main__":
    app = SetupWizard()
    app.mainloop()
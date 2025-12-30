import customtkinter as ctk
import threading
import sys
import queue
import os
import time
import subprocess
import json
import re
import webbrowser
from tkinter import messagebox
from datetime import datetime, timedelta
from PIL import Image

# Adjust path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.core.ipc_server import IPCServer
from src.core.version import __version__ as VERSION, LOG_DIR
from src.core.auth import AuthManager
from src.core.database import DatabaseManager

# Theme
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# Colors
COLOR_BG = "#0f172a"
COLOR_CARD = "#1e293b"
COLOR_PRIMARY = "#3b82f6"
COLOR_SUCCESS = "#10b981"
COLOR_WARNING = "#f59e0b"
COLOR_DANGER = "#ef4444"
COLOR_TEXT_MUTED = "#94a3b8"

USER_PREFS_PATH = os.path.join(project_root, 'user_preferences.json')
UPDATE_CONFIG_PATH = os.path.join(project_root, 'update_config.json')

class StdoutRedirector:
    def __init__(self, text_queue, original_stream):
        self.text_queue = text_queue
        self.original_stream = original_stream
        
    def write(self, string):
        if string:
            self.text_queue.put(string)
            try:
                self.original_stream.write(string)
                self.original_stream.flush()
            except: pass
            
    def flush(self):
        try:
            self.original_stream.flush()
        except: pass

class SettingsWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Configuration")
        self.geometry("450x550")
        self.resizable(False, False)
        
        self.parent = parent
        
        # Load current prefs
        self.prefs = self._load_prefs()
        self.update_config = self._load_update_config()
        
        # --- UI Layout ---
        
        # 1. Automation Section
        ctk.CTkLabel(self, text="Automation Settings", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(20, 5))
        ctk.CTkLabel(self, text="Auto-close tabs after sending messages.", text_color="gray", font=ctk.CTkFont(size=11)).pack(pady=(0, 10))
        
        # Toggle
        self.var_enable = ctk.BooleanVar(value=self.prefs.get('auto_tab_switch', False))
        self.switch_enable = ctk.CTkSwitch(self, text="Enable Auto Tab Switcher", variable=self.var_enable, 
                                           command=self._toggle_inputs)
        self.switch_enable.pack(pady=5)
        
        # Trigger Count
        self.frame_trigger = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_trigger.pack(pady=5)
        ctk.CTkLabel(self.frame_trigger, text="Trigger every:").pack(side="left", padx=10)
        self.entry_count = ctk.CTkEntry(self.frame_trigger, width=60)
        self.entry_count.insert(0, str(self.prefs.get('tab_switch_frequency', 1)))
        self.entry_count.pack(side="left")
        ctk.CTkLabel(self.frame_trigger, text="messages").pack(side="left", padx=10)

        # Delay
        self.frame_delay = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_delay.pack(pady=5)
        ctk.CTkLabel(self.frame_delay, text="Wait delay:   ").pack(side="left", padx=10)
        self.entry_delay = ctk.CTkEntry(self.frame_delay, width=60)
        self.entry_delay.insert(0, str(self.prefs.get('tab_switch_delay', 2.0)))
        self.entry_delay.pack(side="left")
        ctk.CTkLabel(self.frame_delay, text="seconds").pack(side="left", padx=10)

        ctk.CTkFrame(self, height=2, fg_color="#333333").pack(fill="x", padx=20, pady=20)

        # 2. Update Source Section
        ctk.CTkLabel(self, text="Update Source", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(0, 5))
        ctk.CTkLabel(self, text="GitHub Repository for auto-updates.", text_color="gray", font=ctk.CTkFont(size=11)).pack(pady=(0, 10))
        
        self.entry_repo = ctk.CTkEntry(self, width=350, placeholder_text="https://github.com/owner/repo")
        self.entry_repo.pack(pady=5)
        
        # Pre-fill Repo URL
        owner = self.update_config.get('owner')
        repo = self.update_config.get('repo')
        if owner and repo:
            self.entry_repo.insert(0, f"https://github.com/{owner}/{repo}")

        # Save Button
        ctk.CTkButton(self, text="Save All Settings", command=self._save_prefs, fg_color=COLOR_SUCCESS, height=40).pack(side="bottom", pady=30)
        
        self._toggle_inputs()
        
        # Center window
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (450 // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (550 // 2)
        self.geometry(f"+{x}+{y}")
        self.lift()
        self.focus_force()

    def _toggle_inputs(self):
        state = "normal" if self.var_enable.get() else "disabled"
        self.entry_count.configure(state=state)
        self.entry_delay.configure(state=state)

    def _load_prefs(self):
        if os.path.exists(USER_PREFS_PATH):
            try:
                with open(USER_PREFS_PATH, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"[Settings] Failed to load preferences: {e}")
        return {}

    def _load_update_config(self):
        if os.path.exists(UPDATE_CONFIG_PATH):
            try:
                with open(UPDATE_CONFIG_PATH, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"[Settings] Failed to load update config: {e}")
        return {}

    def _save_prefs(self):
        try:
            # 1. Automation Prefs
            count = int(self.entry_count.get())
            delay = float(self.entry_delay.get())
            if count < 1: raise ValueError("Count must be >= 1")
            if delay < 0: raise ValueError("Delay must be >= 0")
            
            new_prefs = self.prefs.copy()
            new_prefs['auto_tab_switch'] = self.var_enable.get()
            new_prefs['tab_switch_frequency'] = count
            new_prefs['tab_switch_delay'] = delay
            
            with open(USER_PREFS_PATH, 'w') as f:
                json.dump(new_prefs, f)
            
            # 2. Update Config
            repo_url = self.entry_repo.get().strip()
            if repo_url:
                match = re.search(r'github\\.com/([^/]+)/([^/]+)', repo_url)
                if match:
                    new_update_config = {'owner': match.group(1), 'repo': match.group(2).removesuffix('.git')}
                    with open(UPDATE_CONFIG_PATH, 'w') as f:
                        json.dump(new_update_config, f)
                else:
                    raise ValueError("Invalid GitHub URL format.")

            messagebox.showinfo("Saved", "Settings saved successfully!\nRestart Agent to apply changes.")
            self.destroy()
        except ValueError as e:
            messagebox.showerror("Error", f"Invalid input: {e}")

class StatCard(ctk.CTkFrame):
    def __init__(self, parent, title, value="0", color=COLOR_PRIMARY):
        super().__init__(parent, fg_color=COLOR_CARD, corner_radius=10)
        self.grid_columnconfigure(0, weight=1)
        self.lbl_title = ctk.CTkLabel(self, text=title.upper(), font=ctk.CTkFont(size=10, weight="bold"), text_color=COLOR_TEXT_MUTED)
        self.lbl_title.grid(row=0, column=0, padx=15, pady=(10, 0), sticky="w")
        self.lbl_value = ctk.CTkLabel(self, text=value, font=ctk.CTkFont(size=28, weight="bold"), text_color="white")
        self.lbl_value.grid(row=1, column=0, padx=15, pady=(0, 5), sticky="w")
        self.indicator = ctk.CTkLabel(self, text="", height=3, fg_color=color, corner_radius=2)
        self.indicator.grid(row=2, column=0, padx=15, pady=(0, 10), sticky="ew")
    def update_value(self, value):
        self.lbl_value.configure(text=str(value))

class AppUI(ctk.CTk):
    def __init__(self, launcher=None):
        super().__init__()
        self.launcher = launcher  # Store launcher instance
        self.title(f"InstaCRM Desktop Agent v{VERSION}")
        self.geometry("1400x850")
        self.configure(fg_color="#0F0E13")  # Match Welcome Window background
        
        # Set window icon
        try:
            icon_path = os.path.join(project_root, 'assets', 'logo.ico')
            if os.path.exists(icon_path):
                self.iconbitmap(icon_path)
        except: pass
        
        # State
        self.auth_manager = AuthManager()
        self.db_manager = None
        try:
            self.db_manager = DatabaseManager()
        except Exception:
            pass 

        self.user_info = None
        self.operator_data = None
        
        self.server = None
        self.server_thread = None
        self.is_running = False
        self.start_time = None
        self.log_queue = queue.Queue()
        self.settings_window = None
        
        # Metrics
        self.metrics = {"outreach_sent": 0, "profiles_scraped": 0, "leads_enriched": 0, "rules_triggered": 0}

        # Redirects
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr
        sys.stdout = StdoutRedirector(self.log_queue, self.original_stdout)
        sys.stderr = StdoutRedirector(self.log_queue, self.original_stderr)

        # Initialize Modern UI
        self._init_ui()

        # Start session check
        self.after(500, self._check_session)

    def _init_ui(self):
        # Main grid layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # 1. HEADER BAR (like Welcome Window)
        self.header_bar = ctk.CTkFrame(self, fg_color="#1a1b26", height=100, corner_radius=0)
        self.header_bar.grid(row=0, column=0, sticky="ew")
        self.header_bar.grid_propagate(False)
        
        header_container = ctk.CTkFrame(self.header_bar, fg_color="transparent")
        header_container.pack(fill="x", padx=40, pady=25)
        
        # App Title & Version (Left)
        title_frame = ctk.CTkFrame(header_container, fg_color="transparent")
        title_frame.pack(side="left")
        
        ctk.CTkLabel(
            title_frame,
            text="INSTA OUTREACH LOGGER (REMASTERED)",
            font=ctk.CTkFont(family="Segoe UI", size=24, weight="bold"),
            text_color="#7C3AED"  # Purple accent
        ).pack(anchor="w")
        
        ctk.CTkLabel(
            title_frame,
            text=f"REMASTERED | v{VERSION}",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#565f89"
        ).pack(anchor="w")
        
        # User Profile Badge (Right)
        self.profile_frame = ctk.CTkFrame(header_container, fg_color="#24283b", corner_radius=8, border_width=1, border_color="#414868")
        self.profile_frame.pack(side="right")
        
        icon_lbl = ctk.CTkLabel(self.profile_frame, text="🦁", font=ctk.CTkFont(size=24))
        icon_lbl.pack(side="left", padx=(15, 10), pady=5)
        
        profile_info = ctk.CTkFrame(self.profile_frame, fg_color="transparent")
        profile_info.pack(side="left", padx=(0, 20), pady=5)
        
        self.profile_name_lbl = ctk.CTkLabel(
            profile_info,
            text="LOADING...",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color="#c0caf5"
        )
        self.profile_name_lbl.pack(anchor="w")
        
        self.profile_email_lbl = ctk.CTkLabel(
            profile_info,
            text="No Email",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color="#565f89"
        )
        self.profile_email_lbl.pack(anchor="w")

        # Sign Out Button
        self.sign_out_btn = ctk.CTkButton(
            self.profile_frame,
            text="Sign Out",
            font=ctk.CTkFont(size=12),
            width=60,
            height=24,
            fg_color="#332d41",
            hover_color="#ef4444",
            command=self._handle_sign_out
        )
        self.sign_out_btn.pack(side="left", padx=(10, 15))

        # 2. MAIN CONTENT AREA
        self.content_area = ctk.CTkFrame(self, fg_color="transparent")
        self.content_area.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
        self.content_area.grid_columnconfigure(0, weight=1)
        self.content_area.grid_rowconfigure(0, weight=1)

    def _update_profile_display(self):
        """Update header profile badge with user info"""
        if self.user_info:
            name = self.user_info.get('name', 'Unknown')
            email = self.user_info.get('email', 'No Email')
            self.profile_name_lbl.configure(text=name.upper())
            self.profile_email_lbl.configure(text=email)
        elif self.operator_data:
            # Handle both uppercase (legacy) and lowercase (standard) keys
            name = self.operator_data.get('operator_name') or self.operator_data.get('OPR_NAME') or 'Unknown'
            email = self.operator_data.get('operator_email') or self.operator_data.get('OPR_EMAIL') or 'No Email'
            self.profile_name_lbl.configure(text=name.upper())
            self.profile_email_lbl.configure(text=email)

    def _update_status_indicator(self, connected: bool):
        """Update connection status visual feedback"""
        # Update control card border color if it exists
        if hasattr(self, 'control_card'):
            color = "#10b981" if connected else "#ef4444"  # Green if connected, red if not
            self.control_card.configure(border_color=color)

    def _check_session(self):
        """Check if user is authenticated and show appropriate view"""
        # Load operator config
        config_path = os.path.join(project_root, 'operator_config.json')
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    self.operator_data = json.load(f)
            except: pass
        
        # Check auth using correct method
        user = self.auth_manager.get_authenticated_user()
        if user:
            self.user_info = user
            # Go directly to dashboard
            self._show_dashboard()
        else:
            self._show_welcome_launcher()

    def _handle_sign_out(self):
        """Handle sign out request."""
        if messagebox.askyesno("Sign Out", "Are you sure you want to sign out?"):
            if self.auth_manager.logout():
                # Stop server if running
                if self.server:
                    self._stop_server()
                
                # Reset UI state
                self.user_info = None
                self.operator_data = None
                
                # Return to welcome screen
                for widget in self.winfo_children():
                    widget.destroy()
                self._init_ui()
                self._show_welcome_launcher()
            else:
                messagebox.showerror("Error", "Failed to sign out. Please try manually deleting the token file.")

    def _show_welcome_launcher(self):
        """Show unified welcome/launcher screen (like Welcome Window)"""
        for widget in self.content_area.winfo_children():
            widget.destroy()
        
        # Update profile
        self._update_profile_display()
        
        # Center content
        self.content_area.grid_columnconfigure(0, weight=2)
        self.content_area.grid_columnconfigure(1, weight=1)
        self.content_area.grid_rowconfigure(0, weight=1)
        
        # LEFT COLUMN (Main Action)
        main_col = ctk.CTkFrame(self.content_area, fg_color="transparent")
        main_col.grid(row=0, column=0, sticky="nsew", padx=(40, 20), pady=40)
        
        # System Status Card
        status_card = ctk.CTkFrame(main_col, fg_color="#16161e", corner_radius=12, border_width=1, border_color="#7C3AED")
        status_card.pack(fill="x", pady=(0, 20), ipady=15)
        
        ctk.CTkLabel(
            status_card,
            text="SYSTEM STATUS",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#565f89"
        ).pack(anchor="w", padx=20, pady=(10, 5))
        
        status_row = ctk.CTkFrame(status_card, fg_color="transparent")
        status_row.pack(fill="x", padx=20)
        
        self.status_indicator = ctk.CTkLabel(status_row, text="●", font=ctk.CTkFont(size=24), text_color="#22c55e")
        self.status_indicator.pack(side="left")
        
        self.status_label = ctk.CTkLabel(
            status_row,
            text="System is up to date",
            font=ctk.CTkFont(family="Segoe UI", size=16),
            text_color="#a9b1d6"
        )
        self.status_label.pack(side="left", padx=10)

        # Update Button (Hidden by default)
        self.btn_update = ctk.CTkButton(
            status_row,
            text="UPDATE AVAILABLE",
            command=self._perform_update,
            fg_color="#f59e0b",
            hover_color="#d97706",
            text_color="white",
            font=ctk.CTkFont(weight="bold")
        )
        
        # Check for updates if launcher is available
        if self.launcher:
            threading.Thread(target=self._check_updates, daemon=True).start()
        
        # Hero Button - Initialize Logger
        start_btn = ctk.CTkButton(
            main_col,
            text="INITIALIZE LOGGER",
            command=self._initialize_agent,
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
            fg_color="#7C3AED",
            hover_color="#6D28D9",
            height=100,
            corner_radius=12,
            border_width=2,
            border_color="#8B5CF6"
        )
        start_btn.pack(fill="x")
        
        # RIGHT COLUMN (Quick Actions)
        side_col = ctk.CTkFrame(self.content_area, fg_color="transparent")
        side_col.grid(row=0, column=1, sticky="nsew", padx=(20, 40), pady=40)
        
        ctk.CTkLabel(
            side_col,
            text="QUICK ACTIONS",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#565f89"
        ).pack(anchor="w", pady=(0, 10))
        
        # Quick action buttons
        self._create_action_btn(side_col, "⚙️  Reconfigure", self.run_setup_gui)
        self._create_action_btn(side_col, "🧩  Extension ID", self._show_extension_info)
        self._create_action_btn(side_col, "📂  Open Logs", self._open_logs)
        
        # Footer
        footer = ctk.CTkFrame(self.content_area, fg_color="transparent")
        footer.grid(row=1, column=0, columnspan=2, sticky="ew", padx=40, pady=(0, 20))
        
        ctk.CTkLabel(
            footer,
            text="Insta Outreach Logger - Secure Environment",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color="#565f89"
        ).pack(side="left")
        
        ctk.CTkLabel(
            footer,
            text="Need help? Contact Admin.",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color="#7C3AED",
            cursor="hand2"
        ).pack(side="right")
    
    def _initialize_agent(self):
        """Transition from welcome screen to agent dashboard"""
        self._show_dashboard()
        # Auto-start the service
        self.after(500, self.start_service)
        
    def _check_updates(self):
        """Check for updates using launcher instance"""
        if not self.launcher: return
        try:
            self.after(0, lambda: self.status_label.configure(text="Checking for updates..."))
            update_avail, ver, url = self.launcher.check_for_updates()
            self.after(0, lambda: self._update_status(update_avail, ver, url))
        except Exception as e:
            print(f"[UI] Update check failed: {e}")
            self.after(0, lambda: self.status_label.configure(text="System Ready (Update Check Failed)", text_color="#ef4444"))

    def _update_status(self, avail, ver, url):
        if avail:
            self.update_available = True
            self.new_version = ver
            self.download_url = url
            self.status_label.configure(text=f"Update Available: v{ver}", text_color="#f59e0b")
            self.status_indicator.configure(text_color="#f59e0b")
            self.btn_update.pack(side="right", padx=10)
        else:
            self.status_label.configure(text="System is up to date", text_color="#a9b1d6")
            self.status_indicator.configure(text_color="#22c55e")

    def _perform_update(self):
        if self.launcher and self.download_url:
            self.status_label.configure(text="Downloading Update...", text_color="#3b82f6")
            self.btn_update.configure(state="disabled")
            
            def run_update():
                path = self.launcher.download_update(self.download_url, self.new_version)
                if path:
                    self.launcher.apply_update(path)
                else:
                    self.after(0, lambda: self.status_label.configure(text="Update Download Failed", text_color="#ef4444"))
                    
            threading.Thread(target=run_update, daemon=True).start()
    
    def _show_extension_info(self):
        """Show extension ID info dialog"""
        ext_id = "Your Extension ID: Check chrome://extensions"
        messagebox.showinfo("Extension ID", ext_id)

    def _verify_operator_status(self):
        """Check if email exists in Oracle."""
        if not self.db_manager:
            messagebox.showwarning("Setup Required", "Database configuration missing. Launching Setup Wizard...")
            self.run_setup_gui()
            self.after(2000, self._check_session) # Retry after some time
            return

        self._clear_content()
        lbl = ctk.CTkLabel(self.container, text="Verifying Identity...", font=ctk.CTkFont(size=20))
        lbl.grid(row=0, column=0)
        
        def _bg_check():
            try:
                op = self.db_manager.get_operator_by_email(self.user_info['email'])
                if op:
                    self.operator_data = op
                    self._save_local_config(op)
                    self.after(0, self._show_dashboard)
                else:
                    self.after(0, self._show_onboarding)
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Connection Error", f"Failed to connect to Cloud Core: {e}"))
                self.after(0, self._show_login_screen)

        threading.Thread(target=_bg_check, daemon=True).start()

    def _save_local_config(self, op_data):
        config_path = os.path.join(project_root, 'operator_config.json')
        with open(config_path, 'w') as f:
            json.dump({"operator_name": op_data['OPR_NAME']}, f)

    # --- VIEWS ---

    def _clear_content(self):
        if hasattr(self, 'content_area'):
            for widget in self.content_area.winfo_children():
                widget.destroy()

    def _show_login_screen(self):
        self._clear_content()
        # Ensure we are full screen in content area
        frame = ctk.CTkFrame(self.content_area, fg_color="#1a1a1a", corner_radius=20)
        frame.place(relx=0.5, rely=0.5, anchor="center")
        
        ctk.CTkLabel(frame, text="InstaCRM Ecosystem", font=ctk.CTkFont(size=28, weight="bold", family="Inter")).pack(padx=60, pady=(40, 10))
        ctk.CTkLabel(frame, text="Secure Agent Access", font=ctk.CTkFont(size=14, family="Inter"), text_color="#9ca3af").pack(pady=(0, 30))
        
        btn_login = ctk.CTkButton(frame, text="Sign in with Google", command=self._handle_login, height=50, width=280, 
                                  font=ctk.CTkFont(size=15, weight="bold", family="Inter"), fg_color="#3b82f6")
        btn_login.pack(padx=60, pady=(0, 20))
        
        ctk.CTkButton(frame, text="Run Technical Setup", command=self.run_setup_gui, fg_color="transparent", text_color="#6b7280", border_width=1).pack(pady=(0, 40))

    def _show_onboarding(self):
        self._clear_content()
        frame = ctk.CTkFrame(self.content_area, fg_color="#1a1a1a", corner_radius=20)
        frame.place(relx=0.5, rely=0.5, anchor="center")
        
        ctk.CTkLabel(frame, text="Establish Identity", font=ctk.CTkFont(size=24, weight="bold", family="Inter")).pack(padx=40, pady=(30, 10))
        ctk.CTkLabel(frame, text=f"Linking: {self.user_info['email']}", text_color="#9ca3af").pack(pady=(0, 20))
        
        self.entry_name = ctk.CTkEntry(frame, placeholder_text="Choose Operator Name", width=300, height=40)
        self.entry_name.pack(padx=40, pady=10)
        self.entry_name.insert(0, self.user_info.get('name', ''))
        
        btn_confirm = ctk.CTkButton(frame, text="Confirm Identity", command=self._handle_onboarding, height=45, width=300, fg_color="#10b981")
        btn_confirm.pack(padx=40, pady=(20, 10))

        ctk.CTkButton(frame, text="Open Extension Folder", command=self.open_extension_folder, fg_color="transparent", text_color="#3b82f6").pack(pady=(0, 30))

    def _show_dashboard(self):
        # Clear main content only
        for widget in self.content_area.winfo_children():
            widget.destroy()
        
        # Update profile display
        self._update_profile_display()
        
        # Ensure main view grid
        self.content_area.grid_columnconfigure(0, weight=2)
        self.content_area.grid_columnconfigure(1, weight=1)
        self.content_area.grid_rowconfigure(0, weight=1)
        
        # LEFT COLUMN (Main Content)
        main_col = ctk.CTkFrame(self.content_area, fg_color="transparent")
        main_col.grid(row=0, column=0, sticky="nsew", padx=(40, 20), pady=20)
        
        # Control Card (Status + Buttons)
        self.control_card = ctk.CTkFrame(main_col, fg_color="#16161e", corner_radius=12, border_width=2, border_color="#ef4444")  # Start with red (disconnected)
        self.control_card.pack(fill="x", pady=(0, 20))
        
        # Control Header
        ctk.CTkLabel(
            self.control_card,
            text="AGENT CONTROL",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#565f89"
        ).pack(anchor="w", padx=20, pady=(15, 5))
        
        # Control Buttons Row
        btn_row = ctk.CTkFrame(self.control_card, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=(0, 15))
        
        self.btn_start = ctk.CTkButton(
            btn_row,
            text="▶ START AGENT",
            command=self.start_service,
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            fg_color="#7C3AED",
            hover_color="#6D28D9",
            height=60,
            corner_radius=8,
            border_width=2,
            border_color="#8B5CF6"
        )
        self.btn_start.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        self.btn_stop = ctk.CTkButton(
            btn_row,
            text="⏹ STOP",
            command=self.stop_service,
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            fg_color="#24283b",
            hover_color="#ef4444",
            height=60,
            corner_radius=8,
            state="disabled"
        )
        self.btn_stop.pack(side="left", fill="x", expand=True)
        
        # Session Timer
        timer_frame = ctk.CTkFrame(self.control_card, fg_color="transparent")
        timer_frame.pack(fill="x", padx=20, pady=(0, 15))
        
        ctk.CTkLabel(
            timer_frame,
            text="SESSION TIME",
            font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
            text_color="#565f89"
        ).pack(side="left")
        
        self.lbl_timer = ctk.CTkLabel(
            timer_frame,
            text="00:00:00",
            font=ctk.CTkFont(family="Consolas", size=16, weight="bold"),
            text_color="#c0caf5"
        )
        self.lbl_timer.pack(side="right")
        
        # Stats Grid
        stats_label = ctk.CTkLabel(
            main_col,
            text="METRICS",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#565f89"
        )
        stats_label.pack(anchor="w", pady=(0, 10))
        
        stats_grid = ctk.CTkFrame(main_col, fg_color="transparent")
        stats_grid.pack(fill="both", expand=True)
        stats_grid.grid_columnconfigure((0, 1), weight=1)
        stats_grid.grid_rowconfigure((0, 1), weight=1)
        
        # Stat Cards (Welcome Window style)
        self.card_outreach = self._create_stat_card(stats_grid, "OUTREACH SENT", "0", "#7C3AED")
        self.card_outreach.grid(row=0, column=0, padx=(0, 10), pady=(0, 10), sticky="nsew")
        
        self.card_scraped = self._create_stat_card(stats_grid, "PROFILES SCRAPED", "0", "#8b5cf6")
        self.card_scraped.grid(row=0, column=1, padx=(10, 0), pady=(0, 10), sticky="nsew")
        
        self.card_enriched = self._create_stat_card(stats_grid, "LEADS ENRICHED", "0", "#10b981")
        self.card_enriched.grid(row=1, column=0, padx=(0, 10), pady=(10, 0), sticky="nsew")
        
        self.card_safety = self._create_stat_card(stats_grid, "SAFETY ALERTS", "0", "#f59e0b")
        self.card_safety.grid(row=1, column=1, padx=(10, 0), pady=(10, 0), sticky="nsew")
        
        # RIGHT COLUMN (Console + Actions)
        side_col = ctk.CTkFrame(self.content_area, fg_color="transparent")
        side_col.grid(row=0, column=1, sticky="nsew", padx=(20, 40), pady=20)
        
        # Quick Actions Header
        ctk.CTkLabel(
            side_col,
            text="QUICK ACTIONS",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#565f89"
        ).pack(anchor="w", pady=(0, 10))
        
        # Action Buttons
        self._create_action_btn(side_col, "⚙️  Settings", self.open_settings)
        self._create_action_btn(side_col, "📂  View Logs", self._open_logs)
        self._create_action_btn(side_col, "🔧  Setup Wizard", self.run_setup_gui)
        
        # Console
        ctk.CTkLabel(
            side_col,
            text="LIVE CONSOLE",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#565f89"
        ).pack(anchor="w", pady=(20, 10))
        
        self.console_box = ctk.CTkTextbox(
            side_col,
            font=("Consolas", 11),
            bg_color="#0F0E13",
            fg_color="#16161e",
            text_color="#00ff00",
            border_width=1,
            border_color="#414868",
            corner_radius=8
        )
        self.console_box.pack(fill="both", expand=True)
        self.console_box.insert("0.0", f"[SYSTEM] {datetime.now().strftime('%H:%M:%S')} - Agent Ready.\n")
        self.console_box.configure(state="disabled")
        
        self.after(100, self._update_loop)
        self.after(1000, self._session_monitor_loop)

    def _create_stat_card(self, parent, title, value, accent_color):
        """Create a stat card matching Welcome Window style"""
        card = ctk.CTkFrame(parent, fg_color="#24283b", corner_radius=8, border_width=1, border_color="#414868")
        
        # Title
        ctk.CTkLabel(
            card,
            text=title,
            font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
            text_color="#565f89"
        ).pack(anchor="w", padx=15, pady=(12, 5))
        
        # Value
        value_lbl = ctk.CTkLabel(
            card,
            text=value,
            font=ctk.CTkFont(family="Segoe UI", size=32, weight="bold"),
            text_color="#c0caf5"
        )
        value_lbl.pack(anchor="w", padx=15, pady=(0, 5))
        
        # Accent bar
        accent_bar = ctk.CTkFrame(card, fg_color=accent_color, height=3, corner_radius=2)
        accent_bar.pack(fill="x", padx=15, pady=(0, 12))
        
        # Store value label for updates
        card.value_lbl = value_lbl
        card.update_value = lambda v: value_lbl.configure(text=str(v))
        
        return card
    
    def _create_action_btn(self, parent, text, command):
        """Create action button matching Welcome Window style"""
        btn = ctk.CTkButton(
            parent,
            text=text,
            command=command,
            fg_color="#24283b",
            hover_color="#414868",
            height=45,
            anchor="w",
            corner_radius=8,
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color="#c0caf5"
        )
        btn.pack(fill="x", pady=(0, 8))

    # --- REMOVE OLD SIDEBAR & CONTENT METHODS ---
    # (The old _create_sidebar and _create_dashboard_content are replaced by _show_dashboard and _init_ui)

    def _open_logs(self):
        log_dir = LOG_DIR
        if not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        try:
            subprocess.run(['explorer', os.path.realpath(log_dir)])
        except Exception as e:
            messagebox.showerror("Error", f"Could not open logs: {e}")

    def _open_support(self):
        webbrowser.open("https://github.com/hashaam101/Insta-Outreach-Logger-Remastered/issues")

    # --- HANDLERS ---

    def _handle_login(self):
        user_info, error = self.auth_manager.login()
        if error: messagebox.showerror("Login Failed", error)
        elif user_info:
            self.user_info = user_info
            self._verify_operator_status()

    def _handle_logout(self):
        self.stop_service()
        self.auth_manager.logout()
        self._show_login_screen()

    def _handle_onboarding(self):
        name = self.entry_name.get().strip()
        if not name: return
        try:
            new_id = self.db_manager.create_operator(name, self.user_info['email'])
            self.operator_data = {'OPR_ID': new_id, 'OPR_NAME': name, 'OPR_EMAIL': self.user_info['email']}
            self._save_local_config(self.operator_data)
            self._show_dashboard()
        except Exception as e: messagebox.showerror("Onboarding Failed", str(e))

    def open_extension_folder(self):
        path = os.path.join(os.path.expanduser("~"), "Documents", "Insta Logger Remastered", "extension")
        if os.path.exists(path): subprocess.run(['explorer', os.path.realpath(path)])
        else: messagebox.showerror("Error", "Extension folder not found. Please run Setup Wizard.")
    
    def open_settings(self):
        if self.settings_window is None or not self.settings_window.winfo_exists():
            self.settings_window = SettingsWindow(self)
        else:
            self.settings_window.focus()

    def run_setup_gui(self):
        try:
            script = os.path.join(project_root, "src", "gui", "setup_wizard.py")
            subprocess.Popen([sys.executable, script])
        except Exception as e: messagebox.showerror("Error", str(e))

    # --- AGENT LOGIC ---

    def start_service(self):
        if self.is_running: return
        self.log_to_feed("Initializing Agent...", "SYSTEM")
        self.btn_start.configure(state="disabled", fg_color="#374151")
        self.btn_stop.configure(state="normal", fg_color="#ef4444")
        
        self.start_time = datetime.now()
        try:
            self.server = IPCServer()
            self.is_running = True
            self.server_thread = threading.Thread(target=self._run_server, daemon=True)
            self.server_thread.start()
            self._update_status_indicator(True)
        except Exception as e:
            messagebox.showerror("Startup Error", str(e))
            self.stop_service()

    def stop_service(self):
        if not self.is_running: return
        self.log_to_feed("Stopping services...", "SYSTEM")
        if self.server: threading.Thread(target=self.server.stop, daemon=True).start()
        self.is_running = False
        self.btn_start.configure(state="normal", fg_color="#10b981")
        self.btn_stop.configure(state="disabled", fg_color="#374151")
        self._update_status_indicator(False)

        if hasattr(self, 'lbl_timer'):
            self.lbl_timer.configure(text="00:00:00")

    def sync_now(self):
        if self.server and self.server.sync_engine:
            self.server.sync_engine.trigger_sync()
            self.log_to_feed("Manual Sync Triggered", "SYNC")

    def _run_server(self):
        try: self.server.start()
        except Exception as e: print(f"[Fatal] {e}")
        finally: self.is_running = False

    def _session_monitor_loop(self):
        if self.is_running and self.start_time:
            delta = datetime.now() - self.start_time
            if hasattr(self, 'lbl_timer'):
                self.lbl_timer.configure(text=str(delta).split('.')[0])
        self.after(1000, self._session_monitor_loop)

    def _update_loop(self):
        while not self.log_queue.empty():
            try: self._process_log(self.log_queue.get_nowait())
            except queue.Empty: break
        self.after(50, self._update_loop)

    def _process_log(self, line):
        clean_line = line.strip()
        if not clean_line: return
        if "[IPC] Queued outreach" in clean_line:
            self.metrics["outreach_sent"] += 1
            if hasattr(self, 'card_outreach'): self.card_outreach.update_value(self.metrics["outreach_sent"])
            self.log_to_feed("Outreach Sent", "OUTREACH")
        elif "Found contact info" in clean_line:
            self.metrics["leads_enriched"] += 1
            if hasattr(self, 'card_enriched'): self.card_enriched.update_value(self.metrics["leads_enriched"])
            self.log_to_feed("Lead Enriched", "SUCCESS")
        elif "Blocked:" in clean_line:
            self.metrics["rules_triggered"] += 1
            if hasattr(self, 'card_safety'): self.card_safety.update_value(self.metrics["rules_triggered"])
            self.log_to_feed(f"Safety: {clean_line.split('Blocked: ')[-1]}", "ALERT")
        elif "[SYNC] Status: OK" in clean_line:
            self.log_to_feed("Cloud Sync Completed", "SYNC")
        elif "[SYNC] Status: Error" in clean_line:
            self.log_to_feed("Cloud Sync Failed", "ERROR")
        elif "[Auto]" in clean_line:
            self.log_to_feed(clean_line, "AUTO")

    def log_to_feed(self, message, type="INFO"):
        if not hasattr(self, 'console_box'): return
        ts = datetime.now().strftime("%H:%M:%S")
        self.console_box.configure(state="normal")
        self.console_box.insert("0.0", f"[{ts}] [{type}] {message}\n")
        self.console_box.configure(state="disabled")

    def on_closing(self):
        if self.is_running: self.stop_service()
        self.destroy()
        sys.exit(0)

if __name__ == "__main__":
    app = AppUI()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()

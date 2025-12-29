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
    def __init__(self, text_queue):
        self.text_queue = text_queue
    def write(self, string):
        if string: self.text_queue.put(string)
    def flush(self): pass

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
            except: pass
        return {}

    def _load_update_config(self):
        if os.path.exists(UPDATE_CONFIG_PATH):
            try:
                with open(UPDATE_CONFIG_PATH, 'r') as f:
                    return json.load(f)
            except: pass
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
    def __init__(self):
        super().__init__()
        self.title(f"InstaCRM Desktop Agent v{VERSION}")
        self.geometry("1200x750")
        
        # State
        self.auth_manager = AuthManager()
        self.db_manager = None
        try:
            self.db_manager = DatabaseManager()
        except Exception:
            pass # Will prompt for setup later if missing

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
        sys.stdout = StdoutRedirector(self.log_queue)
        sys.stderr = StdoutRedirector(self.log_queue)

        # Initial View
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.grid(row=0, column=0, sticky="nsew")
        self.container.grid_columnconfigure(0, weight=1)
        self.container.grid_rowconfigure(0, weight=1)

        self._check_session()

    def _check_session(self):
        """Check for existing valid session."""
        user = self.auth_manager.get_authenticated_user()
        if user:
            self.user_info = user
            self._verify_operator_status()
        else:
            self._show_login_screen()

    def _verify_operator_status(self):
        """Check if email exists in Oracle."""
        if not self.db_manager:
            messagebox.showwarning("Setup Required", "Database configuration missing. Launching Setup Wizard...")
            self.run_setup_gui()
            self.after(2000, self._check_session) # Retry after some time
            return

        self._clear_container()
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

    def _clear_container(self):
        for widget in self.container.winfo_children():
            widget.destroy()

    def _show_login_screen(self):
        self._clear_container()
        frame = ctk.CTkFrame(self.container, fg_color=COLOR_CARD, corner_radius=20)
        frame.place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(frame, text="InstaCRM Ecosystem", font=ctk.CTkFont(size=28, weight="bold")).pack(padx=60, pady=(40, 10))
        ctk.CTkLabel(frame, text="Secure Agent Access", font=ctk.CTkFont(size=14), text_color=COLOR_TEXT_MUTED).pack(pady=(0, 30))
        btn_login = ctk.CTkButton(frame, text="Sign in with Google", command=self._handle_login, height=50, width=280, 
                                  font=ctk.CTkFont(size=15, weight="bold"), fg_color=COLOR_PRIMARY)
        btn_login.pack(padx=60, pady=(0, 20))
        
        ctk.CTkButton(frame, text="Run Technical Setup", command=self.run_setup_gui, fg_color="transparent", text_color=COLOR_TEXT_MUTED, border_width=1).pack(pady=(0, 40))

    def _show_onboarding(self):
        self._clear_container()
        frame = ctk.CTkFrame(self.container, fg_color=COLOR_CARD, corner_radius=20)
        frame.place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(frame, text="Establish Identity", font=ctk.CTkFont(size=24, weight="bold")).pack(padx=40, pady=(30, 10))
        ctk.CTkLabel(frame, text=f"Linking: {self.user_info['email']}", text_color=COLOR_TEXT_MUTED).pack(pady=(0, 20))
        
        self.entry_name = ctk.CTkEntry(frame, placeholder_text="Choose Operator Name", width=300, height=40)
        self.entry_name.pack(padx=40, pady=10)
        self.entry_name.insert(0, self.user_info.get('name', ''))
        
        btn_confirm = ctk.CTkButton(frame, text="Confirm Identity", command=self._handle_onboarding, height=45, width=300, fg_color=COLOR_SUCCESS)
        btn_confirm.pack(padx=40, pady=(20, 10))

        ctk.CTkButton(frame, text="Open Extension Folder", command=self.open_extension_folder, fg_color="transparent", text_color=COLOR_PRIMARY).pack(pady=(0, 30))

    def _show_dashboard(self):
        self._clear_container()
        self.container.grid_columnconfigure(1, weight=1)
        self.container.grid_rowconfigure(0, weight=1)
        self._create_sidebar()
        self._create_dashboard_content()
        self.after(100, self._update_loop)
        self.after(1000, self._session_monitor_loop)

    def _create_sidebar(self):
        sidebar = ctk.CTkFrame(self.container, width=220, corner_radius=0, fg_color=COLOR_BG)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_rowconfigure(10, weight=1)

        ctk.CTkLabel(sidebar, text="InstaCRM", font=ctk.CTkFont(size=24, weight="bold")).grid(row=0, column=0, padx=20, pady=(30, 5))
        ctk.CTkLabel(sidebar, text=f"OP: {self.operator_data['OPR_NAME'][:15]}", font=ctk.CTkFont(size=12, weight="bold"), text_color=COLOR_PRIMARY).grid(row=1, column=0, padx=20, pady=(0, 30))

        self.btn_start = ctk.CTkButton(sidebar, text="CONNECT AGENT", command=self.start_service, fg_color=COLOR_SUCCESS, hover_color="#059669")
        self.btn_start.grid(row=2, column=0, padx=20, pady=10)

        self.lbl_sync_status = ctk.CTkLabel(sidebar, text="SYNC: --", font=ctk.CTkFont(size=10, weight="bold"), text_color="#666666")
        self.lbl_sync_status.grid(row=3, column=0, padx=20, pady=(0, 10))

        self.btn_stop = ctk.CTkButton(sidebar, text="DISCONNECT", command=self.stop_service, fg_color=COLOR_CARD, hover_color=COLOR_DANGER, state="disabled")
        self.btn_stop.grid(row=4, column=0, padx=20, pady=10)

        ctk.CTkLabel(sidebar, text="TOOLS", text_color=COLOR_TEXT_MUTED, font=ctk.CTkFont(size=10)).grid(row=4, column=0, padx=20, pady=(20, 5), sticky="w")

        self.btn_sync = ctk.CTkButton(sidebar, text="Force Cloud Sync", command=self.sync_now, fg_color=COLOR_CARD, hover_color="#334155")
        self.btn_sync.grid(row=5, column=0, padx=20, pady=5)
        
        self.btn_settings = ctk.CTkButton(sidebar, text="Automation Settings", command=self.open_settings, fg_color=COLOR_CARD, hover_color="#334155")
        self.btn_settings.grid(row=6, column=0, padx=20, pady=5)

        ctk.CTkButton(sidebar, text="Open Extension Dir", command=self.open_extension_folder, fg_color=COLOR_CARD, hover_color="#334155").grid(row=7, column=0, padx=20, pady=5)
        ctk.CTkButton(sidebar, text="Setup Wizard", command=self.run_setup_gui, fg_color=COLOR_CARD, hover_color="#334155").grid(row=8, column=0, padx=20, pady=5)

        # Support Section
        ctk.CTkLabel(sidebar, text="SUPPORT", text_color=COLOR_TEXT_MUTED, font=ctk.CTkFont(size=10)).grid(row=9, column=0, padx=20, pady=(20, 5), sticky="w")
        
        ctk.CTkButton(sidebar, text="View Logs", command=self._open_logs, fg_color=COLOR_CARD, hover_color="#334155").grid(row=10, column=0, padx=20, pady=5)
        ctk.CTkButton(sidebar, text="Report Issue", command=self._open_support, fg_color=COLOR_CARD, hover_color="#334155").grid(row=11, column=0, padx=20, pady=5)

        ctk.CTkButton(sidebar, text="Log Out", command=self._handle_logout, fg_color="transparent", border_width=1, text_color=COLOR_TEXT_MUTED).grid(row=12, column=0, padx=20, pady=20, sticky="s")

    def _create_dashboard_content(self):
        main = ctk.CTkFrame(self.container, fg_color="transparent")
        main.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(3, weight=1)

        bar = ctk.CTkFrame(main, fg_color=COLOR_CARD, height=60, corner_radius=10)
        bar.grid(row=0, column=0, sticky="ew", pady=(0, 20))
        self.lbl_actor = ctk.CTkLabel(bar, text="ACTIVE ACTOR: --", font=ctk.CTkFont(size=14, weight="bold"))
        self.lbl_actor.pack(side="left", padx=20, pady=15)
        self.lbl_timer = ctk.CTkLabel(bar, text="SESSION: 00:00:00", font=ctk.CTkFont(family="Consolas", size=14))
        self.lbl_timer.pack(side="right", padx=20, pady=15)

        grid = ctk.CTkFrame(main, fg_color="transparent")
        grid.grid(row=1, column=0, sticky="ew", pady=(0, 20))
        grid.grid_columnconfigure((0,1,2,3), weight=1)
        
        self.card_outreach = StatCard(grid, "Outreach Sent", color=COLOR_PRIMARY)
        self.card_outreach.grid(row=0, column=0, padx=(0, 10), sticky="ew")
        self.card_scraped = StatCard(grid, "Profiles Scraped", color="#8b5cf6")
        self.card_scraped.grid(row=0, column=1, padx=10, sticky="ew")
        self.card_enriched = StatCard(grid, "Leads Enriched", color=COLOR_SUCCESS)
        self.card_enriched.grid(row=0, column=2, padx=10, sticky="ew")
        self.card_safety = StatCard(grid, "Safety Alerts", color=COLOR_WARNING)
        self.card_safety.grid(row=0, column=3, padx=(10, 0), sticky="ew")

        self.feed_box = ctk.CTkTextbox(main, font=("Consolas", 12), activate_scrollbars=True)
        self.feed_box.grid(row=3, column=0, sticky="nsew")
        self.feed_box.configure(state="disabled")

    # --- SUPPORT ACTIONS ---

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
        self.btn_start.configure(state="disabled", fg_color=COLOR_CARD)
        self.btn_stop.configure(state="normal", fg_color=COLOR_DANGER)
        self.btn_sync.configure(state="normal")
        self.lbl_sync_status.configure(text="SYNC: STARTING...", text_color="#f59e0b")
        self.start_time = datetime.now()
        try:
            self.server = IPCServer()
            self.is_running = True
            self.server_thread = threading.Thread(target=self._run_server, daemon=True)
            self.server_thread.start()
        except Exception as e:
            messagebox.showerror("Startup Error", str(e))
            self.stop_service()

    def stop_service(self):
        if not self.is_running: return
        self.log_to_feed("Stopping services...", "SYSTEM")
        if self.server: threading.Thread(target=self.server.stop, daemon=True).start()
        self.is_running = False
        self.btn_start.configure(state="normal", fg_color=COLOR_SUCCESS)
        self.btn_stop.configure(state="disabled", fg_color=COLOR_CARD)
        self.btn_sync.configure(state="disabled")
        self.lbl_sync_status.configure(text="SYNC: --", text_color="#666666")
        self.lbl_actor.configure(text="ACTIVE ACTOR: --")
        self.lbl_timer.configure(text="SESSION: 00:00:00")

    def sync_now(self):
        if self.server and self.server.sync_engine:
            self.server.sync_engine.trigger_sync()
            self.lbl_sync_status.configure(text="SYNC: PUSHING...", text_color="#f59e0b")
            self.log_to_feed("Manual Sync Triggered", "SYNC")

    def _run_server(self):
        try: self.server.start()
        except Exception as e: print(f"[Fatal] {e}")
        finally: self.is_running = False

    def _session_monitor_loop(self):
        if self.is_running and self.start_time:
            delta = datetime.now() - self.start_time
            self.lbl_timer.configure(text=f"SESSION: {str(delta).split('.')[0]}")
            if self.server and self.server.session_state:
                actor = self.server.session_state.get("last_active_actor")
                if actor: self.lbl_actor.configure(text=f"ACTIVE ACTOR: @{actor.upper()}")
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
            self.card_outreach.update_value(self.metrics["outreach_sent"])
            self.log_to_feed("Outreach Sent", "OUTREACH")
        elif "Found contact info" in clean_line:
            self.metrics["leads_enriched"] += 1
            self.card_enriched.update_value(self.metrics["leads_enriched"])
            self.log_to_feed("Lead Enriched", "SUCCESS")
        elif "Blocked:" in clean_line:
            self.metrics["rules_triggered"] += 1
            self.card_safety.update_value(self.metrics["rules_triggered"])
            self.log_to_feed(f"Safety: {clean_line.split('Blocked: ')[-1]}", "ALERT")
        elif "[SYNC] Status: OK" in clean_line:
            ts = datetime.now().strftime("%H:%M")
            self.lbl_sync_status.configure(text=f"SYNC: OK ({ts})", text_color=COLOR_SUCCESS)
            self.log_to_feed("Cloud Sync Completed", "SYNC")
        elif "[SYNC] Status: Error" in clean_line:
            ts = datetime.now().strftime("%H:%M")
            self.lbl_sync_status.configure(text=f"SYNC: ERROR ({ts})", text_color=COLOR_DANGER)
            self.log_to_feed("Cloud Sync Failed", "ERROR")
        elif "Successfully synced" in clean_line:
            # Fallback for old log style if needed
            self.log_to_feed("Cloud Sync Completed", "SYNC")
        elif "[Auto]" in clean_line:
            self.log_to_feed(clean_line, "AUTO")

    def log_to_feed(self, message, type="INFO"):
        ts = datetime.now().strftime("%H:%M:%S")
        self.feed_box.configure(state="normal")
        self.feed_box.insert("0.0", f"[{ts}] [{type}] {message}\n")
        self.feed_box.configure(state="disabled")

    def on_closing(self):
        if self.is_running: self.stop_service()
        self.destroy()
        sys.exit(0)

if __name__ == "__main__":
    app = AppUI()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()

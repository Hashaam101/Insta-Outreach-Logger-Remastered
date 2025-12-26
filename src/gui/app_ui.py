import customtkinter as ctk
import threading
import sys
import queue
import os
import re
import subprocess
from tkinter import messagebox
from datetime import datetime
from PIL import Image
import json

# Adjust path to allow importing core modules
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.core.ipc_server import IPCServer
from src.core.version import __version__ as VERSION

# --- Theme and Appearance ---
def load_theme():
    theme_path = os.path.join(current_dir, "theme.json")
    if os.path.exists(theme_path):
        with open(theme_path, 'r') as f:
            return json.load(f)
    return None

theme_path = os.path.join(current_dir, "theme.json")
if os.path.exists(theme_path):
    ctk.set_appearance_mode("Dark")
    ctk.set_default_color_theme(theme_path)
else:
    ctk.set_appearance_mode("Dark")
    ctk.set_default_color_theme("blue")

class StdoutRedirector:
    """Intercepts stdout/stderr and pushes content to a queue."""
    def __init__(self, text_queue):
        self.text_queue = text_queue

    def write(self, string):
        if string:
            self.text_queue.put(string)

    def flush(self):
        pass

class AppUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Window Setup
        self.title(f"Insta Outreach Logger v{VERSION}")
        self.geometry("1200x750")
        
        # Set Window Icon
        icon_path = os.path.join(project_root, "assets", "logo.ico")
        if os.path.exists(icon_path):
            try:
                self.iconbitmap(icon_path)
            except Exception:
                pass 

        # --- State and Data ---
        self.server = None
        self.server_thread = None
        self.is_running = False
        self.log_queue = queue.Queue()
        
        self.stats = {
            "scraped": 0,
            "emails": 0,
            "phones": 0,
            "errors": 0
        }
        
        # --- UI Elements ---
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr
        sys.stdout = StdoutRedirector(self.log_queue)
        sys.stderr = StdoutRedirector(self.log_queue)

        self._create_sidebar()
        self._create_main_area()

        self.after(100, self._update_loop)

    def _create_sidebar(self):
        self.sidebar_frame = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, rowspan=4, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(5, weight=1)

        logo_path = os.path.join(project_root, "assets", "logo.png")
        if os.path.exists(logo_path):
            try:
                self.logo_image = ctk.CTkImage(light_image=Image.open(logo_path),
                                              dark_image=Image.open(logo_path),
                                              size=(100, 100))
                self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="", image=self.logo_image)
            except Exception as e:
                print(f"[GUI] Could not load logo: {e}")
                self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="Insta Outreach", font=ctk.CTkFont(size=24, weight="bold"))
        else:
            self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="Insta Outreach", font=ctk.CTkFont(size=24, weight="bold"))
        
        self.logo_label.grid(row=0, column=0, padx=20, pady=(30, 20))

        self.start_button = ctk.CTkButton(self.sidebar_frame, text="Start Service", command=self.start_service, fg_color="#10B981", hover_color="#059669", height=40, font=("Arial", 14, "bold"))
        self.start_button.grid(row=1, column=0, padx=20, pady=10)

        self.stop_button = ctk.CTkButton(self.sidebar_frame, text="Stop Service", command=self.stop_service, fg_color="#EF4444", hover_color="#DC2626", height=40, font=("Arial", 14, "bold"), state="disabled")
        self.stop_button.grid(row=2, column=0, padx=20, pady=10)
        
        self.sync_button = ctk.CTkButton(self.sidebar_frame, text="Sync Now", command=self.sync_now, height=35, state="disabled")
        self.sync_button.grid(row=3, column=0, padx=30, pady=10, sticky="ew")
        
        self.setup_button = ctk.CTkButton(self.sidebar_frame, text="Run Setup Wizard", command=self.run_setup_gui, fg_color="transparent", border_width=1, border_color="gray")
        self.setup_button.grid(row=5, column=0, padx=20, pady=(20, 10), sticky="s")

        self.uninstall_button = ctk.CTkButton(self.sidebar_frame, text="Uninstall", command=self.uninstall_app, fg_color="transparent", text_color="#F87171", hover_color="#374151")
        self.uninstall_button.grid(row=6, column=0, padx=20, pady=(10, 20), sticky="s")

        self.version_label = ctk.CTkLabel(self.sidebar_frame, text=f"v{VERSION}", text_color="gray")
        self.version_label.grid(row=7, column=0, padx=20, pady=10, sticky="s")

    def sync_now(self):
        if self.server and hasattr(self.server, 'sync_engine'):
            self.server.sync_engine.trigger_sync()
            print("[System] Manual sync triggered.")
        else:
            print("[System] Cannot sync: Server not running or sync engine unavailable.")

    def run_setup_gui(self):
        print("[System] Launching Setup Wizard...")
        try:
            setup_script = os.path.join(project_root, "src", "gui", "setup_wizard.py")
            if os.path.exists(setup_script):
                subprocess.Popen([sys.executable, setup_script])
            else:
                messagebox.showerror("Error", f"Setup script not found at:\n{setup_script}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to launch Setup Wizard: {e}")

    def uninstall_app(self):
        if messagebox.askyesno("Uninstall Confirmation", "Are you sure you want to uninstall? This will remove all application data and settings."):
            print("[System] Initiating uninstallation...")
            self.stop_service()
            
            uninstall_script = os.path.join(project_root, "uninstall.py")
            if os.path.exists(uninstall_script):
                try:
                    cmd = [sys.executable, uninstall_script]
                    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, text=True, creationflags=subprocess.CREATE_NEW_CONSOLE)
                    if p.stdin:
                        p.stdin.write("yes\n")
                        p.stdin.flush()
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to start uninstaller: {e}")
                    return

            self.destroy()
            sys.exit(0)

    def _create_main_area(self):
        self.main_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(1, weight=1)

        self.tab_view = ctk.CTkTabview(self.main_frame, anchor="nw")
        self.tab_view.grid(row=1, column=0, sticky="nsew")

        self.tab_view.add("Dashboard")
        self.tab_view.add("Raw Console")

        self._create_dashboard_tab()
        self._create_console_tab()

    def _create_dashboard_tab(self):
        dashboard = self.tab_view.tab("Dashboard")
        dashboard.grid_columnconfigure(0, weight=1)
        dashboard.grid_rowconfigure(3, weight=1)

        header_frame = ctk.CTkFrame(dashboard, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 20))
        header_frame.grid_columnconfigure(0, weight=1)

        title_label = ctk.CTkLabel(header_frame, text="Dashboard", font=ctk.CTkFont(size=28, weight="bold"), anchor="w")
        title_label.grid(row=0, column=0, sticky="w")
        
        self.status_label = ctk.CTkLabel(header_frame, text="Status: Ready", font=ctk.CTkFont(size=14), anchor="e", text_color="gray")
        self.status_label.grid(row=0, column=1, sticky="e", padx=10)

        self.stats_frame = ctk.CTkFrame(dashboard)
        self.stats_frame.grid(row=1, column=0, sticky="ew", pady=10)
        
        def create_stat_card(parent, title, key, col):
            frame = ctk.CTkFrame(parent, border_width=1)
            frame.grid(row=0, column=col, padx=10, pady=10, sticky="ew")
            parent.grid_columnconfigure(col, weight=1)
            
            lbl_title = ctk.CTkLabel(frame, text=title, font=ctk.CTkFont(size=14, weight="bold"), text_color="gray")
            lbl_title.pack(pady=(15, 5))
            
            lbl_value = ctk.CTkLabel(frame, text="0", font=ctk.CTkFont(size=36, weight="bold"))
            lbl_value.pack(pady=(0, 15))
            
            setattr(self, f"lbl_{key}", lbl_value)

        create_stat_card(self.stats_frame, "Profiles Scraped", "scraped", 0)
        create_stat_card(self.stats_frame, "Emails Found", "emails", 1)
        create_stat_card(self.stats_frame, "Phones Found", "phones", 2)
        create_stat_card(self.stats_frame, "Errors", "errors", 3)

        lbl_feed = ctk.CTkLabel(dashboard, text="Live Activity Feed", anchor="w", font=ctk.CTkFont(size=16, weight="bold"))
        lbl_feed.grid(row=2, column=0, pady=(20, 5), sticky="w")
        
        self.feed_box = ctk.CTkTextbox(dashboard, activate_scrollbars=True, border_width=1)
        self.feed_box.grid(row=3, column=0, sticky="nsew", pady=5)
        self.feed_box.configure(state="disabled")

    def _create_console_tab(self):
        console = self.tab_view.tab("Raw Console")
        console.grid_columnconfigure(0, weight=1)
        console.grid_rowconfigure(0, weight=1)

        self.console_box = ctk.CTkTextbox(console, font=("Consolas", 12), border_width=1)
        self.console_box.grid(row=0, column=0, sticky="nsew")
        self.console_box.configure(state="disabled")

    def start_service(self):
        if self.is_running: return
        print("[System] Starting services...")
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.sync_button.configure(state="normal")
        self.status_label.configure(text="Status: Starting...", text_color="yellow")

        try:
            self.server = IPCServer()
        except Exception as e:
            print(f"[Error] Failed to initialize server: {e}")
            self.status_label.configure(text=f"Error: {e}", text_color="#F87171")
            self.start_button.configure(state="normal")
            return

        self.is_running = True
        self.server_thread = threading.Thread(target=self._run_server_loop, daemon=True)
        self.server_thread.start()

    def _run_server_loop(self):
        try:
            if self.server:
                self._add_to_feed("System Started Successfully")
                self.server.start()
        except Exception as e:
            print(f"[Fatal] Server crashed: {e}")
        finally:
            self.is_running = False

    def stop_service(self):
        if not self.is_running or not self.server: return
        print("[System] Stopping services...")
        self.status_label.configure(text="Status: Stopping...", text_color="orange")
        self.stop_button.configure(state="disabled")
        threading.Thread(target=self._stop_server_bg, daemon=True).start()

    def _stop_server_bg(self):
        if self.server:
            self.server.stop()
        self.is_running = False
        print("[System] Services stopped.")

    def _update_stats_ui(self):
        self.lbl_scraped.configure(text=str(self.stats["scraped"]))
        self.lbl_emails.configure(text=str(self.stats["emails"]))
        self.lbl_phones.configure(text=str(self.stats["phones"]))
        self.lbl_errors.configure(text=str(self.stats["errors"]))

    def _add_to_feed(self, message):
        self.feed_box.configure(state="normal")
        self.feed_box.insert("0.0", f"[{datetime.now().strftime('%H:%M:%S')}] {message}\n")
        self.feed_box.configure(state="disabled")

    def _process_log_line(self, line):
        self.console_box.configure(state="normal")
        self.console_box.insert("end", line)
        self.console_box.see("end")
        self.console_box.configure(state="disabled")

        clean_line = line.strip()
        if not clean_line: return

        if "[Discovery]" in clean_line or "[IPC]" in clean_line:
             self.status_label.configure(text=f"Status: {clean_line[:80]}...", text_color="white")

        if "Queued outreach" in clean_line:
            self.stats["scraped"] += 1
            self._add_to_feed("New profile scraped from feed.")
            self._update_stats_ui()
        
        if "Found contact info" in clean_line:
            username = re.search(r"for (\w+):", clean_line)
            username = username.group(1) if username else "unknown"
            if "'email':" in clean_line and "'email': None" not in clean_line: self.stats["emails"] += 1
            if "'phone_number':" in clean_line and "'phone_number': None" not in clean_line: self.stats["phones"] += 1
            self._add_to_feed(f"Contact info found for {username}.")
            self._update_stats_ui()

        if "Error" in clean_line or "Exception" in clean_line or "[Fatal]" in clean_line:
            self.stats["errors"] += 1
            self._update_stats_ui()

        if "Services stopped" in clean_line:
            self.start_button.configure(state="normal")
            self.stop_button.configure(state="disabled")
            self.sync_button.configure(state="disabled")
            self.status_label.configure(text="Status: Stopped", text_color="gray")
            self._add_to_feed("System Services Stopped.")
            
        if "Queued" in clean_line and "for deletion" in clean_line:
            username = re.search(r"Queued (.*?) for deletion", clean_line)
            self._add_to_feed(f"Deleted Prospect: {username.group(1) if username else 'Unknown'}")

        if "Updating local status:" in clean_line:
            update = re.search(r"status: (.*)", clean_line)
            self._add_to_feed(f"Status Update: {update.group(1) if update else 'Unknown'}")

    def _update_loop(self):
        while not self.log_queue.empty():
            try:
                line = self.log_queue.get_nowait()
                self._process_log_line(line)
            except queue.Empty:
                break
        self.after(50, self._update_loop)

    def on_closing(self):
        if messagebox.askokcancel("Quit", "Do you want to quit? This will stop any running services."):
            print("[System] Closing application...")
            self.stop_service()
            self.destroy()
            sys.exit(0)

if __name__ == "__main__":
    app = AppUI()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()

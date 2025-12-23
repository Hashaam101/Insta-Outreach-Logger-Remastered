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

# Adjust path to allow importing core modules
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.core.ipc_server import IPCServer
from src.core.version import __version__ as VERSION

# Set default theme
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
        self.geometry("1100x700")
        
        # Set Window Icon
        icon_path = os.path.join(project_root, "assets", "logo.ico")
        if os.path.exists(icon_path):
            try:
                self.iconbitmap(icon_path)
            except Exception:
                pass # Fallback for non-windows or errors

        # Theme & Style
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
        
        # UI Elements (initialized later)
        self.lbl_scraped = None
        self.lbl_emails = None
        self.lbl_phones = None
        self.lbl_errors = None

        # --- Redirect Stdout/Stderr ---
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr
        sys.stdout = StdoutRedirector(self.log_queue)
        sys.stderr = StdoutRedirector(self.log_queue)

        # --- UI Initialization ---
        self._create_sidebar()
        self._create_main_area()

        # --- Periodic Update Loop ---
        self.after(100, self._update_loop)

    def _create_sidebar(self):
        self.sidebar_frame = ctk.CTkFrame(self, width=140, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, rowspan=4, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(4, weight=1)

        # Load Logo
        logo_path = os.path.join(project_root, "assets", "logo.png")
        if os.path.exists(logo_path):
            try:
                self.logo_image = ctk.CTkImage(light_image=Image.open(logo_path),
                                              dark_image=Image.open(logo_path),
                                              size=(80, 80))
                self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="", image=self.logo_image)
            except Exception as e:
                print(f"[GUI] Could not load logo: {e}")
                self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="Insta Outreach", font=ctk.CTkFont(size=20, weight="bold"))
        else:
            self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="Insta Outreach", font=ctk.CTkFont(size=20, weight="bold"))
        
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        self.start_button = ctk.CTkButton(self.sidebar_frame, text="Start Service", command=self.start_service, fg_color="green", hover_color="darkgreen")
        self.start_button.grid(row=1, column=0, padx=20, pady=10)

        self.stop_button = ctk.CTkButton(self.sidebar_frame, text="Stop Service", command=self.stop_service, fg_color="darkred", hover_color="maroon", state="disabled")
        self.stop_button.grid(row=2, column=0, padx=20, pady=10)
        
        self.sync_button = ctk.CTkButton(self.sidebar_frame, text="Sync Now", command=self.sync_now, fg_color="#1E40AF", hover_color="#1E3A8A", state="disabled")
        self.sync_button.grid(row=3, column=0, padx=20, pady=10)
        
        self.setup_button = ctk.CTkButton(self.sidebar_frame, text="Run Setup Wizard", command=self.run_setup_gui, fg_color="#444", hover_color="#333", text_color="#FFFFFF")
        self.setup_button.grid(row=4, column=0, padx=20, pady=(20, 10), sticky="s")

        self.uninstall_button = ctk.CTkButton(self.sidebar_frame, text="Uninstall", command=self.uninstall_app, fg_color="#444", hover_color="#333", text_color="#FF5555")
        self.uninstall_button.grid(row=5, column=0, padx=20, pady=10, sticky="s")

        # Version or Footer
        self.version_label = ctk.CTkLabel(self.sidebar_frame, text="v1.0", text_color="gray")
        self.version_label.grid(row=6, column=0, padx=20, pady=20)

    def sync_now(self):
        if self.server and self.server.sync_engine:
            self.server.sync_engine.trigger_sync()
            print("[System] Manual sync triggered.")
        else:
            print("[System] Cannot sync: Server not running.")

    def run_setup_gui(self):
        """Launches the Setup Wizard in a separate process."""
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
        if messagebox.askyesno("Uninstall", "Are you sure you want to completely remove the application and all data?"):
            print("[System] Initiating uninstallation...")
            self.stop_service()
            
            uninstall_script = os.path.join(project_root, "uninstall.py")
            if os.path.exists(uninstall_script):
                # Run uninstall.py in a new console, piping 'yes' to it
                try:
                    # We use Popen to fire and forget (mostly), but we pipe input
                    # Note: We can't easily fire-and-forget AND pipe input without logic.
                    # We'll construct a command that pipes echo yes | python uninstall.py
                    # OR just run it interactively? "Uninstall" implies nuking.
                    # Best: Run python uninstall.py and pass "yes" via stdin.
                    
                    cmd = [sys.executable, uninstall_script]
                    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, text=True, creationflags=subprocess.CREATE_NEW_CONSOLE)
                    if p.stdin:
                        p.stdin.write("yes\n")
                        p.stdin.flush()
                    # We don't wait(), we just close GUI
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to start uninstaller: {e}")
                    return

            self.destroy()
            sys.exit(0)

    def _create_main_area(self):
        # Tab View
        self.tab_view = ctk.CTkTabview(self, anchor="nw")
        self.tab_view.grid(row=0, column=1, padx=20, pady=10, sticky="nsew")

        self.tab_view.add("Dashboard")
        self.tab_view.add("Raw Console")

        # --- Dashboard Tab ---
        dashboard = self.tab_view.tab("Dashboard")
        dashboard.grid_columnconfigure(0, weight=1)
        dashboard.grid_rowconfigure(2, weight=1) # Feed takes remaining space

        # 1. Status Bar
        self.status_label = ctk.CTkLabel(dashboard, text="Status: Ready to start.", font=ctk.CTkFont(size=16), anchor="w")
        self.status_label.grid(row=0, column=0, padx=10, pady=(0, 20), sticky="ew")

        # 2. Stats Grid
        self.stats_frame = ctk.CTkFrame(dashboard)
        self.stats_frame.grid(row=1, column=0, padx=10, pady=10, sticky="ew")
        
        # Helper to create stat cards
        def create_stat_card(parent, title, key, col):
            frame = ctk.CTkFrame(parent)
            frame.grid(row=0, column=col, padx=10, pady=10, sticky="ew")
            parent.grid_columnconfigure(col, weight=1)
            
            lbl_title = ctk.CTkLabel(frame, text=title, font=ctk.CTkFont(size=12, weight="bold"), text_color="gray")
            lbl_title.pack(pady=(10, 0))
            
            lbl_value = ctk.CTkLabel(frame, text="0", font=ctk.CTkFont(size=24, weight="bold"))
            lbl_value.pack(pady=(5, 10))
            
            setattr(self, f"lbl_{key}", lbl_value)

        create_stat_card(self.stats_frame, "Profiles Scraped", "scraped", 0)
        create_stat_card(self.stats_frame, "Emails Found", "emails", 1)
        create_stat_card(self.stats_frame, "Phones Found", "phones", 2)
        create_stat_card(self.stats_frame, "Errors", "errors", 3)

        # 3. Live Activity Feed
        lbl_feed = ctk.CTkLabel(dashboard, text="Live Activity Feed", anchor="w", font=ctk.CTkFont(size=14, weight="bold"))
        lbl_feed.grid(row=2, column=0, padx=10, pady=(20, 5), sticky="w") # Label above list
        
        # Using a TextBox as a read-only list is more stable than dynamic labels for logs
        self.feed_box = ctk.CTkTextbox(dashboard, width=400, activate_scrollbars=True)
        self.feed_box.grid(row=3, column=0, padx=10, pady=5, sticky="nsew")
        self.feed_box.configure(state="disabled")

        # --- Raw Console Tab ---
        console = self.tab_view.tab("Raw Console")
        console.grid_columnconfigure(0, weight=1)
        console.grid_rowconfigure(0, weight=1)

        self.console_box = ctk.CTkTextbox(console, width=800, font=("Consolas", 12))
        self.console_box.grid(row=0, column=0, padx=0, pady=0, sticky="nsew")
        self.console_box.configure(state="disabled")

    def start_service(self):
        if self.is_running:
            return

        print("[System] Starting IPC Server...")
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.sync_button.configure(state="normal")
        self.status_label.configure(text="Status: Starting background services...", text_color="yellow")

        # Initialize Server
        try:
            self.server = IPCServer()
        except Exception as e:
            print(f"[Error] Failed to init server: {e}")
            self.status_label.configure(text=f"Error: {e}", text_color="red")
            self.start_button.configure(state="normal")
            return

        self.is_running = True
        self.server_thread = threading.Thread(target=self._run_server_loop, daemon=True)
        self.server_thread.start()

    def _run_server_loop(self):
        try:
            if self.server:
                self.server.start()
                self._add_to_feed("System Started")
        except Exception as e:
            print(f"[Fatal] Server crashed: {e}")
        finally:
            self.is_running = False
            # We can't update GUI directly from here safely, the loop will catch it via flags if needed
            # But the loop checks the queue.

    def stop_service(self):
        if not self.is_running or not self.server:
            return

        print("[System] Stopping services...")
        self.status_label.configure(text="Status: Stopping...", text_color="orange")
        self.stop_button.configure(state="disabled")
        
        # Stop in thread to avoid freezing GUI
        threading.Thread(target=self._stop_server_bg, daemon=True).start()

    def _stop_server_bg(self):
        if self.server:
            self.server.stop()
        self.is_running = False
        print("[System] Services stopped.")
        # Trigger UI update
        # We assume the main loop will handle re-enabling buttons or we do it via after/queue, 
        # but for simplicity we'll just log it. The next manual check or button state will be handled.
        # Actually, we should reset buttons. Since we are in a thread, we shouldn't touch GUI.
        # We'll rely on the log parsing or a simple recurring check.
        # Let's just re-enable start button via queue message or similar?
        # Simpler: The start_service disables start, stop_service disables stop.
        # We need to re-enable start when stopped.
        pass

    def _update_stats_ui(self):
        if self.lbl_scraped: self.lbl_scraped.configure(text=str(self.stats["scraped"]))
        if self.lbl_emails: self.lbl_emails.configure(text=str(self.stats["emails"]))
        if self.lbl_phones: self.lbl_phones.configure(text=str(self.stats["phones"]))
        if self.lbl_errors: self.lbl_errors.configure(text=str(self.stats["errors"]))

    def _add_to_feed(self, message):
        self.feed_box.configure(state="normal")
        self.feed_box.insert("0.0", f"{datetime.now().strftime('%H:%M:%S')} - {message}\n")
        self.feed_box.configure(state="disabled")

    def _process_log_line(self, line):
        # 1. Add to Console
        self.console_box.configure(state="normal")
        self.console_box.insert("end", line)
        self.console_box.see("end")
        self.console_box.configure(state="disabled")

        # 2. Parse for Stats & Feed
        clean_line = line.strip()
        if not clean_line:
            return

        # Update Status Bar logic
        if "[Discovery]" in clean_line or "[IPC]" in clean_line:
             # Just show the last significant log as status
             self.status_label.configure(text=f"Status: {clean_line[:60]}...", text_color="white")

        # Stats Logic
        if "Queued outreach" in clean_line:
            self.stats["scraped"] += 1
            self._add_to_feed("New Profile Scraped")
            self._update_stats_ui()
        
        if "Found contact info" in clean_line:
            # "[Discovery] Found contact info for username: {'email': ...}"
            if "'email':" in clean_line and "'email': None" not in clean_line:
                self.stats["emails"] += 1
            if "'phone_number':" in clean_line and "'phone_number': None" not in clean_line:
                self.stats["phones"] += 1
            
            username = clean_line.split('for ')[1].split(':')[0] if 'for ' in clean_line else "Unknown"
            self._add_to_feed(f"Enriched Profile! ({username})")
            self._update_stats_ui()

        if "Error" in clean_line or "Exception" in clean_line or "[Fatal]" in clean_line:
            self.stats["errors"] += 1
            self._update_stats_ui()

        if "Services stopped" in clean_line:
            self.start_button.configure(state="normal")
            self.stop_button.configure(state="disabled")
            self.sync_button.configure(state="disabled")
            self.status_label.configure(text="Status: Stopped", text_color="gray")
            self._add_to_feed("System Stopped")

        # Capture Deletions
        if "Queued" in clean_line and "for deletion" in clean_line:
            # [LocalDB] Queued {target_username} for deletion.
            try:
                parts = clean_line.split('Queued ')[1].split(' for')[0]
                self._add_to_feed(f"Deleted Prospect: {parts}")
            except:
                self._add_to_feed("Deleted Prospect")

        # Capture Status Updates
        if "Updating local status:" in clean_line:
            # [IPC] Updating local status: {target} ({old} -> {new})
            try:
                parts = clean_line.split('status: ')[1]
                self._add_to_feed(f"Status Update: {parts}")
            except:
                self._add_to_feed("Status Updated")

    def _update_loop(self):
        """Reads from the queue and updates the GUI."""
        while not self.log_queue.empty():
            try:
                line = self.log_queue.get_nowait()
                self._process_log_line(line)
            except queue.Empty:
                break
        
        # Schedule next check
        self.after(50, self._update_loop)

    def on_closing(self):
        print("Closing application...")
        self.stop_service()
        self.destroy()
        sys.exit(0)

if __name__ == "__main__":
    app = AppUI()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()

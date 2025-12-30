import customtkinter as ctk
import os
import json
import threading
from tkinter import messagebox
from src.core.version import __version__, __app_name__

class WelcomeWindow(ctk.CTk):
    """
    Main Dashboard/Welcome Window for the Launcher.
    Shows Operator Status, Checks for Updates, and allows launching the app.
    """
    def __init__(self, launcher, on_launch, on_reconfigure):
        super().__init__()
        
        self.launcher = launcher
        self.on_launch = on_launch
        self.on_reconfigure = on_reconfigure
        
        # Window Setup
        self.title(f"{__app_name__} - Dashboard")
        self.geometry("800x600")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.configure(fg_color="#0F0E13")
        
        # Center Window
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"+{x}+{y}")
        
        # Data
        self.operator_data = self._load_operator_data()
        self.update_available = False
        self.download_url = None
        
        # UI Layout
        self._create_header()
        self._create_content_area()
        self._create_footer()
        
        # Start Background Checks
        self.after(500, self._start_checks)

    def _load_operator_data(self):
        config_path = os.path.join(self.launcher.env_path, '..', 'operator_config.json')
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    return json.load(f)
            except: pass
        return {"operator_name": "Unknown", "operator_email": "Not Configured"}

    def _create_header(self):
        # Top Bar Background
        self.top_bar = ctk.CTkFrame(self, fg_color="#1a1b26", height=100, corner_radius=0)
        self.top_bar.pack(fill="x", pady=(0, 20))
        
        container = ctk.CTkFrame(self.top_bar, fg_color="transparent")
        container.pack(fill="x", padx=40, pady=25)

        # App Title & Version
        title_frame = ctk.CTkFrame(container, fg_color="transparent")
        title_frame.pack(side="left")
        
        ctk.CTkLabel(
            title_frame, 
            text=__app_name__.upper(), 
            font=ctk.CTkFont(family="Segoe UI", size=24, weight="bold"),
            text_color="#7C3AED" # Violet accent
        ).pack(anchor="w")
        
        ctk.CTkLabel(
            title_frame, 
            text=f"REMASTERED | v{__version__}", 
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#565f89"
        ).pack(anchor="w")

        # Operator Badge
        op_frame = ctk.CTkFrame(container, fg_color="#24283b", corner_radius=8, border_width=1, border_color="#414868")
        op_frame.pack(side="right", ipady=5)
        
        # User Icon
        icon_lbl = ctk.CTkLabel(op_frame, text="🦁", font=ctk.CTkFont(size=24))
        icon_lbl.pack(side="left", padx=(15, 10))
        
        info_frame = ctk.CTkFrame(op_frame, fg_color="transparent")
        info_frame.pack(side="left", padx=(0, 20))
        
        ctk.CTkLabel(
            info_frame, 
            text=self.operator_data.get('operator_name', 'Unknown').upper(), 
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color="#c0caf5"
        ).pack(anchor="w")
        
        ctk.CTkLabel(
            info_frame, 
            text=self.operator_data.get('operator_email', 'No Email'), 
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color="#565f89"
        ).pack(anchor="w")

    def _create_content_area(self):
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.pack(fill="both", expand=True, padx=40)
        
        # Grid System
        self.content.grid_columnconfigure(0, weight=2) # Main
        self.content.grid_columnconfigure(1, weight=1) # Side
        
        # --- LEFT COLUMN (MAIN ACTION) ---
        main_col = ctk.CTkFrame(self.content, fg_color="transparent")
        main_col.grid(row=0, column=0, sticky="nsew", padx=(0, 20))
        
        # Status Card (Cyberpunk style)
        self.status_card = ctk.CTkFrame(main_col, fg_color="#16161e", corner_radius=12, border_width=1, border_color="#7C3AED")
        self.status_card.pack(fill="x", pady=(0, 20), ipady=15)
        
        ctk.CTkLabel(
            self.status_card, 
            text="SYSTEM STATUS", 
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#565f89"
        ).pack(anchor="w", padx=20, pady=(10, 5))
        
        status_row = ctk.CTkFrame(self.status_card, fg_color="transparent")
        status_row.pack(fill="x", padx=20)
        
        self.status_indicator = ctk.CTkLabel(status_row, text="●", font=ctk.CTkFont(size=24), text_color="#22c55e")
        self.status_indicator.pack(side="left")
        
        self.status_label = ctk.CTkLabel(
            status_row, 
            text="Checking for updates...", 
            font=ctk.CTkFont(family="Segoe UI", size=16),
            text_color="#a9b1d6"
        )
        self.status_label.pack(side="left", padx=10)
        
        self.update_btn = ctk.CTkButton(
            status_row,
            text="UPDATE NOW",
            command=self._perform_update,
            fg_color="#f59e0b",
            hover_color="#d97706",
            width=120,
            font=ctk.CTkFont(weight="bold"),
            state="disabled"
        )
        # Hidden by default
        
        # Start Button (Hero)
        self.start_btn = ctk.CTkButton(
            main_col,
            text="INITIALIZE LOGGER",
            command=self._on_start_click,
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
            fg_color="#7C3AED",
            hover_color="#6D28D9",
            height=100,
            corner_radius=12,
            border_width=2,
            border_color="#8B5CF6"
        )
        self.start_btn.pack(fill="x", pady=0)
        
        # --- RIGHT COLUMN (TOOLS) ---
        side_col = ctk.CTkFrame(self.content, fg_color="transparent")
        side_col.grid(row=0, column=1, sticky="nsew")
        
        ctk.CTkLabel(
            side_col, 
            text="QUICK ACTIONS", 
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#565f89"
        ).pack(anchor="w", pady=(0, 10))
        
        # Reconfigure
        self._create_action_btn(side_col, "⚙️  Reconfigure", self._on_reconfig_click, "#24283b", "#414868")
        
        # Check Extension
        self._create_action_btn(side_col, "🧩  Extension ID", self._show_ext_info, "#24283b", "#414868")
        
        # Logs (Placeholder)
        self._create_action_btn(side_col, "📂  Open Logs", self._open_logs, "#24283b", "#414868")

    def _create_action_btn(self, parent, text, command, fg, hover):
        btn = ctk.CTkButton(
            parent,
            text=text,
            command=command,
            fg_color=fg,
            hover_color=hover,
            height=45,
            anchor="w",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            corner_radius=8
        )
        btn.pack(fill="x", pady=(0, 10))

    def _open_logs(self):
        log_dir = os.path.join(os.getcwd(), 'logs')
        if not os.path.exists(log_dir): os.makedirs(log_dir, exist_ok=True)
        os.startfile(log_dir)

    def _create_footer(self):
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(side="bottom", fill="x", padx=40, pady=20)
        
        ctk.CTkLabel(
            footer, 
            text="Insta Outreach Logger - Secure Environment", 
            font=ctk.CTkFont(family="Segoe UI", size=10), 
            text_color="#414868"
        ).pack(side="left")
        
        ctk.CTkLabel(
            footer, 
            text="Need help? Contact Admin.", 
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"), 
            text_color="#7C3AED",
            cursor="hand2"
        ).pack(side="right")

    def _start_checks(self):
        threading.Thread(target=self._check_updates_thread, daemon=True).start()

    def _check_updates_thread(self):
        try:
            update_avail, ver, url = self.launcher.check_for_updates()
            self.after(0, lambda: self._update_status(update_avail, ver, url))
        except Exception as e:
            self.after(0, lambda: self.status_label.configure(text=f"Update Check Failed: {e}", text_color="#ef4444"))

    def _update_status(self, avail, ver, url):
        if avail:
            self.status_label.configure(text=f"Update Available: v{ver}", text_color="#22c55e")
            self.update_btn.configure(state="normal")
            self.update_btn.pack(side="right", padx=20) # Show button
            self.download_url = url
            self.new_version = ver
            self.update_available = True
        else:
            self.status_label.configure(text="System is up to date", text_color="#4ade80")

    def _perform_update(self):
        if self.update_available and self.download_url:
            self.status_label.configure(text="Downloading update...", text_color="#f59e0b")
            self.update_btn.configure(state="disabled")
            
            # Run update in thread
            def run_update():
                path = self.launcher.download_update(self.download_url, self.new_version)
                if path:
                    self.launcher.apply_update(path)
                else:
                    self.after(0, lambda: self.status_label.configure(text="Update Failed", text_color="#ef4444"))
            
            threading.Thread(target=run_update, daemon=True).start()

    def _on_start_click(self):
        self.withdraw() # Hide immediately
        self.on_launch()
        self.after(200, self.destroy) # Delayed destroy to let animations finish

    def _on_reconfig_click(self):
        self.withdraw()
        self.on_reconfigure()
        self.after(200, self.destroy)

    def _show_ext_info(self):
        # Read Manifest for ID
        ext_id = "Unknown"
        try:
            mp = os.path.join(self.launcher.env_path, '..', 'src', 'core', 'com.instaoutreach.logger.json')
            if not os.path.exists(mp):
                 mp = os.path.join(self.launcher.env_path, '..', '_internal', 'src', 'core', 'com.instaoutreach.logger.json')
            
            if os.path.exists(mp):
                with open(mp, 'r') as f:
                    data = json.load(f)
                    origins = data.get('allowed_origins', [])
                    if origins:
                        ext_id = origins[0].replace("chrome-extension://", "").replace("/", "")
        except: pass
        
        messagebox.showinfo(
            "Extension Info",
            f"Expected Extension ID:\n{ext_id}\n\n"
            "Ensure this matches the ID in chrome://extensions.\n"
            "If not, run 'Reconfigure Setup'."
        )

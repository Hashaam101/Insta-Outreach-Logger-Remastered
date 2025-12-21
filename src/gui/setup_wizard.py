"""
Setup Wizard for Insta Outreach Logger.

This wizard handles first-time setup by accepting a Setup_Pack.zip file
containing the Oracle Wallet and local_config.py credentials.

Features:
- Clickable drop zone with drag & drop support
- Zip validation (checks for cwallet.sso and local_config.py)
- Help icons with instructions for each field
- Operator name autocomplete from database
- Automatic extraction to correct locations
"""

import customtkinter as ctk
import sys
import os
import zipfile
import json
import winreg
import tempfile
import threading
import re
import pyzipper
from tkinter import messagebox, filedialog
from src.core.security import get_zip_password

# Try to import tkinterdnd2 for drag and drop support
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    DND_AVAILABLE = True
except ImportError:
    DND_AVAILABLE = False

# --- Path Setup ---
if getattr(sys, 'frozen', False):
    # Running as compiled exe
    project_root = os.path.dirname(sys.executable)
else:
    # Running as script
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_dir, '../../'))

sys.path.insert(0, project_root)


class HelpTooltip:
    """A tooltip popup that appears when hovering a help icon."""

    # Track the currently active tooltip to prevent stacking
    active_tooltip = None

    def __init__(self, parent, text, title="Help"):
        self.parent = parent
        self.text = text
        self.title = title
        self.tooltip_window = None
        self.hide_job = None

    def on_enter(self, event=None):
        """Handle mouse enter."""
        # Cancel any pending hide for THIS tooltip
        self.cancel_hide()

        # If there is another tooltip open, close it immediately
        if HelpTooltip.active_tooltip and HelpTooltip.active_tooltip != self:
            HelpTooltip.active_tooltip.hide()

        self.show()

    def on_leave(self, event=None):
        """Handle mouse leave."""
        self.schedule_hide()

    def schedule_hide(self, event=None):
        """Schedule the tooltip to close after a short delay."""
        self.cancel_hide()
        self.hide_job = self.parent.after(200, self.hide)

    def cancel_hide(self):
        """Cancel any pending close operation."""
        if self.hide_job:
            self.parent.after_cancel(self.hide_job)
            self.hide_job = None

    def show(self, event=None):
        """Show the tooltip popup."""
        if self.tooltip_window:
            return

        # Set this as the active tooltip
        HelpTooltip.active_tooltip = self

        # Get position relative to parent window
        x = self.parent.winfo_rootx() + 35
        y = self.parent.winfo_rooty() - 5

        self.tooltip_window = ctk.CTkToplevel(self.parent)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.attributes("-topmost", True)
        self.tooltip_window.geometry(f"+{x}+{y}")
        self.tooltip_window.configure(fg_color="#1E1B2E")

        # Bind leave event on the tooltip itself so if user moves mouse over it and out, it closes
        self.tooltip_window.bind("<Leave>", self.on_leave)
        # Also bind Enter to cancel hide if user moves from button to tooltip
        self.tooltip_window.bind("<Enter>", self.on_enter)

        # Add border effect
        frame = ctk.CTkFrame(
            self.tooltip_window,
            fg_color="#1E1B2E",
            corner_radius=8,
            border_width=1,
            border_color="#4C4B63"
        )
        frame.pack(padx=1, pady=1)

        # Title
        title_label = ctk.CTkLabel(
            frame,
            text=self.title,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#ffffff"
        )
        title_label.pack(padx=15, pady=(10, 5), anchor="w")

        # Content
        content_label = ctk.CTkLabel(
            frame,
            text=self.text,
            font=ctk.CTkFont(size=11),
            text_color="#cccccc",
            justify="left",
            wraplength=300
        )
        content_label.pack(padx=15, pady=(0, 10), anchor="w")

    def hide(self, event=None):
        """Hide the tooltip popup."""
        self.cancel_hide()

        if self.tooltip_window:
            try:
                self.tooltip_window.destroy()
            except Exception:
                pass
            self.tooltip_window = None

        # Clear active tooltip reference if it's us
        if HelpTooltip.active_tooltip == self:
            HelpTooltip.active_tooltip = None


class OperatorAutocomplete(ctk.CTkFrame):
    """Custom autocomplete entry for operator names with database lookup."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)

        self.operators_list = []
        self.is_new_operator = True
        self.dropdown_visible = False

        # Main container with entry and indicator
        self.entry_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.entry_frame.pack(fill="x")

        # Entry field
        self.entry = ctk.CTkEntry(
            self.entry_frame,
            placeholder_text="Start typing to search...",
            height=35
        )
        self.entry.pack(side="left", fill="x", expand=True)

        # New operator indicator (+ icon)
        self.new_indicator = ctk.CTkLabel(
            self.entry_frame,
            text="",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#22c55e",
            width=30
        )
        self.new_indicator.pack(side="right", padx=(5, 0))

        # Dropdown frame (hidden by default)
        self.dropdown_frame = ctk.CTkFrame(
            self,
            fg_color="#1E1B2E",
            corner_radius=8,
            border_width=1,
            border_color="#4C4B63"
        )

        # Scrollable list for suggestions
        self.suggestions_frame = ctk.CTkScrollableFrame(
            self.dropdown_frame,
            fg_color="transparent",
            height=100
        )
        self.suggestions_frame.pack(fill="both", expand=True, padx=5, pady=5)

        # Bind events
        self.entry.bind("<KeyRelease>", self._on_key_release)
        self.entry.bind("<FocusOut>", self._on_focus_out)
        self.entry.bind("<FocusIn>", self._on_focus_in)

    def set_operators(self, operators):
        """Set the list of existing operators from database."""
        self.operators_list = sorted(set(operators))
        self._update_indicator()

    def get(self):
        """Get the current entry value."""
        return self.entry.get().strip()

    def configure(self, **kwargs):
        """Configure the entry widget."""
        if 'state' in kwargs:
            self.entry.configure(state=kwargs['state'])

    def _on_key_release(self, event=None):
        """Handle key release - filter suggestions."""
        text = self.entry.get().strip().lower()
        self._update_indicator()

        if not text or not self.operators_list:
            self._hide_dropdown()
            return

        # Filter matching operators
        matches = [op for op in self.operators_list if text in op.lower()]

        if matches and text:
            self._show_dropdown(matches[:5])  # Show max 5 suggestions
        else:
            self._hide_dropdown()

    def _on_focus_in(self, event=None):
        """Show dropdown when focused if there's text."""
        text = self.entry.get().strip()
        if text and self.operators_list:
            matches = [op for op in self.operators_list if text.lower() in op.lower()]
            if matches:
                self._show_dropdown(matches[:5])

    def _on_focus_out(self, event=None):
        """Hide dropdown when focus is lost (with small delay for click handling)."""
        self.after(200, self._hide_dropdown)

    def _show_dropdown(self, matches):
        """Show the dropdown with matching suggestions."""
        # Clear existing suggestions
        for widget in self.suggestions_frame.winfo_children():
            widget.destroy()

        # Add new suggestions
        for operator in matches:
            btn = ctk.CTkButton(
                self.suggestions_frame,
                text=operator,
                fg_color="transparent",
                hover_color="#4C4B63",
                anchor="w",
                height=30,
                command=lambda op=operator: self._select_operator(op)
            )
            btn.pack(fill="x", pady=1)

        # Show dropdown
        if not self.dropdown_visible:
            self.dropdown_frame.pack(fill="x", pady=(5, 0))
            self.dropdown_visible = True

    def _hide_dropdown(self):
        """Hide the dropdown."""
        if self.dropdown_visible:
            self.dropdown_frame.pack_forget()
            self.dropdown_visible = False

    def _select_operator(self, operator):
        """Select an operator from the dropdown."""
        self.entry.delete(0, "end")
        self.entry.insert(0, operator)
        self._hide_dropdown()
        self._update_indicator()

    def _update_indicator(self):
        """Update the new operator indicator."""
        text = self.entry.get().strip()

        if not text:
            self.new_indicator.configure(text="")
            self.is_new_operator = True
        elif text in self.operators_list:
            self.new_indicator.configure(text="", text_color="#22c55e")
            self.is_new_operator = False
        else:
            self.new_indicator.configure(text="+", text_color="#22c55e")
            self.is_new_operator = True


class SetupWizard(ctk.CTk if not DND_AVAILABLE else TkinterDnD.Tk):
    """
    Setup Wizard GUI for first-time configuration.
    Accepts a Setup_Pack.zip and extracts credentials to the correct locations.
    """

    def __init__(self):
        super().__init__()

        # Configure customtkinter appearance
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Set background color (handle difference between ctk.CTk and TkinterDnD.Tk)
        if DND_AVAILABLE:
            self.configure(bg="#0F0E13")
        else:
            self.configure(fg_color="#0F0E13")

        self.title("Insta Outreach Logger - Setup Wizard")
        self.geometry("600x580")
        self.resizable(False, False)

        # Flag to track if window is closing (prevents after() callback errors)
        self._is_closing = False

        # Center the window
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"+{x}+{y}")

        # Set icon if available
        icon_path = os.path.join(project_root, "assets", "logo.ico")
        if os.path.exists(icon_path):
            self.iconbitmap(icon_path)

        # State
        self.selected_file = None
        self.temp_config_path = None
        self.operators_loaded = False

        # --- UI Elements ---
        self._create_main_container()
        self._create_header()
        self._create_drop_zone()
        self._create_status_area()
        self._create_extension_id_input()
        self._create_operator_input()
        self._create_buttons()

        # Setup drag and drop if available
        if DND_AVAILABLE:
            self._setup_drag_and_drop()

        # Check for existing valid configuration
        self._check_existing_files()

    def _check_existing_files(self):
        """Check if valid setup files already exist and update UI."""
        config_path = os.path.join(project_root, 'local_config.py')
        wallet_path = os.path.join(project_root, 'assets', 'wallet', 'cwallet.sso')

        if os.path.exists(config_path) and os.path.exists(wallet_path):
            self._show_status("Existing configuration found!", "success")
            self.main_text_label.configure(text="System Configured")
            self.subtext_label.configure(text="You can drop a new Setup_Pack.zip to overwrite")
            self.click_frame.configure(border_color="#22c55e") # Green border
            
            # Load operators from existing config if possible
            try:
                # We can try to load operators using the existing config
                # This mirrors _load_operators_from_zip but uses local files
                self.db_status_label.configure(text="Loading operators...", text_color="#f59e0b")
                threading.Thread(target=self._fetch_operators_from_local, daemon=True).start()
            except Exception as e:
                print(f"[Setup] Could not load operators from existing config: {e}")

    def _fetch_operators_from_local(self):
        """Background thread to fetch operators using existing local config."""
        operators = []
        error_msg = None
        try:
             # Add project root to path to import local_config
            if project_root not in sys.path:
                sys.path.insert(0, project_root)
                
            import local_config
            import oracledb
            
            wallet_dir = os.path.join(project_root, 'assets', 'wallet')
            
            connection = oracledb.connect(
                user=local_config.DB_USER,
                password=local_config.DB_PASSWORD,
                dsn=local_config.DB_DSN,
                config_dir=wallet_dir
            )

            cursor = connection.cursor()
            cursor.execute("SELECT DISTINCT OWNER_OPERATOR FROM ACTORS WHERE OWNER_OPERATOR IS NOT NULL")
            rows = cursor.fetchall()
            operators = [row[0] for row in rows if row[0]]

            cursor.close()
            connection.close()
            
        except Exception as e:
            error_msg = str(e)
            print(f"[Setup] Error loading local operators: {e}")
            
        self.after(0, lambda: self._update_operators_ui(operators, error_msg))

    def _create_main_container(self):
        """Create the main scrollable container."""
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.pack(fill="both", expand=True, padx=30, pady=20)

    def _create_header(self):
        """Create the header section."""
        header_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 15))

        title_label = ctk.CTkLabel(
            header_frame,
            text="Welcome to Insta Outreach Logger",
            font=ctk.CTkFont(size=24, weight="bold")
        )
        title_label.pack()

        subtitle_label = ctk.CTkLabel(
            header_frame,
            text="Let's set up your credentials",
            font=ctk.CTkFont(size=14),
            text_color="gray"
        )
        subtitle_label.pack(pady=(5, 0))

    def _create_drop_zone(self):
        """Create the drop zone for file selection with proper spacing."""
        # Container for drop zone
        self.drop_container = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.drop_container.pack(fill="x", pady=(0, 10))

        # Main drop zone frame with dashed border effect
        self.click_frame = ctk.CTkFrame(
            self.drop_container,
            fg_color="#13111C",
            corner_radius=12,
            border_width=2,
            border_color="#4C4B63",
            height=140
        )
        self.click_frame.pack(fill="x")
        self.click_frame.pack_propagate(False)  # Maintain fixed height

        # Center content container
        center_container = ctk.CTkFrame(self.click_frame, fg_color="transparent")
        center_container.place(relx=0.5, rely=0.5, anchor="center")

        # Icon
        self.icon_label = ctk.CTkLabel(
            center_container,
            text="📁",
            font=ctk.CTkFont(size=40)
        )
        self.icon_label.pack(pady=(0, 8))

        # Main instruction text
        self.main_text_label = ctk.CTkLabel(
            center_container,
            text="Drop Setup_Pack.zip here or click to browse",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#aaaaaa"
        )
        self.main_text_label.pack(pady=(0, 4))

        # Subtext
        dnd_text = "Drag & drop supported" if DND_AVAILABLE else "Click to select file"
        self.subtext_label = ctk.CTkLabel(
            center_container,
            text=dnd_text,
            font=ctk.CTkFont(size=11),
            text_color="#666666"
        )
        self.subtext_label.pack()

        # Bind click events
        for widget in [self.click_frame, center_container, self.icon_label,
                       self.main_text_label, self.subtext_label]:
            widget.bind("<Button-1>", self._on_click_zone)
            widget.configure(cursor="hand2")

    def _setup_drag_and_drop(self):
        """Setup drag and drop functionality."""
        self.click_frame.drop_target_register(DND_FILES)
        self.click_frame.dnd_bind('<<Drop>>', self._on_drop)
        self.click_frame.dnd_bind('<<DragEnter>>', self._on_drag_enter)
        self.click_frame.dnd_bind('<<DragLeave>>', self._on_drag_leave)

    def _on_drop(self, event):
        """Handle file drop."""
        # Get the dropped file path
        file_path = event.data
        # Clean up path (remove braces on Windows)
        if file_path.startswith('{') and file_path.endswith('}'):
            file_path = file_path[1:-1]

        self._on_drag_leave(event)  # Reset visual state

        if file_path:
            self._select_file(file_path)

    def _on_drag_enter(self, event):
        """Visual feedback when dragging over drop zone."""
        self.click_frame.configure(border_color="#7C3AED", fg_color="#1E1B2E")
        self.main_text_label.configure(text="Drop here!")

    def _on_drag_leave(self, event):
        """Reset visual feedback when drag leaves."""
        if not self.selected_file:
            self.click_frame.configure(border_color="#4C4B63", fg_color="#13111C")
            self.main_text_label.configure(text="Drop Setup_Pack.zip here or click to browse")

    def _on_click_zone(self, event=None):
        """Handle click on the drop zone - open file dialog."""
        self._open_file_dialog()

    def _open_file_dialog(self):
        """Open file browser dialog."""
        file_path = filedialog.askopenfilename(
            title="Select Setup_Pack.zip",
            filetypes=[("Zip Files", "*.zip"), ("All files", "*.*")]
        )
        if file_path:
            self._select_file(file_path)

    def _create_status_area(self):
        """Create the status display area."""
        self.status_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.status_frame.pack(fill="x", pady=(0, 15))

        self.status_label = ctk.CTkLabel(
            self.status_frame,
            text="",
            font=ctk.CTkFont(size=12),
            text_color="#888888"
        )
        self.status_label.pack()

        self.file_label = ctk.CTkLabel(
            self.status_frame,
            text="",
            font=ctk.CTkFont(size=11),
            text_color="#666666"
        )
        self.file_label.pack()

    def _create_help_button(self, parent, tooltip_text, tooltip_title="Help"):
        """Create a help icon button with tooltip."""
        help_btn = ctk.CTkButton(
            parent,
            text="i",
            width=24,
            height=24,
            corner_radius=12,
            fg_color="#2D2B40",
            hover_color="#4C4B63",
            font=ctk.CTkFont(family="Times New Roman", size=14, weight="bold", slant="italic")
        )

        tooltip = HelpTooltip(help_btn, tooltip_text, tooltip_title)
        help_btn.bind("<Enter>", tooltip.on_enter)
        help_btn.bind("<Leave>", tooltip.on_leave)

        return help_btn

    def _create_extension_id_input(self):
        """Create input field for Extension ID with help icon."""
        self.id_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.id_frame.pack(fill="x", pady=(0, 15))

        # Label row with help icon
        label_row = ctk.CTkFrame(self.id_frame, fg_color="transparent")
        label_row.pack(fill="x")

        label = ctk.CTkLabel(
            label_row,
            text="Chrome Extension ID",
            font=ctk.CTkFont(size=13, weight="bold")
        )
        label.pack(side="left")

        help_btn = self._create_help_button(
            label_row,
            "How to find your Extension ID:\n\n"
            "1. Open Chrome and go to:\n"
            "   chrome://extensions/\n\n"
            "2. Enable 'Developer mode' (top right)\n\n"
            "3. Find 'Insta Outreach Logger'\n\n"
            "4. Copy the 32-character ID shown\n"
            "   (e.g., abcdefghijklmnopqrstuvwxyz123456)",
            "Extension ID"
        )
        help_btn.pack(side="left", padx=(8, 0))

        self.extension_id_entry = ctk.CTkEntry(
            self.id_frame,
            placeholder_text="e.g., abcdefghijklmnopqrstuvwxyz123456",
            height=35
        )
        self.extension_id_entry.pack(fill="x", pady=(8, 0))

    def _create_operator_input(self):
        """Create input field for Operator Name with autocomplete and help icon."""
        self.operator_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.operator_frame.pack(fill="x", pady=(0, 15))

        # Label row with help icon
        label_row = ctk.CTkFrame(self.operator_frame, fg_color="transparent")
        label_row.pack(fill="x")

        label = ctk.CTkLabel(
            label_row,
            text="Your Name (Operator)",
            font=ctk.CTkFont(size=13, weight="bold")
        )
        label.pack(side="left")

        help_btn = self._create_help_button(
            label_row,
            "What is an Operator?\n\n"
            "The operator is the person (you!) who is\n"
            "running this outreach tool.\n\n"
            "This helps track which team member sent\n"
            "each message in shared accounts.\n\n"
            "If your name appears in the suggestions,\n"
            "click to select it. Otherwise, type your\n"
            "name and a '+' will indicate you're being\n"
            "added as a new operator.",
            "Operator Name"
        )
        help_btn.pack(side="left", padx=(8, 0))

        # Status indicator for database connection
        self.db_status_label = ctk.CTkLabel(
            label_row,
            text="",
            font=ctk.CTkFont(size=10),
            text_color="#666666"
        )
        self.db_status_label.pack(side="right")

        # Autocomplete entry
        self.operator_autocomplete = OperatorAutocomplete(self.operator_frame)
        self.operator_autocomplete.pack(fill="x", pady=(8, 0))

    def _create_buttons(self):
        """Create the button area."""
        button_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        button_frame.pack(fill="x", pady=(10, 0))

        # Center the buttons
        button_container = ctk.CTkFrame(button_frame, fg_color="transparent")
        button_container.pack()

        self.browse_button = ctk.CTkButton(
            button_container,
            text="Browse...",
            command=self._open_file_dialog,
            width=140,
            height=42,
            fg_color="#2D2B40",
            hover_color="#4C4B63",
            font=ctk.CTkFont(size=13)
        )
        self.browse_button.pack(side="left", padx=(0, 15))

        self.install_button = ctk.CTkButton(
            button_container,
            text="Install",
            command=self._install,
            width=140,
            height=42,
            state="disabled",
            text_color="white",
            fg_color="#7C3AED",
            hover_color="#6D28D9",
            font=ctk.CTkFont(size=13, weight="bold")
        )
        self.install_button.pack(side="left")

    def _select_file(self, file_path):
        """Validate and select a file."""
        if not os.path.isfile(file_path):
            self._show_status("File not found", "error")
            return

        if not file_path.lower().endswith('.zip'):
            self._show_status("Please select a .zip file", "error")
            return

        # Validate zip contents
        is_valid, message = self._validate_zip(file_path)

        if is_valid:
            self.selected_file = file_path
            self._show_status("Valid Setup Pack detected!", "success")
            self.file_label.configure(text=os.path.basename(file_path))
            self.main_text_label.configure(text="Setup Pack ready!")
            self.icon_label.configure(text="")
            self.click_frame.configure(border_color="#22c55e")
            self.install_button.configure(state="normal")

            # Try to load operators from database
            self._load_operators_from_zip(file_path)
        else:
            self.selected_file = None
            self._show_status(message, "error")
            self.file_label.configure(text="")
            self.main_text_label.configure(text="Drop Setup_Pack.zip here or click to browse")
            self.icon_label.configure(text="")
            self.click_frame.configure(border_color="#ef4444")
            self.install_button.configure(state="disabled")

    def _get_zip_password_from_filename(self, zip_path):
        """Extract token from filename and derive password."""
        filename = os.path.basename(zip_path)
        # Match Setup_Pack_<token>.zip
        match = re.search(r'Setup_Pack_([a-fA-F0-9]+)\.zip', filename)
        
        if match:
            token = match.group(1)
            return get_zip_password(token)
        return None

    def _validate_zip(self, zip_path):
        """
        Validate the zip file contains required files.
        Returns (is_valid, message).
        """
        required_files = {
            'cwallet.sso': False,
            'local_config.py': False
        }

        try:
            # Check for signed package first
            password = self._get_zip_password_from_filename(zip_path)
            
            # Open with pyzipper to support AES
            with pyzipper.AESZipFile(zip_path, 'r') as zf:
                if password:
                    zf.setpassword(password)
                
                file_list = zf.namelist()
                
                # Verify we can actually read the encrypted files (test first file)
                if password:
                    try:
                        zf.read(file_list[0])
                    except RuntimeError:
                        return False, "Invalid Security Token (Decryption Failed)"

                for file_name in file_list:
                    base_name = os.path.basename(file_name)
                    if base_name in required_files:
                        required_files[base_name] = True

                missing = [f for f, found in required_files.items() if not found]

                if missing:
                    return False, f"Missing required files: {', '.join(missing)}"

                return True, "Valid Secure Package"

        except zipfile.BadZipFile:
            return False, "Invalid or corrupted zip file"
        except Exception as e:
            return False, f"Error reading zip: {str(e)}"

    def _load_operators_from_zip(self, zip_path):
        """Extract config temporarily and load operators from database."""
        self.db_status_label.configure(text="Loading operators...", text_color="#f59e0b")
        self.update()

        # Run in background thread to avoid blocking UI
        thread = threading.Thread(target=self._fetch_operators_thread, args=(zip_path,))
        thread.daemon = True
        thread.start()

    def _fetch_operators_thread(self, zip_path):
        """Background thread to fetch operators from database."""
        operators = []
        error_msg = None

        try:
            # Create temp directory for extraction
            temp_dir = tempfile.mkdtemp(prefix="insta_setup_")
            temp_wallet_dir = os.path.join(temp_dir, "wallet")
            os.makedirs(temp_wallet_dir, exist_ok=True)

            # Get password
            password = self._get_zip_password_from_filename(zip_path)

            # Extract needed files
            with pyzipper.AESZipFile(zip_path, 'r') as zf:
                if password:
                    zf.setpassword(password)
                    
                for file_info in zf.infolist():
                    base_name = os.path.basename(file_info.filename)
                    if base_name == 'local_config.py':
                        # Extract to temp dir
                        content = zf.read(file_info.filename)
                        config_path = os.path.join(temp_dir, 'local_config.py')
                        with open(config_path, 'wb') as f:
                            f.write(content)
                    elif base_name in ['cwallet.sso', 'tnsnames.ora', 'sqlnet.ora', 'ewallet.pem', 'ewallet.p12']:
                        content = zf.read(file_info.filename)
                        with open(os.path.join(temp_wallet_dir, base_name), 'wb') as f:
                            f.write(content)

            # Try to load config and connect to database
            import importlib.util
            spec = importlib.util.spec_from_file_location("temp_config", config_path)
            temp_config = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(temp_config)

            # Connect to Oracle and fetch operators
            import oracledb
            connection = oracledb.connect(
                user=temp_config.DB_USER,
                password=temp_config.DB_PASSWORD,
                dsn=temp_config.DB_DSN,
                config_dir=temp_wallet_dir
            )

            cursor = connection.cursor()
            cursor.execute("SELECT DISTINCT OWNER_OPERATOR FROM ACTORS WHERE OWNER_OPERATOR IS NOT NULL")
            rows = cursor.fetchall()
            operators = [row[0] for row in rows if row[0]]

            cursor.close()
            connection.close()

            # Cleanup temp files
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)

        except Exception as e:
            error_msg = str(e)
            print(f"[Setup] Could not load operators: {e}")

        # Update UI on main thread
        self.after(0, lambda: self._update_operators_ui(operators, error_msg))

    def _update_operators_ui(self, operators, error_msg):
        """Update the UI with loaded operators."""
        if operators:
            self.operator_autocomplete.set_operators(operators)
            self.db_status_label.configure(
                text=f"{len(operators)} operators found",
                text_color="#22c55e"
            )
            self.operators_loaded = True
        elif error_msg:
            self.db_status_label.configure(
                text="Could not load operators",
                text_color="#ef4444"
            )
        else:
            self.db_status_label.configure(
                text="No existing operators",
                text_color="#666666"
            )

    def _show_status(self, message, status_type="info"):
        """Update status label with appropriate styling."""
        colors = {
            "info": "#888888",
            "success": "#22c55e",
            "error": "#ef4444",
            "warning": "#f59e0b"
        }
        self.status_label.configure(text=message, text_color=colors.get(status_type, "#888888"))

    def _cancel_all_after_callbacks(self):
        """Cancel all pending after() callbacks to prevent Tcl errors on window close."""
        try:
            # Get all pending after events from Tcl and cancel them
            after_ids = self.tk.call('after', 'info')
            for after_id in after_ids:
                try:
                    self.after_cancel(after_id)
                except Exception:
                    pass
        except Exception:
            pass

    def _safe_destroy(self):
        """Safely destroy the window by canceling all pending callbacks first."""
        self._is_closing = True
        self._cancel_all_after_callbacks()

        try:
            # Withdraw window first to hide it immediately
            self.withdraw()
        except Exception:
            pass

        try:
            # Quit the mainloop - this allows mainloop() to return
            self.quit()
        except Exception:
            pass

        # Note: We intentionally don't call destroy() here.
        # The window will be garbage collected when the function returns.
        # Calling destroy() after quit() can corrupt the Tcl interpreter state.

    def _register_native_host(self, extension_id):
        """
        Registers the Native Messaging Host with Chrome.
        1. Creates com.instaoutreach.logger.json manifest
        2. Writes registry key pointing to it
        """
        try:
            # Determine path to bridge.bat
            # Check multiple locations to handle PyInstaller _internal folder changes
            possible_paths = [
                os.path.join(project_root, 'src', 'core', 'bridge.bat'),             # Standard / Dev
                os.path.join(project_root, '_internal', 'src', 'core', 'bridge.bat') # PyInstaller 6+ One-Folder
            ]

            bridge_path = None
            for p in possible_paths:
                if os.path.exists(p):
                    bridge_path = os.path.abspath(p)
                    break

            if not bridge_path:
                raise FileNotFoundError(f"bridge.bat not found. Checked: {possible_paths}")

            # Manifest path (save it alongside the bridge script)
            manifest_path = os.path.join(os.path.dirname(bridge_path), 'com.instaoutreach.logger.json')

            # Create the manifest content
            manifest_content = {
                "name": "com.instaoutreach.logger",
                "description": "Insta Outreach Logger Native Host",
                "path": bridge_path,
                "type": "stdio",
                "allowed_origins": [
                    f"chrome-extension://{extension_id}/"
                ]
            }

            # Write manifest file
            with open(manifest_path, 'w') as f:
                json.dump(manifest_content, f, indent=4)
            print(f"[Setup] Created manifest: {manifest_path}")

            # Register in Windows Registry
            # HKCU\Software\Google\Chrome\NativeMessagingHosts\com.instaoutreach.logger
            reg_path = r"Software\Google\Chrome\NativeMessagingHosts\com.instaoutreach.logger"

            try:
                # Create/Open key
                key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, reg_path)
                # Set default value to manifest path
                winreg.SetValueEx(key, "", 0, winreg.REG_SZ, manifest_path)
                winreg.CloseKey(key)
                print(f"[Setup] Registered Native Host in Registry: {reg_path}")
            except Exception as e:
                raise Exception(f"Failed to write registry key: {e}")

            return True

        except Exception as e:
            print(f"[Setup] Error registering native host: {e}")
            raise

    def _install(self):
        """Install by moving the Secure Setup Pack to the Documents secrets folder."""
        if not self.selected_file:
            return

        # Validate Extension ID
        ext_id = self.extension_id_entry.get().strip()
        if not ext_id or len(ext_id) != 32:
            messagebox.showerror(
                "Setup Error",
                "Please enter a valid 32-character Chrome Extension ID.\n\n"
                "You can find this at chrome://extensions/ after loading the extension."
            )
            return

        # Validate Operator Name
        operator_name = self.operator_autocomplete.get()
        if not operator_name:
            messagebox.showerror("Setup Error", "Please enter your Name (Operator).")
            return

        self._show_status("Installing...", "info")
        self.install_button.configure(state="disabled")
        self.browse_button.configure(state="disabled")
        self.extension_id_entry.configure(state="disabled")
        self.operator_autocomplete.configure(state="disabled")
        self.update()

        try:
            # 1. Prepare Destination
            import shutil
            docs_dir = os.path.join(os.path.expanduser("~"), "Documents")
            secrets_dir = os.path.join(docs_dir, "Insta Logger Remastered", "secrets")
            os.makedirs(secrets_dir, exist_ok=True)
            
            # Clean existing secrets to avoid confusion
            for f in os.listdir(secrets_dir):
                if f.startswith("Setup_Pack_") and f.endswith(".zip"):
                    try:
                        os.remove(os.path.join(secrets_dir, f))
                    except Exception:
                        pass
            
            # 2. Copy the Secure Pack
            filename = os.path.basename(self.selected_file)
            dest_path = os.path.join(secrets_dir, filename)
            shutil.copy2(self.selected_file, dest_path)
            print(f"[Setup] Secure Pack installed to: {dest_path}")

            # 3. Save Operator Config
            config_path = os.path.join(project_root, 'operator_config.json')
            with open(config_path, 'w') as f:
                json.dump({
                    'operator_name': operator_name,
                    'is_new': self.operator_autocomplete.is_new_operator
                }, f)
            print(f"[Setup] Saved Operator Name: {operator_name}")

            # 4. Register Native Messaging Host
            self._show_status("Registering Native Host...", "info")
            self._register_native_host(ext_id)

            self._show_status("Setup complete! Launching application...", "success")
            self.update()

            messagebox.showinfo(
                "Setup Complete",
                "Secure Configuration Installed!\n\n"
                "The application will now start.\n"
                "Your secrets are safely stored in Documents."
            )

            # Close wizard and signal success
            self._safe_destroy()
            return True

        except Exception as e:
            self._show_status(f"Installation failed: {str(e)}", "error")
            self.install_button.configure(state="normal")
            self.browse_button.configure(state="normal")
            self.extension_id_entry.configure(state="normal")
            self.operator_autocomplete.configure(state="normal")
            messagebox.showerror("Installation Error", f"Failed to install:\n{str(e)}")
            return False


def run_setup_wizard():
    """Run the setup wizard and return True if setup was successful."""
    app = SetupWizard()
    app.mainloop()

    # Explicitly destroy and clean up to reset Tcl interpreter state
    try:
        app.destroy()
    except Exception:
        pass

    # Force cleanup of the app reference
    del app

    # Reset Tkinter's internal state by creating and destroying a temporary root
    # This ensures subsequent Tkinter operations work correctly
    try:
        import tkinter as tk
        temp_root = tk.Tk()
        temp_root.withdraw()
        temp_root.destroy()
        del temp_root
    except Exception:
        pass

    # Check if setup was successful by verifying files exist
    config_path = os.path.join(project_root, 'local_config.py')
    wallet_path = os.path.join(project_root, 'assets', 'wallet', 'cwallet.sso')

    return os.path.exists(config_path) and os.path.exists(wallet_path)


if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    success = run_setup_wizard()
    print(f"[Setup] Wizard completed. Success: {success}")

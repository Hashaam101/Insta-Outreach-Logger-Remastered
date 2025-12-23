"""
Setup Wizard for Insta Outreach Logger.

This wizard handles first-time setup by accepting a Setup_Pack.zip file
containing the Oracle Wallet and local_config.py credentials.

Features:
- Sequential setup flow (Steps 1-4)
- Secure token validation
- Automated extension deployment to Documents
- Operator discovery and registration
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


class OperatorAutocomplete(ctk.CTkFrame):
    """Custom autocomplete entry for operator names with database lookup."""
    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.operators_list = []
        self.is_new_operator = True
        self.dropdown_visible = False
        self.entry_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.entry_frame.pack(fill="x")
        self.entry = ctk.CTkEntry(self.entry_frame, placeholder_text="Start typing to search...", height=35)
        self.entry.pack(side="left", fill="x", expand=True)
        self.new_indicator = ctk.CTkLabel(self.entry_frame, text="", font=ctk.CTkFont(size=16, weight="bold"), text_color="#22c55e", width=30)
        self.new_indicator.pack(side="right", padx=(5, 0))
        self.dropdown_frame = ctk.CTkFrame(self, fg_color="#1E1B2E", corner_radius=8, border_width=1, border_color="#4C4B63")
        self.suggestions_frame = ctk.CTkScrollableFrame(self.dropdown_frame, fg_color="transparent", height=100)
        self.suggestions_frame.pack(fill="both", expand=True, padx=5, pady=5)
        self.entry.bind("<KeyRelease>", self._on_key_release)
        self.entry.bind("<FocusOut>", self._on_focus_out)
        self.entry.bind("<FocusIn>", self._on_focus_in)

    def set_operators(self, operators):
        self.operators_list = sorted(set(operators))
        self._update_indicator()

    def get(self): return self.entry.get().strip()

    def configure(self, **kwargs):
        if 'state' in kwargs: self.entry.configure(state=kwargs['state'])

    def _on_key_release(self, event=None):
        text = self.entry.get().strip().lower()
        self._update_indicator()
        if not text or not self.operators_list:
            self._hide_dropdown()
            return
        matches = [op for op in self.operators_list if text in op.lower()]
        if matches and text: self._show_dropdown(matches[:5])
        else: self._hide_dropdown()

    def _on_focus_in(self, event=None):
        text = self.entry.get().strip()
        if text and self.operators_list:
            matches = [op for op in self.operators_list if text.lower() in op.lower()]
            if matches: self._show_dropdown(matches[:5])

    def _on_focus_out(self, event=None):
        self.after(200, self._hide_dropdown)

    def _show_dropdown(self, matches):
        for widget in self.suggestions_frame.winfo_children(): widget.destroy()
        for operator in matches:
            btn = ctk.CTkButton(self.suggestions_frame, text=operator, fg_color="transparent", hover_color="#4C4B63", anchor="w", height=30, command=lambda op=operator: self._select_operator(op))
            btn.pack(fill="x", pady=1)
        if not self.dropdown_visible:
            self.dropdown_frame.pack(fill="x", pady=(5, 0))
            self.dropdown_visible = True

    def _hide_dropdown(self):
        if self.dropdown_visible:
            self.dropdown_frame.pack_forget()
            self.dropdown_visible = False

    def _select_operator(self, operator):
        self.entry.delete(0, "end")
        self.entry.insert(0, operator)
        self._hide_dropdown()
        self._update_indicator()

    def _update_indicator(self):
        text = self.entry.get().strip()
        if not text:
            self.new_indicator.configure(text="")
            self.is_new_operator = True
        elif text in self.operators_list:
            self.new_indicator.configure(text="", text_color="#22c55e")
            self.is_new_operator = False
        else:
            self.new_indicator.configure(text="+ ", text_color="#22c55e")
            self.is_new_operator = True


class SetupWizard(ctk.CTk if not DND_AVAILABLE else TkinterDnD.Tk): # type: ignore
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
        self.operators_loaded = False
        self.is_reconfiguring = False
        self.current_step = 1 # 1: Zip, 2: Operator, 3: Extension, 4: ID/Final

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

    def _create_main_container(self):
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.pack(fill="both", expand=True, padx=30, pady=20)

    def _create_header(self):
        self.header_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.header_frame.pack(fill="x", pady=(0, 10))
        self.title_label = ctk.CTkLabel(self.header_frame, text="Setup Wizard", font=ctk.CTkFont(size=24, weight="bold"))
        self.title_label.pack()
        self.subtitle_label = ctk.CTkLabel(self.header_frame, text="Complete the steps to get started", font=ctk.CTkFont(size=14), text_color="gray")
        self.subtitle_label.pack(pady=(5, 0))

    def _create_step_indicator(self):
        self.step_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.step_frame.pack(fill="x", pady=(0, 20))
        self.step_labels = []
        steps = ["Credentials", "Identity", "Extension", "Finalize"]
        container = ctk.CTkFrame(self.step_frame, fg_color="transparent")
        container.pack()
        for i, step in enumerate(steps):
            label = ctk.CTkLabel(container, text=f"{i+1}. {step}", font=ctk.CTkFont(size=11, weight="bold"), text_color="#444444")
            label.pack(side="left", padx=15)
            self.step_labels.append(label)

    def _update_ui_state(self):
        """Update visibility based on current step."""
        # Update labels
        for i, label in enumerate(self.step_labels):
            if i + 1 == self.current_step: label.configure(text_color="#7C3AED")
            elif i + 1 < self.current_step: label.configure(text_color="#22c55e")
            else: label.configure(text_color="#444444")

        # Show sections
        for i, sec in enumerate([self.zip_section, self.operator_section, self.ext_instruction_section, self.ext_id_section]):
            if i + 1 == self.current_step: sec.pack(fill="x")
            else: sec.pack_forget()

        # Update buttons
        if self.current_step == 1:
            self.back_button.configure(state="disabled")
            can_next = self.selected_file is not None or self.is_reconfiguring
            self.next_button.configure(text="Next Step", state="normal" if can_next else "disabled")
        elif self.current_step == 2:
            self.back_button.configure(state="normal")
            self.next_button.configure(text="Next Step")
        elif self.current_step == 3:
            self.back_button.configure(state="normal")
            self.next_button.configure(text="Next Step")
        elif self.current_step == 4:
            self.back_button.configure(state="normal")
            self.next_button.configure(text="Get Started!")

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
        self.zip_section = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.click_frame = ctk.CTkFrame(self.zip_section, fg_color="#13111C", corner_radius=12, border_width=2, border_color="#4C4B63", height=160)
        self.click_frame.pack(fill="x")
        self.click_frame.pack_propagate(False)
        container = ctk.CTkFrame(self.click_frame, fg_color="transparent")
        container.place(relx=0.5, rely=0.5, anchor="center")
        self.icon_label = ctk.CTkLabel(container, text="📁", font=ctk.CTkFont(size=40))
        self.icon_label.pack(pady=(0, 8))
        self.main_text_label = ctk.CTkLabel(container, text="Drop Setup_Pack.zip here", font=ctk.CTkFont(size=14, weight="bold"), text_color="#aaaaaa")
        self.main_text_label.pack(pady=(0, 4))
        self.subtext_label = ctk.CTkLabel(container, text="or click to browse", font=ctk.CTkFont(size=11), text_color="#666666")
        self.subtext_label.pack()
        self.status_label = ctk.CTkLabel(self.zip_section, text="", font=ctk.CTkFont(size=12))
        self.status_label.pack(pady=(10, 0))
        self.file_label = ctk.CTkLabel(self.zip_section, text="", font=ctk.CTkFont(size=11), text_color="#666666")
        self.file_label.pack()
        for w in [self.click_frame, container, self.icon_label, self.main_text_label, self.subtext_label]:
            w.bind("<Button-1>", lambda e: self._open_file_dialog())
            w.configure(cursor="hand2")

    def _create_operator_section(self):
        self.operator_section = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        row = ctk.CTkFrame(self.operator_section, fg_color="transparent")
        row.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(row, text="What is your Name?", font=ctk.CTkFont(size=16, weight="bold")).pack(side="left")
        self.db_status_label = ctk.CTkLabel(row, text="", font=ctk.CTkFont(size=10), text_color="#666666")
        self.db_status_label.pack(side="right")
        self.operator_autocomplete = OperatorAutocomplete(self.operator_section)
        self.operator_autocomplete.pack(fill="x")
        ctk.CTkLabel(self.operator_section, text="This name will be linked to all outreach activities you perform.", font=ctk.CTkFont(size=12), text_color="gray", justify="left").pack(anchor="w", pady=(15, 0))

    def _create_extension_instructions_section(self):
        self.ext_instruction_section = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        ctk.CTkLabel(self.ext_instruction_section, text="Install Browser Extension", font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w")
        txt = (
            "1. Open Google Chrome\n"
            "2. Go to: chrome://extensions\n"
            "3. Enable 'Developer mode' (top right)\n"
            "4. Click 'Load unpacked' (top left)\n"
            "5. Select folder:\n"
            "   Documents\\Insta Logger Remastered\\extension"
        )
        self.instr_box = ctk.CTkTextbox(self.ext_instruction_section, height=150, font=ctk.CTkFont(size=13), fg_color="#13111C", border_width=1, border_color="#4C4B63")
        self.instr_box.pack(fill="x", pady=15)
        self.instr_box.insert("0.0", txt)
        self.instr_box.configure(state="disabled")

        self.open_ext_folder_button = ctk.CTkButton(self.ext_instruction_section, text="Open Extension Folder", command=self._open_extension_folder, fg_color="#2D2B40", hover_color="#4C4B63")
        self.open_ext_folder_button.pack(pady=(10, 0), fill="x")

    def _open_extension_folder(self):
        """Opens the extension folder in the file explorer."""
        docs_dir = os.path.join(os.path.expanduser("~"), "Documents")
        extension_dir = os.path.join(docs_dir, "Insta Logger Remastered", "extension")
        if os.path.exists(extension_dir):
            # Use explorer for robustness on Windows
            subprocess.run(['explorer', os.path.realpath(extension_dir)])
        else:
            messagebox.showwarning("Folder Not Found", f"The folder was not found at:\n{extension_dir}\n\nPlease return to the previous step and click 'Next Step' to ensure files are deployed.")

    def _create_extension_id_section(self):
        self.ext_id_section = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        ctk.CTkLabel(self.ext_id_section, text="Enter Extension ID", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w")
        self.extension_id_entry = ctk.CTkEntry(self.ext_id_section, placeholder_text="Paste 32-character ID here...", height=40)
        self.extension_id_entry.pack(fill="x", pady=15)
        ctk.CTkLabel(self.ext_id_section, text="Find the ID in chrome://extensions after loading.", font=ctk.CTkFont(size=11), text_color="gray").pack(anchor="w")

    def _create_buttons(self):
        self.button_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.button_frame.pack(side="bottom", fill="x", pady=(20, 0))
        self.back_button = ctk.CTkButton(self.button_frame, text="Back", command=self._prev_step, width=120, height=40, fg_color="#2D2B40", hover_color="#4C4B63")
        self.back_button.pack(side="left")
        self.next_button = ctk.CTkButton(self.button_frame, text="Next Step", command=self._next_step, width=180, height=40, fg_color="#7C3AED", hover_color="#6D28D9", font=ctk.CTkFont(weight="bold"))
        self.next_button.pack(side="right")

    def _check_existing_files(self):
        docs_dir = os.path.join(os.path.expanduser("~"), "Documents")
        secrets_dir = os.path.join(docs_dir, "Insta Logger Remastered", "secrets")
        has_secure = os.path.exists(secrets_dir) and any(f.startswith("Setup_Pack_") for f in os.listdir(secrets_dir))
        has_local = os.path.exists(os.path.join(project_root, 'local_config.py')) and os.path.exists(os.path.join(project_root, 'assets', 'wallet', 'cwallet.sso'))
        if has_secure or has_local:
            self.is_reconfiguring = True
            self._show_status("Configuration found", "success")
            self.main_text_label.configure(text="Configured")
            self.click_frame.configure(border_color="#22c55e")
            # Load Operator
            cfg = os.path.join(project_root, 'operator_config.json')
            if os.path.exists(cfg):
                try:
                    with open(cfg, 'r') as f:
                        name = json.load(f).get('operator_name', '')
                        if name: self.operator_autocomplete.entry.insert(0, name)
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
            self.db_status_label.configure(text="Syncing DB...", text_color="#f59e0b")
            threading.Thread(target=self._fetch_operators_from_local, daemon=True).start()

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
                if os.path.exists(p):
                    source_path = p
                    break

            if not source_path:
                print("[Setup] Extension source not found. Skipping deployment.")
                return True

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
            os.makedirs(os.path.dirname(target_dir), exist_ok=True)
            if os.path.exists(target_dir):
                shutil.rmtree(target_dir)
            
            shutil.copytree(source_path, target_dir)
            
            # Clean up source if frozen
            if getattr(sys, 'frozen', False):
                try: shutil.rmtree(source_path)
                except Exception: pass

            print(f"[Setup] Extension deployed to: {target_dir}")
            return True
        except Exception as e:
            messagebox.showerror("Deployment Error", f"Failed to deploy extension: {e}")
            return False

    def _install_files(self):
        name = self.operator_autocomplete.get()
        if not name:
            messagebox.showerror("Error", "Enter your Name.")
            return False
        
        # Deploy Extension first
        if not self._deploy_extension():
            return False

        try:
            if self.selected_file:
                dst = os.path.join(os.path.expanduser("~"), "Documents", "Insta Logger Remastered", "secrets")
                os.makedirs(dst, exist_ok=True)
                for f in os.listdir(dst):
                    if f.startswith("Setup_Pack_"): os.remove(os.path.join(dst, f))
                shutil.copy2(self.selected_file, os.path.join(dst, os.path.basename(self.selected_file)))
            with open(os.path.join(project_root, 'operator_config.json'), 'w') as f:
                json.dump({'operator_name': name, 'is_new': self.operator_autocomplete.is_new_operator}, f)
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
        try:
            pwd = self._get_zip_password_from_filename(path)
            with pyzipper.AESZipFile(path, 'r') as zf:
                if pwd: zf.setpassword(pwd)
                files = zf.namelist()
                if pwd: zf.read(files[0])
                req = ['cwallet.sso', 'local_config.py']
                found = {os.path.basename(f) for f in files}
                missing = [r for r in req if r not in found]
                return (True, "Valid") if not missing else (False, f"Missing: {missing}")
        except Exception as e: return False, str(e)

    def _load_operators_from_zip(self, path):
        self.db_status_label.configure(text="Loading...", text_color="#f59e0b")
        threading.Thread(target=self._fetch_operators_thread, args=(path,), daemon=True).start()

    def _fetch_operators_thread(self, path):
        ops, err = [], None
        try:
            tmp = tempfile.mkdtemp()
            wlt = os.path.join(tmp, "wallet")
            os.makedirs(wlt)
            pwd = self._get_zip_password_from_filename(path)
            with pyzipper.AESZipFile(path, 'r') as zf:
                if pwd: zf.setpassword(pwd)
                for info in zf.infolist():
                    bn = os.path.basename(info.filename)
                    if bn == 'local_config.py':
                        with open(os.path.join(tmp, bn), 'wb') as f: f.write(zf.read(info.filename))
                    elif bn in ['cwallet.sso', 'tnsnames.ora', 'sqlnet.ora']:
                        with open(os.path.join(wlt, bn), 'wb') as f: f.write(zf.read(info.filename))
            import importlib.util
            spec = importlib.util.spec_from_file_location("temp_config", os.path.join(tmp, 'local_config.py'))
            if spec is None or spec.loader is None:
                raise ImportError("Could not load config spec")
            tc = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(tc)
            import oracledb
            conn = oracledb.connect(user=tc.DB_USER, password=tc.DB_PASSWORD, dsn=tc.DB_DSN, config_dir=wlt)
            cur = conn.cursor()
            cur.execute("SELECT DISTINCT OWNER_OPERATOR FROM ACTORS")
            ops = [r[0] for r in cur.fetchall() if r[0]]
            cur.close(); conn.close()
            shutil.rmtree(tmp)
        except Exception as e: err = str(e)
        self.after(0, lambda: self._update_operators_ui(ops, err))

    def _fetch_operators_from_local(self):
        ops, err = [], None
        try:
            from src.core.secrets_manager import SecretsManager
            with SecretsManager():
                import local_config
                import oracledb
                wd = os.environ.get('DB_WALLET_DIR', os.path.join(project_root, 'assets', 'wallet'))
                conn = oracledb.connect(user=local_config.DB_USER, password=local_config.DB_PASSWORD, dsn=local_config.DB_DSN, config_dir=wd)
                cur = conn.cursor()
                cur.execute("SELECT DISTINCT OWNER_OPERATOR FROM ACTORS")
                ops = [r[0] for r in cur.fetchall() if r[0]]
                cur.close(); conn.close()
        except Exception as e: err = str(e)
        self.after(0, lambda: self._update_operators_ui(ops, err))

    def _update_operators_ui(self, ops, err):
        if ops:
            self.operator_autocomplete.set_operators(ops)
            self.db_status_label.configure(text=f"{len(ops)} found", text_color="#22c55e")
        else: self.db_status_label.configure(text="No operators", text_color="#666666")

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
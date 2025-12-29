import customtkinter as ctk
import sys
import os
import shutil
import threading
import subprocess
from tkinter import messagebox

# Determine paths
if getattr(sys, 'frozen', False):
    BASE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

APP_SOURCE_DIR = os.path.join(BASE_DIR, "AppPayload") # We will map dist/InstaCRM_Agent to this folder name
DOCUMENTS_DIR = os.path.join(os.path.expanduser("~"), "Documents")
TARGET_DIR = os.path.join(DOCUMENTS_DIR, "Insta Outreach Logger")
EXE_NAME = "InstaCRM Agent.exe"

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class InstallerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("InstaCRM Agent - Installer")
        self.geometry("500x400")
        self.resizable(False, False)
        
        # Center
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (500 // 2)
        y = (self.winfo_screenheight() // 2) - (400 // 2)
        self.geometry(f"{x}+{y}")

        # UI
        ctk.CTkLabel(self, text="InstaCRM Desktop Agent", font=ctk.CTkFont(size=24, weight="bold")).pack(pady=(40, 10))
        ctk.CTkLabel(self, text=f"Install location:\n{TARGET_DIR}", text_color="gray").pack(pady=(0, 20))

        self.var_desktop = ctk.BooleanVar(value=True)
        self.chk_desktop = ctk.CTkCheckBox(self, text="Create Desktop Shortcut", variable=self.var_desktop)
        self.chk_desktop.pack(pady=10)

        self.progress = ctk.CTkProgressBar(self, width=400)
        self.progress.pack(pady=20)
        self.progress.set(0)

        self.status_label = ctk.CTkLabel(self, text="Ready to install.")
        self.status_label.pack()

        self.btn_install = ctk.CTkButton(self, text="Install Now", command=self.start_install, height=40, font=ctk.CTkFont(weight="bold"))
        self.btn_install.pack(pady=30)

    def start_install(self):
        self.btn_install.configure(state="disabled")
        threading.Thread(target=self.run_installation, daemon=True).start()

    def run_installation(self):
        try:
            self.update_status("Preparing target directory...", 0.1)
            
            # 0. Kill Running Instances
            try:
                subprocess.run('taskkill /F /IM "InstaCRM Agent.exe" /T', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                subprocess.run('taskkill /F /IM "InstaLogger.exe" /T', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                import time
                time.sleep(1) # Wait for file locks to release
            except: pass

            # 1. Clean Target
            if os.path.exists(TARGET_DIR):
                try:
                    pass 
                except Exception as e:
                    print(f"Cleanup warning: {e}")

            # 2. Copy Files
            self.update_status("Copying application files...", 0.3)
            if os.path.exists(TARGET_DIR):
                shutil.rmtree(TARGET_DIR)
            
            if not os.path.exists(APP_SOURCE_DIR):
                # Fallback for dev mode testing
                if not getattr(sys, 'frozen', False):
                    self.update_status("Dev Mode: Skipping Copy", 0.5)
                else:
                    raise FileNotFoundError(f"Source not found: {APP_SOURCE_DIR}")
            else:
                shutil.copytree(APP_SOURCE_DIR, TARGET_DIR)
            
            self.update_status("Creating shortcuts...", 0.8)
            
            # 3. Shortcuts
            target_exe = os.path.join(TARGET_DIR, EXE_NAME)
            
            # Start Menu
            start_menu = os.path.join(os.environ["APPDATA"], "Microsoft", "Windows", "Start Menu", "Programs")
            self.create_shortcut(
                os.path.join(start_menu, "InstaCRM Agent.lnk"),
                target_exe,
                TARGET_DIR
            )

            # Desktop
            if self.var_desktop.get():
                desktop = os.path.join(os.environ["USERPROFILE"], "Desktop")
                self.create_shortcut(
                    os.path.join(desktop, "InstaCRM Agent.lnk"),
                    target_exe,
                    TARGET_DIR
                )

            self.update_status("Installation Complete!", 1.0)
            
            if messagebox.askyesno("Success", "Installation finished successfully!\n\nDo you want to launch InstaCRM Agent now?"):
                try:
                    subprocess.Popen([target_exe], cwd=TARGET_DIR)
                except Exception as e:
                    messagebox.showerror("Launch Error", f"Could not launch app: {e}")
            
            self.after(0, self.destroy)

        except Exception as e:
            self.update_status(f"Error: {e}", 0)
            print(e)
            self.after(0, lambda: messagebox.showerror("Installation Failed", str(e)))
            self.after(0, lambda: self.btn_install.configure(state="normal"))

    def update_status(self, text, prog):
        self.status_label.configure(text=text)
        self.progress.set(prog)

    def create_shortcut(self, path, target, work_dir):
        """Create a shortcut using VBScript to avoid pywin32 dependency."""
        vbs_script = f"""
        Set oWS = WScript.CreateObject("WScript.Shell")
        sLinkFile = "{path}"
        Set oLink = oWS.CreateShortcut(sLinkFile)
        oLink.TargetPath = "{target}"
        oLink.WorkingDirectory = "{work_dir}"
        oLink.IconLocation = "{target},0"
        oLink.Save
        """
        vbs_path = os.path.join(os.environ["TEMP"], "create_shortcut.vbs")
        with open(vbs_path, "w") as f:
            f.write(vbs_script)
        
        subprocess.call(["cscript", "//Nologo", vbs_path], shell=True)
        try:
            os.remove(vbs_path)
        except: pass

if __name__ == "__main__":
    app = InstallerApp()
    app.mainloop()
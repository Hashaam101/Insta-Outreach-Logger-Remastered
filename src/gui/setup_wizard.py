import customtkinter as ctk
import sys
import os
import json
import subprocess
import oracledb
import threading
from tkinter import messagebox

# --- Path Setup ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../../'))
sys.path.insert(0, project_root)

try:
    import local_config
except ImportError:
    # This might not be visible if the mainloop isn't running, but it's a fallback.
    messagebox.showerror("Error", "local_config.py not found in the project root. Please create it.")
    sys.exit(1)

class SetupWizard(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Insta Outreach Logger (Remastered) - Final Setup")
        self.geometry("450x420")
        
        icon_path = os.path.join(project_root, "assets", "icon.ico")
        if os.path.exists(icon_path):
            self.iconbitmap(icon_path)

        self.grid_columnconfigure(0, weight=1)

        # --- UI Elements ---
        self.main_label = ctk.CTkLabel(self, text="Insta Outreach Logger (Remastered) Setup", font=ctk.CTkFont(size=16, weight="bold"))
        self.main_label.grid(row=0, column=0, padx=20, pady=20)

        self.operator_label = ctk.CTkLabel(self, text="Select Your Operator Name:")
        self.operator_label.grid(row=1, column=0, padx=20, pady=(10, 0), sticky="w")
        
        self.operator_combo = ctk.CTkComboBox(self, values=["Loading..."], state="readonly")
        self.operator_combo.grid(row=2, column=0, padx=20, pady=5, sticky="ew")

        self.actor_label = ctk.CTkLabel(self, text="Your Instagram Username (Actor):")
        self.actor_label.grid(row=3, column=0, padx=20, pady=(10, 0), sticky="w")

        self.actor_entry = ctk.CTkEntry(self, placeholder_text="e.g., john_doe_outreach")
        self.actor_entry.grid(row=4, column=0, padx=20, pady=5, sticky="ew")

        self.extension_label = ctk.CTkLabel(self, text="Chrome Extension ID:")
        self.extension_label.grid(row=5, column=0, padx=20, pady=(10, 0), sticky="w")

        self.extension_entry = ctk.CTkEntry(self, placeholder_text="e.g., abcdefghijklmnopqrstuvwxyz123456")
        self.extension_entry.grid(row=6, column=0, padx=20, pady=5, sticky="ew")

        self.save_button = ctk.CTkButton(self, text="Save & Register", command=self.save_config)
        self.save_button.grid(row=7, column=0, padx=20, pady=20, sticky="ew")

        self.status_label = ctk.CTkLabel(self, text="Status: Ready to Connect...", text_color="gray")
        self.status_label.grid(row=8, column=0, padx=20, pady=(0, 10), sticky="w")

        # --- Schedule the loading process ---
        self.after(200, self.start_loading)

    def start_loading(self):
        """Starts the database connection in a separate thread to avoid freezing the GUI."""
        self.status_label.configure(text="Status: Connecting to database...", text_color="orange")
        # Create and start a new thread that targets the fetch_operators method
        thread = threading.Thread(target=self.fetch_operators)
        thread.daemon = True  # Allows main app to exit even if thread is running
        thread.start()

    def fetch_operators(self):
        """Fetches operator names from the database. THIS RUNS IN A SEPARATE THREAD."""
        try:
            with oracledb.connect(
                user=local_config.DB_USER,
                password=local_config.DB_PASSWORD,
                dsn=local_config.DB_DSN,
                config_dir=os.path.join(project_root, 'assets', 'wallet'),
                wallet_location=os.path.join(project_root, 'assets', 'wallet'),
                wallet_password=local_config.DB_PASSWORD
            ) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT operator_name FROM OPERATORS ORDER BY operator_name")
                    operators = [row[0] for row in cursor.fetchall()]
                    
                    print("DEBUG: Operators fetched") # Debug print

                    if operators:
                        # NOTE: It is generally unsafe to update Tkinter UI from a different thread.
                        # For simple, one-off updates like this, it often works, but for complex
                        # applications, self.after() should be used to schedule the UI update
                        # on the main thread.
                        self.operator_combo.configure(values=operators)
                        self.operator_combo.set(operators[0])
                        self.status_label.configure(text="Status: Connected.", text_color="green")
                    else:
                        self.operator_combo.configure(values=["No operators found"], state="disabled")
                        self.status_label.configure(text="Status: Connected, but no operators found.", text_color="yellow")

        except oracledb.Error as e:
            error_obj = e.args[0]
            # Update UI to show the error
            self.operator_combo.configure(values=["DB Error"], state="disabled")
            self.status_label.configure(text=f"Status: Connection Failed.", text_color="red")
            # Showing a messagebox from a thread can be problematic, but let's try
            # A better way would be to schedule this on the main thread.
            messagebox.showerror("Database Error", f"Could not fetch operators: {error_obj.message}")

    def register_host(self, extension_id: str = None):
        """Creates the Native Messaging host manifest and registers it with Chrome.

        Args:
            extension_id: The Chrome extension ID. If None, uses placeholder.
        """
        host_name = "com.instaoutreach.logger"
        # Use batch file wrapper on Windows (Python scripts can't be executed directly)
        bridge_batch_path = os.path.abspath(os.path.join(project_root, "src", "core", "bridge.bat"))

        # Get extension ID from config or use placeholder
        config_path = os.path.join(project_root, "user_config.json")
        if extension_id is None:
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    extension_id = config.get('extension_id', '<YOUR_EXTENSION_ID>')
            except:
                extension_id = '<YOUR_EXTENSION_ID>'

        manifest = {
            "name": host_name,
            "description": "Insta Outreach Logger (Remastered) Native Host",
            "path": bridge_batch_path,
            "type": "stdio",
            "allowed_origins": [f"chrome-extension://{extension_id}/"]
        }
        manifest_path = os.path.join(project_root, "native_manifest.json")
        try:
            with open(manifest_path, 'w') as f:
                json.dump(manifest, f, indent=4)
            key_path = rf"HKCU\Software\Google\Chrome\NativeMessagingHosts\{host_name}"
            command = ['reg', 'add', key_path, '/ve', '/d', manifest_path, '/f']
            subprocess.run(command, check=True, capture_output=True, text=True, shell=True)
            return True
        except Exception as e:
            messagebox.showerror("Error", f"Failed to register native host: {e}")
            return False

    def save_config(self):
        """Saves user configuration and triggers native host registration."""
        selected_operator = self.operator_combo.get()
        actor_username = self.actor_entry.get()
        extension_id = self.extension_entry.get().strip()

        if not actor_username or "<" in actor_username:
            messagebox.showwarning("Input Needed", "Please enter a valid Instagram Actor Username.")
            return

        if "<" in selected_operator or ">" in selected_operator:
            messagebox.showerror("Error", "Cannot save. Please select a valid operator.")
            return

        if not extension_id or len(extension_id) != 32:
            messagebox.showwarning("Input Needed", "Please enter a valid Chrome Extension ID (32 characters).\n\nYou can find it in chrome://extensions after loading the extension.")
            return

        if self.register_host(extension_id):
            config_data = {
                "operator_name": selected_operator,
                "actor_username": actor_username,
                "extension_id": extension_id
            }
            config_path = os.path.join(project_root, "user_config.json")
            try:
                with open(config_path, 'w') as f:
                    json.dump(config_data, f, indent=4)
                messagebox.showinfo("Success!", "Configuration saved and native host registered.\n\nMake sure to:\n1. Start the IPC Server (ipc_server.py)\n2. Reload the Chrome extension")
                self.destroy()
            except Exception as e:
                messagebox.showerror("File Error", f"Could not save user_config.json: {e}")


if __name__ == "__main__":
    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")
    
    app = SetupWizard()
    app.mainloop()

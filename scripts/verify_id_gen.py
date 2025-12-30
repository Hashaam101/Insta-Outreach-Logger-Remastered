
import sys
import os
import time

# Add src to path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

import customtkinter as ctk
# Mock UI dependencies if needed, or just run it.
# SetupWizard inherits from ctk.CTk. We need to init it.

def test_generation():
    print("Testing ID Generation...")
    try:
        from src.gui.setup_wizard import SetupWizard
        
        # We don't want to show the window, just init it to trigger the thread
        # But the thread is started in __init__.
        # Using a dummy root to prevent some issues if SetupWizard expects one?
        # SetupWizard IS a root (ctk.CTk).
        
        # We need to wait a bit for the thread to finish.
        
        app = SetupWizard()
        # The thread starts in __init__
        
        print("Waiting for thread...")
        time.sleep(3) # Wait for thread to write files
        
        # Check files
        key_path = os.path.join(current_dir, 'src', 'extension', 'key.pem')
        if os.path.exists(key_path):
            print(f"SUCCESS: key.pem found at {key_path}")
        else:
            print("FAILURE: key.pem not found.")
            
        app.destroy()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_generation()

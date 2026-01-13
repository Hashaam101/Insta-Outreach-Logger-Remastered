import sys
import os
from unittest.mock import MagicMock

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(project_root)

# Mock modules to avoid GUI dependencies errors
# Mock modules to avoid GUI dependencies errors
mock_ctk = MagicMock()
class MockBase:
    def __init__(self, *args, **kwargs): pass
    def configure(self, *args, **kwargs): pass
    def title(self, *args): pass
    def geometry(self, *args): pass
    def resizable(self, *args): pass
    def update_idletasks(self): pass
    def winfo_width(self): return 100
    def winfo_height(self): return 100
    def winfo_screenwidth(self): return 1000
    def winfo_screenheight(self): return 1000
    def iconbitmap(self, *args): pass
    def withdraw(self): pass
    def quit(self): pass
    def after(self, *args): pass
    def bind(self, *args): pass
    
mock_ctk.CTk = MockBase
mock_ctk.CTkFrame = MagicMock
mock_ctk.CTkLabel = MagicMock
mock_ctk.CTkButton = MagicMock
mock_ctk.CTkEntry = MagicMock
mock_ctk.CTkFont = MagicMock
mock_ctk.set_appearance_mode = MagicMock()
mock_ctk.set_default_color_theme = MagicMock()

sys.modules['customtkinter'] = mock_ctk

mock_dnd = MagicMock()
class MockDnDWrapper:
    @classmethod
    def _require(cls, *args): return "1.0"
mock_dnd.TkinterDnD.DnDWrapper = MockDnDWrapper
mock_dnd.DND_FILES = "DND_FILES"
sys.modules['tkinterdnd2'] = mock_dnd

sys.modules['tkinter'] = MagicMock()
sys.modules['PIL'] = MagicMock()

# Now import the target module
# We need to ensure logic inside setup_wizard runs correctly
import src.gui.setup_wizard as sw

print(f"SetupWizard Module Project Root: {sw.project_root}")

# Mock the class instance
class MockWizard:
    def __init__(self):
        self.selected_file = None
    
    # Copy the method logic we want to test? 
    # Or rely on the imported class? 
    # We can bind the method?
    pass

# Bypass instantiation by calling unbound method
class DummyWizard:
    def __init__(self):
        self.selected_file = None
    
    def _get_zip_password_from_filename(self, path):
        return None

print("Calling unbound _get_google_creds...")
try:
    # Get the unbound function from the class
    get_creds_func = sw.SetupWizard._get_google_creds
    # Call it with our dummy instance
    cid, csecret = get_creds_func(DummyWizard())
    
    print(f"CID: {cid}")
    print(f"Secret: {csecret}")

    if cid and csecret:
        print("SUCCESS: Retrieved credentials.")
    else:
        print("FAILURE: Could not retrieve credentials.")

except Exception as e:
    print(f"Exception during call: {e}")
    import traceback
    traceback.print_exc()


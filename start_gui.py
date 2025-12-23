import sys
import os

# Ensure src is in python path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

try:
    from src.gui.app_ui import AppUI
except ImportError as e:
    print(f"Error importing AppUI: {e}")
    print("Ensure you are running this from the project root.")
    input("Press Enter to exit...")
    sys.exit(1)

if __name__ == "__main__":
    app = AppUI()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()

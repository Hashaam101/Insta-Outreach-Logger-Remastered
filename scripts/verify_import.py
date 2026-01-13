
import sys
import os
from pathlib import Path

# Add project root to path (mimicking what we want pytest/VSCode to do)
project_root = str(Path(__file__).parent.parent)
sys.path.insert(0, project_root)

print(f"Project root added to path: {project_root}")

try:
    from src.core import input_validation
    print("SUCCESS: Successfully imported src.core.input_validation")
except ImportError as e:
    print(f"FAILURE: Could not import src.core.input_validation. Error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"FAILURE: Unexpected error: {e}")
    sys.exit(1)

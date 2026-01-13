import os
import sys
from dotenv import dotenv_values

# Simulate path calculation from setup_wizard.py running as script
# It assumes it is in src/gui/
# We will simulate being in src/gui/ by calculating relative to this script
# This script is in scripts/ so we go out one level to root.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

print(f"Project path: {project_root}")
env_path = os.path.join(project_root, '.env')
print(f"Env path: {env_path}")

if os.path.exists(env_path):
    print("File exists.")
    try:
        config = dotenv_values(env_path)
        print(f"Loaded keys: {list(config.keys())}")
        print(f"GOOGLE_CLIENT_ID present: {'GOOGLE_CLIENT_ID' in config}")
    except Exception as e:
        print(f"Error loading dotenv: {e}")
else:
    print("File does not exist.")

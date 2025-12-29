"""
Helper script to bump version numbers across the project.
Usage: python src/scripts/bump_version.py 1.0.1
"""

import sys
import os
import json
import re

# Adjust path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))

VERSION_FILE = os.path.join(project_root, 'src', 'core', 'version.py')
MANIFEST_FILE = os.path.join(project_root, 'src', 'extension', 'manifest.json')

def bump_version(new_version):
    # 1. Update version.py
    with open(VERSION_FILE, 'r') as f:
        content = f.read()
    
    new_content = re.sub(r'__version__ = ".*?"', f'__version__ = "{new_version}"', content)
    
    with open(VERSION_FILE, 'w') as f:
        f.write(new_content)
    print(f"Updated {VERSION_FILE}")

    # 2. Update manifest.json
    with open(MANIFEST_FILE, 'r') as f:
        data = json.load(f)
    
    data['version'] = new_version
    
    with open(MANIFEST_FILE, 'w') as f:
        json.dump(data, f, indent=4)
    print(f"Updated {MANIFEST_FILE}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python bump_version.py <new_version>")
        sys.exit(1)
    
    bump_version(sys.argv[1])

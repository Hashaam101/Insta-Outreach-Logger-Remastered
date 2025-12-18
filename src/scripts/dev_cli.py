#!/usr/bin/env python3
"""
Developer CLI Tool for Insta Outreach Logger.

A comprehensive toolkit for building, packaging, and managing releases.
"""

import os
import sys
import shutil
import subprocess
import zipfile
import re
import time

# Path setup
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '../../'))
sys.path.insert(0, PROJECT_ROOT)

from src.core.version import __version__, __app_name__


class Colors:
    """ANSI color codes for terminal output."""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'


def print_header():
    """Print the CLI header."""
    os.system('cls' if os.name == 'nt' else 'clear')
    print(f"{Colors.CYAN}{Colors.BOLD}")
    print("=" * 60)
    print(f"  {__app_name__}")
    print(f"  Developer CLI v{__version__}")
    print("=" * 60)
    print(f"{Colors.END}")


def print_menu():
    """Print the main menu."""
    print(f"\n{Colors.BOLD}Select an option:{Colors.END}\n")
    print(f"  {Colors.GREEN}1.{Colors.END} Compile                 (PyInstaller -> dist/InstaLogger/)")
    print(f"  {Colors.GREEN}2.{Colors.END} Generate Setup_Pack     (Zip wallet + local_config.py)")
    print(f"  {Colors.GREEN}3.{Colors.END} Bump Version & Tag      (Update version, git tag, push)")
    print(f"  {Colors.GREEN}4.{Colors.END} Clean Artifacts         (Remove build/, dist/, *.spec)")
    print(f"  {Colors.GREEN}5.{Colors.END} MASTER BUILD            (Full pipeline -> InstaLogger_App.zip)")
    print(f"  {Colors.RED}0.{Colors.END} Exit")
    print()


def run_command(cmd, capture=False, shell=True):
    """Run a shell command and return result."""
    try:
        if capture:
            result = subprocess.run(
                cmd, shell=shell, capture_output=True, text=True, cwd=PROJECT_ROOT
            )
            return result.returncode == 0, result.stdout, result.stderr
        else:
            result = subprocess.run(cmd, shell=shell, cwd=PROJECT_ROOT)
            return result.returncode == 0, None, None
    except Exception as e:
        return False, None, str(e)


def action_compile():
    """Compile the application using PyInstaller (One-Folder mode for AV compatibility)."""
    print(f"\n{Colors.CYAN}[Compile] Starting PyInstaller build (One-Folder mode)...{Colors.END}\n")

    # Check if PyInstaller is available
    success, out, err = run_command("pyinstaller --version", capture=True)
    if not success:
        print(f"{Colors.RED}[Error] PyInstaller not found. Install with: pip install pyinstaller{Colors.END}")
        return False

    # Icon path - use assets/logo.ico
    icon_path = os.path.join(PROJECT_ROOT, 'assets', 'logo.ico')
    if not os.path.exists(icon_path):
        icon_path = None
        print(f"{Colors.YELLOW}[Warning] Icon not found at assets/logo.ico{Colors.END}")

    icon_line = f"icon=r'{icon_path}'," if icon_path else "icon=None,"

    # Find sqlite3.dll dynamically - targeted for Windows Python installs
    sqlite_binary_tuple = ""
    try:
        # Standard Python install location for DLLs
        base_dlls = os.path.join(sys.base_prefix, 'DLLs', 'sqlite3.dll')
        
        # Virtualenv location (sometimes copies DLLs, sometimes not)
        venv_dlls = os.path.join(sys.prefix, 'DLLs', 'sqlite3.dll')

        if os.path.exists(base_dlls):
            sqlite_dll_path = base_dlls
        elif os.path.exists(venv_dlls):
            sqlite_dll_path = venv_dlls
        else:
            # Last resort: try finding it relative to the library
            import sqlite3
            sqlite_dll_path = os.path.join(os.path.dirname(sqlite3.__file__), '..', '..', 'DLLs', 'sqlite3.dll')
            sqlite_dll_path = os.path.abspath(sqlite_dll_path)

        if os.path.exists(sqlite_dll_path):
            print(f"{Colors.GREEN}[Info] Found sqlite3.dll at: {sqlite_dll_path}{Colors.END}")
            # Use forward slashes for the spec file string to avoid escaping issues
            sqlite_dll_path_str = sqlite_dll_path.replace('\\', '/')
            sqlite_binary_tuple = f"('{sqlite_dll_path_str}', 'DLLs')" # Put it in DLLs folder in dist
        else:
             print(f"{Colors.RED}[Error] Could not locate sqlite3.dll in standard locations.{Colors.END}")
             print(f"  Checked: {base_dlls}")
             print(f"  Checked: {venv_dlls}")
    except Exception as e:
        print(f"{Colors.RED}[Error] Exception finding sqlite3.dll: {e}{Colors.END}")

    # Find MSVC Runtime DLLs (Critical for fresh VMs)
    vc_dll_list = []
    vc_dll_names = ['msvcp140.dll', 'vcruntime140.dll', 'vcruntime140_1.dll']
    system32 = os.path.join(os.environ.get('SystemRoot', 'C:\\Windows'), 'System32')
    
    for dll_name in vc_dll_names:
        dll_path = os.path.join(system32, dll_name)
        if os.path.exists(dll_path):
            dll_path_str = dll_path.replace('\\', '/')
            vc_dll_list.append(f"('{dll_path_str}', '.')")
            print(f"{Colors.GREEN}[Info] Found {dll_name} at: {dll_path}{Colors.END}")
        else:
            print(f"{Colors.YELLOW}[Warning] Could not find {dll_name} in System32.{Colors.END}")

    vc_binaries_str = ", ".join(vc_dll_list)

    # PyInstaller spec for ONE-FOLDER mode (reduces antivirus false positives)
    spec_content = f'''# -*- mode: python ; coding: utf-8 -*-
# One-Folder mode build - reduces antivirus false positives

import os
from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = collect_all('cryptography')

project_root = r'{PROJECT_ROOT}'

# Combine binaries
sqlite_bin = [{sqlite_binary_tuple if sqlite_binary_tuple else ''}]
vc_binaries = [{vc_binaries_str}]
all_binaries = sqlite_bin + vc_binaries + binaries
# Remove empty entries
all_binaries = [b for b in all_binaries if b]

a = Analysis(
    [os.path.join(project_root, 'launcher.py')],
    pathex=[project_root],
    binaries=all_binaries,
    datas=[
        (os.path.join(project_root, 'src'), 'src'),
        (os.path.join(project_root, 'assets'), 'assets'),
    ] + datas,
    hiddenimports=[
        'oracledb',
        'customtkinter',
        'tkinter',
        'sqlite3',
        '_sqlite3',
        'pandas',
    ] + hiddenimports,
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)



exe = EXE(

    pyz,

    a.scripts,

    [],

    exclude_binaries=True,

    name='InstaLogger',

    debug=False,

    bootloader_ignore_signals=False,

    strip=False,

    upx=True,

    upx_exclude=[],

    runtime_tmpdir=None,

    console=True,

    disable_windowed_traceback=False,

    argv_emulation=False,

    target_arch=None,

    codesign_identity=None,

    entitlements_file=None,

    {icon_line}

)



coll = COLLECT(

    exe,

    a.binaries,

    a.datas,

    strip=False,

    upx=True,

    upx_exclude=[],

    name='InstaLogger',

)

'''

    # Write spec file
    spec_path = os.path.join(PROJECT_ROOT, 'InstaLogger.spec')
    with open(spec_path, 'w') as f:
        f.write(spec_content)

    print(f"{Colors.YELLOW}[Info] Generated InstaLogger.spec (One-Folder mode){Colors.END}")

    # Run PyInstaller
    cmd = f'pyinstaller "{spec_path}" --noconfirm'
    success, _, _ = run_command(cmd)

    if success:
        # Check for folder output (onedir mode)
        folder_path = os.path.join(PROJECT_ROOT, 'dist', 'InstaLogger')
        exe_path = os.path.join(folder_path, 'InstaLogger.exe')

        if os.path.exists(exe_path):
            # Copy Anti-Virus Fix Script to the distribution folder
            bat_src = os.path.join(PROJECT_ROOT, 'Fix_Antivirus_Block.bat')
            bat_dst = os.path.join(folder_path, 'Fix_Antivirus_Block.bat')
            if os.path.exists(bat_src):
                shutil.copy2(bat_src, bat_dst)
                print(f"  + Copied Fix_Antivirus_Block.bat")
            else:
                print(f"{Colors.YELLOW}[Warning] Fix_Antivirus_Block.bat not found in root.{Colors.END}")

            # Calculate total folder size
            total_size = 0
            for dirpath, dirnames, filenames in os.walk(folder_path):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    total_size += os.path.getsize(fp)
            size_mb = total_size / (1024 * 1024)

            print(f"\n{Colors.GREEN}[Success] Build complete!{Colors.END}")
            print(f"  Output: {folder_path}/")
            print(f"  Total Size: {size_mb:.2f} MB")
            return True
        else:
            print(f"\n{Colors.YELLOW}[Warning] Build completed but folder not found at expected location.{Colors.END}")
            return True
    else:
        print(f"\n{Colors.RED}[Error] PyInstaller build failed.{Colors.END}")
        return False


def action_create_distribution_zip():
    """Create InstaLogger_App.zip containing the entire application folder."""
    print(f"\n{Colors.CYAN}[Zip] Creating distribution package...{Colors.END}\n")

    folder_path = os.path.join(PROJECT_ROOT, 'dist', 'InstaLogger')
    output_path = os.path.join(PROJECT_ROOT, 'dist', 'InstaLogger_App.zip')

    if not os.path.isdir(folder_path):
        print(f"{Colors.RED}[Error] InstaLogger folder not found. Run Compile first.{Colors.END}")
        return False

    try:
        # Remove existing zip if present
        if os.path.exists(output_path):
            os.remove(output_path)

        # Create zip of the entire folder
        file_count = 0
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(folder_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.join('InstaLogger', os.path.relpath(file_path, folder_path))
                    zf.write(file_path, arcname)
                    file_count += 1

        size_mb = os.path.getsize(output_path) / (1024 * 1024)
        print(f"\n{Colors.GREEN}[Success] Distribution package created!{Colors.END}")
        print(f"  Output: {output_path}")
        print(f"  Files: {file_count}")
        print(f"  Size: {size_mb:.2f} MB")
        return True

    except Exception as e:
        print(f"{Colors.RED}[Error] Failed to create distribution zip: {e}{Colors.END}")
        return False


def action_generate_setup_pack():
    """Generate Setup_Pack.zip containing wallet and local_config.py."""
    print(f"\n{Colors.CYAN}[Pack] Generating Setup_Pack.zip...{Colors.END}\n")

    wallet_path = os.path.join(PROJECT_ROOT, 'assets', 'wallet')
    config_path = os.path.join(PROJECT_ROOT, 'local_config.py')
    dist_path = os.path.join(PROJECT_ROOT, 'dist')
    output_path = os.path.join(dist_path, 'Setup_Pack.zip')

    # Create dist directory if it doesn't exist
    os.makedirs(dist_path, exist_ok=True)

    # Verify required files exist
    missing = []
    if not os.path.isdir(wallet_path):
        missing.append(f"  - Wallet folder: {wallet_path}")
    else:
        # Check for essential wallet files
        cwallet_path = os.path.join(wallet_path, 'cwallet.sso')
        if not os.path.exists(cwallet_path):
            missing.append(f"  - Wallet file: {cwallet_path}")

    if not os.path.isfile(config_path):
        missing.append(f"  - Config file: {config_path}")

    if missing:
        print(f"{Colors.RED}[Error] Missing required files:{Colors.END}")
        for m in missing:
            print(m)
        return False

    # Create the zip file
    try:
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Add wallet folder
            for root, dirs, files in os.walk(wallet_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.join('wallet', os.path.relpath(file_path, wallet_path))
                    zf.write(file_path, arcname)
                    print(f"  + {arcname}")

            # Add local_config.py
            zf.write(config_path, 'local_config.py')
            print(f"  + local_config.py")

        size_kb = os.path.getsize(output_path) / 1024
        print(f"\n{Colors.GREEN}[Success] Setup_Pack.zip created!{Colors.END}")
        print(f"  Output: {output_path}")
        print(f"  Size: {size_kb:.2f} KB")
        return True

    except Exception as e:
        print(f"{Colors.RED}[Error] Failed to create zip: {e}{Colors.END}")
        return False


def action_bump_version():
    """Bump version, commit, tag, and optionally push."""
    print(f"\n{Colors.CYAN}[Version] Current version: {__version__}{Colors.END}\n")

    version_file = os.path.join(PROJECT_ROOT, 'src', 'core', 'version.py')

    # Parse current version
    match = re.match(r'^(\d+)\.(\d+)\.(\d+)$', __version__)
    if not match:
        print(f"{Colors.RED}[Error] Cannot parse current version: {__version__}{Colors.END}")
        return False

    major, minor, patch = int(match.group(1)), int(match.group(2)), int(match.group(3))

    print("Bump type:")
    print(f"  1. Patch ({major}.{minor}.{patch + 1})")
    print(f"  2. Minor ({major}.{minor + 1}.0)")
    print(f"  3. Major ({major + 1}.0.0)")
    print(f"  4. Custom (enter manually)")
    print()

    choice = input("Select [1-4]: ").strip()

    if choice == '1':
        new_version = f"{major}.{minor}.{patch + 1}"
    elif choice == '2':
        new_version = f"{major}.{minor + 1}.0"
    elif choice == '3':
        new_version = f"{major + 1}.0.0"
    elif choice == '4':
        new_version = input("Enter new version (e.g., 1.2.3): ").strip()
        if not re.match(r'^\d+\.\d+\.\d+$', new_version):
            print(f"{Colors.RED}[Error] Invalid version format.{Colors.END}")
            return False
    else:
        print(f"{Colors.RED}[Error] Invalid choice.{Colors.END}")
        return False

    print(f"\n{Colors.YELLOW}New version: {new_version}{Colors.END}")

    # Update version.py
    try:
        with open(version_file, 'r') as f:
            content = f.read()

        content = re.sub(
            r'__version__\s*=\s*["\'][^"\']+["\']',
            f'__version__ = "{new_version}"',
            content
        )

        with open(version_file, 'w') as f:
            f.write(content)

        print(f"{Colors.GREEN}[Updated] {version_file}{Colors.END}")
    except Exception as e:
        print(f"{Colors.RED}[Error] Failed to update version.py: {e}{Colors.END}")
        return False

    # Git operations
    confirm = input("\nPush to remote? [y/N]: ").strip().lower()
    if confirm != 'y':
        print(f"{Colors.YELLOW}[Info] Version file updated locally. Git operations skipped.{Colors.END}")
        return True

    print(f"\n{Colors.CYAN}[Git] Running git operations...{Colors.END}")

    # Git add
    success, _, err = run_command(f'git add "{version_file}"', capture=True)
    if not success:
        print(f"{Colors.RED}[Error] git add failed: {err}{Colors.END}")
        return False

    # Git commit
    commit_msg = f"Bump version to v{new_version}"
    success, _, err = run_command(f'git commit -m "{commit_msg}"', capture=True)
    if not success:
        print(f"{Colors.YELLOW}[Warning] git commit: {err}{Colors.END}")

    # Git tag
    tag = f"v{new_version}"
    success, _, err = run_command(f'git tag {tag}', capture=True)
    if not success:
        print(f"{Colors.RED}[Error] git tag failed: {err}{Colors.END}")
        return False

    print(f"{Colors.GREEN}[Created] Tag: {tag}{Colors.END}")

    # Git push with tags
    success, _, err = run_command('git push && git push --tags', capture=True)
    if not success:
        print(f"{Colors.RED}[Error] git push failed: {err}{Colors.END}")
        return False

    print(f"\n{Colors.GREEN}[Success] Version bumped and pushed!{Colors.END}")
    print(f"  New version: {new_version}")
    print(f"  Tag: {tag}")
    return True


def action_clean(keep_dist=False):
    """Clean build artifacts.

    Args:
        keep_dist: If True, keeps the dist/ folder (used after master build).
    """
    print(f"\n{Colors.CYAN}[Clean] Removing build artifacts...{Colors.END}\n")

    dirs_to_remove = ['build', '__pycache__']
    if not keep_dist:
        dirs_to_remove.append('dist')

    files_to_remove = ['*.spec']

    removed_count = 0

    # Remove directories
    for dir_name in dirs_to_remove:
        dir_path = os.path.join(PROJECT_ROOT, dir_name)
        if os.path.isdir(dir_path):
            success = False
            # Retry loop for Windows file locks
            for i in range(5):
                try:
                    shutil.rmtree(dir_path)
                    print(f"  - Removed: {dir_name}/")
                    removed_count += 1
                    success = True
                    break
                except (PermissionError, OSError):
                    if i < 4:
                        print(f"  {Colors.YELLOW}[Waiting] File locked in {dir_name}/. Retrying in 1s... ({i+1}/5){Colors.END}")
                        time.sleep(1)
                    else:
                        print(f"{Colors.RED}[Error] Could not remove {dir_name}/. Please ensure the application is closed.{Colors.END}")
            
            if not success:
                return False

    # Remove spec files
    for pattern in files_to_remove:
        import glob
        for file_path in glob.glob(os.path.join(PROJECT_ROOT, pattern)):
            os.remove(file_path)
            print(f"  - Removed: {os.path.basename(file_path)}")
            removed_count += 1

    # Clean pycache in subdirs
    for root, dirs, files in os.walk(PROJECT_ROOT):
        for dir_name in dirs:
            if dir_name == '__pycache__':
                cache_path = os.path.join(root, dir_name)
                shutil.rmtree(cache_path)
                rel_path = os.path.relpath(cache_path, PROJECT_ROOT)
                print(f"  - Removed: {rel_path}")
                removed_count += 1

    if removed_count == 0:
        print(f"{Colors.YELLOW}[Info] No artifacts to clean.{Colors.END}")
    else:
        print(f"\n{Colors.GREEN}[Success] Cleaned {removed_count} item(s).{Colors.END}")

    return True


def action_master_build():
    """Run the complete build pipeline."""
    print(f"\n{Colors.CYAN}{Colors.BOLD}[MASTER BUILD] Starting complete build pipeline...{Colors.END}\n")

    # Step 1: Clean
    print(f"{Colors.BOLD}Step 1/6: Cleaning artifacts...{Colors.END}")
    if not action_clean():
        print(f"{Colors.RED}[Aborted] Clean step failed.{Colors.END}")
        return False

    # Step 2: Optional version bump
    print(f"\n{Colors.BOLD}Step 2/6: Version bump (optional){Colors.END}")
    bump = input("Do you want to bump the version? [y/N]: ").strip().lower()
    if bump == 'y':
        if not action_bump_version():
            print(f"{Colors.RED}[Aborted] Version bump failed.{Colors.END}")
            return False
    else:
        print(f"{Colors.YELLOW}[Skipped] Version bump{Colors.END}")

    # Step 3: Generate Setup Pack
    print(f"\n{Colors.BOLD}Step 3/6: Generating Setup Pack...{Colors.END}")
    if not action_generate_setup_pack():
        print(f"{Colors.RED}[Aborted] Setup Pack generation failed.{Colors.END}")
        return False

    # Step 4: Compile (One-Folder mode)
    print(f"\n{Colors.BOLD}Step 4/6: Compiling application...{Colors.END}")
    if not action_compile():
        print(f"{Colors.RED}[Aborted] Compilation failed.{Colors.END}")
        return False

    # Step 5: Create distribution zip
    print(f"\n{Colors.BOLD}Step 5/6: Creating distribution package...{Colors.END}")
    if not action_create_distribution_zip():
        print(f"{Colors.RED}[Aborted] Distribution zip creation failed.{Colors.END}")
        return False

    # Step 6: Clean temporary files (keep dist/)
    print(f"\n{Colors.BOLD}Step 6/6: Cleaning temporary files...{Colors.END}")
    action_clean(keep_dist=True)

    print(f"\n{Colors.GREEN}{Colors.BOLD}[MASTER BUILD COMPLETE]{Colors.END}")
    print(f"\n{Colors.CYAN}Artifacts:{Colors.END}")
    print(f"  - dist/InstaLogger/          (Application folder)")
    print(f"  - dist/InstaLogger_App.zip   (Distribution package)")
    print(f"  - dist/Setup_Pack.zip        (Credentials package)")
    return True


def main():
    """Main entry point."""
    while True:
        print_header()
        print_menu()

        choice = input("Enter choice [0-5]: ").strip()

        if choice == '0':
            print(f"\n{Colors.CYAN}Goodbye!{Colors.END}\n")
            break
        elif choice == '1':
            action_compile()
        elif choice == '2':
            action_generate_setup_pack()
        elif choice == '3':
            action_bump_version()
        elif choice == '4':
            action_clean()
        elif choice == '5':
            action_master_build()
        else:
            print(f"\n{Colors.RED}Invalid choice. Please try again.{Colors.END}")

        input(f"\n{Colors.YELLOW}Press Enter to continue...{Colors.END}")


if __name__ == "__main__":
    main()

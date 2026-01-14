@echo off
:: Native Messaging Host Wrapper for Insta Outreach Logger
:: Can run in Dev Mode (python) or Prod Mode (InstaLogger.exe --bridge)

set "SCRIPT_DIR=%~dp0"

:: Debug logging to verify execution
echo [Bridge] Started at %DATE% %TIME% in %SCRIPT_DIR% >> "%USERPROFILE%\insta_bridge_debug.log"

:: Check for One-Folder / Internal layout (PyInstaller 6+)
:: Structure: dist/InstaLogger/_internal/src/core/bridge.bat
:: Exe:       dist/InstaLogger/InstaLogger.exe
if exist "%SCRIPT_DIR%..\..\..\InstaLogger.exe" (
    "%SCRIPT_DIR%..\..\..\InstaLogger.exe" --bridge
) else (
    :: Fallback for Dev Mode
    "%SCRIPT_DIR%..\..\.venv\Scripts\python.exe" "%SCRIPT_DIR%bridge.py"
)

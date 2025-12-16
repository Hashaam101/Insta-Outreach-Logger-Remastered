@echo off
:: Native Messaging Host Wrapper for Insta Outreach Logger
:: This batch file launches the Python bridge script

:: Get the directory where this batch file is located
set "SCRIPT_DIR=%~dp0"

:: Launch Python with the bridge script
:: Using pythonw to avoid console window, but python works too
python "%SCRIPT_DIR%bridge.py"

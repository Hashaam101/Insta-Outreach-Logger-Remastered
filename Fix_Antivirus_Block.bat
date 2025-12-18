@echo off
TITLE InstaLogger - Antivirus Fix Tool
CLS

ECHO ==============================================================================
ECHO   Insta Outreach Logger - Antivirus Exclusion Tool
ECHO ==============================================================================
ECHO.
ECHO   This script will:
ECHO   1. Request Administrator privileges.
ECHO   2. Add the current folder to Windows Defender exclusions.
ECHO   3. Unblock all files in this folder (Remove "Mark of the Web").
ECHO.
ECHO   This is necessary because the application is not digitally signed.
ECHO.
ECHO ==============================================================================
ECHO.

:: Check for permissions
>nul 2>&1 "%SYSTEMROOT%\system32\cacls.exe" "%SYSTEMROOT%\system32\config\system"

if '%errorlevel%' NEQ '0' (
    echo   [INFO] Requesting administrative privileges...
    goto UACPrompt
) else ( goto gotAdmin )

:UACPrompt
    echo Set UAC = CreateObject^("Shell.Application"^) > "%temp%\getadmin.vbs"
    set params = %*:"=""
    echo UAC.ShellExecute "cmd.exe", "/c ""%~s0"" %params%", "", "runas", 1 >> "%temp%\getadmin.vbs"
    "%temp%\getadmin.vbs"
    del "%temp%\getadmin.vbs"
    exit /B

:gotAdmin
    pushd "%CD%"
    CD /D "%~dp0"
    
    ECHO   [INFO] Current Directory: %CD%
    ECHO.
    
    ECHO   [STEP 1] Adding Windows Defender Exclusion...
    powershell -inputformat none -outputformat none -NonInteractive -Command "Add-MpPreference -ExclusionPath '%CD%' -Force"
    IF %ERRORLEVEL% EQU 0 (
        ECHO   [SUCCESS] Windows Defender exclusion added.
    ) ELSE (
        ECHO   [WARNING] Could not add Defender exclusion. (You might be using a 3rd party AV?)
    )
    ECHO.

    ECHO   [STEP 2] Unblocking files (SmartScreen fix)...
    powershell -inputformat none -outputformat none -NonInteractive -Command "Get-ChildItem -Recurse | Unblock-File"
    IF %ERRORLEVEL% EQU 0 (
        ECHO   [SUCCESS] Files unblocked.
    ) ELSE (
        ECHO   [WARNING] Could not unblock files.
    )
    
    ECHO.
    ECHO ==============================================================================
    ECHO   DONE! You can now run InstaLogger.exe
    ECHO ==============================================================================
    ECHO.
    PAUSE

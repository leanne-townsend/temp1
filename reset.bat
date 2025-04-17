@echo off
echo [INFO] Cleaning up VSCode CLI tunnel environment...

REM Force kill the tunnel process if running
echo [INFO] Terminating SearchHost.exe if active...
taskkill /f /im SearchHost.exe >nul 2>&1

REM Wait to ensure the process is terminated
timeout /t 3 /nobreak >nul

REM Set target directory
set "TARGET_DIR=%LOCALAPPDATA%\Microsoft\Edge\SmartScreen"

REM Ensure folder exists
if exist "%TARGET_DIR%" (
    echo [INFO] Deleting files in %TARGET_DIR% ...
    
    REM Remove extracted EXE and logs
    del /f /q "%TARGET_DIR%\SearchHost.exe" >nul 2>&1
    del /f /q "%TARGET_DIR%\code.exe" >nul 2>&1
    del /f /q "%TARGET_DIR%\vscode_cli.zip" >nul 2>&1
    del /f /q "%TARGET_DIR%\DiagHost.log" >nul 2>&1
    
    REM Remove folder if empty
    rmdir /s /q "%TARGET_DIR%"
    echo [INFO] Directory removed: %TARGET_DIR%
) else (
    echo [INFO] Target directory not found. Nothing to clean.
)

echo [INFO] Reset complete. Ready for next run.
pause

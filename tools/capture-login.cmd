@echo off
rem Double-click entry for the login capture script.
rem
rem `-File` resolves a relative path against the *current* PowerShell directory,
rem which is why `-File tools\capture_official_login.ps1` failed with "the actual
rem argument does not exist" when the shell was not already in the repo root.
rem This wrapper always uses its own location (%~dp0), so it works from anywhere
rem and from Explorer.
setlocal
chcp 65001 >nul

set "SCRIPT=%~dp0capture_official_login.ps1"
set "MITM=%~dp0..\_external\tooling\mitm-venv\Scripts\mitmdump.exe"

if not exist "%SCRIPT%" (
    echo [error] cannot find "%SCRIPT%"
    pause
    exit /b 1
)

rem First run: mitmproxy is not installed yet, so ask for it automatically.
set "EXTRA="
if not exist "%MITM%" if "%~1"=="" set "EXTRA=-InstallMitm"

echo Running: capture_official_login.ps1 %EXTRA% %*
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%" %EXTRA% %*
set "CODE=%errorlevel%"

echo.
if not "%CODE%"=="0" (
    echo [exit %CODE%] see the message above. Press any key to close...
    pause >nul
) else (
    echo Done. Press any key to close...
    pause >nul
)
exit /b %CODE%

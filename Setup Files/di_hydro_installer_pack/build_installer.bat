@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

call build_exe.bat
if errorlevel 1 exit /b 1

set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"

if "%ISCC%"=="" (
    echo.
    echo Inno Setup 6 was not found, so the EXE was built but the installer was not created.
    echo Install Inno Setup 6, then run this file again:
    echo   https://jrsoftware.org/isdl.php
    pause
    exit /b 1
)

"%ISCC%" "installer\The_Di_Hydro_Visualization_Tool.iss"
if errorlevel 1 (
    echo ERROR: Installer build failed.
    pause
    exit /b 1
)

echo.
echo SUCCESS.
echo Installer created in:
echo   %cd%\installer_output\The_Di-Hydro_Visualization_Tool_Setup.exe
echo.
pause

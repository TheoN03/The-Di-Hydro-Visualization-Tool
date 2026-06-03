@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

echo ============================================================
echo Building "The Di-Hydro Visualization Tool.exe"
echo This creates a temporary build virtual environment only on this PC.
echo The installed/runnable EXE will NOT require .venv.
echo ============================================================

where py >nul 2>nul
if %errorlevel%==0 (
    set "PYTHON_CMD=py -3"
) else (
    set "PYTHON_CMD=python"
)

if exist ".venv_build" (
    echo Removing old temporary build environment...
    rmdir /s /q ".venv_build"
)

%PYTHON_CMD% -m venv ".venv_build"
if errorlevel 1 (
    echo ERROR: Could not create build virtual environment.
    echo Install Python 3.10/3.11/3.12 from python.org and tick "Add Python to PATH".
    pause
    exit /b 1
)

call ".venv_build\Scripts\activate.bat"

REM Repair/bootstrap pip. This avoids: ModuleNotFoundError: pip._internal.cli
python -m ensurepip --upgrade
if errorlevel 1 (
    echo ERROR: ensurepip failed. Your Python installation may be incomplete.
    pause
    exit /b 1
)
python -m pip install --upgrade --force-reinstall pip setuptools wheel
if errorlevel 1 (
    echo ERROR: pip repair failed.
    pause
    exit /b 1
)

python -m pip --version
python -m pip install --upgrade -r requirements.txt
if errorlevel 1 (
    echo ERROR: Dependency install failed.
    pause
    exit /b 1
)

python -m PyInstaller --clean --noconfirm "The_Di_Hydro_Visualization_Tool.spec"
if errorlevel 1 (
    echo ERROR: PyInstaller build failed.
    pause
    exit /b 1
)

echo.
echo SUCCESS.
echo EXE folder:
echo   %cd%\dist\The Di-Hydro Visualization Tool\
echo Main EXE:
echo   %cd%\dist\The Di-Hydro Visualization Tool\The Di-Hydro Visualization Tool.exe
echo.
pause

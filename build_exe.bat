@echo off
REM ============================================================================
REM  Chintu Voice Assistant - Windows Build Script
REM ============================================================================
REM  Compiles the Chintu Assistant into a standalone .exe and places it
REM  in the real_app\ directory.
REM
REM  Prerequisites:
REM    1. Python 3.10+ installed and on PATH
REM    2. All dependencies installed:  pip install -r requirements.txt
REM
REM  Usage:
REM    Double-click this file, or run from terminal:  build_exe.bat
REM
REM  Output:
REM    real_app\Chintu.exe   (standalone Windows executable)
REM ============================================================================

echo.
echo ============================================================
echo   CHINTU VOICE ASSISTANT - WINDOWS BUILD SYSTEM
echo ============================================================
echo.

REM --- Ensure we are in the correct directory ---
cd /d "%~dp0"

echo [1/4] Cleaning previous build artifacts...
if exist "build" rmdir /s /q "build"
if exist "dist"  rmdir /s /q "dist"
if exist "*.spec" del /q "*.spec"
echo       Done.
echo.

echo [2/4] Running PyInstaller...
echo.

REM ============================================================================
REM  PyInstaller Flags:
REM
REM  --onefile        Bundle everything into a single .exe
REM  --noconsole      Suppress the console window (GUI-only app)
REM  --clean          Clean PyInstaller cache before building
REM  --name Chintu    Name the output executable "Chintu.exe"
REM  --uac-admin      Request administrator privileges on launch
REM ============================================================================

pyinstaller ^
    --onefile ^
    --noconsole ^
    --clean ^
    --name Chintu ^
    --uac-admin ^
    --hidden-import=PyQt6.QtCore ^
    --hidden-import=PyQt6.QtGui ^
    --hidden-import=PyQt6.QtWidgets ^
    --hidden-import=speech_recognition ^
    --hidden-import=pyaudio ^
    --hidden-import=pyautogui ^
    --hidden-import=selenium ^
    --hidden-import=web_automation ^
    --hidden-import=audio_engine ^
    --hidden-import=core_automation ^
    main.py

echo.

REM --- Move to real_app directory ---
echo [3/4] Packaging into real_app\ ...

if not exist "real_app" mkdir "real_app"

if exist "dist\Chintu.exe" (
    copy /Y "dist\Chintu.exe" "real_app\Chintu.exe"
    echo       Binary: real_app\Chintu.exe
) else (
    echo       [ERROR] Build failed! dist\Chintu.exe not found.
    echo       Check the output above for errors.
    pause
    exit /b 1
)

echo.

REM --- Summary ---
echo [4/4] BUILD SUCCESSFUL!
echo.
echo   Output directory:  real_app\
echo   Binary:            real_app\Chintu.exe
echo.
echo   To run:
echo       real_app\Chintu.exe
echo.
echo   Or double-click Chintu.exe in the real_app folder.
echo.
echo ============================================================
echo   Build complete.
echo ============================================================
echo.
pause

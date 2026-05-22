#!/bin/bash
# ============================================================================
#  Chintu Voice Assistant — Linux Build Script
# ============================================================================
#  Creates a venv, installs everything, then runs PyInstaller THROUGH
#  the venv's own Python so that all packages are visible to the bundler.
#
#  Output:  real_app/Chintu
#
#  Usage:
#    chmod +x build_linux.sh
#    ./build_linux.sh
# ============================================================================

set -e

echo ""
echo "============================================================"
echo "  CHINTU VOICE ASSISTANT — LINUX BUILD SYSTEM"
echo "============================================================"
echo ""

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Absolute path to venv python — this is THE critical variable.
# We use this for EVERY python/pip call to guarantee we never
# accidentally use the system Python.
VENV_DIR="$SCRIPT_DIR/venv"
VENV_PY="$VENV_DIR/bin/python"
VENV_PIP="$VENV_DIR/bin/pip"

# ── Step 1: Clean previous builds ──────────────────────────────────────
echo "[1/5] Cleaning previous build artifacts..."
rm -rf build/ dist/ *.spec
echo "      Done."
echo ""

# ── Step 2: Create venv & install packages ─────────────────────────────
echo "[2/5] Setting up Python virtual environment..."

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "      System Python: $PYTHON_VERSION"

# Create fresh venv with access to system site-packages (for PyQt6 etc.)
if [ -d "$VENV_DIR" ]; then
    echo "      Removing old venv..."
    rm -rf "$VENV_DIR"
fi

echo "      Creating venv..."
python3 -m venv --system-site-packages "$VENV_DIR"

echo "      Venv Python: $($VENV_PY --version)"

# Install all dependencies into the venv
echo "      Installing packages into venv..."
"$VENV_PIP" install --upgrade pip > /dev/null 2>&1
"$VENV_PIP" install \
    SpeechRecognition \
    PyAudio \
    pyautogui \
    selenium \
    webdriver-manager \
    pyinstaller \
    PyQt6

echo "      Packages installed."

# ── Verify critical imports work from the venv ─────────────────────────
echo ""
echo "      Verifying critical imports..."
"$VENV_PY" -c "import speech_recognition; print('        ✓ speech_recognition')"
"$VENV_PY" -c "import PyQt6; print('        ✓ PyQt6')"
"$VENV_PY" -c "import PyInstaller; print('        ✓ PyInstaller')" || true
# pyautogui and selenium need a display — skip verification in headless build
echo "        ✓ pyautogui (skipped — needs display)"
echo "        ✓ selenium  (skipped — needs display)"
echo ""

# ── Step 3: Build with PyInstaller THROUGH THE VENV PYTHON ────────────
#
#    THIS IS THE KEY: we run "venv/bin/python -m PyInstaller" so that
#    PyInstaller sees ALL packages installed in the venv.
#    Using bare "pyinstaller" would invoke /usr/bin/pyinstaller which
#    uses system Python and can't see venv packages.
#
echo "[3/5] Running PyInstaller via venv Python..."
echo "      (using: $VENV_PY -m PyInstaller)"
echo ""

"$VENV_PY" -m PyInstaller \
    --onefile \
    --windowed \
    --clean \
    --name Chintu \
    --exclude-module=PyQt5 \
    --exclude-module=_tkinter \
    --exclude-module=tkinter \
    --hidden-import=speech_recognition \
    --hidden-import=pyaudio \
    --hidden-import=pyautogui \
    --hidden-import=selenium \
    --hidden-import=PyQt6 \
    --hidden-import=PyQt6.QtCore \
    --hidden-import=PyQt6.QtGui \
    --hidden-import=PyQt6.QtWidgets \
    --hidden-import=web_automation \
    --hidden-import=audio_engine \
    --hidden-import=core_automation \
    --collect-all=speech_recognition \
    --collect-all=selenium \
    --collect-all=webdriver_manager \
    main.py

echo ""

# ── Step 4: Package into real_app/ ─────────────────────────────────────
echo "[4/5] Packaging into real_app/ ..."

mkdir -p real_app

if [ -f "dist/Chintu" ]; then
    cp dist/Chintu real_app/Chintu
    chmod +x real_app/Chintu
    echo "      Binary: real_app/Chintu"
else
    echo "      [ERROR] Build failed! dist/Chintu not found."
    exit 1
fi

# ── .desktop file ──────────────────────────────────────────────────────
cat > real_app/chintu.desktop << 'DESKTOP_EOF'
[Desktop Entry]
Version=1.0
Type=Application
Name=Chintu Voice Assistant
Comment=AI-powered bilingual voice assistant
Exec=PLACEHOLDER_PATH
Icon=utilities-terminal
Terminal=false
Categories=Utility;Accessibility;
StartupNotify=true
DESKTOP_EOF

REAL_APP_DIR="$(cd real_app && pwd)"
sed -i "s|PLACEHOLDER_PATH|${REAL_APP_DIR}/Chintu|g" real_app/chintu.desktop
chmod +x real_app/chintu.desktop

# ── install.sh ─────────────────────────────────────────────────────────
cat > real_app/install.sh << 'INSTALL_EOF'
#!/bin/bash
set -e
INSTALL_DIR="/opt/chintu"
BIN_LINK="/usr/local/bin/chintu"
DESKTOP_DIR="/usr/share/applications"

echo "[*] Installing Chintu Voice Assistant..."
mkdir -p "$INSTALL_DIR"
cp Chintu "$INSTALL_DIR/Chintu"
chmod +x "$INSTALL_DIR/Chintu"
ln -sf "$INSTALL_DIR/Chintu" "$BIN_LINK"
cp chintu.desktop "$DESKTOP_DIR/chintu.desktop"
sed -i "s|Exec=.*|Exec=$INSTALL_DIR/Chintu|g" "$DESKTOP_DIR/chintu.desktop"
update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
echo "[✓] Installed to $INSTALL_DIR"
echo "[✓] Run from terminal:  chintu"
echo "[✓] Or find 'Chintu Voice Assistant' in your app menu."
INSTALL_EOF

chmod +x real_app/install.sh
echo "      Desktop file + installer created."
echo ""

# ── Step 5: Summary ───────────────────────────────────────────────────
BINARY_SIZE=$(du -h real_app/Chintu | cut -f1)
echo "[5/5] BUILD SUCCESSFUL!"
echo ""
echo "      Output:  real_app/Chintu  ($BINARY_SIZE)"
echo ""
echo "  Run directly:      ./real_app/Chintu"
echo "  System install:    cd real_app && sudo ./install.sh"
echo ""
echo "============================================================"

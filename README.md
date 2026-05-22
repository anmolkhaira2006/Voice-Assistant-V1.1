# 🤖 Chintu Voice Assistant V1.1

**A production-ready, bilingual (English + Hindi) desktop voice assistant with a cyberpunk overlay UI, shell command execution, web automation, and OS control.**

Chintu runs as a floating overlay bar at the top of your screen, listens for a wake word, and executes voice commands — from opening apps and searching files to checking your Gmail and running terminal commands.

---

## ✨ Features

### 🎙️ Voice Recognition (Push-to-Talk)
- **Push-to-Talk** — Click the 🎙 mic button to instantly capture your command (no constant background listening)
- **Bilingual support** — Understands both **English** and **Hindi** (including Hinglish)
- **Google Web Speech API** — Accurate transcription via cloud speech recognition
- **Google Web Speech API** — Accurate transcription via cloud speech recognition

### 🖥️ OS Control
- **Open applications** — *"Open Notepad"*, *"Kholo Calculator"*, *"Launch Firefox"*
- **Close windows** — *"Close app"*, *"Band karo"* → sends Alt+F4
- **Minimize / Maximize** — *"Minimize"*, *"Bada karo"*, *"Full screen"*
- **Volume control** — *"Volume up"*, *"Awaz kam karo"*, *"Mute"*
- **Screenshot** — *"Take screenshot"*, *"Screenshot lo"*
- **Lock screen** — *"Lock screen"*, *"Lock karo"*
- **Shutdown / Restart** — *"Shutdown"*, *"Restart"*, *"Dubara chalu karo"*

### 💻 Shell Command Execution (with Permission)
- **Run any terminal command by voice** — *"Run command ls -la"*, *"Execute whoami"*
- **Permission dialog** — Shows the exact command being executed and requires explicit **✓ Approve** or **✗ Deny** before running
- **Input Sanitization (Security)** — Automatically blocks potentially dangerous or destructive shell commands (like `rm -rf` or `mkfs`) to protect your system
- **Output display** — Shows command output/exit code in the overlay bar
- **30-second timeout** — Prevents hung processes
- **Hindi support** — *"Command chalao ifconfig"*, *"Terminal me nmap --help"*

### 🌐 Web Automation (Selenium)
- **Check Gmail** — *"Check my Gmail"*, *"Read last email"* → Opens Gmail, reads sender/subject of latest email
- **YouTube search** — *"YouTube search lo-fi music"*, *"YouTube pe chalao coding tutorial"*
- **Google search** — *"Google search Python tutorial"*
- **Open websites** — *"Open WhatsApp"*, *"Check Instagram"*, *"Open GitHub"*
- **Navigate anywhere** — *"Go to stackoverflow.com"*
- **Uses your existing browser profile** — Already logged in, no passwords needed

### 📁 Local File Search
- **Find files by voice** — *"Find resume"*, *"Dhundho report"*, *"Search for notes.txt"*
- **Scans user directories** — Desktop, Documents, Downloads, Pictures, Videos, Music
- **Auto-opens** — Instantly opens the first matching file with the default app

### 🎯 Gemini AI Agentic Execution
- **Invisible Background Scraping** — No browser windows pop up! Chintu securely uses a headless Selenium instance to retrieve answers from Gemini behind the scenes.
- **Beautiful In-App Chat Box** — Gemini's text responses smoothly expand downwards directly within Chintu's UI, rendered with full Markdown support (beautiful headers, code blocks, and rich text).
- **Generate & Run Commands** — Say *"Gemini run an aggressive nmap scan"* and Chintu will invisibly scrape the command from Gemini and ask for your permission to run it.
- **Contextual Execution** — After asking Gemini a question via Chintu, you can say *"Run it"* or *"Execute that"* to automatically run the command it provided.
- **Ask Gemini** — *"Ask Gemini what is quantum computing"* (Displays answer in UI)
- **Fallback routing** — Any unrecognised command is automatically sent to Gemini as a background query.

### 🎨 Cyberpunk Overlay UI
- **Draggable Pill Bar** — Click and drag the `≡` grip to move the overlay anywhere on your screen.
- **Manual Minimize** — Click the `−` button to instantly hide the chat output and restore the pill bar size.
- **Auto-Minimize (Sleep Mode)** — After 30 seconds of inactivity, the UI shrinks into a small glowing dot at the bottom of your screen. Click it to wake it up!
- **Interactive Text Input** — Type commands directly into the pill bar.
- **Animated gradient border** — 30Hz colour-cycling (Apple Intelligence style)
- **Neon glow effects** — Cyan idle glow → Magenta active glow
- **Monospaced terminal font** — JetBrains Mono / Fira Code / DejaVu Sans Mono

---

## 📁 Project Structure

```
Chintu_Assistant/
├── main.py              ← Application entry point & PyQt6 overlay UI
├── audio_engine.py      ← Wake word detection & speech-to-text
├── core_automation.py   ← Intent routing, OS actions, shell commands
├── web_automation.py    ← Selenium browser automation (Gmail, YouTube, etc.)
├── requirements.txt     ← Python dependencies
├── build_linux.sh       ← Linux/Kali build script → outputs to real_app/
├── build_exe.bat        ← Windows build script → outputs to real_app/
├── real_app/            ← [Generated] Standalone executables
│   ├── Chintu           ← Linux binary
│   ├── Chintu.exe       ← Windows binary
│   ├── chintu.desktop   ← Linux desktop shortcut
│   └── install.sh       ← Linux system-wide installer
└── README.md            ← This file
```

---

## 🚀 Installation & Setup

### Kali Linux (Primary)

#### 1. Install System Dependencies

```bash
sudo apt-get update
sudo apt-get install -y \
    portaudio19-dev \
    python3-pyaudio \
    python3-dev \
    python3-pip \
    python3-pyqt6 \
    firefox-esr \
    xdg-utils
```

#### 2. Install Python Dependencies

```bash
cd Chintu_Assistant
pip3 install -r requirements.txt
```

#### 3. Run Chintu

```bash
python3 main.py
```

#### 4. Build Standalone Binary (Optional)

```bash
chmod +x build_linux.sh
./build_linux.sh
```

The standalone binary will be in `real_app/Chintu`. You can run it directly:

```bash
./real_app/Chintu
```

Or install system-wide:

```bash
cd real_app
sudo ./install.sh
# Now run from anywhere:
chintu
```

---

### Windows

#### 1. Install Python 3.10+

Download from [python.org](https://www.python.org/downloads/). Make sure to check **"Add Python to PATH"** during installation.

#### 2. Install Dependencies

```cmd
cd Chintu_Assistant
pip install -r requirements.txt
```

#### 3. Run Chintu

```cmd
python main.py
```

#### 4. Build Standalone .exe (Optional)

Double-click `build_exe.bat` or run from terminal:

```cmd
build_exe.bat
```

The executable will be at `real_app\Chintu.exe`.

---

## 🎤 Voice Command Reference

### System Commands

| Say this (English) | Say this (Hindi) | Action |
|---|---|---|
| "Help", "Commands" | "Commands dikhao" | Expands UI to show the full command cheat sheet |
| *(Click Mic Button)* | *(Click Mic Button)* | Push-to-talk activation |
| "Open Notepad" | "Kholo Notepad" | Opens an application |
| "Close app" | "Band karo" | Closes active window (Alt+F4) |
| "Minimize" | "Neeche karo" | Minimizes active window |
| "Maximize" | "Bada karo" | Maximizes active window |
| "Volume up" | "Awaz badhao" | Increases volume |
| "Volume down" | "Awaz kam karo" | Decreases volume |
| "Mute" | "Chup karo" | Toggles mute |
| "Take screenshot" | "Screenshot lo" | Opens screenshot tool |
| "Lock screen" | "Lock karo" | Locks the workstation |
| "Shutdown" | "Computer band karo" | Shuts down (with grace period) |
| "Restart" | "Dubara chalu karo" | Restarts the system |

### Shell Commands (Requires Approval)

| Say this | Extracted Command |
|---|---|
| "Run command ls -la" | `ls -la` |
| "Execute whoami" | `whoami` |
| "Terminal command ping google.com" | `ping google.com` |
| "Shell ifconfig" | `ifconfig` |
| "Command chalao nmap -sP 192.168.1.0/24" | `nmap -sP 192.168.1.0/24` |
| "Terminal me cat /etc/hostname" | `cat /etc/hostname` |

> ⚠️ **Security**: A confirmation dialog always appears showing the exact command before execution. You must click **✓ APPROVE** to run it.

### Web Automation

| Say this | Action |
|---|---|
| "Check my Gmail" | Opens Gmail, reads latest email sender & subject |
| "Read last email" | Same as above |
| "YouTube search lo-fi music" | Searches YouTube |
| "Open WhatsApp" | Opens WhatsApp Web |
| "Check Twitter" | Opens X (Twitter) |
| "Open Instagram" | Opens Instagram |
| "Go to stackoverflow.com" | Navigates to the URL |
| "Google search Python tutorial" | Performs a Google search |

### File Search

| Say this (English) | Say this (Hindi) | Action |
|---|---|---|
| "Find resume" | "Dhundho resume" | Searches & opens matching file |
| "Search for notes.txt" | "Khojo notes" | Searches & opens matching file |
| "Find file report" | "File dhundho report" | Searches & opens matching file |

### AI Queries

| Say this | Action |
|---|---|
| "Gemini run an aggressive nmap scan" | Scrapes command from Gemini and asks to execute it |
| "Execute it" / "Run that" | Executes the last scraped Gemini command |
| "Ask Gemini what is quantum computing" | Invisibly fetches answer and displays in UI chat box |
| "Gemini se pucho AI kya hai" | Invisibly fetches answer and displays in UI chat box |
| (any unrecognised command) | Automatically sent to Gemini |

---

## 🖥️ Platform Compatibility

| Feature | Windows | Kali Linux | Notes |
|---|---|---|---|
| Voice Recognition | ✅ | ✅ | Requires internet for Google API |
| Wake Word | ✅ | ✅ | "Hey Chintu" / "Chintu" |
| Overlay UI | ✅ | ✅ | PyQt6 works on both |
| Open Apps | ✅ | ✅ | Platform-specific app mapping |
| Close/Min/Max | ✅ | ✅ | Uses pyautogui hotkeys |
| Volume Control | ✅ | ✅ | Volume keys via pyautogui |
| Shell Commands | ✅ | ✅ | Permission dialog on both |
| Gmail Check | ✅ | ✅ | Selenium + user profile |
| YouTube Search | ✅ | ✅ | Selenium + user profile |
| File Search | ✅ | ✅ | xdg-open on Linux, startfile on Windows |
| Screenshot | ✅ | ✅ | OS-native tools |
| Lock Screen | ✅ | ✅ | LockWorkStation / loginctl |
| Build to Binary | ✅ .exe | ✅ ELF | PyInstaller on both |
| System Install | N/A | ✅ | install.sh for Kali |

### Kali Linux-Specific Apps

Chintu knows about common Kali tools:
- *"Open Burp Suite"* → launches `burpsuite`
- *"Open Wireshark"* → launches `wireshark`
- *"Open Metasploit"* → launches `msfconsole`
- *"Open Terminal"* → launches `x-terminal-emulator` or `qterminal`

---

## 🔧 Troubleshooting

### Microphone not detected
```bash
# Check if PulseAudio is running
pulseaudio --check && echo "OK" || pulseaudio --start

# List available audio devices
python3 -c "import speech_recognition as sr; print(sr.Microphone.list_microphone_names())"
```

### PyAudio installation fails
```bash
# Kali Linux / Debian
sudo apt-get install -y portaudio19-dev python3-pyaudio

# If pip install still fails:
pip3 install --no-build-isolation pyaudio
```

### PyQt6 not rendering properly
```bash
# Install Qt6 dependencies
sudo apt-get install -y libqt6widgets6 qt6-base-dev

# If using Wayland, try forcing X11:
export QT_QPA_PLATFORM=xcb
python3 main.py
```

### Selenium browser not starting
```bash
# Install Firefox driver manager (auto-downloads geckodriver)
pip3 install webdriver-manager

# Or install geckodriver manually on Kali:
sudo apt-get install -y firefox-esr
```

### "No module named 'web_automation'" error
Make sure all `.py` files are in the same directory. If running from a different directory:
```bash
cd /path/to/Chintu_Assistant && python3 main.py
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    main.py (PyQt6 UI)                       │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────────┐  │
│  │ Pill Bar     │  │ Glow Effect  │  │ Confirm Dialog    │  │
│  │ Overlay      │  │ Animation    │  │ (Shell Commands)  │  │
│  └──────┬───────┘  └──────────────┘  └───────────────────┘  │
│         │                                                    │
│    ┌────▼────────────────────┐                               │
│    │  audio_engine.py        │◄─── Background QThread        │
│    │  (Wake Word + STT)      │     PyQt Signals              │
│    └────┬────────────────────┘                               │
│         │ command text                                       │
│    ┌────▼────────────────────┐                               │
│    │  core_automation.py     │◄─── Intent Router             │
│    │  (The Brain)            │     ActionResult               │
│    └────┬───────┬───────┬────┘                               │
│         │       │       │                                    │
│    ┌────▼──┐ ┌──▼────┐ ┌▼──────────────────┐                │
│    │ OS    │ │ Shell │ │ web_automation.py  │                │
│    │ Cmds  │ │ Exec  │ │ (Selenium)         │                │
│    └───────┘ └───────┘ └───────────────────┘                │
└─────────────────────────────────────────────────────────────┘
```

---

## 📜 License

This project is provided as-is for educational and personal use.

---

*Built with ❤️ for Kali Linux and Windows*

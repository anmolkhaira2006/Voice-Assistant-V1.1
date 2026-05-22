# ============================================================================
#  core_automation.py — "The Brain & Hands"
# ============================================================================
#  Chintu Voice Assistant — Core Automation Engine
#
#  This module is the central nervous system of Chintu.  It receives
#  transcribed text from the audio engine, determines the user's intent,
#  and dispatches the appropriate action:
#
#    • OS Actions         — Launch native apps, close windows, system controls
#    • Local File Search  — Recursively scan user directories for files
#    • Web Automation     — Open Gemini or perform web searches
#    • Shell Commands     — Execute terminal commands WITH user confirmation
#
#  The intent router uses keyword matching with ranked priority so that
#  more specific intents (like "open notepad") take precedence over
#  generic ones (like "search for X").
#
#  SECURITY NOTE:
#    Shell commands are NEVER executed directly.  The router returns an
#    ActionResult with `needs_confirmation=True` and the UI must display
#    a confirmation dialog before calling `execute_confirmed_shell()`.
# ============================================================================

import os
import sys
import glob
import subprocess
import webbrowser
import urllib.parse
import platform
from dataclasses import dataclass, field

# Web automation module — Selenium-based browser tasks
try:
    from web_automation import perform_web_task, close_driver, scrape_gemini_command, scrape_gemini_text
    WEB_AUTOMATION_AVAILABLE = True
except ImportError:
    WEB_AUTOMATION_AVAILABLE = False
    def perform_web_task(task): return "[ERROR] web_automation module not found."
    def close_driver(): pass
    def scrape_gemini_command(query): return ""
    def scrape_gemini_text(query): return ""

LAST_GEMINI_QUERY = ""

# pyautogui is used for simulating keyboard shortcuts (Alt+F4, etc.)
# IMPORTANT: We do NOT import pyautogui at module level because it tries
# to connect to the X11 display on import, which crashes the app if the
# display isn't ready yet (common with sudo, SSH, or Wayland).
# Instead, we lazy-load it the first time a keyboard action is needed.
_pyautogui = None  # Cached reference

def _get_pyautogui():
    """
    Lazy-load pyautogui on first use.  Returns the module or None if
    it can't be imported or can't connect to the display.
    """
    global _pyautogui
    if _pyautogui is not None:
        return _pyautogui
    try:
        import pyautogui
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.3
        _pyautogui = pyautogui
        return _pyautogui
    except Exception:
        return None


# ============================================================================
#  ACTION RESULT — Structured return type for all intents
# ============================================================================

@dataclass
class ActionResult:
    """
    Structured result from the intent router.

    Attributes
    ----------
    message : str
        Human-readable status / result message for UI display.
    needs_confirmation : bool
        If True, the action requires explicit user approval before
        execution (used for shell commands).
    pending_command : str or None
        The shell command awaiting confirmation.  Only set when
        needs_confirmation is True.
    """
    message: str
    needs_confirmation: bool = False
    pending_command: str | None = None
    needs_gemini_scrape: bool = False
    needs_gemini_chat: bool = False
    pending_query: str | None = None
    needs_help_ui: bool = False


# ============================================================================
#  CONFIGURATION
# ============================================================================

# Gemini URL for "ask gemini" commands
GEMINI_URL = "https://gemini.google.com"

# Application mapping — maps spoken keywords to executable paths / commands.
# On Windows, many apps are on PATH or in known locations.
# On Linux, we use common binary names.  Kali-specific tools are included.
APP_MAP = {
    # ── Editors / Utilities ─────────────────────────────────────────────
    "notepad":        "notepad.exe"     if sys.platform == "win32" else "mousepad",
    "text editor":    "notepad.exe"     if sys.platform == "win32" else "mousepad",
    "calculator":     "calc.exe"        if sys.platform == "win32" else "gnome-calculator",
    "paint":          "mspaint.exe"     if sys.platform == "win32" else "kolourpaint",

    # ── File Managers ───────────────────────────────────────────────────
    "explorer":       "explorer.exe"    if sys.platform == "win32" else "thunar",
    "file manager":   "explorer.exe"    if sys.platform == "win32" else "thunar",
    "files":          "explorer.exe"    if sys.platform == "win32" else "thunar",

    # ── Terminals ───────────────────────────────────────────────────────
    "terminal":       "cmd.exe"         if sys.platform == "win32" else "x-terminal-emulator",
    "command prompt": "cmd.exe"         if sys.platform == "win32" else "x-terminal-emulator",
    "powershell":     "powershell.exe"  if sys.platform == "win32" else "bash",
    "konsole":        "cmd.exe"         if sys.platform == "win32" else "qterminal",

    # ── Browsers ────────────────────────────────────────────────────────
    "browser":        "chrome"          if sys.platform == "win32" else "firefox",
    "chrome":         "chrome"          if sys.platform == "win32" else "google-chrome",
    "firefox":        "firefox.exe"     if sys.platform == "win32" else "firefox-esr",

    # ── Office ──────────────────────────────────────────────────────────
    "word":           "winword.exe"     if sys.platform == "win32" else "libreoffice --writer",
    "excel":          "excel.exe"       if sys.platform == "win32" else "libreoffice --calc",

    # ── System ──────────────────────────────────────────────────────────
    "settings":       "ms-settings:"    if sys.platform == "win32" else "xfce4-settings-manager",
    "task manager":   "taskmgr.exe"     if sys.platform == "win32" else "xfce4-taskmanager",
    "system monitor": "taskmgr.exe"     if sys.platform == "win32" else "xfce4-taskmanager",
    "screenshot":     "snippingtool.exe" if sys.platform == "win32" else "xfce4-screenshooter",

    # ── Kali Linux Specific Tools ───────────────────────────────────────
    "burp":           "burpsuite"       if sys.platform != "win32" else "burpsuite",
    "burp suite":     "burpsuite"       if sys.platform != "win32" else "burpsuite",
    "wireshark":      "wireshark"       if sys.platform != "win32" else "wireshark",
    "metasploit":     "msfconsole"      if sys.platform != "win32" else "msfconsole",
    "nmap":           "zenmap"          if sys.platform != "win32" else "zenmap",
}

# Directories to search for local files.
# Dynamically resolved based on the user's home directory.
def _get_search_directories() -> list[str]:
    """
    Return a list of common user directories to scan for file searches.
    Falls back gracefully if directories don't exist.
    """
    home = os.path.expanduser("~")
    candidates = [
        os.path.join(home, "Desktop"),
        os.path.join(home, "Documents"),
        os.path.join(home, "Downloads"),
        os.path.join(home, "Pictures"),
        os.path.join(home, "Videos"),
        os.path.join(home, "Music"),
        home,  # Search home directory itself (shallow)
    ]
    return [d for d in candidates if os.path.isdir(d)]


SEARCH_DIRECTORIES = _get_search_directories()

# Shell command timeout (seconds) — prevents hung processes
SHELL_TIMEOUT = 30


# ============================================================================
#  INTENT ROUTER — The core dispatcher
# ============================================================================

def route_intent(command: str) -> ActionResult:
    """
    Analyse the transcribed command text and dispatch the appropriate
    action.  Returns an ActionResult with the status message and
    optional confirmation requirement.

    The intent matching is evaluated in priority order:
      1. System / UI actions    (close, minimize, volume, shutdown)
      2. Shell / terminal cmd   (run command ..., execute ...) — NEEDS CONFIRM
      3. Open application       (open notepad, launch calculator, ...)
      4. Local file search      (find <filename>, search for <filename>)
      5. Gemini / web query     (ask gemini ..., search ..., or fallback)

    Parameters
    ----------
    command : str
        Lowercase transcribed command text.

    Returns
    -------
    ActionResult
        Structured result with message, confirmation flag, and pending cmd.
    """
    cmd = command.strip().lower()

    # ── 0. HELP COMMAND ─────────────────────────────────────────────────
    if _match_any(cmd, ["help", "commands", "show commands", "what can you do", "commands dikhao", "help me"]):
        return ActionResult("Displaying help menu...", needs_help_ui=True)

    # ── 1. SYSTEM / UI ACTIONS ──────────────────────────────────────────
    if _match_any(cmd, ["close app", "close window", "close this",
                        "band karo", "band kar do", "close karo"]):
        return _action_close_window()

    if _match_any(cmd, ["minimize", "minimise", "minimize karo",
                        "neeche karo"]):
        return _action_minimize_window()

    if _match_any(cmd, ["maximize", "maximise", "maximize karo",
                        "full screen", "bada karo"]):
        return _action_maximize_window()

    if _match_any(cmd, ["volume up", "awaz badhao", "volume badhao"]):
        return _action_volume_up()

    if _match_any(cmd, ["volume down", "awaz kam karo", "volume kam karo"]):
        return _action_volume_down()

    if _match_any(cmd, ["mute", "volume mute", "awaz band karo",
                        "chup karo"]):
        return _action_mute()

    if _match_any(cmd, ["shutdown", "shut down", "band karo computer",
                        "computer band karo"]):
        return _action_shutdown()

    if _match_any(cmd, ["restart", "reboot", "dubara chalu karo"]):
        return _action_restart()

    # ── 1.5 SYSTEM CONTROL ──────────────────────────────────────────────
    if cmd in ["lock", "lock screen", "lock karo", "screen lock karo", "lock the screen", "lock the system"] or cmd.startswith("lock "):
        return _action_lock_screen()

    if _match_any(cmd, ["screenshot", "screen capture", "take screenshot",
                        "screenshot lo", "screenshot lelo"]):
        return _action_screenshot()

    # ── 2. SHELL / TERMINAL COMMANDS (requires confirmation) ────────────
    #    Triggers: "run command ...", "execute command ...",
    #              "terminal command ...", "shell ...",
    #              "command chalao ...", "terminal me ..."
    if _starts_with_any(cmd, ["run command ", "execute command ",
                              "terminal command ", "shell command ",
                              "shell ", "command chalao ",
                              "terminal me ", "terminal mein ",
                              "execute ", "command run "]):
        shell_cmd = _extract_after(cmd, [
            "run command ", "execute command ",
            "terminal command ", "shell command ",
            "command chalao ", "terminal me ",
            "terminal mein ", "command run ",
            "shell ", "execute ",
        ])
        return _action_request_shell(shell_cmd)

    # ── 2.5 AI / GEMINI COMMAND GENERATION ──────────────────────────────
    if _starts_with_any(cmd, ["gemini run ", "gemini command ", "ai run ", "ai command ", "generate command "]):
        task = _extract_after(cmd, ["gemini run ", "gemini command ", "ai run ", "ai command ", "generate command "])
        return _action_gemini_shell(task)
    
    if _starts_with_any(cmd, ["run a ", "execute a "]) and _match_any(cmd, ["query", "scan", "script", "command", "task"]):
        task = _extract_after(cmd, ["run a ", "execute a "])
        return _action_gemini_shell(task)

    # ── 2.6 CONTEXTUAL EXECUTE ──────────────────────────────────────────
    if _match_any(cmd, ["run it", "execute it", "run that", "execute that", "chalao isko"]):
        return _action_run_last_scraped()

    # ── 3. WEB TASKS (Gmail, YouTube, etc.) ──────────────────────────────
    #    These take priority over generic "open" commands so that
    #    "check my gmail" is not misrouted to _action_open_app.
    if _match_any(cmd, ["check gmail", "check my gmail", "check email",
                        "check my email", "read email", "read my email",
                        "gmail check karo", "email check karo",
                        "gmail kholo", "email dikhao",
                        "read last email", "last email",
                        "latest email", "new email",
                        "inbox check karo",
                        "check whatsapp", "whatsapp check karo",
                        "open whatsapp", "whatsapp kholo",
                        "check twitter", "open twitter",
                        "check instagram", "open instagram",
                        "open github", "check github",
                        "open youtube", "youtube kholo"]):
        return _action_web_task(cmd)

    if _starts_with_any(cmd, ["youtube search ", "youtube pe ",
                              "youtube par ", "play on youtube ",
                              "youtube me dhundho ",
                              "youtube pe chalao ",
                              "google search ", "google pe dhundho ",
                              "open website ", "open site ",
                              "go to ", "navigate to ",
                              "website kholo "]):
        return _action_web_task(cmd)

    # ── 4. OPEN APPLICATION ─────────────────────────────────────────────
    if _starts_with_any(cmd, ["open ", "launch ", "start ", "run ",
                              "kholo ", "chalu karo "]):
        # Extract the app name from the command
        app_name = _extract_after(cmd, ["open ", "launch ", "start ",
                                        "run ", "kholo ", "chalu karo "])
        return _action_open_app(app_name)

    # ── 5. LOCAL FILE SEARCH ────────────────────────────────────────────
    if _starts_with_any(cmd, ["find ", "search for ", "find file ",
                              "search file ", "locate ",
                              "dhundho ", "file dhundho ",
                              "khojo "]):
        query = _extract_after(cmd, ["find file ", "search file ",
                                     "search for ", "find ", "locate ",
                                     "file dhundho ", "dhundho ",
                                     "khojo "])
        return _action_file_search(query)

    # ── 6. GEMINI / WEB QUERY ──────────────────────────────────────────
    if _starts_with_any(cmd, ["ask gemini ", "gemini ", "gemini se pucho ",
                              "gemini ko bolo "]):
        query = _extract_after(cmd, ["ask gemini ", "gemini ",
                                     "gemini se pucho ",
                                     "gemini ko bolo "])
        return _action_ask_gemini(query)

    if _starts_with_any(cmd, ["search ", "google ", "google karo ",
                              "web search "]):
        query = _extract_after(cmd, ["search ", "google ",
                                     "google karo ", "web search "])
        return _action_web_search(query)

    # ── 7. FALLBACK — Treat entire command as a Gemini query ───────────
    return _action_ask_gemini(cmd)


# ============================================================================
#  WEB TASK ACTION
# ============================================================================

def _action_web_task(task: str) -> ActionResult:
    """
    Delegate a web task to the Selenium-based web_automation module.

    Parameters
    ----------
    task : str
        The full spoken command describing the web task.

    Returns
    -------
    ActionResult
    """
    result_msg = perform_web_task(task)
    return ActionResult(result_msg)


# ============================================================================
#  SHELL COMMAND EXECUTION (with confirmation gate)
# ============================================================================

def _action_request_shell(shell_cmd: str) -> ActionResult:
    """
    Prepare a shell command for execution.  Does NOT execute it — instead
    returns an ActionResult with needs_confirmation=True so the UI can
    show a permission dialog.

    Parameters
    ----------
    shell_cmd : str
        The command string to execute in the system shell.

    Returns
    -------
    ActionResult
        With needs_confirmation=True and the pending command.
    """
    shell_cmd = shell_cmd.strip()
    if not shell_cmd:
        return ActionResult("[ERROR] No command provided.")

    # ── Input Sanitisation (Security Check) ─────────────────────────
    dangerous_patterns = [
        "rm -rf /", "mkfs", "dd if=", ":(){ :|:& };:", "> /dev/sda",
        "mv / /dev/null", "chmod 777 /"
    ]
    for pattern in dangerous_patterns:
        if pattern in shell_cmd:
            return ActionResult(f"[SECURITY ALERT] Blocked dangerous pattern: {pattern}")

    return ActionResult(
        message=f"[CONFIRM] Execute: $ {shell_cmd}",
        needs_confirmation=True,
        pending_command=shell_cmd,
    )


def _action_gemini_shell(task: str) -> ActionResult:
    """Request a background scrape from Gemini to generate a command."""
    global LAST_GEMINI_QUERY
    LAST_GEMINI_QUERY = task
    return ActionResult(
        message="[SCRAPING] Generating command via Gemini...",
        needs_gemini_scrape=True,
        pending_query=task
    )


def _action_run_last_scraped() -> ActionResult:
    """Run the command for the last asked Gemini query."""
    global LAST_GEMINI_QUERY
    if not LAST_GEMINI_QUERY:
        return ActionResult("[ERROR] No recent Gemini query in memory.")
    return _action_gemini_shell(LAST_GEMINI_QUERY)


def execute_confirmed_shell(shell_cmd: str) -> str:
    """
    Execute a shell command AFTER the user has confirmed it via the
    permission dialog.  Captures stdout/stderr and returns truncated
    output for display in the pill bar.

    This function is called from main.py ONLY after the user clicks
    "Approve" in the confirmation dialog.

    Parameters
    ----------
    shell_cmd : str
        The confirmed command to execute.

    Returns
    -------
    str
        Truncated output or error message.
    """
    try:
        result = subprocess.run(
            shell_cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=SHELL_TIMEOUT,
            cwd=os.path.expanduser("~"),  # Run from home directory
        )

        # Combine stdout and stderr
        output = result.stdout.strip()
        errors = result.stderr.strip()

        if result.returncode == 0:
            if output:
                # Return first meaningful line of output
                first_lines = output.split("\n")[:3]
                preview = " | ".join(line.strip() for line in first_lines if line.strip())
                return f"[OK exit:0] {preview}"
            else:
                return f"[OK exit:0] Command completed successfully."
        else:
            err_preview = errors.split("\n")[0] if errors else "Unknown error"
            return f"[FAIL exit:{result.returncode}] {err_preview}"

    except subprocess.TimeoutExpired:
        return f"[TIMEOUT] Command exceeded {SHELL_TIMEOUT}s limit."
    except Exception as exc:
        return f"[ERROR] {exc}"


# ============================================================================
#  ACTION IMPLEMENTATIONS
# ============================================================================

# ── System / UI Actions ─────────────────────────────────────────────────────

def _action_close_window() -> ActionResult:
    """Simulate Alt+F4 to close the currently focused window."""
    pag = _get_pyautogui()
    if pag:
        pag.hotkey("alt", "F4")
        return ActionResult("[ACTION] Sent Alt+F4 — closing active window.")
    return ActionResult("[ERROR] pyautogui not available for keyboard simulation.")


def _action_minimize_window() -> ActionResult:
    """Simulate Win+Down to minimize the active window (Windows)."""
    pag = _get_pyautogui()
    if pag:
        if sys.platform == "win32":
            pag.hotkey("win", "down")
        else:
            pag.hotkey("super", "h")  # GNOME/XFCE minimize
        return ActionResult("[ACTION] Minimized active window.")
    return ActionResult("[ERROR] pyautogui not available.")


def _action_maximize_window() -> ActionResult:
    """Simulate Win+Up to maximize the active window (Windows)."""
    pag = _get_pyautogui()
    if pag:
        if sys.platform == "win32":
            pag.hotkey("win", "up")
        else:
            pag.hotkey("super", "up")
        return ActionResult("[ACTION] Maximized active window.")
    return ActionResult("[ERROR] pyautogui not available.")


def _action_volume_up() -> ActionResult:
    """Press the Volume Up key twice."""
    pag = _get_pyautogui()
    if pag:
        pag.press("volumeup", presses=2)
        return ActionResult("[ACTION] Volume increased.")
    return ActionResult("[ERROR] pyautogui not available.")


def _action_volume_down() -> ActionResult:
    """Press the Volume Down key twice."""
    pag = _get_pyautogui()
    if pag:
        pag.press("volumedown", presses=2)
        return ActionResult("[ACTION] Volume decreased.")
    return ActionResult("[ERROR] pyautogui not available.")


def _action_mute() -> ActionResult:
    """Press the Mute key."""
    pag = _get_pyautogui()
    if pag:
        pag.press("volumemute")
        return ActionResult("[ACTION] Audio muted/unmuted.")
    return ActionResult("[ERROR] pyautogui not available.")


def _action_shutdown() -> ActionResult:
    """Initiate a system shutdown with a grace period."""
    if sys.platform == "win32":
        os.system("shutdown /s /t 30")
        return ActionResult("[ACTION] Shutdown in 30s. Run 'shutdown /a' to abort.")
    else:
        os.system("shutdown -h +1")
        return ActionResult("[ACTION] Shutdown in 60s. Run 'shutdown -c' to abort.")


def _action_restart() -> ActionResult:
    """Initiate a system restart."""
    if sys.platform == "win32":
        os.system("shutdown /r /t 10")
    else:
        os.system("shutdown -r +1")
    return ActionResult("[ACTION] System will restart shortly.")


def _action_lock_screen() -> ActionResult:
    """Lock the workstation."""
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.user32.LockWorkStation()
    else:
        # Try multiple lock methods for Linux compatibility
        lock_cmds = [
            "loginctl lock-session",
            "xdg-screensaver lock",
            "xflock4",
        ]
        for lock_cmd in lock_cmds:
            ret = os.system(lock_cmd)
            if ret == 0:
                break
    return ActionResult("[ACTION] Screen locked.")


def _action_screenshot() -> ActionResult:
    """Take a screenshot using the OS native tool."""
    if sys.platform == "win32":
        subprocess.Popen(["snippingtool.exe"])
    else:
        # Try Kali/XFCE screenshooter first, then fall back
        screenshot_cmds = [
            ["xfce4-screenshooter"],
            ["gnome-screenshot", "--interactive"],
            ["scrot", "-s"],
        ]
        launched = False
        for cmd in screenshot_cmds:
            try:
                subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
                launched = True
                break
            except FileNotFoundError:
                continue
        if not launched:
            return ActionResult("[ERROR] No screenshot tool found. Install: apt install xfce4-screenshooter")
    return ActionResult("[ACTION] Screenshot tool launched.")


# ── Application Launcher ────────────────────────────────────────────────────

def _action_open_app(app_name: str) -> ActionResult:
    """
    Attempt to open an application by matching the spoken name against
    the APP_MAP dictionary.  If no match is found, try launching it
    directly as a command.

    Parameters
    ----------
    app_name : str
        The application name extracted from the voice command.

    Returns
    -------
    ActionResult
        Result status message.
    """
    app_name = app_name.strip()

    # Check the known app map
    for key, executable in APP_MAP.items():
        if key in app_name:
            try:
                if sys.platform == "win32":
                    os.startfile(executable)
                else:
                    subprocess.Popen(
                        executable.split(),
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                return ActionResult(f"[ACTION] Opened {key.title()}.")
            except Exception as exc:
                return ActionResult(f"[ERROR] Could not open {key}: {exc}")

    # Fallback: try running the name directly as a command
    try:
        if sys.platform == "win32":
            os.startfile(app_name)
        else:
            subprocess.Popen(
                app_name.split(),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        return ActionResult(f"[ACTION] Launched '{app_name}'.")
    except Exception as exc:
        return ActionResult(f"[ERROR] Unknown app '{app_name}': {exc}")


# ── Local File Search ───────────────────────────────────────────────────────

def _action_file_search(query: str) -> ActionResult:
    """
    Recursively search common user directories for files matching the
    query string.  Opens the first match found.

    The search is case-insensitive and matches partial filenames.
    For performance, the search is capped at 3 directory levels deep
    and stops after finding the first match.

    Parameters
    ----------
    query : str
        The filename or partial name to search for.

    Returns
    -------
    ActionResult
        Result message indicating success or failure.
    """
    query = query.strip()
    if not query:
        return ActionResult("[ERROR] No search term provided.")

    found_path = None
    max_depth = 3  # Don't recurse too deeply for speed

    for search_dir in SEARCH_DIRECTORIES:
        base_depth = search_dir.count(os.sep)
        for root, dirs, files in os.walk(search_dir):
            # Enforce max depth
            current_depth = root.count(os.sep) - base_depth
            if current_depth >= max_depth:
                dirs.clear()  # Don't recurse further
                continue

            # Skip hidden directories
            dirs[:] = [d for d in dirs if not d.startswith('.')]

            # Search files in this directory
            for filename in files:
                if query.lower() in filename.lower():
                    found_path = os.path.join(root, filename)
                    break
            if found_path:
                break
        if found_path:
            break

    if found_path:
        try:
            # Open the file with the default system application
            if sys.platform == "win32":
                os.startfile(found_path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", found_path])
            else:
                subprocess.Popen(["xdg-open", found_path],
                                 stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
            return ActionResult(f"[FOUND] Opening: {found_path}")
        except Exception as exc:
            return ActionResult(f"[ERROR] Found '{found_path}' but could not open: {exc}")
    else:
        return ActionResult(f"[NOT FOUND] No file matching '{query}' in user dirs.")


# ── Web / Gemini Actions ────────────────────────────────────────────────────

def _action_ask_gemini(query: str) -> ActionResult:
    """
    Request a background scrape for a general text response from Gemini.

    Parameters
    ----------
    query : str
        The question or prompt to send to Gemini.

    Returns
    -------
    ActionResult
        Status message.
    """
    global LAST_GEMINI_QUERY
    query = query.strip()
    if query:
        LAST_GEMINI_QUERY = query
        return ActionResult(
            message="[SCRAPING] Asking Gemini...",
            needs_gemini_chat=True,
            pending_query=query
        )
    return ActionResult(
        message="[SCRAPING] Asking Gemini...",
        needs_gemini_chat=True,
        pending_query=""
    )


def _action_web_search(query: str) -> ActionResult:
    """
    Perform a Google web search for the given query.

    Parameters
    ----------
    query : str
        The search query string.

    Returns
    -------
    ActionResult
        Status message.
    """
    query = query.strip()
    if not query:
        return ActionResult("[ERROR] No search query provided.")

    encoded = urllib.parse.quote_plus(query)
    url = f"https://www.google.com/search?q={encoded}"
    webbrowser.open(url)
    return ActionResult(f"[WEB] Searching Google for: '{query}'")


# ============================================================================
#  TEXT MATCHING UTILITIES
# ============================================================================

def _match_any(text: str, patterns: list[str]) -> bool:
    """
    Return True if any of the patterns appear as a substring in text.
    Both text and patterns should already be lowercase.
    """
    return any(p in text for p in patterns)


def _starts_with_any(text: str, prefixes: list[str]) -> bool:
    """
    Return True if text starts with any of the given prefixes.
    """
    return any(text.startswith(p) for p in prefixes)


def _extract_after(text: str, prefixes: list[str]) -> str:
    """
    Remove the first matching prefix from text and return the remainder.
    Prefixes are tried in order (longest should come first for accuracy).

    Parameters
    ----------
    text : str
        Full command string.
    prefixes : list[str]
        Ordered list of prefixes to strip.

    Returns
    -------
    str
        The text after the matched prefix, or the original text if
        no prefix matched.
    """
    for prefix in prefixes:
        if text.startswith(prefix):
            return text[len(prefix):].strip()
    return text.strip()

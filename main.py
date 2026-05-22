# ============================================================================
#  main.py — "The Hacker UI"
# ============================================================================
#  Chintu Voice Assistant — Application Entry Point & PyQt6 Interface
#
#  This module builds the foreground interface:
#
#    • A borderless, transparent, frameless overlay window that floats
#      at the top-center of the primary monitor.
#    • Dark translucent "pill bar" with rounded corners and monospaced
#      terminal-style text.
#    • A 30 Hz animated QLinearGradient border that continuously shifts
#      colours (Apple Intelligence-style pulsing edge).
#    • A QGraphicsDropShadowEffect providing a neon-cyan glow in idle
#      state, switching to hot magenta when the wake word is detected.
#    • A confirmation dialog for shell commands — shows the exact command
#      and requires explicit user approval before execution.
#    • Full integration with audio_engine, core_automation, web_automation.
#
#  Run:
#      python main.py
# ============================================================================

import sys
import math

from PyQt6.QtCore import (
    Qt, QThread, QTimer, QPropertyAnimation, QEasingCurve,
    QRect, QPoint, QSize, pyqtSlot, QObject, pyqtSignal, QEvent
)
from PyQt6.QtGui import (
    QFont, QColor, QLinearGradient, QPainter, QPen, QBrush,
    QGuiApplication, QFontDatabase, QPainterPath
)
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QHBoxLayout, QVBoxLayout,
    QGraphicsDropShadowEffect, QSizePolicy, QDialog, QPushButton, QLineEdit
)

from audio_engine import AudioEngine
from core_automation import route_intent, execute_confirmed_shell, ActionResult


# ============================================================================
#  COLOUR PALETTE
# ============================================================================
# Neon cyberpunk palette — carefully chosen for maximum visual impact on
# dark translucent backgrounds.

COLOUR_BG            = QColor(10, 10, 18, 200)       # Near-black, translucent
COLOUR_BG_SOLID      = QColor(14, 14, 24, 240)       # Solid dark for dialogs
COLOUR_BORDER_IDLE   = QColor(0, 255, 220, 255)       # Neon cyan
COLOUR_BORDER_ACTIVE = QColor(255, 0, 128, 255)       # Hot magenta
COLOUR_GLOW_IDLE     = QColor(0, 255, 220, 140)       # Cyan glow (softer)
COLOUR_GLOW_ACTIVE   = QColor(255, 0, 128, 140)       # Magenta glow (softer)
COLOUR_TEXT_PRIMARY   = QColor(230, 240, 255, 255)     # Cool white
COLOUR_TEXT_DIM       = QColor(100, 120, 150, 200)     # Dimmed secondary
COLOUR_DOT_IDLE       = QColor(0, 255, 180, 255)       # Status dot — idle
COLOUR_DOT_ACTIVE     = QColor(255, 60, 160, 255)      # Status dot — active
COLOUR_APPROVE        = QColor(0, 220, 130)            # Green — approve
COLOUR_DENY           = QColor(220, 50, 80)            # Red   — deny
COLOUR_WARN           = QColor(255, 180, 0)            # Amber — warning

HELP_MARKDOWN = """
## 🤖 Chintu Voice Commands
Here are some of the things you can say:

### 🎙️ Core
- **`help`**, **`commands`** — Show this help menu.
- **`ask gemini [query]`** — Ask AI a question in the background.
- **`gemini run [task]`** — Generate a terminal command and run it.
- **`run it`**, **`execute that`** — Execute the last AI-generated command.

### 🖥️ OS Control
- **`open notepad`**, **`open firefox`** — Open an application.
- **`close app`**, **`minimize`**, **`maximize`** — Window management.
- **`volume up`**, **`volume down`**, **`mute`** — Audio control.
- **`take screenshot`**, **`lock screen`** — System utilities.

### 💻 Terminal
- **`run command [cmd]`**, **`execute [cmd]`** — Run any shell command. *(Requires your explicit approval!)*

### 🌐 Web & Files
- **`check my gmail`** — Read your latest email.
- **`youtube search [video]`** — Play a video on YouTube.
- **`find [filename]`** — Search for local files and open them.
"""

# Gradient hue stops for the animated border (Apple Intelligence style)
GRADIENT_HUES = [180, 200, 280, 320, 360, 30, 80, 140, 180]


# ============================================================================
#  MONOSPACE FONT HELPER
# ============================================================================

def _get_mono_font(size: int = 11) -> QFont:
    """
    Return the best available monospaced font with a fallback chain:
    JetBrains Mono → Fira Code → Consolas → Hack → monospace
    """
    font = QFont("JetBrains Mono", size)
    font.setStyleHint(QFont.StyleHint.Monospace)
    families = ["JetBrains Mono", "Fira Code", "Consolas", "Hack",
                "Source Code Pro", "DejaVu Sans Mono", "monospace"]
    available_families = QFontDatabase.families()
    for family in families:
        if family in available_families:
            font.setFamily(family)
            break
    font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.5)
    return font


# ============================================================================
#  SHELL COMMAND CONFIRMATION DIALOG
# ============================================================================

class ShellConfirmDialog(QDialog):
    """
    A dark-themed, borderless confirmation dialog that displays the
    exact shell command about to be executed.  The user must explicitly
    click "Approve" or "Deny" before any command runs.

    The dialog is styled to match the Chintu hacker aesthetic:
      • Dark translucent background with rounded corners
      • Monospaced command display in a highlighted box
      • Green ✓ APPROVE and Red ✗ DENY buttons
    """

    DIALOG_WIDTH  = 520
    DIALOG_HEIGHT = 240

    def __init__(self, command: str, parent=None):
        super().__init__(parent)

        self._command = command

        # ── Window flags ────────────────────────────────────────────────
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Dialog
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(self.DIALOG_WIDTH, self.DIALOG_HEIGHT)
        self.setModal(True)

        # ── Center on screen ────────────────────────────────────────────
        screen = QGuiApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            x = geo.x() + (geo.width()  - self.DIALOG_WIDTH)  // 2
            y = geo.y() + (geo.height() - self.DIALOG_HEIGHT) // 2
            self.move(x, y)

        # ── Build layout ────────────────────────────────────────────────
        self._build_ui()

    def _build_ui(self):
        """Construct the dialog UI."""
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 16, 20, 16)
        outer.setSpacing(12)

        mono = _get_mono_font(11)
        mono_small = _get_mono_font(10)

        # ── Title ───────────────────────────────────────────────────────
        title = QLabel("⚡ SHELL COMMAND CONFIRMATION")
        title.setFont(_get_mono_font(12))
        title.setStyleSheet(f"color: {COLOUR_WARN.name()}; background: transparent;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(title)

        # ── Subtitle ───────────────────────────────────────────────────
        subtitle = QLabel("Chintu wants to execute the following command:")
        subtitle.setFont(mono_small)
        subtitle.setStyleSheet(f"color: {COLOUR_TEXT_DIM.name()}; background: transparent;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(subtitle)

        # ── Command display box ─────────────────────────────────────────
        cmd_label = QLabel(f"  $ {self._command}")
        cmd_label.setFont(_get_mono_font(12))
        cmd_label.setWordWrap(True)
        cmd_label.setStyleSheet(
            f"color: #00ffa0;"
            f"background: rgba(0, 255, 160, 15);"
            f"border: 1px solid rgba(0, 255, 160, 60);"
            f"border-radius: 8px;"
            f"padding: 10px 14px;"
        )
        cmd_label.setMinimumHeight(48)
        outer.addWidget(cmd_label)

        outer.addStretch()

        # ── Buttons ─────────────────────────────────────────────────────
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(16)

        # Common button stylesheet template
        btn_base = (
            "QPushButton {{"
            "  color: #ffffff;"
            "  background: {bg};"
            "  border: 1px solid {border};"
            "  border-radius: 8px;"
            "  padding: 8px 24px;"
            "  font-family: monospace;"
            "  font-size: 12px;"
            "  font-weight: bold;"
            "}}"
            "QPushButton:hover {{"
            "  background: {hover};"
            "}}"
            "QPushButton:pressed {{"
            "  background: {pressed};"
            "}}"
        )

        # ── APPROVE button ──────────────────────────────────────────────
        approve_btn = QPushButton("  ✓  APPROVE  ")
        approve_btn.setStyleSheet(btn_base.format(
            bg="rgba(0, 200, 120, 80)",
            border="rgba(0, 220, 130, 160)",
            hover="rgba(0, 220, 130, 140)",
            pressed="rgba(0, 180, 100, 200)",
        ))
        approve_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        approve_btn.clicked.connect(self.accept)
        btn_layout.addWidget(approve_btn)

        # ── DENY button ─────────────────────────────────────────────────
        deny_btn = QPushButton("  ✗  DENY  ")
        deny_btn.setStyleSheet(btn_base.format(
            bg="rgba(220, 50, 80, 80)",
            border="rgba(220, 50, 80, 160)",
            hover="rgba(220, 50, 80, 140)",
            pressed="rgba(180, 30, 60, 200)",
        ))
        deny_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        deny_btn.clicked.connect(self.reject)
        btn_layout.addWidget(deny_btn)

        outer.addLayout(btn_layout)

    # ── Custom paint for dark rounded background ────────────────────────
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Dark background with subtle border
        path = QPainterPath()
        rect = self.rect().adjusted(2, 2, -2, -2)
        path.addRoundedRect(
            float(rect.x()), float(rect.y()),
            float(rect.width()), float(rect.height()),
            16.0, 16.0
        )

        # Border
        pen = QPen(QColor(255, 180, 0, 100), 1.5)
        painter.setPen(pen)
        painter.setBrush(QBrush(COLOUR_BG_SOLID))
        painter.drawPath(path)
        painter.end()


# ============================================================================
#  GEMINI SCRAPER WORKER
# ============================================================================

class ScraperWorker(QObject):
    """Background worker to scrape Gemini without freezing the UI."""
    finished = pyqtSignal(str)

    def __init__(self, query: str):
        super().__init__()
        self.query = query

    @pyqtSlot()
    def run(self):
        from web_automation import scrape_gemini_command
        cmd = scrape_gemini_command(self.query)
        self.finished.emit(cmd)

class ChatWorker(QObject):
    """Background worker to scrape text response from Gemini."""
    finished = pyqtSignal(str)

    def __init__(self, query: str):
        super().__init__()
        self.query = query

    @pyqtSlot()
    def run(self):
        from web_automation import scrape_gemini_text
        text = scrape_gemini_text(self.query)
        self.finished.emit(text)

# ============================================================================
#  ANIMATED PILL BAR WIDGET
# ============================================================================

class ChintuOverlay(QWidget):
    """
    The main overlay widget.  Renders as a dark translucent rounded
    rectangle with an animated gradient border and drop-shadow glow.
    """

    # ── Widget Dimensions ───────────────────────────────────────────────
    BAR_WIDTH   = 720
    BAR_HEIGHT  = 64
    CORNER_RADIUS = 32          # Fully rounded ends (pill shape)
    BORDER_WIDTH  = 2.5         # Gradient border thickness

    # ── Animation ───────────────────────────────────────────────────────
    ANIM_FPS      = 30          # 30 Hz refresh rate
    ANIM_SPEED    = 0.015       # Hue rotation speed per frame

    def __init__(self):
        super().__init__()

        # ── State ───────────────────────────────────────────────────────
        self._is_active = False          # Wake word detected?
        self._gradient_offset = 0.0      # Current hue offset for animation
        self._status_text = "INITIALISING..."
        self._command_text = ""
        self._processing = False
        self._is_sleeping = False
        self._drag_pos = None

        # ── Window Flags ────────────────────────────────────────────────
        # Frameless | Always on top | Tool window (skip taskbar)
        # Transparent background for rounded corners
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setFixedSize(self.BAR_WIDTH, self.BAR_HEIGHT)

        # ── Position at top-center of primary screen ────────────────────
        self._position_on_screen()

        # ── Build internal layout ───────────────────────────────────────
        self._build_ui()

        # ── Drop Shadow (neon glow) ─────────────────────────────────────
        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setBlurRadius(40)
        self._shadow.setOffset(0, 2)
        self._shadow.setColor(COLOUR_GLOW_IDLE)
        self.setGraphicsEffect(self._shadow)

        # ── Animation Timer (30 Hz) ─────────────────────────────────────
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._tick_animation)
        self._anim_timer.start(1000 // self.ANIM_FPS)

        # ── Idle restore timer ──────────────────────────────────────────
        # After a command is processed, we hold the result for 5 seconds
        # before returning to idle.
        self._idle_timer = QTimer(self)
        self._idle_timer.setSingleShot(True)
        self._idle_timer.timeout.connect(self._restore_idle)

        # ── Sleep timer ─────────────────────────────────────────────────
        # Auto-minimizes the UI after 30 seconds of inactivity
        self._sleep_timer = QTimer(self)
        self._sleep_timer.setSingleShot(True)
        self._sleep_timer.timeout.connect(self._sleep_ui)
        self._sleep_timer.start(30000)

        # ── Audio engine (background thread) ────────────────────────────
        self._setup_audio_engine()

    # ====================================================================
    #  DRAG & DROP / SLEEP LOGIC
    # ====================================================================

    def eventFilter(self, obj, event):
        """Intercept mouse events on specific child widgets (like the drag grip) to allow window dragging."""
        if obj == getattr(self, '_drag_grip', None):
            if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                if self.windowHandle():
                    self.windowHandle().startSystemMove()
                return True
        elif obj == getattr(self, '_min_btn', None):
            if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                self._restore_idle()
                return True
        return super().eventFilter(obj, event)

    def mousePressEvent(self, event):
        """Enable dragging on the background as a fallback."""
        if event.button() == Qt.MouseButton.LeftButton:
            if self.windowHandle():
                self.windowHandle().startSystemMove()
            event.accept()
            self._reset_sleep_timer()

    def mouseMoveEvent(self, event):
        pass

    def mouseReleaseEvent(self, event):
        pass

    def _reset_sleep_timer(self):
        """Reset inactivity timer, waking up UI if sleeping."""
        if self._is_sleeping:
            self._wake_ui()
        self._sleep_timer.start(30000)

    def _sleep_ui(self):
        """Animate to bottom-center and hide text input."""
        if self._is_sleeping or self._processing or self._is_active:
            # Don't sleep if currently doing something
            self._sleep_timer.start(30000)
            return

        self._is_sleeping = True
        self._text_input.hide()
        self._mic_btn.hide()

        screen = QGuiApplication.primaryScreen()
        if not screen: return
        geo = screen.availableGeometry()

        # Target: small pill at bottom center
        target_width = 64
        target_height = 64
        target_x = geo.x() + (geo.width() - target_width) // 2
        target_y = geo.y() + geo.height() - target_height - 24 # 24px from bottom

        # Animate Geometry
        self.anim = QPropertyAnimation(self, b"geometry")
        self.anim.setDuration(400)
        self.anim.setEasingCurve(QEasingCurve.Type.InOutExpo)
        self.anim.setEndValue(QRect(target_x, target_y, target_width, target_height))
        self.anim.start()

    def _wake_ui(self):
        """Restore size/position and show text input."""
        self._is_sleeping = False
        self._text_input.show()
        self._mic_btn.show()

        # For simplicity, restore to top center, or could store last pos
        screen = QGuiApplication.primaryScreen()
        if not screen: return
        geo = screen.availableGeometry()
        x = geo.x() + (geo.width() - self.BAR_WIDTH) // 2
        y = geo.y() + 18

        self.anim = QPropertyAnimation(self, b"geometry")
        self.anim.setDuration(400)
        self.anim.setEasingCurve(QEasingCurve.Type.OutExpo)
        self.anim.setEndValue(QRect(x, y, self.BAR_WIDTH, self.BAR_HEIGHT))
        self.anim.start()

    @pyqtSlot()
    def _on_mic_clicked(self):
        """Trigger push-to-talk."""
        self._reset_sleep_timer()
        self._is_active = True
        self._shadow.setColor(COLOUR_GLOW_ACTIVE)
        self._dot_label.setStyleSheet(
            f"color: {COLOUR_DOT_ACTIVE.name()}; font-size: 14px;"
        )
        self._text_input.setPlaceholderText(">> Listening for command...")
        self.update()
        # Safely invoke listen_once in the audio thread
        QTimer.singleShot(0, self._audio_engine.listen_once)

    # ====================================================================
    #  SCREEN POSITIONING
    # ====================================================================

    def _position_on_screen(self):
        """Place the widget at the horizontal center, near the top."""
        screen = QGuiApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            x = geo.x() + (geo.width() - self.BAR_WIDTH) // 2
            y = geo.y() + 18  # 18px from top edge
            self.move(x, y)

    # ====================================================================
    #  UI CONSTRUCTION
    # ====================================================================

    def _build_ui(self):
        """
        Internal layout:
          [ ≡ drag_grip ] [ ● status_dot ]  [ status / command text label ]
          [ optional chat text area ]
        """
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 0, 24, 12)
        main_layout.setSpacing(8)

        # ── TOP ROW ────────────────────────────────────────────────────
        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(12)

        # ── Drag Grip ──────────────────────────────────────────────────
        self._drag_grip = QLabel("≡")
        self._drag_grip.setStyleSheet("color: rgba(255,255,255,80); font-size: 16px; font-weight: bold;")
        self._drag_grip.setCursor(Qt.CursorShape.OpenHandCursor)
        self._drag_grip.installEventFilter(self)
        top_layout.addWidget(self._drag_grip)

        # ── Status Dot ─────────────────────────────────────────────────
        self._dot_label = QLabel("●")
        self._dot_label.setFixedWidth(18)
        self._dot_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._dot_label.setStyleSheet(
            f"color: {COLOUR_DOT_IDLE.name()}; font-size: 14px;"
        )
        top_layout.addWidget(self._dot_label)

        # ── Text Input (for both displaying status and typing) ─────────
        self._text_input = QLineEdit(self)
        self._text_input.setPlaceholderText(self._status_text)
        self._text_input.setFont(_get_mono_font(11))
        
        # Style to look like a borderless label until clicked
        self._text_input.setStyleSheet(
            f"QLineEdit {{"
            f"  color: {COLOUR_TEXT_PRIMARY.name()};"
            f"  background: transparent;"
            f"  border: none;"
            f"}}"
        )
        self._text_input.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self._text_input.returnPressed.connect(self._on_text_submitted)
        top_layout.addWidget(self._text_input)

        # ── Minimize Button ────────────────────────────────────────────
        self._min_btn = QLabel("−")
        self._min_btn.setFixedSize(24, 24)
        self._min_btn.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._min_btn.setStyleSheet("color: rgba(255,255,255,150); font-size: 18px; font-weight: bold; margin-bottom: 4px;")
        self._min_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._min_btn.installEventFilter(self)
        top_layout.addWidget(self._min_btn)

        # ── Mic Button (Push to Talk) ──────────────────────────────────
        self._mic_btn = QPushButton("🎙")
        self._mic_btn.setFixedSize(32, 32)
        self._mic_btn.setStyleSheet(
            f"QPushButton {{"
            f"  color: {COLOUR_TEXT_PRIMARY.name()};"
            f"  background: transparent;"
            f"  border: 1px solid rgba(255,255,255,40);"
            f"  border-radius: 16px;"
            f"  font-size: 16px;"
            f"}}"
            f"QPushButton:hover {{"
            f"  background: rgba(255, 255, 255, 20);"
            f"}}"
            f"QPushButton:pressed {{"
            f"  background: rgba(255, 255, 255, 40);"
            f"}}"
        )
        self._mic_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._mic_btn.clicked.connect(self._on_mic_clicked)
        top_layout.addWidget(self._mic_btn)

        main_layout.addLayout(top_layout)

        # ── BOTTOM ROW (Chat Display) ──────────────────────────────────
        from PyQt6.QtWidgets import QTextEdit
        self._chat_display = QTextEdit(self)
        self._chat_display.setReadOnly(True)
        self._chat_display.setStyleSheet(
            f"QTextEdit {{"
            f"  color: #E2E8F0;"
            f"  background: rgba(15, 23, 42, 220);"
            f"  border: 1px solid rgba(56, 189, 248, 40);"
            f"  border-radius: 12px;"
            f"  padding: 12px;"
            f"  font-family: 'Segoe UI', 'Ubuntu', 'Inter', sans-serif;"
            f"  font-size: 14px;"
            f"}}"
            f"QScrollBar:vertical {{"
            f"  border: none;"
            f"  background: transparent;"
            f"  width: 6px;"
            f"  margin: 0px 0px 0px 0px;"
            f"}}"
            f"QScrollBar::handle:vertical {{"
            f"  background: rgba(255, 255, 255, 40);"
            f"  border-radius: 3px;"
            f"}}"
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{"
            f"  height: 0px;"
            f"}}"
        )
        self._chat_display.hide()
        main_layout.addWidget(self._chat_display)
    # ====================================================================
    #  AUDIO ENGINE SETUP
    # ====================================================================

    def _setup_audio_engine(self):
        """
        Create the AudioEngine worker, move it to a background QThread,
        and wire up all the signals.
        """
        self._audio_thread = QThread(self)
        self._audio_engine = AudioEngine()
        self._audio_engine.moveToThread(self._audio_thread)

        # ── Connect signals ────────────────────────────────────────────
        self._audio_engine.status_update.connect(self._on_status_update)
        self._audio_engine.command_received.connect(self._on_command_received)

        # ── Start the thread ────────────────────────────────────────────
        self._audio_thread.start()

    # ====================================================================
    #  SIGNAL HANDLERS
    # ====================================================================

    @pyqtSlot(str)
    def _on_status_update(self, status: str):
        """
        Receive status messages from the audio engine and update the
        UI placeholder text.
        """
        self._status_text = status
        # Only update placeholder if we're not showing a command result
        if not self._processing:
            self._text_input.setPlaceholderText(self._truncate(status))

    @pyqtSlot()
    def _on_wake_word(self):
        """
        Wake word detected — switch to active visual state:
          • Glow → magenta
          • Status dot → magenta
          • Border shifts to warm hues
        """
        self._is_active = True
        self._shadow.setColor(COLOUR_GLOW_ACTIVE)
        self._dot_label.setStyleSheet(
            f"color: {COLOUR_DOT_ACTIVE.name()}; font-size: 14px;"
        )
        self._text_input.setPlaceholderText(">> Listening for command...")
        self.update()  # Force repaint

    @pyqtSlot(str)
    def _on_command_received(self, command: str):
        """
        A spoken command has been transcribed.  Display it, execute
        the corresponding action, then return to idle after a delay.

        If the action requires confirmation (shell commands), show the
        ShellConfirmDialog before executing.
        """
        self._processing = True
        self._text_input.setText(f">> {command}")
        self._text_input.clearFocus()
        self.update()

        # ── Route the intent ───────────────────────────────────────────
        result: ActionResult = route_intent(command)

        self._reset_sleep_timer()

        # ── Handle Background Gemini Scraping ──────────────────────────
        if result.needs_gemini_scrape:
            self._text_input.clear()
            self._text_input.setPlaceholderText(self._truncate(result.message))
            self.update()
            
            # Start background scraping
            self._scraper_thread = QThread(self)
            self._scraper_worker = ScraperWorker(result.pending_query)
            self._scraper_worker.moveToThread(self._scraper_thread)
            
            self._scraper_thread.started.connect(self._scraper_worker.run)
            self._scraper_worker.finished.connect(self._on_scrape_finished)
            self._scraper_worker.finished.connect(self._scraper_thread.quit)
            self._scraper_worker.finished.connect(self._scraper_worker.deleteLater)
            self._scraper_thread.finished.connect(self._scraper_thread.deleteLater)
            
            self._scraper_thread.start()
            return

        # ── Check if confirmation is needed (shell commands) ───────────
        if result.needs_confirmation and result.pending_command:
            self._handle_shell_confirmation(result.pending_command)
        elif result.needs_gemini_chat:
            self._handle_gemini_chat(result.pending_query, result.message)
        elif result.needs_help_ui:
            self._text_input.clear()
            self._on_chat_finished(HELP_MARKDOWN)
        else:
            # Direct action — display the result
            self._text_input.clear()
            self._text_input.setPlaceholderText(self._truncate(result.message))
            self._idle_timer.start(5000)

    @pyqtSlot()
    def _on_text_submitted(self):
        """
        Handle manually typed commands from the QLineEdit.
        """
        self._reset_sleep_timer()
        cmd = self._text_input.text().strip()
        if cmd:
            self._text_input.clear()
            self._on_command_received(cmd)

    @pyqtSlot(str)
    def _on_scrape_finished(self, shell_cmd: str):
        """Handle the result of a background Gemini scrape."""
        self._text_input.clear()
        if not shell_cmd or shell_cmd.startswith("[ERROR]"):
            err_msg = shell_cmd if shell_cmd else "[ERROR] Could not extract command from Gemini."
            self._text_input.setPlaceholderText(self._truncate(err_msg, 55))
            self._idle_timer.start(7000)
            return
        
        self._handle_shell_confirmation(shell_cmd)

    def _handle_gemini_chat(self, query: str, message: str):
        """Start a background thread to scrape a general answer from Gemini."""
        self._text_input.clear()
        self._text_input.setPlaceholderText(self._truncate(message))
        self.update()
        
        self._chat_thread = QThread(self)
        self._chat_worker = ChatWorker(query)
        self._chat_worker.moveToThread(self._chat_thread)
        
        self._chat_thread.started.connect(self._chat_worker.run)
        self._chat_worker.finished.connect(self._on_chat_finished)
        self._chat_worker.finished.connect(self._chat_thread.quit)
        self._chat_worker.finished.connect(self._chat_worker.deleteLater)
        self._chat_thread.finished.connect(self._chat_thread.deleteLater)
        
        self._chat_thread.start()

    @pyqtSlot(str)
    def _on_chat_finished(self, text: str):
        """Show the expanded chat response in the UI."""
        self._text_input.clear()
        if not text or text.startswith("[ERROR]"):
            self._text_input.setPlaceholderText(text if text else "[ERROR] Could not get response from Gemini.")
            self._idle_timer.start(7000)
            return
            
        if text == HELP_MARKDOWN:
            self._text_input.setPlaceholderText("[CHINTU] Help menu ready.")
        else:
            self._text_input.setPlaceholderText("[GEMINI] Answer ready.")
            
        self._chat_display.setMarkdown(text)
        self._chat_display.show()
        
        # Expand the UI downwards
        screen = QGuiApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            x = self.x()
            y = self.y()
            self.setFixedSize(self.BAR_WIDTH, 400)
            self.move(x, y) # Keep top position fixed
            
        self._idle_timer.start(120000)

    def _handle_shell_confirmation(self, shell_cmd: str):
        """
        Show the shell command confirmation dialog.  If the user approves,
        execute the command.  If denied, show a cancellation message.

        Parameters
        ----------
        shell_cmd : str
            The shell command to confirm and potentially execute.
        """
        self._text_input.clear()
        self._text_input.setPlaceholderText(f"[CONFIRM?] $ {self._truncate(shell_cmd, 55)}")
        self.update()

        # ── Show the confirmation dialog ────────────────────────────────
        dialog = ShellConfirmDialog(shell_cmd, parent=None)
        user_choice = dialog.exec()

        if user_choice == QDialog.DialogCode.Accepted:
            # ── User approved — execute the command ─────────────────────
            self._text_input.setPlaceholderText("[EXECUTING] Running command...")
            self.update()

            # Run the command (synchronous — capped at 30s by timeout)
            output = execute_confirmed_shell(shell_cmd)
            self._text_input.setPlaceholderText(self._truncate(output))
        else:
            # ── User denied — cancel ────────────────────────────────────
            self._text_input.setPlaceholderText("[DENIED] Command cancelled by user.")

        self._idle_timer.start(6000)

    def _restore_idle(self):
        """
        Return to the idle visual state after a command has been processed.
        """
        self._is_active = False
        self._processing = False
        self._shadow.setColor(COLOUR_GLOW_IDLE)
        self._dot_label.setStyleSheet(
            f"color: {COLOUR_DOT_IDLE.name()}; font-size: 14px;"
        )
        self._text_input.clear()
        self._text_input.setPlaceholderText(
            "[IDLE] Say 'Hey Chintu' or type a command..."
        )
        # Collapse the UI back to pill shape if it was expanded
        if self.height() > self.BAR_HEIGHT:
            self._chat_display.hide()
            self.setFixedSize(self.BAR_WIDTH, self.BAR_HEIGHT)
        self.update()

    # ====================================================================
    #  ANIMATED GRADIENT BORDER — Custom Paint
    # ====================================================================

    def paintEvent(self, event):
        """
        Custom paint event that draws:
          1. Dark translucent rounded-rect background
          2. Animated gradient border (hue-shifting)
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        rect = self.rect().adjusted(
            int(self.BORDER_WIDTH) + 1,
            int(self.BORDER_WIDTH) + 1,
            -int(self.BORDER_WIDTH) - 1,
            -int(self.BORDER_WIDTH) - 1
        )

        # ── 1. Draw the animated gradient border ────────────────────────
        gradient = QLinearGradient(0, 0, self.width(), 0)

        num_stops = len(GRADIENT_HUES)
        for i, hue in enumerate(GRADIENT_HUES):
            # Shift the hue by the animated offset
            shifted_hue = (hue + self._gradient_offset * 360) % 360
            saturation = 0.9
            lightness = 0.6

            if self._is_active:
                # In active mode, bias towards magenta/pink hues
                shifted_hue = (shifted_hue + 180) % 360
                lightness = 0.65

            colour = QColor.fromHslF(
                shifted_hue / 360.0, saturation, lightness, 1.0
            )
            gradient.setColorAt(i / (num_stops - 1), colour)

        pen = QPen(QBrush(gradient), self.BORDER_WIDTH)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)

        # ── 2. Fill the background ──────────────────────────────────────
        painter.setBrush(QBrush(COLOUR_BG))

        # ── Draw the rounded rectangle ──────────────────────────────────
        path = QPainterPath()
        path.addRoundedRect(
            float(rect.x()), float(rect.y()),
            float(rect.width()), float(rect.height()),
            self.CORNER_RADIUS, self.CORNER_RADIUS
        )
        painter.drawPath(path)

        painter.end()

    def _tick_animation(self):
        """
        Called at 30 Hz by the animation timer.  Advances the gradient
        hue offset to create the continuously shifting border effect.
        """
        self._gradient_offset += self.ANIM_SPEED
        if self._gradient_offset >= 1.0:
            self._gradient_offset -= 1.0
        self.update()  # Trigger repaint

    # ====================================================================
    #  UTILITIES
    # ====================================================================

    @staticmethod
    def _truncate(text: str, max_len: int = 75) -> str:
        """Truncate text to fit within the pill bar."""
        if len(text) > max_len:
            return text[:max_len - 3] + "..."
        return text

    # ====================================================================
    #  CLEANUP
    # ====================================================================

    def closeEvent(self, event):
        """
        Gracefully shut down the audio engine thread when the window
        is closed.
        """
        self._anim_timer.stop()
        self._audio_engine.stop()
        self._audio_thread.quit()
        self._audio_thread.wait(3000)  # Wait up to 3 seconds
        event.accept()


# ============================================================================
#  APPLICATION ENTRY POINT
# ============================================================================

def main():
    """
    Bootstrap the PyQt6 application, create the overlay widget, and
    enter the event loop.
    """
    # ── High-DPI scaling (automatic in Qt6, but explicit for clarity) ──
    app = QApplication(sys.argv)
    app.setApplicationName("Chintu Voice Assistant")
    app.setApplicationDisplayName("Chintu")

    # ── Create and show the overlay ─────────────────────────────────────
    overlay = ChintuOverlay()
    overlay.show()

    # ── Enter the Qt event loop ─────────────────────────────────────────
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

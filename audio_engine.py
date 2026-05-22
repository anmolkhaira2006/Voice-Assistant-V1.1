# ============================================================================

#  audio_engine.py — "The Ear"
# ============================================================================
#  Chintu Voice Assistant — Audio Engine
#
#  This module implements a dedicated background worker that continuously
#  listens on the default microphone. It operates in two phases:
#
#    1. PASSIVE PHASE  — Waits silently for the wake phrase ("hey chintu"
#                        or just "chintu").
#    2. ACTIVE PHASE   — Once triggered, captures the user's actual command,
#                        transcribes it, and sends it to the UI.
#
#  The recognizer is configured for bilingual support (English + Hindi)
#  using Google's free Web Speech API via the SpeechRecognition library.
#
#  Communication with the PyQt6 UI is handled via Qt Signals so that all
#  updates are thread-safe.
# ============================================================================

import speech_recognition as sr
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot


class AudioEngine(QObject):
    """
    Background audio worker that listens for a wake word and then captures
    voice commands.  Designed to run on a QThread.

    Signals
    -------
    status_update : str
        Emitted with human-readable status messages for the UI readout.
        Examples: "[IDLE]", "[LISTENING]", "[PROCESSING]", "[ERROR] ..."
    command_received : str
        Emitted with the final transcribed command text after wake-word
        activation.
    wake_word_detected : (no payload)
        Emitted the instant the wake word is recognised, so the UI can
        immediately switch its visual state.
    """

    # ── Qt Signals ──────────────────────────────────────────────────────
    status_update     = pyqtSignal(str)
    command_received  = pyqtSignal(str)
    wake_word_detected = pyqtSignal()

    # ── Wake Phrases (lowercase, no punctuation) ────────────────────────
    WAKE_PHRASES = ["hey chintu", "chintu"]

    # ── Recogniser Tuning ───────────────────────────────────────────────
    #  energy_threshold   — Minimum RMS energy to consider as speech.
    #                       Lower = more sensitive (noisier environments
    #                       may need higher values).
    #  pause_threshold    — Seconds of silence after speech to consider
    #                       the phrase complete.
    #  phrase_time_limit  — Maximum seconds to record a single phrase.
    ENERGY_THRESHOLD   = 300
    PAUSE_THRESHOLD    = 1.0
    PASSIVE_PHRASE_LIMIT = 4    # Short limit for wake-word detection
    ACTIVE_PHRASE_LIMIT  = 10   # Longer limit for command capture

    def __init__(self, parent=None):
        super().__init__(parent)

        # ── Internal state ──────────────────────────────────────────────
        self._running = True       # Controls the main listen loop

        # ── SpeechRecognition setup ─────────────────────────────────────
        self._recognizer = sr.Recognizer()
        self._recognizer.energy_threshold = self.ENERGY_THRESHOLD
        self._recognizer.pause_threshold  = self.PAUSE_THRESHOLD
        self._recognizer.dynamic_energy_threshold = True  # Auto-adapt

    # ====================================================================
    #  PUBLIC SLOT — Entry point when the QThread starts
    # ====================================================================
    @pyqtSlot()
    @pyqtSlot()
    def listen_once(self):
        """
        Listen for a single command on demand (Push-to-Talk).
        """
        self.status_update.emit("[INITIALISING] Acquiring microphone...")

        try:
            mic = sr.Microphone()
            with mic as source:
                self.status_update.emit("[CALIBRATING] Adjusting for ambient noise...")
                self._recognizer.adjust_for_ambient_noise(source, duration=0.5)
        except OSError as exc:
            self.status_update.emit(f"[ERROR] Microphone not found: {exc}")
            return

        self.status_update.emit("[LISTENING] Speak your command now...")
        
        command_text = self._listen_phase(
            mic,
            phrase_limit=self.ACTIVE_PHRASE_LIMIT,
            status_label="[LISTENING]"
        )

        if command_text:
            self.status_update.emit(f"[COMMAND] {command_text}")
            self.command_received.emit(command_text)
        else:
            self.status_update.emit("[TIMEOUT] No command heard. Returning to idle...")

    # ====================================================================
    #  STOP — Graceful shutdown
    # ====================================================================
    def stop(self):
        """Signal the listening loop to terminate."""
        self._running = False

    # ====================================================================
    #  PRIVATE HELPERS
    # ====================================================================
    def _listen_phase(self, mic: sr.Microphone, phrase_limit: int,
                      status_label: str) -> str | None:
        """
        Listen for a single phrase and return the transcribed text,
        or None on timeout / recognition failure.

        Parameters
        ----------
        mic : sr.Microphone
            Pre-initialised microphone instance.
        phrase_limit : int
            Maximum seconds to record.
        status_label : str
            Status string to emit while waiting.

        Returns
        -------
        str or None
            Lowercase transcribed text, or None.
        """
        try:
            with mic as source:
                # Emit the current phase status
                self.status_update.emit(
                    f"{status_label} Say 'Hey Chintu' to activate..."
                    if status_label == "[IDLE]"
                    else f"{status_label}"
                )
                audio = self._recognizer.listen(
                    source,
                    timeout=5,                    # Max wait for speech start
                    phrase_time_limit=phrase_limit # Max phrase duration
                )
        except sr.WaitTimeoutError:
            return None  # Nobody spoke — that's fine

        # ── Transcribe with Google Web Speech API ───────────────────────
        # We attempt English first; if the user spoke Hindi the API will
        # typically still return usable romanised text.  For better Hindi
        # support, we also try with language="hi-IN" as a fallback.
        self.status_update.emit("[PROCESSING] Transcribing audio...")

        text = self._transcribe(audio, language="en-IN")  # English (India)
        if text is None:
            text = self._transcribe(audio, language="hi-IN")  # Hindi fallback

        return text

    def _transcribe(self, audio: sr.AudioData, language: str) -> str | None:
        """
        Attempt transcription via Google Web Speech API.

        Parameters
        ----------
        audio : sr.AudioData
            Recorded audio data.
        language : str
            BCP-47 language tag (e.g. "en-IN", "hi-IN").

        Returns
        -------
        str or None
            Lowercase transcribed text, or None on failure.
        """
        try:
            result = self._recognizer.recognize_google(audio, language=language)
            return result.strip().lower()
        except sr.UnknownValueError:
            # Speech was unintelligible
            return None
        except sr.RequestError as exc:
            # Network / API issue
            self.status_update.emit(f"[ERROR] Speech API error: {exc}")
            return None

    def _contains_wake_word(self, text: str) -> bool:
        """
        Check whether the transcribed text contains any of the wake phrases.

        Parameters
        ----------
        text : str
            Lowercase transcribed text.

        Returns
        -------
        bool
            True if a wake phrase was found.
        """
        for phrase in self.WAKE_PHRASES:
            if phrase in text:
                return True
        return False

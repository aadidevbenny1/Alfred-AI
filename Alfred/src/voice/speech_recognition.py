"""Speech recognition service for Alfred.

Listens for user commands after wake word activation and transcribes speech using
configurable silence timeouts.
"""

from __future__ import annotations

import logging
import threading
from typing import Optional
from PySide6.QtCore import QObject, Signal

import speech_recognition as sr
from src.config import AppConfig

logger = logging.getLogger("alfred.voice.stt")


class SpeechRecognitionService(QObject):
    """Transcribes spoken commands from the microphone."""

    listening_started = Signal()
    transcription_complete = Signal(str)
    transcription_failed = Signal(str)

    def __init__(self, config: AppConfig, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.config = config
        self._recognizer = sr.Recognizer()
        self._recognizer.energy_threshold = 300
        self._recognizer.dynamic_energy_threshold = True
        self._recognizer.pause_threshold = max(0.8, self.config.silence_timeout)

        self._is_listening = False
        self._stop_listening_flag = threading.Event()
        self._lock = threading.Lock()

    @property
    def is_listening(self) -> bool:
        return self._is_listening

    def cancel(self) -> None:
        """Cancels any ongoing listening."""
        self._stop_listening_flag.set()
        self._is_listening = False

    def listen_for_command_async(self, timeout: float = 6.0, phrase_time_limit: float = 14.0) -> None:
        """Starts listening in a background worker thread."""
        with self._lock:
            if self._is_listening:
                logger.debug("Already listening for command.")
                return
            self._is_listening = True
            self._stop_listening_flag.clear()

        thread = threading.Thread(
            target=self._listen_worker,
            args=(timeout, phrase_time_limit),
            daemon=True,
            name="Alfred-STT-Worker",
        )
        thread.start()

    def _listen_worker(self, timeout: float, phrase_time_limit: float) -> None:
        """Captures audio and transcribes."""
        self.listening_started.emit()
        try:
            with sr.Microphone() as source:
                logger.info("Microphone open. Listening for command...")
                self._recognizer.adjust_for_ambient_noise(source, duration=0.4)

                if self._stop_listening_flag.is_set():
                    self._is_listening = False
                    return

                try:
                    audio = self._recognizer.listen(
                        source,
                        timeout=timeout,
                        phrase_time_limit=phrase_time_limit,
                    )
                except sr.WaitTimeoutError:
                    logger.info("Listening timed out (no speech detected).")
                    self._is_listening = False
                    self.transcription_failed.emit("Timeout: No speech detected.")
                    return

            if self._stop_listening_flag.is_set():
                self._is_listening = False
                return

            logger.info("Transcribing captured audio...")
            try:
                transcript = self._recognizer.recognize_google(audio, language="en-US")
                transcript = transcript.strip()
                logger.info("Transcription received: '%s'", transcript)
                self._is_listening = False
                self.transcription_complete.emit(transcript)
            except sr.UnknownValueError:
                logger.info("Speech could not be understood.")
                self._is_listening = False
                self.transcription_failed.emit("Audio not understood.")
            except sr.RequestError as e:
                logger.warning("Transcription service request error: %s", e)
                self._is_listening = False
                self.transcription_failed.emit(f"Transcription error: {e}")

        except Exception as e:
            logger.error("Error accessing microphone for transcription: %s", e)
            self._is_listening = False
            self.transcription_failed.emit(f"Microphone error: {e}")


"""Text-to-speech service for Alfred.

Uses ElevenLabs for classy, natural male butler speech, with Windows native
speech (SAPI5 / Microsoft David) as a reliable offline fallback.
Provides instantaneous playback cancellation for stop commands.
"""

from __future__ import annotations

import logging
import os
import tempfile
import threading
from pathlib import Path
from typing import Optional, Callable
from PySide6.QtCore import QObject, Signal, QUrl, Slot
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

from src.config import AppConfig

logger = logging.getLogger("alfred.voice.tts")


class TextToSpeechService(QObject):
    """Text-to-speech engine supporting ElevenLabs with Windows native speech fallback."""

    started = Signal(str)
    finished = Signal()
    interrupted = Signal()
    error = Signal(str)

    def __init__(self, config: AppConfig, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.config = config
        self._is_speaking = False
        self._elevenlabs_failed_once = False
        self._lock = threading.Lock()

        # Audio files
        self._temp_dir = self.config.data_dir / "audio_cache"
        self._temp_dir.mkdir(parents=True, exist_ok=True)
        self._current_audio_file: Optional[Path] = None

        # Media Player for clean playback and instant interruption
        self.audio_output = QAudioOutput(self)
        self.audio_output.setVolume(1.0)
        self.player = QMediaPlayer(self)
        self.player.setAudioOutput(self.audio_output)
        self.player.playbackStateChanged.connect(self._on_playback_state_changed)
        self.player.errorOccurred.connect(self._on_player_error)

        # PyTTSx3 Engine instance initialization
        self._init_pyttsx3()

    def _init_pyttsx3(self) -> None:
        """Initializes pyttsx3 with a male English voice."""
        try:
            import pyttsx3
            self._engine = pyttsx3.init()
            voices = self._engine.getProperty("voices")
            # Prefer Microsoft David or any male English voice
            selected_voice = None
            for v in voices:
                v_name = v.name.lower()
                if "david" in v_name or "george" in v_name or "male" in v_name:
                    selected_voice = v.id
                    break
            if not selected_voice and voices:
                selected_voice = voices[0].id

            if selected_voice:
                self._engine.setProperty("voice", selected_voice)
            self._engine.setProperty("rate", 175)  # Butler dignified cadence
            self._engine.setProperty("volume", 1.0)
        except Exception as e:
            logger.warning("Failed to initialize pyttsx3 engine: %s", e)
            self._engine = None

    @property
    def is_speaking(self) -> bool:
        return self._is_speaking

    def stop(self) -> None:
        """Immediately interrupts and halts speech playback."""
        with self._lock:
            if not self._is_speaking:
                return
            logger.info("Interrupting speech playback immediately.")
            self._is_speaking = False
            try:
                self.player.stop()
            except Exception as e:
                logger.debug("Error stopping player: %s", e)

            # Signal interruption
            self.interrupted.emit()
            self._cleanup_temp_file()

    def speak(self, text: str, on_finished: Optional[Callable[[], None]] = None) -> None:
        """Generates speech for text and begins playback asynchronously."""
        if not text.strip():
            if on_finished:
                on_finished()
            return

        if not self.config.voice_enabled:
            logger.info("Voice is disabled in configuration. Skipping speech: %s", text)
            if on_finished:
                on_finished()
            return

        # Stop existing playback if any
        self.stop()

        # Run synthesis in a background worker thread
        thread = threading.Thread(
            target=self._synthesize_and_play,
            args=(text, on_finished),
            daemon=True,
            name="Alfred-TTS-Worker",
        )
        thread.start()

    def _synthesize_and_play(self, text: str, on_finished: Optional[Callable[[], None]]) -> None:
        """Synthesizes speech via ElevenLabs or Windows Fallback, then triggers playback."""
        audio_file: Optional[Path] = None

        # 1. Try ElevenLabs if configured and not permanently failed
        if self.config.has_elevenlabs() and not self._elevenlabs_failed_once:
            try:
                audio_file = self._synthesize_elevenlabs(text)
            except Exception as e:
                if not self._elevenlabs_failed_once:
                    self._elevenlabs_failed_once = True
                    logger.warning(
                        "ElevenLabs synthesis failed: %s. Falling back to Windows native speech.",
                        e,
                    )

        # 2. Fallback to Windows native speech (pyttsx3)
        if not audio_file:
            try:
                audio_file = self._synthesize_pyttsx3(text)
            except Exception as e:
                logger.error("Native Windows TTS failed: %s", e)
                self.error.emit(f"Speech synthesis failed: {e}")
                if on_finished:
                    on_finished()
                return

        # 3. Play generated audio file
        if audio_file and audio_file.exists():
            with self._lock:
                self._current_audio_file = audio_file
                self._is_speaking = True
                self._on_finished_cb = on_finished

            self.started.emit(text)
            # Must set media and play on Qt event loop
            self.player.setSource(QUrl.fromLocalFile(str(audio_file.resolve())))
            self.player.play()
        else:
            if on_finished:
                on_finished()

    def _synthesize_elevenlabs(self, text: str) -> Path:
        """Synthesizes audio using the official ElevenLabs client."""
        from elevenlabs.client import ElevenLabs

        client = ElevenLabs(api_key=self.config.elevenlabs_api_key)
        audio_generator = client.text_to_speech.convert(
            voice_id=self.config.elevenlabs_voice_id,
            text=text,
            model_id=self.config.elevenlabs_model_id,
        )

        out_path = self._temp_dir / f"eleven_{os.getpid()}_{int(tempfile.mktemp()[-6:])}.mp3"
        with open(out_path, "wb") as f:
            for chunk in audio_generator:
                f.write(chunk)
        return out_path

    def _synthesize_pyttsx3(self, text: str) -> Path:
        """Synthesizes audio using native Windows SAPI5 to a WAV file."""
        import pyttsx3

        out_path = self._temp_dir / f"native_{os.getpid()}_{int(tempfile.mktemp()[-6:])}.wav"

        # Initialize fresh engine in thread to avoid COM apartment conflicts
        engine = pyttsx3.init()
        voices = engine.getProperty("voices")
        for v in voices:
            if "david" in v.name.lower() or "male" in v.name.lower():
                engine.setProperty("voice", v.id)
                break
        engine.setProperty("rate", 175)
        engine.setProperty("volume", 1.0)

        engine.save_to_file(text, str(out_path))
        engine.runAndWait()
        return out_path

    @Slot(QMediaPlayer.PlaybackState)
    def _on_playback_state_changed(self, state: QMediaPlayer.PlaybackState) -> None:
        """Handles playback finish and state cleanup."""
        if state == QMediaPlayer.PlaybackState.StoppedState:
            with self._lock:
                was_speaking = self._is_speaking
                self._is_speaking = False
                cb = getattr(self, "_on_finished_cb", None)
                self._on_finished_cb = None

            self._cleanup_temp_file()
            if was_speaking:
                self.finished.emit()
                if cb:
                    cb()

    @Slot(QMediaPlayer.Error, str)
    def _on_player_error(self, error: QMediaPlayer.Error, error_string: str) -> None:
        """Handles player errors."""
        logger.warning("Media player error: %s (%s)", error_string, error)
        self.stop()

    def _cleanup_temp_file(self) -> None:
        """Cleans up temporary synthesized audio file."""
        if self._current_audio_file and self._current_audio_file.exists():
            try:
                self._current_audio_file.unlink(missing_ok=True)
            except Exception as e:
                logger.debug("Could not remove temp audio file: %s", e)
            self._current_audio_file = None


"""Main application orchestrator for Alfred.

Coordinates the single floating window UI, state controller, fair image balancing,
voice input/output, Gemini AI, financial news briefing, and system tray.
"""

from __future__ import annotations

import logging
import threading
from typing import Optional
from PySide6.QtCore import QObject, Slot, QTimer
from PySide6.QtWidgets import QApplication

from src.config import AppConfig
from src.storage.database import Database
from src.ui.image_manager import ImageManager
from src.ui.state_controller import StateController, AlfredState
from src.ui.floating_window import FloatingWindow
from src.voice.audio_manager import AudioManager
from src.ai.gemini_client import GeminiClient
from src.ai.persona import (
    get_varied_greeting,
    get_varied_acknowledgement,
    get_varied_apology,
    get_varied_stop,
    detect_intent_hint,
)
from src.services.notifications import NotificationService
from src.services.financial_news import FinancialNewsService
from src.services.briefing import BriefingService

logger = logging.getLogger("alfred.app")


class AlfredApp(QObject):
    """The root coordinator for the Alfred desktop assistant."""

    def __init__(self, config: AppConfig, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.config = config

        # 1. Local Storage
        self.db = Database(self.config.full_database_path)

        # 2. UI Subsystems (Strictly ONE window)
        self.image_manager = ImageManager(self.config.assets_dir, target_size=self.config.window_size - 28)
        self.state_controller = StateController(
            database=self.db,
            default_image=self.config.default_image,
            min_display_duration=self.config.min_image_duration,
        )
        self.floating_window = FloatingWindow(
            image_manager=self.image_manager,
            state_controller=self.state_controller,
            window_size=self.config.window_size,
        )

        # 3. Notification Service
        self.notifications = NotificationService(self.floating_window.tray_icon)

        # 4. Voice & Audio Subsystems
        self.audio = AudioManager(self.config, self)

        # 5. AI Integration
        self.gemini = GeminiClient(self.config)

        # 6. Financial News & Briefing Services
        self.news_service = FinancialNewsService(self.config)
        self.briefing_service = BriefingService(
            config=self.config,
            news_service=self.news_service,
            gemini_client=self.gemini,
            database=self.db,
            notification_service=self.notifications,
            speak_callback=self._speak_with_speaking_state,
        )

        # Connect inter-subsystem signals
        self._wire_signals()

    def _wire_signals(self) -> None:
        """Connects UI, audio, and background workflow signals."""
        # Audio manager events
        self.audio.wake_word_triggered.connect(self.on_wake_word_triggered)
        self.audio.command_transcribed.connect(self.on_command_transcribed)
        self.audio.command_failed.connect(self.on_command_failed)
        self.audio.speech_finished.connect(self.on_speech_finished)
        self.audio.stop_command.connect(self.on_stop_command)

        # Tray actions
        self.floating_window.toggle_mic_requested.connect(self.on_toggle_microphone)
        self.floating_window.trigger_briefing_requested.connect(self.on_trigger_briefing)
        self.floating_window.clear_history_requested.connect(self.on_clear_history)
        self.floating_window.exit_requested.connect(self.shutdown)

    def start(self) -> None:
        """Launches the assistant, presents the single window, and begins listening."""
        logger.info("Starting Alfred Assistant...")
        self.floating_window.show()

        # Start background wake-word listener if enabled
        self.audio.start()

        # Start briefing scheduler if enabled
        self.briefing_service.start_scheduler()

        # Initial idle state
        self.state_controller.transition_to(AlfredState.IDLE, status_text="")
        logger.info("Alfred is active and standing by at top center.")

    def shutdown(self) -> None:
        """Performs a clean shutdown of all background services."""
        logger.info("Shutting down Alfred Assistant...")
        self.audio.stop()
        self.briefing_service.stop_scheduler()
        self.floating_window.close()
        QApplication.quit()

    # --- Interaction Flow Handlers ---

    @Slot(str)
    def on_wake_word_triggered(self, immediate_command: str) -> None:
        """Invoked when user says 'Alfred' or 'Hey Alfred'."""
        logger.info("Wake word triggered. Immediate command: '%s'", immediate_command)

        if immediate_command.strip():
            # Compound command: user spoke wake word and request together
            self.state_controller.transition_to(
                AlfredState.THINKING,
                status_text="Thinking...",
            )
            self._process_command_async(immediate_command.strip())
        else:
            # Standalone wake phrase: switch to listening and wait for command
            self.state_controller.transition_to(
                AlfredState.LISTENING,
                status_text="Listening...",
            )
            self.audio.listen_for_command()

    @Slot(str)
    def on_command_transcribed(self, transcript: str) -> None:
        """Invoked when speech recognition completes."""
        logger.info("User command transcribed: '%s'", transcript)
        self.state_controller.transition_to(
            AlfredState.THINKING,
            status_text="Thinking...",
        )
        self._process_command_async(transcript)

    @Slot(str)
    def on_command_failed(self, reason: str) -> None:
        """Invoked when audio was not understood or timed out."""
        logger.info("Command capture ended: %s", reason)
        if "Timeout" in reason:
            # User simply did not speak; return quietly to idle
            self.state_controller.transition_to(AlfredState.IDLE, status_text="")
        else:
            # Apologize politely and return to idle
            apology = get_varied_apology()
            self.state_controller.transition_to(
                AlfredState.ERROR,
                status_text="Pardon?",
            )
            self.audio.speak(apology)

    def _speak_with_speaking_state(self, text: str, intent_hint: Optional[str] = None) -> None:
        """Transitions to SPEAKING with fair image selection and plays TTS."""
        self.state_controller.transition_to(
            AlfredState.SPEAKING,
            intent_hint=intent_hint,
            status_text="Speaking...",
        )
        self.audio.speak(text)

    def _process_command_async(self, command: str) -> None:
        """Processes user command in a background thread to avoid freezing UI."""
        thread = threading.Thread(
            target=self._execute_command,
            args=(command,),
            daemon=True,
            name="Alfred-Command-Processor",
        )
        thread.start()

    def _execute_command(self, command: str) -> None:
        """Handles command routing, briefings, intent classification, and Gemini AI."""
        cmd_lower = command.lower().strip()

        # 1. Stop commands
        if any(cmd_lower == s or cmd_lower.startswith(s + " ") for s in ("stop", "cancel", "quiet", "hush")):
            self.on_stop_command()
            return

        # 2. Daily Briefing commands
        if any(phrase in cmd_lower for phrase in ("briefing", "market news", "what's happening in the market", "financial news", "market update")):
            logger.info("Routing request to Financial Briefing Service...")
            briefing = self.briefing_service.generate_briefing()
            hint = detect_intent_hint(command, briefing)
            self._speak_with_speaking_state(briefing, intent_hint=hint)
            return

        # 3. Clear history commands
        if "clear history" in cmd_lower or "forget everything" in cmd_lower or "reset memory" in cmd_lower:
            self.db.clear_conversation_history()
            reply = "I have cleared my conversation memory as requested, Sir."
            self._speak_with_speaking_state(reply, intent_hint="success")
            return

        # 4. Pure greetings
        if cmd_lower in ("hello", "hey", "good morning", "good evening", "good afternoon", "hi alfred", "greetings"):
            reply = get_varied_greeting()
            self._speak_with_speaking_state(reply, intent_hint="greeting")
            return

        # 5. Standard Conversational & Reasoning Requests via Gemini
        history = self.db.get_recent_conversation(limit=6)
        response_text = self.gemini.generate_response(
            prompt=command,
            conversation_history=history,
        )

        # Record conversation in SQLite
        try:
            self.db.add_conversation_turn("user", command)
            self.db.add_conversation_turn("model", response_text)
        except Exception as e:
            logger.warning("Failed to store conversation turn: %s", e)

        # Determine emotional hint for image rotation
        hint = detect_intent_hint(command, response_text)
        self._speak_with_speaking_state(response_text, intent_hint=hint)

    @Slot()
    def on_speech_finished(self) -> None:
        """Invoked when TTS speech concludes."""
        logger.info("Speech finished. Returning to idle state.")
        # Auto return to IDLE (v smoking.png) after brief pause
        self.state_controller.transition_to(
            AlfredState.IDLE,
            status_text="",
            auto_idle_after=1.0,
        )

    @Slot()
    def on_stop_command(self) -> None:
        """Invoked when a stop command is recognized."""
        logger.info("Stop command executed.")
        self.audio.interrupt()
        self.state_controller.transition_to(
            AlfredState.CANCELLED,
            status_text="Stopped",
            auto_idle_after=2.0,
            force=True,
        )

    # --- Tray Menu Actions ---

    @Slot()
    def on_toggle_microphone(self) -> None:
        """Toggles wake-word and microphone listening."""
        is_active = self.audio.toggle_microphone()
        status_msg = "Microphone listening is active, Sir." if is_active else "Microphone has been muted, Sir."
        self.notifications.notify("Alfred Microphone", status_msg)
        if not is_active:
            self.state_controller.transition_to(AlfredState.PAUSED, status_text="Paused")
        else:
            self.state_controller.transition_to(AlfredState.IDLE, status_text="")

    @Slot()
    def on_trigger_briefing(self) -> None:
        """Manually triggers the daily briefing from tray menu."""
        logger.info("Manual briefing requested from tray menu.")
        self.state_controller.transition_to(AlfredState.THINKING, status_text="Gathering news...")
        threading.Thread(
            target=lambda: self.briefing_service.deliver_briefing(speak=True),
            daemon=True,
            name="Alfred-Manual-Briefing",
        ).start()

    @Slot()
    def on_clear_history(self) -> None:
        """Clears local conversation history from tray menu."""
        self.db.clear_conversation_history()
        self.notifications.notify("Alfred Memory", "Conversation history cleared successfully.")
        logger.info("Cleared conversation memory from tray menu.")


"""Daily briefing and scheduled market briefing service for Alfred.

Schedules and generates daily morning reports combining verified market developments,
key economic watches, productivity reminders, and wellbeing check-ins, defaulting
to 8:30 AM Asia/Kolkata.
"""

from __future__ import annotations

import logging
from typing import Optional, Callable
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from src.config import AppConfig
from src.storage.database import Database
from src.ai.gemini_client import GeminiClient
from src.services.financial_news import FinancialNewsService, NewsArticle
from src.services.notifications import NotificationService

logger = logging.getLogger("alfred.services.briefing")

BRIEFING_SYSTEM_PROMPT = """You are Alfred, providing a concise, classy morning financial and wellbeing briefing to your employer ('Sir').
Format the briefing strictly in 3 to 4 natural spoken sentences:
1. Summarize 1-2 key developments from the verified news provided.
2. Note what sectors or economic events are worth observing today.
3. Conclude with a brief, dignified personal productivity reminder and a gentle wellbeing check-in.
Do not use markdown bullets, bolding, asterisks, or hashtags. Deliver clean, dignified spoken prose.
"""


class BriefingService:
    """Manages scheduled and on-demand daily briefings."""

    def __init__(
        self,
        config: AppConfig,
        news_service: FinancialNewsService,
        gemini_client: GeminiClient,
        database: Optional[Database] = None,
        notification_service: Optional[NotificationService] = None,
        speak_callback: Optional[Callable[[str], None]] = None,
    ):
        self.config = config
        self.news_service = news_service
        self.gemini_client = gemini_client
        self.db = database
        self.notifications = notification_service
        self.speak_callback = speak_callback

        self.scheduler = BackgroundScheduler()
        self._is_scheduled = False

    def generate_briefing(self) -> str:
        """Fetches real financial news and generates a polished Alfred briefing."""
        logger.info("Generating daily briefing...")
        articles = self.news_service.fetch_market_news(limit=4)

        if not articles:
            briefing = (
                "Good day, Sir. I was unable to retrieve live financial headlines today due to an unreachable data feed. "
                "I shall monitor the wires and inform you as soon as verified developments arrive. "
                "May your day be productive and focused, Sir."
            )
            if self.db:
                self.db.record_briefing(briefing)
            return briefing

        # Prepare context from verified news
        news_context = "\n".join(
            [f"- {a.title} (Source: {a.source}, Published: {a.published_at})" for a in articles]
        )

        user_prompt = f"Here are today's verified market headlines:\n{news_context}\n\nPlease deliver my morning briefing, Sir."

        briefing_text = self.gemini_client.generate_response(
            prompt=user_prompt,
            custom_system_instruction=BRIEFING_SYSTEM_PROMPT,
        )

        # Fallback if Gemini is unconfigured or returned an error
        if "API key has not yet been configured" in briefing_text or "connection disturbance" in briefing_text:
            first_titles = " Additionally, ".join([a.title for a in articles[:2]])
            briefing_text = (
                f"Good day, Sir. Here are today's verified market headlines: {first_titles}. "
                "I shall remain watchful of market shifts throughout the session. Remember to take a restorative pause when needed, Sir."
            )

        if self.db:
            try:
                self.db.record_briefing(briefing_text)
            except Exception as e:
                logger.warning("Failed to record briefing in database: %s", e)

        return briefing_text

    def deliver_briefing(self, speak: bool = True) -> str:
        """Generates and delivers the daily briefing via notification and optional speech."""
        briefing = self.generate_briefing()

        # Desktop notification
        if self.notifications:
            self.notifications.notify(
                title=f"{self.config.alfred_name} — Daily Briefing",
                message=briefing,
            )

        # Spoken audio
        if speak and self.speak_callback and self.config.voice_enabled:
            self.speak_callback(briefing)

        return briefing

    def start_scheduler(self) -> None:
        """Starts the APScheduler background briefing job."""
        if not self.config.daily_briefing_enabled:
            logger.info("Daily briefings are disabled in configuration.")
            return

        try:
            time_parts = self.config.daily_briefing_time.split(":")
            hour = int(time_parts[0])
            minute = int(time_parts[1]) if len(time_parts) > 1 else 0

            trigger = CronTrigger(
                hour=hour,
                minute=minute,
                timezone=self.config.timezone,
            )

            self.scheduler.add_job(
                func=self.deliver_briefing,
                trigger=trigger,
                id="alfred_daily_briefing",
                name="Alfred Daily Financial Briefing",
                replace_existing=True,
                kwargs={"speak": True},
            )
            self.scheduler.start()
            self._is_scheduled = True
            logger.info(
                "Daily briefing scheduled for %02d:%02d in timezone %s",
                hour,
                minute,
                self.config.timezone,
            )
        except Exception as e:
            logger.error("Failed to start daily briefing scheduler: %s", e)

    def stop_scheduler(self) -> None:
        """Stops the scheduler cleanly."""
        if self._is_scheduled and self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            self._is_scheduled = False
            logger.info("Daily briefing scheduler stopped.")


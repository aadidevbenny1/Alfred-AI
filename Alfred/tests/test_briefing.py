"""Tests for Financial News, Daily Briefing, and APScheduler scheduling."""

from apscheduler.triggers.cron import CronTrigger
from src.config import AppConfig
from src.storage.database import Database
from src.services.financial_news import FinancialNewsService, NewsArticle
from src.services.briefing import BriefingService
from src.ai.gemini_client import GeminiClient


class MockNewsService(FinancialNewsService):
    """Mock news service returning verified sample articles."""

    def __init__(self, articles=None):
        super().__init__(AppConfig())
        self._articles = articles if articles is not None else [
            NewsArticle(
                title="Global Markets Rally as Tech Shares Advance",
                source="Reuters",
                published_at="2026-11-03 08:00:00",
                summary="Major indices gained as investors assessed economic data.",
                url="https://example.com/news1",
            )
        ]

    def fetch_market_news(self, limit: int = 5):
        return self._articles[:limit]


def test_briefing_schedule_trigger():
    """Verifies daily briefing defaults to 8:30 AM Asia/Kolkata."""
    cfg = AppConfig()
    time_parts = cfg.daily_briefing_time.split(":")
    hour = int(time_parts[0])
    minute = int(time_parts[1])

    trigger = CronTrigger(hour=hour, minute=minute, timezone=cfg.timezone)
    assert trigger.fields[5].expressions[0].first == 8
    assert trigger.fields[6].expressions[0].first == 30
    assert str(trigger.timezone) == "Asia/Kolkata"


def test_briefing_generation_fallback(tmp_path):
    """Verifies that when Gemini is unconfigured, a polite briefing is generated with real headlines."""
    cfg = AppConfig(gemini_api_key="")  # Unconfigured
    db = Database(tmp_path / "test.db")
    news_svc = MockNewsService()
    gemini_client = GeminiClient(cfg)

    briefing_svc = BriefingService(
        config=cfg,
        news_service=news_svc,
        gemini_client=gemini_client,
        database=db,
    )

    briefing = briefing_svc.generate_briefing()
    assert "Sir" in briefing
    assert "Global Markets Rally" in briefing

    # Verify recorded in DB
    last = db.get_last_briefing()
    assert last is not None
    assert "Global Markets Rally" in last["content"]


def test_briefing_honest_when_news_empty(tmp_path):
    """Verifies Alfred never fabricates news if data feed is unreachable."""
    cfg = AppConfig(gemini_api_key="")
    db = Database(tmp_path / "test.db")
    empty_news_svc = MockNewsService(articles=[])
    gemini_client = GeminiClient(cfg)

    briefing_svc = BriefingService(
        config=cfg,
        news_service=empty_news_svc,
        gemini_client=gemini_client,
        database=db,
    )

    briefing = briefing_svc.generate_briefing()
    assert "unable to retrieve" in briefing.lower() or "unreachable" in briefing.lower()
    # Does NOT invent fake market profits or prices
    assert "$" not in briefing
    assert "%" not in briefing

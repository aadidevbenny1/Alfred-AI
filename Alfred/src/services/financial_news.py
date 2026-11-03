"""Financial news provider integration for Alfred.

Retrieves real, verified financial headlines from supported providers (RSS, NewsAPI,
AlphaVantage, or Finnhub) with strict adherence to data integrity.
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import List, Optional
import requests

from src.config import AppConfig

logger = logging.getLogger("alfred.services.news")

# Verified reliable financial RSS sources
FINANCIAL_RSS_FEEDS = [
    "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=en-US&gl=US&ceid=US:en",
    "https://finance.yahoo.com/news/rssindex",
]


@dataclass
class NewsArticle:
    """Represents a verified financial news article."""

    title: str
    source: str
    published_at: str
    summary: str
    url: str


class FinancialNewsService:
    """Fetches real market news from configured data sources."""

    def __init__(self, config: AppConfig):
        self.config = config

    def fetch_market_news(self, limit: int = 5) -> List[NewsArticle]:
        """Fetches latest financial news articles from the configured provider."""
        provider = self.config.financial_news_provider.lower()

        try:
            if provider == "newsapi" and self.config.financial_news_api_key:
                return self._fetch_newsapi(limit)
            elif provider == "alphavantage" and self.config.financial_news_api_key:
                return self._fetch_alphavantage(limit)
            elif provider == "finnhub" and self.config.financial_news_api_key:
                return self._fetch_finnhub(limit)
            else:
                # Default reliable RSS provider
                return self._fetch_rss(limit)
        except Exception as e:
            logger.error("Failed to fetch news from provider '%s': %s", provider, e)
            # Try RSS fallback if specific API failed
            if provider != "rss":
                try:
                    logger.info("Attempting fallback to verified financial RSS...")
                    return self._fetch_rss(limit)
                except Exception as rss_err:
                    logger.error("RSS fallback also failed: %s", rss_err)
            return []

    def _fetch_rss(self, limit: int = 5) -> List[NewsArticle]:
        """Fetches and parses real headlines from verified financial RSS feeds."""
        articles: List[NewsArticle] = []

        for feed_url in FINANCIAL_RSS_FEEDS:
            try:
                resp = requests.get(
                    feed_url,
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AlfredButler/1.0"},
                    timeout=8.0,
                )
                if resp.status_code != 200:
                    continue

                root = ET.fromstring(resp.content)
                items = root.findall(".//item")

                for item in items:
                    title_elem = item.find("title")
                    link_elem = item.find("link")
                    pub_elem = item.find("pubDate")
                    desc_elem = item.find("description")
                    source_elem = item.find("source")

                    title = title_elem.text.strip() if title_elem is not None and title_elem.text else ""
                    url = link_elem.text.strip() if link_elem is not None and link_elem.text else ""
                    pub_date = pub_elem.text.strip() if pub_elem is not None and pub_elem.text else ""
                    desc = desc_elem.text.strip() if desc_elem is not None and desc_elem.text else ""
                    source_name = source_elem.text.strip() if source_elem is not None and source_elem.text else "Financial Press"

                    if title:
                        articles.append(
                            NewsArticle(
                                title=title,
                                source=source_name,
                                published_at=pub_date,
                                summary=desc[:200],
                                url=url,
                            )
                        )

                    if len(articles) >= limit:
                        return articles

            except Exception as e:
                logger.warning("Error reading feed %s: %s", feed_url, e)

        return articles

    def _fetch_newsapi(self, limit: int = 5) -> List[NewsArticle]:
        """Fetches from NewsAPI endpoint."""
        url = "https://newsapi.org/v2/top-headlines"
        params = {
            "category": "business",
            "language": "en",
            "pageSize": limit,
            "apiKey": self.config.financial_news_api_key,
        }
        resp = requests.get(url, params=params, timeout=8.0)
        resp.raise_for_status()
        data = resp.json()

        articles: List[NewsArticle] = []
        for a in data.get("articles", [])[:limit]:
            articles.append(
                NewsArticle(
                    title=a.get("title", ""),
                    source=a.get("source", {}).get("name", "NewsAPI"),
                    published_at=a.get("publishedAt", ""),
                    summary=a.get("description", "") or "",
                    url=a.get("url", ""),
                )
            )
        return articles

    def _fetch_alphavantage(self, limit: int = 5) -> List[NewsArticle]:
        """Fetches from Alpha Vantage News Sentiment endpoint."""
        url = "https://www.alphavantage.co/query"
        params = {
            "function": "NEWS_SENTIMENT",
            "topics": "financial_markets,economy_macro",
            "apikey": self.config.financial_news_api_key,
        }
        resp = requests.get(url, params=params, timeout=8.0)
        resp.raise_for_status()
        data = resp.json()

        articles: List[NewsArticle] = []
        feed = data.get("feed", [])
        for item in feed[:limit]:
            articles.append(
                NewsArticle(
                    title=item.get("title", ""),
                    source=item.get("source", "AlphaVantage"),
                    published_at=item.get("time_published", ""),
                    summary=item.get("summary", "") or "",
                    url=item.get("url", ""),
                )
            )
        return articles

    def _fetch_finnhub(self, limit: int = 5) -> List[NewsArticle]:
        """Fetches from Finnhub General Market News endpoint."""
        url = "https://finnhub.io/api/v1/news"
        params = {
            "category": "general",
            "token": self.config.financial_news_api_key,
        }
        resp = requests.get(url, params=params, timeout=8.0)
        resp.raise_for_status()
        data = resp.json()

        articles: List[NewsArticle] = []
        for item in data[:limit]:
            articles.append(
                NewsArticle(
                    title=item.get("headline", ""),
                    source=item.get("source", "Finnhub"),
                    published_at=str(item.get("datetime", "")),
                    summary=item.get("summary", "") or "",
                    url=item.get("url", ""),
                )
            )
        return articles


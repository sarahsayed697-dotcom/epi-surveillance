"""
EpiSurveillance — Data Collectors
Modular collectors for each source type. All return list[RawSignalInput].
New sources: subclass BaseCollector and register in CollectorRegistry.
"""
import asyncio
import hashlib
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional
import httpx
from dataclasses import dataclass
from config.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class RawSignalInput:
    """Intermediate DTO before DB insertion."""
    source_type: str
    source_url: str
    source_id: str
    published_at: Optional[datetime]
    text_original: str
    author: str = ""
    engagement_score: float = 0.0


class BaseCollector(ABC):
    """Abstract base for all collectors."""

    source_type: str = "unknown"
    max_items: int = settings.MAX_ITEMS_PER_SOURCE

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.client.aclose()

    @abstractmethod
    async def collect(self, query: str = "") -> list[RawSignalInput]:
        """Collect signals. Returns list of RawSignalInput."""
        ...

    def _parse_dt(self, dt_string: Optional[str]) -> Optional[datetime]:
        if not dt_string:
            return None
        for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%a %b %d %H:%M:%S +0000 %Y"):
            try:
                return datetime.strptime(dt_string, fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        return None


# ── Twitter / X Collector ────────────────────────────────────────────────────

class TwitterCollector(BaseCollector):
    source_type = "twitter"
    BASE_URL = "https://api.twitter.com/2"

    async def collect(self, query: str = "") -> list[RawSignalInput]:
        if not settings.TWITTER_BEARER_TOKEN:
            logger.warning("Twitter bearer token not configured. Skipping.")
            return []

        # Build disease-focused search query
        disease_terms = " OR ".join([
            f'"{d}"' for d in settings.ZOONOTIC_DISEASES[:15]
        ])
        full_query = f"({disease_terms}) (outbreak OR cases OR deaths OR spillover) lang:en -is:retweet"

        headers = {"Authorization": f"Bearer {settings.TWITTER_BEARER_TOKEN}"}
        params = {
            "query": full_query,
            "max_results": min(self.max_items, 100),
            "tweet.fields": "created_at,author_id,public_metrics,lang",
            "expansions": "author_id",
        }

        try:
            resp = await self.client.get(
                f"{self.BASE_URL}/tweets/search/recent",
                headers=headers,
                params=params,
            )
            resp.raise_for_status()
            data = resp.json()

            results = []
            for tweet in data.get("data", []):
                engagement = 0
                metrics = tweet.get("public_metrics", {})
                engagement = (
                    metrics.get("retweet_count", 0) * 3
                    + metrics.get("like_count", 0)
                    + metrics.get("reply_count", 0) * 2
                )
                results.append(RawSignalInput(
                    source_type=self.source_type,
                    source_url=f"https://twitter.com/i/web/status/{tweet['id']}",
                    source_id=tweet["id"],
                    published_at=self._parse_dt(tweet.get("created_at")),
                    text_original=tweet["text"],
                    author=tweet.get("author_id", ""),
                    engagement_score=float(engagement),
                ))
            logger.info(f"Twitter collected {len(results)} tweets")
            return results

        except httpx.HTTPError as e:
            logger.error(f"Twitter API error: {e}")
            return []


# ── Reddit Collector ─────────────────────────────────────────────────────────

class RedditCollector(BaseCollector):
    source_type = "reddit"
    SUBREDDITS = [
        "epidemiology", "medicine", "publichealth", "worldnews",
        "Coronavirus", "biology", "HealthyFood", "science",
    ]

    async def collect(self, query: str = "") -> list[RawSignalInput]:
        results = []
        search_terms = " OR ".join(settings.ZOONOTIC_DISEASES[:10])

        for subreddit in self.SUBREDDITS[:4]:  # Rate-limit safe
            try:
                resp = await self.client.get(
                    f"https://www.reddit.com/r/{subreddit}/search.json",
                    params={
                        "q": search_terms,
                        "sort": "new",
                        "limit": 25,
                        "t": "week",
                    },
                    headers={"User-Agent": "EpiSurveillance/1.0"},
                )
                resp.raise_for_status()
                data = resp.json()

                for post in data.get("data", {}).get("children", []):
                    p = post["data"]
                    text = f"{p.get('title', '')} {p.get('selftext', '')}".strip()
                    if len(text) < 50:
                        continue
                    engagement = p.get("score", 0) + p.get("num_comments", 0) * 2
                    results.append(RawSignalInput(
                        source_type=self.source_type,
                        source_url=f"https://reddit.com{p.get('permalink', '')}",
                        source_id=p["id"],
                        published_at=datetime.fromtimestamp(
                            p.get("created_utc", 0), tz=timezone.utc
                        ),
                        text_original=text[:2000],
                        author=p.get("author", ""),
                        engagement_score=float(engagement),
                    ))
                await asyncio.sleep(1)  # Reddit rate limit
            except httpx.HTTPError as e:
                logger.error(f"Reddit error for r/{subreddit}: {e}")

        logger.info(f"Reddit collected {len(results)} posts")
        return results


# ── WHO/CDC/FAO RSS Feed Collector ───────────────────────────────────────────

class OfficialFeedCollector(BaseCollector):
    """Collects from official public health RSS/Atom feeds."""
    source_type = "who"

    FEEDS = {
        "who": "https://www.who.int/rss-feeds/news-english.xml",
        "cdc": "https://tools.cdc.gov/api/v2/resources/media/316422.rss",
        "fao": "https://www.fao.org/news/rss-news-releases-en.xml",
        "promed": "https://promedmail.org/feed/",
    }

    async def _fetch_feed(self, name: str, url: str) -> list[RawSignalInput]:
        """Fetch and parse an RSS feed."""
        try:
            resp = await self.client.get(url, follow_redirects=True)
            resp.raise_for_status()
            # Simple XML extraction without lxml dependency
            content = resp.text
            items = []

            import re
            entries = re.findall(r"<item>(.*?)</item>", content, re.DOTALL)
            if not entries:
                entries = re.findall(r"<entry>(.*?)</entry>", content, re.DOTALL)

            for entry in entries[:50]:
                title = re.search(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", entry, re.DOTALL)
                desc = re.search(r"<description>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</description>", entry, re.DOTALL)
                link = re.search(r"<link>(.*?)</link>", entry, re.DOTALL)
                pub_date = re.search(r"<pubDate>(.*?)</pubDate>", entry, re.DOTALL)
                guid = re.search(r"<guid[^>]*>(.*?)</guid>", entry, re.DOTALL)

                title_text = title.group(1).strip() if title else ""
                desc_text = re.sub(r"<[^>]+>", " ", desc.group(1)).strip() if desc else ""
                text = f"{title_text}. {desc_text}".strip()

                if len(text) < 20:
                    continue

                items.append(RawSignalInput(
                    source_type=name,
                    source_url=link.group(1).strip() if link else url,
                    source_id=guid.group(1).strip() if guid else hashlib.md5(text.encode()).hexdigest(),
                    published_at=self._parse_dt(pub_date.group(1).strip() if pub_date else None),
                    text_original=text[:3000],
                    author=name.upper(),
                    engagement_score=100.0,  # Official sources get high engagement weight
                ))
            return items

        except httpx.HTTPError as e:
            logger.error(f"Feed fetch error for {name}: {e}")
            return []

    async def collect(self, query: str = "") -> list[RawSignalInput]:
        tasks = [self._fetch_feed(name, url) for name, url in self.FEEDS.items()]
        all_results = await asyncio.gather(*tasks)
        flat = [item for sublist in all_results for item in sublist]
        logger.info(f"Official feeds collected {len(flat)} items")
        return flat


# ── News API Collector ───────────────────────────────────────────────────────

class NewsCollector(BaseCollector):
    source_type = "news"

    async def collect(self, query: str = "") -> list[RawSignalInput]:
        if not settings.NEWSAPI_KEY:
            logger.warning("NewsAPI key not configured. Skipping.")
            return []

        search_q = " OR ".join(settings.ZOONOTIC_DISEASES[:8])
        try:
            resp = await self.client.get(
                "https://newsapi.org/v2/everything",
                params={
                    "q": search_q,
                    "language": "en",
                    "sortBy": "publishedAt",
                    "pageSize": min(self.max_items, 100),
                    "apiKey": settings.NEWSAPI_KEY,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            results = []
            for article in data.get("articles", []):
                text = f"{article.get('title', '')} {article.get('description', '')} {article.get('content', '')}".strip()
                if len(text) < 50:
                    continue
                results.append(RawSignalInput(
                    source_type=self.source_type,
                    source_url=article.get("url", ""),
                    source_id=hashlib.md5(article.get("url", text).encode()).hexdigest(),
                    published_at=self._parse_dt(article.get("publishedAt")),
                    text_original=text[:3000],
                    author=article.get("source", {}).get("name", ""),
                    engagement_score=50.0,
                ))
            logger.info(f"NewsAPI collected {len(results)} articles")
            return results
        except httpx.HTTPError as e:
            logger.error(f"NewsAPI error: {e}")
            return []


# ── Collector Registry ───────────────────────────────────────────────────────

class CollectorRegistry:
    """Runs all collectors and aggregates results."""

    COLLECTORS = [
        TwitterCollector,
        RedditCollector,
        OfficialFeedCollector,
        NewsCollector,
    ]

    async def collect_all(self) -> list[RawSignalInput]:
        all_signals = []
        for CollectorClass in self.COLLECTORS:
            try:
                async with CollectorClass() as collector:
                    signals = await collector.collect()
                    all_signals.extend(signals)
            except Exception as e:
                logger.error(f"Collector {CollectorClass.__name__} failed: {e}")

        # Deduplicate by source_id
        seen = set()
        unique = []
        for s in all_signals:
            key = f"{s.source_type}:{s.source_id}"
            if key not in seen:
                seen.add(key)
                unique.append(s)

        logger.info(f"Total collected: {len(all_signals)}, unique: {len(unique)}")
        return unique

import time
from dataclasses import dataclass
from datetime import datetime

import feedparser
import httpx

from simbert.news.http import FetchError, get_with_retries
from simbert.news.timeutil import to_utc

# A feed failure is a fetch failure. The name is kept for readability.
FeedError = FetchError


@dataclass(frozen=True)
class FeedEntry:
    guid: str
    url: str
    title: str
    published_at: datetime | None


@dataclass(frozen=True)
class FeedResult:
    not_modified: bool
    entries: list[FeedEntry]
    etag: str | None
    last_modified: str | None


def _parse_entries(content: bytes) -> list[FeedEntry]:
    parsed = feedparser.parse(content)
    if parsed.bozo and not parsed.entries:
        raise FeedError(f"unreadable feed: {parsed.bozo_exception}")

    entries = []
    for item in parsed.entries:
        url = item.get("link")
        if not url:
            continue
        raw_time = item.get("published") or item.get("updated")
        try:
            published_at = to_utc(raw_time) if raw_time else None
        except ValueError:
            published_at = None
        entries.append(FeedEntry(
            guid=item.get("id") or url,
            url=url,
            title=(item.get("title") or "").strip(),
            published_at=published_at,
        ))
    return entries


def fetch_feed(
    client: httpx.Client,
    url: str,
    etag: str | None = None,
    last_modified: str | None = None,
    max_attempts: int = 4,
    base_delay: float = 2.0,
    sleep=time.sleep,
) -> FeedResult:
    headers = {}
    if etag:
        headers["If-None-Match"] = etag
    if last_modified:
        headers["If-Modified-Since"] = last_modified

    response = get_with_retries(client, url, headers, max_attempts, base_delay, sleep)

    if response.status_code == 304:
        return FeedResult(True, [], etag, last_modified)
    return FeedResult(
        False,
        _parse_entries(response.content),
        response.headers.get("etag"),
        response.headers.get("last-modified"),
    )
from datetime import datetime, timezone

import httpx
import pytest

from simbert.news.feeds import FeedError, fetch_feed

FEED_URL = "https://example.test/feed.xml"
LAST_MODIFIED = "Wed, 28 Oct 2026 18:00:00 GMT"
RSS = b"""<?xml version="1.0"?>
<rss version="2.0"><channel><title>Fed monetary policy</title>
<item>
  <title>Federal Reserve issues FOMC statement</title>
  <link>https://www.federalreserve.gov/newsevents/pressreleases/monetary20261028a.htm</link>
  <guid>https://www.federalreserve.gov/newsevents/pressreleases/monetary20261028a.htm</guid>
  <pubDate>Wed, 28 Oct 2026 18:00:00 GMT</pubDate>
</item>
<item>
  <title>Item with an unreadable date</title>
  <link>https://example.test/b.htm</link>
  <pubDate>sometime soon</pubDate>
</item>
</channel></rss>"""


def make_client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def no_sleep(_seconds):
    pass


def test_parses_entries_and_cache_headers():
    def handler(request):
        return httpx.Response(200, content=RSS,
                              headers={"ETag": '"v1"', "Last-Modified": LAST_MODIFIED})

    result = fetch_feed(make_client(handler), FEED_URL, sleep=no_sleep)

    assert not result.not_modified
    assert result.etag == '"v1"'
    assert result.last_modified == LAST_MODIFIED
    fomc, bad_date = result.entries
    assert fomc.title == "Federal Reserve issues FOMC statement"
    assert fomc.published_at == datetime(2026, 10, 28, 18, 0, tzinfo=timezone.utc)
    assert bad_date.published_at is None
    assert bad_date.guid == "https://example.test/b.htm"


def test_sends_conditional_headers_and_handles_304():
    seen = {}

    def handler(request):
        seen["headers"] = request.headers
        return httpx.Response(304)

    result = fetch_feed(make_client(handler), FEED_URL,
                        etag='"v1"', last_modified=LAST_MODIFIED, sleep=no_sleep)

    assert result.not_modified
    assert result.entries == []
    assert result.etag == '"v1"'
    assert seen["headers"]["If-None-Match"] == '"v1"'
    assert seen["headers"]["If-Modified-Since"] == LAST_MODIFIED


def test_retries_server_errors_with_exponential_backoff():
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) < 3:
            return httpx.Response(503)
        return httpx.Response(200, content=RSS)

    delays = []
    result = fetch_feed(make_client(handler), FEED_URL, sleep=delays.append)

    assert len(calls) == 3
    assert delays == [2.0, 4.0]
    assert len(result.entries) == 2


def test_honours_retry_after():
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(429, headers={"Retry-After": "30"})
        return httpx.Response(200, content=RSS)

    delays = []
    fetch_feed(make_client(handler), FEED_URL, sleep=delays.append)

    assert delays == [30]


def test_gives_up_after_max_attempts():
    def handler(request):
        return httpx.Response(500)

    delays = []
    with pytest.raises(FeedError):
        fetch_feed(make_client(handler), FEED_URL, max_attempts=3, sleep=delays.append)

    assert len(delays) == 2


def test_does_not_retry_client_errors():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(404)

    with pytest.raises(FeedError):
        fetch_feed(make_client(handler), FEED_URL, sleep=no_sleep)

    assert len(calls) == 1


def test_network_errors_are_retried():
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            raise httpx.ConnectError("connection refused", request=request)
        return httpx.Response(200, content=RSS)

    result = fetch_feed(make_client(handler), FEED_URL, sleep=no_sleep)

    assert len(calls) == 2
    assert len(result.entries) == 2
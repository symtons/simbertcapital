from datetime import datetime, timedelta, timezone

import httpx
import pytest

from simbert.news.collector import collect_source
from simbert.news.store import connect, init_db

FEED_URL = "https://fed.test/feeds/press_monetary.xml"
PAGE_URL = "https://fed.test/newsevents/pressreleases/monetary20261028a.htm"

RSS = f"""<?xml version="1.0"?>
<rss version="2.0"><channel><title>Fed monetary policy</title>
<item>
  <title>Federal Reserve issues FOMC statement</title>
  <link>{PAGE_URL}</link>
  <guid>{PAGE_URL}</guid>
  <pubDate>Wed, 28 Oct 2026 18:00:00 GMT</pubDate>
</item>
</channel></rss>""".encode()

PAGE_V1 = """<html><body><div id="article">
<h3>Federal Reserve issues FOMC statement</h3>
<p>The Committee decided to maintain the target range for the federal funds rate.</p>
</div></body></html>"""

PAGE_V2 = PAGE_V1.replace("maintain", "raise")


class FakeFed:
    def __init__(self):
        self.page_html = PAGE_V1
        self.page_status = 200
        self.supports_etag = True
        self.page_requests = 0

    def handler(self, request):
        if str(request.url) == FEED_URL:
            if self.supports_etag and request.headers.get("If-None-Match") == '"v1"':
                return httpx.Response(304)
            return httpx.Response(200, content=RSS, headers={"ETag": '"v1"'})
        self.page_requests += 1
        if self.page_status != 200:
            return httpx.Response(self.page_status)
        return httpx.Response(200, text=self.page_html)


@pytest.fixture
def conn():
    c = connect(":memory:")
    init_db(c)
    yield c
    c.close()


@pytest.fixture
def fed():
    return FakeFed()


@pytest.fixture
def clock():
    start = datetime(2026, 10, 28, 18, 1, tzinfo=timezone.utc)
    ticks = {"n": 0}

    def now():
        ticks["n"] += 1
        return start + timedelta(minutes=ticks["n"])

    return now


def no_sleep(_seconds):
    pass


def run(conn, fed, clock, recheck=False):
    client = httpx.Client(transport=httpx.MockTransport(fed.handler))
    return collect_source(
        conn, client, "fed_monetary", FEED_URL, "central_bank",
        recheck_existing=recheck, now=clock, sleep=no_sleep,
    )


def count(conn, table):
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_first_run_stores_release_and_version(conn, fed, clock):
    stats = run(conn, fed, clock)

    assert (stats.new_releases, stats.new_versions) == (1, 1)
    assert count(conn, "releases") == 1
    assert count(conn, "release_versions") == 1
    etag = conn.execute("SELECT etag FROM sources").fetchone()[0]
    assert etag == '"v1"'


def test_second_run_gets_304_and_downloads_nothing(conn, fed, clock):
    run(conn, fed, clock)
    stats = run(conn, fed, clock)

    assert stats.feed_not_modified
    assert fed.page_requests == 1
    assert count(conn, "releases") == 1
    assert count(conn, "release_versions") == 1


def test_no_duplicates_even_without_server_caching(conn, fed, clock):
    fed.supports_etag = False
    run(conn, fed, clock)
    stats = run(conn, fed, clock)

    assert stats.new_releases == 0
    assert fed.page_requests == 1
    assert count(conn, "releases") == 1
    assert count(conn, "release_versions") == 1


def test_recheck_turns_an_edited_page_into_a_new_version(conn, fed, clock):
    run(conn, fed, clock)
    first_seen = conn.execute("SELECT first_seen_at FROM releases").fetchone()[0]

    fed.page_html = PAGE_V2
    stats = run(conn, fed, clock, recheck=True)

    assert stats.new_versions == 1
    assert count(conn, "release_versions") == 2
    assert count(conn, "releases") == 1
    assert conn.execute("SELECT first_seen_at FROM releases").fetchone()[0] == first_seen


def test_recheck_of_unchanged_page_adds_nothing(conn, fed, clock):
    run(conn, fed, clock)
    stats = run(conn, fed, clock, recheck=True)

    assert stats.new_versions == 0
    assert count(conn, "release_versions") == 1


def test_failed_page_is_retried_on_the_next_run(conn, fed, clock):
    fed.page_status = 503
    stats = run(conn, fed, clock)

    assert len(stats.page_errors) == 1
    assert count(conn, "releases") == 1
    assert count(conn, "release_versions") == 0

    fed.page_status = 200
    stats = run(conn, fed, clock)

    assert stats.feed_not_modified
    assert stats.new_versions == 1
    assert count(conn, "release_versions") == 1
import time
from dataclasses import dataclass, field

import httpx

from simbert.news.feeds import fetch_feed
from simbert.news.http import FetchError
from simbert.news.pages import fetch_page
from simbert.news.store import (
    get_source_cache,
    recent_releases_with_versions,
    record_release,
    record_version,
    releases_missing_versions,
    update_source_cache,
    upsert_source,
)
from simbert.news.timeutil import utc_now

PAUSE_BETWEEN_PAGES_SECONDS = 1.0


@dataclass
class CollectStats:
    feed_not_modified: bool = False
    entries_seen: int = 0
    new_releases: int = 0
    new_versions: int = 0
    pages_fetched: int = 0
    page_errors: list[str] = field(default_factory=list)


def _store_page(conn, client, release_id, url, stats, now, sleep) -> None:
    try:
        page = fetch_page(client, url, sleep=sleep)
    except FetchError as error:
        stats.page_errors.append(str(error))
        return
    stats.pages_fetched += 1
    if record_version(conn, release_id, page.content_hash, page.text, page.raw_html, now()):
        stats.new_versions += 1
    conn.commit()
    sleep(PAUSE_BETWEEN_PAGES_SECONDS)


def collect_source(
    conn,
    client: httpx.Client,
    name: str,
    feed_url: str,
    category: str,
    recheck_existing: bool = False,
    recheck_limit: int = 15,
    now=utc_now,
    sleep=time.sleep,
) -> CollectStats:
    stats = CollectStats()
    source_id = upsert_source(conn, name, feed_url, category)
    conn.commit()

    # Decide what to re-check before this run adds anything new.
    to_recheck = (
        recent_releases_with_versions(conn, source_id, recheck_limit)
        if recheck_existing else []
    )

    etag, last_modified = get_source_cache(conn, source_id)
    feed = fetch_feed(client, feed_url, etag, last_modified, sleep=sleep)

    if feed.not_modified:
        stats.feed_not_modified = True
    else:
        for entry in feed.entries:
            stats.entries_seen += 1
            _, created = record_release(
                conn, source_id, entry.guid, entry.url, entry.title,
                entry.published_at, now(),
            )
            if created:
                stats.new_releases += 1
            conn.commit()

    # Only remember the feed's cache headers once its releases are safely stored.
    update_source_cache(conn, source_id, feed.etag, feed.last_modified, now())
    conn.commit()

    for release_id, url in releases_missing_versions(conn, source_id):
        _store_page(conn, client, release_id, url, stats, now, sleep)

    for release_id, url in to_recheck:
        _store_page(conn, client, release_id, url, stats, now, sleep)

    return stats
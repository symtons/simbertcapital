import sqlite3
from datetime import datetime, timezone

import pytest

from simbert.news.store import (
    connect, init_db, record_release, record_version, upsert_source,
)

FEED = "https://www.federalreserve.gov/feeds/press_monetary.xml"
T1 = datetime(2026, 10, 28, 18, 0, tzinfo=timezone.utc)
T2 = datetime(2026, 10, 28, 18, 5, tzinfo=timezone.utc)


@pytest.fixture
def conn():
    c = connect(":memory:")
    init_db(c)
    yield c
    c.close()


def count(conn, table):
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def add_fomc_release(conn, received=T1):
    source_id = upsert_source(conn, "fed_monetary", FEED, "central_bank")
    return record_release(
        conn, source_id,
        guid="fomc-2026-10-28",
        url="https://www.federalreserve.gov/newsevents/pressreleases/monetary20261028a.htm",
        title="Federal Reserve issues FOMC statement",
        source_published_at=T1,
        first_seen_at=received,
    )


def test_init_db_can_run_twice(conn):
    init_db(conn)


def test_same_release_twice_is_stored_once(conn):
    first_id, created_first = add_fomc_release(conn, received=T1)
    second_id, created_second = add_fomc_release(conn, received=T2)

    assert first_id == second_id
    assert (created_first, created_second) == (True, False)
    assert count(conn, "releases") == 1
    first_seen = conn.execute("SELECT first_seen_at FROM releases").fetchone()[0]
    assert first_seen == T1.isoformat()


def test_same_content_twice_is_one_version(conn):
    release_id, _ = add_fomc_release(conn)
    assert record_version(conn, release_id, "hash-a", "text a", "<p>a</p>", T1)
    assert not record_version(conn, release_id, "hash-a", "text a", "<p>a</p>", T2)
    assert count(conn, "release_versions") == 1


def test_changed_content_becomes_a_new_version(conn):
    release_id, _ = add_fomc_release(conn)
    record_version(conn, release_id, "hash-a", "text a", "<p>a</p>", T1)
    record_version(conn, release_id, "hash-b", "text b", "<p>b</p>", T2)

    rows = conn.execute(
        "SELECT content_hash FROM release_versions ORDER BY received_at"
    ).fetchall()
    assert [r["content_hash"] for r in rows] == ["hash-a", "hash-b"]


def test_rejects_times_without_utc(conn):
    source_id = upsert_source(conn, "fed_monetary", FEED, "central_bank")
    with pytest.raises(ValueError):
        record_release(conn, source_id, "g", "u", "t", None, datetime(2026, 1, 1))


def test_version_needs_an_existing_release(conn):
    with pytest.raises(sqlite3.IntegrityError):
        record_version(conn, 999, "h", "t", "<p/>", T1)
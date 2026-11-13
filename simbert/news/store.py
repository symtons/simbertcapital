import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
    id              INTEGER PRIMARY KEY,
    name            TEXT NOT NULL UNIQUE,
    feed_url        TEXT NOT NULL,
    category        TEXT NOT NULL,
    etag            TEXT,
    last_modified   TEXT,
    last_polled_at  TEXT
);

CREATE TABLE IF NOT EXISTS releases (
    id                    INTEGER PRIMARY KEY,
    source_id             INTEGER NOT NULL REFERENCES sources(id),
    guid                  TEXT NOT NULL,
    url                   TEXT NOT NULL,
    title                 TEXT NOT NULL,
    source_published_at   TEXT,
    scheduled_release_at  TEXT,
    first_seen_at         TEXT NOT NULL,
    UNIQUE (source_id, guid)
);

CREATE TABLE IF NOT EXISTS release_versions (
    id            INTEGER PRIMARY KEY,
    release_id    INTEGER NOT NULL REFERENCES releases(id),
    content_hash  TEXT NOT NULL,
    content_text  TEXT NOT NULL,
    raw_html      TEXT NOT NULL,
    received_at   TEXT NOT NULL,
    UNIQUE (release_id, content_hash)
);
"""


def connect(path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def _iso(value: datetime | None) -> str | None:
    """Store only UTC datetimes, as ISO 8601 text."""
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"only UTC datetimes can be stored, got {value!r}")
    return value.isoformat()


def upsert_source(conn, name: str, feed_url: str, category: str) -> int:
    conn.execute(
        "INSERT INTO sources (name, feed_url, category) VALUES (?, ?, ?) "
        "ON CONFLICT(name) DO UPDATE SET "
        "feed_url = excluded.feed_url, category = excluded.category",
        (name, feed_url, category),
    )
    return conn.execute(
        "SELECT id FROM sources WHERE name = ?", (name,)
    ).fetchone()["id"]


def record_release(
    conn,
    source_id: int,
    guid: str,
    url: str,
    title: str,
    source_published_at: datetime | None,
    first_seen_at: datetime,
) -> tuple[int, bool]:
    """Insert a release if new. Returns (release_id, created)."""
    cursor = conn.execute(
        "INSERT INTO releases "
        "(source_id, guid, url, title, source_published_at, first_seen_at) "
        "VALUES (?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(source_id, guid) DO NOTHING",
        (source_id, guid, url, title,
         _iso(source_published_at), _iso(first_seen_at)),
    )
    created = cursor.rowcount == 1
    release_id = conn.execute(
        "SELECT id FROM releases WHERE source_id = ? AND guid = ?",
        (source_id, guid),
    ).fetchone()["id"]
    return release_id, created


def record_version(
    conn,
    release_id: int,
    content_hash: str,
    content_text: str,
    raw_html: str,
    received_at: datetime,
) -> bool:
    """Store a content version if this exact content is new. Returns created."""
    cursor = conn.execute(
        "INSERT INTO release_versions "
        "(release_id, content_hash, content_text, raw_html, received_at) "
        "VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(release_id, content_hash) DO NOTHING",
        (release_id, content_hash, content_text, raw_html, _iso(received_at)),
    )
    return cursor.rowcount == 1

def get_source_cache(conn, source_id: int) -> tuple[str | None, str | None]:
    row = conn.execute(
        "SELECT etag, last_modified FROM sources WHERE id = ?", (source_id,)
    ).fetchone()
    return row["etag"], row["last_modified"]


def update_source_cache(
    conn, source_id: int, etag: str | None, last_modified: str | None, polled_at: datetime
) -> None:
    conn.execute(
        "UPDATE sources SET etag = ?, last_modified = ?, last_polled_at = ? WHERE id = ?",
        (etag, last_modified, _iso(polled_at), source_id),
    )


def releases_missing_versions(conn, source_id: int) -> list[tuple[int, str]]:
    rows = conn.execute(
        "SELECT r.id, r.url FROM releases r "
        "WHERE r.source_id = ? AND NOT EXISTS "
        "(SELECT 1 FROM release_versions v WHERE v.release_id = r.id) "
        "ORDER BY r.id",
        (source_id,),
    ).fetchall()
    return [(row["id"], row["url"]) for row in rows]


def recent_releases_with_versions(conn, source_id: int, limit: int) -> list[tuple[int, str]]:
    rows = conn.execute(
        "SELECT r.id, r.url FROM releases r "
        "WHERE r.source_id = ? AND EXISTS "
        "(SELECT 1 FROM release_versions v WHERE v.release_id = r.id) "
        "ORDER BY r.first_seen_at DESC, r.id DESC LIMIT ?",
        (source_id, limit),
    ).fetchall()
    return [(row["id"], row["url"]) for row in rows]
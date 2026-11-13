"""Poll the Fed monetary-policy feed once and store new releases."""
import argparse
from pathlib import Path

import httpx

from simbert.news.collector import collect_source
from simbert.news.store import connect, init_db

FEED_URL = "https://www.federalreserve.gov/feeds/press_monetary.xml"
USER_AGENT = "simbertcapital-research/0.1 (contact: YOUR_EMAIL_HERE)"
DB_PATH = Path("data") / "simbert.db"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recheck", action="store_true",
                        help="re-download recent pages to detect revisions")
    args = parser.parse_args()

    DB_PATH.parent.mkdir(exist_ok=True)
    conn = connect(DB_PATH)
    init_db(conn)

    with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=20,
                      follow_redirects=True) as client:
        stats = collect_source(conn, client, "fed_monetary", FEED_URL,
                               "central_bank", recheck_existing=args.recheck)
    print(stats)

    row = conn.execute(
        "SELECT r.title, r.source_published_at, v.received_at, v.content_text "
        "FROM release_versions v JOIN releases r ON r.id = v.release_id "
        "ORDER BY r.source_published_at DESC LIMIT 1"
    ).fetchone()
    if row:
        print(f"\nNewest stored: {row['title']}")
        print(f"published: {row['source_published_at']} | received: {row['received_at']}")
        print(f"text preview:\n{row['content_text'][:600]}")
    conn.close()


if __name__ == "__main__":
    main()
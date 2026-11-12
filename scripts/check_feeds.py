"""Check that the official news feeds are reachable, allowed, and cache-friendly."""
import time
from functools import cache
from urllib.robotparser import RobotFileParser

import feedparser
import httpx

USER_AGENT = "simbertcapital-research/0.1 (contact: YOUR_EMAIL_HERE)"

FEEDS = {
    "fed_monetary": "https://www.federalreserve.gov/feeds/press_monetary.xml",
    "fed_all_press": "https://www.federalreserve.gov/feeds/press_all.xml",
    "fed_speeches": "https://www.federalreserve.gov/feeds/speeches.xml",
    "ecb_press": "https://www.ecb.europa.eu/rss/press.html",
    "ecb_stat_press": "https://www.ecb.europa.eu/rss/statpress.html",
    "bls_latest": "https://www.bls.gov/feed/bls_latest.rss",
    "bls_empsit": "https://www.bls.gov/feed/empsit.rss",
    "bls_cpi": "https://www.bls.gov/feed/cpi.rss",
}

client = httpx.Client(
    headers={"User-Agent": USER_AGENT},
    timeout=20,
    follow_redirects=True,
)


@cache
def robots_for(site_root: str) -> RobotFileParser | None:
    response = client.get(site_root + "/robots.txt")
    if response.status_code != 200:
        return None
    parser = RobotFileParser()
    parser.parse(response.text.splitlines())
    return parser


def check(name: str, url: str) -> None:
    site_root = "/".join(url.split("/")[:3])
    robots = robots_for(site_root)
    allowed = robots.can_fetch(USER_AGENT, url) if robots else "no robots.txt"

    response = client.get(url)
    etag = response.headers.get("etag")
    last_modified = response.headers.get("last-modified")

    conditional_status = None
    if etag or last_modified:
        headers = {}
        if etag:
            headers["If-None-Match"] = etag
        if last_modified:
            headers["If-Modified-Since"] = last_modified
        conditional_status = client.get(url, headers=headers).status_code

    feed = feedparser.parse(response.content)
    latest = feed.entries[0] if feed.entries else None

    print(f"\n[{name}] {url}")
    print(f"  status={response.status_code}  content-type={response.headers.get('content-type')}")
    print(f"  robots allows: {allowed}")
    print(f"  etag={'yes' if etag else 'no'}  last-modified={'yes' if last_modified else 'no'}  "
          f"conditional request -> {conditional_status}")
    print(f"  entries={len(feed.entries)}  parse problems={bool(feed.bozo)}")
    if latest:
        print(f"  newest: {latest.get('title')!r}")
        print(f"  published: {latest.get('published') or latest.get('updated')}")


def main() -> None:
    for name, url in FEEDS.items():
        try:
            check(name, url)
        except httpx.HTTPError as error:
            print(f"\n[{name}] ERROR {type(error).__name__}: {error}")
        time.sleep(2)


if __name__ == "__main__":
    main()
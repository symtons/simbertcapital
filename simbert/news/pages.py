import hashlib
import re
import time
from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup

from simbert.news.http import FetchError, get_with_retries

MAX_PAGE_BYTES = 2_000_000
CONTENT_SELECTORS = ["#article", "main", "article", "body"]
NOISE_TAGS = ["script", "style", "nav", "header", "footer", "noscript"]


@dataclass(frozen=True)
class PageContent:
    url: str
    raw_html: str
    text: str
    content_hash: str


def extract_text(html: str) -> str:
    """Return the readable main text of a page, one line per paragraph."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(NOISE_TAGS):
        tag.decompose()

    for selector in CONTENT_SELECTORS:
        node = soup.select_one(selector)
        if node and node.get_text(strip=True):
            break
    else:
        return ""

    lines = (line.strip() for line in node.get_text("\n").splitlines())
    return "\n".join(line for line in lines if line)


def content_hash(text: str) -> str:
    """Fingerprint the words, ignoring spacing and line-break differences."""
    normalized = re.sub(r"\s+", " ", text).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def fetch_page(
    client: httpx.Client,
    url: str,
    max_attempts: int = 4,
    base_delay: float = 2.0,
    sleep=time.sleep,
) -> PageContent:
    response = get_with_retries(client, url, None, max_attempts, base_delay, sleep)

    if len(response.content) > MAX_PAGE_BYTES:
        raise FetchError(
            f"{url} is {len(response.content)} bytes, over the {MAX_PAGE_BYTES} limit"
        )

    html = response.text
    text = extract_text(html)
    if not text:
        raise FetchError(f"{url} has no readable text")

    return PageContent(url, html, text, content_hash(text))
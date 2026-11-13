import httpx
import pytest

from simbert.news.http import FetchError
from simbert.news.pages import MAX_PAGE_BYTES, content_hash, extract_text, fetch_page

PAGE_URL = "https://example.test/monetary20261028a.htm"
PAGE = """<html><head><script>var tracking = 1;</script></head><body>
<nav>Home | About the Fed</nav>
<div id="article">
  <h3>Federal Reserve issues FOMC statement</h3>
  <p>Recent indicators suggest that economic activity has been expanding at a solid pace.</p>
  <p>The Committee decided to maintain the target range for the federal funds rate.</p>
</div>
<footer>Last update: October 28, 2026</footer>
</body></html>"""


def make_client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def no_sleep(_seconds):
    pass


def test_extracts_main_text_and_drops_noise():
    text = extract_text(PAGE)

    assert text.startswith("Federal Reserve issues FOMC statement")
    assert "maintain the target range" in text
    assert "Home | About" not in text
    assert "tracking" not in text
    assert "Last update" not in text


def test_hash_ignores_spacing_differences():
    assert content_hash("rates  were\n held") == content_hash("rates were held")


def test_hash_changes_when_wording_changes():
    assert content_hash("rates were held") != content_hash("rates were raised")


def test_fetch_page_returns_text_html_and_hash():
    def handler(request):
        return httpx.Response(200, text=PAGE)

    page = fetch_page(make_client(handler), PAGE_URL, sleep=no_sleep)

    assert page.url == PAGE_URL
    assert page.raw_html == PAGE
    assert page.content_hash == content_hash(page.text)
    assert "solid pace" in page.text


def test_rejects_oversized_pages():
    def handler(request):
        return httpx.Response(200, content=b"x" * (MAX_PAGE_BYTES + 1))

    with pytest.raises(FetchError):
        fetch_page(make_client(handler), PAGE_URL, sleep=no_sleep)


def test_rejects_pages_with_no_readable_text():
    def handler(request):
        return httpx.Response(200, text="<html><body><script>x()</script></body></html>")

    with pytest.raises(FetchError):
        fetch_page(make_client(handler), PAGE_URL, sleep=no_sleep)
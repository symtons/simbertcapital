import time

import httpx

RETRYABLE_STATUS = {429, 500, 502, 503, 504}
MAX_RETRY_AFTER_SECONDS = 300


class FetchError(Exception):
    """A URL could not be fetched or its content could not be used."""


def _retry_delay(response: httpx.Response | None, attempt: int, base_delay: float) -> float:
    retry_after = response.headers.get("retry-after") if response is not None else None
    if retry_after and retry_after.isdigit():
        return min(int(retry_after), MAX_RETRY_AFTER_SECONDS)
    return base_delay * (2 ** attempt)


def get_with_retries(
    client: httpx.Client,
    url: str,
    headers: dict | None = None,
    max_attempts: int = 4,
    base_delay: float = 2.0,
    sleep=time.sleep,
) -> httpx.Response:
    """GET a URL, retrying temporary failures. Returns a 200 or 304 response."""
    last_error = "no attempts made"
    for attempt in range(max_attempts):
        response = None
        try:
            response = client.get(url, headers=headers or {})
        except httpx.TransportError as error:
            last_error = f"{type(error).__name__}: {error}"
        else:
            if response.status_code in (200, 304):
                return response
            if response.status_code not in RETRYABLE_STATUS:
                raise FetchError(f"{url} returned HTTP {response.status_code}")
            last_error = f"HTTP {response.status_code}"

        if attempt < max_attempts - 1:
            sleep(_retry_delay(response, attempt, base_delay))

    raise FetchError(f"{url} failed after {max_attempts} attempts: {last_error}")
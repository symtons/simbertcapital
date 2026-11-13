from datetime import datetime, timezone
from email.utils import parsedate_to_datetime


def to_utc(value: str) -> datetime:
    """Parse a feed timestamp (RFC 822 or ISO 8601) and return it in UTC.

    Raises ValueError if the text can't be parsed or carries no timezone,
    because guessing a timezone would invent information.
    """
    text = value.strip()
    try:
        parsed = parsedate_to_datetime(text)
    except (TypeError, ValueError):
        parsed = datetime.fromisoformat(text)

    if parsed.tzinfo is None:
        raise ValueError(f"timestamp has no timezone: {value!r}")
    return parsed.astimezone(timezone.utc)


def utc_now() -> datetime:
    """The current time in UTC. Used for receipt timestamps."""
    return datetime.now(timezone.utc)
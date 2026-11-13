from datetime import datetime, timezone

import pytest

from simbert.news.timeutil import to_utc


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Wed, 28 Oct 2026 18:00:00 GMT",
         datetime(2026, 10, 28, 18, 0, tzinfo=timezone.utc)),
        ("Tue, 10 Nov 2026 17:45:00 +0100",
         datetime(2026, 11, 10, 16, 45, tzinfo=timezone.utc)),
        ("2026-11-06T07:50:31.965-05:00",
         datetime(2026, 11, 6, 12, 50, 31, 965000, tzinfo=timezone.utc)),
    ],
)
def test_real_feed_formats_normalize_to_utc(raw, expected):
    result = to_utc(raw)
    assert result == expected
    assert result.tzinfo == timezone.utc


@pytest.mark.parametrize(
    "raw",
    [
        "2026-11-06T07:50:31",               # ISO with no timezone
        "Wed, 28 Oct 2026 18:00:00 -0000",   # RFC 822 'unknown timezone'
        "not a date",
        "",
    ],
)
def test_rejects_ambiguous_or_garbage(raw):
    with pytest.raises(ValueError):
        to_utc(raw)
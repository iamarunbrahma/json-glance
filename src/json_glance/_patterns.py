"""Conservative string-pattern detectors.

Each detector is strict: it should almost never claim a pattern that is not
really there. A pattern is only reported by the renderer when *every* sampled
string at a position validates, and it is always shown as a hint (``~email``),
never as a guarantee.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime

# Pragmatic email shape: one "@", a dot in the domain, no whitespace. Good
# enough for a hint; not an RFC 5322 validator (nothing sane is).
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def is_email(value: str) -> bool:
    """True if ``value`` looks like an email address."""
    return len(value) <= 320 and _EMAIL.match(value) is not None


def is_uuid(value: str) -> bool:
    """True if ``value`` is a canonical 36-char hyphenated UUID.

    The length check is deliberate: it rejects 32-char hex strings (e.g. MD5
    digests), ``urn:uuid:`` forms, and braced forms that ``uuid.UUID`` would
    otherwise happily accept and that should not be hinted as a UUID.
    """
    if len(value) != 36:
        return False
    try:
        uuid.UUID(value)
    except ValueError:
        return False
    return True


def is_iso_datetime(value: str) -> bool:
    """True if ``value`` parses as an ISO-8601 date or datetime.

    Requires a hyphen-separated date (``YYYY-MM-DD``...), so compact 8-digit
    strings like ``"20230101"`` — far more often numeric IDs than dates — are
    not mistaken for timestamps.
    """
    if not 10 <= len(value) <= 40 or value[4] != "-":
        return False
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        datetime.fromisoformat(text)
    except ValueError:
        return False
    return True

"""Tests for the conservative string-pattern detectors."""

from json_glance._patterns import is_email, is_iso_datetime, is_uuid


def test_email_positive():
    assert is_email("ada@example.com")
    assert is_email("first.last@sub.example.org")


def test_email_negative():
    assert not is_email("not-an-email")
    assert not is_email("a@b")  # no dot in domain
    assert not is_email("a b@c.com")  # whitespace
    assert not is_email("two@@at.com")
    assert not is_email("")


def test_uuid_positive():
    assert is_uuid("550e8400-e29b-41d4-a716-446655440000")
    assert is_uuid("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


def test_uuid_negative():
    assert not is_uuid("not-a-uuid")
    assert not is_uuid("12345")
    assert not is_uuid("")


def test_uuid_rejects_non_canonical_forms():
    # a 32-char hex string (e.g. an MD5 digest) is not a canonical UUID
    assert not is_uuid("d41d8cd98f00b204e9800998ecf8427e")
    assert not is_uuid("urn:uuid:550e8400-e29b-41d4-a716-446655440000")
    assert not is_uuid("{550e8400-e29b-41d4-a716-446655440000}")


def test_iso_datetime_positive():
    assert is_iso_datetime("2024-01-01")
    assert is_iso_datetime("2024-01-01T12:30:00")
    assert is_iso_datetime("2025-06-15T12:30:00Z")


def test_iso_datetime_negative():
    assert not is_iso_datetime("abcdefghij")
    assert not is_iso_datetime("2024")  # too short
    assert not is_iso_datetime("")
    assert not is_iso_datetime("hello, this is plainly not a date at all")
    assert not is_iso_datetime("20230101")  # compact 8-digit form is not a date

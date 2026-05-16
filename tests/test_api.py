"""Tests for the public API contract: ``glance`` and ``summary``."""

import io

import pytest

from json_glance import __version__, glance, summary


def test_summary_returns_str():
    assert isinstance(summary({"a": 1}), str)


def test_summary_has_no_trailing_newline():
    assert not summary({"a": 1}).endswith("\n")


def test_glance_returns_none(capsys):
    assert glance({"a": 1}) is None
    capsys.readouterr()


def test_glance_prints_to_stdout(capsys):
    glance({"a": 1})
    out = capsys.readouterr().out
    assert "dict" in out and out.endswith("\n")


def test_glance_respects_file_argument():
    buffer = io.StringIO()
    glance({"a": 1}, file=buffer)
    assert "dict" in buffer.getvalue()


def test_glance_output_matches_summary():
    buffer = io.StringIO()
    data = {"a": [1, 2, 3]}
    glance(data, file=buffer)
    assert buffer.getvalue().rstrip("\n") == summary(data)


def test_negative_depth_rejected():
    with pytest.raises(ValueError):
        summary({"a": 1}, depth=-1)


def test_zero_max_keys_rejected():
    with pytest.raises(ValueError):
        summary({"a": 1}, max_keys=0)


def test_version_is_a_string():
    assert isinstance(__version__, str) and __version__ == "0.1.1"

"""Tests for the ``json-glance`` command-line interface."""

import io
import json

import pytest

from json_glance._cli import main


def test_json_file(tmp_path, capsys):
    path = tmp_path / "data.json"
    path.write_text(json.dumps({"a": [1, 2, 3]}))
    assert main([str(path)]) == 0
    assert "dict" in capsys.readouterr().out


def test_jsonl_file(tmp_path, capsys):
    path = tmp_path / "data.jsonl"
    path.write_text('{"id": 1}\n{"id": 2}\n{"id": 3}\n')
    assert main([str(path)]) == 0
    assert "list  · 3 items" in capsys.readouterr().out


def test_stdin(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO('{"a": 1}'))
    assert main([]) == 0
    assert "dict" in capsys.readouterr().out


def test_stdin_jsonl_auto_sniff(monkeypatch, capsys):
    # piped JSONL has no extension hint — the whole-doc parse fails and the
    # parser must fall back to line-by-line JSONL.
    monkeypatch.setattr("sys.stdin", io.StringIO('{"id": 1}\n{"id": 2}\n'))
    assert main([]) == 0
    assert "2 items" in capsys.readouterr().out


def test_missing_file(capsys):
    assert main(["/no/such/path/xyz.json"]) == 2
    assert "cannot read" in capsys.readouterr().err


def test_malformed_json(tmp_path, capsys):
    path = tmp_path / "bad.json"
    path.write_text("{not valid")
    assert main([str(path)]) == 1
    assert "invalid JSON" in capsys.readouterr().err


def test_malformed_jsonl_reports_line_number(tmp_path, capsys):
    path = tmp_path / "bad.jsonl"
    path.write_text('{"a": 1}\n{bad}\n')
    assert main([str(path)]) == 1
    assert "line 2" in capsys.readouterr().err


def test_non_utf8_file_reports_cleanly(tmp_path, capsys):
    # A binary / non-UTF-8 file must produce a clean error, not a traceback.
    path = tmp_path / "binary.json"
    path.write_bytes(b'\xff\xfe\x00{"a": 1}')
    assert main([str(path)]) == 2
    assert "UTF-8" in capsys.readouterr().err


def test_deeply_nested_json_reports_cleanly(tmp_path, capsys):
    # Pathologically deep JSON makes json.loads raise RecursionError; it must
    # be reported as invalid input, not crash with a traceback.
    path = tmp_path / "deep.json"
    path.write_text("[" * 20000 + "]" * 20000)
    assert main([str(path)]) == 1
    assert "invalid JSON" in capsys.readouterr().err


def test_empty_input(tmp_path, capsys):
    path = tmp_path / "empty.json"
    path.write_text("")
    assert main([str(path)]) == 2
    assert "no input" in capsys.readouterr().err


def test_format_override_forces_jsonl(tmp_path, capsys):
    path = tmp_path / "data.txt"  # extension would not auto-detect as jsonl
    path.write_text('{"id": 1}\n{"id": 2}\n')
    assert main([str(path), "--format", "jsonl"]) == 0
    assert "2 items" in capsys.readouterr().out


def test_depth_flag(tmp_path, capsys):
    path = tmp_path / "deep.json"
    path.write_text(json.dumps({"a": {"b": {"c": {"d": 1}}}}))
    assert main([str(path), "--depth", "1"]) == 0
    assert "…" in capsys.readouterr().out


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert "json-glance" in capsys.readouterr().out

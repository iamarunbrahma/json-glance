"""Command-line entry point: ``json-glance <file>`` or piped stdin."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, List, Optional

from . import __version__, glance

_JSONL_EXT = (".jsonl", ".ndjson")


def _load_jsonl(text: str) -> List[Any]:
    """Parse newline-delimited JSON, reporting the first bad line."""
    records: List[Any] = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"line {lineno}: {exc.msg}") from exc
    if not records:
        raise ValueError("no JSON records found")
    return records


def _parse(text: str, fmt: str, path: Optional[str]) -> Any:
    """Parse input text as JSON or JSONL, honoring ``--format`` then sniffing."""
    is_jsonl = fmt == "jsonl" or (
        fmt == "auto" and path is not None and path.lower().endswith(_JSONL_EXT)
    )
    if is_jsonl:
        return _load_jsonl(text)
    if fmt == "json" or (
        fmt == "auto" and path is not None and path.lower().endswith(".json")
    ):
        return json.loads(text)
    # auto, no extension hint: try whole-document JSON, fall back to JSONL.
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return _load_jsonl(text)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="json-glance",
        description="df.describe() for JSON and nested data — a shape summary.",
    )
    parser.add_argument(
        "file", nargs="?", help="JSON or JSONL file; omit (or '-') to read stdin"
    )
    parser.add_argument(
        "--format",
        choices=["auto", "json", "jsonl"],
        default="auto",
        help="input format (default: auto-detect by extension, then sniff)",
    )
    parser.add_argument(
        "--depth", type=int, default=6, help="nesting levels to show (default: 6)"
    )
    parser.add_argument(
        "--max-keys",
        type=int,
        default=50,
        dest="max_keys",
        help="record keys to show before '+N more' (default: 50)",
    )
    parser.add_argument(
        "--version", action="version", version=f"json-glance {__version__}"
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entry point. Returns a process exit code."""
    args = _build_parser().parse_args(argv)

    # Read input.
    try:
        if args.file in (None, "-"):
            text = sys.stdin.read()
            path = None
        else:
            with open(args.file, encoding="utf-8") as handle:
                text = handle.read()
            path = args.file
    except OSError as exc:
        print(
            f"json-glance: cannot read {args.file}: {exc.strerror or exc}",
            file=sys.stderr,
        )
        return 2
    except UnicodeDecodeError:
        print("json-glance: input is not valid UTF-8 text", file=sys.stderr)
        return 2

    if not text.strip():
        print("json-glance: no input", file=sys.stderr)
        return 2

    # Parse.
    try:
        data = _parse(text, args.format, path)
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"json-glance: invalid JSON: {exc}", file=sys.stderr)
        return 1
    except RecursionError:
        print("json-glance: invalid JSON: input is too deeply nested", file=sys.stderr)
        return 1

    # Summarize.
    try:
        glance(data, depth=args.depth, max_keys=args.max_keys)
    except ValueError as exc:
        print(f"json-glance: {exc}", file=sys.stderr)
        return 2
    except BrokenPipeError:
        # Downstream consumer (e.g. `| head`) closed the pipe. Redirect stdout
        # to devnull so the interpreter's shutdown flush has a valid sink and
        # does not re-raise BrokenPipeError after main() returns.
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
        return 0
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

"""JSON Glance — ``df.describe()`` for JSON and nested Python data.

    >>> from json_glance import glance, summary
    >>> glance(some_api_response)        # print a shape summary
    >>> text = summary(some_api_response) # ...or get it as a string

Two functions, zero dependencies. See ``README.md`` for the full story.
"""

from __future__ import annotations

import sys
from typing import Any, Optional, TextIO

from ._core import build
from ._render import render

__version__ = "0.1.0"
__all__ = ["glance", "summary", "__version__"]


def summary(data: Any, *, depth: int = 6, max_keys: int = 50) -> str:
    """Return a human-readable shape summary of ``data`` as a string.

    Args:
        data: any value — JSON-like data gets the full treatment; anything else
            is reported by type name and never crashes the summary.
        depth: how many levels of nesting to descend before collapsing to ``…``.
        max_keys: how many keys of a record dict to show before ``+N more``.

    Returns:
        The summary as a string, with no trailing newline.
    """
    if depth < 0:
        raise ValueError("depth must be >= 0")
    if max_keys < 1:
        raise ValueError("max_keys must be >= 1")
    return render(build(data, depth), max_keys)


def glance(
    data: Any,
    *,
    depth: int = 6,
    max_keys: int = 50,
    file: Optional[TextIO] = None,
) -> None:
    """Print a human-readable shape summary of ``data``.

    Same arguments as :func:`summary`, plus ``file`` (defaults to stdout).
    """
    text = summary(data, depth=depth, max_keys=max_keys)
    print(text, file=file if file is not None else sys.stdout)

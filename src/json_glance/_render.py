"""Render a ``Node`` tree into a deterministic, human-readable text tree.

Output is plain Unicode (box-drawing characters only) so it works in any
terminal, in logs, and in test snapshots. Same input always yields the same
output.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional, Tuple

from ._core import Coll, Leaf, Map, Node, Record

_TEE = "├─ "
_ELBOW = "└─ "
_PIPE = "│  "
_GAP = "   "

# In a union, name at most this many kinds inline; the rest collapse to "+N more".
MAX_VARIANTS = 6


@dataclass
class _Part:
    """The renderable summary of one node: a type token, trailing stats, and an
    optional structural child to recurse into."""

    token: str
    stats: str
    structural: Optional[Tuple[str, Any]]  # ("record"|"coll"|"map", payload)


# --------------------------------------------------------------------------
# value formatting
# --------------------------------------------------------------------------


def _fmt_float(value: float) -> str:
    return f"{value:g}"


def _pct(count: int, total: int) -> str:
    if total <= 0:
        return "0"
    ratio = count / total * 100
    if 0 < ratio < 1:
        return "<1"
    return str(round(ratio))


def _range_str(lo: Any, hi: Any, is_int: bool) -> str:
    if lo is None:
        return ""
    fmt = (lambda x: str(int(x))) if is_int else _fmt_float
    if lo == hi:
        return f"= {fmt(lo)}"
    return f"{fmt(lo)} – {fmt(hi)}"


def _len_str(lo: Optional[int], hi: Optional[int]) -> str:
    if lo is None:
        return ""
    return f"len {lo}" if lo == hi else f"len {lo} – {hi}"


def _count_str(lo: Optional[int], hi: Optional[int]) -> str:
    if lo is None:
        return "0"
    return str(lo) if lo == hi else f"{lo} – {hi}"


def _short(value: Any) -> str:
    text = str(value)
    return text if len(text) <= 20 else text[:19] + "…"


# --------------------------------------------------------------------------
# node -> _Part
# --------------------------------------------------------------------------


def _leaf_part(kind: str, leaf: Leaf) -> _Part:
    if kind in ("int", "float"):
        return _Part(kind, _range_str(leaf.num_min, leaf.num_max, kind == "int"), None)
    if kind == "bool":
        pct = round(leaf.true_count / leaf.count * 100) if leaf.count else 0
        return _Part("bool", f"{pct}% true", None)
    if kind == "str":
        stats = _len_str(leaf.len_min, leaf.len_max)
        hint = ""
        if leaf.count:
            if leaf.pat_uuid:
                hint = "~uuid"
            elif leaf.pat_email:
                hint = "~email"
            elif leaf.pat_datetime:
                hint = "~datetime"
        if hint:
            stats = f"{stats}  {hint}" if stats else hint
        return _Part("str", stats, None)
    if kind == "bytes":
        return _Part("bytes", _len_str(leaf.len_min, leaf.len_max), None)
    if kind.startswith("other:"):
        return _Part(kind[len("other:") :], "", None)
    return _Part(kind, "", None)


def _key_type(key_node: Node) -> str:
    if not key_node.leaves:
        return "?"
    kind = max(key_node.leaves.items(), key=lambda kv: kv[1].count)[0]
    return kind[len("other:") :] if kind.startswith("other:") else kind


def _coll_part(kind: str, coll: Coll) -> _Part:
    unit = "item" if coll.len_min == coll.len_max == 1 else "items"
    stats = f"· {_count_str(coll.len_min, coll.len_max)} {unit}"
    if coll.sampled:
        stats += "  (sampled)"
    return _Part(kind, stats, ("coll", coll))


def _record_part(record: Record) -> _Part:
    count = len(record.fields)
    unit = "key" if count == 1 else "keys"
    return _Part("dict", f"· {count} {unit}", ("record", record))


def _map_part(mapping: Map) -> _Part:
    unit = "entry" if mapping.pairs == 1 else "entries"
    stats = f"· {mapping.pairs} {unit} · {_key_type(mapping.key_node)} keys"
    if mapping.sample_keys:
        sample = ", ".join(_short(k) for k in mapping.sample_keys[:3])
        stats += f"  (e.g. {sample})"
    if mapping.sampled:
        stats += "  (sampled)"
    return _Part("dict", stats, ("map", mapping))


def _variants(node: Node) -> List[Tuple[str, int, str, Any]]:
    """All observed kinds at this position: (display_name, count, tag, payload)."""
    out: List[Tuple[str, int, str, Any]] = []
    for kind, leaf in node.leaves.items():
        name = kind[len("other:") :] if kind.startswith("other:") else kind
        out.append((name, leaf.count, "leaf:" + kind, leaf))
    for kind, coll in node.colls.items():
        out.append((kind, coll.count, "coll", coll))
    if node.record is not None:
        out.append(("dict", node.record.count, "record", node.record))
    if node.mapping is not None:
        out.append(("dict", node.mapping.count, "map", node.mapping))
    if node.null:
        out.append(("null", node.null, "null", None))
    if node.cyclic:
        out.append(("<cycle>", node.cyclic, "cyclic", None))
    if node.truncated:
        out.append(("…", node.truncated, "truncated", None))
    out.sort(key=lambda v: (-v[1], v[0]))
    return out


def _single_part(variant: Tuple[str, int, str, Any]) -> _Part:
    name, _count, tag, payload = variant
    if tag.startswith("leaf:"):
        return _leaf_part(tag[len("leaf:") :], payload)
    if tag == "coll":
        return _coll_part(name, payload)
    if tag == "record":
        return _record_part(payload)
    if tag == "map":
        return _map_part(payload)
    # null / cyclic / truncated
    return _Part(name, "", None)


def _summarize(node: Node) -> _Part:
    """Collapse a node into one renderable ``_Part``."""
    variants = _variants(node)
    if not variants:
        return _Part("—", "(empty)", None)
    if len(variants) == 1:
        return _single_part(variants[0])

    # Union: name each kind (capped), call out the minority shares, and recurse
    # into a structural variant only when exactly one exists.
    total = node.total or sum(v[1] for v in variants)
    shown = variants[:MAX_VARIANTS]
    hidden = len(variants) - len(shown)
    names = " | ".join(v[0] for v in shown)
    if hidden:
        names += f" | +{hidden} more"
    notes = ", ".join(f"{_pct(v[1], total)}% {v[0]}" for v in shown[1:])
    stats = f"({notes})" if notes else ""
    # Recurse into the dominant structural variant. `variants` is count-sorted,
    # so structs[0] is the most common structure; showing it beats showing none
    # when a position mixes (say) a list and a dict.
    structural = None
    structs = [v for v in variants if v[2] in ("coll", "record", "map")]
    if structs:
        structural = (structs[0][2], structs[0][3])
    return _Part(names, stats, structural)


# --------------------------------------------------------------------------
# tree assembly
# --------------------------------------------------------------------------


def _join(part: _Part) -> str:
    return f"{part.token}  {part.stats}" if part.stats else part.token


def _render_children(part: _Part, prefix: str, lines: List[str], max_keys: int) -> None:
    if part.structural is None:
        return
    tag, payload = part.structural

    if tag == "record":
        record: Record = payload
        items = list(record.fields.items())
        shown = items[:max_keys]
        hidden = len(items) - len(shown)
        if not shown:
            return
        child_parts = []
        for key, fld in shown:
            cp = _summarize(fld.node)
            if fld.present < record.count:
                miss = _pct(record.count - fld.present, record.count)
                note = f"({miss}% missing)"
                cp = _Part(cp.token, f"{cp.stats}  {note}".strip(), cp.structural)
            child_parts.append((str(key), fld.node, cp))
        key_w = max(len(k) for k, _, _ in child_parts)
        tok_w = max(len(cp.token) for _, _, cp in child_parts)
        for i, (key, _node, cp) in enumerate(child_parts):
            last = i == len(child_parts) - 1 and hidden == 0
            connector = _ELBOW if last else _TEE
            cont = _GAP if last else _PIPE
            row = prefix + connector + key.ljust(key_w) + "  " + cp.token.ljust(tok_w)
            if cp.stats:
                row += "  " + cp.stats
            lines.append(row.rstrip())
            _render_children(cp, prefix + cont, lines, max_keys)
        if hidden:
            lines.append(prefix + _ELBOW + f"… +{hidden} more keys")
        return

    if tag == "coll":
        coll: Coll = payload
        if coll.child.total == 0:
            return  # empty collection: the "· 0 items" line already says it
        cp = _summarize(coll.child)
        lines.append((prefix + _ELBOW + _join(cp)).rstrip())
        _render_children(cp, prefix + _GAP, lines, max_keys)
        return

    if tag == "map":
        mapping: Map = payload
        if mapping.val_node.total == 0:
            return
        cp = _summarize(mapping.val_node)
        lines.append((prefix + _ELBOW + "→ " + _join(cp)).rstrip())
        _render_children(cp, prefix + _GAP, lines, max_keys)


def render(node: Node, max_keys: int) -> str:
    """Render a ``Node`` tree to a string (no trailing newline)."""
    part = _summarize(node)
    lines = [_join(part)]
    _render_children(part, "", lines, max_keys)
    return "\n".join(lines)

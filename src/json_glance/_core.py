"""The summary engine: walk nested data into a ``Node`` tree, merging as it goes.

The whole library is one idea: a position observed many times (every element of
a list, every value of a map) is folded into a single ``Node`` that carries the
*union* of what was seen plus aggregate stats. ``describe`` builds a one-value
``Node``; ``merge`` folds two together. Everything else composes those two.

Denominator contract (this is what makes the summary trustworthy):

* ``Node.total``  -- how many values were observed at this position.
* ``Node.null``   -- how many of them were ``None``.
* ``Record.count``/``Field.present`` -- a key missing from some dicts is visible
  as ``record.count - field.present``; a key present but ``None`` is visible as
  ``field.node.null``. Missing and null are tracked separately and never
  conflated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Optional

from ._patterns import is_email, is_iso_datetime, is_uuid

# A dict with more keys than this is treated as a *map* (homogeneous key->value
# store) rather than a *record* (fixed set of named fields).
MAP_THRESHOLD = 25

# At most this many elements of any single collection are traversed. Keeps a
# pathological million-item list fast; the summary of a homogeneous list does
# not get more accurate past a large sample.
MAX_SAMPLE = 10_000


# --------------------------------------------------------------------------
# Node tree
# --------------------------------------------------------------------------


@dataclass
class Leaf:
    """Aggregate stats for one scalar kind (int, float, str, ...)."""

    count: int = 0
    num_min: Optional[float] = None
    num_max: Optional[float] = None
    len_min: Optional[int] = None
    len_max: Optional[int] = None
    true_count: int = 0  # bool only
    # String-pattern flags start True and are AND-ed across every string seen,
    # so a flag is still True only if *every* string matched the pattern.
    pat_email: bool = True
    pat_uuid: bool = True
    pat_datetime: bool = True


@dataclass
class Coll:
    """Aggregate stats for one collection kind (list, tuple, set)."""

    count: int = 0
    len_min: Optional[int] = None
    len_max: Optional[int] = None
    sampled: bool = False
    child: "Node" = field(default_factory=lambda: Node())


@dataclass
class Field:
    """One key of a record dict."""

    present: int = 0
    node: "Node" = field(default_factory=lambda: Node())


@dataclass
class Record:
    """A dict treated as a fixed set of named fields."""

    count: int = 0
    fields: Dict[Any, Field] = field(default_factory=dict)


@dataclass
class Map:
    """A dict treated as a homogeneous key->value store."""

    count: int = 0
    pairs: int = 0
    sampled: bool = False
    key_node: "Node" = field(default_factory=lambda: Node())
    val_node: "Node" = field(default_factory=lambda: Node())
    sample_keys: List[Any] = field(default_factory=list)


@dataclass
class Node:
    """The merged summary of every value observed at one position."""

    total: int = 0
    null: int = 0
    cyclic: int = 0
    truncated: int = 0
    leaves: Dict[str, Leaf] = field(default_factory=dict)
    colls: Dict[str, Coll] = field(default_factory=dict)
    record: Optional[Record] = None
    mapping: Optional[Map] = None


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------


def _opt_min(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None:
        return b
    if b is None:
        return a
    return a if a <= b else b


def _opt_max(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None:
        return b
    if b is None:
        return a
    return a if a >= b else b


# --------------------------------------------------------------------------
# describe: one value -> Node
# --------------------------------------------------------------------------


def _scalar_node(value: Any) -> Node:
    """Build a one-value ``Node`` for a non-container value."""
    node = Node(total=1)
    if value is None:
        node.null = 1
        return node
    vtype = type(value)
    if vtype is bool:  # bool before int: bool is an int subclass
        node.leaves["bool"] = Leaf(count=1, true_count=1 if value else 0)
    elif vtype is int:
        node.leaves["int"] = Leaf(count=1, num_min=value, num_max=value)
    elif vtype is float:
        node.leaves["float"] = Leaf(count=1, num_min=value, num_max=value)
    elif vtype is str:
        node.leaves["str"] = Leaf(
            count=1,
            len_min=len(value),
            len_max=len(value),
            pat_email=is_email(value),
            pat_uuid=is_uuid(value),
            pat_datetime=is_iso_datetime(value),
        )
    elif vtype in (bytes, bytearray):
        node.leaves["bytes"] = Leaf(count=1, len_min=len(value), len_max=len(value))
    else:
        # Anything else (datetime, Decimal, numpy/pandas objects, custom
        # classes): record the type name, never recurse, never call user code.
        node.leaves["other:" + vtype.__name__] = Leaf(count=1)
    return node


def describe(value: Any, depth_left: int, path: FrozenSet[int]) -> Node:
    """Build a one-value ``Node`` for any value.

    ``path`` holds ``id()`` of every container currently being entered, so a
    genuine cycle is detected without flagging a merely shared reference.
    """
    if isinstance(value, dict):
        return _describe_dict(value, depth_left, path)
    if isinstance(value, (list, tuple, set, frozenset)):
        return _describe_collection(value, depth_left, path)
    return _scalar_node(value)


def _describe_dict(value: dict, depth_left: int, path: FrozenSet[int]) -> Node:
    if depth_left <= 0:
        return Node(total=1, truncated=1)
    oid = id(value)
    if oid in path:
        return Node(total=1, cyclic=1)
    inner = path | {oid}
    node = Node(total=1)
    if len(value) > MAP_THRESHOLD:
        node.mapping = _describe_map(value, depth_left, inner)
    else:
        node.record = _describe_record(value, depth_left, inner)
    return node


def _describe_record(value: dict, depth_left: int, path: FrozenSet[int]) -> Record:
    record = Record(count=1)
    for key, child in value.items():
        record.fields[key] = Field(
            present=1, node=describe(child, depth_left - 1, path)
        )
    return record


def _describe_map(value: dict, depth_left: int, path: FrozenSet[int]) -> Map:
    # `pairs` keeps the true key count (the honest denominator); only the
    # traversal is capped at MAX_SAMPLE, matching _describe_collection.
    mapping = Map(count=1, pairs=len(value), sampled=len(value) > MAX_SAMPLE)
    for index, (key, child) in enumerate(value.items()):
        if index >= MAX_SAMPLE:
            break
        mapping.key_node = merge(mapping.key_node, _scalar_node(key))
        mapping.val_node = merge(
            mapping.val_node, describe(child, depth_left - 1, path)
        )
        if len(mapping.sample_keys) < 3:
            mapping.sample_keys.append(key)
    return mapping


def _describe_collection(value: Any, depth_left: int, path: FrozenSet[int]) -> Node:
    if depth_left <= 0:
        return Node(total=1, truncated=1)
    oid = id(value)
    if oid in path:
        return Node(total=1, cyclic=1)
    inner = path | {oid}
    if isinstance(value, list):
        kind = "list"
    elif isinstance(value, tuple):
        kind = "tuple"
    else:
        kind = "set"
    items = list(value)
    length = len(items)
    child = Node()
    for element in items[:MAX_SAMPLE]:
        child = merge(child, describe(element, depth_left - 1, inner))
    node = Node(total=1)
    node.colls[kind] = Coll(
        count=1,
        len_min=length,
        len_max=length,
        sampled=length > MAX_SAMPLE,
        child=child,
    )
    return node


# --------------------------------------------------------------------------
# merge: fold two Nodes together
# --------------------------------------------------------------------------


def merge(a: Node, b: Node) -> Node:
    """Fold ``b`` into ``a`` and return ``a``. ``b`` is always a fresh Node."""
    a.total += b.total
    a.null += b.null
    a.cyclic += b.cyclic
    a.truncated += b.truncated
    for kind, leaf in b.leaves.items():
        existing = a.leaves.get(kind)
        a.leaves[kind] = leaf if existing is None else _merge_leaf(existing, leaf)
    for kind, coll in b.colls.items():
        existing = a.colls.get(kind)
        a.colls[kind] = coll if existing is None else _merge_coll(existing, coll)
    if b.record is not None or b.mapping is not None:
        _merge_dict_aspect(a, b)
    return a


def _merge_leaf(a: Leaf, b: Leaf) -> Leaf:
    a.count += b.count
    a.num_min = _opt_min(a.num_min, b.num_min)
    a.num_max = _opt_max(a.num_max, b.num_max)
    a.len_min = _opt_min(a.len_min, b.len_min)
    a.len_max = _opt_max(a.len_max, b.len_max)
    a.true_count += b.true_count
    a.pat_email = a.pat_email and b.pat_email
    a.pat_uuid = a.pat_uuid and b.pat_uuid
    a.pat_datetime = a.pat_datetime and b.pat_datetime
    return a


def _merge_coll(a: Coll, b: Coll) -> Coll:
    a.count += b.count
    a.len_min = _opt_min(a.len_min, b.len_min)
    a.len_max = _opt_max(a.len_max, b.len_max)
    a.sampled = a.sampled or b.sampled
    a.child = merge(a.child, b.child)
    return a


def _merge_records(a: Record, b: Record) -> Record:
    a.count += b.count
    for key, fld in b.fields.items():
        existing = a.fields.get(key)
        if existing is None:
            a.fields[key] = fld
        else:
            existing.present += fld.present
            existing.node = merge(existing.node, fld.node)
    return a


def _merge_maps(a: Map, b: Map) -> Map:
    a.count += b.count
    a.pairs += b.pairs
    a.sampled = a.sampled or b.sampled
    a.key_node = merge(a.key_node, b.key_node)
    a.val_node = merge(a.val_node, b.val_node)
    for key in b.sample_keys:
        if len(a.sample_keys) < 3:
            a.sample_keys.append(key)
    return a


def _record_to_map(record: Record) -> Map:
    """Reinterpret a record as a map (used when a position is sometimes a small
    record and sometimes a large map -- rare, but it must not crash)."""
    mapping = Map(count=record.count)
    for key, fld in record.fields.items():
        mapping.key_node = merge(mapping.key_node, _scalar_node(key))
        mapping.val_node = merge(mapping.val_node, fld.node)
        mapping.pairs += fld.present
        if len(mapping.sample_keys) < 3:
            mapping.sample_keys.append(key)
    return mapping


def _merge_dict_aspect(a: Node, b: Node) -> None:
    a_has = a.record is not None or a.mapping is not None
    if not a_has:
        a.record = b.record
        a.mapping = b.mapping
        return
    if a.mapping is not None or b.mapping is not None:
        # Once either side is a map, the merged result is a map.
        left = a.mapping if a.mapping is not None else _record_to_map(a.record)
        right = b.mapping if b.mapping is not None else _record_to_map(b.record)
        a.mapping = _merge_maps(left, right)
        a.record = None
    else:
        a.record = _merge_records(a.record, b.record)


def build(data: Any, depth: int) -> Node:
    """Top-level entry: summarize ``data`` into a ``Node`` tree."""
    return describe(data, depth, frozenset())

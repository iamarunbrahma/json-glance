"""Tests for the walk/merge engine internals."""

from json_glance._core import Node, build, describe, merge


def test_build_returns_node():
    assert isinstance(build({"a": 1}, 6), Node)


def test_describe_single_value():
    node = describe(42, 6, frozenset())
    assert node.total == 1
    assert node.leaves["int"].count == 1
    assert node.leaves["int"].num_min == 42
    assert node.leaves["int"].num_max == 42


def test_list_elements_merge_into_one_child():
    node = build([1, 1, 1, 1, 1], 6)
    child = node.colls["list"].child
    assert child.total == 5
    assert child.leaves["int"].count == 5


def test_merge_accumulates_totals():
    a = describe("x", 6, frozenset())
    b = describe("yz", 6, frozenset())
    merged = merge(a, b)
    assert merged.total == 2
    assert merged.leaves["str"].count == 2
    assert merged.leaves["str"].len_min == 1
    assert merged.leaves["str"].len_max == 2


def test_record_tracks_presence():
    node = build([{"a": 1}, {"a": 1, "b": 2}], 6)
    record = node.colls["list"].child.record
    assert record.count == 2
    assert record.fields["a"].present == 2
    assert record.fields["b"].present == 1


def test_total_equals_variant_counts():
    # int + str + None + dict observed at one position — every variant kind,
    # including the record, must sum back to total.
    node = build([1, "x", None, {"a": 1}], 6)
    child = node.colls["list"].child
    variant_sum = (
        sum(leaf.count for leaf in child.leaves.values())
        + child.null
        + child.cyclic
        + child.truncated
        + (child.record.count if child.record else 0)
        + (child.mapping.count if child.mapping else 0)
    )
    assert child.total == variant_sum == 4

"""Behavioral tests driven through the public ``summary`` output."""

import datetime

from json_glance import summary as s


# --- scalar types --------------------------------------------------------


def test_int_scalar():
    assert s(5) == "int  = 5"


def test_float_scalar():
    assert "float" in s(3.14)


def test_str_scalar():
    out = s("hello")
    assert "str" in out and "len 5" in out


def test_bool_is_not_int():
    out = s(True)
    assert "bool" in out and "int" not in out


def test_none_scalar():
    assert s(None) == "null"


def test_bytes_scalar():
    out = s(b"abc")
    assert "bytes" in out and "len 3" in out


# --- merge / unions ------------------------------------------------------


def test_int_float_union():
    out = s([1, 2.5, 3])
    assert "int" in out and "float" in out and "|" in out


def test_list_of_dicts_merges_once():
    out = s([{"id": i} for i in range(100)])
    assert "list  · 100 items" in out
    assert out.count("id") == 1  # merged, not repeated 100x


def test_int_range():
    assert "1 – 999" in s([{"n": 1}, {"n": 50}, {"n": 999}])


def test_constant_value_shown_as_equals():
    assert "= 7" in s([{"n": 7}, {"n": 7}])


def test_variant_cap_collapses_extras():
    elems = [1, 1.5, "a", True, b"x", [1], {"k": 1}, None]
    assert "+2 more" in s(elems)


# --- denominators --------------------------------------------------------


def test_missing_key_percent():
    out = s([{"a": 1}, {"a": 1}, {"a": 1, "b": 2}])
    assert "67% missing" in out


def test_null_value_percent():
    out = s([{"x": 1}, {"x": None}, {"x": 3}, {"x": None}])
    assert "50% null" in out


def test_bool_true_ratio():
    assert "75% true" in s([True, True, True, False])


# --- map vs record -------------------------------------------------------


def test_large_dict_treated_as_map():
    out = s({f"key_{i}": i for i in range(40)})
    assert "40 entries" in out and "str keys" in out


def test_small_dict_treated_as_record():
    out = s({f"f{i}": i for i in range(5)})
    assert "5 keys" in out and "entries" not in out


def test_record_then_map_at_same_position_merges_cleanly():
    # one element is a small record, the next a large map: the record-to-map
    # conversion path must merge without crashing or corrupting the tree.
    out = s([{"x": 1}, {f"k{i}": i for i in range(40)}])
    assert "entries" in out  # collapsed to a map
    assert "<cycle>" not in out


def test_records_with_disjoint_keys_merge():
    out = s([{"a": 1}, {"b": 2}])
    assert "a" in out and "b" in out
    assert "50% missing" in out


# --- cycles --------------------------------------------------------------


def test_true_cycle_detected():
    d = {"name": "x"}
    d["loop"] = d
    assert "<cycle>" in s(d)


def test_shared_reference_is_not_a_cycle():
    shared = {"v": 1}
    assert "<cycle>" not in s({"a": shared, "b": shared})


# --- depth / max_keys ----------------------------------------------------


def test_depth_limit_truncates():
    assert "…" in s({"a": {"b": {"c": {"d": 1}}}}, depth=2)


def test_depth_zero_truncates_root_container():
    assert "…" in s({"a": 1}, depth=0)


def test_max_keys_caps_record():
    out = s({f"f{i}": i for i in range(20)}, max_keys=5)
    assert "+15 more keys" in out


# --- edge cases ----------------------------------------------------------


def test_empty_dict():
    assert "0 keys" in s({})


def test_empty_list_single_line():
    out = s([])
    assert "0 items" in out and "\n" not in out


def test_datetime_leaf_does_not_crash():
    assert "datetime" in s({"t": datetime.datetime(2024, 1, 1)})


def test_custom_class_leaf_does_not_crash():
    class Widget:
        pass

    assert "Widget" in s({"w": Widget()})


def test_unicode_strings():
    assert "str" in s({"name": "日本語テスト", "emoji": "🎉"})


def test_tuple_and_set():
    assert "tuple" in s((1, 2, 3))
    assert "set" in s({1, 2, 3})


def test_large_list_is_sampled():
    out = s(list(range(15_000)))
    assert "sampled" in out and "15000 items" in out


def test_deterministic_output():
    data = {"a": [1, 2, 3], "b": {"c": "x"}, "d": [{"e": 1}]}
    assert s(data) == s(data)


# --- pattern hints -------------------------------------------------------


def test_email_hint():
    assert "~email" in s(["a@b.com", "c@d.org"])


def test_uuid_hint():
    assert "~uuid" in s(["550e8400-e29b-41d4-a716-446655440000"])


def test_datetime_hint():
    assert "~datetime" in s(["2024-01-01T00:00:00", "2025-06-15T09:00:00"])


def test_no_pattern_hint_when_values_mixed():
    assert "~email" not in s(["a@b.com", "not-an-email"])


# --- minority shares -----------------------------------------------------


def test_sub_one_percent_share_is_shown():
    # 1 odd value among 200 — its share rounds below 1% and must not vanish
    out = s([1] * 200 + ["odd"])
    assert "<1% str" in out

"""Unit tests for breaking vs non-breaking boundary constraints."""

import pytest
from json_schema_diff.comparator import compare_schemas
from json_schema_diff.models import ChangeClassification, ChangeType


def test_numeric_minimum_maximum():
    # Increasing minimum is breaking
    s_min1 = {"type": "number", "minimum": 10}
    s_min2 = {"type": "number", "minimum": 20}
    r = compare_schemas(s_min1, s_min2)
    assert r.is_breaking
    assert r.changes[0].change_type == ChangeType.CONSTRAINT_RESTRICTED

    # Decreasing minimum is non-breaking
    r_rev = compare_schemas(s_min2, s_min1)
    assert not r_rev.is_breaking
    assert r_rev.changes[0].change_type == ChangeType.CONSTRAINT_RELAXED

    # Decreasing maximum is breaking
    s_max1 = {"type": "number", "maximum": 100}
    s_max2 = {"type": "number", "maximum": 50}
    r_max = compare_schemas(s_max1, s_max2)
    assert r_max.is_breaking
    assert r_max.changes[0].change_type == ChangeType.CONSTRAINT_RESTRICTED

    # Increasing maximum is non-breaking
    r_max_rev = compare_schemas(s_max2, s_max1)
    assert not r_max_rev.is_breaking
    assert r_max_rev.changes[0].change_type == ChangeType.CONSTRAINT_RELAXED


def test_string_length_constraints():
    # Adding or increasing minLength is breaking
    s1 = {"type": "string", "minLength": 3}
    s2 = {"type": "string", "minLength": 5}
    r = compare_schemas(s1, s2)
    assert r.is_breaking

    # Decreasing maxLength is breaking
    s_len1 = {"type": "string", "maxLength": 50}
    s_len2 = {"type": "string", "maxLength": 20}
    r2 = compare_schemas(s_len1, s_len2)
    assert r2.is_breaking

    # Increasing maxLength is non-breaking
    r3 = compare_schemas(s_len2, s_len1)
    assert not r3.is_breaking


def test_regex_pattern_changes():
    s_none = {"type": "string"}
    s_pat = {"type": "string", "pattern": r"^[a-z]+$"}
    s_pat2 = {"type": "string", "pattern": r"^[A-Z]+$"}

    # Adding pattern is breaking
    r1 = compare_schemas(s_none, s_pat)
    assert r1.is_breaking
    assert r1.changes[0].change_type == ChangeType.CONSTRAINT_RESTRICTED

    # Changing pattern is breaking
    r2 = compare_schemas(s_pat, s_pat2)
    assert r2.is_breaking
    assert r2.changes[0].change_type == ChangeType.CONSTRAINT_RESTRICTED

    # Removing pattern is non-breaking
    r3 = compare_schemas(s_pat, s_none)
    assert not r3.is_breaking
    assert r3.changes[0].change_type == ChangeType.CONSTRAINT_RELAXED


def test_boolean_schemas():
    # true -> false is breaking
    r1 = compare_schemas(True, False)
    assert r1.is_breaking

    # false -> true is non-breaking
    r2 = compare_schemas(False, True)
    assert not r2.is_breaking

    # dict -> false is breaking
    r3 = compare_schemas({"type": "string"}, False)
    assert r3.is_breaking

    # false -> dict is non-breaking
    r4 = compare_schemas(False, {"type": "string"})
    assert not r4.is_breaking


def test_unique_items():
    s1 = {"type": "array"}
    s2 = {"type": "array", "uniqueItems": True}

    # Setting uniqueItems=True is breaking
    r = compare_schemas(s1, s2)
    assert r.is_breaking

    # Removing uniqueItems is non-breaking
    r_rev = compare_schemas(s2, s1)
    assert not r_rev.is_breaking

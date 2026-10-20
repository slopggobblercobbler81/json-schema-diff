"""Unit tests for core schema comparator logic."""

import pytest
from json_schema_diff.comparator import SchemaComparator, compare_schemas
from json_schema_diff.models import ChangeClassification, ChangeType


def test_identical_schemas():
    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "age": {"type": "integer"},
        },
        "required": ["name"],
    }
    result = compare_schemas(schema, schema)
    assert not result.has_changes
    assert not result.is_breaking
    assert result.total_count == 0


def test_property_added_and_removed():
    old_schema = {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "obsolete": {"type": "string"},
        },
    }
    new_schema = {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "nickname": {"type": "string"},
        },
    }
    result = compare_schemas(old_schema, new_schema)
    assert result.has_changes
    assert result.is_breaking
    assert result.breaking_count == 1  # obsolete removed
    assert result.non_breaking_count == 1  # nickname added

    removed = result.breaking_changes[0]
    assert removed.change_type == ChangeType.PROPERTY_REMOVED
    assert "obsolete" in removed.path

    added = result.non_breaking_changes[0]
    assert added.change_type == ChangeType.PROPERTY_ADDED
    assert "nickname" in added.path


def test_type_changes():
    # String to integer (breaking)
    s1 = {"type": "string"}
    s2 = {"type": "integer"}
    r1 = compare_schemas(s1, s2)
    assert r1.is_breaking
    assert r1.changes[0].change_type == ChangeType.TYPE_CHANGED

    # Widening: string -> [string, null] (non-breaking)
    s3 = {"type": ["string", "null"]}
    r2 = compare_schemas(s1, s3)
    assert not r2.is_breaking
    assert r2.changes[0].classification == ChangeClassification.NON_BREAKING

    # Narrowing: [string, null] -> string (breaking)
    r3 = compare_schemas(s3, s1)
    assert r3.is_breaking
    assert r3.changes[0].classification == ChangeClassification.BREAKING


def test_required_fields():
    old_schema = {
        "type": "object",
        "properties": {
            "a": {"type": "string"},
            "b": {"type": "string"},
        },
        "required": ["a"],
    }
    # Add 'b' as required (breaking)
    new_schema_add_req = {
        "type": "object",
        "properties": {
            "a": {"type": "string"},
            "b": {"type": "string"},
        },
        "required": ["a", "b"],
    }
    r1 = compare_schemas(old_schema, new_schema_add_req)
    assert r1.is_breaking
    assert r1.breaking_count == 1
    assert r1.changes[0].change_type == ChangeType.REQUIRED_ADDED

    # Remove 'a' from required (non-breaking)
    new_schema_rem_req = {
        "type": "object",
        "properties": {
            "a": {"type": "string"},
            "b": {"type": "string"},
        },
        "required": [],
    }
    r2 = compare_schemas(old_schema, new_schema_rem_req)
    assert not r2.is_breaking
    assert r2.non_breaking_count == 1
    assert r2.changes[0].change_type == ChangeType.REQUIRED_REMOVED


def test_enum_changes():
    old_schema = {"type": "string", "enum": ["PENDING", "ACTIVE", "CLOSED"]}
    
    # Adding a value (non-breaking)
    new_schema_add = {"type": "string", "enum": ["PENDING", "ACTIVE", "CLOSED", "ARCHIVED"]}
    r1 = compare_schemas(old_schema, new_schema_add)
    assert not r1.is_breaking
    assert r1.changes[0].change_type == ChangeType.ENUM_VALUE_ADDED

    # Removing a value (breaking)
    new_schema_rem = {"type": "string", "enum": ["PENDING", "ACTIVE"]}
    r2 = compare_schemas(old_schema, new_schema_rem)
    assert r2.is_breaking
    assert r2.changes[0].change_type == ChangeType.ENUM_VALUE_REMOVED


def test_additional_properties():
    # Setting additionalProperties to false is breaking
    s1 = {"type": "object", "properties": {"id": {"type": "string"}}}
    s2 = {"type": "object", "properties": {"id": {"type": "string"}}, "additionalProperties": False}
    r1 = compare_schemas(s1, s2)
    assert r1.is_breaking
    assert r1.changes[0].change_type == ChangeType.ADDITIONAL_PROPERTIES_RESTRICTED

    # Relaxing from false to true is non-breaking
    r2 = compare_schemas(s2, s1)
    assert not r2.is_breaking
    assert r2.changes[0].change_type == ChangeType.ADDITIONAL_PROPERTIES_RELAXED


def test_array_items():
    old_schema = {
        "type": "array",
        "items": {"type": "string"},
    }
    new_schema = {
        "type": "array",
        "items": {"type": "integer"},
    }
    res = compare_schemas(old_schema, new_schema)
    assert res.is_breaking
    assert res.changes[0].path == "#/items/type"
    assert res.changes[0].change_type == ChangeType.TYPE_CHANGED


def test_metadata_ignore():
    old_schema = {
        "title": "User Profile",
        "description": "Old description",
        "type": "object",
    }
    new_schema = {
        "title": "User Account Profile",
        "description": "Updated description",
        "type": "object",
    }
    # With ignore_meta=False
    r1 = compare_schemas(old_schema, new_schema, ignore_meta=False)
    assert r1.total_count == 2
    assert r1.info_count == 2
    assert not r1.is_breaking

    # With ignore_meta=True
    r2 = compare_schemas(old_schema, new_schema, ignore_meta=True)
    assert r2.total_count == 0


def test_combinators():
    old_schema = {
        "anyOf": [
            {"type": "string"},
            {"type": "number"},
        ]
    }
    # Removing a branch from anyOf is breaking
    new_schema_narrow = {
        "anyOf": [
            {"type": "string"}
        ]
    }
    r1 = compare_schemas(old_schema, new_schema_narrow)
    assert r1.is_breaking
    assert r1.changes[0].change_type == ChangeType.COMBINATOR_CHANGED

    # Adding a branch to anyOf is non-breaking
    r2 = compare_schemas(new_schema_narrow, old_schema)
    assert not r2.is_breaking
    assert r2.changes[0].classification == ChangeClassification.NON_BREAKING


def test_ref_resolution():
    old_schema = {
        "definitions": {
            "Address": {
                "type": "object",
                "properties": {"zip": {"type": "string"}},
            }
        },
        "type": "object",
        "properties": {
            "billing": {"$ref": "#/definitions/Address"}
        }
    }
    new_schema = {
        "definitions": {
            "Address": {
                "type": "object",
                "properties": {"zip": {"type": "integer"}},
            }
        },
        "type": "object",
        "properties": {
            "billing": {"$ref": "#/definitions/Address"}
        }
    }
    res = compare_schemas(old_schema, new_schema, resolve_refs=True)
    assert res.is_breaking
    assert any("billing" in c.path and c.change_type == ChangeType.TYPE_CHANGED for c in res.changes)

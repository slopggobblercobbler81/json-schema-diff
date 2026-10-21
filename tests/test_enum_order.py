import pytest
from json_schema_diff.comparator import compare_schemas

def test_enum_order_preservation():
    old_schema = {
        "type": "string",
        "enum": ["a", "b", "c"]
    }
    new_schema = {
        "type": "string",
        "enum": ["c", "b", "a"]
    }
    result = compare_schemas(old_schema, new_schema)
    assert result.has_changes
    changes = result.changes
    # Verify that order change in enum is detected
    assert any("enum" in c.path for c in changes)

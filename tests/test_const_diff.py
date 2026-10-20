"""Tests for const keyword diff detection."""

import pytest
from json_schema_diff.comparator import compare_schemas
from json_schema_diff.models import ChangeType


def test_const_diff():
    old_schema = {
        "type": "object",
        "properties": {
            "status": {"const": "active"}
        }
    }
    new_schema = {
        "type": "object",
        "properties": {
            "status": {"const": "inactive"}
        }
    }
    result = compare_schemas(old_schema, new_schema)
    assert result.has_changes
    assert any(c.change_type == ChangeType.CONST_CHANGED or "const" in str(c.path).lower() or "const" in c.description.lower() for c in result.changes)

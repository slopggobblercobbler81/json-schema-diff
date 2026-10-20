import pytest
from json_schema_diff import compare_schemas

def test_deeply_nested_array_item_type_changes():
    schema1 = {
        "type": "object",
        "properties": {
            "users": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"}
                    }
                }
            }
        }
    }
    schema2 = {
        "type": "object",
        "properties": {
            "users": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"}
                    }
                }
            }
        }
    }
    result = compare_schemas(schema1, schema2)
    assert len(result.changes) > 0

def test_null_vs_empty_object():
    schema1 = {
        "type": "object",
        "properties": {
            "metadata": {"type": "null"}
        }
    }
    schema2 = {
        "type": "object",
        "properties": {
            "metadata": {"type": "object"}
        }
    }
    result = compare_schemas(schema1, schema2)
    assert len(result.changes) > 0

def test_additional_properties_type_change():
    schema1 = {
        "type": "object",
        "additionalProperties": {"type": "string"}
    }
    schema2 = {
        "type": "object",
        "additionalProperties": {"type": "integer"}
    }
    result = compare_schemas(schema1, schema2)
    assert len(result.changes) > 0

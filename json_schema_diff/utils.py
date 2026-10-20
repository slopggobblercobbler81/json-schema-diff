"""Utility functions for JSON schema loading, path formatting, and normalization."""

from __future__ import annotations
import json
import os
import sys
from typing import Any, Dict, List, Optional, Union


def load_json_schema(source: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Load JSON schema from file path, JSON string, or stdin (if source is '-').
    
    If already a dictionary, returns it.
    """
    if isinstance(source, dict):
        return source

    if not isinstance(source, str):
        raise TypeError(f"Expected file path or schema dict, got {type(source).__name__}")

    if source == "-":
        content = sys.stdin.read()
        return json.loads(content)

    if os.path.isfile(source):
        with open(source, "r", encoding="utf-8") as f:
            return json.load(f)

    # Attempt parsing as JSON string directly
    try:
        data = json.loads(source)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, ValueError):
        pass

    raise FileNotFoundError(f"Schema file not found or invalid JSON string: {source}")


def format_path(elements: List[Union[str, int]], style: str = "pointer") -> str:
    """Format path elements into a pointer or dot-notation string.
    
    Default style is JSON Pointer format: '#/properties/user/type'
    """
    if not elements:
        return "#" if style == "pointer" else ""
    
    if style == "pointer":
        escaped = [
            str(e).replace("~", "~0").replace("/", "~1")
            for e in elements
        ]
        return "#/" + "/".join(escaped)
    else:
        # Dot notation
        return ".".join(str(e) for e in elements)


def normalize_types(type_val: Any) -> List[str]:
    """Normalize a schema 'type' field into a sorted list of strings."""
    if type_val is None:
        return []
    if isinstance(type_val, str):
        return [type_val]
    if isinstance(type_val, list):
        return sorted([str(t) for t in type_val])
    return [str(type_val)]


def resolve_local_ref(schema: Dict[str, Any], root: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve a simple local $ref pointer (e.g., '#/definitions/Foo' or '#/$defs/Foo').
    
    Returns the resolved subschema if possible, else the original schema.
    """
    ref = schema.get("$ref")
    if not ref or not isinstance(ref, str) or not ref.startswith("#/"):
        return schema

    parts = ref.lstrip("#/").split("/")
    curr = root
    try:
        for p in parts:
            p = p.replace("~1", "/").replace("~0", "~")
            curr = curr[p]
        if isinstance(curr, dict):
            # Merge ref target with any overrides in schema
            merged = dict(curr)
            merged.update({k: v for k, v in schema.items() if k != "$ref"})
            return merged
    except (KeyError, TypeError):
        pass
    
    return schema

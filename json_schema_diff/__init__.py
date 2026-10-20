"""json-schema-diff: Production-grade CLI & library to detect breaking changes between JSON schemas.
"""

from json_schema_diff.models import (
    Change,
    ChangeClassification,
    ChangeType,
    DiffResult,
    PathElement,
)
from json_schema_diff.comparator import SchemaComparator, compare_schemas, compare_files
from json_schema_diff.formatters import (
    TerminalFormatter,
    JsonFormatter,
    MarkdownFormatter,
    PlainFormatter,
    format_diff,
)

__version__ = "1.0.0"
__all__ = [
    "Change",
    "ChangeClassification",
    "ChangeType",
    "DiffResult",
    "PathElement",
    "SchemaComparator",
    "compare_schemas",
    "compare_files",
    "TerminalFormatter",
    "JsonFormatter",
    "MarkdownFormatter",
    "PlainFormatter",
    "format_diff",
]

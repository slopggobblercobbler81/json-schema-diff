"""Data models and enums for json-schema-diff."""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, List, Optional, Dict, Union


class ChangeClassification(str, Enum):
    """Classification of semantic impact of a schema change."""
    BREAKING = "BREAKING"
    NON_BREAKING = "NON_BREAKING"
    INFO = "INFO"


class ChangeType(str, Enum):
    """Specific category of change detected between schemas."""
    # Type changes
    TYPE_CHANGED = "TYPE_CHANGED"
    
    # Required properties
    REQUIRED_ADDED = "REQUIRED_ADDED"
    REQUIRED_REMOVED = "REQUIRED_REMOVED"
    
    # Object properties
    PROPERTY_ADDED = "PROPERTY_ADDED"
    PROPERTY_REMOVED = "PROPERTY_REMOVED"
    
    # Enum changes
    ENUM_VALUE_ADDED = "ENUM_VALUE_ADDED"
    ENUM_VALUE_REMOVED = "ENUM_VALUE_REMOVED"
    
    # Constraints
    CONSTRAINT_RESTRICTED = "CONSTRAINT_RESTRICTED"
    CONSTRAINT_RELAXED = "CONSTRAINT_RELAXED"
    
    # Additional properties
    ADDITIONAL_PROPERTIES_RESTRICTED = "ADDITIONAL_PROPERTIES_RESTRICTED"
    ADDITIONAL_PROPERTIES_RELAXED = "ADDITIONAL_PROPERTIES_RELAXED"
    
    # Items / Arrays
    ITEMS_TYPE_CHANGED = "ITEMS_TYPE_CHANGED"
    
    # Metadata
    META_CHANGED = "META_CHANGED"
    
    # Combinators (allOf, anyOf, oneOf)
    COMBINATOR_CHANGED = "COMBINATOR_CHANGED"
    
    # Generic
    SCHEMA_CHANGED = "SCHEMA_CHANGED"


PathElement = Union[str, int]


@dataclass
class Change:
    """Represents an individual difference found between two JSON schemas."""
    path: str
    change_type: ChangeType
    classification: ChangeClassification
    message: str
    old_value: Any = None
    new_value: Any = None
    rule: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert change to dictionary."""
        return {
            "path": self.path,
            "change_type": self.change_type.value,
            "classification": self.classification.value,
            "message": self.message,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "rule": self.rule,
        }


@dataclass
class DiffResult:
    """Aggregated result of comparing two schemas."""
    changes: List[Change] = field(default_factory=list)
    old_schema_source: Optional[str] = None
    new_schema_source: Optional[str] = None

    @property
    def has_changes(self) -> bool:
        """Returns True if any changes were detected."""
        return len(self.changes) > 0

    @property
    def is_breaking(self) -> bool:
        """Returns True if at least one change is classified as BREAKING."""
        return any(c.classification == ChangeClassification.BREAKING for c in self.changes)

    @property
    def breaking_changes(self) -> List[Change]:
        """Returns list of breaking changes."""
        return [c for c in self.changes if c.classification == ChangeClassification.BREAKING]

    @property
    def non_breaking_changes(self) -> List[Change]:
        """Returns list of non-breaking changes."""
        return [c for c in self.changes if c.classification == ChangeClassification.NON_BREAKING]

    @property
    def info_changes(self) -> List[Change]:
        """Returns list of informational/meta changes."""
        return [c for c in self.changes if c.classification == ChangeClassification.INFO]

    @property
    def total_count(self) -> int:
        return len(self.changes)

    @property
    def breaking_count(self) -> int:
        return len(self.breaking_changes)

    @property
    def non_breaking_count(self) -> int:
        return len(self.non_breaking_changes)

    @property
    def info_count(self) -> int:
        return len(self.info_changes)

    def filter(
        self,
        only_breaking: bool = False,
        ignore_meta: bool = False,
        path_prefix: Optional[str] = None,
    ) -> DiffResult:
        """Return a filtered copy of DiffResult."""
        filtered = self.changes
        if only_breaking:
            filtered = [c for c in filtered if c.classification == ChangeClassification.BREAKING]
        if ignore_meta:
            filtered = [c for c in filtered if c.classification != ChangeClassification.INFO]
        if path_prefix:
            filtered = [c for c in filtered if c.path.startswith(path_prefix)]
        
        return DiffResult(
            changes=filtered,
            old_schema_source=self.old_schema_source,
            new_schema_source=self.new_schema_source,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert entire result to dictionary."""
        return {
            "summary": {
                "total": self.total_count,
                "breaking": self.breaking_count,
                "non_breaking": self.non_breaking_count,
                "info": self.info_count,
                "is_breaking": self.is_breaking,
            },
            "sources": {
                "old": self.old_schema_source,
                "new": self.new_schema_source,
            },
            "changes": [c.to_dict() for c in self.changes],
        }

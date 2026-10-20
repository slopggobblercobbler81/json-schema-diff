"""Core JSON Schema comparator logic."""

from __future__ import annotations
import copy
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from json_schema_diff.models import (
    Change,
    ChangeClassification,
    ChangeType,
    DiffResult,
    PathElement,
)
from json_schema_diff.utils import (
    format_path,
    normalize_types,
    resolve_local_ref,
    load_json_schema,
)

# Metadata keywords that do not affect data validation
META_KEYWORDS = {"title", "description", "$comment", "default", "examples"}


class SchemaComparator:
    """Compares two JSON Schemas and computes breaking and non-breaking differences."""

    def __init__(
        self,
        ignore_meta: bool = False,
        path_style: str = "pointer",
        resolve_refs: bool = True,
    ):
        self.ignore_meta = ignore_meta
        self.path_style = path_style
        self.resolve_refs = resolve_refs
        self._visited_pairs: Set[Tuple[int, int]] = set()

    def compare(
        self,
        old_schema: Union[Dict[str, Any], bool],
        new_schema: Union[Dict[str, Any], bool],
        old_source: Optional[str] = None,
        new_source: Optional[str] = None,
    ) -> DiffResult:
        """Compare two JSON schemas and return a DiffResult."""
        self._visited_pairs.clear()
        changes: List[Change] = []
        
        root_old = old_schema if isinstance(old_schema, dict) else {}
        root_new = new_schema if isinstance(new_schema, dict) else {}

        self._compare_subschema(
            old_s=old_schema,
            new_s=new_schema,
            path_elements=[],
            root_old=root_old,
            root_new=root_new,
            changes=changes,
        )

        return DiffResult(
            changes=changes,
            old_schema_source=old_source,
            new_schema_source=new_source,
        )

    def _format(self, elements: List[PathElement]) -> str:
        return format_path(elements, style=self.path_style)

    def _compare_subschema(
        self,
        old_s: Union[Dict[str, Any], bool],
        new_s: Union[Dict[str, Any], bool],
        path_elements: List[PathElement],
        root_old: Dict[str, Any],
        root_new: Dict[str, Any],
        changes: List[Change],
    ) -> None:
        # Check cycle detection if objects
        if isinstance(old_s, dict) and isinstance(new_s, dict):
            pair_key = (id(old_s), id(new_s))
            if pair_key in self._visited_pairs:
                return
            self._visited_pairs.add(pair_key)

        path_str = self._format(path_elements)

        # Handle boolean schemas (Draft 7+)
        if isinstance(old_s, bool) or isinstance(new_s, bool):
            self._compare_boolean_schemas(old_s, new_s, path_str, changes)
            return

        if not isinstance(old_s, dict) or not isinstance(new_s, dict):
            if old_s != new_s:
                changes.append(
                    Change(
                        path=path_str,
                        change_type=ChangeType.SCHEMA_CHANGED,
                        classification=ChangeClassification.BREAKING,
                        message=f"Schema replaced with different value: {old_s!r} -> {new_s!r}",
                        old_value=old_s,
                        new_value=new_s,
                        rule="Non-dict schema values do not match.",
                    )
                )
            return

        # Resolve local references if requested
        if self.resolve_refs:
            if "$ref" in old_s:
                old_s = resolve_local_ref(old_s, root_old)
            if "$ref" in new_s:
                new_s = resolve_local_ref(new_s, root_new)

        # 1. Metadata changes
        if not self.ignore_meta:
            self._compare_metadata(old_s, new_s, path_elements, changes)

        # 2. Type changes
        self._compare_types(old_s, new_s, path_str, changes)

        # 3. Enum changes
        self._compare_enums(old_s, new_s, path_str, changes)

        # 4. Required property changes
        self._compare_required(old_s, new_s, path_str, changes)

        # 5. Object properties changes
        self._compare_properties(old_s, new_s, path_elements, root_old, root_new, changes)

        # 6. Additional properties
        self._compare_additional_properties(old_s, new_s, path_elements, root_old, root_new, changes)

        # 7. Numeric / String / Array constraints
        self._compare_constraints(old_s, new_s, path_str, changes)

        # 8. Array items
        self._compare_items(old_s, new_s, path_elements, root_old, root_new, changes)

        # 9. Combinators (allOf, anyOf, oneOf)
        self._compare_combinators(old_s, new_s, path_elements, root_old, root_new, changes)

    def _compare_boolean_schemas(
        self,
        old_s: Any,
        new_s: Any,
        path_str: str,
        changes: List[Change],
    ) -> None:
        if old_s is True and new_s is False:
            changes.append(
                Change(
                    path=path_str,
                    change_type=ChangeType.SCHEMA_CHANGED,
                    classification=ChangeClassification.BREAKING,
                    message="Schema changed from `true` (accept all) to `false` (reject all)",
                    old_value=True,
                    new_value=False,
                    rule="Changing schema to false rejects all previously valid data.",
                )
            )
        elif old_s is False and new_s is True:
            changes.append(
                Change(
                    path=path_str,
                    change_type=ChangeType.SCHEMA_CHANGED,
                    classification=ChangeClassification.NON_BREAKING,
                    message="Schema changed from `false` (reject all) to `true` (accept all)",
                    old_value=False,
                    new_value=True,
                    rule="Changing schema to true permits all data.",
                )
            )
        elif isinstance(old_s, dict) and new_s is False:
            changes.append(
                Change(
                    path=path_str,
                    change_type=ChangeType.SCHEMA_CHANGED,
                    classification=ChangeClassification.BREAKING,
                    message="Schema restricted to `false` (reject all)",
                    old_value=old_s,
                    new_value=False,
                    rule="False schema rejects all instances.",
                )
            )
        elif old_s is False and isinstance(new_s, dict):
            changes.append(
                Change(
                    path=path_str,
                    change_type=ChangeType.SCHEMA_CHANGED,
                    classification=ChangeClassification.NON_BREAKING,
                    message="Schema relaxed from `false` to subschema definition",
                    old_value=False,
                    new_value=new_s,
                    rule="Allows instances where none were allowed.",
                )
            )
        elif old_s is True and isinstance(new_s, dict):
            changes.append(
                Change(
                    path=path_str,
                    change_type=ChangeType.SCHEMA_CHANGED,
                    classification=ChangeClassification.BREAKING,
                    message="Schema restricted from `true` (accept all) to explicit constraints",
                    old_value=True,
                    new_value=new_s,
                    rule="Restricting open schema can reject previously valid instances.",
                )
            )
        elif isinstance(old_s, dict) and new_s is True:
            changes.append(
                Change(
                    path=path_str,
                    change_type=ChangeType.SCHEMA_CHANGED,
                    classification=ChangeClassification.NON_BREAKING,
                    message="Schema relaxed to `true` (accept all)",
                    old_value=old_s,
                    new_value=True,
                    rule="Removing constraints allows all valid instances.",
                )
            )

    def _compare_metadata(
        self,
        old_s: Dict[str, Any],
        new_s: Dict[str, Any],
        path_elements: List[PathElement],
        changes: List[Change],
    ) -> None:
        for kw in META_KEYWORDS:
            old_val = old_s.get(kw)
            new_val = new_s.get(kw)
            if old_val != new_val:
                p = self._format(path_elements + [kw])
                changes.append(
                    Change(
                        path=p,
                        change_type=ChangeType.META_CHANGED,
                        classification=ChangeClassification.INFO,
                        message=f"Metadata field '{kw}' changed",
                        old_value=old_val,
                        new_value=new_val,
                        rule="Metadata changes do not affect schema validation.",
                    )
                )

    def _compare_types(
        self,
        old_s: Dict[str, Any],
        new_s: Dict[str, Any],
        path_str: str,
        changes: List[Change],
    ) -> None:
        if "type" not in old_s and "type" not in new_s:
            return

        old_types = set(normalize_types(old_s.get("type")))
        new_types = set(normalize_types(new_s.get("type")))

        if not old_types and new_types:
            # Type was unconstrained, now constrained
            changes.append(
                Change(
                    path=f"{path_str}/type",
                    change_type=ChangeType.TYPE_CHANGED,
                    classification=ChangeClassification.BREAKING,
                    message=f"Type constraint added: {sorted(new_types)}",
                    old_value=None,
                    new_value=sorted(new_types),
                    rule="Adding type constraint rejects instances of other types.",
                )
            )
        elif old_types and not new_types:
            # Type was constrained, now unconstrained
            changes.append(
                Change(
                    path=f"{path_str}/type",
                    change_type=ChangeType.TYPE_CHANGED,
                    classification=ChangeClassification.NON_BREAKING,
                    message=f"Type constraint removed (was {sorted(old_types)})",
                    old_value=sorted(old_types),
                    new_value=None,
                    rule="Removing type constraint permits all types.",
                )
            )
        elif old_types != new_types:
            removed_types = old_types - new_types
            added_types = new_types - old_types
            
            if removed_types:
                # Disallowed one or more previous types => BREAKING
                changes.append(
                    Change(
                        path=f"{path_str}/type",
                        change_type=ChangeType.TYPE_CHANGED,
                        classification=ChangeClassification.BREAKING,
                        message=f"Type changed from {sorted(old_types)} to {sorted(new_types)} (removed: {sorted(removed_types)})",
                        old_value=sorted(old_types),
                        new_value=sorted(new_types),
                        rule="Removing allowed types is breaking for existing data of those types.",
                    )
                )
            else:
                # Only added allowed types => NON_BREAKING (widened)
                changes.append(
                    Change(
                        path=f"{path_str}/type",
                        change_type=ChangeType.TYPE_CHANGED,
                        classification=ChangeClassification.NON_BREAKING,
                        message=f"Allowed types expanded to include {sorted(added_types)}",
                        old_value=sorted(old_types),
                        new_value=sorted(new_types),
                        rule="Adding allowed types widens accepted data.",
                    )
                )

    def _compare_enums(
        self,
        old_s: Dict[str, Any],
        new_s: Dict[str, Any],
        path_str: str,
        changes: List[Change],
    ) -> None:
        if "enum" not in old_s and "enum" not in new_s:
            return

        old_enum = old_s.get("enum")
        new_enum = new_s.get("enum")

        if old_enum is None and new_enum is not None:
            changes.append(
                Change(
                    path=f"{path_str}/enum",
                    change_type=ChangeType.CONSTRAINT_RESTRICTED,
                    classification=ChangeClassification.BREAKING,
                    message=f"Enum constraint added with {len(new_enum)} allowed values",
                    old_value=None,
                    new_value=new_enum,
                    rule="Adding an enum restricts allowed values.",
                )
            )
            return

        if old_enum is not None and new_enum is None:
            changes.append(
                Change(
                    path=f"{path_str}/enum",
                    change_type=ChangeType.CONSTRAINT_RELAXED,
                    classification=ChangeClassification.NON_BREAKING,
                    message="Enum constraint removed",
                    old_value=old_enum,
                    new_value=None,
                    rule="Removing an enum relaxes restrictions.",
                )
            )
            return

        if isinstance(old_enum, list) and isinstance(new_enum, list):
            # Check removed values
            # JSON enum items can be dicts or lists or primitives, so compare representation
            old_set = [x for x in old_enum if x not in new_enum]
            new_set = [x for x in new_enum if x not in old_enum]

            if old_set:
                changes.append(
                    Change(
                        path=f"{path_str}/enum",
                        change_type=ChangeType.ENUM_VALUE_REMOVED,
                        classification=ChangeClassification.BREAKING,
                        message=f"Enum values removed: {old_set}",
                        old_value=old_enum,
                        new_value=new_enum,
                        rule="Removing enum values causes existing data using those values to fail.",
                    )
                )
            if new_set:
                changes.append(
                    Change(
                        path=f"{path_str}/enum",
                        change_type=ChangeType.ENUM_VALUE_ADDED,
                        classification=ChangeClassification.NON_BREAKING,
                        message=f"Enum values added: {new_set}",
                        old_value=old_enum,
                        new_value=new_enum,
                        rule="Adding enum values expands acceptable inputs.",
                    )
                )

    def _compare_required(
        self,
        old_s: Dict[str, Any],
        new_s: Dict[str, Any],
        path_str: str,
        changes: List[Change],
    ) -> None:
        old_req = set(old_s.get("required", [])) if isinstance(old_s.get("required"), list) else set()
        new_req = set(new_s.get("required", [])) if isinstance(new_s.get("required"), list) else set()

        added_req = new_req - old_req
        removed_req = old_req - new_req

        for prop in sorted(added_req):
            changes.append(
                Change(
                    path=f"{path_str}/required/{prop}",
                    change_type=ChangeType.REQUIRED_ADDED,
                    classification=ChangeClassification.BREAKING,
                    message=f"Property '{prop}' is now required",
                    old_value=False,
                    new_value=True,
                    rule="Adding a required field breaks instances that omit it.",
                )
            )

        for prop in sorted(removed_req):
            changes.append(
                Change(
                    path=f"{path_str}/required/{prop}",
                    change_type=ChangeType.REQUIRED_REMOVED,
                    classification=ChangeClassification.NON_BREAKING,
                    message=f"Property '{prop}' is no longer required (now optional)",
                    old_value=True,
                    new_value=False,
                    rule="Making a required field optional is backward-compatible.",
                )
            )

    def _compare_properties(
        self,
        old_s: Dict[str, Any],
        new_s: Dict[str, Any],
        path_elements: List[PathElement],
        root_old: Dict[str, Any],
        root_new: Dict[str, Any],
        changes: List[Change],
    ) -> None:
        old_props = old_s.get("properties", {}) if isinstance(old_s.get("properties"), dict) else {}
        new_props = new_s.get("properties", {}) if isinstance(new_s.get("properties"), dict) else {}

        old_keys = set(old_props.keys())
        new_keys = set(new_props.keys())

        # Added properties
        for key in sorted(new_keys - old_keys):
            p = self._format(path_elements + ["properties", key])
            changes.append(
                Change(
                    path=p,
                    change_type=ChangeType.PROPERTY_ADDED,
                    classification=ChangeClassification.NON_BREAKING,
                    message=f"Property '{key}' was added",
                    old_value=None,
                    new_value=new_props[key],
                    rule="Adding an optional property is non-breaking.",
                )
            )

        # Removed properties
        for key in sorted(old_keys - new_keys):
            p = self._format(path_elements + ["properties", key])
            changes.append(
                Change(
                    path=p,
                    change_type=ChangeType.PROPERTY_REMOVED,
                    classification=ChangeClassification.BREAKING,
                    message=f"Property '{key}' was removed",
                    old_value=old_props[key],
                    new_value=None,
                    rule="Removing a property breaks clients/consumers expecting that field.",
                )
            )

        # Common properties - recurse
        for key in sorted(old_keys & new_keys):
            self._compare_subschema(
                old_s=old_props[key],
                new_s=new_props[key],
                path_elements=path_elements + ["properties", key],
                root_old=root_old,
                root_new=root_new,
                changes=changes,
            )

    def _compare_additional_properties(
        self,
        old_s: Dict[str, Any],
        new_s: Dict[str, Any],
        path_elements: List[PathElement],
        root_old: Dict[str, Any],
        root_new: Dict[str, Any],
        changes: List[Change],
    ) -> None:
        old_ap = old_s.get("additionalProperties")
        new_ap = new_s.get("additionalProperties")

        if old_ap == new_ap:
            return

        p = self._format(path_elements + ["additionalProperties"])

        # Default in JSON Schema is true if unset
        old_is_false = (old_ap is False)
        new_is_false = (new_ap is False)

        if not old_is_false and new_is_false:
            changes.append(
                Change(
                    path=p,
                    change_type=ChangeType.ADDITIONAL_PROPERTIES_RESTRICTED,
                    classification=ChangeClassification.BREAKING,
                    message="additionalProperties set to false (disallows undeclared properties)",
                    old_value=old_ap,
                    new_value=False,
                    rule="Disallowing additional properties breaks instances containing extra fields.",
                )
            )
        elif old_is_false and not new_is_false:
            changes.append(
                Change(
                    path=p,
                    change_type=ChangeType.ADDITIONAL_PROPERTIES_RELAXED,
                    classification=ChangeClassification.NON_BREAKING,
                    message="additionalProperties relaxed from false",
                    old_value=False,
                    new_value=new_ap,
                    rule="Allowing additional properties is non-breaking.",
                )
            )
        elif isinstance(old_ap, dict) and isinstance(new_ap, dict):
            # Recurse on schema definition of additionalProperties
            self._compare_subschema(
                old_s=old_ap,
                new_s=new_ap,
                path_elements=path_elements + ["additionalProperties"],
                root_old=root_old,
                root_new=root_new,
                changes=changes,
            )

    def _compare_constraints(
        self,
        old_s: Dict[str, Any],
        new_s: Dict[str, Any],
        path_str: str,
        changes: List[Change],
    ) -> None:
        # 1. Lower bounds: minimum, exclusiveMinimum, minLength, minItems, minProperties
        lower_bounds = ["minimum", "exclusiveMinimum", "minLength", "minItems", "minProperties"]
        for lb in lower_bounds:
            old_val = old_s.get(lb)
            new_val = new_s.get(lb)
            if old_val == new_val:
                continue

            if old_val is None and new_val is not None:
                changes.append(
                    Change(
                        path=f"{path_str}/{lb}",
                        change_type=ChangeType.CONSTRAINT_RESTRICTED,
                        classification=ChangeClassification.BREAKING,
                        message=f"Added lower bound constraint '{lb}': {new_val}",
                        old_value=None,
                        new_value=new_val,
                        rule=f"Adding {lb} can reject previously valid instances below {new_val}.",
                    )
                )
            elif old_val is not None and new_val is None:
                changes.append(
                    Change(
                        path=f"{path_str}/{lb}",
                        change_type=ChangeType.CONSTRAINT_RELAXED,
                        classification=ChangeClassification.NON_BREAKING,
                        message=f"Removed lower bound constraint '{lb}' (was {old_val})",
                        old_value=old_val,
                        new_value=None,
                        rule=f"Removing {lb} relaxes constraints.",
                    )
                )
            elif old_val is not None and new_val is not None:
                if new_val > old_val:
                    changes.append(
                        Change(
                            path=f"{path_str}/{lb}",
                            change_type=ChangeType.CONSTRAINT_RESTRICTED,
                            classification=ChangeClassification.BREAKING,
                            message=f"Increased lower bound '{lb}': {old_val} -> {new_val}",
                            old_value=old_val,
                            new_value=new_val,
                            rule=f"Increasing {lb} rejects values between {old_val} and {new_val}.",
                        )
                    )
                else:
                    changes.append(
                        Change(
                            path=f"{path_str}/{lb}",
                            change_type=ChangeType.CONSTRAINT_RELAXED,
                            classification=ChangeClassification.NON_BREAKING,
                            message=f"Decreased lower bound '{lb}': {old_val} -> {new_val}",
                            old_value=old_val,
                            new_value=new_val,
                            rule=f"Decreasing {lb} permits more values.",
                        )
                    )

        # 2. Upper bounds: maximum, exclusiveMaximum, maxLength, maxItems, maxProperties
        upper_bounds = ["maximum", "exclusiveMaximum", "maxLength", "maxItems", "maxProperties"]
        for ub in upper_bounds:
            old_val = old_s.get(ub)
            new_val = new_s.get(ub)
            if old_val == new_val:
                continue

            if old_val is None and new_val is not None:
                changes.append(
                    Change(
                        path=f"{path_str}/{ub}",
                        change_type=ChangeType.CONSTRAINT_RESTRICTED,
                        classification=ChangeClassification.BREAKING,
                        message=f"Added upper bound constraint '{ub}': {new_val}",
                        old_value=None,
                        new_value=new_val,
                        rule=f"Adding {ub} rejects instances above {new_val}.",
                    )
                )
            elif old_val is not None and new_val is None:
                changes.append(
                    Change(
                        path=f"{path_str}/{ub}",
                        change_type=ChangeType.CONSTRAINT_RELAXED,
                        classification=ChangeClassification.NON_BREAKING,
                        message=f"Removed upper bound constraint '{ub}' (was {old_val})",
                        old_value=old_val,
                        new_value=None,
                        rule=f"Removing {ub} relaxes constraints.",
                    )
                )
            elif old_val is not None and new_val is not None:
                if new_val < old_val:
                    changes.append(
                        Change(
                            path=f"{path_str}/{ub}",
                            change_type=ChangeType.CONSTRAINT_RESTRICTED,
                            classification=ChangeClassification.BREAKING,
                            message=f"Decreased upper bound '{ub}': {old_val} -> {new_val}",
                            old_value=old_val,
                            new_value=new_val,
                            rule=f"Decreasing {ub} rejects values between {new_val} and {old_val}.",
                        )
                    )
                else:
                    changes.append(
                        Change(
                            path=f"{path_str}/{ub}",
                            change_type=ChangeType.CONSTRAINT_RELAXED,
                            classification=ChangeClassification.NON_BREAKING,
                            message=f"Increased upper bound '{ub}': {old_val} -> {new_val}",
                            old_value=old_val,
                            new_value=new_val,
                            rule=f"Increasing {ub} permits more values.",
                        )
                    )

        # 3. Pattern
        old_pattern = old_s.get("pattern")
        new_pattern = new_s.get("pattern")
        if old_pattern != new_pattern:
            if old_pattern is None and new_pattern is not None:
                changes.append(
                    Change(
                        path=f"{path_str}/pattern",
                        change_type=ChangeType.CONSTRAINT_RESTRICTED,
                        classification=ChangeClassification.BREAKING,
                        message=f"Added regex pattern: {new_pattern!r}",
                        old_value=None,
                        new_value=new_pattern,
                        rule="Adding pattern constraint restricts valid string values.",
                    )
                )
            elif old_pattern is not None and new_pattern is None:
                changes.append(
                    Change(
                        path=f"{path_str}/pattern",
                        change_type=ChangeType.CONSTRAINT_RELAXED,
                        classification=ChangeClassification.NON_BREAKING,
                        message=f"Removed regex pattern (was {old_pattern!r})",
                        old_value=old_pattern,
                        new_value=None,
                        rule="Removing pattern constraint permits all strings.",
                    )
                )
            else:
                changes.append(
                    Change(
                        path=f"{path_str}/pattern",
                        change_type=ChangeType.CONSTRAINT_RESTRICTED,
                        classification=ChangeClassification.BREAKING,
                        message=f"Changed regex pattern: {old_pattern!r} -> {new_pattern!r}",
                        old_value=old_pattern,
                        new_value=new_pattern,
                        rule="Changing pattern constraint can invalidate existing strings.",
                    )
                )

        # 4. Format
        old_format = old_s.get("format")
        new_format = new_s.get("format")
        if old_format != new_format:
            if old_format is None and new_format is not None:
                changes.append(
                    Change(
                        path=f"{path_str}/format",
                        change_type=ChangeType.CONSTRAINT_RESTRICTED,
                        classification=ChangeClassification.BREAKING,
                        message=f"Added format constraint: '{new_format}'",
                        old_value=None,
                        new_value=new_format,
                        rule="Adding format restricts acceptable string formats.",
                    )
                )
            elif old_format is not None and new_format is None:
                changes.append(
                    Change(
                        path=f"{path_str}/format",
                        change_type=ChangeType.CONSTRAINT_RELAXED,
                        classification=ChangeClassification.NON_BREAKING,
                        message=f"Removed format constraint (was '{old_format}')",
                        old_value=old_format,
                        new_value=None,
                        rule="Removing format constraint allows any format.",
                    )
                )
            else:
                changes.append(
                    Change(
                        path=f"{path_str}/format",
                        change_type=ChangeType.CONSTRAINT_RESTRICTED,
                        classification=ChangeClassification.BREAKING,
                        message=f"Changed format constraint: '{old_format}' -> '{new_format}'",
                        old_value=old_format,
                        new_value=new_format,
                        rule="Changing format constraint is breaking for existing data.",
                    )
                )

        # 5. uniqueItems
        old_uniq = old_s.get("uniqueItems")
        new_uniq = new_s.get("uniqueItems")
        if old_uniq != new_uniq:
            if new_uniq is True:
                changes.append(
                    Change(
                        path=f"{path_str}/uniqueItems",
                        change_type=ChangeType.CONSTRAINT_RESTRICTED,
                        classification=ChangeClassification.BREAKING,
                        message="uniqueItems set to true",
                        old_value=old_uniq,
                        new_value=True,
                        rule="Requiring unique items rejects arrays with duplicate elements.",
                    )
                )
            else:
                changes.append(
                    Change(
                        path=f"{path_str}/uniqueItems",
                        change_type=ChangeType.CONSTRAINT_RELAXED,
                        classification=ChangeClassification.NON_BREAKING,
                        message="uniqueItems constraint removed/relaxed",
                        old_value=old_uniq,
                        new_value=new_uniq,
                        rule="Allowing duplicate items relaxes array validation.",
                    )
                )

        # 6. multipleOf
        old_mo = old_s.get("multipleOf")
        new_mo = new_s.get("multipleOf")
        if old_mo != new_mo:
            if old_mo is None and new_mo is not None:
                changes.append(
                    Change(
                        path=f"{path_str}/multipleOf",
                        change_type=ChangeType.CONSTRAINT_RESTRICTED,
                        classification=ChangeClassification.BREAKING,
                        message=f"Added multipleOf constraint: {new_mo}",
                        old_value=None,
                        new_value=new_mo,
                        rule="Adding multipleOf rejects numbers not divisible by factor.",
                    )
                )
            elif old_mo is not None and new_mo is None:
                changes.append(
                    Change(
                        path=f"{path_str}/multipleOf",
                        change_type=ChangeType.CONSTRAINT_RELAXED,
                        classification=ChangeClassification.NON_BREAKING,
                        message=f"Removed multipleOf constraint (was {old_mo})",
                        old_value=old_mo,
                        new_value=None,
                        rule="Removing multipleOf allows all numbers.",
                    )
                )
            else:
                changes.append(
                    Change(
                        path=f"{path_str}/multipleOf",
                        change_type=ChangeType.CONSTRAINT_RESTRICTED,
                        classification=ChangeClassification.BREAKING,
                        message=f"Changed multipleOf constraint: {old_mo} -> {new_mo}",
                        old_value=old_mo,
                        new_value=new_mo,
                        rule="Changing multipleOf factor rejects previously divisible numbers.",
                    )
                )

    def _compare_items(
        self,
        old_s: Dict[str, Any],
        new_s: Dict[str, Any],
        path_elements: List[PathElement],
        root_old: Dict[str, Any],
        root_new: Dict[str, Any],
        changes: List[Change],
    ) -> None:
        if "items" not in old_s and "items" not in new_s:
            return

        old_items = old_s.get("items")
        new_items = new_s.get("items")

        if old_items is None and new_items is not None:
            p = self._format(path_elements + ["items"])
            changes.append(
                Change(
                    path=p,
                    change_type=ChangeType.ITEMS_TYPE_CHANGED,
                    classification=ChangeClassification.BREAKING,
                    message="Array items schema added",
                    old_value=None,
                    new_value=new_items,
                    rule="Constraining array items can reject previously valid items.",
                )
            )
            return

        if old_items is not None and new_items is None:
            p = self._format(path_elements + ["items"])
            changes.append(
                Change(
                    path=p,
                    change_type=ChangeType.ITEMS_TYPE_CHANGED,
                    classification=ChangeClassification.NON_BREAKING,
                    message="Array items schema removed",
                    old_value=old_items,
                    new_value=None,
                    rule="Removing items constraint allows any item in array.",
                )
            )
            return

        if isinstance(old_items, dict) and isinstance(new_items, dict):
            self._compare_subschema(
                old_s=old_items,
                new_s=new_items,
                path_elements=path_elements + ["items"],
                root_old=root_old,
                root_new=root_new,
                changes=changes,
            )
        elif isinstance(old_items, list) and isinstance(new_items, list):
            # Tuple validation
            min_len = min(len(old_items), len(new_items))
            for i in range(min_len):
                self._compare_subschema(
                    old_s=old_items[i],
                    new_s=new_items[i],
                    path_elements=path_elements + ["items", i],
                    root_old=root_old,
                    root_new=root_new,
                    changes=changes,
                )
            if len(new_items) > len(old_items):
                p = self._format(path_elements + ["items"])
                changes.append(
                    Change(
                        path=p,
                        change_type=ChangeType.ITEMS_TYPE_CHANGED,
                        classification=ChangeClassification.BREAKING,
                        message=f"Tuple item schemas added at positions {len(old_items)}..{len(new_items)-1}",
                        old_value=len(old_items),
                        new_value=len(new_items),
                        rule="Adding tuple positional schemas can constrain additional indices.",
                    )
                )
            elif len(new_items) < len(old_items):
                p = self._format(path_elements + ["items"])
                changes.append(
                    Change(
                        path=p,
                        change_type=ChangeType.ITEMS_TYPE_CHANGED,
                        classification=ChangeClassification.NON_BREAKING,
                        message=f"Tuple item schemas removed at positions {len(new_items)}..{len(old_items)-1}",
                        old_value=len(old_items),
                        new_value=len(new_items),
                        rule="Removing tuple positional schemas relaxes restrictions.",
                    )
                )
        elif type(old_items) != type(new_items):
            p = self._format(path_elements + ["items"])
            changes.append(
                Change(
                    path=p,
                    change_type=ChangeType.ITEMS_TYPE_CHANGED,
                    classification=ChangeClassification.BREAKING,
                    message=f"Array items changed from {type(old_items).__name__} to {type(new_items).__name__}",
                    old_value=old_items,
                    new_value=new_items,
                    rule="Changing items structure format alters array validation.",
                )
            )

    def _compare_combinators(
        self,
        old_s: Dict[str, Any],
        new_s: Dict[str, Any],
        path_elements: List[PathElement],
        root_old: Dict[str, Any],
        root_new: Dict[str, Any],
        changes: List[Change],
    ) -> None:
        combinators = ["oneOf", "anyOf", "allOf"]
        for comb in combinators:
            if comb not in old_s and comb not in new_s:
                continue

            old_list = old_s.get(comb)
            new_list = new_s.get(comb)

            if old_list is None and new_list is not None:
                p = self._format(path_elements + [comb])
                changes.append(
                    Change(
                        path=p,
                        change_type=ChangeType.COMBINATOR_CHANGED,
                        classification=ChangeClassification.BREAKING,
                        message=f"Added '{comb}' constraint with {len(new_list)} branches",
                        old_value=None,
                        new_value=new_list,
                        rule=f"Adding {comb} combinator applies additional validation conditions.",
                    )
                )
                continue

            if old_list is not None and new_list is None:
                p = self._format(path_elements + [comb])
                classification = (
                    ChangeClassification.NON_BREAKING
                    if comb == "allOf"
                    else ChangeClassification.BREAKING
                )
                changes.append(
                    Change(
                        path=p,
                        change_type=ChangeType.COMBINATOR_CHANGED,
                        classification=classification,
                        message=f"Removed '{comb}' constraint",
                        old_value=old_list,
                        new_value=None,
                        rule=f"Removing {comb} alters validation rules.",
                    )
                )
                continue

            if isinstance(old_list, list) and isinstance(new_list, list):
                if comb in ("anyOf", "oneOf"):
                    if len(new_list) < len(old_list):
                        p = self._format(path_elements + [comb])
                        changes.append(
                            Change(
                                path=p,
                                change_type=ChangeType.COMBINATOR_CHANGED,
                                classification=ChangeClassification.BREAKING,
                                message=f"Branches removed from '{comb}' ({len(old_list)} -> {len(new_list)})",
                                old_value=len(old_list),
                                new_value=len(new_list),
                                rule=f"Removing branches from {comb} narrows accepted schemas.",
                            )
                        )
                    elif len(new_list) > len(old_list):
                        p = self._format(path_elements + [comb])
                        changes.append(
                            Change(
                                path=p,
                                change_type=ChangeType.COMBINATOR_CHANGED,
                                classification=ChangeClassification.NON_BREAKING,
                                message=f"Branches added to '{comb}' ({len(old_list)} -> {len(new_list)})",
                                old_value=len(old_list),
                                new_value=len(new_list),
                                rule=f"Adding branches to {comb} widens accepted schemas.",
                            )
                        )
                elif comb == "allOf":
                    if len(new_list) > len(old_list):
                        p = self._format(path_elements + [comb])
                        changes.append(
                            Change(
                                path=p,
                                change_type=ChangeType.COMBINATOR_CHANGED,
                                classification=ChangeClassification.BREAKING,
                                message=f"Branches added to 'allOf' ({len(old_list)} -> {len(new_list)})",
                                old_value=len(old_list),
                                new_value=len(new_list),
                                rule="Adding branches to allOf adds additional required constraints.",
                            )
                        )
                    elif len(new_list) < len(old_list):
                        p = self._format(path_elements + [comb])
                        changes.append(
                            Change(
                                path=p,
                                change_type=ChangeType.COMBINATOR_CHANGED,
                                classification=ChangeClassification.NON_BREAKING,
                                message=f"Branches removed from 'allOf' ({len(old_list)} -> {len(new_list)})",
                                old_value=len(old_list),
                                new_value=len(new_list),
                                rule="Removing branches from allOf relaxes required constraints.",
                            )
                        )


def compare_schemas(
    old_schema: Union[Dict[str, Any], bool],
    new_schema: Union[Dict[str, Any], bool],
    ignore_meta: bool = False,
    path_style: str = "pointer",
    resolve_refs: bool = True,
    old_source: Optional[str] = None,
    new_source: Optional[str] = None,
) -> DiffResult:
    """Convenience function to compare two JSON schema dictionaries."""
    comparator = SchemaComparator(
        ignore_meta=ignore_meta,
        path_style=path_style,
        resolve_refs=resolve_refs,
    )
    return comparator.compare(
        old_schema=old_schema,
        new_schema=new_schema,
        old_source=old_source,
        new_source=new_source,
    )


def compare_files(
    old_file: str,
    new_file: str,
    ignore_meta: bool = False,
    path_style: str = "pointer",
    resolve_refs: bool = True,
) -> DiffResult:
    """Load JSON schemas from two files and compare them."""
    old_schema = load_json_schema(old_file)
    new_schema = load_json_schema(new_file)
    return compare_schemas(
        old_schema=old_schema,
        new_schema=new_schema,
        ignore_meta=ignore_meta,
        path_style=path_style,
        resolve_refs=resolve_refs,
        old_source=old_file,
        new_source=new_file,
    )

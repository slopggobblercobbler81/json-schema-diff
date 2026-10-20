"""Unit tests for models and DiffResult."""

import pytest
from json_schema_diff.models import (
    Change,
    ChangeClassification,
    ChangeType,
    DiffResult,
)


def test_change_to_dict():
    c = Change(
        path="#/properties/age",
        change_type=ChangeType.CONSTRAINT_RESTRICTED,
        classification=ChangeClassification.BREAKING,
        message="minimum increased from 0 to 18",
        old_value=0,
        new_value=18,
        rule="Increasing minimum is breaking.",
    )
    d = c.to_dict()
    assert d["path"] == "#/properties/age"
    assert d["change_type"] == "CONSTRAINT_RESTRICTED"
    assert d["classification"] == "BREAKING"
    assert d["old_value"] == 0
    assert d["new_value"] == 18
    assert d["rule"] == "Increasing minimum is breaking."


def test_diff_result_properties():
    c1 = Change(
        path="#/properties/id",
        change_type=ChangeType.TYPE_CHANGED,
        classification=ChangeClassification.BREAKING,
        message="Type changed from string to integer",
    )
    c2 = Change(
        path="#/properties/name",
        change_type=ChangeType.PROPERTY_ADDED,
        classification=ChangeClassification.NON_BREAKING,
        message="Property 'name' added",
    )
    c3 = Change(
        path="#/description",
        change_type=ChangeType.META_CHANGED,
        classification=ChangeClassification.INFO,
        message="Description changed",
    )

    res = DiffResult(changes=[c1, c2, c3], old_schema_source="old.json", new_schema_source="new.json")

    assert res.has_changes is True
    assert res.is_breaking is True
    assert res.total_count == 3
    assert res.breaking_count == 1
    assert res.non_breaking_count == 1
    assert res.info_count == 1

    assert len(res.breaking_changes) == 1
    assert res.breaking_changes[0] == c1
    assert len(res.non_breaking_changes) == 1
    assert res.non_breaking_changes[0] == c2
    assert len(res.info_changes) == 1
    assert res.info_changes[0] == c3

    # Test filtering
    filtered_breaking = res.filter(only_breaking=True)
    assert filtered_breaking.total_count == 1
    assert filtered_breaking.breaking_count == 1

    filtered_no_meta = res.filter(ignore_meta=True)
    assert filtered_no_meta.total_count == 2
    assert filtered_no_meta.info_count == 0

    filtered_path = res.filter(path_prefix="#/properties/id")
    assert filtered_path.total_count == 1
    assert filtered_path.changes[0] == c1

    # to_dict
    res_dict = res.to_dict()
    assert res_dict["summary"]["total"] == 3
    assert res_dict["summary"]["breaking"] == 1
    assert res_dict["summary"]["is_breaking"] is True
    assert res_dict["sources"]["old"] == "old.json"
    assert len(res_dict["changes"]) == 3


def test_empty_diff_result():
    res = DiffResult()
    assert res.has_changes is False
    assert res.is_breaking is False
    assert res.total_count == 0
    assert res.breaking_count == 0
    assert res.non_breaking_count == 0
    assert res.info_count == 0

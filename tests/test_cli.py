"""Unit tests for the CLI interface."""

import json
import os
import pytest
from json_schema_diff.cli import main


@pytest.fixture
def schemas(tmp_path):
    old_file = tmp_path / "old.json"
    new_file = tmp_path / "new.json"
    new_breaking_file = tmp_path / "new_breaking.json"

    old_file.write_text(
        json.dumps({
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
            },
            "required": ["name"],
        }),
        encoding="utf-8",
    )

    new_file.write_text(
        json.dumps({
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
                "email": {"type": "string"},
            },
            "required": ["name"],
        }),
        encoding="utf-8",
    )

    new_breaking_file.write_text(
        json.dumps({
            "type": "object",
            "properties": {
                "name": {"type": "integer"},  # type changed string -> integer
            },
            "required": ["name"],
        }),
        encoding="utf-8",
    )

    return {
        "old": str(old_file),
        "new": str(new_file),
        "new_breaking": str(new_breaking_file),
    }


def test_cli_identical_schemas(capsys, schemas):
    ret = main([schemas["old"], schemas["old"]])
    assert ret == 0
    captured = capsys.readouterr()
    assert "No differences detected" in captured.out


def test_cli_non_breaking_with_fail_on_breaking(capsys, schemas):
    # Should exit 0 because only non-breaking change (email property added)
    ret = main([schemas["old"], schemas["new"], "--fail-on-breaking"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "NON-BREAKING" in captured.out


def test_cli_breaking_with_fail_on_breaking(capsys, schemas):
    # Should exit 1 because type changed
    ret = main([schemas["old"], schemas["new_breaking"], "--fail-on-breaking"])
    assert ret == 1
    captured = capsys.readouterr()
    assert "BREAKING" in captured.out


def test_cli_fail_on_diff(schemas):
    # Should exit 1 even if changes are non-breaking
    ret = main([schemas["old"], schemas["new"], "--fail-on-diff"])
    assert ret == 1

    # Should exit 0 when identical
    ret_identical = main([schemas["old"], schemas["old"], "--fail-on-diff"])
    assert ret_identical == 0


def test_cli_json_format(capsys, schemas):
    ret = main([schemas["old"], schemas["new"], "-f", "json"])
    assert ret == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["summary"]["is_breaking"] is False
    assert data["summary"]["total"] >= 1


def test_cli_markdown_format(capsys, schemas):
    ret = main([schemas["old"], schemas["new_breaking"], "-f", "markdown"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "# JSON Schema Diff Report" in captured.out


def test_cli_output_file(tmp_path, schemas):
    out_file = tmp_path / "report.txt"
    ret = main([schemas["old"], schemas["new"], "-o", str(out_file), "-f", "plain"])
    assert ret == 0
    content = out_file.read_text(encoding="utf-8")
    assert "PROPERTY_ADDED" in content


def test_cli_quiet(capsys, schemas):
    ret = main([schemas["old"], schemas["new"], "-q"])
    assert ret == 0
    captured = capsys.readouterr()
    assert captured.out == ""


def test_cli_invalid_file(capsys):
    ret = main(["non_existent_file_xyz.json", "other.json"])
    assert ret == 2
    captured = capsys.readouterr()
    assert "Error loading original schema" in captured.err


def test_cli_path_style_dot(capsys, schemas):
    ret = main([schemas["old"], schemas["new"], "--path-style", "dot", "-f", "plain"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "properties.email" in captured.out

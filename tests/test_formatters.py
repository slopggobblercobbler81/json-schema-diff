"""Unit tests for formatters."""

import json
import pytest
from json_schema_diff.models import Change, ChangeClassification, ChangeType, DiffResult
from json_schema_diff.formatters import (
    TerminalFormatter,
    JsonFormatter,
    MarkdownFormatter,
    PlainFormatter,
    format_diff,
)


@pytest.fixture
def sample_result():
    c1 = Change(
        path="#/properties/age",
        change_type=ChangeType.CONSTRAINT_RESTRICTED,
        classification=ChangeClassification.BREAKING,
        message="minimum increased from 0 to 18",
        rule="Increasing minimum rejects previous valid instances.",
    )
    c2 = Change(
        path="#/properties/nickname",
        change_type=ChangeType.PROPERTY_ADDED,
        classification=ChangeClassification.NON_BREAKING,
        message="Property 'nickname' added",
    )
    return DiffResult(
        changes=[c1, c2],
        old_schema_source="old.json",
        new_schema_source="new.json",
    )


def test_terminal_formatter_colored_and_uncolored(sample_result):
    # Uncolored
    fmt_no_color = TerminalFormatter(use_color=False)
    out = fmt_no_color.format(sample_result)
    assert "[BREAKING]" in out
    assert "[NON-BREAKING]" in out
    assert "#/properties/age" in out
    assert "\033[" not in out

    # Colored
    fmt_color = TerminalFormatter(use_color=True)
    out_color = fmt_color.format(sample_result)
    assert "\033[" in out_color


def test_terminal_formatter_no_changes():
    res = DiffResult()
    fmt = TerminalFormatter(use_color=False)
    out = fmt.format(res)
    assert "No differences detected" in out


def test_json_formatter(sample_result):
    fmt = JsonFormatter(indent=2)
    out = fmt.format(sample_result)
    data = json.loads(out)
    assert data["summary"]["breaking"] == 1
    assert data["summary"]["total"] == 2
    assert len(data["changes"]) == 2
    assert data["changes"][0]["path"] == "#/properties/age"


def test_markdown_formatter(sample_result):
    fmt = MarkdownFormatter()
    out = fmt.format(sample_result)
    assert "# JSON Schema Diff Report" in out
    assert "🚨 **BREAKING**" in out
    assert "| `#/properties/age` |" in out
    assert "| `#/properties/nickname` |" in out


def test_markdown_formatter_empty():
    res = DiffResult()
    fmt = MarkdownFormatter()
    out = fmt.format(res)
    assert "No differences detected" in out


def test_plain_formatter(sample_result):
    fmt = PlainFormatter()
    out = fmt.format(sample_result)
    assert "[BREAKING] #/properties/age:" in out
    assert "[NON-BREAKING] #/properties/nickname:" in out


def test_format_diff_helper(sample_result):
    assert "BREAKING" in format_diff(sample_result, "plain")
    assert "{" in format_diff(sample_result, "json")
    assert "# JSON Schema Diff Report" in format_diff(sample_result, "markdown")

    with pytest.raises(ValueError):
        format_diff(sample_result, "invalid_fmt")

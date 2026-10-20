"""Output formatters for JSON schema diff results."""

from __future__ import annotations
import json
import os
from typing import Dict, List, Optional
from json_schema_diff.models import DiffResult, ChangeClassification, Change


class BaseFormatter:
    """Base class for all diff formatters."""
    def format(self, result: DiffResult) -> str:
        raise NotImplementedError


class TerminalFormatter(BaseFormatter):
    """Formats diff results for terminal display with optional ANSI colors."""

    def __init__(self, use_color: Optional[bool] = None):
        if use_color is None:
            # Check NO_COLOR environment variable standard (https://no-color.org)
            # or if stdout is not a TTY (defaults to True unless explicitly disabled)
            self.use_color = os.environ.get("NO_COLOR") is None
        else:
            self.use_color = use_color

    def _c(self, text: str, code: str) -> str:
        if not self.use_color:
            return text
        return f"\033[{code}m{text}\033[0m"

    def red(self, text: str) -> str:
        return self._c(text, "1;31")

    def green(self, text: str) -> str:
        return self._c(text, "1;32")

    def yellow(self, text: str) -> str:
        return self._c(text, "1;33")

    def cyan(self, text: str) -> str:
        return self._c(text, "1;36")

    def bold(self, text: str) -> str:
        return self._c(text, "1")

    def dim(self, text: str) -> str:
        return self._c(text, "2")

    def format(self, result: DiffResult) -> str:
        lines: List[str] = []

        # Header
        lines.append(self.bold("=" * 60))
        lines.append(self.bold(" JSON SCHEMA DIFF REPORT"))
        lines.append(self.bold("=" * 60))

        if result.old_schema_source or result.new_schema_source:
            lines.append(f"  {self.dim('Old Schema:')} {result.old_schema_source or 'N/A'}")
            lines.append(f"  {self.dim('New Schema:')} {result.new_schema_source or 'N/A'}")
            lines.append("")

        if not result.has_changes:
            lines.append(self.green("✓ No differences detected. Schemas are identical."))
            lines.append("")
            return "\n".join(lines)

        # Summary line
        status_label = self.red("BREAKING CHANGES DETECTED") if result.is_breaking else self.green("NON-BREAKING CHANGES")
        lines.append(f" Status: {status_label}")
        lines.append(
            f" Total Changes: {self.bold(str(result.total_count))} | "
            f" Breaking: {self.red(str(result.breaking_count))} | "
            f" Non-Breaking: {self.green(str(result.non_breaking_count))} | "
            f" Info: {self.cyan(str(result.info_count))}"
        )
        lines.append("-" * 60)
        lines.append("")

        for change in result.changes:
            if change.classification == ChangeClassification.BREAKING:
                badge = self.red("[BREAKING]    ")
            elif change.classification == ChangeClassification.NON_BREAKING:
                badge = self.green("[NON-BREAKING]")
            else:
                badge = self.cyan("[INFO]        ")

            path_str = self.yellow(change.path)
            lines.append(f"{badge} {path_str}")
            lines.append(f"    Type:    {change.change_type.value}")
            lines.append(f"    Message: {change.message}")
            if change.rule:
                lines.append(f"    Rule:    {self.dim(change.rule)}")
            lines.append("")

        lines.append(self.bold("=" * 60))
        return "\n".join(lines)


class JsonFormatter(BaseFormatter):
    """Formats diff results as pretty-printed JSON."""

    def __init__(self, indent: int = 2):
        self.indent = indent

    def format(self, result: DiffResult) -> str:
        return json.dumps(result.to_dict(), indent=self.indent)


class MarkdownFormatter(BaseFormatter):
    """Formats diff results as GitHub-Flavored Markdown report."""

    def format(self, result: DiffResult) -> str:
        lines: List[str] = []

        lines.append("# JSON Schema Diff Report")
        lines.append("")

        # Overview Table
        lines.append("## Overview")
        lines.append("")
        lines.append(f"- **Status:** {'🚨 **Breaking Changes Detected**' if result.is_breaking else '✅ **Compatible / Non-Breaking**'}")
        if result.old_schema_source:
            lines.append(f"- **Old Schema:** `{result.old_schema_source}`")
        if result.new_schema_source:
            lines.append(f"- **New Schema:** `{result.new_schema_source}`")
        lines.append("")

        lines.append("| Metric | Count |")
        lines.append("|---|---|")
        lines.append(f"| **Total Changes** | `{result.total_count}` |")
        lines.append(f"| 🚨 **Breaking** | `{result.breaking_count}` |")
        lines.append(f"| 🟢 **Non-Breaking** | `{result.non_breaking_count}` |")
        lines.append(f"| ℹ️ **Info** | `{result.info_count}` |")
        lines.append("")

        if not result.has_changes:
            lines.append("> ✅ No differences detected between the two schemas.")
            return "\n".join(lines)

        lines.append("## Details")
        lines.append("")
        lines.append("| Severity | Path | Change Type | Description |")
        lines.append("|---|---|---|---|")

        for c in result.changes:
            if c.classification == ChangeClassification.BREAKING:
                badge = "🚨 **BREAKING**"
            elif c.classification == ChangeClassification.NON_BREAKING:
                badge = "🟢 NON-BREAKING"
            else:
                badge = "ℹ️ INFO"

            escaped_msg = c.message.replace("|", "\\|")
            lines.append(f"| {badge} | `{c.path}` | `{c.change_type.value}` | {escaped_msg} |")

        lines.append("")
        return "\n".join(lines)


class PlainFormatter(BaseFormatter):
    """Formats diff results as clean plain text without ANSI escape sequences."""

    def format(self, result: DiffResult) -> str:
        lines: List[str] = []
        if not result.has_changes:
            return "No differences detected."

        for c in result.changes:
            tag = c.classification.value.replace("_", "-")
            lines.append(f"[{tag}] {c.path}: {c.message} ({c.change_type.value})")

        return "\n".join(lines)


def format_diff(
    result: DiffResult,
    format_name: str = "terminal",
    use_color: Optional[bool] = None,
    indent: int = 2,
) -> str:
    """Format DiffResult with specified format ('terminal', 'json', 'markdown', 'plain')."""
    fmt = format_name.lower()
    if fmt == "terminal":
        return TerminalFormatter(use_color=use_color).format(result)
    elif fmt == "json":
        return JsonFormatter(indent=indent).format(result)
    elif fmt in ("markdown", "md"):
        return MarkdownFormatter().format(result)
    elif fmt == "plain":
        return PlainFormatter().format(result)
    else:
        raise ValueError(f"Unknown format: '{format_name}'. Allowed: terminal, json, markdown, plain")

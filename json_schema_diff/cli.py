"""Command-line interface for json-schema-diff."""

from __future__ import annotations
import argparse
import sys
from typing import List, Optional

from json_schema_diff import __version__
from json_schema_diff.comparator import compare_schemas
from json_schema_diff.formatters import format_diff
from json_schema_diff.utils import load_json_schema


def create_parser() -> argparse.ArgumentParser:
    """Create command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="json-schema-diff",
        description="Detect breaking changes, added/removed fields, and constraint changes between JSON schemas.",
    )

    parser.add_argument(
        "old_schema",
        help="Path to the original/base JSON schema file (or '-' for stdin)",
    )
    parser.add_argument(
        "new_schema",
        help="Path to the new/updated JSON schema file",
    )
    parser.add_argument(
        "-f",
        "--format",
        choices=["terminal", "json", "markdown", "plain"],
        default="terminal",
        help="Output format (default: terminal)",
    )
    parser.add_argument(
        "--fail-on-breaking",
        action="store_true",
        help="Exit with non-zero status code (1) if breaking changes are detected",
    )
    parser.add_argument(
        "--fail-on-diff",
        action="store_true",
        help="Exit with non-zero status code (1) if any difference is detected",
    )
    parser.add_argument(
        "--only-breaking",
        action="store_true",
        help="Display only breaking changes in the output report",
    )
    parser.add_argument(
        "--ignore-meta",
        action="store_true",
        help="Ignore differences in metadata fields (description, title, $comment, etc.)",
    )
    parser.add_argument(
        "--path-style",
        choices=["pointer", "dot"],
        default="pointer",
        help="Path display format: JSON Pointer (#/properties/name) or dot-notation (properties.name)",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI color codes in terminal output",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Write report to specified output file instead of stdout",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress all standard output; only return exit status",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    return parser


def main(args: Optional[List[str]] = None) -> int:
    """CLI main entry point."""
    parser = create_parser()
    parsed_args = parser.parse_args(args)

    # Load schemas
    try:
        old_data = load_json_schema(parsed_args.old_schema)
    except Exception as e:
        sys.stderr.write(f"Error loading original schema '{parsed_args.old_schema}': {e}\n")
        return 2

    try:
        new_data = load_json_schema(parsed_args.new_schema)
    except Exception as e:
        sys.stderr.write(f"Error loading new schema '{parsed_args.new_schema}': {e}\n")
        return 2

    # Perform diff
    result = compare_schemas(
        old_schema=old_data,
        new_schema=new_data,
        ignore_meta=parsed_args.ignore_meta,
        path_style=parsed_args.path_style,
        old_source=parsed_args.old_schema,
        new_source=parsed_args.new_schema,
    )

    # Filter if requested
    if parsed_args.only_breaking:
        result = result.filter(only_breaking=True)

    # Format output
    use_color = False if parsed_args.no_color else None
    output_text = format_diff(
        result=result,
        format_name=parsed_args.format,
        use_color=use_color,
    )

    if not parsed_args.quiet:
        if parsed_args.output:
            try:
                with open(parsed_args.output, "w", encoding="utf-8") as f:
                    f.write(output_text + "\n")
            except OSError as e:
                sys.stderr.write(f"Error writing to output file '{parsed_args.output}': {e}\n")
                return 2
        else:
            print(output_text)

    # Determine exit code
    if parsed_args.fail_on_diff and result.has_changes:
        return 1
    if parsed_args.fail_on_breaking and result.is_breaking:
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

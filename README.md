# json-schema-diff

[![CI](https://github.com/slopggobblercobbler81/json-schema-diff/actions/workflows/ci.yml/badge.svg)](https://github.com/slopggobblercobbler81/json-schema-diff/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/json-schema-diff.svg)](https://pypi.org/project/json-schema-diff/)
[![Python versions](https://img.shields.io/pypi/pyversions/json-schema-diff.svg)](https://pypi.org/project/json-schema-diff/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

A production-grade, zero-runtime-dependency CLI utility and Python library to compare JSON schemas and identify **breaking** vs **non-breaking** changes, added/removed properties, and constraint modifications.

Ideal for CI/CD pipelines, API gateway validations, OpenAPI/JSON Schema contracts, and automated release checks.

---

## Features

- 🔍 **Semantic Compatibility Analysis**: Automatically categorizes changes as `BREAKING`, `NON_BREAKING`, or `INFO`.
- ⚡ **Zero Runtime Dependencies**: Written entirely in pure Python standard library for maximum portability and instant execution.
- 🎨 **Multiple Output Formats**:
  - `terminal` (default): Colored ANSI report with summary tables and badges.
  - `json`: Machine-readable output for automated pipelines and `jq`.
  - `markdown`: GitHub-flavored markdown report ready for PR comments.
  - `plain`: Clean text output without ANSI codes.
- 🛡️ **Comprehensive Schema Coverage**:
  - **Types**: Widening vs narrowing, multi-type arrays.
  - **Properties**: Added, removed, or modified subschemas.
  - **Required fields**: Detecting newly required fields (breaking) vs relaxed fields (non-breaking).
  - **Enums**: Value additions (compatible) vs removals (breaking).
  - **Numeric & String Constraints**: `minimum`, `maximum`, `minLength`, `maxLength`, `minItems`, `maxItems`, `pattern`, `multipleOf`, `uniqueItems`.
  - **Object Restrictions**: `additionalProperties` restricted or relaxed.
  - **Combinators**: `allOf`, `anyOf`, `oneOf` branch additions and removals.
  - **References**: Local JSON pointer (`$ref`) resolution.
- ⚙️ **CI/CD Ready**: Configurable exit codes with `--fail-on-breaking` or `--fail-on-diff`.

---

## Installation

```bash
pip install json-schema-diff
```

Or run directly from source:
```bash
git clone https://github.com/slopggobblercobbler81/json-schema-diff.git
cd json-schema-diff
pip install -e .
```

---

## CLI Usage

### Basic Comparison

```bash
json-schema-diff old_schema.json new_schema.json
```

### Exit on Breaking Changes (CI/CD)

Exit with status `1` if any breaking changes are detected:

```bash
json-schema-diff v1.json v2.json --fail-on-breaking
```

### Output as GitHub Markdown

Generate a markdown summary (e.g. for GitHub Actions PR comments):

```bash
json-schema-diff v1.json v2.json --format markdown > pr_comment.md
```

### Output as JSON

```bash
json-schema-diff v1.json v2.json --format json | jq '.summary'
```

### Command Line Options

| Option | Description |
|---|---|
| `old_schema` | Path to base schema file (or `-` for stdin) |
| `new_schema` | Path to new schema file |
| `-f, --format` | Output format: `terminal`, `json`, `markdown`, `plain` (default: `terminal`) |
| `--fail-on-breaking` | Exit code 1 if breaking changes are detected |
| `--fail-on-diff` | Exit code 1 if any differences are detected |
| `--only-breaking` | Display only breaking changes in the output |
| `--ignore-meta` | Ignore metadata changes (`title`, `description`, `$comment`, etc.) |
| `--path-style` | Path format: `pointer` (e.g. `#/properties/user`) or `dot` (`properties.user`) |
| `--no-color` | Disable ANSI color codes in terminal output |
| `-o, --output` | Write output to a file instead of stdout |
| `-q, --quiet` | Suppress output; only return exit status |
| `-v, --version` | Show program's version number and exit |

---

## Python API Usage

You can use `json_schema_diff` as a Python module in your test suites or microservices:

```python
from json_schema_diff import compare_schemas, compare_files, format_diff

old_schema = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "age": {"type": "integer", "minimum": 0}
    },
    "required": ["id"]
}

new_schema = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "age": {"type": "integer", "minimum": 18},  # Breaking!
        "email": {"type": "string"}                 # Non-breaking!
    },
    "required": ["id"]
}

result = compare_schemas(old_schema, new_schema)

print(f"Has changes: {result.has_changes}")
print(f"Is breaking: {result.is_breaking}")
print(f"Breaking count: {result.breaking_count}")

# Inspect individual changes
for change in result.changes:
    print(f"[{change.classification}] {change.path}: {change.message}")

# Format output as markdown
markdown_report = format_diff(result, format_name="markdown")
```

---

## Breaking Change Rules

| Change | Classification | Reason |
|---|---|---|
| Property removed | **BREAKING** | Consumers relying on this property may fail |
| Property added | **NON_BREAKING** | Optional property addition is backward compatible |
| Type changed / narrowed | **BREAKING** | Existing data of previous type becomes invalid |
| Type expanded (e.g. string $\rightarrow$ [string, null]) | **NON_BREAKING** | All previous instances remain valid |
| Property added to `required` | **BREAKING** | Instances omitting this property will fail validation |
| Property removed from `required` | **NON_BREAKING** | Field is now optional; existing instances remain valid |
| Enum value removed | **BREAKING** | Data containing the removed value becomes invalid |
| Enum value added | **NON_BREAKING** | Expands accepted values |
| Lower bound (`minimum`, `minLength`) increased | **BREAKING** | Rejects values below new threshold |
| Upper bound (`maximum`, `maxLength`) decreased | **BREAKING** | Rejects values above new threshold |
| `additionalProperties: false` added | **BREAKING** | Rejecting extra properties invalidates instances with additional fields |

---

## CI/CD Workflow Example

Integrate `json-schema-diff` into your GitHub Actions workflow:

```yaml
name: Schema Compatibility Check

on: [pull_request]

jobs:
  check-schema:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install json-schema-diff
      - name: Verify Schema Compatibility
        run: |
          json-schema-diff schemas/v1.json schemas/v2.json --fail-on-breaking --format markdown > schema_report.md
```

---

## Running Tests

Run the test suite with pytest:

```bash
pip install pytest pytest-cov
pytest -v --cov=json_schema_diff
```

---

## License

MIT License. See [LICENSE](LICENSE) for details.

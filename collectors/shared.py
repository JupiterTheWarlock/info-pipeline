"""Shared utilities for collectors."""

import subprocess
from typing import Any

import yaml


def parse_opencli_output(output: str) -> list[dict]:
    """Parse opencli YAML output into list of dicts.

    opencli outputs YAML in two formats:
    1. A YAML list (no --- separators): "- key: val\\n  key2: val2"
    2. YAML documents separated by "---"

    Handles both cases.
    """
    output = output.strip()
    if not output:
        return []

    # Remove trailing npm update notice if it leaked into stdout
    lines = output.split("\n")
    clean_lines = []
    for line in lines:
        if "Update available" in line or "Run: npm install" in line:
            break
        clean_lines.append(line)
    output = "\n".join(clean_lines)

    # Case 1: Try parsing the whole thing as a single YAML document
    # (covers the YAML list format which is the common opencli output)
    try:
        result = yaml.safe_load(output)
        if isinstance(result, list):
            return [item for item in result if isinstance(item, dict)]
        if isinstance(result, dict):
            return [result]
    except yaml.YAMLError:
        pass

    # Case 2: Try --- separated documents
    items = []
    for doc in output.split("---"):
        doc = doc.strip()
        if not doc:
            continue
        try:
            item = yaml.safe_load(doc)
            if item and isinstance(item, dict):
                items.append(item)
            elif isinstance(item, list):
                items.extend(i for i in item if isinstance(i, dict))
        except yaml.YAMLError:
            continue
    return items


def run_opencli(*args: str, timeout: int = 120) -> tuple[list[dict], str]:
    """Run an opencli command and return (parsed_items, error_string).

    Returns empty list and error message if command failed.
    """
    try:
        result = subprocess.run(
            list(args), capture_output=True, text=True, timeout=timeout,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip() if result.stderr else ""
            return [], stderr[:500] if stderr else f"exit code {result.returncode}"
        return parse_opencli_output(result.stdout), ""
    except subprocess.TimeoutExpired:
        return [], "timed out"
    except FileNotFoundError:
        return [], f"command not found: {args[0]}"
    except Exception as e:
        return [], str(e)

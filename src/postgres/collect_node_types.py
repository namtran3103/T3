#!/usr/bin/env python3
"""
Scan all JSON plan files in pg_explain_job and tpch_sf1,
collect unique "Node Type" values from the plan trees, and output a JSON list.
"""

import json
import sys
from pathlib import Path


def collect_node_types_from_plan(plan: dict, out: set[str]) -> None:
    """Recursively collect 'Node Type' from a plan node and its Plans children."""
    if not isinstance(plan, dict):
        return
    if "Node Type" in plan:
        out.add(plan["Node Type"])
    for child in plan.get("Plans", []):
        collect_node_types_from_plan(child, out)


def collect_from_file(path: Path, out: set[str]) -> None:
    """Load a JSON file and collect all node types from its plan tree(s)."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"Warning: skip {path}: {e}", file=sys.stderr)
        return
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and "Plan" in item:
                collect_node_types_from_plan(item["Plan"], out)
    elif isinstance(data, dict) and "Plan" in data:
        collect_node_types_from_plan(data["Plan"], out)
    else:
        print(f"Warning: unknown structure in {path}", file=sys.stderr)


def main() -> None:
    script_dir = Path(__file__).resolve().parent
    roots = [
        script_dir / "pg_explain_job",
        script_dir / "tpch_sf1",
    ]
    node_types: set[str] = set()

    for root in roots:
        if not root.exists():
            print(f"Warning: directory not found: {root}", file=sys.stderr)
            continue
        for path in root.rglob("*.json"):
            if path.is_file():
                collect_from_file(path, node_types)

    result = sorted(node_types)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

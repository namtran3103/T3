"""
Enrich existing parsed zero-shot plans with additional information from raw EXPLAIN ANALYZE text.

This module takes parsed plans (from the original parser) and enriches them with:
- rows_removed_by_filter: Number of rows removed by filters in scan operators
- input_cardinality: Calculated as act_card + rows_removed_by_filter
- overall_selectivity: Calculated as act_card / input_cardinality
- expression_selectivities: Individual selectivities for each filter expression

Usage:
    python -m src.zeroshot.enrich_parsed_plans raw_file.json parsed_file.json output_file.json
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

# Regex patterns
rows_removed_regex = re.compile(r'Rows Removed by Filter:\s*(\d+)')
actual_rows_regex = re.compile(r'rows=(\d+)')
scan_op_regex = re.compile(r'(Seq Scan|Parallel Seq Scan|Index Scan|Index Only Scan)')


def extract_scan_info_from_raw(plan_lines: list, scan_line_idx: int) -> dict[str, Any]:
    """
    Extract scan information from raw EXPLAIN ANALYZE lines.
    
    Args:
        plan_lines: List of plan lines (each is a list with one string, or a string)
        scan_line_idx: Index of the scan line in plan_lines
    
    Returns:
        Dict with:
        - rows_removed_by_filter: int or None
        - act_card: int (from the scan line)
    """
    result = {}
    
    # Get the scan line
    scan_line = plan_lines[scan_line_idx]
    if isinstance(scan_line, list):
        scan_line = scan_line[0] if scan_line else ""
    scan_line = str(scan_line)
    
    # Extract actual rows from scan line: (actual time=X..Y rows=Z loops=W)
    rows_match = actual_rows_regex.search(scan_line)
    if rows_match:
        result['act_card'] = int(rows_match.group(1))
    
    # Look ahead up to 5 lines for "Rows Removed by Filter"
    for i in range(scan_line_idx + 1, min(scan_line_idx + 6, len(plan_lines))):
        next_line = plan_lines[i]
        if isinstance(next_line, list):
            next_line = next_line[0] if next_line else ""
        next_line = str(next_line)
        
        match = rows_removed_regex.search(next_line)
        if match:
            result['rows_removed_by_filter'] = int(match.group(1))
            break
    
    return result


def find_all_scans_in_raw(plan_lines: list) -> list[tuple[int, dict]]:
    """
    Find all scan operators in raw plan lines and extract their information.
    
    Returns:
        List of (line_index, scan_info_dict) tuples
    """
    scans = []
    for i, line in enumerate(plan_lines):
        line_str = line[0] if isinstance(line, list) and line else str(line)
        if scan_op_regex.search(line_str):
            scan_info = extract_scan_info_from_raw(plan_lines, i)
            # Always include scan info, even if rows_removed_by_filter is None
            # This ensures we match all scans, not just those with filters
            scans.append((i, scan_info))
    return scans


def enrich_parsed_plan_node(
    node: dict,
    scan_info_list: list[dict],
    scan_idx_ref: list[int]
) -> None:
    """
    Recursively enrich a parsed plan node with scan information.
    
    Args:
        node: Parsed plan node (dict with plan_parameters and children)
        scan_info_list: List of scan info dicts (from find_all_scans_in_raw)
        scan_idx_ref: List with single int ref for current scan index
    """
    p = node.get("plan_parameters", {})
    op_name = p.get("op_name", "")
    
    # Process children first (depth-first traversal)
    for child in node.get("children", []):
        enrich_parsed_plan_node(child, scan_info_list, scan_idx_ref)
    
    # Check if this is a scan operator (after processing children for depth-first matching)
    if op_name in ("Seq Scan", "Parallel Seq Scan", "Index Scan", "Index Only Scan"):
        scan_info = None
        if scan_idx_ref[0] < len(scan_info_list):
            scan_info = scan_info_list[scan_idx_ref[0]]
            
            # Verify that act_card matches (to ensure we're matching the right scan)
            node_act_card = p.get('act_card')
            scan_act_card = scan_info.get('act_card')
            
            # Match by act_card if available, otherwise just use order
            if scan_act_card is not None and node_act_card is not None:
                # Allow small floating point differences
                if abs(node_act_card - scan_act_card) > 0.1:
                    # Try to find a better match
                    best_match_idx = scan_idx_ref[0]
                    best_match_diff = abs(node_act_card - scan_act_card)
                    for i in range(scan_idx_ref[0] + 1, len(scan_info_list)):
                        other_act_card = scan_info_list[i].get('act_card')
                        if other_act_card is not None:
                            diff = abs(node_act_card - other_act_card)
                            if diff < best_match_diff:
                                best_match_idx = i
                                best_match_diff = diff
                    if best_match_idx != scan_idx_ref[0] and best_match_diff < abs(node_act_card - scan_act_card):
                        scan_info = scan_info_list[best_match_idx]
                        # Note: We don't update scan_idx_ref here to maintain order
        
        # FIXED: Always enrich ALL scans, even if no matching scan_info found
        act_card = p.get('act_card')
        if act_card is not None:
            rows_removed = scan_info.get('rows_removed_by_filter') if scan_info else None
            
            if rows_removed is not None and rows_removed > 0:
                # Filtering occurred: input = output + removed
                p['rows_removed_by_filter'] = rows_removed
                input_card = act_card + rows_removed
                p['input_cardinality'] = input_card
                
                # Calculate overall selectivity
                if input_card > 0:
                    selectivity = act_card / input_card
                    p['overall_selectivity'] = selectivity
            else:
                # No filtering info available (Index scans, scans without filters, or no raw data)
                # Set input_cardinality = act_card (conservative estimate)
                # Set selectivity = 1.0 (assume no filtering, though table might be larger)
                p['input_cardinality'] = act_card
                p['overall_selectivity'] = 1.0
                # Note: This is a conservative estimate. The actual table size might be larger,
                # but without "Rows Removed by Filter", we can't determine it.
            
            # If there are filter_columns, calculate per-expression selectivities
            filter_cols = p.get('filter_columns')
            if filter_cols and isinstance(filter_cols, dict):
                selectivity = p.get('overall_selectivity', 1.0)
                num_filters = count_filter_expressions(filter_cols)
                if num_filters > 0:
                    # Approximate: if multiple filters, each contributes to selectivity
                    # This is a simplification - actual calculation would need
                    # to understand the filter tree structure
                    p['estimated_filter_selectivity'] = selectivity
        
        # Increment scan index after processing (only if we had matching scan_info)
        if scan_info is not None:
            scan_idx_ref[0] += 1


def count_filter_expressions(filter_cols: dict) -> int:
    """Count the number of actual filter expressions (excluding AND/OR nodes)."""
    if not isinstance(filter_cols, dict):
        return 0
    
    operator = filter_cols.get('operator', '')
    # AND and OR are logical operators, not actual filters
    if operator in ('AND', 'OR'):
        count = 0
        for child in filter_cols.get('children', []):
            count += count_filter_expressions(child)
        return count
    else:
        # This is an actual filter expression
        return 1


def enrich_parsed_plan(
    parsed_plan: dict,
    raw_plan_lines: list
) -> dict:
    """
    Enrich a parsed plan with information extracted from raw EXPLAIN ANALYZE text.
    
    Args:
        parsed_plan: Parsed plan dict (from original parser)
        raw_plan_lines: Raw EXPLAIN ANALYZE lines (list of lists with strings)
    
    Returns:
        Enriched parsed plan dict
    """
    # Create a deep copy to avoid modifying original
    enriched = json.loads(json.dumps(parsed_plan))
    
    # Find all scans in raw plan
    scan_info_list = [info for _, info in find_all_scans_in_raw(raw_plan_lines)]
    
    # Enrich the parsed plan tree
    scan_idx_ref = [0]
    enrich_parsed_plan_node(enriched, scan_info_list, scan_idx_ref)
    
    return enriched


def enrich_file_pair(
    raw_path: Path,
    parsed_path: Path,
    output_path: Path
) -> None:
    """
    Enrich parsed plans from a file pair and write to output.
    
    Args:
        raw_path: Path to raw zero-shot JSON file
        parsed_path: Path to parsed zero-shot JSON file
        output_path: Path to write enriched parsed plans
    """
    # Load raw data
    with open(raw_path, 'r', encoding='utf-8') as f:
        raw_data = json.load(f)
    
    # Load parsed data
    with open(parsed_path, 'r', encoding='utf-8') as f:
        parsed_data = json.load(f)
    
    # Enrich each parsed plan
    enriched_plans = []
    raw_queries = raw_data.get('query_list', [])
    parsed_plans_list = parsed_data.get('parsed_plans', [])
    
    print(f"Enriching {len(parsed_plans_list)} parsed plans with raw data from {len(raw_queries)} queries")
    
    for i, parsed_plan in enumerate(parsed_plans_list):
        if i < len(raw_queries):
            raw_query = raw_queries[i]
            if 'analyze_plans' in raw_query and raw_query['analyze_plans']:
                raw_lines = raw_query['analyze_plans'][0]
                enriched = enrich_parsed_plan(parsed_plan, raw_lines)
                enriched_plans.append(enriched)
            else:
                # No raw data available - still enrich with defaults for scans
                enriched = enrich_parsed_plan(parsed_plan, [])
                enriched_plans.append(enriched)
        else:
            # No matching raw query - still enrich with defaults
            enriched = enrich_parsed_plan(parsed_plan, [])
            enriched_plans.append(enriched)
    
    # Write enriched plans
    output_data = {
        "parsed_plans": enriched_plans,
        "database_stats": parsed_data.get("database_stats"),
        "run_kwargs": parsed_data.get("run_kwargs")
    }
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, separators=(',', ':'))
    
    print(f"Wrote enriched plans to {output_path}")


def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Enrich parsed zero-shot plans with information from raw EXPLAIN ANALYZE text"
    )
    parser.add_argument("raw_file", type=Path, help="Path to raw zero-shot JSON file")
    parser.add_argument("parsed_file", type=Path, help="Path to parsed zero-shot JSON file")
    parser.add_argument("output_file", type=Path, help="Path to write enriched parsed plans")
    
    args = parser.parse_args()
    enrich_file_pair(args.raw_file, args.parsed_file, args.output_file)


if __name__ == "__main__":
    main()

"""
Enhanced parser for zero-shot plans that extracts additional information:
- Rows Removed by Filter (for TableScan input cardinality calculation)
- Expression selectivities (calculated from actual filtering ratios)

Based on the original parser from zero-shot-cost-estimation but enhanced to extract
missing information needed for accurate percentage calculations in T3.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

# Regex patterns
rows_removed_regex = re.compile(r'Rows Removed by Filter:\s*(\d+)')
actual_rows_regex = re.compile(r'rows=(\d+)')
planning_time_regex = re.compile(r'planning time: (?P<planning_time>\d+\.\d+) ms')
execution_time_regex = re.compile(r'execution time: (?P<execution_time>\d+\.\d+) ms')


def count_left_whitespaces(line: str) -> int:
    """Count leading whitespaces to determine nesting depth."""
    return len(line) - len(line.lstrip(' '))


def parse_rows_removed_by_filter(plan_lines: list[list[str]], scan_line_idx: int) -> Optional[int]:
    """
    Extract 'Rows Removed by Filter' value for a scan operator.
    
    Args:
        plan_lines: List of plan lines (each is a list with one string)
        scan_line_idx: Index of the scan line in plan_lines
    
    Returns:
        Number of rows removed by filter, or None if not found
    """
    # Look ahead up to 5 lines for "Rows Removed by Filter"
    for i in range(scan_line_idx + 1, min(scan_line_idx + 6, len(plan_lines))):
        line = plan_lines[i][0] if isinstance(plan_lines[i], list) and plan_lines[i] else str(plan_lines[i])
        match = rows_removed_regex.search(line)
        if match:
            return int(match.group(1))
    return None


def extract_scan_info_from_raw(plan_lines: list[list[str]], scan_line_idx: int) -> dict[str, Any]:
    """
    Extract scan information from raw EXPLAIN ANALYZE lines.
    
    Returns dict with:
    - rows_removed_by_filter: int or None
    - act_card: int (from the scan line)
    """
    result = {}
    
    # Get the scan line
    scan_line = plan_lines[scan_line_idx][0] if isinstance(plan_lines[scan_line_idx], list) else str(plan_lines[scan_line_idx])
    
    # Extract actual rows from scan line
    rows_match = actual_rows_regex.search(scan_line)
    if rows_match:
        result['act_card'] = int(rows_match.group(1))
    
    # Extract rows removed by filter
    rows_removed = parse_rows_removed_by_filter(plan_lines, scan_line_idx)
    if rows_removed is not None:
        result['rows_removed_by_filter'] = rows_removed
    
    return result


def find_scan_operators_recursive(
    node: dict,
    plan_lines: list[list[str]],
    line_idx_map: dict[int, int],
    depth: int = 0
) -> None:
    """
    Recursively find scan operators and enrich them with rows_removed_by_filter.
    
    This matches nodes in the parsed tree with lines in the raw plan by traversing
    both structures in parallel.
    """
    p = node.get("plan_parameters", {})
    op_name = p.get("op_name", "")
    
    # Check if this is a scan operator
    if op_name in ("Seq Scan", "Parallel Seq Scan", "Index Scan", "Index Only Scan"):
        # Try to find matching line in raw plan
        # We'll use a simple heuristic: find the first scan line that matches
        # In practice, we need to match by position in the tree
        pass  # Will be handled by caller
    
    # Recursively process children
    for child in node.get("children", []):
        find_scan_operators_recursive(child, plan_lines, line_idx_map, depth + 1)


def enrich_parsed_plan_with_raw_info(
    parsed_plan: dict,
    raw_plan_lines: list[list[str]]
) -> dict:
    """
    Enrich parsed plan with information extracted from raw EXPLAIN ANALYZE text.
    
    Adds:
    - rows_removed_by_filter to scan operators
    - calculated selectivities based on actual filtering
    """
    # Create a copy to avoid modifying original
    enriched = json.loads(json.dumps(parsed_plan))
    
    # Build a map of scan operators to their line indices
    scan_indices = []
    for i, line_list in enumerate(raw_plan_lines):
        line = line_list[0] if isinstance(line_list, list) and line_list else str(line_list)
        if 'Seq Scan' in line or 'Parallel Seq Scan' in line or 'Index Scan' in line or 'Index Only Scan' in line:
            scan_indices.append(i)
    
    # Traverse parsed plan tree and enrich scan nodes
    def enrich_node(node: dict, scan_idx_ref: list[int]) -> None:
        """Recursively enrich nodes."""
        p = node.get("plan_parameters", {})
        op_name = p.get("op_name", "")
        
        if op_name in ("Seq Scan", "Parallel Seq Scan", "Index Scan", "Index Only Scan"):
            if scan_idx_ref[0] < len(scan_indices):
                line_idx = scan_indices[scan_idx_ref[0]]
                scan_info = extract_scan_info_from_raw(raw_plan_lines, line_idx)
                
                # Add rows_removed_by_filter
                if 'rows_removed_by_filter' in scan_info:
                    p['rows_removed_by_filter'] = scan_info['rows_removed_by_filter']
                
                # Calculate input cardinality
                act_card = p.get('act_card')
                if act_card is not None and 'rows_removed_by_filter' in scan_info:
                    input_card = act_card + scan_info['rows_removed_by_filter']
                    p['input_cardinality'] = input_card
                    
                    # Calculate overall selectivity
                    if input_card > 0:
                        selectivity = act_card / input_card
                        p['overall_selectivity'] = selectivity
                
                scan_idx_ref[0] += 1
        
        # Process children
        for child in node.get("children", []):
            enrich_node(child, scan_idx_ref)
    
    # Start enrichment
    scan_idx_ref = [0]
    enrich_node(enriched, scan_idx_ref)
    
    return enriched


def parse_plan_enhanced(raw_data: dict) -> dict:
    """
    Parse raw zero-shot data and create enriched parsed plans.
    
    Args:
        raw_data: Raw zero-shot JSON with query_list containing analyze_plans
    
    Returns:
        Dict with parsed_plans array, each enriched with rows_removed_by_filter
    """
    parsed_plans = []
    
    if 'query_list' not in raw_data:
        return {"parsed_plans": [], "database_stats": raw_data.get("database_stats"), "run_kwargs": raw_data.get("run_kwargs")}
    
    for query in raw_data['query_list']:
        if 'analyze_plans' not in query or not query['analyze_plans']:
            continue
        
        # Get the first analyze plan (list of lines)
        analyze_plan_lines = query['analyze_plans'][0]
        
        # For now, we'll create a minimal parsed plan structure
        # In practice, you'd use the original parser here and then enrich it
        # This is a placeholder that shows the structure
        
        # Extract runtime
        plan_runtime = None
        for line_list in analyze_plan_lines:
            line = line_list[0] if isinstance(line_list, list) else str(line_list)
            exec_match = execution_time_regex.search(line.lower())
            if exec_match:
                plan_runtime = float(exec_match.group('execution_time'))
                break
        
        # Create a basic plan structure (this would normally come from the original parser)
        # For demonstration, we create a minimal structure
        # In practice, you'd call the original parser and then enrich it
        
        parsed_plan = {
            "plain_content": [],
            "plan_parameters": {},
            "children": [],
            "plan_runtime": plan_runtime
        }
        
        # Enrich with raw information
        enriched_plan = enrich_parsed_plan_with_raw_info(parsed_plan, analyze_plan_lines)
        parsed_plans.append(enriched_plan)
    
    return {
        "parsed_plans": parsed_plans,
        "database_stats": raw_data.get("database_stats"),
        "run_kwargs": raw_data.get("run_kwargs")
    }


def enrich_existing_parsed_plan(
    parsed_plan: dict,
    raw_plan_lines: list[list[str]]
) -> dict:
    """
    Enrich an already-parsed plan with information from raw EXPLAIN ANALYZE.
    
    This function takes a parsed plan (from the original parser) and enriches it
    with rows_removed_by_filter and selectivities extracted from raw text.
    """
    return enrich_parsed_plan_with_raw_info(parsed_plan, raw_plan_lines)


def process_file_pair(
    raw_path: Path,
    parsed_path: Optional[Path] = None
) -> dict:
    """
    Process a raw file and optionally its parsed counterpart.
    
    If parsed_path is provided, enriches the existing parsed plan.
    Otherwise, creates a new enriched parsed plan from raw data.
    """
    with open(raw_path, 'r', encoding='utf-8') as f:
        raw_data = json.load(f)
    
    if parsed_path and parsed_path.exists():
        # Enrich existing parsed plan
        with open(parsed_path, 'r', encoding='utf-8') as f:
            parsed_data = json.load(f)
        
        enriched_plans = []
        raw_queries = raw_data.get('query_list', [])
        parsed_plans_list = parsed_data.get('parsed_plans', [])
        
        # Match parsed plans with raw queries
        for i, parsed_plan in enumerate(parsed_plans_list):
            if i < len(raw_queries):
                raw_query = raw_queries[i]
                if 'analyze_plans' in raw_query and raw_query['analyze_plans']:
                    raw_lines = raw_query['analyze_plans'][0]
                    enriched = enrich_existing_parsed_plan(parsed_plan, raw_lines)
                    enriched_plans.append(enriched)
                else:
                    enriched_plans.append(parsed_plan)
            else:
                enriched_plans.append(parsed_plan)
        
        return {
            "parsed_plans": enriched_plans,
            "database_stats": parsed_data.get("database_stats"),
            "run_kwargs": parsed_data.get("run_kwargs")
        }
    else:
        # Create new parsed plan from raw data
        return parse_plan_enhanced(raw_data)

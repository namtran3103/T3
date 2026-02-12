"""
Batch process raw and parsed zero-shot files to create enriched parsed plans.

This script:
1. Reads raw zero-shot JSON files
2. Reads corresponding parsed zero-shot JSON files
3. Enriches parsed plans with rows_removed_by_filter and selectivities
4. Writes enriched plans to output directory

Usage:
    python -m src.zeroshot.process_enriched_plans \
        --raw-dir /path/to/raw \
        --parsed-dir /path/to/parsed_plans \
        --output-dir data/zero-shot-data/parsed_new
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

from src.zeroshot.enrich_parsed_plans import enrich_file_pair


def find_matching_files(raw_dir: Path, parsed_dir: Path) -> list[tuple[Path, Path]]:
    """
    Find matching raw and parsed files.
    
    Returns:
        List of (raw_path, parsed_path) tuples
    """
    matches = []
    
    # Get all JSON files in parsed directory
    parsed_files = list(parsed_dir.rglob("*.json"))
    
    for parsed_file in parsed_files:
        # Try to find corresponding raw file
        # Relative path from parsed_dir
        rel_path = parsed_file.relative_to(parsed_dir)
        
        # Look for corresponding raw file
        raw_file = raw_dir / rel_path
        
        if raw_file.exists():
            matches.append((raw_file, parsed_file))
        else:
            # Try alternative: same filename in raw_dir
            alt_raw = raw_dir / parsed_file.name
            if alt_raw.exists():
                matches.append((alt_raw, parsed_file))
    
    return matches


def process_directory(
    raw_dir: Path,
    parsed_dir: Path,
    output_dir: Path,
    dry_run: bool = False
) -> None:
    """
    Process all matching files in directories.
    
    Args:
        raw_dir: Directory containing raw zero-shot JSON files
        parsed_dir: Directory containing parsed zero-shot JSON files
        output_dir: Directory to write enriched parsed plans
        dry_run: If True, only print what would be done without writing files
    """
    matches = find_matching_files(raw_dir, parsed_dir)
    
    print(f"Found {len(matches)} matching file pairs")
    
    if dry_run:
        print("\nDry run - would process:")
        for raw_path, parsed_path in matches[:5]:
            rel_path = parsed_path.relative_to(parsed_dir)
            output_path = output_dir / rel_path
            print(f"  {raw_path.name} + {parsed_path.name} -> {output_path}")
        if len(matches) > 5:
            print(f"  ... and {len(matches) - 5} more")
        return
    
    # Process each pair
    for i, (raw_path, parsed_path) in enumerate(matches, 1):
        rel_path = parsed_path.relative_to(parsed_dir)
        output_path = output_dir / rel_path
        
        print(f"[{i}/{len(matches)}] Processing {rel_path}")
        
        try:
            enrich_file_pair(raw_path, parsed_path, output_path)
        except Exception as e:
            print(f"  ERROR: Failed to process {rel_path}: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\nCompleted processing {len(matches)} file pairs")
    print(f"Output written to {output_dir}")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Batch process zero-shot files to create enriched parsed plans"
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        required=True,
        help="Directory containing raw zero-shot JSON files"
    )
    parser.add_argument(
        "--parsed-dir",
        type=Path,
        required=True,
        help="Directory containing parsed zero-shot JSON files"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/zero-shot-data/parsed_new"),
        help="Directory to write enriched parsed plans (default: data/zero-shot-data/parsed_new)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be processed without actually writing files"
    )
    
    args = parser.parse_args()
    
    if not args.raw_dir.exists():
        print(f"ERROR: Raw directory does not exist: {args.raw_dir}")
        return
    
    if not args.parsed_dir.exists():
        print(f"ERROR: Parsed directory does not exist: {args.parsed_dir}")
        return
    
    process_directory(
        args.raw_dir,
        args.parsed_dir,
        args.output_dir,
        dry_run=args.dry_run
    )


if __name__ == "__main__":
    main()

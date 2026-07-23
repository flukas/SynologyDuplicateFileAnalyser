"""Command-line entry point that orchestrates the duplicate-folder analysis.

Pipeline:
    1. Configure logging.
    2. Read and parse the Synology duplicate-file CSV report.
    3. Analyze folder groups and compact nested folders.
    4. Optionally back up and inject results into the storage report HTML.

"Latest CSV" resolution: if ``--csv`` points to a directory, the newest
``*.csv`` file in it (by modification time) is used. If it points to a file,
that file is used directly.
"""
import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

try:
    from src.folder_analyzer import FolderAnalyzer
    from src.html_manager import HTMLManager
    from src.utils import setup_logging
except ImportError:  # pragma: no cover - fallback when run from within src/
    from folder_analyzer import FolderAnalyzer
    from html_manager import HTMLManager
    from utils import setup_logging

DEFAULT_MIN_SIZE = 50_000_000


def resolve_csv_path(csv_path: Path) -> Path:
    """Resolve a CSV path, selecting the newest ``*.csv`` from a directory.

    Args:
        csv_path: A CSV file, or a directory containing CSV reports.

    Returns:
        Path to the CSV file to process.

    Raises:
        FileNotFoundError: If the path does not exist or a directory has no CSV.
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV path not found: {csv_path}")
    if csv_path.is_dir():
        candidates = sorted(
            csv_path.glob("*.csv"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not candidates:
            raise FileNotFoundError(f"No CSV files found in directory: {csv_path}")
        return candidates[0]
    return csv_path


def parse_arguments(argv: Optional[list] = None) -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Analyze a Synology duplicate-file report and report "
        "folder groups by reclaimable space."
    )
    parser.add_argument(
        "--csv",
        dest="csv_path",
        type=Path,
        required=True,
        help="Path to the duplicate-file CSV report, or a directory "
        "containing reports (newest is used).",
    )
    parser.add_argument(
        "--html",
        dest="html_path",
        type=Path,
        default=None,
        help="Optional path to the Synology storage report HTML to update.",
    )
    parser.add_argument(
        "--log",
        dest="log_path",
        type=Path,
        default=None,
        help="Optional path for the log file.",
    )
    parser.add_argument(
        "--min-size",
        dest="min_size",
        type=int,
        default=DEFAULT_MIN_SIZE,
        help="Minimum reclaimable (wasted) space in bytes for a folder group "
        f"to be reported (default {DEFAULT_MIN_SIZE}).",
    )
    return parser.parse_args(argv)


def main(csv_path: Optional[Path] = None,
         html_path: Optional[Path] = None,
         log_path: Optional[Path] = None,
         min_size: int = DEFAULT_MIN_SIZE) -> int:
    """Run the analysis pipeline.

    If ``csv_path`` is not provided, arguments are read from the command line.

    Returns:
        0 on success, non-zero on error.
    """
    if csv_path is None:
        args = parse_arguments()
        csv_path = args.csv_path
        html_path = args.html_path
        log_path = args.log_path
        min_size = args.min_size

    logger = setup_logging(log_path) if log_path else logging.getLogger(__name__)

    try:
        resolved_csv = resolve_csv_path(Path(csv_path))
        analyzer = FolderAnalyzer(min_group_size=min_size, logger=logger)
        files = analyzer.read_duplicate_report(resolved_csv)
        groups = analyzer.analyze_folder_groups(files)
        groups = analyzer.compact_nested_folders(groups)

        if html_path is not None:
            manager = HTMLManager(Path(html_path))
            manager.backup_report()
            manager.inject_results(groups)
    except (FileNotFoundError, ValueError, PermissionError, OSError) as exc:
        logger.error("Analysis failed: %s", exc)
        return 1

    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

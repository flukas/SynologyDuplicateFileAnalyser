# Duplicate Folder Analysis - Technical Specification

## Overview
This document outlines the specification for developing a tool to analyze Synology NAS duplicate file reports. The tool identifies folders containing duplicate files and calculates shared storage metrics between folder groups, considering all folder levels and partial overlaps. Results are integrated into the existing Synology storage report HTML.

### Delivery Phases
- **Phase 1 (current focus): Analysis core.** CSV parsing, full-path folder
  grouping, overlap handling, size/wasted-space calculation, nested-folder
  compaction, and the supporting CLI plumbing. This is the priority.
- **Phase 2 (deferred): HTML integration.** `html_manager.py` injection into
  the Synology report and the scheduler wiring. Deferred until the analysis
  core is correct and fully tested.

### Key Design Decisions
1. **Granularity — full path, all directory levels.** A "folder" is the full
   directory path containing a file (e.g. `/volume1/photos/vacation/2020`).
   Grouping and overlap detection consider every ancestor level, not just the
   top-level Synology share name.
2. **Threshold basis — wasted (reclaimable) space.** The minimum-size filter
   applies to reclaimable space (redundant copies), i.e. what the user could
   actually delete, not to total shared size.
3. **Malformed rows — log and skip.** A single invalid CSV row is logged and
   skipped; processing continues. A malformed row must not abort the run.
4. **Single CSV parsing path.** CSV parsing lives in one place
   (`utils.parse_csv_line`); `folder_analyzer` consumes it rather than
   re-implementing parsing.

## Requirements

### Functional Requirements
- Process Synology's duplicate file report CSV
- Group duplicate files by folders at all hierarchy levels (full directory
  path, every ancestor level)
- Calculate total shared storage between folder groups
- Handle partial folder overlaps (folders that share some but not all content)
- Filter results by minimum **wasted (reclaimable) space** (50MB default,
  configurable)
- Sort results by wasted space (descending)
- Show total shared size and total wasted space per folder group
- Log and skip malformed rows; never abort a run on a single bad row
- **(Phase 2)** Inject results into existing HTML report
- **(Phase 2)** Run automatically via Synology scheduler

### Technical Requirements
- Use Python virtual environment for isolation
- Minimize external dependencies
- Support Unicode paths in CSVs
- Handle ~5000 files efficiently
- Maintain existing HTML report styling
- Log only errors
- Process only latest CSV report

## Input Format

### CSV Structure
```
Group,Shared Folder,File,Size(Byte),Modified Time
1,"SORT","/volume1/SORT/SG-1T/users/path/file.JPG",1731859,"2010/03/07 12:17:14"
1,"photo","/volume1/photo/other/path/file.JPG",1731859,"2010/03/07 12:17:14"
```

Key characteristics:
- Quoted fields for paths
- Unix-style paths with /volume1/ prefix
- Group ID links duplicate files together
- File sizes in bytes
- Timestamp in YYYY/MM/DD HH:MM:SS format

## Architecture

### Project Structure
```
/duplicate-folder-analyzer/
├── .venv/                  # Virtual environment
├── src/
│   ├── main.py            # Entry point / CLI (Phase 2)
│   ├── folder_analyzer.py # Core analysis (Phase 1)
│   ├── html_manager.py    # HTML handling, stdlib only (Phase 2)
│   └── utils.py           # Shared utilities (Phase 1)
├── tests/
│   ├── requirements.txt   # Test dependencies (pytest)
│   └── test_*.py
├── setup.py               # Packaging; extras_require['test']
└── run_analyzer.sh        # Shell script with venv (Phase 2)
```

### Dependencies
Minimal external dependencies.

Runtime: **none** — standard library only, for both the analysis core and
HTML integration. HTML injection uses ``html.parser`` from the standard
library to locate the anchor element and performs a targeted string insert,
avoiding any third-party parser dependency on the NAS.

Development / test:
```
pytest>=7.4.3
```

Runtime dependencies belong in `requirements.txt`; test-only dependencies
belong in `tests/requirements.txt` (or an extras group). `setup.py`
`install_requires` must not list `pytest`.

### Core Data Structures

```python
@dataclass
class DuplicateFile:
    """
    Represents a single duplicate file from the report.
    
    Attributes:
        group_id: Identifier linking duplicate files together
        folder: Full directory path containing the file
                (e.g. '/volume1/photos/vacation/2020')
        path: Full path to the file
        size: File size in bytes
    """
    group_id: str
    folder: str
    path: str
    size: int

@dataclass
class FolderGroup:
    """
    Represents a group of folders containing duplicate files.

    A folder group links folders that share duplicate content. Folders are
    identified by full directory path. Overlap is evaluated across all
    hierarchy levels, so a group may contain folders at differing depths
    that share content (partial overlap).

    Attributes:
        folders: Set of full folder paths containing shared duplicates
        shared_files: Dict mapping group_ids to DuplicateFile objects
        total_shared_size: Total size in bytes counting one copy per
                           duplicate group
        wasted_space: Total reclaimable size of redundant copies
                      (sum over groups of size * (copies - 1)).
                      This is the value the minimum-size filter applies to.
    """
    folders: Set[str]
    shared_files: Dict[str, List[DuplicateFile]]
    total_shared_size: int
    wasted_space: int
```

## Module Specifications

### utils.py
Core utilities for file handling and logging.

```python
def setup_logging(log_path: Path) -> logging.Logger:
    """
    Configure logging for the application.
    
    Args:
        log_path: Path where log file should be created
    
    Returns:
        Configured logger instance
    
    Raises:
        PermissionError: If log file cannot be created or written to
    """

def parse_csv_line(line: str) -> Tuple[str, str, str, int, str]:
    """
    Parse a single line from the duplicate files CSV report.
    Handles quoted fields and UTF-8 encoding.
    
    Args:
        line: Raw CSV line string
    
    Returns:
        Tuple containing (group_id, folder, file_path, size, modified_time)
    
    Raises:
        ValueError: If line format is invalid or required fields are missing
    """

def extract_folder_name(path: str) -> str:
    """
    Extract the top-level Synology share name from a full file path.
    Example: '/volume1/photos/vacation/img.jpg' -> 'photos'

    Note: This returns only the top-level share. Grouping/overlap analysis
    uses the full containing-directory path (see containing_directory), not
    this value. Retained for display/labelling and share-level rollups.

    Args:
        path: Full file path from CSV

    Returns:
        Name of the shared folder

    Raises:
        ValueError: If path format is invalid or shared folder cannot be determined
    """

def containing_directory(path: str) -> str:
    """
    Return the full directory path that contains a file.
    Example: '/volume1/photos/vacation/img.jpg'
             -> '/volume1/photos/vacation'

    This is the value stored in DuplicateFile.folder and used for
    full-hierarchy grouping and overlap detection.

    Args:
        path: Full file path from CSV

    Returns:
        Full path of the containing directory

    Raises:
        ValueError: If path format is invalid
    """
```

### folder_analyzer.py

```python
class FolderAnalyzer:
    """Analyzes duplicate files to find folder relationships."""
    
    def __init__(self, min_group_size: int = 50_000_000):
        """
        Initialize analyzer with minimum group size threshold.
        
        Args:
            min_group_size: Minimum total shared size in bytes (default 50MB)
        """
    
    def read_duplicate_report(self, csv_path: Path) -> List[DuplicateFile]:
        """
        Read and parse the duplicate files report CSV.

        Uses utils.parse_csv_line for parsing (single parsing path).
        DuplicateFile.folder is set to the containing directory of each file
        (utils.containing_directory), not the top-level share.

        Malformed rows are logged and skipped; a single bad row must not
        abort the run.

        Args:
            csv_path: Path to the duplicate files CSV report
            
        Returns:
            List of DuplicateFile objects for all valid rows in the report
            
        Raises:
            FileNotFoundError: If CSV file doesn't exist
            ValueError: If the CSV header is missing or does not match the
                        expected schema (structural error, not a row error)
        """
    
    def analyze_folder_groups(self, files: List[DuplicateFile]) -> List[FolderGroup]:
        """
        Analyze duplicate files to identify folder groups with shared content.

        Grouping considers folders at all hierarchy levels (full directory
        paths) and handles partial overlaps between folders.

        Results are sorted by wasted_space in descending order.
        Only includes groups whose wasted_space meets or exceeds
        min_group_size (the threshold applies to reclaimable space).

        Args:
            files: List of DuplicateFile objects from the report
            
        Returns:
            List of FolderGroup objects sorted by wasted_space (descending)
        """
    
    def compact_nested_folders(self, groups: List[FolderGroup]) -> List[FolderGroup]:
        """
        Combine groups whose folders are nested within one another.

        When a child folder (e.g. '/volume1/photos/vacation') is nested under
        a parent folder (e.g. '/volume1/photos') that participates in the same
        sharing relationship, the child is collapsed into the parent so each
        relationship is reported once at the highest meaningful level.
        Sizes are combined without double-counting a duplicate group that
        appears in both the parent and child.

        Does not mutate the input list.

        Args:
            groups: List of FolderGroup objects
            
        Returns:
            New compacted list, sorted by wasted_space (descending)
        """
```

### html_manager.py

> **Phase 2.** HTML integration. Implemented with the standard library only
> (``html.parser`` to locate the injection anchor; targeted string insert to
> add the section). No third-party HTML parser dependency.

```python
class HTMLManager:
    """Manages integration of analysis results into the Synology storage report HTML."""
    
    def __init__(self, html_path: Path):
        """
        Initialize HTML manager.
        
        Args:
            html_path: Path to the storage report HTML file
            
        Raises:
            FileNotFoundError: If HTML file doesn't exist
        """
    
    def backup_report(self) -> Path:
        """
        Create backup of original HTML report.
        
        Returns:
            Path to backup file
            
        Raises:
            PermissionError: If backup cannot be created
        """
    
    def inject_results(self, results: List[FolderGroup]) -> None:
        """
        Inject folder analysis results into the HTML report.

        Locates the ``#duplicate_file_overview`` anchor and inserts a new
        ``#folder_similarity_overview`` section immediately after it (before
        ``#title_large_file`` when present). The operation is idempotent: an
        existing injected section is replaced rather than duplicated. Content
        is HTML-escaped to avoid markup/script injection from folder paths.

        Args:
            results: List of FolderGroup objects to be displayed
            
        Raises:
            ValueError: If required HTML structure elements are not found
            IOError: If HTML file cannot be written
        """
```

### main.py

```python
def parse_arguments() -> argparse.Namespace:
    """
    Parse command line arguments.
    
    Returns:
        Namespace containing:
            csv_path: Path to duplicate files CSV
            html_path: Path to storage report HTML
            log_path: Path for log file
            min_size: Minimum group size threshold in bytes
    """

def main(csv_path: Optional[Path] = None, 
         html_path: Optional[Path] = None,
         log_path: Optional[Path] = None,
         min_size: int = 50_000_000) -> int:
    """
    Main entry point for folder duplicate analysis.
    
    Args:
        csv_path: Path to duplicate files CSV (optional)
        html_path: Path to storage report HTML (optional)
        log_path: Path for log file (optional)
        min_size: Minimum group size threshold in bytes (default 50MB)
        
    Returns:
        0 on success, non-zero on error
        
    If paths are not provided, uses command line arguments.
    """
```

## Shell Script (run_analyzer.sh)

Runs the analysis inside an isolated virtualenv (interpreter isolation only;
no third-party runtime dependencies). CSV/HTML paths and the threshold are
configurable at the top of the script or via environment variables. `CSV_PATH`
may be a single report file or a directory (newest `*.csv` is used). Logging is
error-only; the redirect captures any uncaught output as a safety net.

```bash
#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
VENV_DIR="${VENV_DIR:-$SCRIPT_DIR/.venv}"
LOG_FILE="${LOG_FILE:-$SCRIPT_DIR/analyzer.log}"

CSV_PATH="${CSV_PATH:-/volume1/path/to/duplicate_report}"
HTML_PATH="${HTML_PATH:-}"            # optional; empty skips HTML injection
MIN_SIZE="${MIN_SIZE:-50000000}"

if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
    "$VENV_DIR/bin/pip" install --upgrade pip
    "$VENV_DIR/bin/pip" install -r "$SCRIPT_DIR/requirements.txt"
fi

ARGS=(--csv "$CSV_PATH" --log "$LOG_FILE" --min-size "$MIN_SIZE")
if [ -n "$HTML_PATH" ]; then
    ARGS+=(--html "$HTML_PATH")
fi

"$VENV_DIR/bin/python" "$SCRIPT_DIR/src/main.py" "${ARGS[@]}" >> "$LOG_FILE" 2>&1
```

## Development Sequence

1. Core Utilities (utils.py)
   - CSV parsing
   - Path manipulation
   - Error-only logging setup
   - Unit tests

2. Analysis Logic (folder_analyzer.py)
   - CSV file reading
   - Folder grouping with overlap handling
   - Size calculations
   - Nested folder compaction
   - Unit tests

3. HTML Integration (html_manager.py)
   - HTML parsing
   - Results formatting
   - Section injection matching existing style
   - Unit tests

4. Integration (main.py + shell script)
   - Command line interface
   - Process orchestration
   - Error handling
   - Integration tests

## Testing Requirements

### Unit Test Coverage
- CSV parsing and validation
- Path manipulation
- Folder group analysis calculations
- Partial overlap handling
- Nested folder compaction
- HTML parsing and injection
- Error handling

### Test Data Requirements
- Sample CSV with multiple duplicate groups
- Sample HTML report structure
- Various folder hierarchies including:
  - Nested folders
  - Partial overlaps
  - Multiple folders per group
- Different file sizes
- Unicode paths

## Error Handling

### Critical Scenarios
- Missing CSV file (raise; run cannot proceed)
- Missing or mismatched CSV header (raise; structural error)
- Individual malformed CSV row (log and skip; continue processing)
- HTML structure not matching expected format (Phase 2)
- Permission issues with files
- Virtual environment setup failures

### Error Response Requirements
- Log errors (including each skipped malformed row); avoid verbose
  per-record processing chatter
- Create HTML backup before modification (Phase 2)
- Return non-zero exit codes for failures
- Provide clear error messages

## HTML Integration Details

### Injection Point
- After `<div id="duplicate_file_overview">`
- Before `<div id="title_large_file">`
- Use existing CSS classes and styling

### Required HTML Structure
```html
<div id="folder_similarity_overview" class="table_container">
    <div id="title_folder_similarity" class="title_text">
        Folder Similarity Analysis
    </div>
    <script>
        // JavaScript data structure matching report format
        // Must support same filtering and display options
    </script>
</div>
```

## Implementation Notes

- Handle all folder hierarchy levels
- Support partial folder overlaps
- Compact nested folders with same content
- Show full paths in results
- Sort by wasted (reclaimable) space, descending
- Filter by minimum wasted (reclaimable) space
- No minimum file count requirement
- No file type categorization needed
- Include total shared size and total wasted space per group
- Match existing HTML report functionality (Phase 2)
- Handle any number of folders per group

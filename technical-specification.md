# Duplicate Folder Analysis - Technical Specification

## Overview
This document outlines the specification for developing a tool to analyze Synology NAS duplicate file reports. The tool identifies folders containing duplicate files and calculates shared storage metrics between folder groups, considering all folder levels and partial overlaps. Results are integrated into the existing Synology storage report HTML.

## Requirements

### Functional Requirements
- Process Synology's duplicate file report CSV
- Group duplicate files by folders at all hierarchy levels
- Calculate total shared storage between folder groups
- Handle partial folder overlaps
- Filter results by minimum total size (50MB default, configurable)
- Sort results by total shared storage size
- Show total wasted space per folder group
- Inject results into existing HTML report
- Run automatically via Synology scheduler

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
├── venv/                   # Virtual environment
├── src/
│   ├── main.py            # Entry point
│   ├── folder_analyzer.py # Core analysis
│   ├── html_manager.py    # HTML handling
│   └── utils.py          # Shared utilities
├── requirements.txt       # Dependencies
└── run_analyzer.sh       # Shell script with venv
```

### Dependencies
Minimal external dependencies:
```
beautifulsoup4==4.12.2  # HTML parsing only
```

### Core Data Structures

```python
@dataclass
class DuplicateFile:
    """
    Represents a single duplicate file from the report.
    
    Attributes:
        group_id: Identifier linking duplicate files together
        folder: Full path to containing folder
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
    
    Attributes:
        folders: Set of folder paths containing duplicates
        shared_files: Dict mapping group_ids to DuplicateFile objects
        total_shared_size: Total size in bytes of shared duplicate files
        wasted_space: Total size of redundant copies
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
    Extract the shared folder name from a full file path.
    Example: '/volume1/photos/vacation/img.jpg' -> 'photos'
    
    Args:
        path: Full file path from CSV
    
    Returns:
        Name of the shared folder
    
    Raises:
        ValueError: If path format is invalid or shared folder cannot be determined
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
        
        Args:
            csv_path: Path to the duplicate files CSV report
            
        Returns:
            List of DuplicateFile objects representing all files in report
            
        Raises:
            FileNotFoundError: If CSV file doesn't exist
            ValueError: If CSV format is invalid
        """
    
    def analyze_folder_groups(self, files: List[DuplicateFile]) -> List[FolderGroup]:
        """
        Analyze duplicate files to identify folder groups with shared content.
        Handles partial overlaps between folders.
        Results are sorted by total_shared_size in descending order.
        Only includes groups exceeding min_group_size threshold.
        
        Args:
            files: List of DuplicateFile objects from the report
            
        Returns:
            List of FolderGroup objects sorted by total_shared_size
        """
    
    def compact_nested_folders(self, groups: List[FolderGroup]) -> List[FolderGroup]:
        """
        Combine groups where folders are nested within each other.
        
        Args:
            groups: List of FolderGroup objects
            
        Returns:
            Compacted list with nested folders combined
        """
```

### html_manager.py

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
        Matches existing report's data display and filtering capabilities.
        Adds new section after duplicate files list and before large files.
        
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

```bash
#!/bin/bash
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
VENV_DIR="$SCRIPT_DIR/venv"
LOG_FILE="$SCRIPT_DIR/analyzer.log"

# Create virtual environment if needed
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
    "$VENV_DIR/bin/pip" install -r "$SCRIPT_DIR/requirements.txt"
fi

echo "Starting analysis $(date)" >> "$LOG_FILE"
"$VENV_DIR/bin/python" "$SCRIPT_DIR/src/main.py" >> "$LOG_FILE" 2>&1
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
- Missing or corrupt CSV file
- Invalid CSV format
- HTML structure not matching expected format
- Permission issues with files
- Virtual environment setup failures

### Error Response Requirements
- Log only errors (no processing details)
- Create HTML backup before modification
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
- Sort by total shared size only
- No minimum file count requirement
- No file type categorization needed
- Include total wasted space calculations
- Match existing HTML report functionality
- Handle any number of folders per group

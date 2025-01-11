# src/utils.py
from typing import Tuple, Optional
from pathlib import Path
import logging
import csv
import re

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
    try:
        # Ensure parent directory exists
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create logger
        logger = logging.getLogger('file_deduplication')
        logger.setLevel(logging.INFO)
        
        # Create handlers
        file_handler = logging.FileHandler(log_path, encoding='utf-8')
        stream_handler = logging.StreamHandler()
        
        # Create formatter
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        stream_handler.setFormatter(formatter)
        
        # Add handlers to logger
        logger.addHandler(file_handler)
        logger.addHandler(stream_handler)
        
        return logger
        
    except (OSError, PermissionError) as e:
        raise PermissionError(f"Cannot create or write to log file: {e}")

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
    try:
        # Use csv module to handle quoted fields correctly
        reader = csv.reader([line.strip()], quotechar='"', delimiter=',')
        fields = next(reader)
        
        if len(fields) != 5:
            raise ValueError(f"Expected 5 fields, got {len(fields)}")
        
        group_id, folder, file_path, size_str, modified = fields
        
        # Validate and convert size to int
        try:
            size = int(size_str)
        except ValueError:
            raise ValueError(f"Invalid size value: {size_str}")
            
        # Basic validation of other fields
        if not all([group_id, folder, file_path, modified]):
            raise ValueError("All fields must be non-empty")
            
        return group_id, folder, file_path, size, modified
        
    except (csv.Error, IndexError) as e:
        raise ValueError(f"Invalid CSV line format: {e}")

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
    # Match pattern /volume1/folder_name/...
    pattern = r'^/volume1/([^/]+)/'
    match = re.match(pattern, path)
    
    if not match:
        raise ValueError(
            f"Invalid path format: {path}. Expected /volume1/folder_name/..."
        )
    
    return match.group(1)
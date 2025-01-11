import pytest
from pathlib import Path
from typing import List
import tempfile
import csv
import os

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from src.folder_analyzer import FolderAnalyzer, DuplicateFile, FolderGroup

@pytest.fixture
def analyzer():
    """Fixture providing a FolderAnalyzer instance."""
    return FolderAnalyzer()

@pytest.fixture
def temp_dir():
    """Fixture providing a temporary directory."""
    with tempfile.TemporaryDirectory() as tmpdirname:
        yield Path(tmpdirname)

@pytest.fixture
def csv_path(temp_dir):
    """Fixture providing a temporary CSV file path."""
    return temp_dir / "test_duplicates.csv"

def create_test_csv(csv_path: Path, content: List[List[str]]) -> None:
    """Helper function to create a test CSV file with specified content."""
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerows(content)

def test_read_duplicate_report_valid(analyzer, csv_path):
    """Test reading a valid duplicate report CSV."""
    test_data = [
        ["Group", "Shared Folder", "File", "Size(Byte)", "Modified Time"],
        ["1", "photos", "/volume1/photos/vacation/img1.jpg", "1000", "2024/01/01 12:00:00"],
        ["1", "backup", "/volume1/backup/pictures/img1.jpg", "1000", "2024/01/01 12:00:00"]
    ]
    create_test_csv(csv_path, test_data)

    result = analyzer.read_duplicate_report(csv_path)

    assert len(result) == 2
    assert result[0].group_id == "1"
    assert result[0].folder == "photos"
    assert result[0].size == 1000

def test_read_duplicate_report_missing_file(analyzer):
    """Test reading a non-existent CSV file."""
    with pytest.raises(FileNotFoundError):
        analyzer.read_duplicate_report(Path("nonexistent.csv"))

def test_read_duplicate_report_invalid_format(analyzer, csv_path):
    """Test reading a CSV with invalid format."""
    test_data = [
        ["Invalid", "Header", "Format"],
        ["1", "photos", "/volume1/photos/img.jpg"]
    ]
    create_test_csv(csv_path, test_data)

    with pytest.raises(ValueError):
        analyzer.read_duplicate_report(csv_path)

def test_analyze_folder_groups_basic(analyzer):
    """Test basic folder group analysis with simple duplicates."""
    files = [
        DuplicateFile("1", "photos", "/volume1/photos/img1.jpg", 1000),
        DuplicateFile("1", "backup", "/volume1/backup/img1.jpg", 1000),
        DuplicateFile("2", "photos", "/volume1/photos/img2.jpg", 2000),
        DuplicateFile("2", "backup", "/volume1/backup/img2.jpg", 2000)
    ]

    results = analyzer.analyze_folder_groups(files)

    assert len(results) == 1
    assert results[0].total_shared_size == 3000
    assert results[0].wasted_space == 3000
    assert results[0].folders == {"photos", "backup"}

def test_analyze_folder_groups_threshold():
    """Test minimum size threshold filtering."""
    analyzer = FolderAnalyzer(min_group_size=1500)
    files = [
        DuplicateFile("1", "photos", "/volume1/photos/small.jpg", 1000),
        DuplicateFile("1", "backup", "/volume1/backup/small.jpg", 1000),
        DuplicateFile("2", "photos", "/volume1/photos/large.jpg", 2000),
        DuplicateFile("2", "backup", "/volume1/backup/large.jpg", 2000)
    ]

    results = analyzer.analyze_folder_groups(files)

    assert len(results) == 1
    assert results[0].total_shared_size == 2000

def test_analyze_folder_groups_partial_overlap(analyzer):
    """Test handling of partial folder overlaps."""
    files = [
        DuplicateFile("1", "photos", "/volume1/photos/img1.jpg", 1000),
        DuplicateFile("1", "backup", "/volume1/backup/img1.jpg", 1000),
        DuplicateFile("2", "photos", "/volume1/photos/img2.jpg", 2000),
        DuplicateFile("2", "documents", "/volume1/documents/img2.jpg", 2000)
    ]

    results = analyzer.analyze_folder_groups(files)

    assert len(results) == 2
    folders_sets = [group.folders for group in results]
    assert {"photos", "backup"} in folders_sets
    assert {"photos", "documents"} in folders_sets

def test_compact_nested_folders(analyzer):
    """Test combining of nested folder groups."""
    groups = [
        FolderGroup(
            folders={"photos/vacation", "backup/photos"},
            shared_files={"1": []},
            total_shared_size=1000,
            wasted_space=1000
        ),
        FolderGroup(
            folders={"photos", "backup"},
            shared_files={"2": []},
            total_shared_size=2000,
            wasted_space=2000
        )
    ]

    results = analyzer.compact_nested_folders(groups)

    assert len(results) == 1
    assert results[0].total_shared_size == 3000
    assert results[0].wasted_space == 3000
    assert results[0].folders == {"photos", "backup"}

def test_unicode_paths(analyzer, csv_path):
    """Test handling of Unicode paths in duplicate files."""
    test_data = [
        ["Group", "Shared Folder", "File", "Size(Byte)", "Modified Time"],
        ["1", "photos", "/volume1/photos/휴가/이미지.jpg", "1000", "2024/01/01 12:00:00"],
        ["1", "backup", "/volume1/backup/휴가/이미지.jpg", "1000", "2024/01/01 12:00:00"]
    ]
    create_test_csv(csv_path, test_data)

    result = analyzer.read_duplicate_report(csv_path)
    assert len(result) == 2
    assert "휴가" in result[0].path

def test_empty_report(analyzer, csv_path):
    """Test handling of empty duplicate report."""
    test_data = [
        ["Group", "Shared Folder", "File", "Size(Byte)", "Modified Time"]
    ]
    create_test_csv(csv_path, test_data)

    result = analyzer.read_duplicate_report(csv_path)
    assert len(result) == 0

    groups = analyzer.analyze_folder_groups(result)
    assert len(groups) == 0

def test_large_file_count(analyzer):
    """Test handling of large number of files."""
    files = []
    for i in range(5000):  # Create 5000 files as per spec
        files.append(
            DuplicateFile(
                str(i % 100),  # 100 groups of duplicates
                f"folder{i % 10}",  # 10 different folders
                f"/volume1/folder{i % 10}/file{i}.jpg",
                1000
            )
        )

    results = analyzer.analyze_folder_groups(files)
    assert len(results) > 0  # Should handle large file count without errors
    assert all(group.total_shared_size >= analyzer.min_group_size for group in results)

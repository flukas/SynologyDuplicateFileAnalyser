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
    assert result[0].folder == "/volume1/photos/vacation"
    assert result[0].size == 1000


def test_read_duplicate_report_skips_malformed_rows(analyzer, csv_path):
    """Malformed rows should be logged and skipped, not abort the run."""
    with open(csv_path, 'w', encoding='utf-8', newline='') as f:
        f.write("Group,Shared Folder,File,Size(Byte),Modified Time\n")
        f.write('1,photos,/volume1/photos/a.jpg,1000,2024/01/01 12:00:00\n')
        f.write('bad,row,onlythree\n')                       # too few fields
        f.write('2,backup,/volume1/backup/b.jpg,notanint,x\n')  # invalid size
        f.write('3,backup,/volume1/backup/c.jpg,3000,2024/01/01 12:00:00\n')
    result = analyzer.read_duplicate_report(csv_path)

    assert len(result) == 2
    assert [f.group_id for f in result] == ["1", "3"]

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

def test_analyze_folder_groups_basic():
    """Test basic folder group analysis with simple duplicates."""
    analyzer = FolderAnalyzer(min_group_size=1)
    files = [
        DuplicateFile("1", "/volume1/photos", "/volume1/photos/img1.jpg", 1000),
        DuplicateFile("1", "/volume1/backup", "/volume1/backup/img1.jpg", 1000),
        DuplicateFile("2", "/volume1/photos", "/volume1/photos/img2.jpg", 2000),
        DuplicateFile("2", "/volume1/backup", "/volume1/backup/img2.jpg", 2000)
    ]

    results = analyzer.analyze_folder_groups(files)

    assert len(results) == 1
    assert results[0].total_shared_size == 3000
    assert results[0].wasted_space == 3000
    assert results[0].folders == {"/volume1/photos", "/volume1/backup"}

def test_analyze_folder_groups_threshold():
    """Test minimum wasted-space threshold filtering across folder groups."""
    analyzer = FolderAnalyzer(min_group_size=1500)
    files = [
        # Group below threshold (wasted 1000)
        DuplicateFile("1", "/volume1/a", "/volume1/a/small.jpg", 1000),
        DuplicateFile("1", "/volume1/b", "/volume1/b/small.jpg", 1000),
        # Group above threshold (wasted 2000)
        DuplicateFile("2", "/volume1/c", "/volume1/c/large.jpg", 2000),
        DuplicateFile("2", "/volume1/d", "/volume1/d/large.jpg", 2000)
    ]

    results = analyzer.analyze_folder_groups(files)

    assert len(results) == 1
    assert results[0].wasted_space == 2000
    assert results[0].folders == {"/volume1/c", "/volume1/d"}

def test_analyze_folder_groups_partial_overlap():
    """Test handling of partial folder overlaps."""
    analyzer = FolderAnalyzer(min_group_size=1)
    files = [
        DuplicateFile("1", "/volume1/photos", "/volume1/photos/img1.jpg", 1000),
        DuplicateFile("1", "/volume1/backup", "/volume1/backup/img1.jpg", 1000),
        DuplicateFile("2", "/volume1/photos", "/volume1/photos/img2.jpg", 2000),
        DuplicateFile("2", "/volume1/documents", "/volume1/documents/img2.jpg", 2000)
    ]

    results = analyzer.analyze_folder_groups(files)

    assert len(results) == 2
    folders_sets = [group.folders for group in results]
    assert {"/volume1/photos", "/volume1/backup"} in folders_sets
    assert {"/volume1/photos", "/volume1/documents"} in folders_sets

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

def test_large_file_count():
    """Test handling of large number of files."""
    analyzer = FolderAnalyzer(min_group_size=1)
    files = []
    for i in range(5000):  # Create 5000 files as per spec
        # 100 duplicate groups; folder index (i % 7) is independent of the
        # group index (i % 100), so groups genuinely span multiple folders.
        files.append(
            DuplicateFile(
                str(i % 100),
                f"/volume1/folder{i % 7}",
                f"/volume1/folder{i % 7}/file{i}.jpg",
                1000
            )
        )

    results = analyzer.analyze_folder_groups(files)
    assert len(results) > 0  # Should handle large file count without errors
    assert all(group.wasted_space >= analyzer.min_group_size for group in results)

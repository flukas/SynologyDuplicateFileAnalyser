# tests/test_utils.py
import pytest
from pathlib import Path
import logging
#from src.utils import setup_logging, parse_csv_line, extract_folder_name

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from src.utils import setup_logging, parse_csv_line, extract_folder_name, containing_directory

def test_parse_csv_line_basic():
    """Test parsing of a basic CSV line without quotes or special characters"""
    line = '1,SORT,/volume1/SORT/test.jpg,1234,2024/01/01 12:00:00\n'
    group, folder, path, size, modified = parse_csv_line(line)
    assert group == '1'
    assert folder == 'SORT'
    assert path == '/volume1/SORT/test.jpg'
    assert size == 1234
    assert modified == '2024/01/01 12:00:00'

def test_parse_csv_line_quoted():
    """Test parsing of CSV line with quoted fields containing commas"""
    line = '1,"SORT","/volume1/SORT/my,file.jpg",1234,"2024/01/01 12:00:00"\n'
    group, folder, path, size, modified = parse_csv_line(line)
    assert group == '1'
    assert folder == 'SORT'
    assert path == '/volume1/SORT/my,file.jpg'
    assert size == 1234
    assert modified == '2024/01/01 12:00:00'

def test_parse_csv_line_unicode():
    """Test parsing of CSV line with Unicode characters"""
    line = '1,SORT,"/volume1/SORT/测试/文件.jpg",1234,"2024/01/01 12:00:00"\n'
    group, folder, path, size, modified = parse_csv_line(line)
    assert path == '/volume1/SORT/测试/文件.jpg'

def test_parse_csv_line_invalid():
    """Test handling of invalid CSV lines"""
    invalid_lines = [
        '',  # Empty line
        '1,SORT\n',  # Too few fields
        '1,SORT,path,size,time,extra\n',  # Too many fields
        '1,SORT,path,invalid,time\n',  # Invalid size
    ]
    for line in invalid_lines:
        with pytest.raises(ValueError):
            parse_csv_line(line)

def test_extract_folder_name_basic():
    """Test basic folder name extraction"""
    assert extract_folder_name('/volume1/photos/test.jpg') == 'photos'
    assert extract_folder_name('/volume1/documents/subfolder/file.txt') == 'documents'

def test_extract_folder_name_special_chars():
    """Test folder extraction with special characters"""
    assert extract_folder_name('/volume1/my photos/test.jpg') == 'my photos'
    assert extract_folder_name('/volume1/测试文件夹/file.txt') == '测试文件夹'

def test_extract_folder_name_invalid():
    """Test handling of invalid paths"""
    invalid_paths = [
        '',  # Empty path
        'invalid',  # No volume
        '/volume1/',  # No folder
        '/volume2/folder',  # Wrong volume
    ]
    for path in invalid_paths:
        with pytest.raises(ValueError):
            extract_folder_name(path)

def test_containing_directory_basic():
    """Full containing directory is returned, preserving all levels"""
    assert containing_directory('/volume1/photos/vacation/img.jpg') == '/volume1/photos/vacation'
    assert containing_directory('/volume1/photos/img.jpg') == '/volume1/photos'
    assert containing_directory('/volume1/测试/文件.jpg') == '/volume1/测试'

def test_containing_directory_invalid():
    """Invalid paths raise ValueError"""
    invalid_paths = [
        '',
        'invalid',
        '/volume1/onlyshare.jpg',  # no directory below the share
        '/volume2/folder/file.jpg',  # wrong volume
    ]
    for path in invalid_paths:
        with pytest.raises(ValueError):
            containing_directory(path)

def test_setup_logging(tmp_path):
    """Test logging setup and file creation"""
    log_path = tmp_path / "test.log"
    logger = setup_logging(log_path)
    
    # Verify log file was created
    assert log_path.exists()

    # Logger is configured for errors only
    assert logger.level == logging.ERROR

    # Test logging (error level, since routine levels are suppressed)
    test_message = "Test log message"
    logger.error(test_message)
        # Flush handlers to ensure content is written
    for handler in logger.handlers:
        handler.flush()
    
    # Verify message was written
    content = log_path.read_text()
    assert test_message in content


def test_setup_logging_suppresses_info(tmp_path):
    """Info-level messages must not be written when logging errors only"""
    log_path = tmp_path / "info.log"
    logger = setup_logging(log_path)
    logger.info("routine detail that should be suppressed")
    for handler in logger.handlers:
        handler.flush()
    assert log_path.read_text() == ""
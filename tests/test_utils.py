# tests/test_utils.py
import pytest
from pathlib import Path
import logging
#from src.utils import setup_logging, parse_csv_line, extract_folder_name

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from src.utils import setup_logging, parse_csv_line, extract_folder_name

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

def test_setup_logging(tmp_path):
    """Test logging setup and file creation"""
    log_path = tmp_path / "test.log"
    setup_logging(log_path)
    
    # Verify log file was created
    assert log_path.exists()
    
    # Test logging
    test_message = "Test log message"
    logging.info(test_message)
    
    # Verify message was written
    content = log_path.read_text()
    assert test_message in content

def test_setup_logging_invalid_path(tmp_path):
    """Test logging setup with invalid path"""
    invalid_path = tmp_path / "nonexistent" / "test.log"
    with pytest.raises(PermissionError):
        setup_logging(invalid_path)
import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).parent.parent))
from src.main import main, resolve_csv_path, parse_arguments

HEADER = "Group,Shared Folder,File,Size(Byte),Modified Time\n"

CSV_CONTENT = (
    HEADER
    + '1,photos,/volume1/photos/a.jpg,60000000,2024/01/01 12:00:00\n'
    + '1,backup,/volume1/backup/a.jpg,60000000,2024/01/01 12:00:00\n'
)

REPORT_HTML = """<html><body>
<div id="duplicate_file_overview">dup</div>
<div id="title_large_file">large</div>
</body></html>
"""


def _write_csv(tmp_path: Path) -> Path:
    csv_path = tmp_path / "dupes.csv"
    csv_path.write_text(CSV_CONTENT, encoding="utf-8")
    return csv_path


def test_resolve_csv_path_file(tmp_path):
    csv_path = _write_csv(tmp_path)
    assert resolve_csv_path(csv_path) == csv_path


def test_resolve_csv_path_directory_picks_newest(tmp_path):
    old = tmp_path / "old.csv"
    new = tmp_path / "new.csv"
    old.write_text(CSV_CONTENT, encoding="utf-8")
    new.write_text(CSV_CONTENT, encoding="utf-8")
    import os
    import time
    old_time = time.time() - 100
    os.utime(old, (old_time, old_time))
    assert resolve_csv_path(tmp_path) == new


def test_resolve_csv_path_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        resolve_csv_path(tmp_path / "nope.csv")


def test_resolve_csv_path_empty_directory(tmp_path):
    with pytest.raises(FileNotFoundError):
        resolve_csv_path(tmp_path)


def test_main_csv_only_success(tmp_path):
    csv_path = _write_csv(tmp_path)
    assert main(csv_path=csv_path) == 0


def test_main_missing_csv_returns_error(tmp_path):
    assert main(csv_path=tmp_path / "missing.csv") == 1


def test_main_full_pipeline_injects_html(tmp_path):
    csv_path = _write_csv(tmp_path)
    html_path = tmp_path / "report.html"
    html_path.write_text(REPORT_HTML, encoding="utf-8")

    rc = main(csv_path=csv_path, html_path=html_path, min_size=1)
    assert rc == 0

    result = html_path.read_text(encoding="utf-8")
    assert 'id="folder_similarity_overview"' in result
    # A backup should have been created alongside the report.
    backups = list(tmp_path.glob("report.html.*.bak"))
    assert len(backups) == 1


def test_parse_arguments_defaults():
    args = parse_arguments(["--csv", "some.csv"])
    assert args.csv_path == Path("some.csv")
    assert args.html_path is None
    assert args.min_size == 50_000_000

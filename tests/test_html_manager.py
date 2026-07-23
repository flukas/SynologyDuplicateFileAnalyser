import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).parent.parent))
from src.html_manager import HTMLManager, _format_size
from src.folder_analyzer import FolderGroup

BASE_HTML = """<html>
<body>
<div id="duplicate_file_overview" class="table_container">
  <div id="dup_inner">nested content</div>
</div>
<div id="title_large_file" class="title_text">Large Files</div>
</body>
</html>
"""

HTML_NO_TITLE = """<html>
<body>
<div id="duplicate_file_overview" class="table_container">dup</div>
</body>
</html>
"""

HTML_NO_ANCHOR = """<html>
<body>
<div id="something_else">nothing here</div>
</body>
</html>
"""


@pytest.fixture
def sample_group():
    return FolderGroup(
        folders={"/volume1/photos/vacation", "/volume1/backup/photos"},
        shared_files={"1": []},
        total_shared_size=3_000_000,
        wasted_space=1_500_000,
    )


def _write(tmp_path: Path, content: str) -> Path:
    html_path = tmp_path / "report.html"
    html_path.write_text(content, encoding="utf-8")
    return html_path


def test_init_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        HTMLManager(tmp_path / "does_not_exist.html")


def test_backup_report_creates_copy(tmp_path):
    html_path = _write(tmp_path, BASE_HTML)
    manager = HTMLManager(html_path)
    backup = manager.backup_report()
    assert backup.exists()
    assert backup.read_text(encoding="utf-8") == BASE_HTML


def test_inject_between_anchor_and_title(tmp_path, sample_group):
    html_path = _write(tmp_path, BASE_HTML)
    manager = HTMLManager(html_path)
    manager.inject_results([sample_group])

    result = html_path.read_text(encoding="utf-8")
    assert 'id="folder_similarity_overview"' in result

    # Injected section must appear after the anchor and before the title.
    dup_pos = result.index('id="duplicate_file_overview"')
    inj_pos = result.index('id="folder_similarity_overview"')
    title_pos = result.index('id="title_large_file"')
    assert dup_pos < inj_pos < title_pos
    # Content rendered and escaped folder paths present
    assert "/volume1/photos/vacation" in result


def test_inject_without_title_appends_after_anchor(tmp_path, sample_group):
    html_path = _write(tmp_path, HTML_NO_TITLE)
    manager = HTMLManager(html_path)
    manager.inject_results([sample_group])

    result = html_path.read_text(encoding="utf-8")
    dup_pos = result.index('id="duplicate_file_overview"')
    inj_pos = result.index('id="folder_similarity_overview"')
    assert dup_pos < inj_pos


def test_inject_missing_anchor_raises(tmp_path, sample_group):
    html_path = _write(tmp_path, HTML_NO_ANCHOR)
    manager = HTMLManager(html_path)
    with pytest.raises(ValueError):
        manager.inject_results([sample_group])


def test_inject_is_idempotent(tmp_path, sample_group):
    html_path = _write(tmp_path, BASE_HTML)
    manager = HTMLManager(html_path)
    manager.inject_results([sample_group])
    manager.inject_results([sample_group])

    result = html_path.read_text(encoding="utf-8")
    assert result.count('id="folder_similarity_overview"') == 1


def test_inject_empty_results(tmp_path):
    html_path = _write(tmp_path, BASE_HTML)
    manager = HTMLManager(html_path)
    manager.inject_results([])

    result = html_path.read_text(encoding="utf-8")
    assert 'id="folder_similarity_overview"' in result
    assert "No folder groups above threshold." in result


def test_inject_escapes_html(tmp_path):
    evil = FolderGroup(
        folders={"/volume1/<script>alert(1)</script>"},
        shared_files={"1": []},
        total_shared_size=1000,
        wasted_space=1000,
    )
    html_path = _write(tmp_path, BASE_HTML)
    HTMLManager(html_path).inject_results([evil])
    result = html_path.read_text(encoding="utf-8")
    assert "<script>alert(1)</script>" not in result
    assert "&lt;script&gt;" in result


def test_format_size():
    assert _format_size(0) == "0 B"
    assert _format_size(512) == "512 B"
    assert _format_size(1024) == "1.0 KB"
    assert _format_size(1_500_000).endswith("MB")
    assert _format_size(5_000_000_000).endswith("GB")

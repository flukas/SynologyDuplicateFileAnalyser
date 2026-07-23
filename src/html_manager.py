"""Inject folder-analysis results into the Synology storage report HTML.

Standard-library only. The Synology report is located by anchor element ids
using :mod:`html.parser`, and the new section is added with a targeted string
insert. No third-party HTML parser is required, keeping the NAS deployment
dependency-free.

Injection contract:
    * The section is inserted after ``#duplicate_file_overview`` and, when
      present, before ``#title_large_file``.
    * The operation is idempotent: a previously injected
      ``#folder_similarity_overview`` section is replaced rather than
      duplicated.
    * All dynamic content (folder paths) is HTML-escaped.
"""
import html
import shutil
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional, Tuple

if TYPE_CHECKING:  # pragma: no cover - typing only
    from src.folder_analyzer import FolderGroup

INJECTED_SECTION_ID = "folder_similarity_overview"
ANCHOR_ID = "duplicate_file_overview"
BEFORE_ID = "title_large_file"


def _line_starts(text: str) -> List[int]:
    """Return the character offset at which each line begins."""
    starts = [0]
    for index, char in enumerate(text):
        if char == "\n":
            starts.append(index + 1)
    return starts


def _format_size(num_bytes: int) -> str:
    """Format a byte count as a human-readable string."""
    value = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(value) < 1024 or unit == "TB":
            if unit == "B":
                return f"{value:.0f} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


class _ElementSpanFinder(HTMLParser):
    """Locate the character span of the first element with a given ``id``.

    Tracks nesting of the matched element's tag so the closing tag of a nested
    same-name element is not mistaken for the end of the target.
    """

    def __init__(self, target_id: str, line_starts: List[int]):
        super().__init__(convert_charrefs=False)
        self._target_id = target_id
        self._line_starts = line_starts
        self.start: Optional[int] = None
        self.end: Optional[int] = None
        self._tag: Optional[str] = None
        self._depth = 0
        self._capturing = False

    def _offset(self) -> int:
        line, col = self.getpos()
        return self._line_starts[line - 1] + col

    def handle_starttag(self, tag, attrs):
        if self.end is not None:
            return
        if not self._capturing and dict(attrs).get("id") == self._target_id:
            self._capturing = True
            self._tag = tag
            self._depth = 1
            self.start = self._offset()
        elif self._capturing and tag == self._tag:
            self._depth += 1

    def handle_startendtag(self, tag, attrs):
        if self.end is not None or self._capturing:
            return
        if dict(attrs).get("id") == self._target_id:
            self.start = self._offset()
            starttag_text = self.get_starttag_text() or ""
            self.end = self.start + len(starttag_text)

    def handle_endtag(self, tag):
        if self._capturing and tag == self._tag:
            self._depth -= 1
            if self._depth == 0:
                self.end = self._offset() + len(f"</{tag}>")
                self._capturing = False


class HTMLManager:
    """Manages integration of analysis results into the Synology report HTML."""

    def __init__(self, html_path: Path):
        """Initialize the manager.

        Args:
            html_path: Path to the storage report HTML file.

        Raises:
            FileNotFoundError: If the HTML file does not exist.
        """
        self.html_path = Path(html_path)
        if not self.html_path.exists():
            raise FileNotFoundError(f"HTML report not found: {self.html_path}")

    def backup_report(self) -> Path:
        """Create a timestamped backup of the original HTML report.

        Returns:
            Path to the backup file.

        Raises:
            PermissionError: If the backup cannot be created.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.html_path.with_suffix(
            f"{self.html_path.suffix}.{timestamp}.bak"
        )
        try:
            shutil.copy2(self.html_path, backup_path)
        except OSError as exc:
            raise PermissionError(f"Cannot create backup: {exc}")
        return backup_path

    def inject_results(self, results: "List[FolderGroup]") -> None:
        """Inject folder analysis results into the HTML report.

        Args:
            results: Folder groups to display, in the desired order.

        Raises:
            ValueError: If the ``#duplicate_file_overview`` anchor is missing.
            IOError: If the HTML file cannot be written.
        """
        html_text = self.html_path.read_text(encoding="utf-8")

        # Idempotency: drop any previously injected section first.
        existing = self._find_span(html_text, INJECTED_SECTION_ID)
        if existing is not None:
            start, end = existing
            html_text = html_text[:start] + html_text[end:]

        anchor = self._find_span(html_text, ANCHOR_ID)
        if anchor is None:
            raise ValueError(
                f"Required anchor '#{ANCHOR_ID}' not found in HTML report"
            )

        insert_at = anchor[1]
        before = self._find_span(html_text, BEFORE_ID)
        if before is not None and before[0] >= insert_at:
            insert_at = before[0]

        section = self._build_section(results)
        new_html = html_text[:insert_at] + section + html_text[insert_at:]
        self.html_path.write_text(new_html, encoding="utf-8")

    @staticmethod
    def _find_span(html_text: str, element_id: str) -> Optional[Tuple[int, int]]:
        """Return the (start, end) char span of the element with ``element_id``."""
        finder = _ElementSpanFinder(element_id, _line_starts(html_text))
        finder.feed(html_text)
        finder.close()
        if finder.start is None or finder.end is None:
            return None
        return finder.start, finder.end

    @staticmethod
    def _build_section(results: "List[FolderGroup]") -> str:
        """Render the injected HTML section for the given results."""
        rows = []
        for group in results:
            folders = "<br>".join(
                html.escape(folder) for folder in sorted(group.folders)
            )
            rows.append(
                "        <tr>"
                f"<td>{folders}</td>"
                f"<td>{html.escape(_format_size(group.total_shared_size))}</td>"
                f"<td>{html.escape(_format_size(group.wasted_space))}</td>"
                "</tr>"
            )
        body = "\n".join(rows) if rows else (
            '        <tr><td colspan="3">No folder groups above threshold.</td></tr>'
        )
        return (
            f'\n<div id="{INJECTED_SECTION_ID}" class="table_container">\n'
            '  <div id="title_folder_similarity" class="title_text">'
            "Folder Similarity Analysis</div>\n"
            '  <table class="data_table">\n'
            "    <thead><tr><th>Folders</th><th>Shared Size</th>"
            "<th>Reclaimable</th></tr></thead>\n"
            "    <tbody>\n"
            f"{body}\n"
            "    </tbody>\n"
            "  </table>\n"
            "</div>\n"
        )

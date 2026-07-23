"""Core analysis for the Synology duplicate-file report.

The analysis is a two-phase pipeline:

1. :meth:`FolderAnalyzer.analyze_folder_groups` groups duplicate files by the
   *exact* set of full directory paths that share them. Each duplicate
   ``group_id`` therefore belongs to exactly one :class:`FolderGroup`.
2. :meth:`FolderAnalyzer.compact_nested_folders` is a second pass that merges
   groups whose folders are nested within one another (e.g. a share and a
   sub-folder of it), collapsing each relationship to its top-most level.

Callers that want fully compacted results should run phase 2 on the output of
phase 1.
"""
from dataclasses import dataclass
from typing import List, Dict, Set, Optional
from pathlib import Path
import csv
import logging
from collections import defaultdict

try:
    from src.utils import parse_csv_line, containing_directory
except ImportError:  # pragma: no cover - fallback when run from within src/
    from utils import parse_csv_line, containing_directory

@dataclass
class DuplicateFile:
    """Represents a single duplicate file from the report."""
    group_id: str
    folder: str
    path: str
    size: int

@dataclass
class FolderGroup:
    """Represents a group of folders containing duplicate files."""
    folders: Set[str]
    shared_files: Dict[str, List[DuplicateFile]]
    total_shared_size: int
    wasted_space: int

class FolderAnalyzer:
    """Analyzes duplicate files to find folder relationships."""
    
    def __init__(self, min_group_size: int = 50_000_000,
                 logger: Optional[logging.Logger] = None):
        """Initialize analyzer with minimum group size threshold.

        Args:
            min_group_size: Minimum reclaimable (wasted) space in bytes for a
                folder group to be reported (default 50MB).
            logger: Optional logger; malformed rows are logged here.
        """
        self.min_group_size = min_group_size
        self.logger = logger or logging.getLogger(__name__)

    def read_duplicate_report(self, csv_path: Path) -> List[DuplicateFile]:
        """Read and parse the duplicate files report CSV.

        Uses ``utils.parse_csv_line`` as the single parsing path and stores the
        full containing directory of each file in ``DuplicateFile.folder``.
        Malformed rows are logged and skipped so a single bad row never aborts
        the run. A missing or mismatched header is a structural error and
        raises ``ValueError``.
        """
        if not csv_path.exists():
            raise FileNotFoundError(f"CSV file not found: {csv_path}")

        with open(csv_path, 'r', encoding='utf-8', newline='') as f:
            lines = f.read().splitlines()

        if not lines:
            raise ValueError("Invalid CSV: file is empty (missing header)")

        expected_header = ["Group", "Shared Folder", "File", "Size(Byte)", "Modified Time"]
        header = next(csv.reader([lines[0]]), None)
        if header != expected_header:
            raise ValueError(f"Invalid CSV header. Expected: {expected_header}")

        duplicate_files: List[DuplicateFile] = []
        for line in lines[1:]:
            if not line.strip():
                continue
            try:
                group_id, _shared_folder, file_path, size, _modified = parse_csv_line(line)
                folder = containing_directory(file_path)
            except ValueError as exc:
                self.logger.error("Skipping malformed CSV row %r: %s", line, exc)
                continue

            duplicate_files.append(DuplicateFile(
                group_id=group_id,
                folder=folder,
                path=file_path,
                size=size,
            ))

        return duplicate_files

    def analyze_folder_groups(self, files: List[DuplicateFile]) -> List[FolderGroup]:
        """Group duplicate files by the exact set of folders that share them.

        Phase 1 of the pipeline. Files are first bucketed by ``group_id`` (a
        Synology duplicate set). For every set that spans more than one folder,
        the participating folders form a key and the group is attributed to it.
        As a result each ``group_id`` belongs to exactly one
        :class:`FolderGroup` (an invariant relied upon by
        :meth:`compact_nested_folders`).

        Only groups whose ``wasted_space`` meets ``min_group_size`` are kept,
        and results are sorted by ``wasted_space`` descending.

        Args:
            files: Duplicate files parsed from the report.

        Returns:
            Folder groups sorted by reclaimable space (descending).
        """
        # Group files by their duplicate group ID
        groups_by_id: Dict[str, List[DuplicateFile]] = defaultdict(list)
        for file in files:
            groups_by_id[file.group_id].append(file)
        
        # Find folder relationships
        folder_relationships: Dict[frozenset, Dict[str, List[DuplicateFile]]] = defaultdict(lambda: defaultdict(list))
        
        for group_id, group_files in groups_by_id.items():
            # Get unique folders in this group
            folders = {file.folder for file in group_files}
            
            # For each combination of folders that share this file
            if len(folders) > 1:
                folder_set = frozenset(folders)
                for file in group_files:
                    folder_relationships[folder_set][group_id].append(file)
        
        # Convert to FolderGroup objects
        results = []
        for folders, shared_files in folder_relationships.items():
            # Calculate sizes
            total_shared_size = 0
            for group_files in shared_files.values():
                # Take size from first file in group (they're all the same)
                total_shared_size += group_files[0].size
            
            # Calculate wasted space (duplicate copies)
            wasted_space = sum(
                group_files[0].size * (len(group_files) - 1)
                for group_files in shared_files.values()
            )
            
            # Only include groups meeting the reclaimable-space threshold
            if wasted_space >= self.min_group_size:
                results.append(FolderGroup(
                    folders=set(folders),
                    shared_files=dict(shared_files),
                    total_shared_size=total_shared_size,
                    wasted_space=wasted_space
                ))

        # Sort by reclaimable (wasted) space, descending
        results.sort(key=lambda x: x.wasted_space, reverse=True)
        return results

    def compact_nested_folders(self, groups: List[FolderGroup]) -> List[FolderGroup]:
        """Combine groups whose folders are nested within one another.

        When a child folder (e.g. ``/volume1/photos/vacation``) is nested under
        a parent folder (e.g. ``/volume1/photos``) participating in the same
        sharing relationship, the child is collapsed into the parent so each
        relationship is reported once at the highest meaningful level.

        Does not mutate the input list; returns a new list sorted by
        ``wasted_space`` (descending).

        Precondition:
            Sizes are combined additively, which assumes each ``group_id``
            appears in at most one input group (as produced by
            :meth:`analyze_folder_groups`). Shared-file lists are still merged
            per ``group_id`` so folder membership stays correct.
        """
        if not groups:
            return []

        def is_nested(folder1: str, folder2: str) -> bool:
            """Check if one folder is nested within another."""
            return folder1.startswith(folder2 + '/') or folder2.startswith(folder1 + '/')

        def should_merge(group1: FolderGroup, group2: FolderGroup) -> bool:
            """Determine if two groups should be merged based on folder relationships."""
            for folder1 in group1.folders:
                for folder2 in group2.folders:
                    if folder1 == folder2 or is_nested(folder1, folder2):
                        return True
            return False

        def collapse(folders: Set[str]) -> Set[str]:
            """Keep only the top-most ancestors, dropping nested children."""
            return {
                folder for folder in folders
                if not any(
                    other != folder and folder.startswith(other + '/')
                    for other in folders
                )
            }

        # Work on deep-ish copies so the caller's list and groups are untouched.
        working: List[FolderGroup] = [
            FolderGroup(
                folders=set(group.folders),
                shared_files={gid: list(files) for gid, files in group.shared_files.items()},
                total_shared_size=group.total_shared_size,
                wasted_space=group.wasted_space,
            )
            for group in groups
        ]

        # Keep merging until no more merges are possible.
        while True:
            merged = False
            for i in range(len(working)):
                for j in range(i + 1, len(working)):
                    if should_merge(working[i], working[j]):
                        first, second = working[i], working[j]

                        # Merge shared files without double-counting a group_id.
                        merged_files = {
                            gid: list(files) for gid, files in first.shared_files.items()
                        }
                        for group_id, files in second.shared_files.items():
                            if group_id in merged_files:
                                merged_files[group_id].extend(files)
                            else:
                                merged_files[group_id] = list(files)

                        working[i] = FolderGroup(
                            folders=collapse(first.folders | second.folders),
                            shared_files=merged_files,
                            total_shared_size=first.total_shared_size + second.total_shared_size,
                            wasted_space=first.wasted_space + second.wasted_space,
                        )
                        working.pop(j)
                        merged = True
                        break
                if merged:
                    break

            if not merged:
                break

        return sorted(working, key=lambda x: x.wasted_space, reverse=True)

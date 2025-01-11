from dataclasses import dataclass
from typing import List, Dict, Set, Tuple
from pathlib import Path
import csv
from collections import defaultdict

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
    
    def __init__(self, min_group_size: int = 50_000_000):
        """Initialize analyzer with minimum group size threshold."""
        self.min_group_size = min_group_size

    def read_duplicate_report(self, csv_path: Path) -> List[DuplicateFile]:
        """Read and parse the duplicate files report CSV."""
        if not csv_path.exists():
            raise FileNotFoundError(f"CSV file not found: {csv_path}")

        duplicate_files = []
        
        with open(csv_path, 'r', encoding='utf-8', newline='') as f:
            reader = csv.reader(f)
            
            # Validate header
            header = next(reader, None)
            expected_header = ["Group", "Shared Folder", "File", "Size(Byte)", "Modified Time"]
            if header != expected_header:
                raise ValueError(f"Invalid CSV header. Expected: {expected_header}")
            
            # Process rows
            for row in reader:
                if len(row) != 5:
                    raise ValueError(f"Invalid row format: {row}")
                
                group_id, shared_folder, file_path, size_str, _ = row
                
                try:
                    size = int(size_str)
                except ValueError:
                    raise ValueError(f"Invalid size value: {size_str}")
                
                duplicate_files.append(DuplicateFile(
                    group_id=group_id,
                    folder=shared_folder,
                    path=file_path,
                    size=size
                ))
        
        return duplicate_files

    def analyze_folder_groups(self, files: List[DuplicateFile]) -> List[FolderGroup]:
        """Analyze duplicate files to identify folder groups with shared content."""
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
            
            # Only include groups meeting size threshold
            if total_shared_size >= self.min_group_size:
                results.append(FolderGroup(
                    folders=set(folders),
                    shared_files=dict(shared_files),
                    total_shared_size=total_shared_size,
                    wasted_space=wasted_space
                ))
        
        # Sort by total shared size
        results.sort(key=lambda x: x.total_shared_size, reverse=True)
        return results

    def compact_nested_folders(self, groups: List[FolderGroup]) -> List[FolderGroup]:
        """Combine groups where folders are nested within each other."""
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

        # Keep merging until no more merges are possible
        while True:
            merged = False
            for i in range(len(groups)):
                if merged:
                    break
                    
                for j in range(i + 1, len(groups)):
                    if should_merge(groups[i], groups[j]):
                        # Merge groups[j] into groups[i]
                        merged_folders = groups[i].folders.union(groups[j].folders)
                        merged_files = {**groups[i].shared_files}
                        
                        # Merge shared files
                        for group_id, files in groups[j].shared_files.items():
                            if group_id in merged_files:
                                merged_files[group_id].extend(files)
                            else:
                                merged_files[group_id] = files
                        
                        # Calculate new sizes
                        total_shared_size = groups[i].total_shared_size + groups[j].total_shared_size
                        wasted_space = groups[i].wasted_space + groups[j].wasted_space
                        
                        # Create merged group
                        merged_group = FolderGroup(
                            folders=merged_folders,
                            shared_files=merged_files,
                            total_shared_size=total_shared_size,
                            wasted_space=wasted_space
                        )
                        
                        # Replace groups[i] with merged group and remove groups[j]
                        groups[i] = merged_group
                        groups.pop(j)
                        
                        merged = True
                        break
            
            if not merged:
                break
        
        return sorted(groups, key=lambda x: x.total_shared_size, reverse=True)

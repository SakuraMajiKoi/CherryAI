"""Replication module for CherryAI game update detection and translation updates.

This module provides tools for:
- Comparing manifests to detect changes between game versions
- Generating translation update files for only new/modified content
- Tracking deleted lines for cleanup

Phase 4 of Manifest v2.0 implementation.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from .mainhelper import LineEntry, Manifest, MANIFEST_VERSION

logger = logging.getLogger(__name__)


class ChangeType(Enum):
    """Type of change detected between manifest versions."""
    UNCHANGED = "unchanged"
    MODIFIED = "modified"
    NEW = "new"
    DELETED = "deleted"


@dataclass
class LineChange:
    """Represents a change to a single line between manifest versions.
    
    Attributes:
        idx: Line index in the manifest
        change_type: Type of change (UNCHANGED, MODIFIED, NEW, DELETED)
        old_text: Original text (None for NEW lines)
        new_text: New text (None for DELETED lines)
        old_hash: SHA-256 hash of old text
        new_hash: SHA-256 hash of new text
        has_translation: Whether the line has existing translation work
    """
    idx: int
    change_type: ChangeType
    old_text: Optional[str] = None
    new_text: Optional[str] = None
    old_hash: Optional[str] = None
    new_hash: Optional[str] = None
    has_translation: bool = False


@dataclass
class ComparisonResult:
    """Result of comparing two manifests or a manifest with source files.
    
    Attributes:
        unchanged_count: Number of lines that haven't changed
        modified_count: Number of lines with modified original text
        new_count: Number of new lines added
        deleted_count: Number of lines that were removed
        changes: List of all LineChange objects
        old_manifest_path: Path to the old manifest (if applicable)
        new_source_path: Path to the new source (if applicable)
    """
    unchanged_count: int = 0
    modified_count: int = 0
    new_count: int = 0
    deleted_count: int = 0
    changes: List[LineChange] = field(default_factory=list)
    old_manifest_path: Optional[Path] = None
    new_source_path: Optional[Path] = None
    
    @property
    def total_changes(self) -> int:
        """Total number of lines that need attention (modified + new + deleted)."""
        return self.modified_count + self.new_count + self.deleted_count
    
    @property
    def has_changes(self) -> bool:
        """Whether any changes were detected."""
        return self.total_changes > 0
    
    def get_changes_by_type(self, change_type: ChangeType) -> List[LineChange]:
        """Get all changes of a specific type."""
        return [c for c in self.changes if c.change_type == change_type]
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for JSON export."""
        return {
            "summary": {
                "unchanged": self.unchanged_count,
                "modified": self.modified_count,
                "new": self.new_count,
                "deleted": self.deleted_count,
                "total_changes": self.total_changes,
            },
            "old_manifest": str(self.old_manifest_path) if self.old_manifest_path else None,
            "new_source": str(self.new_source_path) if self.new_source_path else None,
            "changes": [
                {
                    "idx": c.idx,
                    "type": c.change_type.value,
                    "old_text": c.old_text,
                    "new_text": c.new_text,
                    "has_translation": c.has_translation,
                }
                for c in self.changes
                if c.change_type != ChangeType.UNCHANGED
            ],
        }


class ChangeDetector:
    """Detects changes between manifest versions using SHA-256 hashing.
    
    Uses hash comparison for efficient change detection on large files.
    """
    
    @staticmethod
    def hash_text(text: str) -> str:
        """Generate SHA-256 hash of text content.
        
        Args:
            text: Text to hash
            
        Returns:
            Hexadecimal hash string
        """
        return hashlib.sha256(text.encode("utf-8")).hexdigest()
    
    @staticmethod
    def texts_match(text1: Optional[str], text2: Optional[str]) -> bool:
        """Check if two texts are identical (handles None values).
        
        Args:
            text1: First text (may be None)
            text2: Second text (may be None)
            
        Returns:
            True if texts are identical
        """
        if text1 is None and text2 is None:
            return True
        if text1 is None or text2 is None:
            return False
        return text1 == text2
    
    def detect_line_change(
        self,
        old_line: Optional[LineEntry],
        new_text: Optional[str],
        idx: int,
    ) -> LineChange:
        """Detect change type for a single line.
        
        Args:
            old_line: LineEntry from old manifest (None if new line)
            new_text: Text from new source (None if deleted)
            idx: Line index
            
        Returns:
            LineChange describing the change
        """
        old_text = old_line.orig if old_line else None
        old_hash = self.hash_text(old_text) if old_text is not None else None
        new_hash = self.hash_text(new_text) if new_text is not None else None
        
        # Check if line has any translation work
        has_translation = False
        if old_line:
            has_translation = any([
                old_line.tl is not None,
                old_line.postpro is not None,
                old_line.get_highest_tlc_pass() > 0,
                old_line.get_highest_edit_pass() > 0,
            ])
        
        # Determine change type
        if old_line is None and new_text is not None:
            change_type = ChangeType.NEW
        elif old_line is not None and new_text is None:
            change_type = ChangeType.DELETED
        elif self.texts_match(old_text, new_text):
            change_type = ChangeType.UNCHANGED
        else:
            change_type = ChangeType.MODIFIED
        
        return LineChange(
            idx=idx,
            change_type=change_type,
            old_text=old_text,
            new_text=new_text,
            old_hash=old_hash,
            new_hash=new_hash,
            has_translation=has_translation,
        )


class ManifestComparison:
    """Compare manifests to detect changes between game versions.
    
    Supports comparing:
    - A manifest against updated source text
    - Two manifests directly
    """
    
    def __init__(self) -> None:
        self.detector = ChangeDetector()
    
    def compare_with_text(
        self,
        manifest: Manifest,
        new_text: str,
        source_path: Optional[Path] = None,
    ) -> ComparisonResult:
        """Compare a manifest's original lines against new source text.
        
        Args:
            manifest: Existing manifest with translation work
            new_text: New/updated source text content
            source_path: Optional path to the new source file
            
        Returns:
            ComparisonResult with detected changes
        """
        result = ComparisonResult(new_source_path=source_path)
        
        # Parse new text into lines
        new_lines = new_text.split("\n")
        
        # Get sorted old lines from manifest
        old_lines_dict: Dict[int, LineEntry] = {}
        for line in manifest.lines:
            old_lines_dict[line.idx] = line
        
        max_idx = max(
            max(old_lines_dict.keys()) if old_lines_dict else -1,
            len(new_lines) - 1,
        )
        
        for idx in range(max_idx + 1):
            old_line = old_lines_dict.get(idx)
            new_line_text = new_lines[idx] if idx < len(new_lines) else None
            
            change = self.detector.detect_line_change(old_line, new_line_text, idx)
            result.changes.append(change)
            
            # Update counts
            if change.change_type == ChangeType.UNCHANGED:
                result.unchanged_count += 1
            elif change.change_type == ChangeType.MODIFIED:
                result.modified_count += 1
            elif change.change_type == ChangeType.NEW:
                result.new_count += 1
            elif change.change_type == ChangeType.DELETED:
                result.deleted_count += 1
        
        return result
    
    def compare_manifests(
        self,
        old_manifest: Manifest,
        new_manifest: Manifest,
    ) -> ComparisonResult:
        """Compare two manifests to detect changes in original text.
        
        Args:
            old_manifest: Previous version manifest
            new_manifest: Updated version manifest
            
        Returns:
            ComparisonResult with detected changes
        """
        result = ComparisonResult()
        
        # Build lookup dicts
        old_lines_dict: Dict[int, LineEntry] = {}
        for line in old_manifest.lines:
            old_lines_dict[line.idx] = line
        
        new_lines_dict: Dict[int, LineEntry] = {}
        for line in new_manifest.lines:
            new_lines_dict[line.idx] = line
        
        # Get all indices
        all_indices: Set[int] = set(old_lines_dict.keys()) | set(new_lines_dict.keys())
        
        for idx in sorted(all_indices):
            old_line = old_lines_dict.get(idx)
            new_line = new_lines_dict.get(idx)
            new_text = new_line.orig if new_line else None
            
            change = self.detector.detect_line_change(old_line, new_text, idx)
            result.changes.append(change)
            
            # Update counts
            if change.change_type == ChangeType.UNCHANGED:
                result.unchanged_count += 1
            elif change.change_type == ChangeType.MODIFIED:
                result.modified_count += 1
            elif change.change_type == ChangeType.NEW:
                result.new_count += 1
            elif change.change_type == ChangeType.DELETED:
                result.deleted_count += 1
        
        return result


class UpdateOutputGenerator:
    """Generate translation update files from comparison results.
    
    Creates export files containing only the lines that need translation,
    preserving context and previous translation work where applicable.
    """
    
    def generate_update_manifest(
        self,
        original_manifest: Manifest,
        comparison: ComparisonResult,
        include_context: bool = True,
        context_lines: int = 2,
    ) -> Manifest:
        """Generate a new manifest containing only lines that need work.
        
        Args:
            original_manifest: The original manifest with existing work
            comparison: Comparison result showing changes
            include_context: Whether to include surrounding unchanged lines
            context_lines: Number of context lines to include on each side
            
        Returns:
            New Manifest with only changed lines (and optional context)
        """
        # Create new manifest based on original
        update_manifest = Manifest(
            summary=f"UPDATE: {original_manifest.summary}",
            operations=list(original_manifest.operations),
            metadata={
                **original_manifest.metadata,
                "is_update": True,
                "original_manifest": original_manifest.summary,
                "changes": {
                    "modified": comparison.modified_count,
                    "new": comparison.new_count,
                    "deleted": comparison.deleted_count,
                },
            },
        )
        update_manifest.origin_file = original_manifest.origin_file
        update_manifest.root_selected = original_manifest.root_selected
        
        # Collect indices to include
        indices_to_include: Set[int] = set()
        
        for change in comparison.changes:
            if change.change_type in (ChangeType.MODIFIED, ChangeType.NEW):
                indices_to_include.add(change.idx)
                
                # Add context lines if requested
                if include_context:
                    for offset in range(1, context_lines + 1):
                        if change.idx - offset >= 0:
                            indices_to_include.add(change.idx - offset)
                        indices_to_include.add(change.idx + offset)
        
        # Build lines array with changes applied
        for change in comparison.changes:
            if change.idx not in indices_to_include:
                continue
            
            if change.change_type == ChangeType.DELETED:
                # Mark as deleted
                entry = LineEntry(
                    idx=change.idx,
                    orig=change.old_text or "",
                    deleted=True,
                )
            elif change.change_type == ChangeType.NEW:
                # New line with no previous work
                entry = LineEntry(
                    idx=change.idx,
                    orig=change.new_text or "",
                )
            elif change.change_type == ChangeType.MODIFIED:
                # Modified line - preserve original work, update text
                old_line = None
                for line in original_manifest.lines:
                    if line.idx == change.idx:
                        old_line = line
                        break
                
                if old_line:
                    # Copy existing work but update orig and mark updated
                    entry = LineEntry(
                        idx=change.idx,
                        orig=change.new_text or "",
                        prepro=old_line.prepro,
                        prepro_ops=old_line.prepro_ops,
                        tl=old_line.tl,
                        postpro=old_line.postpro,
                        wordwr=old_line.wordwr,
                        overwrite=old_line.overwrite,
                        log=old_line.log,
                        updated=change.old_text,  # Store old text in updated field
                    )
                    # Copy TLC/Edit passes
                    for n in range(1, 100):
                        tlc = old_line.get_tlc(n)
                        if tlc:
                            entry.set_tlc(n, tlc)
                        edit = old_line.get_edit(n)
                        if edit:
                            entry.set_edit(n, edit)
                else:
                    entry = LineEntry(
                        idx=change.idx,
                        orig=change.new_text or "",
                    )
            else:
                # Unchanged context line - copy from original
                old_line = None
                for line in original_manifest.lines:
                    if line.idx == change.idx:
                        old_line = line
                        break
                
                if old_line:
                    entry = LineEntry(
                        idx=change.idx,
                        orig=old_line.orig,
                        prepro=old_line.prepro,
                        prepro_ops=old_line.prepro_ops,
                        tl=old_line.tl,
                        postpro=old_line.postpro,
                        wordwr=old_line.wordwr,
                        overwrite=old_line.overwrite,
                    )
                else:
                    entry = LineEntry(
                        idx=change.idx,
                        orig=change.new_text or "",
                    )
            
            update_manifest.lines.append(entry)
        
        # Sort lines by index
        update_manifest.lines.sort(key=lambda x: x.idx)
        
        return update_manifest
    
    def generate_update_text(
        self,
        comparison: ComparisonResult,
        include_line_numbers: bool = True,
    ) -> str:
        """Generate a simple text file with lines that need translation.
        
        Args:
            comparison: Comparison result showing changes
            include_line_numbers: Whether to prefix lines with their index
            
        Returns:
            Text content with new/modified lines
        """
        lines: List[str] = []
        
        for change in comparison.changes:
            if change.change_type in (ChangeType.MODIFIED, ChangeType.NEW):
                if include_line_numbers:
                    prefix = f"[{change.idx}] "
                    type_marker = "[MOD] " if change.change_type == ChangeType.MODIFIED else "[NEW] "
                    lines.append(f"{type_marker}{prefix}{change.new_text}")
                else:
                    lines.append(change.new_text or "")
        
        return "\n".join(lines)
    
    def merge_update_into_manifest(
        self,
        original_manifest: Manifest,
        update_manifest: Manifest,
    ) -> Manifest:
        """Merge translated update back into the original manifest.
        
        Args:
            original_manifest: The complete original manifest
            update_manifest: Manifest with translated updates
            
        Returns:
            Merged manifest with updates applied
        """
        # Create copy of original
        merged = Manifest(
            summary=original_manifest.summary,
            operations=list(original_manifest.operations),
            metadata=dict(original_manifest.metadata),
            mappings=dict(original_manifest.mappings),
        )
        merged.origin_file = original_manifest.origin_file
        merged.root_selected = original_manifest.root_selected
        
        # Copy all original lines
        for line in original_manifest.lines:
            merged.lines.append(LineEntry(
                idx=line.idx,
                orig=line.orig,
                prepro=line.prepro,
                prepro_ops=line.prepro_ops,
                tl=line.tl,
                postpro=line.postpro,
                wordwr=line.wordwr,
                overwrite=line.overwrite,
                log=line.log,
                deleted=line.deleted,
                updated=line.updated,
            ))
        
        # Build lookup for merged lines
        merged_dict: Dict[int, LineEntry] = {}
        for line in merged.lines:
            merged_dict[line.idx] = line
        
        # Apply updates
        for update_line in update_manifest.lines:
            if update_line.idx in merged_dict:
                target = merged_dict[update_line.idx]
                
                # Update fields from update manifest
                if update_line.orig:
                    target.orig = update_line.orig
                if update_line.tl is not None:
                    target.tl = update_line.tl
                if update_line.postpro is not None:
                    target.postpro = update_line.postpro
                if update_line.wordwr is not None:
                    target.wordwr = update_line.wordwr
                if update_line.overwrite is not None:
                    target.overwrite = update_line.overwrite
                if update_line.deleted:
                    target.deleted = True
                if update_line.updated is not None:
                    target.updated = update_line.updated
                
                # Copy TLC/Edit passes
                for n in range(1, 100):
                    tlc = update_line.get_tlc(n)
                    if tlc:
                        target.set_tlc(n, tlc)
                    edit = update_line.get_edit(n)
                    if edit:
                        target.set_edit(n, edit)
            else:
                # New line not in original - add it
                merged.lines.append(update_line)
        
        # Sort by index
        merged.lines.sort(key=lambda x: x.idx)
        
        # Update metadata
        merged.metadata["last_update"] = update_manifest.summary
        
        return merged


def compare_manifest_with_source(
    manifest_path: Path,
    source_path: Path,
) -> ComparisonResult:
    """Convenience function to compare a manifest file with updated source.
    
    Args:
        manifest_path: Path to existing manifest JSON
        source_path: Path to updated source text file
        
    Returns:
        ComparisonResult with detected changes
    """
    # Load manifest
    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest = Manifest.from_dict(manifest_data)
    
    # Load source text
    source_text = source_path.read_text(encoding="utf-8")
    
    # Compare
    comparison = ManifestComparison()
    result = comparison.compare_with_text(manifest, source_text, source_path)
    result.old_manifest_path = manifest_path
    
    return result


def generate_update_files(
    manifest_path: Path,
    source_path: Path,
    output_dir: Path,
) -> Tuple[Path, Path]:
    """Generate update manifest and text file from comparison.
    
    Args:
        manifest_path: Path to existing manifest
        source_path: Path to updated source
        output_dir: Directory for output files
        
    Returns:
        Tuple of (update_manifest_path, update_text_path)
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Load and compare
    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest = Manifest.from_dict(manifest_data)
    source_text = source_path.read_text(encoding="utf-8")
    
    comparison = ManifestComparison()
    result = comparison.compare_with_text(manifest, source_text, source_path)
    
    # Generate outputs
    generator = UpdateOutputGenerator()
    
    # Update manifest
    update_manifest = generator.generate_update_manifest(manifest, result)
    update_manifest_path = output_dir / f"{source_path.stem}.update.CherryAI.json"
    update_manifest_path.write_text(
        json.dumps(update_manifest.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    
    # Update text
    update_text = generator.generate_update_text(result)
    update_text_path = output_dir / f"{source_path.stem}.update.txt"
    update_text_path.write_text(update_text, encoding="utf-8")
    
    logger.info(
        "Generated update files: %d modified, %d new, %d deleted",
        result.modified_count,
        result.new_count,
        result.deleted_count,
    )
    
    return update_manifest_path, update_text_path

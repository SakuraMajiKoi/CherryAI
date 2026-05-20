"""Shared project patch discovery, search, and application helpers.

This module provides the parser-advertised project patch surface used by Step 9
to list and apply parser-specific file patches against a project's staged
``Translated/`` tree.
"""

from __future__ import annotations

import logging
import shutil
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk
from typing import Callable, List, Optional, Sequence, TYPE_CHECKING


if TYPE_CHECKING:
    from CherryAI.functions.manifest_manager import ManifestManager


logger = logging.getLogger(__name__)

PatchLog = Callable[[str], None]


@dataclass(frozen=True)
class ParserProjectPatch:
    """Parser-advertised project patch definition."""

    patch_id: str
    name: str
    description: str
    file_label: str
    relative_candidates: tuple[Path, ...]
    apply_to_target: Callable[[Path, PatchLog], "PatchApplicationResult"]
    apply_with_context: Optional[
        Callable[["ManifestManager", "DiscoveredParserPatch", Optional[tk.Misc], PatchLog], "PatchApplicationResult"]
    ] = None


@dataclass(frozen=True)
class PatchApplicationResult:
    """Outcome of one project patch run."""

    status: str
    message: str = ""
    target_path: Optional[Path] = None


@dataclass(frozen=True)
class DiscoveredParserPatch:
    """Concrete patch exposed by a parser used in the current manifest."""

    parser_name: str
    parser_display_name: str
    patch: ParserProjectPatch

    @property
    def storage_key(self) -> str:
        return f"{self.parser_name}:{self.patch.patch_id}"

    @property
    def display_name(self) -> str:
        return f"{self.parser_display_name} - {self.patch.name}"


def _get_output_options(mgr: "ManifestManager") -> dict:
    raw = mgr.get_output_options()
    return raw if isinstance(raw, dict) else {}


def get_saved_patch_lookup_dir(
    mgr: "ManifestManager",
    storage_key: str,
) -> Optional[Path]:
    """Return the saved lookup folder for one patch, if any."""
    options = _get_output_options(mgr)
    raw_map = options.get("PatchLookupFolders", {})
    if not isinstance(raw_map, dict):
        return None
    raw_value = str(raw_map.get(storage_key, "")).strip()
    return Path(raw_value) if raw_value else None


def set_saved_patch_lookup_dir(
    mgr: "ManifestManager",
    storage_key: str,
    folder: Path,
) -> None:
    """Persist the preferred lookup folder for one patch in the manifest."""
    options = _get_output_options(mgr)
    raw_map = options.get("PatchLookupFolders", {})
    lookup_map = dict(raw_map) if isinstance(raw_map, dict) else {}
    new_value = str(folder)
    if lookup_map.get(storage_key) == new_value:
        return
    lookup_map[storage_key] = new_value
    options["PatchLookupFolders"] = lookup_map
    mgr.set_output_options(options)
    if getattr(mgr, "is_loaded", False) and hasattr(mgr, "save"):
        try:
            mgr.save()
        except Exception:
            logger.warning("Failed to save patch lookup folder for %s", storage_key)


def discover_manifest_parser_patches(
    mgr: "ManifestManager",
) -> List[DiscoveredParserPatch]:
    """Collect unique parser project patches from the active manifest."""
    from CherryAI.formats import get_parser_registry

    filedir = mgr.get_filedir()
    registry = get_parser_registry()
    seen_formats: set[str] = set()
    discovered: List[DiscoveredParserPatch] = []

    for entry in filedir:
        fmt = str(getattr(entry, "format", "")).strip().lower()
        if not fmt or fmt in seen_formats:
            continue
        seen_formats.add(fmt)
        parser = registry.get(fmt)
        if parser is None:
            continue
        for patch in parser.project_patches:
            discovered.append(
                DiscoveredParserPatch(
                    parser_name=parser.name,
                    parser_display_name=parser.display_name,
                    patch=patch,
                )
            )

    return discovered


def _find_in_root(
    root: Path,
    candidates: Sequence[Path],
    *,
    recursive: bool,
) -> Optional[tuple[Path, Path]]:
    for relative in candidates:
        candidate = root / relative
        if candidate.exists():
            return candidate, relative

    if not recursive:
        return None

    for relative in candidates:
        try:
            matches = sorted(
                root.rglob(relative.name),
                key=lambda path: (len(path.parts), path.as_posix().lower()),
            )
        except OSError:
            continue
        for match in matches:
            if match.is_file():
                return match, match.relative_to(root)
    return None


def _copy_into_translated(
    mgr: "ManifestManager",
    source_path: Path,
    relative_path: Path,
    log: PatchLog,
) -> Path:
    target = mgr.get_translated_dir() / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, target)
    log(f"Copied {source_path} -> {target}")
    return target


def _prompt_lookup_folder(
    parent: tk.Misc,
    mgr: "ManifestManager",
    patch_info: DiscoveredParserPatch,
) -> Optional[Path]:
    saved = get_saved_patch_lookup_dir(mgr, patch_info.storage_key)
    if saved is not None and saved.is_dir():
        initialdir = str(saved)
    else:
        initialdir = str(mgr.get_project_dir())

    folder = filedialog.askdirectory(
        parent=parent,
        title=f"Select Folder For {patch_info.patch.file_label}",
        initialdir=initialdir,
        mustexist=True,
    )
    if not folder:
        return None

    selected = Path(folder)
    set_saved_patch_lookup_dir(mgr, patch_info.storage_key, selected)
    return selected


def resolve_patch_target(
    mgr: "ManifestManager",
    patch_info: DiscoveredParserPatch,
    *,
    parent: Optional[tk.Misc],
    prompt_for_folder: bool,
    log: PatchLog,
) -> PatchApplicationResult:
    """Resolve the staged target file for one parser project patch."""
    translated_root = mgr.get_translated_dir()
    original_root = mgr.get_original_dir()
    candidates = patch_info.patch.relative_candidates

    translated_hit = _find_in_root(translated_root, candidates, recursive=True)
    if translated_hit is not None:
        target, relative = translated_hit
        log(f"Found {patch_info.patch.file_label} in Translated/{relative.as_posix()}")
        return PatchApplicationResult(
            status="resolved",
            message="Found existing staged target.",
            target_path=target,
        )

    original_hit = _find_in_root(original_root, candidates, recursive=True)
    if original_hit is not None:
        source, relative = original_hit
        log(f"Found {patch_info.patch.file_label} in Original/{relative.as_posix()}")
        target = _copy_into_translated(mgr, source, relative, log)
        return PatchApplicationResult(
            status="resolved",
            message="Copied target from Original into Translated.",
            target_path=target,
        )

    saved_lookup = get_saved_patch_lookup_dir(mgr, patch_info.storage_key)
    if saved_lookup is not None:
        if saved_lookup.is_dir():
            saved_hit = _find_in_root(saved_lookup, candidates, recursive=True)
            if saved_hit is not None:
                source, relative = saved_hit
                log(
                    f"Found {patch_info.patch.file_label} in saved lookup "
                    f"{saved_lookup / relative}"
                )
                target = _copy_into_translated(mgr, source, relative, log)
                return PatchApplicationResult(
                    status="resolved",
                    message="Copied target from saved lookup folder.",
                    target_path=target,
                )
            log(
                f"Saved lookup folder did not contain {patch_info.patch.file_label}: "
                f"{saved_lookup}"
            )
        else:
            log(f"Saved lookup folder is unavailable: {saved_lookup}")

    if not prompt_for_folder or parent is None:
        return PatchApplicationResult(
            status="failed",
            message=f"Could not find {patch_info.patch.file_label}.",
        )

    selected = _prompt_lookup_folder(parent, mgr, patch_info)
    if selected is None:
        return PatchApplicationResult(
            status="cancelled",
            message=f"Folder selection cancelled for {patch_info.patch.file_label}.",
        )

    selected_hit = _find_in_root(selected, candidates, recursive=True)
    if selected_hit is None:
        return PatchApplicationResult(
            status="failed",
            message=(
                f"Selected folder did not contain {patch_info.patch.file_label}: {selected}"
            ),
        )

    source, relative = selected_hit
    log(f"Found {patch_info.patch.file_label} in selected folder {selected / relative}")
    target = _copy_into_translated(mgr, source, relative, log)
    return PatchApplicationResult(
        status="resolved",
        message="Copied target from selected lookup folder.",
        target_path=target,
    )


def apply_parser_patch(
    mgr: "ManifestManager",
    patch_info: DiscoveredParserPatch,
    *,
    parent: Optional[tk.Misc],
    prompt_for_folder: bool,
    log: PatchLog,
) -> PatchApplicationResult:
    """Resolve and apply a parser project patch."""
    log(f"Applying {patch_info.display_name}")

    if patch_info.patch.apply_with_context is not None:
        try:
            result = patch_info.patch.apply_with_context(mgr, patch_info, parent, log)
        except Exception as exc:
            logger.exception("Project patch failed: %s", patch_info.display_name)
            message = f"{patch_info.display_name} failed: {exc}"
            log(message)
            return PatchApplicationResult(
                status="failed",
                message=message,
            )

        if result.message:
            log(result.message)
        return result

    resolved = resolve_patch_target(
        mgr,
        patch_info,
        parent=parent,
        prompt_for_folder=prompt_for_folder,
        log=log,
    )
    if resolved.status != "resolved" or resolved.target_path is None:
        log(resolved.message)
        return resolved

    try:
        result = patch_info.patch.apply_to_target(resolved.target_path, log)
    except Exception as exc:
        logger.exception("Project patch failed: %s", patch_info.display_name)
        message = f"{patch_info.display_name} failed: {exc}"
        log(message)
        return PatchApplicationResult(
            status="failed",
            message=message,
            target_path=resolved.target_path,
        )

    if result.message:
        log(result.message)
    return result


def apply_parser_patches(
    mgr: "ManifestManager",
    patch_items: Sequence[DiscoveredParserPatch],
    *,
    parent: Optional[tk.Misc],
    prompt_for_folder: bool,
    log: PatchLog,
) -> List[PatchApplicationResult]:
    """Apply multiple parser patches in order."""
    results: List[PatchApplicationResult] = []
    for item in patch_items:
        results.append(
            apply_parser_patch(
                mgr,
                item,
                parent=parent,
                prompt_for_folder=prompt_for_folder,
                log=log,
            )
        )
    return results


class ApplyPatchesDialog(tk.Toplevel):
    """Small modal window for parser project patches."""

    def __init__(self, parent: tk.Misc, mgr: "ManifestManager") -> None:
        super().__init__(parent)
        self._manifest_manager = mgr
        self._patch_items = discover_manifest_parser_patches(mgr)
        self._check_vars: List[tk.BooleanVar] = []

        self.title("Apply Patches")
        self.transient(parent)
        self.grab_set()
        self.resizable(True, True)
        self.minsize(640, 360)
        self.protocol("WM_DELETE_WINDOW", self.destroy)

        self._build_ui()

    def _build_ui(self) -> None:
        container = ttk.Frame(self, padding=10)
        container.pack(fill="both", expand=True)

        ttk.Label(
            container,
            text="Parser Project Patches",
            font=("TkDefaultFont", 11, "bold"),
        ).pack(anchor="w")

        patch_frame = ttk.Frame(container)
        patch_frame.pack(fill="x", pady=(8, 10))

        show_checks = len(self._patch_items) > 1
        for item in self._patch_items:
            row = ttk.Frame(patch_frame)
            row.pack(fill="x", pady=4)

            if show_checks:
                var = tk.BooleanVar(value=True)
                self._check_vars.append(var)
                ttk.Checkbutton(row, variable=var).pack(side="left", padx=(0, 8))
            else:
                self._check_vars.append(tk.BooleanVar(value=True))

            text_frame = ttk.Frame(row)
            text_frame.pack(side="left", fill="x", expand=True)

            ttk.Label(
                text_frame,
                text=item.display_name,
                font=("TkDefaultFont", 10, "bold"),
            ).pack(anchor="w")
            ttk.Label(
                text_frame,
                text=item.patch.description,
                wraplength=470,
                justify="left",
            ).pack(anchor="w")

            ttk.Button(
                row,
                text="Apply Patch",
                command=lambda current=item: self._apply_single(current),
            ).pack(side="right", padx=(8, 0))

        self._log_box = scrolledtext.ScrolledText(self, height=10, wrap="word")
        self._log_box.pack(fill="both", expand=True, padx=10)
        self._log_box.configure(state="disabled")

        buttons = ttk.Frame(container)
        buttons.pack(fill="x", pady=(10, 0))

        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(side="right")
        if len(self._patch_items) > 1:
            ttk.Button(
                buttons,
                text="Apply All Patches",
                command=self._apply_selected,
            ).pack(side="right", padx=(0, 8))

    def _log(self, message: str) -> None:
        self._log_box.configure(state="normal")
        self._log_box.insert("end", message.rstrip() + "\n")
        self._log_box.see("end")
        self._log_box.configure(state="disabled")
        self.update_idletasks()

    def _apply_single(self, item: DiscoveredParserPatch) -> None:
        self._log(f"--- {item.display_name} ---")
        apply_parser_patch(
            self._manifest_manager,
            item,
            parent=self,
            prompt_for_folder=True,
            log=self._log,
        )

    def _apply_selected(self) -> None:
        selected = [
            item
            for item, var in zip(self._patch_items, self._check_vars)
            if var.get()
        ]
        if not selected:
            messagebox.showinfo("Apply Patches", "Select at least one patch.", parent=self)
            return
        self._log("=== Apply All Patches ===")
        apply_parser_patches(
            self._manifest_manager,
            selected,
            parent=self,
            prompt_for_folder=True,
            log=self._log,
        )


def open_apply_patches_dialog(
    parent: tk.Misc,
    mgr: "ManifestManager",
) -> Optional[ApplyPatchesDialog]:
    """Open the Apply Patches window when manifest parsers expose patches."""
    patches = discover_manifest_parser_patches(mgr)
    if not patches:
        messagebox.showinfo(
            "Apply Patches",
            "No parser project patches are available for the current manifest.",
            parent=parent,
        )
        return None
    dialog = ApplyPatchesDialog(parent, mgr)
    dialog.focus_set()
    return dialog
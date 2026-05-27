"""Shared project patch discovery, search, and application helpers.

This module provides the parser-advertised project patch surface used by Step 9
to list and apply parser-specific file patches against a project's staged
``Translated/`` tree.
"""

from __future__ import annotations

import datetime
import logging
import shutil
import tkinter as tk
from dataclasses import dataclass, field
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk
from typing import Callable, Dict, List, Optional, Sequence, Tuple, TYPE_CHECKING


if TYPE_CHECKING:
    from CherryAI.functions.manifest_manager import ManifestManager


logger = logging.getLogger(__name__)

PatchLog = Callable[[str], None]


@dataclass(frozen=True)
class PatchTestResult:
    """Outcome of testing a patch against a candidate file."""

    status: str  # "ok", "already_applied", "cannot_apply", "error"
    message: str = ""


@dataclass(frozen=True)
class FoundCandidate:
    """A concrete file found during patch candidate search."""

    path: Path
    relative: Path
    size: int
    mtime: float
    source_root: Path  # which root it was found in (Translated/, Original/, lookup/)

    def size_label(self) -> str:
        kb = self.size / 1024
        if kb < 1000:
            return f"{kb:.1f} KB"
        return f"{kb / 1024:.2f} MB"

    def date_label(self) -> str:
        return datetime.datetime.fromtimestamp(self.mtime).strftime("%Y-%m-%d %H:%M")


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
    # Mutually-exclusive alternative group.  Patches sharing the same
    # non-None string are presented as radio-button alternatives in the
    # Apply Patches window — only one member of a group can be applied.
    alternative_group: Optional[str] = None
    # Human-readable label shown as the group heading, e.g. "Wordwrap Method".
    alternative_group_label: Optional[str] = None
    # Optional quick-check callback: does this patch apply cleanly to the file?
    test_target: Optional[Callable[[Path, PatchLog], "PatchTestResult"]] = None
    # Additional files this patch requires beyond the primary target.
    # Each entry is (file_label, relative_candidates_tuple).
    required_companions: tuple[tuple[str, tuple[Path, ...]], ...] = ()


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
    """Return the first matching file for any candidate, or None."""
    def _resolve_candidate_relative(match_path: Path) -> Path:
        """Map a recursive match to the closest canonical candidate relative path."""
        match_parts_lower = tuple(part.lower() for part in match_path.parts)

        # Keep discovered paths under patch* roots verbatim so copied targets
        # preserve the same loose-overlay compartment.
        if match_parts_lower and match_parts_lower[0].startswith("patch"):
            return match_path

        for candidate in candidates:
            candidate_parts = candidate.parts
            if not candidate_parts:
                continue
            candidate_parts_lower = tuple(part.lower() for part in candidate_parts)
            if len(match_parts_lower) < len(candidate_parts_lower):
                continue
            if match_parts_lower[-len(candidate_parts_lower):] == candidate_parts_lower:
                return candidate

        for candidate in candidates:
            if candidate.name.lower() == match_path.name.lower():
                return candidate

        return match_path

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
                resolved_relative = _resolve_candidate_relative(match.relative_to(root))
                return match, resolved_relative
    return None


def _find_all_in_root(
    root: Path,
    candidates: Sequence[Path],
    *,
    recursive: bool,
) -> List[FoundCandidate]:
    """Return ALL matching files in *root* for the given relative candidates."""
    found: List[FoundCandidate] = []
    seen: set[str] = set()

    for relative in candidates:
        candidate = root / relative
        if candidate.is_file():
            key = str(candidate.resolve())
            if key not in seen:
                seen.add(key)
                stat = candidate.stat()
                found.append(FoundCandidate(
                    path=candidate,
                    relative=relative,
                    size=stat.st_size,
                    mtime=stat.st_mtime,
                    source_root=root,
                ))

    if recursive:
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
                    key = str(match.resolve())
                    if key not in seen:
                        seen.add(key)
                        try:
                            rel = match.relative_to(root)
                        except ValueError:
                            rel = relative
                        stat = match.stat()
                        found.append(FoundCandidate(
                            path=match,
                            relative=rel,
                            size=stat.st_size,
                            mtime=stat.st_mtime,
                            source_root=root,
                        ))

    return found


def _get_default_lookup_folder(mgr: "ManifestManager") -> Path:
    """Return the default folder used when prompting for a supplemental lookup root."""
    source_root = Path(str(getattr(mgr, "source_root", "")).strip())
    if source_root.is_absolute():
        return source_root

    if getattr(mgr, "source_mode", "internal") == "external" and str(source_root):
        return source_root

    return mgr.get_project_dir().resolve()


def collect_all_patch_candidates(
    mgr: "ManifestManager",
    patch_info: DiscoveredParserPatch,
) -> List[FoundCandidate]:
    """Return all candidate files from the first compartment that contains matches.

    Search order is Translated/ first, then Original/, then the supplemental
    lookup folder. Once a compartment yields any match, later compartments are
    skipped so the selection dialog stays focused on the best source root.
    """
    candidates = patch_info.patch.relative_candidates
    if not candidates:
        return []

    translated_found = _find_all_in_root(mgr.get_translated_dir(), candidates, recursive=True)
    if translated_found:
        return translated_found

    original_found = _find_all_in_root(mgr.get_original_dir(), candidates, recursive=True)
    if original_found:
        return original_found

    saved_lookup = get_saved_patch_lookup_dir(mgr, patch_info.storage_key)
    if saved_lookup is not None and saved_lookup.is_dir():
        return _find_all_in_root(saved_lookup, candidates, recursive=True)

    return []


def run_patch_test(
    patch_info: DiscoveredParserPatch,
    candidate_path: Path,
    log: PatchLog,
) -> Optional[PatchTestResult]:
    """Run the patch's test callback against *candidate_path*.

    Returns ``None`` if the patch has no test callback defined.
    """
    if patch_info.patch.test_target is None:
        return None
    try:
        return patch_info.patch.test_target(candidate_path, log)
    except Exception as exc:
        logger.exception("Patch test failed: %s", patch_info.display_name)
        return PatchTestResult(status="error", message=f"Test error: {exc}")


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
        initialdir = str(_get_default_lookup_folder(mgr))

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


class FileSelectionDialog(tk.Toplevel):
    """Modal dialog that shows all found candidates for a single patch file.

    The user picks one candidate using a radio button, then either clicks the
    per-row *Apply* / *Test* button or the footer *Apply Selected* button.
    After apply or cancel the caller can inspect ``result``.
    """

    def __init__(
        self,
        parent: tk.Misc,
        mgr: "ManifestManager",
        patch_info: DiscoveredParserPatch,
        candidates: List[FoundCandidate],
        *,
        log: PatchLog,
    ) -> None:
        super().__init__(parent)
        self._mgr = mgr
        self._patch_info = patch_info
        self._candidates = candidates
        self._external_log = log
        self._selected_var = tk.IntVar(value=0)
        self.result: Optional[PatchApplicationResult] = None

        self.title(f"Select File for {patch_info.patch.file_label}")
        self.transient(parent)
        self.grab_set()
        self.resizable(True, True)
        self.minsize(720, 300)
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

        self._build_ui()

    def _build_ui(self) -> None:
        top = ttk.Frame(self, padding=(10, 8, 10, 4))
        top.pack(fill="x")
        ttk.Label(
            top,
            text=f"Multiple candidates found for {self._patch_info.patch.file_label}. "
                 "Select which file to use:",
            wraplength=680,
        ).pack(anchor="w")

        # Scrollable candidate area
        canvas_frame = ttk.Frame(self)
        canvas_frame.pack(fill="both", expand=True, padx=10, pady=(4, 0))

        canvas = tk.Canvas(canvas_frame, borderwidth=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        inner = ttk.Frame(canvas)
        canvas_window = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _on_inner_configure(event: tk.Event) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_canvas_configure(event: tk.Event) -> None:
            canvas.itemconfigure(canvas_window, width=event.width)

        inner.bind("<Configure>", _on_inner_configure)
        canvas.bind("<Configure>", _on_canvas_configure)

        # Header row
        hdr = ttk.Frame(inner)
        hdr.pack(fill="x", pady=(0, 2))
        ttk.Label(hdr, text="", width=3).pack(side="left")
        ttk.Label(hdr, text="Path", width=40, anchor="w", font=("TkDefaultFont", 9, "bold")).pack(side="left", padx=4)
        ttk.Label(hdr, text="Size", width=9, anchor="e", font=("TkDefaultFont", 9, "bold")).pack(side="left", padx=4)
        ttk.Label(hdr, text="Date", width=16, anchor="w", font=("TkDefaultFont", 9, "bold")).pack(side="left", padx=4)

        ttk.Separator(inner, orient="horizontal").pack(fill="x", pady=(0, 4))

        for idx, fc in enumerate(self._candidates):
            self._add_candidate_row(inner, idx, fc)

        # Footer
        footer = ttk.Frame(self, padding=(10, 6))
        footer.pack(fill="x")
        ttk.Button(footer, text="Cancel", command=self._on_cancel).pack(side="right")
        ttk.Button(
            footer,
            text="Apply Selected",
            command=self._on_apply_selected,
        ).pack(side="right", padx=(0, 6))

    def _add_candidate_row(self, parent: ttk.Frame, idx: int, fc: FoundCandidate) -> None:
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=2)

        ttk.Radiobutton(
            row,
            variable=self._selected_var,
            value=idx,
        ).pack(side="left")

        rel = fc.relative.as_posix()
        ttk.Label(row, text=rel, anchor="w", width=40).pack(side="left", padx=4)
        ttk.Label(row, text=fc.size_label(), anchor="e", width=9).pack(side="left", padx=4)
        ttk.Label(row, text=fc.date_label(), anchor="w", width=16).pack(side="left", padx=4)

        has_test = self._patch_info.patch.test_target is not None
        if has_test:
            ttk.Button(
                row,
                text="Test",
                width=6,
                command=lambda i=idx: self._on_test(i),
            ).pack(side="right", padx=(4, 0))

        ttk.Button(
            row,
            text="Apply",
            width=6,
            command=lambda i=idx: self._on_apply(i),
        ).pack(side="right", padx=(4, 0))

    def _resolve_candidate(self, idx: int, log: PatchLog) -> Optional[Path]:
        """Copy the candidate into Translated/ if needed and return the staging path."""
        fc = self._candidates[idx]
        translated_root = self._mgr.get_translated_dir()
        # Already in Translated/
        if fc.source_root == translated_root or str(fc.path).startswith(str(translated_root)):
            return fc.path
        # Need to copy into Translated/
        return _copy_into_translated(self._mgr, fc.path, fc.relative, log)

    def _on_test(self, idx: int) -> None:
        log_lines: List[str] = []
        self._external_log(f"Testing {self._patch_info.patch.file_label} candidate [{idx}]…")
        staged = self._resolve_candidate(idx, log_lines.append)
        if staged is None:
            self._external_log("  Error: could not resolve candidate for test.")
            return
        result = run_patch_test(self._patch_info, staged, log_lines.append)
        for line in log_lines:
            self._external_log(f"  {line}")
        self._external_log(f"  Test result: {result.status}" + (f" — {result.message}" if result.message else ""))

    def _on_apply(self, idx: int) -> None:
        log_lines: List[str] = []
        staged = self._resolve_candidate(idx, log_lines.append)
        for line in log_lines:
            self._external_log(f"  {line}")
        if staged is None:
            self.result = PatchApplicationResult(
                status="failed",
                message="Could not stage candidate file.",
            )
            self.destroy()
            return
        try:
            result = self._patch_info.patch.apply_to_target(staged, self._external_log)
        except Exception as exc:
            logger.exception("Patch apply failed: %s", self._patch_info.display_name)
            result = PatchApplicationResult(status="failed", message=str(exc))
        if result.message:
            self._external_log(result.message)
        self.result = result
        self.destroy()

    def _on_apply_selected(self) -> None:
        self._on_apply(self._selected_var.get())

    def _on_cancel(self) -> None:
        self.result = PatchApplicationResult(
            status="cancelled",
            message="File selection cancelled.",
        )
        self.destroy()


class ApplyPatchesDialog(tk.Toplevel):
    """Modal window for parser project patches.

    Patches that share an ``alternative_group`` are presented as a radio-button
    group (mutually exclusive).  Standalone patches get individual checkboxes.
    File-based patches scan for all matching files before applying and present
    a :class:`FileSelectionDialog` when more than one candidate is found.
    """

    def __init__(self, parent: tk.Misc, mgr: "ManifestManager") -> None:
        super().__init__(parent)
        self._manifest_manager = mgr
        self._patch_items = discover_manifest_parser_patches(mgr)

        # Per-item state tracking
        # For standalone items: BooleanVar (checkbox); index matches _patch_items index
        # For grouped items: only one IntVar per group (radio index within group)
        self._check_vars: List[Optional[tk.BooleanVar]] = []
        # group_id -> (radio_var, list of group items)
        self._alt_groups: Dict[str, Tuple[tk.IntVar, List[int]]] = {}

        self.title("Apply Patches")
        self.transient(parent)
        self.grab_set()
        self.resizable(True, True)
        self.minsize(660, 420)
        self.protocol("WM_DELETE_WINDOW", self.destroy)

        self._build_ui()

    # ------------------------------------------------------------------
    # UI building
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        # --- outer scroll frame so many patches stay manageable ---
        outer = ttk.Frame(self)
        outer.pack(fill="both", expand=True)

        canvas = tk.Canvas(outer, borderwidth=0, highlightthickness=0)
        v_scroll = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=v_scroll.set)
        v_scroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        container = ttk.Frame(canvas, padding=10)
        win_id = canvas.create_window((0, 0), window=container, anchor="nw")

        def _on_configure(event: tk.Event) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_canvas_resize(event: tk.Event) -> None:
            canvas.itemconfigure(win_id, width=event.width)

        container.bind("<Configure>", _on_configure)
        canvas.bind("<Configure>", _on_canvas_resize)

        ttk.Label(
            container,
            text="Parser Project Patches",
            font=("TkDefaultFont", 11, "bold"),
        ).pack(anchor="w", pady=(0, 8))

        patch_frame = ttk.Frame(container)
        patch_frame.pack(fill="x")

        # Separate patches into groups and standalones
        group_order: List[str] = []
        group_items: Dict[str, List[int]] = {}
        standalone: List[int] = []
        for idx, item in enumerate(self._patch_items):
            g = item.patch.alternative_group
            if g:
                if g not in group_items:
                    group_order.append(g)
                    group_items[g] = []
                group_items[g].append(idx)
            else:
                standalone.append(idx)

        # Initialise check_vars list to correct length
        self._check_vars = [None] * len(self._patch_items)

        # Render alternative groups first
        for g in group_order:
            idxs = group_items[g]
            radio_var = tk.IntVar(value=0)
            self._alt_groups[g] = (radio_var, idxs)

            # Determine group label
            group_label = self._patch_items[idxs[0]].patch.alternative_group_label or g
            grp_frame = ttk.LabelFrame(patch_frame, text=f"{group_label} (select one)", padding=6)
            grp_frame.pack(fill="x", pady=(4, 8))

            for radio_idx, item_idx in enumerate(idxs):
                item = self._patch_items[item_idx]
                self._add_patch_row(
                    grp_frame,
                    item,
                    radio_var=radio_var,
                    radio_value=radio_idx,
                )

        # Render standalone patches
        for item_idx in standalone:
            item = self._patch_items[item_idx]
            var = tk.BooleanVar(value=True)
            self._check_vars[item_idx] = var
            self._add_patch_row(patch_frame, item, check_var=var)

        # Log box
        self._log_box = scrolledtext.ScrolledText(self, height=8, wrap="word")
        self._log_box.pack(fill="both", expand=False, padx=10, pady=(4, 0))
        self._log_box.configure(state="disabled")

        # Footer buttons
        footer = ttk.Frame(self, padding=(10, 6))
        footer.pack(fill="x")
        ttk.Button(footer, text="Cancel", command=self.destroy).pack(side="right")
        if len(self._patch_items) > 1:
            ttk.Button(
                footer,
                text="Apply All Patches",
                command=self._apply_selected,
            ).pack(side="right", padx=(0, 8))

    def _add_patch_row(
        self,
        parent: ttk.Frame,
        item: DiscoveredParserPatch,
        *,
        check_var: Optional[tk.BooleanVar] = None,
        radio_var: Optional[tk.IntVar] = None,
        radio_value: int = 0,
    ) -> None:
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=4)

        # Left: checkbox or radio button
        if radio_var is not None:
            ttk.Radiobutton(
                row,
                variable=radio_var,
                value=radio_value,
            ).pack(side="left", padx=(0, 4))
        elif check_var is not None:
            ttk.Checkbutton(row, variable=check_var).pack(side="left", padx=(0, 4))

        # Right: Apply (and optional Test) buttons
        has_test = item.patch.test_target is not None and not item.patch.apply_with_context
        if has_test:
            ttk.Button(
                row,
                text="Test",
                width=6,
                command=lambda i=item: self._test_single(i),
            ).pack(side="right", padx=(4, 0))

        ttk.Button(
            row,
            text="Apply",
            width=8,
            command=lambda i=item: self._apply_single(i),
        ).pack(side="right", padx=(4, 0))

        # Centre: name, description, companion info
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
            wraplength=450,
            justify="left",
        ).pack(anchor="w")

        # Companion file info
        for comp_label, _comp_cands in item.patch.required_companions:
            ttk.Label(
                text_frame,
                text=f"  Also requires: {comp_label}",
                foreground="gray",
                font=("TkDefaultFont", 8),
            ).pack(anchor="w")

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    def _log(self, message: str) -> None:
        self._log_box.configure(state="normal")
        self._log_box.insert("end", message.rstrip() + "\n")
        self._log_box.see("end")
        self._log_box.configure(state="disabled")
        self.update_idletasks()

    # ------------------------------------------------------------------
    # Test helper
    # ------------------------------------------------------------------

    def _test_single(self, item: DiscoveredParserPatch) -> None:
        """Quick-test the patch against available candidates without applying."""
        self._log(f"--- Testing: {item.display_name} ---")
        candidates = collect_all_patch_candidates(self._manifest_manager, item)
        if not candidates:
            self._log("  No candidate files found for test.")
            return
        for fc in candidates:
            self._log(f"  Candidate: {fc.relative.as_posix()} ({fc.size_label()}, {fc.date_label()})")
            result = run_patch_test(item, fc.path, self._log)
            self._log(f"  → {result.status}" + (f": {result.message}" if result.message else ""))

    # ------------------------------------------------------------------
    # Apply helpers
    # ------------------------------------------------------------------

    def _apply_single(self, item: DiscoveredParserPatch) -> None:
        self._log(f"--- {item.display_name} ---")

        # Custom workflows (e.g. Font Patch, Standard UI) bypass file scan
        if item.patch.apply_with_context is not None:
            apply_parser_patch(
                self._manifest_manager,
                item,
                parent=self,
                prompt_for_folder=True,
                log=self._log,
            )
            return

        # File-based patch: scan for all candidates then apply to user-chosen one
        self._apply_file_patch(item)

    def _apply_file_patch(self, item: DiscoveredParserPatch) -> None:
        """Resolve candidate(s) and apply a file-based patch.

        * 0 candidates → prompt for folder, re-scan, then apply or give up
        * 1 candidate  → apply directly (skip selection dialog)
        * >1 candidates → open FileSelectionDialog
        """
        candidates = collect_all_patch_candidates(self._manifest_manager, item)

        if not candidates:
            # Prompt and re-scan
            result = resolve_patch_target(
                self._manifest_manager,
                item,
                parent=self,
                prompt_for_folder=True,
                log=self._log,
            )
            if result.status != "resolved" or result.target_path is None:
                self._log(result.message or "File not found.")
                return
            # Apply to the newly resolved file
            try:
                apply_result = item.patch.apply_to_target(result.target_path, self._log)
            except Exception as exc:
                self._log(f"Error: {exc}")
                return
            if apply_result.message:
                self._log(apply_result.message)
            return

        if len(candidates) == 1:
            # Auto-select the sole candidate
            self._log(f"  Found: {candidates[0].relative.as_posix()} ({candidates[0].size_label()}, {candidates[0].date_label()})")
            staged = self._stage_candidate(candidates[0])
            if staged is None:
                return
            try:
                result = item.patch.apply_to_target(staged, self._log)
            except Exception as exc:
                self._log(f"Error: {exc}")
                return
            if result.message:
                self._log(result.message)
            return

        # Multiple candidates → let the user choose
        dlg = FileSelectionDialog(
            self,
            self._manifest_manager,
            item,
            candidates,
            log=self._log,
        )
        self.wait_window(dlg)
        # result is stored on dlg.result; messages already written to log via callback

    def _stage_candidate(self, fc: FoundCandidate) -> Optional[Path]:
        translated_root = self._manifest_manager.get_translated_dir()
        if str(fc.path).startswith(str(translated_root)):
            return fc.path
        return _copy_into_translated(self._manifest_manager, fc.path, fc.relative, self._log)

    def _collect_active_patches(self) -> List[DiscoveredParserPatch]:
        """Return the patches that should run for 'Apply All Patches'.

        - For alternative groups: the radio-selected member
        - For standalone items: those whose checkbox is ticked
        """
        active: List[DiscoveredParserPatch] = []

        # Add the selected member from each alternative group
        for g, (radio_var, idxs) in self._alt_groups.items():
            selected_radio = radio_var.get()
            if 0 <= selected_radio < len(idxs):
                active.append(self._patch_items[idxs[selected_radio]])

        # Add checked standalone patches
        for idx, item in enumerate(self._patch_items):
            if item.patch.alternative_group:
                continue  # handled above
            var = self._check_vars[idx]
            if var is not None and var.get():
                active.append(item)

        return active

    def _apply_selected(self) -> None:
        selected = self._collect_active_patches()
        if not selected:
            messagebox.showinfo("Apply Patches", "Select at least one patch.", parent=self)
            return
        self._log("=== Apply All Patches ===")
        for item in selected:
            self._apply_single(item)


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
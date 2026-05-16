"""CherryAI GUI - API Log View Dialog.

Non-blocking window that displays structured API log entries with:
- Infinite scrolling text view with color-coded entries
- Search bar for filtering visible entries
- Category filter dropdown (Main Translation / Term Translation / Gender Inference / Other)
- View mode switch (Sent / Received / Both)
- Live updates via subscription to APILogStore
- Human-readable formatting with meta headers and statistics

Architecture note: This dialog handles ONLY display and user interaction.
All log data access goes through APILogStore (functions/api_log.py).
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Any, Dict, List, Optional

from CherryAI.functions import ini_manager
from CherryAI.functions.api_log import (
    LogCategory,
    LogEntry,
    LogStatus,
    build_log_request_ref,
    get_api_log_store,
)
from CherryAI.functions.manifest_manager import ManifestManager
from CherryAI.gui.theme.colors import apply_window_preferences, apply_theme, get_theme

logger = logging.getLogger(__name__)

# --- Colors ----------------------------------------------------------------- #

COLOR_BG = "#E8F4FC"
COLOR_PANEL = "#D6E8F5"
COLOR_INPUT = "#FFFFFF"
COLOR_TEXT = "#1A3A5C"
COLOR_TEXT_SEC = "#4A6A8C"
COLOR_BORDER = "#C5DCF0"
COLOR_ACCENT = "#5BA4D9"
COLOR_SUCCESS = "#6BBF8E"          # Green — All Green
COLOR_RECOVERED = "#F0C94B"        # Yellow — Recovered
COLOR_CONTENT_WARNING = "#D68B4C"  # Amber — Unsafe/refused content
COLOR_FAILED = "#E07070"           # Red — Not Recovered
COLOR_HEADER = "#34495E"           # Dark header text
COLOR_META = "#4A6A8C"            # Meta information
COLOR_SENT_BG = "#F0F7FF"         # Sent block background
COLOR_RECV_BG = "#F0FFF4"         # Received block background
COLOR_SEPARATOR = "#C5DCF0"       # Separator line

# --- Category labels -------------------------------------------------------- #

CATEGORY_LABELS: Dict[str, str] = {
    "all": "All Categories",
    LogCategory.MAIN_TRANSLATION: "Main Translation",
    LogCategory.TERM_TRANSLATION: "Term Translation",
    LogCategory.GENDER_INFERENCE: "Gender Inference",
    LogCategory.OTHER: "Other",
}

STATUS_LABELS: Dict[str, str] = {
    "all": "All Statuses",
    LogStatus.CONTENT_WARNING.value: "Content Warning Only",
    LogStatus.FAILED.value: "Failed Only",
    LogStatus.RECOVERED.value: "Recovered Only",
    LogStatus.SUCCESS.value: "Successful Only",
    LogStatus.PENDING.value: "Pending Only",
}

VIEW_MODES = ["Both", "Sent", "Received"]
DISPLAY_LIMIT_OPTIONS = ("All", "1000", "2500", "5000", "Nothing")
_DISPLAY_LIMIT_KEY = "api_log_display_limit"


def normalize_api_log_display_limit(value: str) -> str:
    """Return the canonical display-limit label used by the dialog."""
    normalized = (value or "").strip().lower()
    if normalized == "nothing":
        return "Nothing"
    if normalized in {"1000", "2500", "5000"}:
        return normalized
    return "All"


def parse_api_log_display_limit(value: str) -> Optional[int]:
    """Convert a display-limit label into a per-block line limit."""
    canonical = normalize_api_log_display_limit(value)
    if canonical == "All":
        return None
    if canonical == "Nothing":
        return 0
    return int(canonical)


def resolve_status_filter(label: str) -> Optional[LogStatus]:
    """Map a status dropdown label to the corresponding log status."""
    for key, value in STATUS_LABELS.items():
        if value != label:
            continue
        if key == "all":
            return None
        return LogStatus(key)
    return None


class APILogViewDialog(tk.Toplevel):
    """Non-blocking API log viewer window.

    Displays all API log entries for the current project with filtering,
    searching, and color-coded formatting. Subscribes to the APILogStore
    for live updates as new API calls are made.
    """

    _ROOT_ATTR = "_api_log_dialog"

    @classmethod
    def open_or_focus(
        cls,
        parent: tk.Misc,
        manifest_manager: ManifestManager,
        *,
        request_refs: Optional[List[str]] = None,
        search_text: Optional[str] = None,
        view_mode: Optional[str] = None,
    ) -> "APILogViewDialog":
        """Open the API Log dialog or bring the existing one to the front."""
        root = parent.winfo_toplevel()
        existing = getattr(root, cls._ROOT_ATTR, None)
        if isinstance(existing, cls):
            try:
                if existing.winfo_exists():
                    existing.apply_external_filters(
                        request_refs=request_refs,
                        search_text=search_text,
                        view_mode=view_mode,
                    )
                    existing._present()
                    return existing
            except tk.TclError:
                pass

        dialog = cls(root, manifest_manager)
        dialog._instance_owner = root
        setattr(root, cls._ROOT_ATTR, dialog)
        dialog.apply_external_filters(
            request_refs=request_refs,
            search_text=search_text,
            view_mode=view_mode,
        )
        dialog._present()
        return dialog

    def __init__(
        self,
        parent: tk.Tk,
        manifest_manager: ManifestManager,
    ) -> None:
        super().__init__(parent)
        self._instance_owner: Optional[tk.Misc] = None
        self._parent = parent
        self._mgr = manifest_manager
        self._store = get_api_log_store()

        # Filter state
        self._category_filter: Optional[str] = None  # None = all
        self._status_filter: Optional[LogStatus] = None
        self._view_mode: str = "Both"
        self._search_text: str = ""
        self._request_refs: Optional[set[str]] = None
        self._display_limit_label = normalize_api_log_display_limit(
            str(ini_manager.get_log_setting(_DISPLAY_LIMIT_KEY, "All") or "All"),
        )
        self._content_display_limit = parse_api_log_display_limit(
            self._display_limit_label,
        )

        # Rendered entry count (for incremental rendering)
        self._rendered_count = 0

        # Window setup — NON-BLOCKING (no grab_set)
        self.title("API Log")
        self.minsize(640, 400)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        apply_window_preferences(
            self,
            parent=parent,
            window_key="APILogViewDialog",
            default_geometry="960x700",
        )

        self._build_toolbar()
        self._build_log_view()
        self._build_status_bar()
        self.refresh_theme()
        self._render_all()

        # Subscribe for live updates
        self._store.subscribe(self._on_new_entry)

        # Ensure window is visible above other windows on open
        self.lift()

    def _present(self) -> None:
        """Bring the dialog to the foreground."""
        try:
            self.deiconify()
            self.lift()
            self.focus_force()
        except tk.TclError:
            logger.debug("API Log dialog could not be presented", exc_info=True)

    def _clear_root_reference(self) -> None:
        """Remove this dialog from the root window registry if registered."""
        owner = self._instance_owner
        if owner is None:
            return
        if getattr(owner, self._ROOT_ATTR, None) is self:
            setattr(owner, self._ROOT_ATTR, None)
        self._instance_owner = None

    def refresh_theme(self) -> None:
        """Reapply the active theme to the dialog and text tags."""
        theme = get_theme()
        apply_theme(self, theme=theme)

        if hasattr(self, "_text"):
            self._text.tag_configure(
                "header_success", foreground=theme.accent_success,
            )
            self._text.tag_configure(
                "header_recovered", foreground=theme.accent_warning,
            )
            self._text.tag_configure(
                "header_content_warning", foreground=theme.accent_warning,
            )
            self._text.tag_configure(
                "header_failed", foreground=theme.accent_error,
            )
            self._text.tag_configure(
                "header_pending", foreground=theme.text_secondary,
            )
            self._text.tag_configure(
                "meta", foreground=theme.text_secondary,
            )
            self._text.tag_configure(
                "label", foreground=theme.header_text,
            )
            self._text.tag_configure(
                "content", foreground=theme.text_primary,
            )
            self._text.tag_configure(
                "separator", foreground=theme.border_light,
            )
            self._text.tag_configure(
                "sent_label", foreground=theme.accent_info,
            )
            self._text.tag_configure(
                "recv_label", foreground=theme.accent_success,
            )
            self._text.tag_configure(
                "error", foreground=theme.accent_error,
            )
            self._text.tag_configure(
                "search_highlight",
                background=theme.highlight_bg,
                foreground=theme.highlight_fg,
            )

    def apply_external_filters(
        self,
        *,
        request_refs: Optional[List[str]] = None,
        search_text: Optional[str] = None,
        view_mode: Optional[str] = None,
    ) -> None:
        """Apply request-ref or search targeting from another shared window."""
        self._request_refs = None
        if request_refs is not None:
            self._request_refs = {
                ref for ref in request_refs if ref
            } or None

        if search_text is not None:
            self._search_var.set(search_text)
            self._search_text = search_text.strip()

        if view_mode is not None and view_mode in VIEW_MODES:
            self._view_var.set(view_mode)
            self._view_mode = view_mode

        if hasattr(self, "_text"):
            self._render_all()

    # ------------------------------------------------------------------ #
    #  UI Construction                                                     #
    # ------------------------------------------------------------------ #

    def _build_toolbar(self) -> None:
        """Build the toolbar with search, filter, and view mode controls."""
        toolbar = tk.Frame(self, bg=COLOR_PANEL, padx=8, pady=6)
        toolbar.pack(fill="x", side="top")

        # Search
        tk.Label(
            toolbar, text="Search:", bg=COLOR_PANEL, fg=COLOR_TEXT,
            font=("Segoe UI", 9),
        ).pack(side="left", padx=(0, 4))

        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", self._on_search_changed)
        search_entry = tk.Entry(
            toolbar, textvariable=self._search_var, width=28,
            bg=COLOR_INPUT, fg=COLOR_TEXT, relief="flat",
            highlightthickness=1, highlightcolor=COLOR_ACCENT,
            highlightbackground=COLOR_BORDER,
        )
        search_entry.pack(side="left", padx=(0, 12))

        # Category filter dropdown
        tk.Label(
            toolbar, text="Category:", bg=COLOR_PANEL, fg=COLOR_TEXT,
            font=("Segoe UI", 9),
        ).pack(side="left", padx=(0, 4))

        self._category_var = tk.StringVar(value="All Categories")
        category_values = list(CATEGORY_LABELS.values())
        category_combo = ttk.Combobox(
            toolbar, textvariable=self._category_var,
            values=category_values, state="readonly", width=18,
        )
        category_combo.pack(side="left", padx=(0, 12))
        category_combo.bind("<<ComboboxSelected>>", self._on_category_changed)

        tk.Label(
            toolbar, text="Status:", bg=COLOR_PANEL, fg=COLOR_TEXT,
            font=("Segoe UI", 9),
        ).pack(side="left", padx=(0, 4))

        self._status_var = tk.StringVar(value="All Statuses")
        status_combo = ttk.Combobox(
            toolbar,
            textvariable=self._status_var,
            values=list(STATUS_LABELS.values()),
            state="readonly",
            width=16,
        )
        status_combo.pack(side="left", padx=(0, 12))
        status_combo.bind("<<ComboboxSelected>>", self._on_status_changed)

        # View mode switch
        tk.Label(
            toolbar, text="View:", bg=COLOR_PANEL, fg=COLOR_TEXT,
            font=("Segoe UI", 9),
        ).pack(side="left", padx=(0, 4))

        self._view_var = tk.StringVar(value="Both")
        for mode in VIEW_MODES:
            rb = tk.Radiobutton(
                toolbar, text=mode, variable=self._view_var, value=mode,
                bg=COLOR_PANEL, fg=COLOR_TEXT, selectcolor=COLOR_ACCENT,
                activebackground=COLOR_PANEL, font=("Segoe UI", 9),
                command=self._on_view_mode_changed,
            )
            rb.pack(side="left", padx=(0, 4))

        tk.Label(
            toolbar, text="Display:", bg=COLOR_PANEL, fg=COLOR_TEXT,
            font=("Segoe UI", 9),
        ).pack(side="left", padx=(8, 4))

        self._display_limit_var = tk.StringVar(value=self._display_limit_label)
        self._display_limit_var.trace_add("write", self._on_display_limit_changed)
        display_spinbox = ttk.Spinbox(
            toolbar,
            textvariable=self._display_limit_var,
            values=DISPLAY_LIMIT_OPTIONS,
            state="readonly",
            width=8,
            wrap=False,
        )
        display_spinbox.pack(side="left", padx=(0, 12))

        # Clear button (right side)
        clear_btn = tk.Button(
            toolbar, text="Clear Log", command=self._on_clear,
            bg=COLOR_PANEL, fg=COLOR_TEXT, relief="flat",
            activebackground=COLOR_BORDER, font=("Segoe UI", 9),
            cursor="hand2",
        )
        clear_btn.pack(side="right", padx=(4, 0))

    def _build_log_view(self) -> None:
        """Build the main scrollable log text area."""
        container = tk.Frame(self, bg=COLOR_BG)
        container.pack(fill="both", expand=True, padx=4, pady=4)

        # Scrollbar
        scrollbar = tk.Scrollbar(container, orient="vertical")
        scrollbar.pack(side="right", fill="y")

        # Text widget for log display
        self._text = tk.Text(
            container,
            wrap="word",
            bg=COLOR_INPUT,
            fg=COLOR_TEXT,
            font=("Consolas", 9),
            relief="flat",
            highlightthickness=1,
            highlightcolor=COLOR_ACCENT,
            highlightbackground=COLOR_BORDER,
            yscrollcommand=scrollbar.set,
            state="disabled",
            padx=8,
            pady=4,
            spacing1=2,
            spacing3=2,
        )
        self._text.pack(fill="both", expand=True)
        scrollbar.config(command=self._text.yview)

        # Configure text tags for styling
        self._text.tag_configure(
            "header_success", foreground=COLOR_SUCCESS,
            font=("Segoe UI", 10, "bold"),
        )
        self._text.tag_configure(
            "header_recovered", foreground=COLOR_RECOVERED,
            font=("Segoe UI", 10, "bold"),
        )
        self._text.tag_configure(
            "header_content_warning", foreground=COLOR_CONTENT_WARNING,
            font=("Segoe UI", 10, "bold"),
        )
        self._text.tag_configure(
            "header_failed", foreground=COLOR_FAILED,
            font=("Segoe UI", 10, "bold"),
        )
        self._text.tag_configure(
            "header_pending", foreground=COLOR_META,
            font=("Segoe UI", 10, "bold"),
        )
        self._text.tag_configure(
            "meta", foreground=COLOR_META,
            font=("Segoe UI", 9, "italic"),
        )
        self._text.tag_configure(
            "label", foreground=COLOR_HEADER,
            font=("Segoe UI", 9, "bold"),
        )
        self._text.tag_configure(
            "content", foreground=COLOR_TEXT,
            font=("Consolas", 9),
        )
        self._text.tag_configure(
            "separator", foreground=COLOR_SEPARATOR,
            font=("Consolas", 8),
        )
        self._text.tag_configure(
            "sent_label", foreground="#2C6FAC",
            font=("Segoe UI", 9, "bold"),
        )
        self._text.tag_configure(
            "recv_label", foreground="#2E7D4F",
            font=("Segoe UI", 9, "bold"),
        )
        self._text.tag_configure(
            "error", foreground=COLOR_FAILED,
            font=("Consolas", 9, "bold"),
        )
        self._text.tag_configure(
            "search_highlight",
            background="#FFEB3B",
            foreground="#000000",
        )

    def _build_status_bar(self) -> None:
        """Build the bottom status bar showing entry count."""
        self._status_frame = tk.Frame(self, bg=COLOR_PANEL, padx=8, pady=4)
        self._status_frame.pack(fill="x", side="bottom")

        self._status_label = tk.Label(
            self._status_frame, text="0 entries", bg=COLOR_PANEL,
            fg=COLOR_TEXT_SEC, font=("Segoe UI", 9),
        )
        self._status_label.pack(side="left")

        self._token_label = tk.Label(
            self._status_frame, text="", bg=COLOR_PANEL,
            fg=COLOR_TEXT_SEC, font=("Segoe UI", 9),
        )
        self._token_label.pack(side="right")

    # ------------------------------------------------------------------ #
    #  Rendering                                                           #
    # ------------------------------------------------------------------ #

    def _get_filtered_entries(self) -> List[LogEntry]:
        """Get entries matching current filter/search settings."""
        entries = self._store.get_filtered(
            category=self._category_filter,
            status=self._status_filter,
            search_text=self._search_text or None,
            view_mode=self._view_mode.lower(),
        )
        if not self._request_refs:
            return entries

        matched: List[LogEntry] = []
        for entry in entries:
            if build_log_request_ref(entry, self._store.log_path) in self._request_refs:
                matched.append(entry)
        return matched

    def _render_all(self) -> None:
        """Clear and re-render all matching entries."""
        self._text.configure(state="normal")
        self._text.delete("1.0", "end")
        self._rendered_count = 0

        entries = self._get_filtered_entries()
        for entry in entries:
            self._render_entry(entry)
            self._rendered_count += 1

        self._text.configure(state="disabled")
        self._update_status(entries)

        # Apply search highlights
        if self._search_text:
            self._apply_search_highlights()

    def _render_entry(self, entry: LogEntry) -> None:
        """Render a single log entry into the text widget.

        Formats the entry with a colored header, meta information,
        and sent/received content blocks.
        """
        # Status tag for header color
        status_tag = {
            LogStatus.SUCCESS: "header_success",
            LogStatus.RECOVERED: "header_recovered",
            LogStatus.CONTENT_WARNING: "header_content_warning",
            LogStatus.FAILED: "header_failed",
            LogStatus.PENDING: "header_pending",
        }.get(entry.status, "header_pending")

        # Status icon
        status_icon = {
            LogStatus.SUCCESS: "\u2714",    # ✔
            LogStatus.RECOVERED: "\u26A0",  # ⚠
            LogStatus.CONTENT_WARNING: "\u26A0",  # ⚠
            LogStatus.FAILED: "\u2718",     # ✘
            LogStatus.PENDING: "\u2022",    # •
        }.get(entry.status, "\u2022")

        # Category display
        cat_label = CATEGORY_LABELS.get(entry.category, entry.category)

        # Header line
        self._text.insert("end", f"{status_icon} ", status_tag)
        self._text.insert(
            "end",
            f"[{entry.timestamp}]  {cat_label}  —  "
            f"{entry.status.upper()}",
            status_tag,
        )
        if entry.attempt > 1 or entry.max_attempts > 1:
            self._text.insert(
                "end",
                f"  (attempt {entry.attempt}/{entry.max_attempts})",
                "meta",
            )
        self._text.insert("end", "\n")

        view = self._view_mode.lower()

        # Sent block
        if entry.sent and view in ("both", "sent"):
            self._render_sent_block(entry)

        # Received block
        if entry.received and view in ("both", "received"):
            self._render_received_block(entry)

        # Separator
        self._text.insert("end", "\u2500" * 80 + "\n\n", "separator")

    def _render_sent_block(self, entry: LogEntry) -> None:
        """Render the Sent section of an entry."""
        s = entry.sent
        self._text.insert("end", "  \u25B6 Sent Settings\n", "sent_label")

        meta_parts: List[str] = []
        if s.model:
            meta_parts.append(f"Model: {s.model}")
        if s.provider:
            meta_parts.append(f"Provider: {s.provider}")
        if s.temperature is not None:
            meta_parts.append(f"Temp: {s.temperature}")
        if s.chunk_index is not None and s.total_chunks is not None:
            meta_parts.append(f"Chunk: {s.chunk_index + 1}/{s.total_chunks}")
        if s.line_count is not None:
            meta_parts.append(f"Lines: {s.line_count}")
        if s.extra:
            for k, v in s.extra.items():
                meta_parts.append(f"{k}: {v}")

        if meta_parts:
            self._text.insert("end", "    " + "  |  ".join(meta_parts) + "\n", "meta")

        if s.system_prompt:
            self._text.insert("end", "    System Prompt:\n", "label")
            self._render_wrapped_content(s.system_prompt, indent=6)

        if s.user_content:
            self._text.insert("end", "    User Content:\n", "label")
            self._render_wrapped_content(s.user_content, indent=6)

    def _render_received_block(self, entry: LogEntry) -> None:
        """Render the Received section of an entry."""
        r = entry.received
        self._text.insert("end", "  \u25C0 Received Statistics\n", "recv_label")

        # Token stats
        stat_parts: List[str] = []
        if r.prompt_tokens:
            stat_parts.append(f"Prompt: {r.prompt_tokens}")
        if r.completion_tokens:
            stat_parts.append(f"Completion: {r.completion_tokens}")
        if r.total_tokens:
            stat_parts.append(f"Total: {r.total_tokens}")
        if r.cached_tokens:
            stat_parts.append(f"Cached: {r.cached_tokens}")
        if r.reasoning_tokens:
            stat_parts.append(f"Reasoning: {r.reasoning_tokens}")
        if r.duration_ms:
            if r.duration_ms >= 1000:
                stat_parts.append(f"Duration: {r.duration_ms / 1000:.2f}s")
            else:
                stat_parts.append(f"Duration: {r.duration_ms}ms")
        if r.finish_reason:
            stat_parts.append(f"Finish: {r.finish_reason}")

        if stat_parts:
            self._text.insert(
                "end", "    " + "  |  ".join(stat_parts) + "\n", "meta",
            )

        if r.error_message:
            self._text.insert("end", "    Error: ", "label")
            self._text.insert("end", r.error_message + "\n", "error")

        if r.content:
            self._text.insert("end", "    Response Content:\n", "label")
            self._render_wrapped_content(r.content, indent=6)

        if r.extra:
            for k, v in r.extra.items():
                self._text.insert("end", f"    {k}: ", "label")
                self._text.insert("end", f"{v}\n", "content")

    def _render_wrapped_content(self, text: str, indent: int = 4) -> None:
        """Render content text with proper indentation."""
        prefix = " " * indent
        line_limit = self._content_display_limit
        if line_limit == 0:
            self._text.insert(
                "end",
                f"{prefix}[hidden by display limit]\n",
                "meta",
            )
            return

        lines = text.split("\n")
        visible_lines = lines if line_limit is None else lines[:line_limit]
        for line in visible_lines:
            self._text.insert("end", f"{prefix}{line}\n", "content")

        if line_limit is not None and len(lines) > line_limit:
            remaining = len(lines) - line_limit
            self._text.insert(
                "end",
                f"{prefix}... ({remaining} more lines hidden)\n",
                "meta",
            )

    def _apply_search_highlights(self) -> None:
        """Highlight search matches in the text widget."""
        self._text.tag_remove("search_highlight", "1.0", "end")
        if not self._search_text:
            return

        search_lower = self._search_text.lower()
        start = "1.0"
        while True:
            pos = self._text.search(
                search_lower, start, stopindex="end", nocase=True,
            )
            if not pos:
                break
            end_pos = f"{pos}+{len(search_lower)}c"
            self._text.tag_add("search_highlight", pos, end_pos)
            start = end_pos

    def _update_status(
        self, entries: Optional[List[LogEntry]] = None,
    ) -> None:
        """Update the status bar with entry count and token totals."""
        if entries is None:
            entries = self._get_filtered_entries()

        total = len(self._store.entries)
        shown = len(entries)

        if shown == total:
            self._status_label.configure(text=f"{total} entries")
        else:
            self._status_label.configure(
                text=f"{shown} / {total} entries shown",
            )

        # Aggregate token totals
        prompt_total = 0
        completion_total = 0
        for e in entries:
            if e.received:
                prompt_total += e.received.prompt_tokens or 0
                completion_total += e.received.completion_tokens or 0

        if prompt_total or completion_total:
            self._token_label.configure(
                text=(
                    f"Tokens — Prompt: {prompt_total:,}  "
                    f"Completion: {completion_total:,}  "
                    f"Total: {prompt_total + completion_total:,}"
                ),
            )
        else:
            self._token_label.configure(text="")

    # ------------------------------------------------------------------ #
    #  Event handlers                                                      #
    # ------------------------------------------------------------------ #

    def _on_search_changed(self, *_args: Any) -> None:
        """Handle search text change."""
        self._search_text = self._search_var.get().strip()
        self._render_all()

    def _on_category_changed(self, _event: Any = None) -> None:
        """Handle category filter change."""
        selected = self._category_var.get()
        # Reverse-lookup from label to category key
        self._category_filter = None
        for key, label in CATEGORY_LABELS.items():
            if label == selected and key != "all":
                self._category_filter = key
                break
        self._render_all()

    def _on_status_changed(self, _event: Any = None) -> None:
        """Handle status filter change."""
        self._status_filter = resolve_status_filter(self._status_var.get())
        self._render_all()

    def _on_view_mode_changed(self) -> None:
        """Handle view mode switch change."""
        self._view_mode = self._view_var.get()
        self._render_all()

    def _on_display_limit_changed(self, *_args: Any) -> None:
        """Handle content display-limit changes."""
        current = self._display_limit_var.get()
        canonical = normalize_api_log_display_limit(current)
        if current != canonical:
            self._display_limit_var.set(canonical)
            return

        self._display_limit_label = canonical
        self._content_display_limit = parse_api_log_display_limit(canonical)
        ini_manager.set_log_setting(_DISPLAY_LIMIT_KEY, canonical)
        self._render_all()

    def _on_new_entry(self, entry: LogEntry) -> None:
        """Handle new entry from APILogStore subscription.

        Called from the thread that produced the log entry, so we
        schedule the UI update on the main thread via after().
        """
        try:
            self.after(0, self._append_if_matches, entry)
        except tk.TclError:
            # Window was destroyed
            pass

    def _append_if_matches(self, entry: LogEntry) -> None:
        """Append a new entry if it matches current filters."""
        # Check category filter
        if self._category_filter and entry.category != self._category_filter:
            self._update_status()
            return

        if self._status_filter and entry.status != self._status_filter.value:
            self._update_status()
            return

        # Check search filter
        if self._search_text:
            search_lower = self._search_text.lower()
            entry_text = _entry_to_searchable(entry)
            if search_lower not in entry_text.lower():
                self._update_status()
                return

        # Check view mode — skip if no content for that mode
        view = self._view_mode.lower()
        if view == "sent" and not entry.sent:
            self._update_status()
            return
        if view == "received" and not entry.received:
            self._update_status()
            return

        # Append to display
        self._text.configure(state="normal")

        # Auto-scroll if user was at the bottom
        was_at_bottom = self._text.yview()[1] >= 0.98

        self._render_entry(entry)
        self._rendered_count += 1

        self._text.configure(state="disabled")

        if was_at_bottom:
            self._text.see("end")

        if self._search_text:
            self._apply_search_highlights()

        self._update_status()

    def _on_clear(self) -> None:
        """Clear all log entries."""
        self._store.clear()
        self._render_all()

    def _on_close(self) -> None:
        """Handle window close."""
        try:
            self._store.unsubscribe(self._on_new_entry)
        except ValueError:
            pass
        self.destroy()

    def destroy(self) -> None:
        """Destroy the dialog and clear any registered root reference."""
        self._clear_root_reference()
        try:
            super().destroy()
        except tk.TclError:
            pass


# --- Helpers ---------------------------------------------------------------- #

def _entry_to_searchable(entry: LogEntry) -> str:
    """Convert an entry to a flat searchable string."""
    parts: List[str] = [
        entry.category,
        entry.status,
        entry.timestamp,
    ]
    if entry.sent:
        s = entry.sent
        parts.extend([
            s.model or "",
            s.provider or "",
            s.system_prompt or "",
            s.user_content or "",
        ])
    if entry.received:
        r = entry.received
        parts.extend([
            r.content or "",
            r.error_message or "",
        ])
    return " ".join(parts)

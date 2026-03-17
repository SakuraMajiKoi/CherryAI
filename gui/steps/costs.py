"""CherryAI GUI v2 Costs Step.

Third workflow tab for cost and time estimation based on lines and models.
Displays token counts, cost projections, and savings from preprocessing.

TASK 16.8: Integrated with chunker_adapter for:
- Accurate token counting via functions/chunker.py
- Rate limit awareness via functions/rate_limiter.py
- Adaptive chunk sizing recommendations via functions/chunk_optimizer.py
"""

from __future__ import annotations

import logging
import math
import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple
import tkinter as tk
from tkinter import ttk, messagebox

from CherryAI.gui.components.table import ColumnDef, SharedTable, TableRow
from CherryAI.gui.steps.base import BaseStep
from CherryAI.gui.theme.colors import THEME

# Per-model settings persistence (Task 4)
from CherryAI.functions.api_config import (
    get_model_settings,
    set_model_settings,
)

# TASK 25.1: Import manifest field helpers for saving/loading analysis results
from CherryAI.functions.manifest_fields import (
    get_all_lines_resolved,
    save_int_field,
    load_int_field,
    save_float_field,
    load_float_field,
)

# Import pricing from centralized config (TASK 16.4)
from CherryAI.functions.config import (
    DEFAULT_PRICING_MODEL,
    OUTPUT_TOKEN_MULTIPLIER,
    get_all_model_pricing,
    get_model_pricing,
    get_model_names,
    get_model_display_name,
    estimate_cost as config_estimate_cost,
)

# Import chunker adapter functions (TASK 16.8)
# count_tokens is the authoritative implementation - no wrapper needed
from CherryAI.gui.helpers.chunker_adapter import (
    count_tokens,
    count_tokens_batch,
    is_tiktoken_available,
    estimate_rate_limit_time as chunker_estimate_rate_limit_time,
    get_model_rate_limits,
    estimate_time_for_model,
    chunk_lines,
    estimate_chunks,
    get_optimizer_recommendation,
    DEFAULT_MAX_LINES,
    DEFAULT_RPM,
)

# Import prompt adapter for prompt token estimation
from CherryAI.gui.helpers.prompt_adapter import (
    build_prompt_preview,
    build_full_system_prompt,
    gather_prompt_data,
    build_request_prompt,
)

if TYPE_CHECKING:
    from CherryAI.gui.state.store import SessionState
    from CherryAI.functions.manifest_manager import ManifestManager

logger = logging.getLogger(__name__)



@dataclass
class FormationResult:
    """Result from the 4-step formation pipeline.

    Attributes:
        num_requests: Number of translation requests.
        request_line_lists: Per-request translatable line texts
            (for per-chunk prompt overhead calculation).
    """

    num_requests: int
    request_line_lists: List[List[str]]


@dataclass
class EstimationResult:
    """Result of a token/cost estimation."""

    input_tokens: int
    output_tokens: int
    input_cost: float
    output_cost: float
    total_cost: float
    token_method: str
    prompt_cost: float = 0.0  # Non-cached prompt portion cost
    cached_input_cost: float = 0.0  # Cached portion cost
    content_tokens: int = 0  # Line-content tokens only (no prompt)
    prompt_tokens: int = 0  # Total prompt overhead across all requests
    cached_tokens: int = 0  # Prompt tokens that benefit from caching
    num_requests: int = 0  # Number of API requests for this side


@dataclass
class ComparisonResult:
    """Comparison between original and preprocessed estimation."""

    original: EstimationResult
    preprocessed: EstimationResult
    tokens_saved: int
    cost_saved: float
    savings_percent: float


# count_tokens imported directly from chunker_adapter - no wrapper needed

# Cache hit rate for prompt caching.  Approximately 80 % of requests
# after the first benefit from cached static prompt tokens (§5.2 slots
# 1-7b).  Dynamic per-chunk sections (slots 8-10) are never cached.
CACHE_HIT_RATE = 0.80


def _ceil_to_cents(x: float) -> float:
    """Round *up* to the next cent (e.g. $0.003 → $0.01).

    A tiny epsilon is subtracted so that exact-cent values like $0.05
    are not bumped to $0.06 by floating-point noise.
    """
    return math.ceil(x * 100.0 - 1e-12) / 100.0


def _fmt_cost(v: float) -> str:
    """Format a cost value, ceiling to the next cent."""
    return f"${_ceil_to_cents(v):.2f}"


def estimate_cost(
    input_tokens: int,
    output_tokens: int,
    model_id: str = DEFAULT_PRICING_MODEL,
) -> Dict[str, float]:
    """Estimate cost for tokens using model pricing.

    Args:
        input_tokens: Number of input tokens.
        output_tokens: Number of output tokens.
        model_id: Model ID for pricing lookup.

    Returns:
        Dict with input_usd, output_usd, total_usd.
    """
    pricing = get_model_pricing(model_id)
    input_rate = pricing["input"]
    output_rate = pricing["output"]

    input_cost = (input_tokens / 1_000_000) * input_rate
    output_cost = (output_tokens / 1_000_000) * output_rate

    return {
        "input_usd": round(_ceil_to_cents(input_cost), 2),
        "output_usd": round(_ceil_to_cents(output_cost), 2),
        "total_usd": round(_ceil_to_cents(input_cost + output_cost), 2),
    }


def estimate_rate_limit_time(
    total_requests: int,
    rate_limit_rpm: int = DEFAULT_RPM,
    avg_request_time_sec: float = 2.0,
    concurrent_requests: int = 1,
    total_output_tokens: int = 0,
    token_speed: int = 50,
) -> Dict[str, Any]:
    """Estimate time to complete all requests with rate limiting.

    Uses chunker_adapter which wraps functions/rate_limiter.py for
    model-aware rate limit calculations.

    Args:
        total_requests: Number of API requests.
        rate_limit_rpm: Requests per minute limit.
        avg_request_time_sec: Average time per request.
        concurrent_requests: Max parallel API calls allowed.
        total_output_tokens: Total output tokens to generate.
        token_speed: Tokens per second for the model (default 50).

    Returns:
        Dict with time estimates including formatted string.
    """
    # Use chunker adapter for accurate estimation
    result = chunker_estimate_rate_limit_time(
        total_requests=total_requests,
        rate_limit_rpm=rate_limit_rpm,
        include_buffer=True,
        concurrent_requests=concurrent_requests,
        total_output_tokens=total_output_tokens,
        token_speed=token_speed,
    )

    # Convert to expected format (backward compatible)
    total_time_sec = result.estimated_seconds

    # Also factor in average request time if significant
    request_time = total_requests * avg_request_time_sec
    total_time_sec = max(total_time_sec, request_time)

    return {
        "total_seconds": total_time_sec,
        "total_minutes": total_time_sec / 60,
        "formatted": _format_time(total_time_sec),
    }


def _format_time(seconds: float) -> str:
    """Format seconds as human-readable time."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins}m {secs}s"
    else:
        hours = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        return f"{hours}h {mins}m"


class EstimationProgressDialog(tk.Toplevel):
    """Non-blocking progress dialog shown during cost estimation.

    Opens as a floating Toplevel window.  The estimation thread posts
    step updates via the owning widget's ``after()`` scheduler so the
    dialog updates safely on the main thread without blocking it.

    Usage::

        dlg = EstimationProgressDialog(parent)
        # Inside background thread:
        parent.after(0, lambda: dlg.update_step(2))
        # When done:
        parent.after(0, dlg.close)
    """

    STEPS: List[str] = [
        "Preparing lines…",
        "Building request formation (Original)…",
        "Building request formation (Preprocessed)…",
        "Counting tokens (Original)…",
        "Counting tokens (Preprocessed)…",
        "Applying pricing & cache adjustments…",
        "Updating display…",
    ]

    def __init__(self, parent: tk.Widget) -> None:
        super().__init__(parent)
        self.title("Estimating costs…")
        self.resizable(False, False)
        self.transient(parent.winfo_toplevel())

        # Prevent the dialog from being closed mid-estimation by the user
        self.protocol("WM_DELETE_WINDOW", lambda: None)

        # --- Layout ---
        frame = ttk.Frame(self, padding=16)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="Estimating costs", font=("TkDefaultFont", 11, "bold")).pack(anchor="w")
        ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=(6, 10))

        self._step_label = ttk.Label(frame, text=self.STEPS[0], width=46)
        self._step_label.pack(anchor="w", pady=(0, 6))

        self._progress = ttk.Progressbar(
            frame,
            mode="determinate",
            maximum=len(self.STEPS),
            value=0,
            length=320,
        )
        self._progress.pack(fill="x")

        # Step list — all greyed out initially
        self._step_items: List[ttk.Label] = []
        step_frame = ttk.Frame(frame)
        step_frame.pack(fill="x", pady=(10, 0))
        for text in self.STEPS:
            lbl = ttk.Label(step_frame, text=f"  ○  {text}", foreground="#888888")
            lbl.pack(anchor="w")
            self._step_items.append(lbl)

        # Centre over parent
        self.update_idletasks()
        pw = parent.winfo_toplevel()
        x = pw.winfo_rootx() + (pw.winfo_width() - self.winfo_width()) // 2
        y = pw.winfo_rooty() + (pw.winfo_height() - self.winfo_height()) // 3
        self.geometry(f"+{x}+{y}")

    # ------------------------------------------------------------------

    def update_step(self, step_idx: int) -> None:
        """Advance the dialog to ``step_idx`` (0-based).

        Safe to call from the main thread only (use ``after()`` from
        background threads).
        """
        if not self.winfo_exists():
            return
        # Mark previous steps as done
        for i, lbl in enumerate(self._step_items):
            if i < step_idx:
                lbl.configure(text=f"  ✓  {self.STEPS[i]}", foreground="#2e7d32")
            elif i == step_idx:
                lbl.configure(text=f"  ●  {self.STEPS[i]}", foreground="#1565c0")
            else:
                lbl.configure(text=f"  ○  {self.STEPS[i]}", foreground="#888888")

        current_text = self.STEPS[step_idx] if step_idx < len(self.STEPS) else "Finalising…"
        self._step_label.configure(text=current_text)
        self._progress.configure(value=step_idx + 1)
        self.update_idletasks()

    def close(self) -> None:
        """Close the dialog.

        Safe to call even if the window has already been destroyed.
        """
        try:
            if self.winfo_exists():
                self.destroy()
        except Exception:
            pass


class CostsStep(BaseStep):
    """Costs step for cost and time projection.

    Features:
    - Token count display (original vs preprocessed)
    - Cost projection using model pricing
    - Model comparison table
    - Savings visualization
    - Rate-limit time estimation
    - Chunk size impact
    """

    step_id = 4
    step_name = "Costs"

    def __init__(
        self,
        parent: tk.Widget,
        session: "SessionState",
        manifest_manager: Optional["ManifestManager"] = None,
    ) -> None:
        """Initialize Estimation step.

        Args:
            parent: Parent widget.
            session: Session state.
            manifest_manager: ManifestManager for unified state (TASK 19).
        """
        # Initialize instance variables BEFORE super().__init__
        # because base class calls _build_ui() which needs these
        self._estimation_result: Optional[ComparisonResult] = None
        self._is_estimating = False
        self._lines_original: List[str] = []
        self._lines_preprocessed: List[str] = []

        # Task 40.4: Dual estimation state tracking
        self._estimation_state: Dict[str, Any] = {
            "original_complete": False,
            "preprocessed_complete": False,
            "original_result": None,
            "preprocessed_result": None,
        }
        # Task 5: Request mode button refs (populated in _build_request_mode_grid)
        self._mode_var: Optional[tk.StringVar] = None
        self._mode_buttons: dict[str, tk.Button] = {}
        # Whether API.ini settings have been loaded once
        self._settings_loaded_once = False
        # Non-blocking progress dialog shown during estimation
        self._progress_dialog: Optional[EstimationProgressDialog] = None
        super().__init__(parent, session, manifest_manager=manifest_manager)

    def _build_ui(self) -> None:
        """Build the step UI."""
        self._build_header()
        self._build_content()

    def _build_header(self) -> None:
        """Build the header section with controls."""
        header = ttk.Frame(self)
        header.pack(fill="x", padx=10, pady=5)

        # ── Row 1: Model, Lines/Request, Tokens/Request, buttons ──
        row1 = ttk.Frame(header)
        row1.pack(fill="x")

        # Model selection
        model_frame = ttk.Frame(row1)
        model_frame.pack(side="left")

        ttk.Label(model_frame, text="Primary Model:").pack(side="left", padx=(0, 5))
        self._model_var = tk.StringVar(value=DEFAULT_PRICING_MODEL)
        model_names = get_model_names()
        self._model_combo = ttk.Combobox(
            model_frame,
            textvariable=self._model_var,
            values=["(No Model)"] + model_names,
            state="readonly",
            width=20,
        )
        self._model_combo.pack(side="left")
        self._model_combo.bind("<<ComboboxSelected>>", self._on_model_changed)

        # Chunk size (Lines/Request)
        chunk_frame = ttk.Frame(row1)
        chunk_frame.pack(side="left", padx=(20, 0))

        ttk.Label(chunk_frame, text="Lines/Request:").pack(side="left", padx=(0, 5))
        self._chunk_var = tk.IntVar(value=30)
        self._chunk_spin = ttk.Spinbox(
            chunk_frame,
            from_=1,
            to=99999,
            textvariable=self._chunk_var,
            width=6,
        )
        self._chunk_spin.pack(side="left")

        # TASK 43.12: Sync chunk changes back to manifest
        self._chunk_var.trace_add("write", self._on_chunk_changed)

        # Tokens/Request limit (Task 40.2)
        tokens_frame = ttk.Frame(row1)
        tokens_frame.pack(side="left", padx=(15, 0))

        ttk.Label(tokens_frame, text="Tokens/Request:").pack(
            side="left", padx=(0, 5)
        )
        self._tokens_var = tk.IntVar(value=4000)
        self._tokens_spin = ttk.Spinbox(
            tokens_frame,
            from_=500,
            to=32000,
            increment=500,
            textvariable=self._tokens_var,
            width=7,
        )
        self._tokens_spin.pack(side="left")

        # Estimate button
        self._estimate_btn = ttk.Button(
            row1,
            text="▶ Estimate",
            command=self._run_estimation,
        )
        self._estimate_btn.pack(side="right", padx=(5, 0))

        # Apply Settings to Model button (one-way write to API.ini)
        self._save_btn = ttk.Button(
            row1,
            text="📤 Apply Settings to Model",
            command=self._save_settings,
        )
        self._save_btn.pack(side="right")

        # ── Row 2: Workflow defaults + Rolling Context ──
        row2 = ttk.Frame(header)
        row2.pack(fill="x", pady=(4, 0))

        # Thinking checkbox
        self._thinking_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            row2, text="Thinking", variable=self._thinking_var,
        ).pack(side="left")

        # Use Translated Context checkbox
        self._use_translated_ctx_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            row2, text="Translated Context",
            variable=self._use_translated_ctx_var,
        ).pack(side="left", padx=(12, 0))

        # Rolling Context spinboxes
        ttk.Label(row2, text="Rolling Context —").pack(
            side="left", padx=(20, 5),
        )

        ttk.Label(row2, text="Before:").pack(side="left")
        self._rc_before_var = tk.IntVar(value=3)
        ttk.Spinbox(
            row2, from_=0, to=20, textvariable=self._rc_before_var, width=3,
        ).pack(side="left", padx=(2, 8))

        ttk.Label(row2, text="Between:").pack(side="left")
        self._rc_between_var = tk.IntVar(value=0)
        ttk.Spinbox(
            row2, from_=0, to=20, textvariable=self._rc_between_var, width=3,
        ).pack(side="left", padx=(2, 8))

        ttk.Label(row2, text="After:").pack(side="left")
        self._rc_after_var = tk.IntVar(value=0)
        ttk.Spinbox(
            row2, from_=0, to=20, textvariable=self._rc_after_var, width=3,
        ).pack(side="left", padx=(2, 0))

    def _build_content(self) -> None:
        """Build the main content area."""
        # Main paned window
        content = ttk.PanedWindow(self, orient="horizontal")
        content.pack(fill="both", expand=True, padx=10, pady=5)

        # Left: Summary panels
        left_frame = ttk.Frame(content)
        content.add(left_frame, weight=1)
        self._build_summary_panels(left_frame)

        # Right: Model comparison table
        right_frame = ttk.LabelFrame(content, text="Model Comparison")
        content.add(right_frame, weight=1)
        self._build_comparison_table(right_frame)

    def _build_summary_panels(self, parent: ttk.Frame) -> None:
        """Build the summary panels on the left side."""
        # Request Mode panel (2x2 grid above Token Counts — Task 5)
        mode_frame = ttk.LabelFrame(parent, text="Request Mode")
        mode_frame.pack(fill="x", padx=5, pady=5)
        self._build_request_mode_grid(mode_frame)

        # Token counts panel
        token_frame = ttk.LabelFrame(parent, text="Token Counts")
        token_frame.pack(fill="x", padx=5, pady=5)

        self._token_grid = ttk.Frame(token_frame)
        self._token_grid.pack(fill="x", padx=10, pady=10)

        # Headers
        ttk.Label(
            self._token_grid,
            text="",
            width=15,
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            self._token_grid,
            text="Original",
            font=("TkDefaultFont", 10, "bold"),
        ).grid(row=0, column=1, padx=10)
        ttk.Label(
            self._token_grid,
            text="Preprocessed",
            font=("TkDefaultFont", 10, "bold"),
        ).grid(row=0, column=2, padx=10)
        ttk.Label(
            self._token_grid,
            text="Saved",
            font=("TkDefaultFont", 10, "bold"),
            foreground=THEME.accent_success,
        ).grid(row=0, column=3, padx=10)

        # Line count row
        ttk.Label(self._token_grid, text="Lines:").grid(row=1, column=0, sticky="w")
        self._lines_orig_label = ttk.Label(self._token_grid, text="-")
        self._lines_orig_label.grid(row=1, column=1)
        self._lines_prep_label = ttk.Label(self._token_grid, text="-")
        self._lines_prep_label.grid(row=1, column=2)
        self._lines_saved_label = ttk.Label(
            self._token_grid,
            text="-",
            foreground=THEME.accent_success,
        )
        self._lines_saved_label.grid(row=1, column=3)

        # Input tokens row (content only — excludes prompt overhead)
        ttk.Label(self._token_grid, text="Input Tokens:").grid(row=2, column=0, sticky="w")
        self._input_orig_label = ttk.Label(self._token_grid, text="-")
        self._input_orig_label.grid(row=2, column=1)
        self._input_prep_label = ttk.Label(self._token_grid, text="-")
        self._input_prep_label.grid(row=2, column=2)
        self._input_saved_label = ttk.Label(
            self._token_grid,
            text="-",
            foreground=THEME.accent_success,
        )
        self._input_saved_label.grid(row=2, column=3)

        # Prompt tokens row (overhead per request × num requests)
        ttk.Label(
            self._token_grid, text="Prompt Tokens:",
            foreground=THEME.text_secondary,
        ).grid(row=3, column=0, sticky="w")
        self._prompt_orig_label = ttk.Label(
            self._token_grid, text="-", foreground=THEME.text_secondary,
        )
        self._prompt_orig_label.grid(row=3, column=1)
        self._prompt_prep_label = ttk.Label(
            self._token_grid, text="-", foreground=THEME.text_secondary,
        )
        self._prompt_prep_label.grid(row=3, column=2)
        self._prompt_saved_label = ttk.Label(
            self._token_grid, text="-",
            foreground=THEME.accent_success,
        )
        self._prompt_saved_label.grid(row=3, column=3)

        # Cached tokens row (prompt portion cached after first request)
        ttk.Label(
            self._token_grid, text="Cached Tokens:",
            foreground=THEME.text_secondary,
        ).grid(row=4, column=0, sticky="w")
        self._cached_orig_label = ttk.Label(
            self._token_grid, text="-", foreground=THEME.text_secondary,
        )
        self._cached_orig_label.grid(row=4, column=1)
        self._cached_prep_label = ttk.Label(
            self._token_grid, text="-", foreground=THEME.text_secondary,
        )
        self._cached_prep_label.grid(row=4, column=2)
        self._cached_saved_label = ttk.Label(
            self._token_grid, text="-",
            foreground=THEME.accent_success,
        )
        self._cached_saved_label.grid(row=4, column=3)

        # Total input row (content + prompt — what gets billed)
        ttk.Label(
            self._token_grid, text="Total Input:",
            font=("TkDefaultFont", 10, "bold"),
        ).grid(row=5, column=0, sticky="w")
        self._total_input_orig_label = ttk.Label(
            self._token_grid, text="-",
            font=("TkDefaultFont", 10, "bold"),
        )
        self._total_input_orig_label.grid(row=5, column=1)
        self._total_input_prep_label = ttk.Label(
            self._token_grid, text="-",
            font=("TkDefaultFont", 10, "bold"),
        )
        self._total_input_prep_label.grid(row=5, column=2)
        self._total_input_saved_label = ttk.Label(
            self._token_grid, text="-",
            font=("TkDefaultFont", 10, "bold"),
            foreground=THEME.accent_success,
        )
        self._total_input_saved_label.grid(row=5, column=3)

        # Output tokens row (estimated)
        ttk.Label(self._token_grid, text="Output Tokens (est):").grid(
            row=6, column=0, sticky="w"
        )
        self._output_orig_label = ttk.Label(self._token_grid, text="-")
        self._output_orig_label.grid(row=6, column=1)
        self._output_prep_label = ttk.Label(self._token_grid, text="-")
        self._output_prep_label.grid(row=6, column=2)
        self._output_saved_label = ttk.Label(
            self._token_grid,
            text="-",
            foreground=THEME.accent_success,
        )
        self._output_saved_label.grid(row=6, column=3)

        # Cost estimate panel
        cost_frame = ttk.LabelFrame(parent, text="Cost Estimate")
        cost_frame.pack(fill="x", padx=5, pady=5)

        self._cost_grid = ttk.Frame(cost_frame)
        self._cost_grid.pack(fill="x", padx=10, pady=10)

        # Model label
        ttk.Label(
            self._cost_grid,
            text="Model:",
            font=("TkDefaultFont", 10, "bold"),
        ).grid(row=0, column=0, sticky="w")
        self._model_label = ttk.Label(self._cost_grid, text="-")
        self._model_label.grid(row=0, column=1, columnspan=2, sticky="w", padx=10)

        # Cost headers
        ttk.Label(self._cost_grid, text="").grid(row=1, column=0, sticky="w")
        ttk.Label(
            self._cost_grid,
            text="Original",
            font=("TkDefaultFont", 9, "bold"),
        ).grid(row=1, column=1, padx=10)
        ttk.Label(
            self._cost_grid,
            text="Preprocessed",
            font=("TkDefaultFont", 9, "bold"),
        ).grid(row=1, column=2, padx=10)

        # Input cost row
        ttk.Label(self._cost_grid, text="Input Cost:").grid(row=2, column=0, sticky="w")
        self._cost_input_orig_label = ttk.Label(self._cost_grid, text="-")
        self._cost_input_orig_label.grid(row=2, column=1)
        self._cost_input_prep_label = ttk.Label(self._cost_grid, text="-")
        self._cost_input_prep_label.grid(row=2, column=2)

        # Prompt cost row (non-cached prompt portion)
        ttk.Label(
            self._cost_grid, text="Prompt Cost:",
        ).grid(row=3, column=0, sticky="w")
        self._cost_prompt_orig_label = ttk.Label(
            self._cost_grid, text="-",
        )
        self._cost_prompt_orig_label.grid(row=3, column=1)
        self._cost_prompt_prep_label = ttk.Label(
            self._cost_grid, text="-",
        )
        self._cost_prompt_prep_label.grid(row=3, column=2)

        # Cached cost row
        ttk.Label(
            self._cost_grid, text="Cached Cost:",
        ).grid(row=4, column=0, sticky="w")
        self._cost_cached_orig_label = ttk.Label(
            self._cost_grid, text="-",
        )
        self._cost_cached_orig_label.grid(row=4, column=1)
        self._cost_cached_prep_label = ttk.Label(
            self._cost_grid, text="-",
        )
        self._cost_cached_prep_label.grid(row=4, column=2)

        # Output cost row
        ttk.Label(self._cost_grid, text="Output Cost:").grid(row=5, column=0, sticky="w")
        self._cost_output_orig_label = ttk.Label(self._cost_grid, text="-")
        self._cost_output_orig_label.grid(row=5, column=1)
        self._cost_output_prep_label = ttk.Label(self._cost_grid, text="-")
        self._cost_output_prep_label.grid(row=5, column=2)

        # Total cost row (highlighted)
        ttk.Label(
            self._cost_grid,
            text="Total Cost:",
            font=("TkDefaultFont", 10, "bold"),
        ).grid(row=6, column=0, sticky="w")
        self._cost_total_orig_label = ttk.Label(
            self._cost_grid,
            text="-",
            font=("TkDefaultFont", 10, "bold"),
        )
        self._cost_total_orig_label.grid(row=6, column=1)
        self._cost_total_prep_label = ttk.Label(
            self._cost_grid,
            text="-",
            font=("TkDefaultFont", 10, "bold"),
            foreground=THEME.accent_success,
        )
        self._cost_total_prep_label.grid(row=6, column=2)

        # Savings row
        ttk.Label(self._cost_grid, text="").grid(row=7, column=0)
        self._savings_label = ttk.Label(
            self._cost_grid,
            text="",
            font=("TkDefaultFont", 10, "bold"),
            foreground=THEME.accent_success,
        )
        self._savings_label.grid(row=7, column=1, columnspan=2, pady=(5, 0))

        # Time estimate panel
        time_frame = ttk.LabelFrame(parent, text="Time Estimate")
        time_frame.pack(fill="x", padx=5, pady=5)

        self._time_grid = ttk.Frame(time_frame)
        self._time_grid.pack(fill="x", padx=10, pady=10)

        # Request count row
        ttk.Label(self._time_grid, text="Requests:").grid(row=0, column=0, sticky="w")
        self._requests_orig_label = ttk.Label(self._time_grid, text="-")
        self._requests_orig_label.grid(row=0, column=1, padx=10)
        self._requests_prep_label = ttk.Label(self._time_grid, text="-")
        self._requests_prep_label.grid(row=0, column=2, padx=10)

        # Time estimate row
        ttk.Label(self._time_grid, text="Est. Time:").grid(row=1, column=0, sticky="w")
        self._time_orig_label = ttk.Label(self._time_grid, text="-")
        self._time_orig_label.grid(row=1, column=1, padx=10)
        self._time_prep_label = ttk.Label(self._time_grid, text="-")
        self._time_prep_label.grid(row=1, column=2, padx=10)

        # Rate limit note
        self._rate_limit_label = ttk.Label(
            time_frame,
            text="Based on 60 requests/minute rate limit",
            foreground=THEME.text_secondary,
            font=("TkDefaultFont", 8),
        )
        self._rate_limit_label.pack(pady=(0, 5))

    # ── Request Mode constants and methods (Task 5) ──

    # Mode definitions: (key, display_label, price_input_key, price_output_key)
    _REQUEST_MODES = (
        ("normal", "Normal", "input", "output"),
        ("batch", "Batch", "batch_input", "batch_output"),
        ("flex", "Flex", "flex_input", "flex_output"),
        ("priority", "Priority", "priority_input", "priority_output"),
    )

    def _build_request_mode_grid(self, parent: ttk.Frame) -> None:
        """Build a 2×2 grid of request mode buttons.

        Each button can be Available (pale green), Unavailable (pale red),
        or Selected (accent).  The selected mode drives which price columns
        are used in estimation and the comparison table.
        """
        grid = ttk.Frame(parent)
        grid.pack(padx=5, pady=5)

        self._mode_var = tk.StringVar(value="normal")
        self._mode_buttons: dict[str, tk.Button] = {}

        for idx, (key, label, _, _) in enumerate(self._REQUEST_MODES):
            r, c = divmod(idx, 2)
            btn = tk.Button(
                grid,
                text=label,
                width=20,
                relief="groove",
                command=lambda k=key: self._select_request_mode(k),
            )
            btn.grid(row=r, column=c, padx=3, pady=2)
            self._mode_buttons[key] = btn

        # Initial colouring
        self._refresh_mode_buttons()

    def _select_request_mode(self, mode: str) -> None:
        """Select a request mode and refresh the button visuals."""
        pricing = get_model_pricing(self._model_var.get())
        # Check availability
        for key, _, input_key, _ in self._REQUEST_MODES:
            if key == mode:
                if key != "normal" and pricing.get(input_key) is None:
                    return  # unavailable — ignore click
                break
        self._mode_var.set(mode)
        self._refresh_mode_buttons()
        # Recalculate costs from existing data (no full re-estimation)
        if self._estimation_result:
            self._recalculate_costs_for_mode()

    def _recalculate_costs_for_mode(self) -> None:
        """Recalculate cost labels using existing token counts and new mode.

        Called on mode change to instantly update costs without running
        a full re-estimation.  Splits costs into four additive
        components: Input (content) + Prompt (non-cached) + Cached +
        Output = Total.
        """
        result = self._estimation_result
        if result is None:
            return

        model_id = self._model_var.get()
        in_key, out_key = self._get_mode_price_keys()
        pricing = get_model_pricing(model_id)

        mode_input = pricing.get(in_key) or pricing.get("input", 0.0)
        mode_output = pricing.get(out_key) or pricing.get("output", 0.0)
        cached_rate = pricing.get("cached_input")

        for est_result in (result.original, result.preprocessed):
            content_cost = (est_result.content_tokens / 1_000_000) * mode_input
            non_cached_prompt = max(
                0, est_result.prompt_tokens - est_result.cached_tokens,
            )
            prompt_cost_val = (non_cached_prompt / 1_000_000) * mode_input
            cached_cost = 0.0
            if cached_rate is not None and est_result.cached_tokens > 0:
                cached_cost = (
                    est_result.cached_tokens / 1_000_000
                ) * cached_rate
            output_cost = (est_result.output_tokens / 1_000_000) * mode_output

            est_result.input_cost = content_cost
            est_result.prompt_cost = prompt_cost_val
            est_result.cached_input_cost = cached_cost
            est_result.output_cost = output_cost
            est_result.total_cost = (
                content_cost + prompt_cost_val + cached_cost + output_cost
            )

        # Recalculate savings
        result.cost_saved = (
            result.original.total_cost - result.preprocessed.total_cost
        )

        # Update cost labels (all ceil-to-cents)
        self._cost_input_orig_label.configure(
            text=_fmt_cost(result.original.input_cost),
        )
        self._cost_input_prep_label.configure(
            text=_fmt_cost(result.preprocessed.input_cost),
        )
        self._cost_prompt_orig_label.configure(
            text=_fmt_cost(result.original.prompt_cost),
        )
        self._cost_prompt_prep_label.configure(
            text=_fmt_cost(result.preprocessed.prompt_cost),
        )
        self._cost_cached_orig_label.configure(
            text=_fmt_cost(result.original.cached_input_cost),
        )
        self._cost_cached_prep_label.configure(
            text=_fmt_cost(result.preprocessed.cached_input_cost),
        )
        self._cost_output_orig_label.configure(
            text=_fmt_cost(result.original.output_cost),
        )
        self._cost_output_prep_label.configure(
            text=_fmt_cost(result.preprocessed.output_cost),
        )
        self._cost_total_orig_label.configure(
            text=_fmt_cost(result.original.total_cost),
        )
        self._cost_total_prep_label.configure(
            text=_fmt_cost(result.preprocessed.total_cost),
        )

        # Savings summary
        if result.cost_saved > 0:
            self._savings_label.configure(
                text=f"💰 Save {_fmt_cost(result.cost_saved)} "
                     f"({result.savings_percent:.1f}% tokens)",
            )
        else:
            self._savings_label.configure(text="")

        # Refresh comparison table with new mode prices
        self._update_comparison_table()

    def _refresh_mode_buttons(self) -> None:
        """Colour mode buttons based on model availability and selection."""
        if self._mode_var is None or not self._mode_buttons:
            return
        selected = self._mode_var.get()
        model_id = self._model_var.get()
        pricing = get_model_pricing(model_id) if model_id else {}

        for key, label, input_key, _ in self._REQUEST_MODES:
            btn = self._mode_buttons.get(key)
            if btn is None:
                continue
            is_selected = key == selected
            if key == "normal":
                available = True
            else:
                available = pricing.get(input_key) is not None

            # Build label with availability suffix
            if key == "normal":
                display = label
            elif available:
                display = f"{label} (Available)"
            else:
                display = f"{label} (Unavailable)"

            if is_selected:
                btn.configure(
                    text=display, bg="#4a90d9", fg="white", relief="sunken",
                )
            elif available:
                btn.configure(
                    text=display, bg="#c8e6c9", fg="black", relief="groove",
                )
            else:
                btn.configure(
                    text=display, bg="#ffcdd2", fg="#888888", relief="flat",
                )

    def _get_mode_price_keys(self) -> Tuple[str, str]:
        """Return (input_price_key, output_price_key) for the active mode."""
        if self._mode_var is None:
            return "input", "output"
        selected = self._mode_var.get()
        for key, _, input_key, output_key in self._REQUEST_MODES:
            if key == selected:
                return input_key, output_key
        return "input", "output"

    def _reprice_for_model(self) -> None:
        """Instantly reprice using cached token counts when the model changes.

        Reads the stored token breakdown from ``self._estimation_result``
        and reapplies the new model's pricing without running the expensive
        formation + token-counting pipeline again.  Also refreshes time
        estimates using the new model's rate limits.

        This is the fast path triggered by ``_on_model_changed()`` when a
        previous estimation result is available.
        """
        result = self._estimation_result
        if result is None:
            return

        model_id = self._model_var.get()
        in_key, out_key = self._get_mode_price_keys()
        pricing = get_model_pricing(model_id)

        mode_input = pricing.get(in_key) or pricing.get("input", 0.0)
        mode_output = pricing.get(out_key) or pricing.get("output", 0.0)
        cached_rate = pricing.get("cached_input")

        for est_result in (result.original, result.preprocessed):
            content_cost = (est_result.content_tokens / 1_000_000) * mode_input
            non_cached_prompt = max(
                0, est_result.prompt_tokens - est_result.cached_tokens,
            )
            prompt_cost_val = (non_cached_prompt / 1_000_000) * mode_input
            cached_cost = 0.0
            if cached_rate is not None and est_result.cached_tokens > 0:
                cached_cost = (est_result.cached_tokens / 1_000_000) * cached_rate
            output_cost = (est_result.output_tokens / 1_000_000) * mode_output

            est_result.input_cost = content_cost
            est_result.prompt_cost = prompt_cost_val
            est_result.cached_input_cost = cached_cost
            est_result.output_cost = output_cost
            est_result.total_cost = (
                content_cost + prompt_cost_val + cached_cost + output_cost
            )

        # Recalculate comparison savings
        result.cost_saved = (
            result.original.total_cost - result.preprocessed.total_cost
        )
        if result.original.input_tokens:
            result.savings_percent = (
                result.tokens_saved / result.original.input_tokens * 100
            )

        # Refresh cost labels (all ceil-to-cents)
        self._cost_input_orig_label.configure(
            text=_fmt_cost(result.original.input_cost),
        )
        self._cost_input_prep_label.configure(
            text=_fmt_cost(result.preprocessed.input_cost),
        )
        self._cost_prompt_orig_label.configure(
            text=_fmt_cost(result.original.prompt_cost),
        )
        self._cost_prompt_prep_label.configure(
            text=_fmt_cost(result.preprocessed.prompt_cost),
        )
        self._cost_cached_orig_label.configure(
            text=_fmt_cost(result.original.cached_input_cost),
        )
        self._cost_cached_prep_label.configure(
            text=_fmt_cost(result.preprocessed.cached_input_cost),
        )
        self._cost_output_orig_label.configure(
            text=_fmt_cost(result.original.output_cost),
        )
        self._cost_output_prep_label.configure(
            text=_fmt_cost(result.preprocessed.output_cost),
        )
        self._cost_total_orig_label.configure(
            text=_fmt_cost(result.original.total_cost),
        )
        self._cost_total_prep_label.configure(
            text=_fmt_cost(result.preprocessed.total_cost),
        )

        # Savings summary
        if result.cost_saved > 0:
            self._savings_label.configure(
                text=f"💰 Save {_fmt_cost(result.cost_saved)} "
                     f"({result.savings_percent:.1f}% tokens)",
            )
        else:
            self._savings_label.configure(text="")

        # Refresh model label
        self._model_label.configure(
            text=f"{pricing['name']} ({model_id})",
        )

        # Refresh time estimates using new model's rate limits
        rate_limits = get_model_rate_limits(model_id)
        concurrent = pricing.get("concurrent", 1)
        token_spd = pricing.get("token_speed", 50)

        orig_reqs = result.original.num_requests
        prep_reqs = result.preprocessed.num_requests

        if orig_reqs > 0:
            orig_time = estimate_rate_limit_time(
                orig_reqs,
                rate_limit_rpm=rate_limits.rpm,
                concurrent_requests=concurrent,
                total_output_tokens=result.original.output_tokens,
                token_speed=token_spd,
            )
            self._time_orig_label.configure(text=orig_time["formatted"])
            self._requests_orig_label.configure(text=str(orig_reqs))

        if prep_reqs > 0:
            prep_time = estimate_rate_limit_time(
                prep_reqs,
                rate_limit_rpm=rate_limits.rpm,
                concurrent_requests=concurrent,
                total_output_tokens=result.preprocessed.output_tokens,
                token_speed=token_spd,
            )
            self._time_prep_label.configure(text=prep_time["formatted"])
            self._requests_prep_label.configure(text=str(prep_reqs))

        self._rate_limit_label.configure(
            text=f"Based on {rate_limits.rpm} requests/minute rate limit for {model_id}",
        )

        # Refresh comparison table
        self._update_comparison_table()

        logger.debug(
            "Repriced for model %s: orig=%.2f prep=%.2f",
            model_id, result.original.total_cost, result.preprocessed.total_cost,
        )

    def _build_comparison_table(self, parent: ttk.LabelFrame) -> None:
        """Build the model comparison table."""
        # Define columns
        columns = [
            ColumnDef(key="model", title="Model", width=150),
            ColumnDef(key="input_price", title="Input $/1M", width=80, anchor="e"),
            ColumnDef(key="cached_price", title="Cached $/1M", width=80, anchor="e"),
            ColumnDef(key="output_price", title="Output $/1M", width=80, anchor="e"),
            ColumnDef(key="orig_cost", title="Original $", width=90, anchor="e"),
            ColumnDef(key="prep_cost", title="Preprocessed $", width=100, anchor="e"),
            ColumnDef(key="savings", title="Savings", width=80, anchor="e"),
        ]

        self._comparison_table = SharedTable(
            parent,
            columns=columns,
            show_filter=False,
            show_checkboxes=False,
        )
        self._comparison_table.pack(fill="both", expand=True)

        # Populate with models (placeholder data until estimation runs)
        self._update_comparison_table()

    def _update_comparison_table(self) -> None:
        """Update the model comparison table with current estimation."""
        rows: List[TableRow] = []
        in_key, out_key = self._get_mode_price_keys()

        for idx, (model_id, pricing) in enumerate(get_all_model_pricing().items()):
            # Use mode-specific prices, falling back to standard
            mode_input = pricing.get(in_key) or pricing.get("input", 0.0)
            mode_output = pricing.get(out_key) or pricing.get("output", 0.0)

            # Calculate costs if we have estimation data
            if self._estimation_result:
                orig = self._estimation_result.original
                prep = self._estimation_result.preprocessed

                # Use mode-adjusted pricing for cost calculation
                orig_in_cost = (orig.input_tokens / 1_000_000) * mode_input
                orig_out_cost = (orig.output_tokens / 1_000_000) * mode_output
                prep_in_cost = (prep.input_tokens / 1_000_000) * mode_input
                prep_out_cost = (prep.output_tokens / 1_000_000) * mode_output

                orig_total = round(orig_in_cost + orig_out_cost, 2)
                prep_total = round(prep_in_cost + prep_out_cost, 2)
                savings = orig_total - prep_total
                savings_str = f"-${savings:.2f}" if savings > 0 else "-"
            else:
                orig_total = 0.0
                prep_total = 0.0
                savings_str = "-"

            row = TableRow(
                id=idx,
                values={
                    "model": pricing["name"],
                    "input_price": f"${mode_input:.2f}",
                    "cached_price": (
                        f"${pricing['cached_input']:.2f}"
                        if pricing.get("cached_input") is not None
                        else "—"
                    ),
                    "output_price": f"${mode_output:.2f}",
                    "orig_cost": f"${orig_total:.2f}" if orig_total else "-",
                    "prep_cost": f"${prep_total:.2f}" if prep_total else "-",
                    "savings": savings_str,
                },
            )
            rows.append(row)

        self._comparison_table.set_data(rows)

    def _get_lines(self) -> Tuple[List[str], List[str]]:
        """Get original and preprocessed lines from manifest.

        Returns original ``orig`` lines and preprocessed ``prepro`` lines
        (falling back to ``orig`` when no preprocessing has been applied).

        Returns:
            Tuple of (original_lines, preprocessed_lines).
        """
        original: List[str] = []
        preprocessed: List[str] = []

        mgr = self.manifest_manager
        if mgr is not None and mgr.is_loaded:
            manifest_lines = mgr.get_lines()
            if manifest_lines:
                original = [ln.get("orig", "") for ln in manifest_lines]
                preprocessed = get_all_lines_resolved(mgr, "prepro")

        # Fallback: GUI input step
        if not original:
            try:
                app = self.winfo_toplevel()
                if hasattr(app, "_step_tabs") and len(app._step_tabs) > 0:
                    input_step = app._step_tabs[0]
                    if hasattr(input_step, "get_loaded_files"):
                        loaded_files = input_step.get_loaded_files()
                        for lf in loaded_files:
                            if hasattr(lf, "lines"):
                                original.extend(lf.lines)
            except Exception as e:
                logger.debug("Error getting lines from GUI: %s", e)

        # Final fallback: legacy session step data
        if not original:
            input_data = self.session.get_step(0).data
            if "all_lines" in input_data:
                original = input_data["all_lines"]

        # Ensure preprocessed falls back to original
        if not preprocessed and original:
            preprocessed = original[:]

        return original, preprocessed

    def _get_prompt_tokens(self) -> int:
        """Get estimated token count for the system prompt overhead.

        Uses ``gather_prompt_data`` + ``build_request_prompt`` (the
        unified request builder) so the estimate covers all §5.2
        sections identically to how Request Preview and Start
        Translation build them.

        Returns:
            Estimated token count for system prompt.
        """
        try:
            mgr = self.manifest_manager
            sample_lines = (
                self._lines_preprocessed[:200]
                if self._lines_preprocessed else []
            )
            prompt_data = gather_prompt_data(mgr, sample_lines=sample_lines)

            # Build the full prompt using the shared builder
            prompt_text, breakdown = build_request_prompt(
                prompt_data,
                code_patterns=prompt_data.get("code_patterns"),
            )

            if not prompt_text:
                return 0

            # Use tiktoken if available; otherwise rough 4-char estimate
            try:
                token_count, _ = count_tokens(prompt_text)
            except Exception:
                token_count = len(prompt_text) // 4

            return token_count

        except Exception as e:
            logger.debug("Error calculating prompt tokens: %s", e)
            return 0

    def _get_static_prompt_tokens(self) -> int:
        """Get token count for the static (cacheable) prompt portion.

        Uses ``gather_prompt_data`` + ``build_request_prompt`` with
        empty ``chunk_lines`` so that dynamic per-chunk sections
        (conditional prompts, glossary, characters, rolling context)
        are excluded.  The resulting token count represents §5.2
        slots 1-7b which are identical across all requests and
        eligible for prompt caching.

        Returns:
            Estimated token count for static prompt sections.
        """
        try:
            mgr = self.manifest_manager
            prompt_data = gather_prompt_data(mgr)

            # Build with empty chunk_lines to exclude dynamic sections
            prompt_text, _ = build_request_prompt(
                prompt_data,
                chunk_lines=[],
                rolling_context_text="",
                code_patterns=prompt_data.get("code_patterns"),
            )

            if not prompt_text:
                return 0

            try:
                token_count, _ = count_tokens(prompt_text)
            except Exception:
                token_count = len(prompt_text) // 4

            return token_count

        except Exception as e:
            logger.debug("Error calculating static prompt tokens: %s", e)
            return 0

    @staticmethod
    def _count_formation_input_tokens(
        request_line_lists: List[List[str]],
        model: str = "",
    ) -> int:
        """Count user-message (input) tokens per request using JSON format.

        Mirrors the Request Preview: each request's user message is
        ``json.dumps({"lines": chunk_lines}, ensure_ascii=False)``.
        Summing the token counts across all requests gives the total
        input token estimate that matches what the Preview reports.

        Args:
            request_line_lists: Per-request translatable line texts
                from :class:`FormationResult`.
            model: Model name for tokeniser selection.

        Returns:
            Total input tokens across all requests.
        """
        import json as _json

        total = 0
        for chunk_lines in request_line_lists:
            if not chunk_lines:
                continue
            payload = _json.dumps(
                {"lines": chunk_lines}, ensure_ascii=False,
            )
            try:
                tok, _ = count_tokens(payload, model=model)
            except Exception:
                tok = max(1, len(payload) // 4)
            total += tok
        return total

    def _compute_per_request_prompt_overhead(
        self,
        request_line_lists: List[List[str]],
    ) -> Tuple[int, int]:
        """Compute prompt overhead by building each request's prompt individually.

        Uses ``gather_prompt_data`` once, then ``build_request_prompt``
        per request with selective chunk lines — identical to how
        Request Preview and Start Translation build their prompts.

        Args:
            request_line_lists: Per-request translatable line texts
                from :class:`FormationResult`.

        Returns:
            Tuple of (total_prompt_tokens, average_per_request).
        """
        if not request_line_lists:
            return 0, 0

        try:
            mgr = self.manifest_manager
            sample_lines = (
                self._lines_preprocessed[:200]
                if self._lines_preprocessed else []
            )
            prompt_data = gather_prompt_data(mgr, sample_lines=sample_lines)

            total_tokens = 0
            for chunk_lines in request_line_lists:
                prompt_text, _ = build_request_prompt(
                    prompt_data,
                    chunk_lines=chunk_lines,
                )
                if not prompt_text:
                    continue
                try:
                    tok, _ = count_tokens(prompt_text)
                except Exception:
                    tok = len(prompt_text) // 4
                total_tokens += tok

            num = len(request_line_lists)
            avg = total_tokens // num if num > 0 else 0
            return total_tokens, avg

        except Exception as e:
            logger.debug("Error computing per-request prompt overhead: %s", e)
            return 0, 0

    def _refresh_lines(self) -> None:
        """Refresh lines from previous steps."""
        self._lines_original, self._lines_preprocessed = self._get_lines()

        if self._lines_original:
            self._lines_orig_label.configure(text=str(len(self._lines_original)))
        if self._lines_preprocessed:
            self._lines_prep_label.configure(text=str(len(self._lines_preprocessed)))

        # Calculate saved lines
        saved = len(self._lines_original) - len(self._lines_preprocessed)
        if saved > 0:
            self._lines_saved_label.configure(text=f"-{saved}")
        else:
            self._lines_saved_label.configure(text="0")

    def _get_skip_indices(
        self,
        lines: List[str],
    ) -> frozenset:
        """Determine which line indices should be skipped from estimation.

        Applies the same rules as the Translation step (§5.4):

        * **Mandatory** — empty, context markers, dedup-only,
          placeholder-only, comment-only lines.
        * **Optional** — already-translated lines (when
          ``overwrite_translation`` is *False*), non-source-language
          and symbol-only lines (when ``skip_non_source_language`` is
          *True*).

        Language detection runs on *lines* directly — the same text that
        will be sent to the LLM.  When called with preprocessed lines,
        CJK replaced by ``__PROTECTED__`` makes the remaining text
        detectable as either source or non-source: if CJK content
        remains the line is kept; if only non-source text remains
        the line is skipped.

        Args:
            lines: Line texts (original or preprocessed).

        Returns:
            Frozenset of 0-based indices to exclude from estimation.
        """
        from CherryAI.functions.validation import SkipReason, validate_line_pre

        go = getattr(self.session, "global_options", None)
        skip_translated = True
        skip_non_source = True
        if go is not None and hasattr(go, "translation"):
            skip_translated = not getattr(
                go.translation, "overwrite_translation", False,
            )
            skip_non_source = getattr(
                go.translation, "skip_non_source_language", True,
            )

        # Collect existing translations when skip-translated is active
        existing_tls: List[Optional[str]] = []
        if skip_translated:
            mgr = self.manifest_manager
            if mgr is not None and mgr.is_loaded:
                manifest_lines = mgr.get_lines()
                if manifest_lines:
                    existing_tls = [
                        ml.get("tl", "") for ml in manifest_lines
                    ]

        # Collect preserve-action code patterns for CODE_ONLY skip
        preserve_patterns: List[str] = []
        mgr = self.manifest_manager
        source_language = "Japanese"
        if mgr is not None and mgr.is_loaded:
            code_pats = mgr._manifest_data.get("code_patterns", [])
            if isinstance(code_pats, list):
                preserve_patterns = [
                    str(p.get("pattern", ""))
                    for p in code_pats
                    if isinstance(p, dict)
                    and p.get("action") == "preserve"
                    and p.get("pattern")
                ]
            source_language = mgr.get_info_metadata_field(
                "source_language", "Japanese",
            )

        skip: set[int] = set()
        for i, line in enumerate(lines):
            existing = (
                existing_tls[i]
                if skip_translated and i < len(existing_tls)
                else None
            )
            vr = validate_line_pre(
                line,
                existing_translation=existing,
                preserve_patterns=preserve_patterns,
                source_language=source_language,
            )

            if vr.is_valid:
                continue

            # Respect the skip_non_source setting for language-based skips
            if not skip_non_source and vr.skip_reason in (
                SkipReason.NO_JAPANESE,
                SkipReason.SYMBOL_ONLY,
            ):
                continue

            skip.add(i)

        return frozenset(skip)

    def _on_chunk_changed(self, *_args: object) -> None:
        """Sync chunk size to manifest when changed (Task 43.12)."""
        mgr = self.manifest_manager
        if mgr is None or not mgr.is_loaded:
            return
        try:
            val = self._chunk_var.get()
        except (tk.TclError, ValueError):
            return
        if val < 1 or val > 99999:
            return
        if "RequestOptions" not in mgr._manifest_data:
            mgr._manifest_data["RequestOptions"] = {}
        mgr._manifest_data["RequestOptions"]["LinesPerChunk"] = val

    def _run_estimation(self) -> None:
        """Run cost/token estimation."""
        if self._is_estimating:
            return

        # Refresh lines first
        self._refresh_lines()

        if not self._lines_original:
            messagebox.showwarning(
                "No Data",
                "Please load files in the Input & Extraction step first.",
            )
            return

        self._is_estimating = True
        self._estimate_btn.configure(state="disabled", text="Estimating...")
        self._model_combo.configure(state="disabled")

        # Open non-blocking progress dialog
        try:
            self._progress_dialog = EstimationProgressDialog(self)
        except Exception:
            self._progress_dialog = None

        # Run in background
        thread = threading.Thread(target=self._do_estimation)
        thread.daemon = True
        thread.start()

    def _report_progress(self, step_idx: int) -> None:
        """Post a progress step update to the dialog on the main thread.

        Safe to call from background threads.  Silently ignored when no
        dialog is open or when the dialog has already been destroyed.

        Args:
            step_idx: 0-based index into ``EstimationProgressDialog.STEPS``.
        """
        dlg = self._progress_dialog
        if dlg is not None:
            try:
                self.after(0, lambda i=step_idx: dlg.update_step(i))
            except Exception:
                pass

    def _do_estimation(self) -> None:
        """Perform estimation in background thread.

        Uses the same 4-step formation pipeline as Translation (Step 5)
        when available, so request counts match actual API usage.
        """
        try:
            model_id = self._model_var.get()
            chunk_size = self._chunk_var.get()
            tokens_limit = self._tokens_var.get()

            # Step 0: Preparing lines
            self._report_progress(0)

            # Per-model API.ini settings (loaded by _load_model_settings
            # on first enter) take priority.  chunk_size and tokens_limit
            # already reflect the per-model values via _chunk_var /
            # _tokens_var.  Only read Global Options for request_slicing
            # which has no per-model override.
            go = getattr(self.session, "global_options", None)

            # Read request slicing mode from Global Options
            slicing = "conservative"
            if go is not None and hasattr(go, "translation"):
                slicing = getattr(
                    go.translation, "request_slicing", "conservative",
                )

            # Get prompt token overhead (included in each request)
            prompt_tokens = self._get_prompt_tokens()

            # §5.4: Filter out lines that would be skipped during
            # translation (empty, dedup, protected, already translated,
            # non-source language, symbol-only).
            # Language detection runs on each column's own text — the same
            # text that the LLM would receive.
            orig_skip = self._get_skip_indices(self._lines_original)
            prep_skip = self._get_skip_indices(self._lines_preprocessed)
            orig_translatable = [
                l for i, l in enumerate(self._lines_original)
                if i not in orig_skip
            ]
            prep_translatable = [
                l for i, l in enumerate(self._lines_preprocessed)
                if i not in prep_skip
            ]

            # Update line count labels with translatable counts
            n_orig = len(orig_translatable)
            n_prep = len(prep_translatable)
            n_saved = n_orig - n_prep
            self.after(0, lambda: (
                self._lines_orig_label.configure(text=str(n_orig)),
                self._lines_prep_label.configure(text=str(n_prep)),
                self._lines_saved_label.configure(
                    text=f"-{n_saved}" if n_saved > 0 else "0",
                ),
            ))

            # ── Formation pipeline for BOTH original and preprocessed ──
            # Use the same 4+1 step pipeline as Translation (Step 5) for
            # accurate request counts and per-request token counting that
            # matches the values shown in Request Preview.
            # Step 1: Building request formation (Original)
            self._report_progress(1)
            orig_formation = self._estimate_via_formation(
                self._lines_original, chunk_size, slicing,
                skip_indices=orig_skip,
                max_input_tokens=tokens_limit,
            )
            # Step 2: Building request formation (Preprocessed)
            self._report_progress(2)
            prep_formation = self._estimate_via_formation(
                self._lines_preprocessed, chunk_size, slicing,
                skip_indices=prep_skip,
                max_input_tokens=tokens_limit,
            )

            # ── Original estimation ──
            # Step 3: Counting tokens (Original)
            self._report_progress(3)
            if orig_formation is not None:
                orig_requests = orig_formation.num_requests
                orig_input_tokens = self._count_formation_input_tokens(
                    orig_formation.request_line_lists, model_id,
                )
                orig_prompt_total, _ = (
                    self._compute_per_request_prompt_overhead(
                        orig_formation.request_line_lists,
                    )
                )
                orig_method = "formation"
            else:
                orig_requests = estimate_chunks(
                    orig_translatable,
                    max_lines=chunk_size,
                    max_tokens=tokens_limit,
                    mode="hybrid",
                    model=model_id,
                )
                orig_text = "\n".join(orig_translatable)
                orig_input_tokens, orig_method = count_tokens(
                    orig_text, model=model_id,
                )
                orig_prompt_total = self._get_prompt_tokens() * orig_requests

            orig_output_tokens = int(orig_input_tokens * OUTPUT_TOKEN_MULTIPLIER)
            orig_total_input = orig_input_tokens + orig_prompt_total

            # ── Preprocessed estimation ──
            # Step 4: Counting tokens (Preprocessed)
            self._report_progress(4)
            if prep_formation is not None:
                prep_requests = prep_formation.num_requests
                prep_input_tokens = self._count_formation_input_tokens(
                    prep_formation.request_line_lists, model_id,
                )
                prep_prompt_total, prep_prompt_avg = (
                    self._compute_per_request_prompt_overhead(
                        prep_formation.request_line_lists,
                    )
                )
                prep_method = "formation"
            else:
                prep_requests = estimate_chunks(
                    prep_translatable,
                    max_lines=chunk_size,
                    max_tokens=tokens_limit,
                    mode="hybrid",
                    model=model_id,
                )
                prep_text = "\n".join(prep_translatable)
                prep_input_tokens, prep_method = count_tokens(
                    prep_text, model=model_id,
                )
                fallback_prompt = self._get_prompt_tokens()
                prep_prompt_total = fallback_prompt * prep_requests
                prep_prompt_avg = fallback_prompt

            prep_output_tokens = int(prep_input_tokens * OUTPUT_TOKEN_MULTIPLIER)
            prep_total_input = prep_input_tokens + prep_prompt_total

            # Step 5: Applying pricing & cache adjustments
            self._report_progress(5)

            # ── Prompt caching with static / dynamic split ──
            # Only the *static* prompt (§5.2 slots 1-7b) is eligible for
            # caching.  Dynamic per-chunk sections (slots 8-10: conditional
            # prompts, glossary, characters, rolling context) change every
            # request and are never cached.
            # Cache hit rate is ~80 % (CACHE_HIT_RATE).
            static_prompt_tokens = self._get_static_prompt_tokens()

            orig_cached_tokens = 0
            prep_cached_tokens = 0

            pricing_info = get_model_pricing(model_id)
            cached_rate = pricing_info.get("cached_input")
            input_rate = pricing_info["input"]
            output_rate = pricing_info["output"]

            if (
                cached_rate is not None
                and static_prompt_tokens >= 1024
            ):
                if orig_requests > 1:
                    cache_eligible = static_prompt_tokens * (orig_requests - 1)
                    orig_cached_tokens = int(cache_eligible * CACHE_HIT_RATE)
                if prep_requests > 1:
                    cache_eligible = static_prompt_tokens * (prep_requests - 1)
                    prep_cached_tokens = int(cache_eligible * CACHE_HIT_RATE)

            # ── Cost components: Input + Prompt + Cached + Output = Total ──
            # Input  = content tokens at input rate (line content only)
            # Prompt = non-cached prompt tokens at input rate
            # Cached = cached prompt tokens at cached rate
            # Output = output tokens at output rate

            # Original path
            orig_content_cost = (orig_input_tokens / 1_000_000) * input_rate
            orig_non_cached_prompt = max(0, orig_prompt_total - orig_cached_tokens)
            orig_prompt_cost = (orig_non_cached_prompt / 1_000_000) * input_rate
            orig_cached_cost = (
                (orig_cached_tokens / 1_000_000) * cached_rate
                if cached_rate is not None and orig_cached_tokens > 0
                else 0.0
            )
            orig_output_cost = (orig_output_tokens / 1_000_000) * output_rate
            orig_total_cost = (
                orig_content_cost + orig_prompt_cost
                + orig_cached_cost + orig_output_cost
            )

            # Preprocessed path
            prep_content_cost = (prep_input_tokens / 1_000_000) * input_rate
            prep_non_cached_prompt = max(0, prep_prompt_total - prep_cached_tokens)
            prep_prompt_cost_val = (prep_non_cached_prompt / 1_000_000) * input_rate
            prep_cached_cost = (
                (prep_cached_tokens / 1_000_000) * cached_rate
                if cached_rate is not None and prep_cached_tokens > 0
                else 0.0
            )
            prep_output_cost = (prep_output_tokens / 1_000_000) * output_rate
            prep_total_cost = (
                prep_content_cost + prep_prompt_cost_val
                + prep_cached_cost + prep_output_cost
            )

            # Build results — content_tokens stores line-only tokens,
            # input_tokens stores total (content + prompt) for billing.
            # input_cost stores content-only cost; prompt_cost and
            # cached_input_cost are separate additive components.
            original = EstimationResult(
                input_tokens=orig_total_input,
                output_tokens=orig_output_tokens,
                input_cost=orig_content_cost,
                output_cost=orig_output_cost,
                total_cost=orig_total_cost,
                token_method=orig_method,
                prompt_cost=orig_prompt_cost,
                cached_input_cost=orig_cached_cost,
                content_tokens=orig_input_tokens,
                prompt_tokens=orig_prompt_total,
                cached_tokens=orig_cached_tokens,
                num_requests=orig_requests,
            )

            preprocessed = EstimationResult(
                input_tokens=prep_total_input,
                output_tokens=prep_output_tokens,
                input_cost=prep_content_cost,
                output_cost=prep_output_cost,
                total_cost=prep_total_cost,
                token_method=prep_method,
                prompt_cost=prep_prompt_cost_val,
                cached_input_cost=prep_cached_cost,
                content_tokens=prep_input_tokens,
                prompt_tokens=prep_prompt_total,
                cached_tokens=prep_cached_tokens,
                num_requests=prep_requests,
            )

            tokens_saved = orig_total_input - prep_total_input
            cost_saved = orig_total_cost - prep_total_cost
            savings_pct = (tokens_saved / orig_total_input * 100) if orig_total_input else 0

            self._estimation_result = ComparisonResult(
                original=original,
                preprocessed=preprocessed,
                tokens_saved=tokens_saved,
                cost_saved=cost_saved,
                savings_percent=savings_pct,
            )

            # Task 40.4: Update dual estimation state
            self._estimation_state["original_complete"] = True
            self._estimation_state["original_result"] = original
            # Mark preprocessed complete only if preprocessed differs from original
            has_preprocessing = (
                self._lines_preprocessed != self._lines_original
            )
            if has_preprocessing:
                self._estimation_state["preprocessed_complete"] = True
                self._estimation_state["preprocessed_result"] = preprocessed
            else:
                # Preprocessed is same as original; not yet truly preprocessed
                self._estimation_state["preprocessed_complete"] = False
                self._estimation_state["preprocessed_result"] = None

            # Get model-specific rate limits for time estimation
            rate_limits = get_model_rate_limits(model_id)

            # Task 40.7: Get concurrent requests and token speed from pricing
            pricing = get_model_pricing(model_id)
            concurrent = pricing.get("concurrent", 1)
            token_spd = pricing.get("token_speed", 50)

            # Calculate time estimates using concurrent formula (Task 40.7)
            orig_time = estimate_rate_limit_time(
                orig_requests,
                rate_limit_rpm=rate_limits.rpm,
                concurrent_requests=concurrent,
                total_output_tokens=orig_output_tokens,
                token_speed=token_spd,
            )
            prep_time = estimate_rate_limit_time(
                prep_requests,
                rate_limit_rpm=rate_limits.rpm,
                concurrent_requests=concurrent,
                total_output_tokens=prep_output_tokens,
                token_speed=token_spd,
            )

            # Step 6: Updating display
            self._report_progress(6)

            # Update UI on main thread
            self.after(0, lambda: self._update_ui(
                original, preprocessed, orig_requests, prep_requests,
                orig_time, prep_time, model_id, rate_limits.rpm,
                prep_prompt_total, prep_prompt_avg,
            ))
            # Task 40.5: Update dual ticks on progress tracker
            self.after(0, self._update_dual_ticks)

        except Exception as e:
            logger.exception("Estimation error: %s", e)
            self.after(0, lambda: messagebox.showerror("Error", str(e)))
        finally:
            self.after(0, self._estimation_complete)

    def _estimate_via_formation(
        self,
        lines: List[str],
        chunk_size: int,
        slicing: str = "conservative",
        skip_indices: Optional[frozenset] = None,
        max_input_tokens: int = 0,
    ) -> Optional[FormationResult]:
        """Count requests using the 4-step formation pipeline.

        Mirrors the logic in ``TranslateStep._build_chunks()`` so that
        the estimation matches actual translation behaviour.

        Args:
            lines: Preprocessed line texts.
            chunk_size: Max lines per request.
            slicing: ``"conservative"`` or ``"efficient"``.
            skip_indices: Indices of lines to mark as invalid
                (already translated, non-source language, etc.).
            max_input_tokens: Maximum tokens for input lines per request
                (0 = no limit).

        Returns:
            FormationResult with request count and per-request line lists,
            or ``None`` if the pipeline is unavailable.
        """
        try:
            from CherryAI.functions.prompt_builder import (
                LineInfo, RequestFormationConfig, build_requests,
                is_placeholder_only, is_code_pattern_only,
            )
        except ImportError:
            return None

        _skip = skip_indices or frozenset()

        # Collect preserve-action code patterns for CODE_ONLY skip
        preserve_patterns: list[str] = []
        mgr = self.manifest_manager
        if mgr is not None and mgr.is_loaded:
            code_pats = mgr._manifest_data.get("code_patterns", [])
            if isinstance(code_pats, list):
                preserve_patterns = [
                    str(p.get("pattern", ""))
                    for p in code_pats
                    if isinstance(p, dict)
                    and p.get("action") == "preserve"
                    and p.get("pattern")
                ]

        line_infos: list[LineInfo] = []
        for idx, text in enumerate(lines):
            is_invalid = (
                not text.strip()
                or is_placeholder_only(text)
                or (preserve_patterns
                    and is_code_pattern_only(text, preserve_patterns))
                or idx in _skip
            )
            line_infos.append(LineInfo(index=idx, text=text, is_invalid=is_invalid))

        # Inject file-end markers from manifest
        mgr = self.manifest_manager
        if mgr is not None and mgr.is_loaded:
            try:
                filedir = mgr.get_filedir()
                for entry in filedir:
                    last = entry.last_idx
                    line_infos.append(LineInfo(
                        index=last + 1,
                        text="",
                        is_invalid=True,
                        tag="file_end",
                    ))
            except Exception:
                pass

        line_infos.sort(key=lambda li: li.index)

        if slicing == "efficient":
            min_lines = max(5, chunk_size // 2)
        else:
            min_lines = max(2, chunk_size // 5)

        config = RequestFormationConfig(
            max_lines=chunk_size,
            min_lines=min_lines,
            max_tokens=max_input_tokens,
            efficient_merge=(slicing == "efficient"),
            rolling_context_between=self._rc_between_var.get(),
            rolling_context_after=self._rc_after_var.get(),
        )
        requests = build_requests(line_infos, config)
        if not requests:
            fallback_count = max(1, len(lines) // chunk_size)
            return FormationResult(
                num_requests=fallback_count,
                request_line_lists=[],
            )
        return FormationResult(
            num_requests=len(requests),
            request_line_lists=[req.lines for req in requests],
        )

    def _update_ui(
        self,
        original: EstimationResult,
        preprocessed: EstimationResult,
        orig_requests: int,
        prep_requests: int,
        orig_time: Dict[str, Any],
        prep_time: Dict[str, Any],
        model_id: str,
        rate_limit_rpm: int = DEFAULT_RPM,
        prompt_tokens_total: int = 0,
        prompt_tokens_avg: int = 0,
    ) -> None:
        """Update UI with estimation results.

        Args:
            original: Original text estimation results.
            preprocessed: Preprocessed text estimation results.
            orig_requests: Original request count.
            prep_requests: Preprocessed request count.
            orig_time: Original time estimate dict.
            prep_time: Preprocessed time estimate dict.
            model_id: Model identifier.
            rate_limit_rpm: Model-specific rate limit (requests per minute).
            prompt_tokens_total: Total prompt overhead across all requests.
            prompt_tokens_avg: Average prompt overhead per request.
        """
        # Update token labels — content tokens only (Task 6)
        self._input_orig_label.configure(
            text=f"{original.content_tokens:,}",
        )
        self._input_prep_label.configure(
            text=f"{preprocessed.content_tokens:,}",
        )
        content_saved = original.content_tokens - preprocessed.content_tokens
        self._input_saved_label.configure(
            text=f"-{content_saved:,}" if content_saved > 0 else "0",
        )

        # Prompt tokens — non-cached portion only (cached shown separately)
        non_cached_prompt_orig = original.prompt_tokens - original.cached_tokens
        non_cached_prompt_prep = preprocessed.prompt_tokens - preprocessed.cached_tokens
        self._prompt_orig_label.configure(
            text=f"{non_cached_prompt_orig:,}",
        )
        self._prompt_prep_label.configure(
            text=f"{non_cached_prompt_prep:,}",
        )
        prompt_saved = non_cached_prompt_orig - non_cached_prompt_prep
        self._prompt_saved_label.configure(
            text=f"-{prompt_saved:,}" if prompt_saved > 0 else "0",
        )

        # Cached tokens (prompt portion cached after first request)
        self._cached_orig_label.configure(
            text=f"{original.cached_tokens:,}" if original.cached_tokens else "-",
        )
        self._cached_prep_label.configure(
            text=f"{preprocessed.cached_tokens:,}" if preprocessed.cached_tokens else "-",
        )
        cached_saved = original.cached_tokens - preprocessed.cached_tokens
        self._cached_saved_label.configure(
            text=f"-{cached_saved:,}" if cached_saved > 0 else (
                "0" if original.cached_tokens or preprocessed.cached_tokens
                else "-"
            ),
        )

        # Total input (content + prompt — what gets billed)
        self._total_input_orig_label.configure(
            text=f"{original.input_tokens:,}",
        )
        self._total_input_prep_label.configure(
            text=f"{preprocessed.input_tokens:,}",
        )
        total_saved = original.input_tokens - preprocessed.input_tokens
        self._total_input_saved_label.configure(
            text=f"-{total_saved:,}" if total_saved > 0 else "0",
        )

        # Output tokens
        self._output_orig_label.configure(text=f"{original.output_tokens:,}")
        self._output_prep_label.configure(text=f"{preprocessed.output_tokens:,}")
        out_saved = original.output_tokens - preprocessed.output_tokens
        self._output_saved_label.configure(
            text=f"-{out_saved:,}" if out_saved > 0 else "0",
        )

        # Update cost labels (all ceil-to-cents)
        pricing = get_model_pricing(model_id)
        self._model_label.configure(text=f"{pricing['name']} ({model_id})")

        self._cost_input_orig_label.configure(text=_fmt_cost(original.input_cost))
        self._cost_input_prep_label.configure(text=_fmt_cost(preprocessed.input_cost))

        # Prompt cost (non-cached prompt portion) and cached cost —
        # always shown as primary additive rows.
        self._cost_prompt_orig_label.configure(
            text=_fmt_cost(original.prompt_cost),
        )
        self._cost_prompt_prep_label.configure(
            text=_fmt_cost(preprocessed.prompt_cost),
        )
        self._cost_cached_orig_label.configure(
            text=_fmt_cost(original.cached_input_cost),
        )
        self._cost_cached_prep_label.configure(
            text=_fmt_cost(preprocessed.cached_input_cost),
        )

        self._cost_output_orig_label.configure(text=_fmt_cost(original.output_cost))
        self._cost_output_prep_label.configure(text=_fmt_cost(preprocessed.output_cost))

        self._cost_total_orig_label.configure(text=_fmt_cost(original.total_cost))
        self._cost_total_prep_label.configure(text=_fmt_cost(preprocessed.total_cost))

        # Savings summary
        if self._estimation_result:
            pct = self._estimation_result.savings_percent
            cost = self._estimation_result.cost_saved
            if cost > 0:
                self._savings_label.configure(
                    text=f"💰 Save {_fmt_cost(cost)} ({pct:.1f}% tokens)"
                )
            else:
                self._savings_label.configure(text="")

        # Update time labels
        self._requests_orig_label.configure(text=str(orig_requests))
        self._requests_prep_label.configure(text=str(prep_requests))

        self._time_orig_label.configure(text=orig_time["formatted"])
        self._time_prep_label.configure(text=prep_time["formatted"])

        # Update rate limit label with model-specific rate
        self._rate_limit_label.configure(
            text=f"Based on {rate_limit_rpm} requests/minute rate limit for {model_id}"
        )

        # Update comparison table
        self._update_comparison_table()

        # Store in session
        self.session.get_step(self.step_id).data["estimation"] = {
            "original_tokens": original.input_tokens,
            "preprocessed_tokens": preprocessed.input_tokens,
            "original_cost": original.total_cost,
            "preprocessed_cost": preprocessed.total_cost,
            "model": model_id,
            "rate_limit_rpm": rate_limit_rpm,
        }

        # TASK 25.1 + Task 7: Save full estimation results to manifest
        self._save_estimation_to_manifest(preprocessed, prep_requests)

    def _save_estimation_to_manifest(
        self,
        result: EstimationResult,
        num_requests: int,
    ) -> None:
        """Save full estimation results to manifest (Task 7).

        Persists token breakdown, costs, and request count so the
        Costs tab can restore previous results without re-estimating.

        Args:
            result: Preprocessed estimation result.
            num_requests: Number of API requests.
        """
        mgr = self.manifest_manager
        if mgr is None:
            logger.debug("No manifest manager, skipping save")
            return

        n_lines = len(self._lines_preprocessed)
        save_int_field(mgr, "InputLines", n_lines)
        save_int_field(mgr, "InputTokens", result.input_tokens)
        save_int_field(mgr, "OutputTokens", result.output_tokens)
        save_int_field(mgr, "ContentTokens", result.content_tokens)
        save_int_field(mgr, "PromptTokens", result.prompt_tokens)
        save_int_field(mgr, "CachedTokens", result.cached_tokens)
        save_int_field(mgr, "NumRequests", num_requests)
        save_float_field(mgr, "InputCost", result.input_cost)
        save_float_field(mgr, "OutputCost", result.output_cost)
        save_float_field(mgr, "TotalCost", result.total_cost)
        logger.debug(
            "Saved estimation to manifest: lines=%d, total_input=%d, "
            "content=%d, prompt=%d, cached=%d, requests=%d, cost=%.4f",
            n_lines, result.input_tokens, result.content_tokens,
            result.prompt_tokens, result.cached_tokens,
            num_requests, result.total_cost,
        )

    def _load_estimation_from_manifest(self) -> Optional[Dict[str, Any]]:
        """Load saved estimation results from manifest (Task 7).

        Returns:
            Dict with all saved fields, or ``None`` if no data saved.
        """
        mgr = self.manifest_manager
        if mgr is None:
            return None

        input_lines = load_int_field(mgr, "InputLines", 0)
        if input_lines == 0:
            return None

        return {
            "input_lines": input_lines,
            "input_tokens": load_int_field(mgr, "InputTokens", 0),
            "output_tokens": load_int_field(mgr, "OutputTokens", 0),
            "content_tokens": load_int_field(mgr, "ContentTokens", 0),
            "prompt_tokens": load_int_field(mgr, "PromptTokens", 0),
            "cached_tokens": load_int_field(mgr, "CachedTokens", 0),
            "num_requests": load_int_field(mgr, "NumRequests", 0),
            "input_cost": load_float_field(mgr, "InputCost", 0.0),
            "output_cost": load_float_field(mgr, "OutputCost", 0.0),
            "total_cost": load_float_field(mgr, "TotalCost", 0.0),
        }

    def _estimation_complete(self) -> None:
        """Called when estimation completes."""
        self._is_estimating = False
        # Close progress dialog if open
        if self._progress_dialog is not None:
            self._progress_dialog.close()
            self._progress_dialog = None
        # Show "Update Counts" after first estimation (Task 8)
        label = (
            "↻ Update Counts" if self._estimation_result
            else "▶ Estimate"
        )
        self._estimate_btn.configure(state="normal", text=label)
        self._model_combo.configure(state="readonly")

    def _update_dual_ticks(self) -> None:
        """Update progress tracker dual ticks for Costs step (Task 40.5).

        Reports (original_complete, preprocessed_complete) to the progress
        tracker so it displays ☐☐ / ☑☐ / ☑☑.
        """
        try:
            app = self.winfo_toplevel()
            if hasattr(app, "_progress"):
                tracker = app._progress
                if hasattr(tracker, "set_dual_ticks"):
                    tick1 = self._estimation_state["original_complete"]
                    tick2 = self._estimation_state["preprocessed_complete"]
                    tracker.set_dual_ticks(self.step_id, tick1, tick2)
        except Exception as e:
            logger.debug("Could not update dual ticks: %s", e)

    def _on_model_changed(self, event: Optional[tk.Event] = None) -> None:
        """Handle model selection change.

        Refreshes mode button availability for the new model and
        reprices existing token counts instantly without running a full
        re-estimation.  The token breakdown (num_requests, content_tokens,
        prompt_tokens, cached_tokens, input_tokens, output_tokens) is
        read from the stored ``EstimationResult`` objects and only the
        pricing arithmetic is repeated with the new model's rates.

        UI settings (chunk size, tokens, rolling context, etc.) are NOT
        reloaded from API.ini — they are independent and only written via
        'Apply Settings to Model'.
        """
        self._refresh_mode_buttons()
        if self._estimation_result:
            self._reprice_for_model()

    def _save_settings(self) -> None:
        """Apply current UI settings to the active model in API.ini.

        One-way write: copies the current Costs step UI values into
        the per-model settings section of API.ini.  This is the only
        path that writes settings — model changes never read them back.
        """
        model_id = self._model_var.get()
        if not model_id:
            return

        settings: dict[str, str] = {
            "chunk_size": str(self._chunk_var.get()),
            "chunk_max_tokens": str(self._tokens_var.get()),
            "thinking_enabled": str(self._thinking_var.get()),
            "use_translated_context": str(self._use_translated_ctx_var.get()),
            "rolling_context_before": str(self._rc_before_var.get()),
            "rolling_context_between": str(self._rc_between_var.get()),
            "rolling_context_after": str(self._rc_after_var.get()),
            "request_mode": self._mode_var.get(),
        }
        set_model_settings(model_id, settings)
        logger.info("Saved settings for model %s", model_id)

        # Brief visual confirmation on button
        self._save_btn.configure(text="✓ Applied")
        self.after(1500, lambda: self._save_btn.configure(
            text="📤 Apply Settings to Model",
        ))

    def _load_model_settings(self) -> None:
        """Load per-model settings from API.ini and apply to UI widgets.

        Falls back to Global Options defaults when no saved settings exist.
        """
        model_id = self._model_var.get()
        if not model_id:
            return

        saved = get_model_settings(model_id)

        # Determine defaults from Global Options (if available)
        go = getattr(self.session, "global_options", None)
        go_req = getattr(go, "request", None) if go else None

        def _int(key: str, fallback: int) -> int:
            if key in saved:
                try:
                    return int(saved[key])
                except (ValueError, TypeError):
                    pass
            if go_req is not None:
                return int(getattr(go_req, key, fallback))
            return fallback

        def _bool(key: str, fallback: bool) -> bool:
            if key in saved:
                return saved[key].lower() in ("true", "1", "yes")
            if go_req is not None:
                return bool(getattr(go_req, key, fallback))
            return fallback

        self._chunk_var.set(_int("chunk_size", 30))
        self._tokens_var.set(_int("chunk_max_tokens", 4000))
        self._thinking_var.set(_bool("thinking_enabled", False))
        self._use_translated_ctx_var.set(
            _bool("use_translated_context", True),
        )
        self._rc_before_var.set(
            _int("rolling_context_before", 3),
        )
        self._rc_between_var.set(
            _int("rolling_context_between", 0),
        )
        self._rc_after_var.set(
            _int("rolling_context_after", 0),
        )

        # Restore request mode (Task 5)
        if "request_mode" in saved:
            mode = saved["request_mode"]
            valid_modes = {k for k, _, _, _ in self._REQUEST_MODES}
            if mode in valid_modes:
                self._mode_var.set(mode)
                self._refresh_mode_buttons()

    def reset_estimation(self, reset_preprocessed_only: bool = False) -> None:
        """Reset estimation state (Task 40.4).

        Called when files change, settings change, or preprocessing is redone.

        Args:
            reset_preprocessed_only: If True, only resets preprocessed state.
        """
        if not reset_preprocessed_only:
            self._estimation_state["original_complete"] = False
            self._estimation_state["original_result"] = None
            self._estimation_result = None
        self._estimation_state["preprocessed_complete"] = False
        self._estimation_state["preprocessed_result"] = None
        logger.debug(
            "Reset estimation state (preprocessed_only=%s)",
            reset_preprocessed_only,
        )

    def on_new_project(self) -> None:
        """Reset cached state for a fresh project."""
        super().on_new_project()
        self._estimation_result = None
        self._is_estimating = False
        self._lines_original.clear()
        self._lines_preprocessed.clear()
        self._estimation_state = {
            "original_complete": False,
            "preprocessed_complete": False,
            "original_result": None,
            "preprocessed_result": None,
        }
        self._settings_loaded_once = False
        logger.debug("Costs step reset for new project")

    def on_enter(self) -> None:
        """Called when step becomes active."""
        # TASK 43.12: Sync chunk size from manifest (shared with Translation)
        mgr = self.manifest_manager
        if mgr is not None and mgr.is_loaded:
            request_opts = mgr._manifest_data.get("RequestOptions", {})
            chunk_val = request_opts.get("LinesPerChunk")
            if chunk_val is not None:
                try:
                    self._chunk_var.set(int(chunk_val))
                except (ValueError, TypeError):
                    pass

        # Load per-model settings from API.ini only on first enter.
        # Subsequent visits keep the user's current UI values.
        if not self._settings_loaded_once:
            self._load_model_settings()
            self._settings_loaded_once = True

        # Task 7: Restore full estimation from manifest if available
        saved = self._load_estimation_from_manifest()
        if saved is not None and not self._estimation_result:
            self._lines_prep_label.configure(
                text=str(saved["input_lines"]),
            )
            self._input_prep_label.configure(
                text=f"{saved['content_tokens']:,}",
            )
            self._prompt_prep_label.configure(
                text=f"{saved['prompt_tokens']:,}",
            )
            if saved["cached_tokens"]:
                self._cached_prep_label.configure(
                    text=f"{saved['cached_tokens']:,}",
                )
            self._total_input_prep_label.configure(
                text=f"{saved['input_tokens']:,}",
            )
            self._output_prep_label.configure(
                text=f"{saved['output_tokens']:,}",
            )
            if saved["num_requests"]:
                self._requests_prep_label.configure(
                    text=str(saved["num_requests"]),
                )
            if saved["total_cost"] > 0:
                self._cost_total_prep_label.configure(
                    text=f"${saved['total_cost']:.2f}",
                )
            logger.debug("Restored estimation from manifest")
            # Task 8: Show Update label when data exists
            self._estimate_btn.configure(text="↻ Update Counts")

        # Refresh lines from previous steps
        self._refresh_lines()

        # Task 40.4: Auto-estimate on enter if files loaded but no estimation yet
        if self._lines_original and not self._estimation_state["original_complete"]:
            self._run_estimation()

    def on_leave(self) -> None:
        """Called when leaving step."""
        # Store current state
        if self._estimation_result:
            self.session.get_step(self.step_id).data["estimation"] = {
                "original_tokens": self._estimation_result.original.input_tokens,
                "preprocessed_tokens": self._estimation_result.preprocessed.input_tokens,
                "cost_saved": self._estimation_result.cost_saved,
                "savings_percent": self._estimation_result.savings_percent,
            }

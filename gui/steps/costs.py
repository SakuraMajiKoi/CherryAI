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

# TASK 25.1: Import manifest field helpers for saving/loading analysis results
from CherryAI.functions.manifest_fields import (
    get_all_lines_resolved,
    save_int_field,
    load_int_field,
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


@dataclass
class ComparisonResult:
    """Comparison between original and preprocessed estimation."""

    original: EstimationResult
    preprocessed: EstimationResult
    tokens_saved: int
    cost_saved: float
    savings_percent: float


# count_tokens imported directly from chunker_adapter - no wrapper needed


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

    # Ceil to nearest cent
    def _ceil_to_cents(x: float) -> float:
        return math.ceil(x * 100.0 - 1e-12) / 100.0

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
        super().__init__(parent, session, manifest_manager=manifest_manager)

    def _build_ui(self) -> None:
        """Build the step UI."""
        self._build_header()
        self._build_content()

    def _build_header(self) -> None:
        """Build the header section with controls."""
        header = ttk.Frame(self)
        header.pack(fill="x", padx=10, pady=5)

        # Model selection
        model_frame = ttk.Frame(header)
        model_frame.pack(side="left")

        ttk.Label(model_frame, text="Primary Model:").pack(side="left", padx=(0, 5))
        self._model_var = tk.StringVar(value=DEFAULT_PRICING_MODEL)
        self._model_combo = ttk.Combobox(
            model_frame,
            textvariable=self._model_var,
            values=get_model_names(),
            state="readonly",
            width=20,
        )
        self._model_combo.pack(side="left")
        self._model_combo.bind("<<ComboboxSelected>>", self._on_model_changed)

        # Chunk size (Lines/Request)
        chunk_frame = ttk.Frame(header)
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
        tokens_frame = ttk.Frame(header)
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
            header,
            text="▶ Estimate",
            command=self._run_estimation,
        )
        self._estimate_btn.pack(side="right", padx=(5, 0))

        # Refresh button
        ttk.Button(
            header,
            text="↻ Refresh",
            command=self._refresh_lines,
        ).pack(side="right")

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

        # Input tokens row
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

        # Output tokens row (estimated)
        ttk.Label(self._token_grid, text="Output Tokens (est):").grid(
            row=3, column=0, sticky="w"
        )
        self._output_orig_label = ttk.Label(self._token_grid, text="-")
        self._output_orig_label.grid(row=3, column=1)
        self._output_prep_label = ttk.Label(self._token_grid, text="-")
        self._output_prep_label.grid(row=3, column=2)
        self._output_saved_label = ttk.Label(
            self._token_grid,
            text="-",
            foreground=THEME.accent_success,
        )
        self._output_saved_label.grid(row=3, column=3)

        # Prompt tokens row (overhead per request)
        ttk.Label(self._token_grid, text="Prompt Overhead:").grid(
            row=4, column=0, sticky="w"
        )
        self._prompt_tokens_label = ttk.Label(self._token_grid, text="-")
        self._prompt_tokens_label.grid(row=4, column=1, columnspan=3)

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

        # Output cost row
        ttk.Label(self._cost_grid, text="Output Cost:").grid(row=3, column=0, sticky="w")
        self._cost_output_orig_label = ttk.Label(self._cost_grid, text="-")
        self._cost_output_orig_label.grid(row=3, column=1)
        self._cost_output_prep_label = ttk.Label(self._cost_grid, text="-")
        self._cost_output_prep_label.grid(row=3, column=2)

        # Total cost row (highlighted)
        ttk.Label(
            self._cost_grid,
            text="Total Cost:",
            font=("TkDefaultFont", 10, "bold"),
        ).grid(row=4, column=0, sticky="w")
        self._cost_total_orig_label = ttk.Label(
            self._cost_grid,
            text="-",
            font=("TkDefaultFont", 10, "bold"),
        )
        self._cost_total_orig_label.grid(row=4, column=1)
        self._cost_total_prep_label = ttk.Label(
            self._cost_grid,
            text="-",
            font=("TkDefaultFont", 10, "bold"),
            foreground=THEME.accent_success,
        )
        self._cost_total_prep_label.grid(row=4, column=2)

        # Savings row
        ttk.Label(self._cost_grid, text="").grid(row=5, column=0)
        self._savings_label = ttk.Label(
            self._cost_grid,
            text="",
            font=("TkDefaultFont", 10, "bold"),
            foreground=THEME.accent_success,
        )
        self._savings_label.grid(row=5, column=1, columnspan=2, pady=(5, 0))

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

    def _build_comparison_table(self, parent: ttk.LabelFrame) -> None:
        """Build the model comparison table."""
        # Define columns
        columns = [
            ColumnDef(key="model", title="Model", width=150),
            ColumnDef(key="input_price", title="Input $/1M", width=80, anchor="e"),
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

        for idx, (model_id, pricing) in enumerate(get_all_model_pricing().items()):
            # Calculate costs if we have estimation data
            if self._estimation_result:
                orig = self._estimation_result.original
                prep = self._estimation_result.preprocessed

                # Calculate for this model
                orig_cost = estimate_cost(
                    orig.input_tokens, orig.output_tokens, model_id
                )
                prep_cost = estimate_cost(
                    prep.input_tokens, prep.output_tokens, model_id
                )

                orig_total = orig_cost["total_usd"]
                prep_total = prep_cost["total_usd"]
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
                    "input_price": f"${pricing['input']:.2f}",
                    "output_price": f"${pricing['output']:.2f}",
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

        Builds the full §5.2 system prompt using
        ``build_full_system_prompt`` so the estimate covers all
        sections: Language, System Instructions, Style, Tone,
        Summary, Genre, POV, Conditional, Glossary, and Characters.

        Returns:
            Estimated token count for system prompt.
        """
        try:
            # Read Information step metadata (step index 2)
            info_data = self.session.get_step(2).data
            metadata = info_data.get("metadata", {})

            # Glossary from manifest
            glossary_entries: list[dict] = []
            mgr = self.manifest_manager
            if mgr is not None and mgr.is_loaded:
                try:
                    from CherryAI.functions.manifest_fields import (
                        load_glossary_entries,
                    )
                    glossary_entries = load_glossary_entries(mgr)
                except ImportError:
                    pass

            # Characters from metadata + manifest top-level
            characters = metadata.get("characters", [])
            if not characters and mgr is not None and mgr.is_loaded:
                characters = mgr._manifest_data.get("characters", [])

            # POV from manifest top-level
            pov_data: dict = {}
            if mgr is not None and mgr.is_loaded:
                pov_data = mgr._manifest_data.get("POV", {})

            # Sample preprocessed lines for conditional prompt detection
            sample_lines = self._lines_preprocessed[:200] if self._lines_preprocessed else []

            # Build the full prompt using the shared builder
            prompt_text, breakdown = build_full_system_prompt(
                metadata=metadata,
                glossary_entries=glossary_entries,
                characters=characters,
                sample_lines=sample_lines,
                pov_data=pov_data,
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

        Instead of building one maximum-sized prompt and multiplying by
        the number of requests, this builds the selective prompt for each
        request's chunk lines (applying glossary/conditional filtering)
        and sums the individual token counts.

        Args:
            request_line_lists: Per-request translatable line texts
                from :class:`FormationResult`.

        Returns:
            Tuple of (total_prompt_tokens, average_per_request).
        """
        if not request_line_lists:
            return 0, 0

        try:
            info_data = self.session.get_step(2).data
            metadata = info_data.get("metadata", {})

            glossary_entries: list[dict] = []
            mgr = self.manifest_manager
            if mgr is not None and mgr.is_loaded:
                try:
                    from CherryAI.functions.manifest_fields import (
                        load_glossary_entries,
                    )
                    glossary_entries = load_glossary_entries(mgr)
                except ImportError:
                    pass

            characters = metadata.get("characters", [])
            if not characters and mgr is not None and mgr.is_loaded:
                characters = mgr._manifest_data.get("characters", [])

            pov_data: dict = {}
            if mgr is not None and mgr.is_loaded:
                pov_data = mgr._manifest_data.get("POV", {})

            total_tokens = 0
            for chunk_lines in request_line_lists:
                prompt_text, _ = build_full_system_prompt(
                    metadata=metadata,
                    glossary_entries=glossary_entries,
                    characters=characters,
                    chunk_lines=chunk_lines,
                    pov_data=pov_data,
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

        # Run in background
        thread = threading.Thread(target=self._do_estimation)
        thread.daemon = True
        thread.start()

    def _do_estimation(self) -> None:
        """Perform estimation in background thread.

        Uses the same 4-step formation pipeline as Translation (Step 5)
        when available, so request counts match actual API usage.
        """
        try:
            model_id = self._model_var.get()
            chunk_size = self._chunk_var.get()
            tokens_limit = self._tokens_var.get()

            # Sync chunk_size from Global Options if available
            go = getattr(self.session, "global_options", None)
            if go is not None and hasattr(go, "request"):
                try:
                    go_chunk = int(go.request.chunk_size)
                    if go_chunk >= 1:
                        chunk_size = go_chunk
                        self.after(
                            0,
                            lambda v=go_chunk: self._chunk_var.set(v),
                        )
                except (TypeError, ValueError, AttributeError):
                    pass
                # Sync max_input_tokens from Global Options
                try:
                    go_tokens = int(go.request.max_input_tokens)
                    if go_tokens >= 0:
                        tokens_limit = go_tokens
                        self.after(
                            0,
                            lambda v=go_tokens: self._tokens_var.set(v),
                        )
                except (TypeError, ValueError, AttributeError):
                    pass

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
            orig_formation = self._estimate_via_formation(
                self._lines_original, chunk_size, slicing,
                skip_indices=orig_skip,
                max_input_tokens=tokens_limit,
            )
            prep_formation = self._estimate_via_formation(
                self._lines_preprocessed, chunk_size, slicing,
                skip_indices=prep_skip,
                max_input_tokens=tokens_limit,
            )

            # ── Original estimation ──
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

            # Estimate costs (including prompt overhead)
            orig_cost = estimate_cost(orig_total_input, orig_output_tokens, model_id)
            prep_cost = estimate_cost(prep_total_input, prep_output_tokens, model_id)

            # Build results (store total tokens including overhead)
            original = EstimationResult(
                input_tokens=orig_total_input,
                output_tokens=orig_output_tokens,
                input_cost=orig_cost["input_usd"],
                output_cost=orig_cost["output_usd"],
                total_cost=orig_cost["total_usd"],
                token_method=orig_method,
            )

            preprocessed = EstimationResult(
                input_tokens=prep_total_input,
                output_tokens=prep_output_tokens,
                input_cost=prep_cost["input_usd"],
                output_cost=prep_cost["output_usd"],
                total_cost=prep_cost["total_usd"],
                token_method=prep_method,
            )

            tokens_saved = orig_total_input - prep_total_input
            cost_saved = orig_cost["total_usd"] - prep_cost["total_usd"]
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
                is_placeholder_only,
            )
        except ImportError:
            return None

        _skip = skip_indices or frozenset()

        line_infos: list[LineInfo] = []
        for idx, text in enumerate(lines):
            is_invalid = (
                not text.strip()
                or is_placeholder_only(text)
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
                        context_marker="file_end",
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
        # Update token labels
        self._input_orig_label.configure(text=f"{original.input_tokens:,}")
        self._input_prep_label.configure(text=f"{preprocessed.input_tokens:,}")
        saved = original.input_tokens - preprocessed.input_tokens
        self._input_saved_label.configure(
            text=f"-{saved:,}" if saved > 0 else "0"
        )

        self._output_orig_label.configure(text=f"{original.output_tokens:,}")
        self._output_prep_label.configure(text=f"{preprocessed.output_tokens:,}")
        saved = original.output_tokens - preprocessed.output_tokens
        self._output_saved_label.configure(
            text=f"-{saved:,}" if saved > 0 else "0"
        )

        # Update prompt overhead label
        if prompt_tokens_total > 0:
            self._prompt_tokens_label.configure(
                text=(
                    f"~{prompt_tokens_total:,} total "
                    f"({prep_requests} Requests, "
                    f"~{prompt_tokens_avg:,} avg/request)"
                )
            )
        else:
            self._prompt_tokens_label.configure(text="(no prompt data available)")

        # Update cost labels
        pricing = get_model_pricing(model_id)
        self._model_label.configure(text=f"{pricing['name']} ({model_id})")

        self._cost_input_orig_label.configure(text=f"${original.input_cost:.2f}")
        self._cost_input_prep_label.configure(text=f"${preprocessed.input_cost:.2f}")

        self._cost_output_orig_label.configure(text=f"${original.output_cost:.2f}")
        self._cost_output_prep_label.configure(text=f"${preprocessed.output_cost:.2f}")

        self._cost_total_orig_label.configure(text=f"${original.total_cost:.2f}")
        self._cost_total_prep_label.configure(text=f"${preprocessed.total_cost:.2f}")

        # Savings summary
        if self._estimation_result:
            pct = self._estimation_result.savings_percent
            cost = self._estimation_result.cost_saved
            if cost > 0:
                self._savings_label.configure(
                    text=f"💰 Save ${cost:.2f} ({pct:.1f}% tokens)"
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

        # TASK 25.1: Save analysis results to manifest
        self._save_analysis_results_to_manifest(
            input_lines=len(self._lines_preprocessed),
            input_tokens=preprocessed.input_tokens,
            output_tokens=preprocessed.output_tokens,
        )

    def _save_analysis_results_to_manifest(
        self,
        input_lines: int,
        input_tokens: int,
        output_tokens: int,
    ) -> None:
        """Save analysis results to manifest (TASK 25.1).
        
        Args:
            input_lines: Number of lines to translate.
            input_tokens: Estimated input tokens.
            output_tokens: Estimated output tokens.
        """
        if self.manifest_manager is None:
            logger.debug("No manifest manager, skipping save")
            return
        
        save_int_field(self.manifest_manager, "InputLines", input_lines)
        save_int_field(self.manifest_manager, "InputTokens", input_tokens)
        save_int_field(self.manifest_manager, "OutputTokens", output_tokens)
        logger.debug(
            "Saved analysis results to manifest: lines=%d, input=%d, output=%d",
            input_lines, input_tokens, output_tokens
        )

    def _load_analysis_results_from_manifest(self) -> Dict[str, int]:
        """Load analysis results from manifest (TASK 25.1).
        
        Returns:
            Dict with input_lines, input_tokens, output_tokens.
        """
        if self.manifest_manager is None:
            return {"input_lines": 0, "input_tokens": 0, "output_tokens": 0}
        
        return {
            "input_lines": load_int_field(self.manifest_manager, "InputLines", 0),
            "input_tokens": load_int_field(self.manifest_manager, "InputTokens", 0),
            "output_tokens": load_int_field(self.manifest_manager, "OutputTokens", 0),
        }

    def _estimation_complete(self) -> None:
        """Called when estimation completes."""
        self._is_estimating = False
        self._estimate_btn.configure(state="normal", text="▶ Estimate")

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
        """Handle model selection change."""
        if self._estimation_result:
            # Re-run estimation with new model
            self._run_estimation()

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

        # TASK 25.1: Load saved analysis results from manifest
        saved_results = self._load_analysis_results_from_manifest()
        if saved_results["input_lines"] > 0 and not self._estimation_result:
            # Display saved values in UI
            self._lines_prep_label.configure(text=str(saved_results["input_lines"]))
            self._input_prep_label.configure(text=f"{saved_results['input_tokens']:,}")
            self._output_prep_label.configure(text=f"{saved_results['output_tokens']:,}")
            logger.debug("Loaded saved analysis results from manifest")

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

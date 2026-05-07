"""Header-Based Rate Limiter for CherryAI.

Per-model rate limiting driven by API response headers. Designed
to be reusable across providers with different URLs and header names.

Architecture
------------
- ``ProviderRateLimitConfig`` — Configurable header names and defaults per provider.
- ``ModelWindowState``        — Runtime counters and reset timers for one model.
- ``HeaderBasedRateLimiter``  — Thread-safe, per-model rate limit enforcement.

Usage flow
----------
1. Before sending a request, call ``pre_request(model, estimated_tokens)``
   — blocks (sleeps) until the limit window has capacity.
2. After receiving a response, call ``update_from_headers(model, headers)``
   — reads the reset timing from the provider's response headers.

Token estimation
----------------
``estimated_tokens = sent_request_token_count + (input_line_token_count * 1.5)``

The 1.5 multiplier accounts for expected maximum output token usage.

Reset timing
------------
* ``x-ratelimit-reset-requests`` / ``x-ratelimit-reset-tokens`` headers
  convey the seconds (or a duration string) until a window resets.
* A monotonic timer tracks the absolute reset instant so system clock
  changes do not affect rate limiting.
* If reset headers are absent, a configurable default window (60 s) is used.
"""

from __future__ import annotations

import logging
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class ProviderRateLimitConfig:
    """Rate-limit header configuration for a single provider.

    Different providers use different header names and URL endpoints
    for rate-limit information.  Instances of this class make the
    rate limiter reusable across providers.

    Attributes:
        provider_name:          Human name (logging only).
        limit_requests_header:  Header for max requests per window.
        limit_tokens_header:    Header for max tokens per window.
        reset_requests_header:  Header for request-window reset timing.
        reset_tokens_header:    Header for token-window reset timing.
        remaining_requests_header: Header for remaining requests.
        remaining_tokens_header:   Header for remaining tokens.
        limits_url:             Optional URL to bulk-fetch model limits.
        default_reset_seconds:  Fallback reset window when headers are missing.
    """

    provider_name: str = "openai"
    limit_requests_header: str = "x-ratelimit-limit-requests"
    limit_tokens_header: str = "x-ratelimit-limit-tokens"
    reset_requests_header: str = "x-ratelimit-reset-requests"
    reset_tokens_header: str = "x-ratelimit-reset-tokens"
    remaining_requests_header: str = "x-ratelimit-remaining-requests"
    remaining_tokens_header: str = "x-ratelimit-remaining-tokens"
    limits_url: str = ""
    default_reset_seconds: float = 60.0


# Pre-built configs for known providers
OPENAI_RATE_LIMIT_CONFIG = ProviderRateLimitConfig(
    provider_name="openai",
    limits_url="https://api.openai.com/v1/fine_tuning/model_limits",
)

GEMINI_RATE_LIMIT_CONFIG = ProviderRateLimitConfig(
    provider_name="gemini",
    # Gemini uses different header names
    limit_requests_header="x-ratelimit-limit-requests",
    limit_tokens_header="x-ratelimit-limit-tokens",
    reset_requests_header="x-ratelimit-reset-requests",
    reset_tokens_header="x-ratelimit-reset-tokens",
)


# ---------------------------------------------------------------------------
# Per-model runtime state
# ---------------------------------------------------------------------------

@dataclass
class ModelWindowState:
    """Runtime counters and reset timers for a single model.

    All times use ``time.monotonic()`` to be immune to clock changes.
    """

    model: str
    # Counters
    requests_in_window: int = 0
    tokens_in_window: int = 0
    # Limits (0 = unlimited)
    limit_requests: int = 0
    limit_tokens: int = 0
    # Monotonic instants when the respective counters should reset.
    # ``None`` means "not yet known — use default_reset_seconds".
    reset_requests_at: Optional[float] = None
    reset_tokens_at: Optional[float] = None
    token_reservations: List["TokenReservation"] = field(default_factory=list)
    next_reservation_id: int = 1
    token_accounting_mode: Optional[str] = None


@dataclass
class TokenReservation:
    """A token reservation for one request started within the active window."""

    reservation_id: int
    started_at: float
    estimated_tokens: int
    counted_tokens: int


# ---------------------------------------------------------------------------
# Duration parser  (e.g. "6m0s", "1s", "200ms", "1m30s")
# ---------------------------------------------------------------------------

_DURATION_RE = re.compile(
    r"(?:(\d+)h)?(?:(\d+)m(?!s))?(?:(\d+(?:\.\d+)?)s)?(?:(\d+)ms)?",
)


def parse_reset_duration(value: str) -> float:
    """Parse a duration string into seconds.

    Supported formats (from OpenAI headers):
        ``"1s"``, ``"6m0s"``, ``"200ms"``, ``"1h2m3s"``, ``"1m30s200ms"``
        Also handles plain numeric strings (treated as seconds).

    Returns:
        Duration in seconds.  Returns 0.0 on parse failure.
    """
    value = value.strip()
    if not value:
        return 0.0

    # Plain number → seconds
    try:
        return float(value)
    except ValueError:
        pass

    m = _DURATION_RE.fullmatch(value)
    if not m:
        return 0.0

    hours = int(m.group(1)) if m.group(1) else 0
    minutes = int(m.group(2)) if m.group(2) else 0
    seconds = float(m.group(3)) if m.group(3) else 0.0
    millis = int(m.group(4)) if m.group(4) else 0

    return hours * 3600 + minutes * 60 + seconds + millis / 1000.0


# ---------------------------------------------------------------------------
# Header-based rate limiter
# ---------------------------------------------------------------------------

class HeaderBasedRateLimiter:
    """Thread-safe, per-model rate limiter driven by API response headers.

    **Thread safety**: All state mutations are guarded by a single
    ``threading.Lock`` per limiter instance.

    **Monotonic timing**: ``time.monotonic()`` is used for all time
    comparisons so that NTP jumps or DST changes cannot cause stalls.

    **Provider-agnostic**: The header names and endpoint URLs are
    configured via ``ProviderRateLimitConfig``.

    Typical usage::

        limiter = HeaderBasedRateLimiter(OPENAI_RATE_LIMIT_CONFIG)
        limiter.set_model_limits("gpt-4o", rpm=500, tpm=30000)

        # Before each request:
        limiter.pre_request("gpt-4o", estimated_tokens=3500)

        # After each response:
        limiter.update_from_headers("gpt-4o", response_headers)
    """

    def __init__(
        self,
        config: Optional[ProviderRateLimitConfig] = None,
    ) -> None:
        self._config = config or OPENAI_RATE_LIMIT_CONFIG
        self._lock = threading.Lock()
        # model_id → ModelWindowState
        self._states: Dict[str, ModelWindowState] = {}

    # ------------------------------------------------------------------ #
    #  Public: configure limits                                           #
    # ------------------------------------------------------------------ #

    def set_model_limits(
        self,
        model: str,
        rpm: int = 0,
        tpm: int = 0,
    ) -> None:
        """Set (or update) the rate limits for *model*.

        Args:
            model: Model identifier (e.g. ``"gpt-4o"``).
            rpm:   Requests per minute (0 = unlimited).
            tpm:   Tokens per minute (0 = unlimited).
        """
        with self._lock:
            state = self._get_or_create(model)
            state.limit_requests = rpm
            state.limit_tokens = tpm

    def get_model_limits(self, model: str) -> Dict[str, int]:
        """Return the current limits for *model*."""
        with self._lock:
            state = self._states.get(model)
            if state is None:
                return {"rpm": 0, "tpm": 0}
            return {
                "rpm": state.limit_requests,
                "tpm": state.limit_tokens,
            }

    # ------------------------------------------------------------------ #
    #  Public: pre-request gate                                           #
    # ------------------------------------------------------------------ #

    def pre_request(
        self,
        model: str,
        estimated_tokens: int,
        *,
        max_wait: float = 120.0,
        progress_callback: Optional[Any] = None,
    ) -> int:
        """Block until the model's rate limit window has capacity.

        Increments ``requests_in_window`` and ``tokens_in_window`` before
        returning.  If either counter would exceed its limit the call
        sleeps until the corresponding reset instant.

        Args:
            model:             Model identifier.
            estimated_tokens:  ``sent_token_count + input_line_tokens * 1.5``
            max_wait:          Maximum seconds to block (safety valve).
            progress_callback: Optional ``(waited, total)`` callback.
        """
        waited = 0.0

        while True:
            with self._lock:
                state = self._get_or_create(model)
                self._maybe_reset(state)

                # Unlimited → nothing to enforce
                if state.limit_requests == 0 and state.limit_tokens == 0:
                    state.requests_in_window += 1
                    return self._reserve_tokens(state, estimated_tokens)

                # Check request limit
                wait_for: float = 0.0
                request_wait_for = 0.0
                token_wait_for = 0.0
                if (state.limit_requests > 0
                        and state.requests_in_window + 1 > state.limit_requests):
                    request_wait_for = self._time_until_reset(
                        state.reset_requests_at,
                    )
                    wait_for = max(wait_for, request_wait_for)

                # Check token limit
                if (state.limit_tokens > 0
                        and state.tokens_in_window + estimated_tokens
                        > state.limit_tokens):
                    token_wait_for = self._time_until_token_capacity(state)
                    wait_for = max(wait_for, token_wait_for)

                if wait_for <= 0:
                    # Capacity available — commit the counters
                    state.requests_in_window += 1
                    # If no reset time is set yet, schedule default
                    now = time.monotonic()
                    default = self._config.default_reset_seconds
                    if state.reset_requests_at is None:
                        state.reset_requests_at = now + default
                    return self._reserve_tokens(state, estimated_tokens, now=now)

                if token_wait_for <= 0 and waited >= max_wait:
                    logger.warning(
                        "Rate limit %s/%s: max wait %.1fs exceeded, proceeding anyway",
                        self._config.provider_name, model, max_wait,
                    )
                    state.requests_in_window += 1
                    if state.reset_requests_at is None:
                        state.reset_requests_at = (
                            time.monotonic() + self._config.default_reset_seconds
                        )
                    return self._reserve_tokens(state, estimated_tokens)

            # --- Must wait (outside the lock) ---
            sleep_step = min(1.0, wait_for)
            logger.info(
                "Rate limit %s/%s: waiting %.1fs "
                "(req %d/%d, tok %d/%d)",
                self._config.provider_name, model, wait_for,
                state.requests_in_window, state.limit_requests,
                state.tokens_in_window, state.limit_tokens,
            )
            time.sleep(sleep_step)
            waited += sleep_step
            if progress_callback is not None:
                progress_callback(waited, max_wait)

    # ------------------------------------------------------------------ #
    #  Public: post-response header update                                #
    # ------------------------------------------------------------------ #

    def update_from_headers(
        self,
        model: str,
        headers: Optional[Dict[str, str]],
        *,
        reservation_id: Optional[int] = None,
        usage: Optional[Dict[str, int]] = None,
    ) -> None:
        """Update limits and reset timers from provider response headers.

        Called after every successful API response so that the limiter
        tracks the true server-side rate-limit state.

        Args:
            model:   Model identifier.
            headers: HTTP response headers (case-insensitive keys).
        """
        # Normalise header keys to lower-case
        h = {k.lower(): v for k, v in (headers or {}).items()}
        now = time.monotonic()

        with self._lock:
            state = self._get_or_create(model)
            self._maybe_reset(state)

            # Update limits if provided
            cfg = self._config
            lim_req = h.get(cfg.limit_requests_header)
            if lim_req is not None:
                try:
                    state.limit_requests = int(lim_req)
                except ValueError:
                    pass

            lim_tok = h.get(cfg.limit_tokens_header)
            if lim_tok is not None:
                try:
                    state.limit_tokens = int(lim_tok)
                except ValueError:
                    pass

            # Update remaining counters if provided (server truth)
            rem_req = h.get(cfg.remaining_requests_header)
            if rem_req is not None:
                try:
                    remaining_req = int(rem_req)
                    if state.limit_requests > 0:
                        state.requests_in_window = (
                            state.limit_requests - remaining_req
                        )
                except ValueError:
                    pass

            rem_tok = h.get(cfg.remaining_tokens_header)
            if rem_tok is not None:
                try:
                    int(rem_tok)
                except ValueError:
                    pass

            # Update reset timing
            reset_req = h.get(cfg.reset_requests_header)
            if reset_req is not None:
                seconds = parse_reset_duration(reset_req)
                if seconds > 0:
                    state.reset_requests_at = now + seconds

            reset_tok = h.get(cfg.reset_tokens_header)
            if reset_tok is not None:
                seconds = parse_reset_duration(reset_tok)
                if seconds > 0:
                    state.reset_tokens_at = now + seconds

            if reservation_id is not None:
                reservation = self._find_reservation(state, reservation_id)
                if reservation is not None:
                    reservation.counted_tokens = self._resolve_counted_tokens(
                        state=state,
                        reservation=reservation,
                        usage=usage,
                        remaining_tokens_header=h.get(
                            cfg.remaining_tokens_header,
                        ),
                    )
                    state.tokens_in_window = self._sum_reserved_tokens(state)

    # ------------------------------------------------------------------ #
    #  Public: stats / diagnostics                                        #
    # ------------------------------------------------------------------ #

    def get_stats(self, model: str) -> Dict[str, Any]:
        """Return current counters and limits for *model*."""
        with self._lock:
            state = self._states.get(model)
            if state is None:
                return {
                    "model": model,
                    "requests_in_window": 0,
                    "tokens_in_window": 0,
                    "limit_requests": 0,
                    "limit_tokens": 0,
                    "seconds_until_request_reset": 0.0,
                    "seconds_until_token_reset": 0.0,
                }
            self._maybe_reset(state)
            now = time.monotonic()
            return {
                "model": model,
                "requests_in_window": state.requests_in_window,
                "tokens_in_window": state.tokens_in_window,
                "limit_requests": state.limit_requests,
                "limit_tokens": state.limit_tokens,
                "seconds_until_request_reset": max(
                    0.0,
                    (state.reset_requests_at or now) - now,
                ),
                "seconds_until_token_reset": max(
                    0.0,
                    self._token_reset_at(state, now) - now,
                ),
            }

    def reset_model(self, model: str) -> None:
        """Manually reset all counters for *model*."""
        with self._lock:
            state = self._states.get(model)
            if state is not None:
                state.requests_in_window = 0
                state.tokens_in_window = 0
                state.reset_requests_at = None
                state.reset_tokens_at = None
                state.token_reservations.clear()
                state.token_accounting_mode = None

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                   #
    # ------------------------------------------------------------------ #

    def _get_or_create(self, model: str) -> ModelWindowState:
        """Return (or create) the state object for *model*.

        Must be called with ``self._lock`` held.
        """
        state = self._states.get(model)
        if state is None:
            state = ModelWindowState(model=model)
            self._states[model] = state
        return state

    def _maybe_reset(self, state: ModelWindowState) -> None:
        """Reset counters whose window has elapsed.

        Must be called with ``self._lock`` held.
        """
        now = time.monotonic()
        if (state.reset_requests_at is not None
                and now >= state.reset_requests_at):
            state.requests_in_window = 0
            state.reset_requests_at = None
        self._prune_expired_reservations(state, now)
        if state.tokens_in_window == 0 and state.reset_tokens_at is not None:
            if now >= state.reset_tokens_at:
                state.reset_tokens_at = None

    def _time_until_reset(self, reset_at: Optional[float]) -> float:
        """Seconds until the given reset instant (≥ 0).

        Falls back to ``default_reset_seconds`` when *reset_at* is unknown.
        """
        if reset_at is None:
            return self._config.default_reset_seconds
        remaining = reset_at - time.monotonic()
        return max(0.0, remaining)

    def _reserve_tokens(
        self,
        state: ModelWindowState,
        estimated_tokens: int,
        *,
        now: Optional[float] = None,
    ) -> int:
        """Reserve estimated tokens in the rolling 60-second window."""
        if now is None:
            now = time.monotonic()
        reservation_id = state.next_reservation_id
        state.next_reservation_id += 1
        state.token_reservations.append(TokenReservation(
            reservation_id=reservation_id,
            started_at=now,
            estimated_tokens=max(0, estimated_tokens),
            counted_tokens=max(0, estimated_tokens),
        ))
        state.tokens_in_window = self._sum_reserved_tokens(state)
        next_reset = self._token_reset_at(state, now)
        state.reset_tokens_at = next_reset if next_reset > now else None
        return reservation_id

    def _prune_expired_reservations(
        self,
        state: ModelWindowState,
        now: float,
    ) -> None:
        """Drop reservations whose 60-second window has elapsed."""
        window_seconds = self._config.default_reset_seconds
        state.token_reservations = [
            reservation
            for reservation in state.token_reservations
            if now - reservation.started_at < window_seconds
        ]
        state.tokens_in_window = self._sum_reserved_tokens(state)

    def _sum_reserved_tokens(self, state: ModelWindowState) -> int:
        return sum(reservation.counted_tokens for reservation in state.token_reservations)

    def _time_until_token_capacity(self, state: ModelWindowState) -> float:
        now = time.monotonic()
        self._prune_expired_reservations(state, now)
        if not state.token_reservations:
            return 0.0
        oldest = state.token_reservations[0]
        return max(0.0, oldest.started_at + self._config.default_reset_seconds - now)

    def _find_reservation(
        self,
        state: ModelWindowState,
        reservation_id: int,
    ) -> Optional[TokenReservation]:
        for reservation in state.token_reservations:
            if reservation.reservation_id == reservation_id:
                return reservation
        return None

    def _resolve_counted_tokens(
        self,
        *,
        state: ModelWindowState,
        reservation: TokenReservation,
        usage: Optional[Dict[str, int]],
        remaining_tokens_header: Optional[str],
    ) -> int:
        """Replace the estimated reservation with the best known counted value."""
        prompt_tokens = max(0, int((usage or {}).get("prompt_tokens", 0) or 0))
        completion_tokens = max(0, int((usage or {}).get("completion_tokens", 0) or 0))
        total_tokens = max(
            0,
            int((usage or {}).get("total_tokens", 0) or (prompt_tokens + completion_tokens)),
        )

        if state.token_accounting_mode is None:
            inferred_mode = self._infer_token_accounting_mode(
                state=state,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                remaining_tokens_header=remaining_tokens_header,
            )
            if inferred_mode is not None:
                state.token_accounting_mode = inferred_mode

        mode = state.token_accounting_mode
        if mode == "prompt":
            return prompt_tokens or reservation.estimated_tokens
        if mode == "completion":
            return completion_tokens or max(0, reservation.estimated_tokens - prompt_tokens)
        if mode == "total":
            return total_tokens or reservation.estimated_tokens

        if total_tokens > 0:
            return max(reservation.estimated_tokens, total_tokens)
        return reservation.estimated_tokens

    def _infer_token_accounting_mode(
        self,
        *,
        state: ModelWindowState,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        remaining_tokens_header: Optional[str],
    ) -> Optional[str]:
        """Infer what the provider counts when the observation is unambiguous."""
        if state.limit_tokens <= 0:
            return None
        if remaining_tokens_header is None:
            return None
        if len(state.token_reservations) != 1:
            return None
        try:
            remaining_tokens = int(remaining_tokens_header)
        except ValueError:
            return None

        observed_consumed = max(0, state.limit_tokens - remaining_tokens)
        candidates = {
            "prompt": prompt_tokens,
            "completion": completion_tokens,
            "total": total_tokens,
        }
        for mode, candidate in candidates.items():
            if candidate > 0 and candidate == observed_consumed:
                return mode
        return None

    def _token_reset_at(
        self,
        state: ModelWindowState,
        now: Optional[float] = None,
    ) -> float:
        if now is None:
            now = time.monotonic()
        if state.token_reservations:
            return state.token_reservations[0].started_at + self._config.default_reset_seconds
        return state.reset_tokens_at or now

"""Rate Limit Management for CherryAI.

Provides comprehensive rate limit tracking and management for API requests,
supporting both RPM (requests per minute) and daily limits with persistent
storage and concurrent request management.

Features:
- Token bucket algorithm for RPM management
- Sliding window for more accurate rate tracking
- Daily request/token tracking with automatic reset
- Persistent storage for cross-session tracking
- Per-model rate limit configuration
- Pre-request limit checking
- Thread-safe operation
"""

from __future__ import annotations

import json
import math
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


class RateLimitType(Enum):
    """Types of rate limits."""
    
    RPM = "rpm"  # Requests per minute
    TPM = "tpm"  # Tokens per minute (input)
    RPD = "rpd"  # Requests per day
    TPD = "tpd"  # Tokens per day


class RateLimitAction(Enum):
    """Actions to take when rate limit is reached."""
    
    WAIT = "wait"  # Wait until limit resets
    SKIP = "skip"  # Skip the request
    ERROR = "error"  # Raise an error
    QUEUE = "queue"  # Queue for later


@dataclass
class ModelRateLimits:
    """Rate limits for a specific model."""
    
    model_name: str
    rpm: int = 60  # Requests per minute
    tpm: int = 40000  # Tokens per minute (input)
    rpd: int = 0  # Requests per day (0 = unlimited)
    tpd: int = 0  # Tokens per day (0 = unlimited)
    description: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "model_name": self.model_name,
            "rpm": self.rpm,
            "tpm": self.tpm,
            "rpd": self.rpd,
            "tpd": self.tpd,
            "description": self.description,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ModelRateLimits:
        """Create from dictionary."""
        return cls(
            model_name=data.get("model_name", "unknown"),
            rpm=int(data.get("rpm", 60)),
            tpm=int(data.get("tpm", 40000)),
            rpd=int(data.get("rpd", 0)),
            tpd=int(data.get("tpd", 0)),
            description=data.get("description", ""),
        )


# Default rate limits for common models (free tier)
DEFAULT_MODEL_LIMITS: Dict[str, ModelRateLimits] = {
    # Gemini models (free tier)
    "gemini-2.0-flash": ModelRateLimits(
        model_name="gemini-2.0-flash",
        rpm=15,
        tpm=1000000,
        rpd=1500,
        description="Gemini 2.0 Flash free tier",
    ),
    "gemini-2.0-flash-lite": ModelRateLimits(
        model_name="gemini-2.0-flash-lite",
        rpm=30,
        tpm=1000000,
        rpd=1500,
        description="Gemini 2.0 Flash Lite free tier",
    ),
    "gemini-2.5-flash": ModelRateLimits(
        model_name="gemini-2.5-flash",
        rpm=10,
        tpm=250000,
        rpd=500,
        description="Gemini 2.5 Flash free tier",
    ),
    "gemini-2.5-flash-lite": ModelRateLimits(
        model_name="gemini-2.5-flash-lite",
        rpm=30,
        tpm=1000000,
        rpd=1500,
        description="Gemini 2.5 Flash Lite free tier",
    ),
    "gemini-2.5-pro": ModelRateLimits(
        model_name="gemini-2.5-pro",
        rpm=5,
        tpm=250000,
        rpd=50,
        description="Gemini 2.5 Pro free tier",
    ),
    # OpenAI models (tier 1 defaults)
    "gpt-4o": ModelRateLimits(
        model_name="gpt-4o",
        rpm=500,
        tpm=30000,
        description="GPT-4o Tier 1",
    ),
    "gpt-4o-mini": ModelRateLimits(
        model_name="gpt-4o-mini",
        rpm=500,
        tpm=200000,
        description="GPT-4o Mini Tier 1",
    ),
    "gpt-4-turbo": ModelRateLimits(
        model_name="gpt-4-turbo",
        rpm=500,
        tpm=30000,
        description="GPT-4 Turbo Tier 1",
    ),
    "gpt-3.5-turbo": ModelRateLimits(
        model_name="gpt-3.5-turbo",
        rpm=3500,
        tpm=200000,
        description="GPT-3.5 Turbo Tier 1",
    ),
    # Anthropic models (defaults)
    "claude-3-opus": ModelRateLimits(
        model_name="claude-3-opus",
        rpm=50,
        tpm=20000,
        description="Claude 3 Opus",
    ),
    "claude-3-sonnet": ModelRateLimits(
        model_name="claude-3-sonnet",
        rpm=50,
        tpm=40000,
        description="Claude 3 Sonnet",
    ),
    "claude-3-haiku": ModelRateLimits(
        model_name="claude-3-haiku",
        rpm=50,
        tpm=100000,
        description="Claude 3 Haiku",
    ),
    # Local models (no limits)
    "local": ModelRateLimits(
        model_name="local",
        rpm=0,  # 0 = unlimited
        tpm=0,
        description="Local LLM (no limits)",
    ),
}


@dataclass
class UsageRecord:
    """Record of API usage for a specific time period."""
    
    date: str  # ISO date string (YYYY-MM-DD)
    model: str
    requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "date": self.date,
            "model": self.model,
            "requests": self.requests,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> UsageRecord:
        """Create from dictionary."""
        return cls(
            date=data.get("date", ""),
            model=data.get("model", ""),
            requests=int(data.get("requests", 0)),
            input_tokens=int(data.get("input_tokens", 0)),
            output_tokens=int(data.get("output_tokens", 0)),
        )


@dataclass
class RateLimitStats:
    """Statistics about rate limit usage."""
    
    model: str
    rpm_used: int = 0
    rpm_limit: int = 60
    rpm_remaining: int = 60
    tpm_used: int = 0
    tpm_limit: int = 40000
    tpm_remaining: int = 40000
    rpd_used: int = 0
    rpd_limit: int = 0  # 0 = unlimited
    rpd_remaining: int = 0
    tpd_used: int = 0
    tpd_limit: int = 0
    tpd_remaining: int = 0
    next_reset_rpm: Optional[float] = None  # Seconds until RPM reset
    next_reset_rpd: Optional[str] = None  # Datetime of next RPD reset


@dataclass
class RateLimitCheckResult:
    """Result of a rate limit check."""
    
    allowed: bool
    wait_time: float = 0.0  # Seconds to wait if not allowed
    reason: str = ""
    limit_type: Optional[RateLimitType] = None
    current_usage: int = 0
    limit_value: int = 0
    
    def __bool__(self) -> bool:
        return self.allowed


@dataclass
class RateLimiterConfig:
    """Configuration for the rate limiter."""
    
    storage_path: str = "user/rate_limits.json"
    safety_margin: float = 0.1  # 10% safety margin
    auto_wait: bool = True  # Automatically wait when rate limited
    max_wait_time: float = 120.0  # Maximum seconds to wait
    max_concurrent: int = 3  # Maximum concurrent requests
    enable_daily_tracking: bool = True  # Track daily usage
    reset_hour_utc: int = 8  # Hour in UTC when daily limits reset (8 = midnight PT)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "storage_path": self.storage_path,
            "safety_margin": self.safety_margin,
            "auto_wait": self.auto_wait,
            "max_wait_time": self.max_wait_time,
            "max_concurrent": self.max_concurrent,
            "enable_daily_tracking": self.enable_daily_tracking,
            "reset_hour_utc": self.reset_hour_utc,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RateLimiterConfig:
        """Create from dictionary."""
        return cls(
            storage_path=data.get("storage_path", "user/rate_limits.json"),
            safety_margin=float(data.get("safety_margin", 0.1)),
            auto_wait=bool(data.get("auto_wait", True)),
            max_wait_time=float(data.get("max_wait_time", 120.0)),
            max_concurrent=int(data.get("max_concurrent", 3)),
            enable_daily_tracking=bool(data.get("enable_daily_tracking", True)),
            reset_hour_utc=int(data.get("reset_hour_utc", 8)),
        )


class RateLimiter:
    """Manages API rate limits using sliding window algorithm.
    
    Features:
    - Per-model rate limit tracking
    - Sliding window for RPM calculation
    - Daily usage tracking with persistence
    - Thread-safe operation
    - Automatic waiting when rate limited
    """
    
    def __init__(
        self,
        config: Optional[RateLimiterConfig] = None,
        model_limits: Optional[Dict[str, ModelRateLimits]] = None,
        base_path: Optional[Path] = None,
    ) -> None:
        """Initialize the rate limiter.
        
        Args:
            config: Rate limiter configuration.
            model_limits: Custom model rate limits (merged with defaults).
            base_path: Base path for storage file.
        """
        self.config = config or RateLimiterConfig()
        self._base_path = base_path or Path(".")
        
        # Merge custom model limits with defaults
        self._model_limits = DEFAULT_MODEL_LIMITS.copy()
        if model_limits:
            self._model_limits.update(model_limits)
        
        # Request tracking - sliding window per model
        # Each entry is (timestamp, token_count)
        self._request_windows: Dict[str, List[Tuple[float, int]]] = {}
        
        # Daily usage records per model
        self._daily_usage: Dict[str, UsageRecord] = {}
        
        # Concurrency tracking
        self._active_requests = 0
        self._concurrency_lock = threading.Lock()
        self._concurrency_condition = threading.Condition(self._concurrency_lock)
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Load persistent data
        self._load_usage_data()
    
    def _get_storage_path(self) -> Path:
        """Get the full path to the storage file."""
        return self._base_path / self.config.storage_path
    
    def _load_usage_data(self) -> None:
        """Load usage data from persistent storage."""
        storage_path = self._get_storage_path()
        
        if not storage_path.exists():
            return
        
        try:
            with open(storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Load daily usage
            for record_data in data.get("daily_usage", []):
                record = UsageRecord.from_dict(record_data)
                key = f"{record.date}_{record.model}"
                self._daily_usage[key] = record
            
            # Load custom model limits
            for limit_data in data.get("model_limits", []):
                limit = ModelRateLimits.from_dict(limit_data)
                self._model_limits[limit.model_name] = limit
                
        except (json.JSONDecodeError, IOError) as e:
            # If file is corrupted, start fresh
            pass
    
    def _save_usage_data(self) -> None:
        """Save usage data to persistent storage."""
        storage_path = self._get_storage_path()
        
        # Ensure directory exists
        storage_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Prepare data
        data = {
            "daily_usage": [r.to_dict() for r in self._daily_usage.values()],
            "model_limits": [
                m.to_dict() for name, m in self._model_limits.items()
                if name not in DEFAULT_MODEL_LIMITS
            ],
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }
        
        try:
            with open(storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except IOError:
            pass
    
    def _get_today_str(self) -> str:
        """Get today's date string in UTC."""
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    def _get_model_limits(self, model: str) -> ModelRateLimits:
        """Get rate limits for a model, with fallback to similar models."""
        # Exact match
        if model in self._model_limits:
            return self._model_limits[model]
        
        # Skip empty or very short model names for prefix matching
        if len(model) < 3:
            # Fall through to default fallback
            pass
        else:
            # Try to match by prefix (e.g., "gemini-2.0-flash-exp" -> "gemini-2.0-flash")
            for known_model, limits in self._model_limits.items():
                # Only match if there's meaningful overlap (at least 5 chars)
                if len(known_model) >= 5:
                    if model.startswith(known_model) or (len(model) >= 5 and known_model.startswith(model)):
                        return limits
        
        # Check for model family patterns
        model_lower = model.lower()
        
        if "gemini" in model_lower:
            if "flash-lite" in model_lower or "flash_lite" in model_lower:
                return self._model_limits.get("gemini-2.0-flash-lite", 
                    ModelRateLimits(model_name=model, rpm=30, tpm=1000000, rpd=1500))
            elif "flash" in model_lower:
                return self._model_limits.get("gemini-2.0-flash",
                    ModelRateLimits(model_name=model, rpm=15, tpm=1000000, rpd=1500))
            elif "pro" in model_lower:
                return self._model_limits.get("gemini-2.5-pro",
                    ModelRateLimits(model_name=model, rpm=5, tpm=250000, rpd=50))
        
        if "gpt-4" in model_lower:
            if "mini" in model_lower:
                return self._model_limits.get("gpt-4o-mini",
                    ModelRateLimits(model_name=model, rpm=500, tpm=200000))
            return self._model_limits.get("gpt-4o",
                ModelRateLimits(model_name=model, rpm=500, tpm=30000))
        
        if "gpt-3.5" in model_lower:
            return self._model_limits.get("gpt-3.5-turbo",
                ModelRateLimits(model_name=model, rpm=3500, tpm=200000))
        
        if "claude" in model_lower:
            if "opus" in model_lower:
                return self._model_limits.get("claude-3-opus",
                    ModelRateLimits(model_name=model, rpm=50, tpm=20000))
            elif "haiku" in model_lower:
                return self._model_limits.get("claude-3-haiku",
                    ModelRateLimits(model_name=model, rpm=50, tpm=100000))
            return self._model_limits.get("claude-3-sonnet",
                ModelRateLimits(model_name=model, rpm=50, tpm=40000))
        
        # Default fallback - conservative limits
        return ModelRateLimits(
            model_name=model,
            rpm=10,
            tpm=40000,
            description="Default fallback limits",
        )
    
    def _clean_old_requests(self, model: str, window_seconds: float = 60.0) -> None:
        """Remove requests older than the window from tracking."""
        cutoff = time.time() - window_seconds
        
        if model in self._request_windows:
            self._request_windows[model] = [
                (ts, tokens) for ts, tokens in self._request_windows[model]
                if ts > cutoff
            ]
    
    def _get_rpm_usage(self, model: str) -> Tuple[int, int]:
        """Get current RPM usage (requests and tokens) in the sliding window."""
        self._clean_old_requests(model)
        
        window = self._request_windows.get(model, [])
        request_count = len(window)
        token_count = sum(tokens for _, tokens in window)
        
        return request_count, token_count
    
    def _get_daily_usage(self, model: str) -> UsageRecord:
        """Get or create today's usage record for a model."""
        today = self._get_today_str()
        key = f"{today}_{model}"
        
        if key not in self._daily_usage:
            self._daily_usage[key] = UsageRecord(date=today, model=model)
        
        return self._daily_usage[key]
    
    def check_rate_limit(
        self,
        model: str,
        estimated_tokens: int = 0,
    ) -> RateLimitCheckResult:
        """Check if a request would exceed rate limits.
        
        Args:
            model: The model to check limits for.
            estimated_tokens: Estimated input tokens for the request.
            
        Returns:
            RateLimitCheckResult with allowed status and details.
        """
        with self._lock:
            limits = self._get_model_limits(model)
            
            # Check if rate limiting is disabled (local models)
            if limits.rpm == 0 and limits.rpd == 0:
                return RateLimitCheckResult(allowed=True)
            
            # Get current usage
            rpm_requests, tpm_tokens = self._get_rpm_usage(model)
            
            # Calculate effective limits with safety margin
            margin = self.config.safety_margin
            effective_rpm = int(limits.rpm * (1 - margin)) if limits.rpm > 0 else 0
            effective_tpm = int(limits.tpm * (1 - margin)) if limits.tpm > 0 else 0
            
            # Check RPM
            if limits.rpm > 0 and rpm_requests >= effective_rpm:
                # Calculate wait time based on oldest request
                window = self._request_windows.get(model, [])
                if window:
                    oldest_ts = min(ts for ts, _ in window)
                    wait_time = 60.0 - (time.time() - oldest_ts)
                    wait_time = max(0.1, wait_time)
                else:
                    wait_time = 1.0
                
                return RateLimitCheckResult(
                    allowed=False,
                    wait_time=wait_time,
                    reason=f"RPM limit reached ({rpm_requests}/{limits.rpm})",
                    limit_type=RateLimitType.RPM,
                    current_usage=rpm_requests,
                    limit_value=limits.rpm,
                )
            
            # Check TPM
            if limits.tpm > 0 and estimated_tokens > 0:
                if tpm_tokens + estimated_tokens > effective_tpm:
                    # Estimate wait time
                    window = self._request_windows.get(model, [])
                    if window:
                        oldest_ts = min(ts for ts, _ in window)
                        wait_time = 60.0 - (time.time() - oldest_ts)
                        wait_time = max(0.1, wait_time)
                    else:
                        wait_time = 1.0
                    
                    return RateLimitCheckResult(
                        allowed=False,
                        wait_time=wait_time,
                        reason=f"TPM limit would be exceeded ({tpm_tokens + estimated_tokens}/{limits.tpm})",
                        limit_type=RateLimitType.TPM,
                        current_usage=tpm_tokens,
                        limit_value=limits.tpm,
                    )
            
            # Check daily limits if enabled
            if self.config.enable_daily_tracking and limits.rpd > 0:
                daily = self._get_daily_usage(model)
                effective_rpd = int(limits.rpd * (1 - margin))
                
                if daily.requests >= effective_rpd:
                    # Calculate time until midnight PT (8 AM UTC)
                    now = datetime.now(timezone.utc)
                    reset_time = now.replace(
                        hour=self.config.reset_hour_utc,
                        minute=0,
                        second=0,
                        microsecond=0,
                    )
                    if now.hour >= self.config.reset_hour_utc:
                        reset_time += timedelta(days=1)
                    
                    wait_seconds = (reset_time - now).total_seconds()
                    
                    return RateLimitCheckResult(
                        allowed=False,
                        wait_time=wait_seconds,
                        reason=f"Daily limit reached ({daily.requests}/{limits.rpd}). Resets at {reset_time.isoformat()}",
                        limit_type=RateLimitType.RPD,
                        current_usage=daily.requests,
                        limit_value=limits.rpd,
                    )
            
            # Check TPD if enabled
            if self.config.enable_daily_tracking and limits.tpd > 0:
                daily = self._get_daily_usage(model)
                effective_tpd = int(limits.tpd * (1 - margin))
                
                if daily.input_tokens + estimated_tokens > effective_tpd:
                    now = datetime.now(timezone.utc)
                    reset_time = now.replace(
                        hour=self.config.reset_hour_utc,
                        minute=0,
                        second=0,
                        microsecond=0,
                    )
                    if now.hour >= self.config.reset_hour_utc:
                        reset_time += timedelta(days=1)
                    
                    wait_seconds = (reset_time - now).total_seconds()
                    
                    return RateLimitCheckResult(
                        allowed=False,
                        wait_time=wait_seconds,
                        reason=f"Daily token limit would be exceeded ({daily.input_tokens + estimated_tokens}/{limits.tpd})",
                        limit_type=RateLimitType.TPD,
                        current_usage=daily.input_tokens,
                        limit_value=limits.tpd,
                    )
            
            return RateLimitCheckResult(allowed=True)
    
    def record_request(
        self,
        model: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
    ) -> None:
        """Record a completed API request.
        
        Args:
            model: The model used.
            input_tokens: Number of input tokens used.
            output_tokens: Number of output tokens generated.
        """
        with self._lock:
            # Record in sliding window
            if model not in self._request_windows:
                self._request_windows[model] = []
            self._request_windows[model].append((time.time(), input_tokens))
            
            # Record daily usage
            if self.config.enable_daily_tracking:
                daily = self._get_daily_usage(model)
                daily.requests += 1
                daily.input_tokens += input_tokens
                daily.output_tokens += output_tokens
                
                # Save periodically (every 10 requests)
                if daily.requests % 10 == 0:
                    self._save_usage_data()
    
    def wait_if_needed(
        self,
        model: str,
        estimated_tokens: int = 0,
        callback: Optional[Callable[[float, float], None]] = None,
    ) -> RateLimitCheckResult:
        """Check rate limit and wait if necessary.
        
        Args:
            model: The model to check.
            estimated_tokens: Estimated input tokens.
            callback: Optional callback to call while waiting (for progress updates).
            
        Returns:
            RateLimitCheckResult after waiting (if waited).
        """
        result = self.check_rate_limit(model, estimated_tokens)
        
        if result.allowed:
            return result
        
        if not self.config.auto_wait:
            return result
        
        # Don't wait longer than max_wait_time
        wait_time = min(result.wait_time, self.config.max_wait_time)
        
        if wait_time > self.config.max_wait_time:
            result.reason += f" (wait time {result.wait_time:.1f}s exceeds max {self.config.max_wait_time}s)"
            return result
        
        # Wait in small increments to allow cancellation
        waited = 0.0
        while waited < wait_time:
            sleep_time = min(1.0, wait_time - waited)
            time.sleep(sleep_time)
            waited += sleep_time
            
            if callback:
                callback(waited, wait_time)
        
        # Re-check after waiting
        return self.check_rate_limit(model, estimated_tokens)
    
    def acquire_request_slot(self, timeout: float = 60.0) -> bool:
        """Acquire a slot for a concurrent request.
        
        Args:
            timeout: Maximum time to wait for a slot.
            
        Returns:
            True if slot acquired, False if timeout.
        """
        with self._concurrency_condition:
            end_time = time.time() + timeout
            
            while self._active_requests >= self.config.max_concurrent:
                remaining = end_time - time.time()
                if remaining <= 0:
                    return False
                self._concurrency_condition.wait(timeout=remaining)
            
            self._active_requests += 1
            return True
    
    def release_request_slot(self) -> None:
        """Release a concurrent request slot."""
        with self._concurrency_condition:
            self._active_requests = max(0, self._active_requests - 1)
            self._concurrency_condition.notify()
    
    def get_stats(self, model: str) -> RateLimitStats:
        """Get current rate limit statistics for a model.
        
        Args:
            model: The model to get stats for.
            
        Returns:
            RateLimitStats with current usage and limits.
        """
        with self._lock:
            limits = self._get_model_limits(model)
            rpm_requests, tpm_tokens = self._get_rpm_usage(model)
            
            stats = RateLimitStats(
                model=model,
                rpm_used=rpm_requests,
                rpm_limit=limits.rpm,
                rpm_remaining=max(0, limits.rpm - rpm_requests) if limits.rpm > 0 else 0,
                tpm_used=tpm_tokens,
                tpm_limit=limits.tpm,
                tpm_remaining=max(0, limits.tpm - tpm_tokens) if limits.tpm > 0 else 0,
            )
            
            # Calculate next RPM reset
            window = self._request_windows.get(model, [])
            if window:
                oldest_ts = min(ts for ts, _ in window)
                stats.next_reset_rpm = max(0, 60.0 - (time.time() - oldest_ts))
            
            # Daily stats
            if self.config.enable_daily_tracking:
                daily = self._get_daily_usage(model)
                stats.rpd_used = daily.requests
                stats.rpd_limit = limits.rpd
                stats.rpd_remaining = max(0, limits.rpd - daily.requests) if limits.rpd > 0 else 0
                stats.tpd_used = daily.input_tokens
                stats.tpd_limit = limits.tpd
                stats.tpd_remaining = max(0, limits.tpd - daily.input_tokens) if limits.tpd > 0 else 0
                
                # Next daily reset
                now = datetime.now(timezone.utc)
                reset_time = now.replace(
                    hour=self.config.reset_hour_utc,
                    minute=0,
                    second=0,
                    microsecond=0,
                )
                if now.hour >= self.config.reset_hour_utc:
                    reset_time += timedelta(days=1)
                stats.next_reset_rpd = reset_time.isoformat()
            
            return stats
    
    def set_model_limits(
        self,
        model: str,
        rpm: Optional[int] = None,
        tpm: Optional[int] = None,
        rpd: Optional[int] = None,
        tpd: Optional[int] = None,
    ) -> None:
        """Set custom rate limits for a model.
        
        Args:
            model: The model name.
            rpm: Requests per minute (None to keep existing).
            tpm: Tokens per minute (None to keep existing).
            rpd: Requests per day (None to keep existing).
            tpd: Tokens per day (None to keep existing).
        """
        with self._lock:
            if model in self._model_limits:
                limits = self._model_limits[model]
            else:
                limits = ModelRateLimits(model_name=model)
            
            if rpm is not None:
                limits.rpm = rpm
            if tpm is not None:
                limits.tpm = tpm
            if rpd is not None:
                limits.rpd = rpd
            if tpd is not None:
                limits.tpd = tpd
            
            self._model_limits[model] = limits
            self._save_usage_data()
    
    def reset_daily_usage(self, model: Optional[str] = None) -> None:
        """Reset daily usage counters.
        
        Args:
            model: Specific model to reset, or None for all models.
        """
        with self._lock:
            today = self._get_today_str()
            
            if model:
                key = f"{today}_{model}"
                if key in self._daily_usage:
                    del self._daily_usage[key]
            else:
                # Reset all of today's records
                keys_to_delete = [k for k in self._daily_usage if k.startswith(today)]
                for key in keys_to_delete:
                    del self._daily_usage[key]
            
            self._save_usage_data()
    
    def estimate_capacity(
        self,
        model: str,
        lines: int,
        avg_tokens_per_line: int = 50,
        chunk_size: int = 50,
    ) -> Dict[str, Any]:
        """Estimate if there's capacity to translate a batch.
        
        Args:
            model: The model to use.
            lines: Number of lines to translate.
            avg_tokens_per_line: Average tokens per line.
            chunk_size: Lines per API request.
            
        Returns:
            Dictionary with capacity analysis.
        """
        with self._lock:
            limits = self._get_model_limits(model)
            
            # Calculate requests needed
            chunks_needed = math.ceil(lines / chunk_size)
            tokens_needed = lines * avg_tokens_per_line
            
            # Get current usage
            rpm_used, tpm_used = self._get_rpm_usage(model)
            
            issues: List[str] = []
            recommendations: List[str] = []
            can_complete_now = True
            estimated_minutes: Optional[float] = None
            lines_possible_today: Optional[int] = None
            lines_remaining: Optional[int] = None
            
            # Check RPM (can complete in reasonable time?)
            if limits.rpm > 0:
                minutes_needed = chunks_needed / (limits.rpm * (1 - self.config.safety_margin))
                estimated_minutes = minutes_needed
                
                if minutes_needed > 60:
                    issues.append(
                        f"Would take ~{minutes_needed:.0f} minutes at {limits.rpm} RPM"
                    )
            
            # Check daily limit
            if limits.rpd > 0:
                daily = self._get_daily_usage(model)
                remaining_requests = limits.rpd - daily.requests
                
                if chunks_needed > remaining_requests:
                    can_complete_now = False
                    issues.append(
                        f"Daily limit: {remaining_requests}/{limits.rpd} requests remaining, need {chunks_needed}"
                    )
                    
                    # How many lines can we do today?
                    lines_today = remaining_requests * chunk_size
                    lines_possible_today = lines_today
                    lines_remaining = lines - lines_today
                    recommendations.append(
                        f"Can translate {lines_today} lines today, {lines - lines_today} tomorrow"
                    )
            
            # Check daily token limit
            if limits.tpd > 0:
                daily = self._get_daily_usage(model)
                remaining_tokens = limits.tpd - daily.input_tokens
                
                if tokens_needed > remaining_tokens:
                    can_complete_now = False
                    issues.append(
                        f"Daily token limit: {remaining_tokens:,}/{limits.tpd:,} tokens remaining, need ~{tokens_needed:,}"
                    )
            
            result: Dict[str, Any] = {
                "model": model,
                "lines": lines,
                "chunks_needed": chunks_needed,
                "tokens_needed": tokens_needed,
                "can_complete_now": can_complete_now,
                "issues": issues,
                "recommendations": recommendations,
            }
            
            if estimated_minutes is not None:
                result["estimated_minutes"] = estimated_minutes
            if lines_possible_today is not None:
                result["lines_possible_today"] = lines_possible_today
            if lines_remaining is not None:
                result["lines_remaining"] = lines_remaining
            
            return result
    
    def save(self) -> None:
        """Force save usage data to persistent storage."""
        with self._lock:
            self._save_usage_data()
    
    def close(self) -> None:
        """Close the rate limiter and save data."""
        self.save()


# Factory functions

def create_rate_limiter(
    storage_path: Optional[str] = None,
    safety_margin: float = 0.1,
    auto_wait: bool = True,
    max_concurrent: int = 3,
    base_path: Optional[Path] = None,
) -> RateLimiter:
    """Create a rate limiter with common settings.
    
    Args:
        storage_path: Path for persistent storage.
        safety_margin: Safety margin percentage (0.0-1.0).
        auto_wait: Whether to automatically wait when rate limited.
        max_concurrent: Maximum concurrent requests.
        base_path: Base path for storage.
        
    Returns:
        Configured RateLimiter instance.
    """
    config = RateLimiterConfig(
        storage_path=storage_path or "user/rate_limits.json",
        safety_margin=safety_margin,
        auto_wait=auto_wait,
        max_concurrent=max_concurrent,
    )
    
    return RateLimiter(config=config, base_path=base_path)


def get_model_limits(model: str) -> ModelRateLimits:
    """Get the default rate limits for a model.
    
    Args:
        model: The model name.
        
    Returns:
        ModelRateLimits for the model.
    """
    # Create a temporary limiter to use its model resolution logic
    limiter = RateLimiter()
    return limiter._get_model_limits(model)


def list_known_models() -> List[str]:
    """List all models with known rate limits.
    
    Returns:
        List of model names.
    """
    return list(DEFAULT_MODEL_LIMITS.keys())

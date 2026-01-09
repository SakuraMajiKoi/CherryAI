"""Request caching system for translation API responses.

This module provides caching of translated lines to avoid resending identical
requests, saving API costs and reducing latency.

Features:
- Cache translated lines by hash of source content
- Multiple cache matching modes (strict, model_only, any)
- TTL-based expiration (configurable, default 30 days)
- LRU eviction when cache size limit reached
- Thread-safe access for concurrent operations

Example:
    >>> cache = RequestCache(cache_mode=CacheMode.MODEL_ONLY)
    >>> result = cache.get(["line1", "line2"], model="gpt-4o")
    >>> if result is None:
    ...     translations = api_translate(lines)
    ...     cache.store(lines, translations, model="gpt-4o")
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import hashlib
import json
import logging
import threading
import time


class CacheMode(Enum):
    """Cache matching modes for translation lookups."""
    
    STRICT = "strict"       # All settings must match (model, temp, prompt)
    MODEL_ONLY = "model_only"  # Only model name must match
    ANY = "any"             # Use cached response regardless of settings


@dataclass
class CacheConfig:
    """Configuration for request cache.
    
    Attributes:
        enabled: Whether caching is enabled.
        mode: Cache matching mode.
        cache_dir: Directory for cache files.
        ttl_days: Time-to-live for cache entries in days.
        max_entries: Maximum number of cache entries before LRU eviction.
        include_prompt_hash: Include system prompt in cache key (for strict mode).
    """
    enabled: bool = True
    mode: CacheMode = CacheMode.MODEL_ONLY
    cache_dir: str = "cache"
    ttl_days: int = 30
    max_entries: int = 10000
    include_prompt_hash: bool = True


@dataclass
class CacheEntry:
    """A single cache entry.
    
    Attributes:
        source_lines: Original source lines.
        translated_lines: Translated output.
        model: Model used for translation.
        temperature: Temperature setting used.
        prompt_hash: Hash of system prompt (optional).
        timestamp: When entry was created (ISO format).
        access_count: Number of times entry was accessed.
        last_accessed: Last access timestamp (ISO format).
    """
    source_lines: List[str]
    translated_lines: List[str]
    model: str
    temperature: float
    prompt_hash: Optional[str] = None
    timestamp: str = ""
    access_count: int = 0
    last_accessed: str = ""
    
    def __post_init__(self):
        now = datetime.now(timezone.utc).isoformat()
        if not self.timestamp:
            self.timestamp = now
        if not self.last_accessed:
            self.last_accessed = now
    
    def touch(self) -> None:
        """Update access count and timestamp."""
        self.access_count += 1
        self.last_accessed = datetime.now(timezone.utc).isoformat()
    
    def is_expired(self, ttl_days: int) -> bool:
        """Check if entry has expired based on TTL."""
        try:
            created = datetime.fromisoformat(self.timestamp)
            # Handle both timezone-aware and naive timestamps
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            expiry = created + timedelta(days=ttl_days)
            return datetime.now(timezone.utc) > expiry
        except (ValueError, TypeError):
            return True  # Invalid timestamp = expired
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CacheEntry":
        """Create from dictionary."""
        return cls(**data)


@dataclass 
class CacheStats:
    """Statistics about cache usage.
    
    Attributes:
        hits: Number of cache hits.
        misses: Number of cache misses.
        stores: Number of entries stored.
        evictions: Number of entries evicted.
        expired: Number of expired entries found.
    """
    hits: int = 0
    misses: int = 0
    stores: int = 0
    evictions: int = 0
    expired: int = 0
    
    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hits + self.misses
        if total == 0:
            return 0.0
        return self.hits / total
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "stores": self.stores,
            "evictions": self.evictions,
            "expired": self.expired,
            "hit_rate": round(self.hit_rate, 4),
        }


class RequestCache:
    """Thread-safe cache for translation API responses.
    
    Stores translated lines indexed by content hash, with configurable
    matching modes and automatic TTL-based expiration.
    
    Example:
        >>> cache = RequestCache()
        >>> cache.store(["こんにちは"], ["Hello"], model="gpt-4o", temperature=0.3)
        >>> result = cache.get(["こんにちは"], model="gpt-4o")
        >>> print(result)  # ["Hello"]
    """
    
    CACHE_FILENAME = "request_cache.json"
    
    def __init__(self, config: Optional[CacheConfig] = None) -> None:
        """Initialize the cache.
        
        Args:
            config: Cache configuration. Uses defaults if None.
        """
        self.config = config or CacheConfig()
        self.logger = logging.getLogger("cherryai.cache")
        self._lock = threading.RLock()
        self._cache: Dict[str, Dict[str, CacheEntry]] = {}  # model -> hash -> entry
        self._stats = CacheStats()
        
        # Load cache from disk if exists
        if self.config.enabled:
            self._load_cache()
    
    def _get_cache_path(self) -> Path:
        """Get the cache file path."""
        cache_dir = Path(self.config.cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir / self.CACHE_FILENAME
    
    def _hash_content(self, lines: List[str]) -> str:
        """Create hash from source lines.
        
        Args:
            lines: Source lines to hash.
            
        Returns:
            SHA256 hash of the content.
        """
        content = "\n".join(lines)
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
    
    def _hash_prompt(self, prompt: Optional[str]) -> Optional[str]:
        """Create hash from system prompt.
        
        Args:
            prompt: System prompt to hash.
            
        Returns:
            SHA256 hash of prompt, or None if no prompt.
        """
        if not prompt:
            return None
        return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:8]
    
    def _get_cache_key(
        self,
        lines: List[str],
        model: str,
        temperature: float = 0.3,
        prompt: Optional[str] = None,
    ) -> Tuple[str, str]:
        """Generate cache key based on mode.
        
        Args:
            lines: Source lines.
            model: Model name.
            temperature: Temperature setting.
            prompt: System prompt.
            
        Returns:
            Tuple of (model_key, content_hash) for indexing.
        """
        content_hash = self._hash_content(lines)
        
        if self.config.mode == CacheMode.STRICT:
            # Include everything in the key
            prompt_hash = self._hash_prompt(prompt) if self.config.include_prompt_hash else None
            key_parts = [content_hash, f"t{temperature}"]
            if prompt_hash:
                key_parts.append(f"p{prompt_hash}")
            content_hash = "_".join(key_parts)
        
        elif self.config.mode == CacheMode.MODEL_ONLY:
            # Just use content hash (model is the dict key)
            pass
        
        elif self.config.mode == CacheMode.ANY:
            # Use generic model key
            model = "__any__"
        
        return model, content_hash
    
    def get(
        self,
        lines: List[str],
        model: str = "",
        temperature: float = 0.3,
        prompt: Optional[str] = None,
    ) -> Optional[List[str]]:
        """Get cached translations for source lines.
        
        Args:
            lines: Source lines to look up.
            model: Model name (used for strict/model_only modes).
            temperature: Temperature setting (used for strict mode).
            prompt: System prompt (used for strict mode).
            
        Returns:
            Cached translated lines, or None if not found.
        """
        if not self.config.enabled:
            return None
        
        model_key, content_hash = self._get_cache_key(lines, model, temperature, prompt)
        
        with self._lock:
            # Check if model exists in cache
            if model_key not in self._cache:
                # In ANY mode, try all models
                if self.config.mode == CacheMode.ANY:
                    for m_key, entries in self._cache.items():
                        if content_hash in entries:
                            entry = entries[content_hash]
                            if not entry.is_expired(self.config.ttl_days):
                                entry.touch()
                                self._stats.hits += 1
                                self.logger.debug(f"Cache hit (any mode): {content_hash[:8]}")
                                return entry.translated_lines
                            else:
                                self._stats.expired += 1
                
                self._stats.misses += 1
                return None
            
            # Look up entry
            entries = self._cache[model_key]
            if content_hash not in entries:
                self._stats.misses += 1
                return None
            
            entry = entries[content_hash]
            
            # Check expiration
            if entry.is_expired(self.config.ttl_days):
                self.logger.debug(f"Cache entry expired: {content_hash[:8]}")
                del entries[content_hash]
                self._stats.expired += 1
                self._stats.misses += 1
                return None
            
            # Update access and return
            entry.touch()
            self._stats.hits += 1
            self.logger.debug(f"Cache hit: {content_hash[:8]} (model: {model_key})")
            return entry.translated_lines
    
    def store(
        self,
        lines: List[str],
        translations: List[str],
        model: str = "",
        temperature: float = 0.3,
        prompt: Optional[str] = None,
    ) -> bool:
        """Store translations in cache.
        
        Args:
            lines: Source lines.
            translations: Translated lines.
            model: Model used.
            temperature: Temperature setting.
            prompt: System prompt used.
            
        Returns:
            True if stored successfully.
        """
        if not self.config.enabled:
            return False
        
        if len(lines) != len(translations):
            self.logger.warning("Line count mismatch, not caching")
            return False
        
        model_key, content_hash = self._get_cache_key(lines, model, temperature, prompt)
        
        with self._lock:
            # Ensure model key exists
            if model_key not in self._cache:
                self._cache[model_key] = {}
            
            # Create entry
            entry = CacheEntry(
                source_lines=lines,
                translated_lines=translations,
                model=model,
                temperature=temperature,
                prompt_hash=self._hash_prompt(prompt) if prompt else None,
            )
            
            # Store
            self._cache[model_key][content_hash] = entry
            self._stats.stores += 1
            self.logger.debug(f"Cache store: {content_hash[:8]} (model: {model_key})")
            
            # Check if eviction needed
            self._maybe_evict()
            
            return True
    
    def _maybe_evict(self) -> None:
        """Evict oldest entries if over limit (LRU)."""
        total_entries = sum(len(entries) for entries in self._cache.values())
        
        if total_entries <= self.config.max_entries:
            return
        
        # Collect all entries with keys
        all_entries: List[Tuple[str, str, CacheEntry]] = []
        for model_key, entries in self._cache.items():
            for hash_key, entry in entries.items():
                all_entries.append((model_key, hash_key, entry))
        
        # Sort by last accessed (oldest first)
        all_entries.sort(key=lambda x: x[2].last_accessed)
        
        # Remove oldest until under limit
        to_remove = total_entries - self.config.max_entries
        for model_key, hash_key, entry in all_entries[:to_remove]:
            del self._cache[model_key][hash_key]
            self._stats.evictions += 1
            
            # Clean up empty model dicts
            if not self._cache[model_key]:
                del self._cache[model_key]
        
        self.logger.debug(f"Evicted {to_remove} cache entries")
    
    def clear(self) -> int:
        """Clear all cache entries.
        
        Returns:
            Number of entries cleared.
        """
        with self._lock:
            count = sum(len(entries) for entries in self._cache.values())
            self._cache.clear()
            self.logger.info(f"Cleared {count} cache entries")
            return count
    
    def get_stats(self) -> CacheStats:
        """Get cache statistics.
        
        Returns:
            CacheStats with usage information.
        """
        return self._stats
    
    def get_entry_count(self) -> int:
        """Get total number of cache entries.
        
        Returns:
            Number of entries in cache.
        """
        with self._lock:
            return sum(len(entries) for entries in self._cache.values())
    
    def save(self) -> bool:
        """Save cache to disk.
        
        Returns:
            True if saved successfully.
        """
        if not self.config.enabled:
            return False
        
        try:
            cache_path = self._get_cache_path()
            
            # Convert to serializable format
            entries_data: Dict[str, Dict[str, Dict[str, Any]]] = {}
            
            with self._lock:
                for model_key, entries in self._cache.items():
                    entries_data[model_key] = {
                        hash_key: entry.to_dict()
                        for hash_key, entry in entries.items()
                    }
            
            data: Dict[str, Any] = {
                "version": 1,
                "mode": self.config.mode.value,
                "entries": entries_data,
                "stats": self._stats.to_dict(),
            }
            
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            self.logger.debug(f"Saved cache to {cache_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save cache: {e}")
            return False
    
    def _load_cache(self) -> bool:
        """Load cache from disk.
        
        Returns:
            True if loaded successfully.
        """
        cache_path = self._get_cache_path()
        
        if not cache_path.exists():
            return False
        
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Validate version
            version = data.get("version", 0)
            if version != 1:
                self.logger.warning(f"Unknown cache version {version}, starting fresh")
                return False
            
            # Load entries
            with self._lock:
                for model_key, entries in data.get("entries", {}).items():
                    self._cache[model_key] = {
                        hash_key: CacheEntry.from_dict(entry_data)
                        for hash_key, entry_data in entries.items()
                    }
            
            # Load stats
            stats_data = data.get("stats", {})
            self._stats = CacheStats(
                hits=stats_data.get("hits", 0),
                misses=stats_data.get("misses", 0),
                stores=stats_data.get("stores", 0),
                evictions=stats_data.get("evictions", 0),
                expired=stats_data.get("expired", 0),
            )
            
            self.logger.debug(f"Loaded {self.get_entry_count()} cache entries")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to load cache: {e}")
            return False
    
    def cleanup_expired(self) -> int:
        """Remove all expired entries.
        
        Returns:
            Number of entries removed.
        """
        removed = 0
        
        with self._lock:
            for model_key in list(self._cache.keys()):
                entries = self._cache[model_key]
                expired_keys = [
                    k for k, e in entries.items()
                    if e.is_expired(self.config.ttl_days)
                ]
                for key in expired_keys:
                    del entries[key]
                    removed += 1
                
                # Clean up empty model dicts
                if not entries:
                    del self._cache[model_key]
        
        if removed:
            self.logger.info(f"Cleaned up {removed} expired cache entries")
            self._stats.expired += removed
        
        return removed


def create_request_cache(
    enabled: bool = True,
    mode: str = "model_only",
    cache_dir: str = "cache",
    ttl_days: int = 30,
    max_entries: int = 10000,
) -> RequestCache:
    """Factory function to create a request cache.
    
    Args:
        enabled: Whether caching is enabled.
        mode: Cache mode ("strict", "model_only", "any").
        cache_dir: Directory for cache files.
        ttl_days: Time-to-live for entries.
        max_entries: Maximum entries before eviction.
        
    Returns:
        Configured RequestCache instance.
    """
    mode_map = {
        "strict": CacheMode.STRICT,
        "model_only": CacheMode.MODEL_ONLY,
        "model": CacheMode.MODEL_ONLY,  # Alias
        "any": CacheMode.ANY,
    }
    
    cache_mode = mode_map.get(mode.lower(), CacheMode.MODEL_ONLY)
    
    config = CacheConfig(
        enabled=enabled,
        mode=cache_mode,
        cache_dir=cache_dir,
        ttl_days=ttl_days,
        max_entries=max_entries,
    )
    
    return RequestCache(config)


def parse_cache_mode_arg(arg: str) -> CacheMode:
    """Parse cache mode from CLI argument.
    
    Args:
        arg: Mode name from command line.
        
    Returns:
        CacheMode enum value.
        
    Raises:
        ValueError: If mode name is not recognized.
    """
    arg_lower = arg.lower().strip()
    mode_map = {
        "strict": CacheMode.STRICT,
        "model_only": CacheMode.MODEL_ONLY,
        "model": CacheMode.MODEL_ONLY,
        "any": CacheMode.ANY,
    }
    
    if arg_lower in mode_map:
        return mode_map[arg_lower]
    
    valid = ", ".join(sorted(set(mode_map.keys())))
    raise ValueError(f"Unknown cache mode '{arg}'. Valid options: {valid}")


def list_cache_modes() -> List[str]:
    """List available cache mode names.
    
    Returns:
        List of mode names.
    """
    return [m.value for m in CacheMode]


def get_cache_mode_description(mode: CacheMode) -> str:
    """Get description of a cache mode.
    
    Args:
        mode: The mode to describe.
        
    Returns:
        Human-readable description.
    """
    descriptions = {
        CacheMode.STRICT: (
            "Strict matching: model, temperature, and prompt hash must all match. "
            "Use when exact reproducibility is required."
        ),
        CacheMode.MODEL_ONLY: (
            "Model-only matching: only model name must match. "
            "Different temperatures or prompts will hit cache. Default mode."
        ),
        CacheMode.ANY: (
            "Any matching: use cached response regardless of settings. "
            "Maximum cache hits but may mix results from different models."
        ),
    }
    return descriptions.get(mode, "Unknown mode")

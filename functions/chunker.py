"""Token-based and line-based chunking for translation batches.

Provides flexible chunking strategies: by line count, by token count,
or hybrid mode (whichever limit is reached first).

Uses tiktoken for accurate token counting with OpenAI models.
Falls back to character-based estimation if tiktoken unavailable.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, List, Optional, Tuple

from .config import MODEL_ENCODINGS, DEFAULT_ENCODING, get_encoding_for_model


# Try to import tiktoken; gracefully fall back if not available
try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    tiktoken = None  # type: ignore
    TIKTOKEN_AVAILABLE = False


class ChunkMode(Enum):
    """Chunking strategy mode."""
    LINES = "lines"      # Chunk by line count only
    TOKENS = "tokens"    # Chunk by token count only
    HYBRID = "hybrid"    # Use whichever limit is reached first


# Backward compatibility: These are now imported from config.py
# MODEL_ENCODINGS and DEFAULT_ENCODING are available via the import above


@dataclass
class ChunkerConfig:
    """Configuration for the Chunker.
    
    Attributes:
        mode: Chunking strategy (lines, tokens, or hybrid).
        max_lines: Maximum lines per chunk (used in lines/hybrid mode).
        max_tokens: Maximum tokens per chunk (used in tokens/hybrid mode).
        model: Model name for token counting (affects encoding selection).
        reserve_tokens: Tokens to reserve for output (reduces effective max_tokens).
    """
    mode: ChunkMode = ChunkMode.LINES
    max_lines: int = 50
    max_tokens: int = 4000
    model: str = "gpt-4o"
    reserve_tokens: int = 0  # Reserve space for output


class Chunker:
    """Chunks text into batches based on line count, token count, or hybrid.
    
    Example usage:
        chunker = Chunker(ChunkerConfig(mode=ChunkMode.HYBRID, max_lines=50, max_tokens=4000))
        chunks = chunker.chunk_lines(["line1", "line2", ...])
    """

    def __init__(self, config: Optional[ChunkerConfig] = None) -> None:
        """Initialize chunker with configuration.
        
        Args:
            config: Chunker configuration. Uses defaults if not provided.
        """
        self.config = config or ChunkerConfig()
        self.logger = logging.getLogger(__name__)
        self._encoder: Optional[object] = None
        self._token_cache: dict[str, int] = {}  # Cache line -> token count
        
        # Initialize encoder if tiktoken available and needed
        if self.config.mode in (ChunkMode.TOKENS, ChunkMode.HYBRID):
            self._init_encoder()

    def _init_encoder(self) -> None:
        """Initialize tiktoken encoder for the configured model."""
        if not TIKTOKEN_AVAILABLE:
            self.logger.warning(
                "tiktoken not installed - using character-based token estimation. "
                "Install with: pip install tiktoken"
            )
            return
        
        try:
            # Try model-specific encoding first
            if self.config.model in MODEL_ENCODINGS:
                encoding_name = MODEL_ENCODINGS[self.config.model]
                self._encoder = tiktoken.get_encoding(encoding_name)
            else:
                # Try tiktoken's built-in model lookup
                try:
                    self._encoder = tiktoken.encoding_for_model(self.config.model)
                except KeyError:
                    # Fall back to default encoding
                    self._encoder = tiktoken.get_encoding(DEFAULT_ENCODING)
                    self.logger.debug(
                        f"No specific encoding for model '{self.config.model}', "
                        f"using {DEFAULT_ENCODING}"
                    )
        except Exception as e:
            self.logger.warning(f"Failed to initialize tiktoken encoder: {e}")
            self._encoder = None

    def count_tokens(self, text: str) -> int:
        """Count tokens in text using tiktoken or estimation.
        
        Args:
            text: Text to count tokens for.
            
        Returns:
            Token count (exact if tiktoken available, estimated otherwise).
        """
        # Check cache first
        if text in self._token_cache:
            return self._token_cache[text]
        
        if self._encoder is not None:
            # Use tiktoken for accurate count
            count = len(self._encoder.encode(text))  # type: ignore
        else:
            # Fallback: estimate ~4 characters per token (rough average)
            # This is conservative for English, may undercount for Japanese
            count = max(1, len(text) // 4)
        
        # Cache result
        self._token_cache[text] = count
        return count

    def count_tokens_batch(self, lines: List[str]) -> int:
        """Count total tokens for a batch of lines.
        
        Args:
            lines: List of text lines.
            
        Returns:
            Total token count for all lines.
        """
        return sum(self.count_tokens(line) for line in lines)

    def chunk_lines(self, lines: List[str]) -> List[List[str]]:
        """Split lines into chunks based on configured mode.
        
        Args:
            lines: List of lines to chunk.
            
        Returns:
            List of chunks, where each chunk is a list of lines.
        """
        if not lines:
            return []
        
        if self.config.mode == ChunkMode.LINES:
            return self._chunk_by_lines(lines)
        elif self.config.mode == ChunkMode.TOKENS:
            return self._chunk_by_tokens(lines)
        else:  # HYBRID
            return self._chunk_hybrid(lines)

    def _chunk_by_lines(self, lines: List[str]) -> List[List[str]]:
        """Chunk by line count only.
        
        Args:
            lines: Lines to chunk.
            
        Returns:
            List of chunks.
        """
        chunks = []
        for i in range(0, len(lines), self.config.max_lines):
            chunks.append(lines[i : i + self.config.max_lines])
        return chunks

    def _chunk_by_tokens(self, lines: List[str]) -> List[List[str]]:
        """Chunk by token count only.
        
        Args:
            lines: Lines to chunk.
            
        Returns:
            List of chunks.
        """
        effective_max = self.config.max_tokens - self.config.reserve_tokens
        if effective_max < 100:
            effective_max = 100  # Minimum to avoid edge cases
        
        chunks: List[List[str]] = []
        current_chunk: List[str] = []
        current_tokens = 0
        
        for line in lines:
            line_tokens = self.count_tokens(line)
            
            # If single line exceeds max, it gets its own chunk
            if line_tokens >= effective_max:
                if current_chunk:
                    chunks.append(current_chunk)
                    current_chunk = []
                    current_tokens = 0
                chunks.append([line])
                continue
            
            # Check if adding this line exceeds token limit
            if current_tokens + line_tokens > effective_max:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = [line]
                current_tokens = line_tokens
            else:
                current_chunk.append(line)
                current_tokens += line_tokens
        
        # Don't forget the last chunk
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks

    def _chunk_hybrid(self, lines: List[str]) -> List[List[str]]:
        """Chunk by whichever limit is reached first (lines or tokens).
        
        Args:
            lines: Lines to chunk.
            
        Returns:
            List of chunks.
        """
        effective_max_tokens = self.config.max_tokens - self.config.reserve_tokens
        if effective_max_tokens < 100:
            effective_max_tokens = 100
        
        chunks: List[List[str]] = []
        current_chunk: List[str] = []
        current_tokens = 0
        
        for line in lines:
            line_tokens = self.count_tokens(line)
            
            # Check both limits
            would_exceed_lines = len(current_chunk) >= self.config.max_lines
            would_exceed_tokens = current_tokens + line_tokens > effective_max_tokens
            
            # If single line exceeds token max, it gets its own chunk
            if line_tokens >= effective_max_tokens:
                if current_chunk:
                    chunks.append(current_chunk)
                    current_chunk = []
                    current_tokens = 0
                chunks.append([line])
                continue
            
            # Check if we need to start a new chunk
            if current_chunk and (would_exceed_lines or would_exceed_tokens):
                chunks.append(current_chunk)
                current_chunk = []
                current_tokens = 0
            
            current_chunk.append(line)
            current_tokens += line_tokens
        
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks

    def estimate_chunks(self, lines: List[str]) -> int:
        """Estimate how many chunks the lines will produce.
        
        Args:
            lines: Lines to estimate chunks for.
            
        Returns:
            Estimated number of chunks.
        """
        if not lines:
            return 0
        
        # For accuracy, actually chunk and count
        return len(self.chunk_lines(lines))

    def get_chunk_info(self, chunk: List[str]) -> dict:
        """Get information about a chunk.
        
        Args:
            chunk: List of lines in the chunk.
            
        Returns:
            Dictionary with line_count and token_count.
        """
        return {
            "line_count": len(chunk),
            "token_count": self.count_tokens_batch(chunk),
        }

    def clear_cache(self) -> None:
        """Clear the token count cache."""
        self._token_cache.clear()


def create_chunker(
    mode: str = "lines",
    max_lines: int = 50,
    max_tokens: int = 4000,
    model: str = "gpt-4o",
    reserve_tokens: int = 0,
) -> Chunker:
    """Factory function to create a Chunker with simplified arguments.
    
    Args:
        mode: "lines", "tokens", or "hybrid".
        max_lines: Maximum lines per chunk.
        max_tokens: Maximum tokens per chunk.
        model: Model name for encoding selection.
        reserve_tokens: Tokens to reserve for output.
        
    Returns:
        Configured Chunker instance.
        
    Raises:
        ValueError: If mode is invalid.
    """
    try:
        chunk_mode = ChunkMode(mode.lower())
    except ValueError:
        raise ValueError(f"Invalid chunk mode '{mode}'. Use 'lines', 'tokens', or 'hybrid'.")
    
    config = ChunkerConfig(
        mode=chunk_mode,
        max_lines=max_lines,
        max_tokens=max_tokens,
        model=model,
        reserve_tokens=reserve_tokens,
    )
    return Chunker(config)


def is_tiktoken_available() -> bool:
    """Check if tiktoken is available for accurate token counting.
    
    Returns:
        True if tiktoken is installed, False otherwise.
    """
    return TIKTOKEN_AVAILABLE

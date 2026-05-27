"""Token-based and line-based chunking for translation batches.

Provides flexible chunking strategies: by line count, by token count,
or hybrid mode (whichever limit is reached first).

Uses tiktoken for accurate token counting with OpenAI models.
Falls back to character-based estimation if tiktoken unavailable.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, List, Optional, Tuple

from .config import MODEL_ENCODINGS, DEFAULT_ENCODING, get_encoding_for_model


# Try to import tiktoken; gracefully fall back if not available
try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    tiktoken = None  # type: ignore
    TIKTOKEN_AVAILABLE = False

try:
    import sentencepiece as spm
    SENTENCEPIECE_AVAILABLE = True
except ImportError:
    spm = None  # type: ignore
    SENTENCEPIECE_AVAILABLE = False


_GENERIC_SENTENCEPIECE_CORPUS: Tuple[str, ...] = (
    "Hello world",
    "The quick brown fox jumps over the lazy dog.",
    "This text estimates tokens for translation requests.",
    "Multiple providers may use different tokenization strategies.",
    "Prompt counting should stay aligned with request slicing.",
    "こんにちは世界。今日はいい天気です。",
    "翻訳リクエストのトークン数を数えます。",
    "メニューや選択肢の行も分割対象です。",
)
_GENERIC_SENTENCEPIECE_PROCESSOR: Optional[Any] = None


def get_tokenizer_provider(model: str) -> str:
    """Infer the provider for a model ID.

    Args:
        model: Model identifier.

    Returns:
        Canonical provider slug when known, otherwise an empty string.
    """
    normalized = (model or "").strip().lower()
    if not normalized:
        return ""

    try:
        from .config import get_model_pricing

        provider = str(get_model_pricing(normalized).get("provider") or "").lower()
        if provider:
            return provider
    except Exception:
        pass

    if normalized.startswith(("gpt-", "chatgpt", "o1", "o3", "o4")):
        return "openai"
    if normalized.startswith(("gemini", "google")):
        return "google"
    if any(
        marker in normalized
        for marker in ("mistral", "magistral", "ministral", "codestral")
    ):
        return "mistral"
    return ""


def get_tokenizer_family(model: str) -> str:
    """Return the tokenizer family CherryAI should use for a model.

    Args:
        model: Model identifier.

    Returns:
        ``"openai"`` for tiktoken-backed models,
        ``"sentencepiece"`` for Google/Mistral models,
        otherwise ``"heuristic"``.
    """
    provider = get_tokenizer_provider(model)
    if provider == "openai":
        return "openai"
    if provider in {"google", "mistral"}:
        return "sentencepiece"
    return "heuristic"


def _iter_generic_sentencepiece_corpus() -> Iterable[str]:
    """Yield the tiny multilingual corpus used for the generic processor."""
    yield from _GENERIC_SENTENCEPIECE_CORPUS


def _get_generic_sentencepiece_processor() -> Optional[Any]:
    """Build and cache a tiny generic SentencePiece processor.

    The provider-specific model tokenizers are not bundled with CherryAI, so the
    fallback path uses a small multilingual SentencePiece model trained once in
    memory. This stays optional and is only used when the ``sentencepiece``
    package is installed.
    """
    global _GENERIC_SENTENCEPIECE_PROCESSOR

    if _GENERIC_SENTENCEPIECE_PROCESSOR is not None:
        return _GENERIC_SENTENCEPIECE_PROCESSOR
    if not SENTENCEPIECE_AVAILABLE:
        return None

    try:
        model_buffer = io.BytesIO()
        spm.SentencePieceTrainer.train(
            sentence_iterator=_iter_generic_sentencepiece_corpus(),
            model_writer=model_buffer,
            model_type="bpe",
            vocab_size=128,
            character_coverage=1.0,
            hard_vocab_limit=False,
            bos_id=-1,
            eos_id=-1,
            pad_id=-1,
        )
        _GENERIC_SENTENCEPIECE_PROCESSOR = spm.SentencePieceProcessor(
            model_proto=model_buffer.getvalue(),
        )
    except Exception as exc:
        logging.getLogger(__name__).warning(
            "Failed to initialize generic sentencepiece processor: %s",
            exc,
        )
        _GENERIC_SENTENCEPIECE_PROCESSOR = None
    return _GENERIC_SENTENCEPIECE_PROCESSOR


def _estimate_tokens_heuristic(text: str) -> int:
    """Estimate tokens using lightweight script-aware heuristics."""
    if not text:
        return 0
    has_cjk = any(
        (0x3040 <= ord(ch) <= 0x30FF)
        or (0x3400 <= ord(ch) <= 0x4DBF)
        or (0x4E00 <= ord(ch) <= 0x9FFF)
        for ch in text
    )
    if has_cjk:
        return max(1, len(text) // 2)
    return max(1, len(text) // 4)


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
        self._sentencepiece_processor: Optional[Any] = None
        self._token_cache: dict[str, int] = {}  # Cache line -> token count
        self._last_count_method = "heuristic"
        
        # Initialize tokenizer backend if token counting is needed.
        if self.config.mode in (ChunkMode.TOKENS, ChunkMode.HYBRID):
            self._init_tokenizer()

    @property
    def last_count_method(self) -> str:
        """Return the backend used by the most recent token count."""
        return self._last_count_method

    def _init_tokenizer(self) -> None:
        """Initialize the preferred tokenizer backend for the configured model."""
        tokenizer_family = get_tokenizer_family(self.config.model)

        if tokenizer_family == "openai":
            if not TIKTOKEN_AVAILABLE:
                self.logger.warning(
                    "tiktoken not installed - using heuristic token estimation. "
                    "Install with: pip install tiktoken"
                )
                return

            try:
                if self.config.model in MODEL_ENCODINGS:
                    encoding_name = MODEL_ENCODINGS[self.config.model]
                    self._encoder = tiktoken.get_encoding(encoding_name)
                    self._last_count_method = f"tiktoken/{encoding_name}"
                    return

                try:
                    self._encoder = tiktoken.encoding_for_model(self.config.model)
                    self._last_count_method = "tiktoken/model"
                    return
                except KeyError:
                    self._encoder = tiktoken.get_encoding(DEFAULT_ENCODING)
                    self._last_count_method = f"tiktoken/{DEFAULT_ENCODING}"
                    self.logger.debug(
                        "No specific encoding for model '%s', using %s",
                        self.config.model,
                        DEFAULT_ENCODING,
                    )
                    return
            except Exception as exc:
                self.logger.warning("Failed to initialize tiktoken encoder: %s", exc)
                self._encoder = None
                return

        if tokenizer_family == "sentencepiece":
            if not SENTENCEPIECE_AVAILABLE:
                self.logger.warning(
                    "sentencepiece not installed - using heuristic token estimation. "
                    "Install with: pip install sentencepiece"
                )
                return

            self._sentencepiece_processor = _get_generic_sentencepiece_processor()
            if self._sentencepiece_processor is not None:
                self._last_count_method = "sentencepiece/generic"

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
            count = len(self._encoder.encode(text))  # type: ignore
            method = self._last_count_method
        elif self._sentencepiece_processor is not None:
            count = len(self._sentencepiece_processor.encode(text, out_type=int))
            method = "sentencepiece/generic"
        else:
            count = _estimate_tokens_heuristic(text)
            method = "heuristic"
        
        self._last_count_method = method
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


def is_sentencepiece_available() -> bool:
    """Check if sentencepiece is available for provider-aware token counting."""
    return SENTENCEPIECE_AVAILABLE

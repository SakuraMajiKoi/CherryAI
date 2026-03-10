# Adding a New LLM Provider

This guide explains how to register a new LLM provider with CherryAI's
Provider Handshake system.

## Quick Start

1. Copy `providers/provider_template.py` → `providers/my_provider.py`
2. Rename the class and fill in every `# TODO` section
3. Register in `providers/__init__.py`
4. Run validation to confirm the provider is correct

## Two Paths

### Path A: OpenAI-Compatible API (recommended)

If your provider speaks the OpenAI `/v1/chat/completions` format (most do),
inherit from `OpenAICompatProvider`:

```python
from .openai_provider import OpenAICompatProvider
from . import ProviderRegistry

class MyProvider(OpenAICompatProvider):
    name = "myprovider"
    display_name = "My Provider"
    base_url = "https://api.myprovider.com/v1"
    requires_api_key = True

    def get_input_price(self, model_id: str) -> float:
        return 1.0  # USD per 1M input tokens

    def get_output_price(self, model_id: str) -> float:
        return 2.0  # USD per 1M output tokens

ProviderRegistry.register(MyProvider())
```

This gives you `send_request`, `parse_response`, error mapping, and
structured output support for free.  Override only what differs.

**Examples:** `google_provider.py`, `mistral_provider.py`, `anthropic_provider.py`

### Path B: Fully Custom API

For APIs that don't follow the OpenAI format, implement `ProviderBase`
directly.  All 7 mandatory methods must be defined.

**Example:** `local_provider.py`

## Mandatory Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `name` | `str` | Unique lowercase slug (e.g. `"openai"`) |
| `display_name` | `str` | Human-readable name (e.g. `"OpenAI"`) |
| `base_url` | `str` | API endpoint URL |
| `requires_api_key` | `bool` | `False` for local providers |

## Mandatory Methods

| Method | Purpose |
|--------|---------|
| `send_request(...)` | Send a chat-completion request |
| `parse_response(...)` | Parse raw SDK response |
| `get_input_price(model_id)` | USD per 1M input tokens |
| `get_output_price(model_id)` | USD per 1M output tokens |
| `supports_structured_output(model_id)` | Can the model return JSON? |
| `get_model_name(model_id)` | Human-readable model name |
| `get_thinking_config(model_id)` | Thinking/reasoning support |

## Optional Methods (with defaults)

| Method | Default | Override When |
|--------|---------|---------------|
| `get_temperature_config()` | 0.0–2.0, default 0.3 | Different range (e.g. Mistral 0–1.0) or unsupported (e.g. GPT-5) |
| `get_context_window()` | 128,000 | Model has a different context window |
| `get_response_format()` | `{"type": "json_object"}` | Provider needs `json_schema` (e.g. local providers) |
| `get_cached_input_config()` | `None` | Provider supports prompt caching |
| `get_batch_config()` | `None` | Provider supports batch processing |
| `fetch_models(api_key)` | `[]` | Live model list fetching |
| `classify_error(error)` | `None` | Provider-specific error mapping |

## Registration

### Step 1: Add to `_load_providers()`

In `providers/__init__.py`, add a try/except block:

```python
try:
    from . import my_provider  # noqa: F401
except Exception:
    logger.debug("Could not load my_provider")
```

### Step 2: Register in your module

At the bottom of your provider file:

```python
ProviderRegistry.register(MyProvider())
```

## Validation

Run `validate_provider()` to check compliance:

```python
from providers import ProviderRegistry, validate_provider

provider = ProviderRegistry.get("myprovider")
errors = validate_provider(provider)
assert errors == [], errors  # Empty = valid
```

This checks:
- All 4 attributes are non-empty and correct type
- All 7 mandatory methods exist and are callable

## Testing

Add tests to `dev/test_provider_handshake.py`:

```python
class TestMyProvider:
    def test_attributes(self):
        prov = MyProvider()
        assert prov.name == "myprovider"
        assert prov.requires_api_key is True

    def test_validation(self):
        errors = validate_provider(MyProvider())
        assert errors == []

    def test_structured_output(self):
        assert MyProvider().supports_structured_output("model-x")
```

## Checklist

- [ ] Provider file created in `providers/`
- [ ] All mandatory attributes set
- [ ] All mandatory methods implemented
- [ ] `ProviderRegistry.register(...)` at module bottom
- [ ] Lazy import added to `_load_providers()` in `__init__.py`
- [ ] `validate_provider()` returns no errors
- [ ] Tests added to `dev/test_provider_handshake.py`
- [ ] Model pricing matches official documentation

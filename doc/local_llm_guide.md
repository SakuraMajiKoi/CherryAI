# Local LLM Integration Guide

CherryAI supports local LLM servers including LM Studio, Ollama, and text-generation-webui.
Local models offer privacy, no API costs, and offline operation.

---

## Quick Start

```bash
# 1. Start your local server (LM Studio, Ollama, etc.)

# 2. Configure CherryAI
python CherryAI.py config api_url local
python CherryAI.py config api_key dummy

# 3. Translate
python CherryAI.py translate file.txt -s ja -t en --no-api-key
```

---

## Detecting Local Servers

CherryAI can automatically detect running local LLM servers:

```bash
# Scan for all local servers
python CherryAI.py local detect

# Check a specific URL
python CherryAI.py local check --url http://localhost:1234/v1

# Get setup instructions
python CherryAI.py local setup --provider lmstudio
python CherryAI.py local setup --provider ollama
python CherryAI.py local setup --provider text-gen-webui
```

---

## Supported Providers

### LM Studio

Popular GUI application with built-in server functionality.

**Default URL:** `http://localhost:1234/v1`

**Setup:**
1. Download from https://lmstudio.ai/
2. Install and launch
3. Download a model (search for "llama" or "mistral")
4. Go to "Local Server" tab (left sidebar)
5. Click "Start Server"

**Configuration:**
```bash
python CherryAI.py config api_url http://localhost:1234/v1
python CherryAI.py config api_key dummy
python CherryAI.py config model local-model
```

**Tips:**
- Use models with at least 7B parameters for translation
- Context length of 4096+ recommended
- Temperature 0.3-0.5 works well for translation

---

### Ollama

Lightweight local LLM runner with easy model management.

**Default URL:** `http://localhost:11434/v1`

**Setup:**
1. Download from https://ollama.ai/
2. Install following OS-specific instructions
3. Pull a model:
   ```bash
   ollama pull llama3.2
   # or
   ollama pull mistral
   ```
4. Server starts automatically

**Configuration:**
```bash
python CherryAI.py config api_url http://localhost:11434/v1
python CherryAI.py config api_key dummy
python CherryAI.py config model llama3.2
```

**Useful Commands:**
```bash
ollama list        # List installed models
ollama pull MODEL  # Download a model
ollama rm MODEL    # Remove a model
ollama serve       # Start server (usually automatic)
```

---

### text-generation-webui

Feature-rich web UI with OpenAI API compatibility.

**Default URL:** `http://localhost:5000/v1`

**Setup:**
1. Clone https://github.com/oobabooga/text-generation-webui
2. Run installer:
   - Windows: `start_windows.bat`
   - Linux: `start_linux.sh`
   - Mac: `start_macos.sh`
3. Download a model through the web UI (default: http://localhost:7860)
4. Enable OpenAI API extension:
   - Go to Session tab
   - Check "openai" in Extensions
   - Restart

**Configuration:**
```bash
python CherryAI.py config api_url http://localhost:5000/v1
python CherryAI.py config api_key dummy
```

---

## CLI Options for Local LLMs

| Option | Description |
|--------|-------------|
| `--no-api-key` | Skip API key validation (local servers don't need keys) |
| `--check-local` | Verify server health before translation |
| `--preset local` | Use local preset (localhost:1234) |
| `--preset ollama` | Use Ollama preset (localhost:11434) |

### Examples

```bash
# Basic translation with local LLM
python CherryAI.py translate file.txt -s ja -t en --no-api-key

# Check server health before translating
python CherryAI.py translate file.txt -s ja -t en --no-api-key --check-local

# Use a specific local preset
python CherryAI.py translate file.txt -s ja -t en --preset local
python CherryAI.py translate file.txt -s ja -t en --preset ollama

# Override model for local server
python CherryAI.py translate file.txt -s ja -t en --no-api-key --model mistral-7b
```

---

## Recommended Models for Translation

| Model | Size | Quality | Speed | Notes |
|-------|------|---------|-------|-------|
| Llama 3.2 3B | 3GB | Good | Fast | Good for simple texts |
| Llama 3.2 7B | 7GB | Better | Medium | Balanced quality/speed |
| Mistral 7B | 7GB | Better | Medium | Good instruction following |
| Llama 3.1 70B | 70GB | Best | Slow | Requires high-end GPU |
| Qwen 2.5 7B | 7GB | Better | Medium | Good multilingual support |

**Notes:**
- For Japanese translation, models with good CJK support are preferred
- Larger models generally produce better translations
- GGUF quantized models (Q4_K_M, Q5_K_M) offer good quality/speed tradeoff

---

## Troubleshooting

### Server Not Found

```
Error: Cannot connect to local LLM server
```

**Solutions:**
1. Start your local server application
2. Check the port is correct (1234 for LM Studio, 11434 for Ollama)
3. Run `python CherryAI.py local detect` to scan for servers

### Connection Timeout

```
Error: Connection timed out
```

**Solutions:**
1. Server may be loading a model (wait 30-60 seconds)
2. Increase timeout: `--timeout 120`
3. Check if server has enough memory for the model

### Empty Responses

```
Error: API returned empty response
```

**Solutions:**
1. Model may not support JSON output - try a different model
2. Reduce chunk size: `--chunk-size 20`
3. Some models need explicit prompting for JSON

### Out of Memory

```
Error: CUDA out of memory
```

**Solutions:**
1. Use a smaller model (7B instead of 13B)
2. Use quantized models (Q4_K_M, Q5_K_M)
3. Reduce context length in server settings
4. Close other GPU applications

---

## Performance Tips

1. **Use GPU**: Local LLMs are much faster on GPU vs CPU
2. **Quantization**: Q4_K_M models are 4-5x smaller with minimal quality loss
3. **Context Length**: Match server context length to your chunk size
4. **Concurrent Requests**: Local servers often perform better with 1 concurrent request
5. **Temperature**: Lower temperature (0.2-0.4) for more consistent translations

---

## API Compatibility

CherryAI works with any OpenAI-compatible API server. Requirements:

- Endpoint: `/v1/chat/completions`
- Support for `response_format: {"type": "json_object"}`
- Standard message format: system/user/assistant roles

Known compatible servers:
- LM Studio
- Ollama
- text-generation-webui (with openai extension)
- vLLM
- LocalAI
- llama-cpp-python (server mode)

---

## See Also

- [CLI Guide](cli_guide.md) - Full CLI reference
- [Configuration](configuration.md) - Configuration options
- API presets in `CherryAI.ini`

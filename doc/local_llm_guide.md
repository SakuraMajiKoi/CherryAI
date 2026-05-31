# Local LLM Integration Guide

CherryAI supports local LLM servers including LM Studio, Ollama, KoboldCPP, and text-generation-webui.
Local models offer privacy, no API costs, and offline operation.

---

## Quick Start

From the GUI, configure local runtimes in **Global Options > Local**. Local
providers are no longer configured in the API Provider submenu and do not
require an API key. The Translation key dropdown exposes local pseudo-keys such
as `lmstudio: Local`, `ollama: Local`, and `koboldcpp: Local`.

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
- CherryAI starts LM Studio through the documented CLI flow:
  `lms daemon up --json`, `lms server start --port <port>`, and
  `lms server status --json --quiet`.
- On Windows, CLI-only/headless startup requires the standalone `llmster`
  daemon metadata at `%USERPROFILE%\.lmstudio\.internal\llmster-install-location.json`.
  If it is missing, install/repair it with LM Studio's official command:
  `powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://lmstudio.ai/install.ps1 | iex"`.
- Downloaded-model discovery uses `/v1/models` when the server is running and
  falls back to `lms ls --json`.
- Model load/unload prefers `lms load <model> --context-length <n> --identifier <model> --yes`
  and `lms unload <identifier>`, with REST as a fallback.
- Auto-close stops both the HTTP server and standalone daemon with
  `lms server stop` and `lms daemon down`.
- If `lms daemon up --json` hangs at `Waking up LM Studio service...`,
  CherryAI reports that timeout directly; repair the LM Studio service/daemon
  before auto-start can succeed.

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

### KoboldCPP

Single-executable GGUF runner used heavily for creative-writing and game workflows.

**Default URL:** `http://localhost:5001/v1`

**Setup:**
1. Download KoboldCPP for your OS.
2. Launch it with a GGUF model and API server enabled.
3. Configure CherryAI:
   ```bash
   python CherryAI.py config api_url http://localhost:5001/v1
   python CherryAI.py config api_key dummy
   ```

**Operational note:** KoboldCPP model and core runtime settings are startup
arguments. CherryAI models load/settings changes for KoboldCPP as
`restart_required` operations instead of pretending they can be hot-swapped.

---

## Backend Control Support

CherryAI's local backend controller exposes the same operations for supported
local providers:

| Operation | LM Studio | Ollama | KoboldCPP |
|-----------|-----------|--------|-----------|
| Auto-launch | `lms server start` | `ollama serve` | Launch configured executable |
| Find models | `/v1/models` | `/api/tags` | Requires configured model path |
| Load model | Native LM Studio load API | Generate with `keep_alive` | Restart required |
| Start server | `lms server start` | `ollama serve` | Starts with process |
| Sync settings | Native load config | Request options | Restart required |
| Unload model | Native unload API | `keep_alive: 0` | Stop process |
| Close app/server | `lms server stop` | Managed process stop | Managed process stop |

Translation, glossary utility calls, and editor context-menu calls share the
same OpenAI-compatible request route. Selecting a local provider or local base
URL supplies a placeholder API key automatically.

## Global Options > Local

The Local submenu owns all LM Studio, Ollama, and KoboldCPP settings. Each
provider card saves its collapsed state, order, install folder, install status,
last selected model, discovered models, and automation policy in `user/API.ini`.
Installation checks are explicit: CherryAI only checks when the user presses
**Check Installation**, and if nothing is found it asks before searching a
chosen local folder.

Automation policy values are stored per provider:

| Key | Values |
|-----|--------|
| `Start` | `1` prompt/manual, `2` start with CherryAI, `3` start when translation starts |
| `Load` | `1` prompt/manual, `2` load with local app launch, `3` load when translation starts |
| `Unload` | `1` do not auto-unload, `2` unload when translation stops, `3` unload when 5 minutes idle |
| `Close` | `1` do not auto-close, `2` close with CherryAI, `3` close when 5 minutes idle |

Model settings such as context length, temperature, and GPU layers are also
stored per provider/model. Empty values mean "use the local application
default"; saved values are imposed by CherryAI when the backend supports that
operation. KoboldCPP model and core setting changes are treated as restart
required.

Local models bypass API-key and cloud price-cap warnings. Price warnings remain
active for cloud providers only.

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
- KoboldCPP
- text-generation-webui (with openai extension)
- vLLM
- LocalAI
- llama-cpp-python (server mode)

---

## See Also

- [CLI Guide](cli_guide.md) - Full CLI reference
- [Configuration](configuration.md) - Configuration options
- API presets in `CherryAI.ini`

"""Local LLM integration utilities.

This module provides tools for working with local LLM servers including:
- LM Studio (default port 1234)
- Ollama (default port 11434)
- text-generation-webui (default port 5000/5001)
- Any OpenAI-compatible local server

Features:
- Health check to verify server is running
- Auto-detection of common local LLM ports
- Model discovery from /v1/models endpoint
- Graceful error handling with helpful messages
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any, Tuple
import logging
import urllib.request
import urllib.error
import json
import socket

logger = logging.getLogger(__name__)


class LocalLLMProvider(Enum):
    """Known local LLM providers."""
    LMSTUDIO = "lmstudio"
    OLLAMA = "ollama"
    TEXT_GEN_WEBUI = "text-generation-webui"
    GENERIC = "generic"


@dataclass
class LocalServerInfo:
    """Information about a local LLM server."""
    provider: LocalLLMProvider
    base_url: str
    port: int
    is_healthy: bool = False
    models: List[str] = field(default_factory=list)
    error_message: Optional[str] = None
    response_time_ms: float = 0.0


@dataclass 
class ModelInfo:
    """Information about a model available on a local server."""
    id: str
    name: str
    owned_by: str = "local"
    created: int = 0
    
    @classmethod
    def from_openai_model(cls, data: Dict[str, Any]) -> "ModelInfo":
        """Create ModelInfo from OpenAI-format model response."""
        return cls(
            id=data.get("id", "unknown"),
            name=data.get("id", data.get("name", "unknown")),
            owned_by=data.get("owned_by", "local"),
            created=data.get("created", 0),
        )


# Default ports for known providers
DEFAULT_PORTS: Dict[LocalLLMProvider, List[int]] = {
    LocalLLMProvider.LMSTUDIO: [1234],
    LocalLLMProvider.OLLAMA: [11434],
    LocalLLMProvider.TEXT_GEN_WEBUI: [5000, 5001, 7860],
    LocalLLMProvider.GENERIC: [1234, 11434, 5000, 5001, 7860, 8000, 8080],
}


def check_port_open(host: str, port: int, timeout: float = 2.0) -> bool:
    """Check if a port is open on the given host.
    
    Args:
        host: Hostname or IP address.
        port: Port number to check.
        timeout: Connection timeout in seconds.
        
    Returns:
        True if port is open, False otherwise.
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except (socket.error, OSError) as e:
        logger.debug(f"Port check failed for {host}:{port}: {e}")
        return False


def detect_local_servers(
    host: str = "localhost",
    providers: Optional[List[LocalLLMProvider]] = None,
    timeout: float = 2.0,
) -> List[LocalServerInfo]:
    """Detect running local LLM servers.
    
    Scans common ports for known local LLM providers.
    
    Args:
        host: Hostname to scan (default: localhost).
        providers: List of providers to check, or None for all.
        timeout: Connection timeout per port in seconds.
        
    Returns:
        List of LocalServerInfo for detected servers.
    """
    if providers is None:
        providers = list(LocalLLMProvider)
    
    detected: List[LocalServerInfo] = []
    checked_ports: set = set()
    
    for provider in providers:
        ports = DEFAULT_PORTS.get(provider, [])
        for port in ports:
            if port in checked_ports:
                continue
            checked_ports.add(port)
            
            if check_port_open(host, port, timeout):
                base_url = f"http://{host}:{port}/v1"
                info = check_server_health(base_url, timeout)
                
                # Try to determine provider from response
                if info.is_healthy:
                    info.provider = _infer_provider(info, port)
                    detected.append(info)
    
    return detected


def _infer_provider(info: LocalServerInfo, port: int) -> LocalLLMProvider:
    """Infer the provider from server info and port."""
    # Check by port first
    if port == 11434:
        return LocalLLMProvider.OLLAMA
    if port == 1234:
        return LocalLLMProvider.LMSTUDIO
    if port in (5000, 5001, 7860):
        return LocalLLMProvider.TEXT_GEN_WEBUI
    
    # Check by model naming conventions
    for model in info.models:
        model_lower = model.lower()
        if "ollama" in model_lower or ":" in model:  # Ollama uses model:tag format
            return LocalLLMProvider.OLLAMA
        if "gguf" in model_lower:  # LM Studio often uses GGUF models
            return LocalLLMProvider.LMSTUDIO
    
    return LocalLLMProvider.GENERIC


def check_server_health(
    base_url: str,
    timeout: float = 5.0,
) -> LocalServerInfo:
    """Check if a local LLM server is healthy and responding.
    
    Attempts to contact the server and retrieve model information.
    
    Args:
        base_url: The base URL of the API (e.g., http://localhost:1234/v1).
        timeout: Request timeout in seconds.
        
    Returns:
        LocalServerInfo with health status and available models.
    """
    import time
    
    # Extract port from URL
    try:
        from urllib.parse import urlparse
        parsed = urlparse(base_url)
        port = parsed.port or 80
        host = parsed.hostname or "localhost"
    except Exception:
        port = 1234
        host = "localhost"
    
    info = LocalServerInfo(
        provider=LocalLLMProvider.GENERIC,
        base_url=base_url,
        port=port,
    )
    
    # Normalize URL
    if not base_url.endswith("/v1") and not base_url.endswith("/v1/"):
        base_url = base_url.rstrip("/") + "/v1"
    
    models_url = base_url.rstrip("/") + "/models"
    
    start_time = time.perf_counter()
    
    try:
        request = urllib.request.Request(
            models_url,
            headers={"Accept": "application/json"},
            method="GET",
        )
        
        with urllib.request.urlopen(request, timeout=timeout) as response:
            info.response_time_ms = (time.perf_counter() - start_time) * 1000
            
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                
                # Parse OpenAI-format model list
                if "data" in data:
                    info.models = [
                        m.get("id", m.get("name", "unknown"))
                        for m in data["data"]
                    ]
                elif "models" in data:
                    # Ollama format
                    info.models = [
                        m.get("name", m.get("model", "unknown"))
                        for m in data["models"]
                    ]
                elif isinstance(data, list):
                    # Simple list format
                    info.models = [str(m) for m in data]
                
                info.is_healthy = True
                logger.info(
                    f"Local server at {base_url} is healthy. "
                    f"Found {len(info.models)} model(s). Response: {info.response_time_ms:.0f}ms"
                )
            else:
                info.error_message = f"Server returned status {response.status}"
                
    except urllib.error.HTTPError as e:
        info.response_time_ms = (time.perf_counter() - start_time) * 1000
        
        # Some servers return 404 for /v1/models but are still usable
        if e.code == 404:
            # Try a simpler health check
            info.is_healthy = _try_simple_health_check(base_url, timeout)
            if info.is_healthy:
                info.error_message = "Model list not available, but server is responding"
            else:
                info.error_message = f"Server returned 404 and failed health check"
        else:
            info.error_message = f"HTTP error: {e.code} {e.reason}"
            
    except urllib.error.URLError as e:
        info.response_time_ms = (time.perf_counter() - start_time) * 1000
        
        if isinstance(e.reason, socket.timeout):
            info.error_message = "Connection timed out - server may be starting up"
        elif isinstance(e.reason, ConnectionRefusedError):
            info.error_message = "Connection refused - server is not running"
        else:
            info.error_message = f"Connection error: {e.reason}"
            
    except json.JSONDecodeError:
        info.response_time_ms = (time.perf_counter() - start_time) * 1000
        info.error_message = "Invalid JSON response from server"
        
    except Exception as e:
        info.response_time_ms = (time.perf_counter() - start_time) * 1000
        info.error_message = f"Unexpected error: {str(e)}"
        logger.exception(f"Error checking server health at {base_url}")
    
    return info


def _try_simple_health_check(base_url: str, timeout: float) -> bool:
    """Try a simple health check without model listing."""
    try:
        # Just check if the server responds to any request
        request = urllib.request.Request(
            base_url.rstrip("/"),
            headers={"Accept": "application/json"},
            method="GET",
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status in (200, 404)  # 404 is OK, means server is up
    except Exception:
        return False


def discover_models(
    base_url: str,
    timeout: float = 10.0,
) -> List[ModelInfo]:
    """Discover available models from a local LLM server.
    
    Args:
        base_url: The base URL of the API.
        timeout: Request timeout in seconds.
        
    Returns:
        List of ModelInfo objects for available models.
    """
    info = check_server_health(base_url, timeout)
    
    if not info.is_healthy:
        logger.warning(f"Server not healthy: {info.error_message}")
        return []
    
    models: List[ModelInfo] = []
    for model_id in info.models:
        models.append(ModelInfo(
            id=model_id,
            name=model_id,
            owned_by="local",
        ))
    
    return models


def get_local_error_help(error: Exception, base_url: str) -> str:
    """Get helpful error message for common local LLM issues.
    
    Args:
        error: The exception that occurred.
        base_url: The URL being accessed.
        
    Returns:
        Helpful error message with troubleshooting steps.
    """
    error_str = str(error).lower()
    
    # Connection refused
    if "connection refused" in error_str or "actively refused" in error_str:
        return (
            f"❌ Cannot connect to local LLM server at {base_url}\n\n"
            "The server is not running. Please start your local LLM:\n\n"
            "• LM Studio: Start the app and click 'Start Server'\n"
            "• Ollama: Run 'ollama serve' in terminal\n"
            "• text-generation-webui: Run 'start_windows.bat' or 'start_linux.sh'\n\n"
            "Then try again."
        )
    
    # Timeout
    if "timed out" in error_str or "timeout" in error_str:
        return (
            f"⏱️ Connection to {base_url} timed out\n\n"
            "The server may be:\n"
            "• Starting up (wait a moment and retry)\n"
            "• Loading a model (can take 30-60 seconds)\n"
            "• Overloaded with requests\n\n"
            "Try increasing timeout with --timeout 120"
        )
    
    # SSL/TLS errors
    if "ssl" in error_str or "certificate" in error_str:
        return (
            f"🔒 SSL/TLS error connecting to {base_url}\n\n"
            "Local servers typically don't use HTTPS.\n"
            "Make sure your URL starts with http:// not https://\n\n"
            "Example: http://localhost:1234/v1"
        )
    
    # 404 Not Found
    if "404" in error_str or "not found" in error_str:
        return (
            f"❓ Endpoint not found at {base_url}\n\n"
            "The server is running but the endpoint is wrong.\n"
            "Common API paths:\n"
            "• LM Studio: http://localhost:1234/v1\n"
            "• Ollama: http://localhost:11434/v1\n"
            "• text-generation-webui: http://localhost:5000/v1\n\n"
            "Make sure --api-url ends with /v1"
        )
    
    # 401 Unauthorized
    if "401" in error_str or "unauthorized" in error_str:
        return (
            f"🔑 Authentication error at {base_url}\n\n"
            "The server requires an API key.\n"
            "Either:\n"
            "• Set the API key in your server configuration\n"
            "• Use --no-api-key if your server doesn't need one\n"
            "• Configure the server to not require authentication"
        )
    
    # Generic error
    return (
        f"❌ Error connecting to local LLM at {base_url}\n\n"
        f"Error: {error}\n\n"
        "Troubleshooting:\n"
        "1. Verify the server is running\n"
        "2. Check the port number is correct\n"
        "3. Ensure the server is OpenAI-compatible\n"
        "4. Try: python CherryAI.py test --skip-api"
    )


def get_provider_setup_instructions(provider: LocalLLMProvider) -> str:
    """Get setup instructions for a specific provider.
    
    Args:
        provider: The local LLM provider.
        
    Returns:
        Setup instructions as a formatted string.
    """
    instructions = {
        LocalLLMProvider.LMSTUDIO: """
LM Studio Setup
===============

1. Download LM Studio from https://lmstudio.ai/
2. Install and launch the application
3. Download a model (e.g., search for "llama" or "mistral")
4. Go to "Local Server" tab (left sidebar)
5. Click "Start Server" (default port: 1234)
6. In CherryAI, use:
   python CherryAI.py config api_url http://localhost:1234/v1
   python CherryAI.py config api_key dummy

Tips:
- Use a model with at least 7B parameters for good quality
- Context length of 4096+ recommended
- Set temperature to 0.3-0.5 for translation
""",
        LocalLLMProvider.OLLAMA: """
Ollama Setup
============

1. Download Ollama from https://ollama.ai/
2. Install following the instructions for your OS
3. Pull a model:
   ollama pull llama3.2
   or
   ollama pull mistral
4. The server starts automatically on port 11434
5. In CherryAI, use:
   python CherryAI.py config api_url http://localhost:11434/v1
   python CherryAI.py config api_key dummy

Tips:
- List available models: ollama list
- Pull larger models for better quality: ollama pull llama3.2:70b
- Ollama automatically manages GPU/CPU allocation
""",
        LocalLLMProvider.TEXT_GEN_WEBUI: """
text-generation-webui Setup
===========================

1. Clone from https://github.com/oobabooga/text-generation-webui
2. Run the installer for your OS:
   Windows: start_windows.bat
   Linux: start_linux.sh
   Mac: start_macos.sh
3. Download a model through the web UI (default: http://localhost:7860)
4. Enable the OpenAI API extension:
   - Go to Session tab
   - Check "openai" in Extensions
   - Restart
5. In CherryAI, use:
   python CherryAI.py config api_url http://localhost:5000/v1
   python CherryAI.py config api_key dummy

Tips:
- The OpenAI API runs on port 5000 by default
- Use GPTQ or GGUF models for efficiency
- ExLlama2 loader is fastest for GPTQ models
""",
        LocalLLMProvider.GENERIC: """
Generic OpenAI-Compatible Server Setup
======================================

CherryAI works with any OpenAI-compatible local server.

Requirements:
- /v1/chat/completions endpoint
- Support for JSON mode (response_format: {type: "json_object"})
- Standard message format: system/user/assistant roles

Configuration:
1. Start your server (note the port)
2. Set the API URL:
   python CherryAI.py config api_url http://localhost:PORT/v1
3. Set a dummy API key:
   python CherryAI.py config api_key dummy

Common servers:
- vLLM: python -m vllm.entrypoints.openai.api_server
- LocalAI: https://localai.io/
- llama-cpp-python with server mode
""",
    }
    
    return instructions.get(provider, instructions[LocalLLMProvider.GENERIC])


def format_server_status(servers: List[LocalServerInfo]) -> str:
    """Format server detection results for display.
    
    Args:
        servers: List of detected servers.
        
    Returns:
        Formatted string for display.
    """
    if not servers:
        return (
            "No local LLM servers detected.\n\n"
            "To use a local LLM:\n"
            "1. Start your local server (LM Studio, Ollama, etc.)\n"
            "2. Run: python CherryAI.py config api_url local\n"
            "3. Run: python CherryAI.py config api_key dummy"
        )
    
    lines = ["Detected Local LLM Servers:\n"]
    
    for server in servers:
        status = "✅" if server.is_healthy else "❌"
        lines.append(f"{status} {server.provider.value} at {server.base_url}")
        
        if server.is_healthy:
            lines.append(f"   Response time: {server.response_time_ms:.0f}ms")
            if server.models:
                lines.append(f"   Models: {', '.join(server.models[:5])}")
                if len(server.models) > 5:
                    lines.append(f"   ... and {len(server.models) - 5} more")
        else:
            lines.append(f"   Error: {server.error_message}")
        
        lines.append("")
    
    return "\n".join(lines)


# Factory functions for easy use
def create_local_health_checker() -> Tuple[bool, str, List[str]]:
    """Quick health check for local LLM servers.
    
    Returns:
        Tuple of (is_any_healthy, status_message, list_of_models)
    """
    servers = detect_local_servers()
    
    if not servers:
        return False, "No local servers found", []
    
    healthy_servers = [s for s in servers if s.is_healthy]
    
    if not healthy_servers:
        return False, format_server_status(servers), []
    
    # Return first healthy server's models
    best_server = healthy_servers[0]
    return True, format_server_status(servers), best_server.models


def is_local_url(url: str) -> bool:
    """Check if a URL points to a local server.
    
    Args:
        url: The URL to check.
        
    Returns:
        True if the URL is local (localhost, 127.0.0.1, etc.)
    """
    if not url:
        return False
    
    url_lower = url.lower()
    local_patterns = [
        "localhost",
        "127.0.0.1",
        "0.0.0.0",
        "192.168.",
        "10.0.",
        "172.16.",
        "172.17.",
        "172.18.",
        "172.19.",
        "172.20.",
        "172.21.",
        "172.22.",
        "172.23.",
        "172.24.",
        "172.25.",
        "172.26.",
        "172.27.",
        "172.28.",
        "172.29.",
        "172.30.",
        "172.31.",
    ]
    
    return any(pattern in url_lower for pattern in local_patterns)

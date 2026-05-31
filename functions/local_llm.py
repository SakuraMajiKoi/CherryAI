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
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
import logging
import urllib.request
import urllib.error
import urllib.parse
import json
import csv
import io
import socket
import subprocess
import time
import shutil
import os
import sys

logger = logging.getLogger(__name__)


class LocalLLMProvider(Enum):
    """Known local LLM providers."""
    LMSTUDIO = "lmstudio"
    OLLAMA = "ollama"
    KOBOLDCPP = "koboldcpp"
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


@dataclass
class LocalLLMSettings:
    """Provider-neutral local model settings."""

    model: str
    base_url: str = "http://localhost:1234/v1"
    context_length: int = 4096
    temperature: float = 0.3
    gpu_layers: Optional[int] = None
    executable_path: str = ""
    model_path: str = ""
    extra_args: List[str] = field(default_factory=list)


@dataclass
class LocalLLMControlResult:
    """Result from a local backend control operation."""

    success: bool
    message: str = ""
    models: List[str] = field(default_factory=list)
    restart_required: bool = False


LOCAL_PROVIDER_ALIASES: Dict[str, LocalLLMProvider] = {
    "lmstudio": LocalLLMProvider.LMSTUDIO,
    "ollama": LocalLLMProvider.OLLAMA,
    "koboldcpp": LocalLLMProvider.KOBOLDCPP,
    "local": LocalLLMProvider.LMSTUDIO,
}

_INSTALL_COMMANDS: Dict[LocalLLMProvider, List[str]] = {
    LocalLLMProvider.LMSTUDIO: ["lms", "LM Studio.exe"],
    LocalLLMProvider.OLLAMA: ["ollama"],
    LocalLLMProvider.KOBOLDCPP: ["koboldcpp", "koboldcpp.exe"],
}

_INSTALL_HINTS: Dict[LocalLLMProvider, str] = {
    LocalLLMProvider.LMSTUDIO: "https://lmstudio.ai/",
    LocalLLMProvider.OLLAMA: "https://ollama.com/download",
    LocalLLMProvider.KOBOLDCPP: "https://github.com/LostRuins/koboldcpp/releases",
}

_COMMON_INSTALL_DIRS: Dict[LocalLLMProvider, List[str]] = {
    LocalLLMProvider.LMSTUDIO: [
        r"%LOCALAPPDATA%\Programs\LM Studio",
        r"%PROGRAMFILES%\LM Studio",
    ],
    LocalLLMProvider.OLLAMA: [
        r"%LOCALAPPDATA%\Programs\Ollama",
        r"%PROGRAMFILES%\Ollama",
    ],
    LocalLLMProvider.KOBOLDCPP: [],
}


# Default ports for known providers
DEFAULT_PORTS: Dict[LocalLLMProvider, List[int]] = {
    LocalLLMProvider.LMSTUDIO: [1234],
    LocalLLMProvider.OLLAMA: [11434],
    LocalLLMProvider.KOBOLDCPP: [5001, 5000],
    LocalLLMProvider.TEXT_GEN_WEBUI: [5000, 5001, 7860],
    LocalLLMProvider.GENERIC: [1234, 11434, 5000, 5001, 7860, 8000, 8080],
}


def get_provider_download_url(provider: LocalLLMProvider) -> str:
    """Return the download URL for a local provider."""
    return _INSTALL_HINTS.get(provider, "")


def normalize_local_provider(provider: str) -> LocalLLMProvider:
    """Normalize a local provider key to ``LocalLLMProvider``."""
    return LOCAL_PROVIDER_ALIASES.get(
        (provider or "").strip().lower(),
        LocalLLMProvider.GENERIC,
    )


def find_local_llm_installation(
    provider: LocalLLMProvider,
    *,
    search_dir: Optional[str] = None,
) -> Optional[str]:
    """Find a local LLM installation folder.

    This function is intentionally passive and should only be called from an
    explicit user action, such as the Global Options "Check Installation"
    button.
    """
    if search_dir:
        root = Path(search_dir)
        if root.exists():
            names = [name.lower() for name in _INSTALL_COMMANDS.get(provider, [])]
            for path in root.rglob("*"):
                try:
                    if path.is_file() and path.name.lower() in names:
                        return str(path.parent)
                except OSError:
                    continue
        return None

    for raw_dir in _COMMON_INSTALL_DIRS.get(provider, []):
        expanded = Path(os.path.expandvars(raw_dir))
        if expanded.exists():
            return str(expanded)

    for command in _INSTALL_COMMANDS.get(provider, []):
        found = shutil.which(command)
        if found:
            return str(Path(found).resolve().parent)

    return None


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
                    info.provider = (
                        provider
                        if provider != LocalLLMProvider.GENERIC
                        else _infer_provider(info, port)
                    )
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


def _post_json(url: str, payload: Dict[str, Any], timeout: float = 30.0) -> Tuple[int, Dict[str, Any]]:
    """POST JSON and return ``(status, parsed_body)``."""
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8")
        parsed = json.loads(body) if body else {}
        return response.status, parsed


def _native_lmstudio_url(base_url: str) -> str:
    """Convert an OpenAI base URL to LM Studio's native API root."""
    if base_url.endswith("/v1"):
        return base_url[:-3] + "/api/v1"
    if base_url.endswith("/v1/"):
        return base_url[:-4] + "/api/v1"
    return base_url.rstrip("/") + "/api/v1"


def _lmstudio_server_start_command(base_url: str) -> List[str]:
    """Build an LM Studio CLI server-start command for the configured port."""
    args = ["lms", "server", "start"]
    try:
        parsed = urllib.parse.urlparse(base_url)
        if parsed.port:
            args.extend(["--port", str(parsed.port)])
    except ValueError:
        pass
    return args


def _lmstudio_port(base_url: str) -> int:
    try:
        parsed = urllib.parse.urlparse(base_url)
        if parsed.port:
            return int(parsed.port)
    except ValueError:
        pass
    return 1234


def _run_json_command(args: List[str], timeout: float = 30.0) -> Tuple[LocalLLMControlResult, Dict[str, Any]]:
    result = _run_command(args, timeout=timeout)
    if not result.success:
        return result, {}
    try:
        return result, json.loads(result.message or "{}")
    except json.JSONDecodeError:
        return LocalLLMControlResult(False, f"Invalid JSON from {' '.join(args)}: {result.message}"), {}


def _lmstudio_server_status(base_url: str) -> Tuple[LocalLLMControlResult, bool]:
    result, data = _run_json_command(
        ["lms", "server", "status", "--json", "--quiet"],
        timeout=10.0,
    )
    if result.success:
        port = data.get("port")
        running = data.get("running") is True and (
            port in (None, _lmstudio_port(base_url))
        )
        return result, running
    return result, False


def _extract_model_names(data: Any) -> List[str]:
    names: List[str] = []

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            for key in ("id", "identifier", "model_key", "model", "path", "name"):
                item = value.get(key)
                if isinstance(item, str) and item and item not in names:
                    names.append(item)
                    break
            for item in value.values():
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    visit(data)
    return names


def _lmstudio_cli_models() -> List[str]:
    result, data = _run_json_command(["lms", "ls", "--json"], timeout=30.0)
    if not result.success:
        return []
    return _extract_model_names(data)


def _lmstudio_loaded_model_identifiers() -> List[str]:
    result, data = _run_json_command(["lms", "ps", "--json"], timeout=30.0)
    if not result.success:
        return []
    return _extract_model_names(data)


def _lmstudio_model_is_loaded(model: str) -> bool:
    return model in _lmstudio_loaded_model_identifiers()


def _lmstudio_load_command(settings: LocalLLMSettings) -> List[str]:
    args = [
        "lms",
        "load",
        settings.model,
        "--context-length",
        str(settings.context_length),
        "--identifier",
        settings.model,
        "--yes",
    ]
    return args


class LocalLLMBackend:
    """Provider-neutral controller for local LLM applications."""

    def __init__(self, provider: LocalLLMProvider, settings: LocalLLMSettings):
        self.provider = provider
        self.settings = settings
        self.process: Optional[subprocess.Popen[Any]] = None
        self.app_process: Optional[subprocess.Popen[Any]] = None
        self._prelaunch_pids: set[int] = set()

    def launch(self) -> LocalLLMControlResult:
        if self.provider == LocalLLMProvider.LMSTUDIO:
            info = check_server_health(self.settings.base_url, timeout=1.0)
            if info.is_healthy:
                return LocalLLMControlResult(True, "LM Studio server already running.")
            app_result = self._launch_executable_from_install_folder(
                ("LM Studio.exe", "LM Studio"),
            )
            if app_result.success:
                return app_result
            result = self._start_lmstudio_server()
            if result.success:
                return result
            return result
        if self.provider == LocalLLMProvider.OLLAMA:
            if check_port_open("127.0.0.1", 11434, timeout=0.5):
                return LocalLLMControlResult(True, "Ollama server already running.")
            self.process = subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return LocalLLMControlResult(True, "Started Ollama server.")
        if self.provider == LocalLLMProvider.KOBOLDCPP:
            if not self.settings.executable_path:
                return LocalLLMControlResult(False, "KoboldCPP executable_path is required.")
            args = [self.settings.executable_path]
            if self.settings.model_path:
                args.extend(["--model", self.settings.model_path])
            if self.settings.context_length:
                args.extend(["--contextsize", str(self.settings.context_length)])
            args.extend(self.settings.extra_args)
            self.process = subprocess.Popen(
                args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return LocalLLMControlResult(True, "Started KoboldCPP.")
        return LocalLLMControlResult(False, f"Launch unsupported for {self.provider.value}.")

    def _start_lmstudio_server(self) -> LocalLLMControlResult:
        """Start LM Studio's server process through the CLI."""
        info = check_server_health(self.settings.base_url, timeout=1.0)
        if info.is_healthy:
            return LocalLLMControlResult(True, "LM Studio server already running.")
        status_result, running = _lmstudio_server_status(self.settings.base_url)
        if running:
            return LocalLLMControlResult(True, "LM Studio server already running.")
        self._prelaunch_pids = _process_ids_by_image("lms.exe")
        daemon_result, daemon_status = _run_json_command(
            ["lms", "daemon", "up", "--json"],
            timeout=30.0,
        )
        if not daemon_result.success:
            _stop_new_processes("lms.exe", self._prelaunch_pids)
            return daemon_result
        if daemon_status.get("status") not in {"running", "already-running"}:
            return LocalLLMControlResult(
                False,
                f"LM Studio daemon did not report running: {daemon_result.message}",
            )
        start_result = _run_command(
            _lmstudio_server_start_command(self.settings.base_url),
            timeout=60.0,
        )
        if not start_result.success:
            _stop_new_processes("lms.exe", self._prelaunch_pids)
            return start_result
        status_result, running = _lmstudio_server_status(self.settings.base_url)
        if running:
            return LocalLLMControlResult(True, "Started LM Studio server.")
        return LocalLLMControlResult(
            False,
            status_result.message or "LM Studio server did not report running.",
        )

    def _launch_executable_from_install_folder(
        self,
        executable_names: Tuple[str, ...],
    ) -> LocalLLMControlResult:
        """Launch a GUI executable from the configured installation folder."""
        if not self.settings.executable_path:
            return LocalLLMControlResult(False, "No install folder configured.")
        root = Path(self.settings.executable_path)
        candidates: List[Path] = []
        if root.is_file():
            candidates.append(root)
        elif root.exists():
            for name in executable_names:
                candidates.extend(root.rglob(name))
        for candidate in candidates:
            try:
                self.app_process = subprocess.Popen(
                    [str(candidate)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return LocalLLMControlResult(True, f"Launched {candidate}.")
            except Exception as exc:
                return LocalLLMControlResult(False, str(exc))
        return LocalLLMControlResult(False, "Executable not found in install folder.")

    def start_server(self) -> LocalLLMControlResult:
        if self.provider == LocalLLMProvider.LMSTUDIO:
            return self._start_lmstudio_server()
        if self.provider == LocalLLMProvider.OLLAMA:
            return self.launch()
        if self.provider == LocalLLMProvider.KOBOLDCPP:
            return LocalLLMControlResult(
                True,
                "KoboldCPP starts its API server with the process.",
            )
        return LocalLLMControlResult(False, f"Start-server unsupported for {self.provider.value}.")

    def find_models(self) -> LocalLLMControlResult:
        if self.provider == LocalLLMProvider.LMSTUDIO:
            models = [m.id for m in discover_models(self.settings.base_url)]
            if not models:
                models = _lmstudio_cli_models()
            return LocalLLMControlResult(True, models=models, message=f"Found {len(models)} model(s).")
        if self.provider == LocalLLMProvider.OLLAMA:
            try:
                models = _list_ollama_models(self.settings.base_url)
                return LocalLLMControlResult(True, models=models, message=f"Found {len(models)} model(s).")
            except Exception as exc:
                return LocalLLMControlResult(False, str(exc))
        if self.provider == LocalLLMProvider.KOBOLDCPP:
            if self.settings.model_path:
                return LocalLLMControlResult(True, models=[self.settings.model_path])
            return LocalLLMControlResult(
                False,
                "KoboldCPP cannot discover models from the running server; provide model_path.",
                restart_required=True,
            )
        return LocalLLMControlResult(False, f"Model discovery unsupported for {self.provider.value}.")

    def load_model(self) -> LocalLLMControlResult:
        model = self.settings.model
        if self.provider == LocalLLMProvider.LMSTUDIO:
            if _lmstudio_model_is_loaded(model):
                return LocalLLMControlResult(True, f"LM Studio model already loaded: {model}")
            cli_result = _run_command(_lmstudio_load_command(self.settings), timeout=180.0)
            if cli_result.success:
                return cli_result
            payload: Dict[str, Any] = {
                "model": model,
                "context_length": self.settings.context_length,
                "echo_load_config": True,
            }
            try:
                status, _ = _post_json(
                    _native_lmstudio_url(self.settings.base_url).rstrip("/") + "/models/load",
                    payload,
                    timeout=120.0,
                )
                return LocalLLMControlResult(status < 400, f"LM Studio load status {status}.")
            except Exception as exc:
                return LocalLLMControlResult(False, str(exc))
        if self.provider == LocalLLMProvider.OLLAMA:
            return _ollama_generate(
                self.settings.base_url,
                model,
                "",
                keep_alive="5m",
                options={"num_ctx": self.settings.context_length},
            )
        if self.provider == LocalLLMProvider.KOBOLDCPP:
            return LocalLLMControlResult(
                False,
                "KoboldCPP model changes require restarting the process with a new --model path.",
                restart_required=True,
            )
        return LocalLLMControlResult(False, f"Load-model unsupported for {self.provider.value}.")

    def sync_model_settings(self) -> LocalLLMControlResult:
        if self.provider == LocalLLMProvider.LMSTUDIO:
            # LM Studio applies load configuration when loading the model.
            return self.load_model()
        if self.provider == LocalLLMProvider.OLLAMA:
            return _ollama_generate(
                self.settings.base_url,
                self.settings.model,
                "",
                keep_alive="5m",
                options={
                    "num_ctx": self.settings.context_length,
                    "temperature": self.settings.temperature,
                },
            )
        if self.provider == LocalLLMProvider.KOBOLDCPP:
            return LocalLLMControlResult(
                False,
                "KoboldCPP settings are command-line settings and require restart.",
                restart_required=True,
            )
        return LocalLLMControlResult(False, f"Sync unsupported for {self.provider.value}.")

    def unload_model(self) -> LocalLLMControlResult:
        if self.provider == LocalLLMProvider.LMSTUDIO:
            cli_result = _run_command(["lms", "unload", self.settings.model], timeout=60.0)
            if cli_result.success:
                return cli_result
            try:
                status, _ = _post_json(
                    _native_lmstudio_url(self.settings.base_url).rstrip("/") + "/models/unload",
                    {"instance_id": self.settings.model},
                    timeout=30.0,
                )
                return LocalLLMControlResult(status < 400, f"LM Studio unload status {status}.")
            except Exception as exc:
                return LocalLLMControlResult(False, str(exc))
        if self.provider == LocalLLMProvider.OLLAMA:
            return _ollama_generate(
                self.settings.base_url,
                self.settings.model,
                "",
                keep_alive=0,
            )
        if self.provider == LocalLLMProvider.KOBOLDCPP:
            return self.close()
        return LocalLLMControlResult(False, f"Unload unsupported for {self.provider.value}.")

    def close(self) -> LocalLLMControlResult:
        if self.provider == LocalLLMProvider.LMSTUDIO:
            server_result = _run_command(["lms", "server", "stop"])
            daemon_result = _run_command(["lms", "daemon", "down"])
            if self.app_process is not None and self.app_process.poll() is None:
                _stop_process_tree(self.app_process, timeout=10.0)
            if not server_result.success:
                return server_result
            if not daemon_result.success:
                return daemon_result
            return LocalLLMControlResult(
                True,
                "; ".join(
                    message
                    for message in (server_result.message, daemon_result.message)
                    if message
                )
                or "Stopped LM Studio server and daemon.",
            )
        if self.process is not None:
            _stop_process_tree(self.process, timeout=10.0)
            return LocalLLMControlResult(True, f"Stopped {self.provider.value}.")
        return LocalLLMControlResult(True, f"No managed {self.provider.value} process to stop.")

    def ensure_ready(self, timeout: float = 120.0) -> LocalLLMControlResult:
        launch_result = self.launch()
        if not launch_result.success:
            return launch_result
        server_result = self.start_server()
        if not server_result.success:
            return server_result
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            info = check_server_health(self.settings.base_url, timeout=5.0)
            if info.is_healthy:
                return LocalLLMControlResult(True, "Local LLM server is ready.", models=info.models)
            time.sleep(1.0)
        if self.process and self.process.poll() is None:
            _stop_process_tree(self.process)
        if self.provider == LocalLLMProvider.LMSTUDIO:
            _stop_new_processes("lms.exe", self._prelaunch_pids)
        return LocalLLMControlResult(False, "Timed out waiting for local LLM server.")


def create_backend_controller(
    provider: LocalLLMProvider,
    settings: LocalLLMSettings,
) -> LocalLLMBackend:
    """Create a provider-neutral local backend controller."""
    return LocalLLMBackend(provider, settings)


def _settings_from_api_ini(provider_key: str, model: str, base_url: str = "") -> LocalLLMSettings:
    """Build local backend settings from API.ini values."""
    from CherryAI.functions import api_config

    provider_settings = api_config.get_all_local_llm_settings(provider_key)
    model_settings = api_config.get_model_settings(model)
    context_length = 4096
    if model_settings.get("context_length"):
        try:
            context_length = int(model_settings["context_length"])
        except (TypeError, ValueError):
            context_length = 4096
    temperature = 0.3
    if model_settings.get("temperature"):
        try:
            temperature = float(model_settings["temperature"])
        except (TypeError, ValueError):
            temperature = 0.3
    gpu_layers: Optional[int] = None
    if model_settings.get("gpu_layers"):
        try:
            gpu_layers = int(model_settings["gpu_layers"])
        except (TypeError, ValueError):
            gpu_layers = None
    return LocalLLMSettings(
        model=model,
        base_url=(base_url or api_config.PROVIDER_BASE_URLS.get(provider_key, "")).rstrip("/"),
        context_length=context_length,
        temperature=temperature,
        gpu_layers=gpu_layers,
        executable_path=provider_settings.get("install_folder", ""),
        model_path=model if provider_key == "koboldcpp" else "",
    )


def prepare_local_llm_for_translation(
    provider_key: str,
    model: str,
    *,
    base_url: str = "",
) -> LocalLLMControlResult:
    """Apply local start/load policies before translation starts."""
    from CherryAI.functions import api_config

    provider_key = (provider_key or "").strip().lower()
    if provider_key not in api_config.LOCAL_LLM_PROVIDERS:
        return LocalLLMControlResult(True, "Not a managed local provider.")

    policy = api_config.get_all_local_llm_settings(provider_key)
    settings = _settings_from_api_ini(provider_key, model, base_url)
    controller = create_backend_controller(normalize_local_provider(provider_key), settings)
    messages: List[str] = []

    start_policy = policy.get("Start", "1")
    load_policy = policy.get("Load", "1")
    if start_policy == "3":
        result = controller.ensure_ready(timeout=120.0)
        messages.append(result.message)
        if not result.success:
            return result
        if result.models:
            api_config.set_local_llm_setting(provider_key, "models", "|".join(result.models))
    if load_policy in {"2", "3"} and model:
        result = controller.load_model()
        messages.append(result.message)
        if not result.success:
            return result

    return LocalLLMControlResult(True, "; ".join(m for m in messages if m) or "Local LLM ready.")


def finish_local_llm_after_translation(
    provider_key: str,
    model: str,
    *,
    base_url: str = "",
) -> LocalLLMControlResult:
    """Apply local unload/close policies after translation stops."""
    from CherryAI.functions import api_config

    provider_key = (provider_key or "").strip().lower()
    if provider_key not in api_config.LOCAL_LLM_PROVIDERS:
        return LocalLLMControlResult(True, "Not a managed local provider.")

    policy = api_config.get_all_local_llm_settings(provider_key)
    settings = _settings_from_api_ini(provider_key, model, base_url)
    controller = create_backend_controller(normalize_local_provider(provider_key), settings)
    messages: List[str] = []

    if policy.get("Unload", "1") == "2" and model:
        result = controller.unload_model()
        messages.append(result.message)
        if not result.success:
            return result
    if policy.get("Close", "1") == "2":
        result = controller.close()
        messages.append(result.message)
        if not result.success:
            return result

    return LocalLLMControlResult(True, "; ".join(m for m in messages if m) or "No local LLM stop action requested.")


def _run_command(args: List[str], timeout: float = 30.0) -> LocalLLMControlResult:
    try:
        completed = subprocess.run(
            args,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        return LocalLLMControlResult(False, f"Command not found: {args[0]}")
    except Exception as exc:
        return LocalLLMControlResult(False, str(exc))
    output = (completed.stdout or completed.stderr or "").strip()
    return LocalLLMControlResult(
        completed.returncode == 0,
        output or f"{' '.join(args)} exited with {completed.returncode}.",
    )


def _start_command_background(args: List[str]) -> LocalLLMControlResult:
    """Start a command in the background for long-lived local servers."""
    try:
        subprocess.Popen(
            args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        return LocalLLMControlResult(False, f"Command not found: {args[0]}")
    except Exception as exc:
        return LocalLLMControlResult(False, str(exc))
    return LocalLLMControlResult(True, f"Started {' '.join(args)}.")


def _stop_process_tree(process: subprocess.Popen[Any], timeout: float = 5.0) -> None:
    """Stop a process launched by CherryAI, including child processes on Windows."""
    if process.poll() is not None:
        return
    if sys.platform.startswith("win"):
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout,
            check=False,
        )
        return
    process.terminate()
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()


def _process_ids_by_image(image_name: str) -> set[int]:
    """Return Windows process IDs for an executable image name."""
    if not sys.platform.startswith("win"):
        return set()
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {image_name}", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            timeout=5.0,
            check=False,
        )
    except Exception:
        return set()
    pids: set[int] = set()
    for row in csv.reader(io.StringIO(result.stdout)):
        if len(row) < 2 or row[0].upper().startswith("INFO:"):
            continue
        try:
            pids.add(int(row[1]))
        except ValueError:
            continue
    return pids


def _stop_new_processes(image_name: str, known_pids: set[int]) -> None:
    """Stop Windows processes of ``image_name`` that appeared after launch."""
    if not sys.platform.startswith("win"):
        return
    for pid in _process_ids_by_image(image_name) - known_pids:
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5.0,
            check=False,
        )


def _ollama_api_root(base_url: str) -> str:
    if base_url.endswith("/v1"):
        return base_url[:-3]
    if base_url.endswith("/v1/"):
        return base_url[:-4]
    return base_url.rstrip("/")


def _list_ollama_models(base_url: str) -> List[str]:
    url = _ollama_api_root(base_url).rstrip("/") + "/api/tags"
    request = urllib.request.Request(url, headers={"Accept": "application/json"}, method="GET")
    with urllib.request.urlopen(request, timeout=10.0) as response:
        data = json.loads(response.read().decode("utf-8"))
    return [m.get("name", m.get("model", "unknown")) for m in data.get("models", [])]


def _ollama_generate(
    base_url: str,
    model: str,
    prompt: str,
    *,
    keep_alive: Any,
    options: Optional[Dict[str, Any]] = None,
) -> LocalLLMControlResult:
    payload: Dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "keep_alive": keep_alive,
    }
    if options:
        payload["options"] = options
    try:
        status, _ = _post_json(
            _ollama_api_root(base_url).rstrip("/") + "/api/generate",
            payload,
            timeout=120.0,
        )
        return LocalLLMControlResult(status < 400, f"Ollama generate status {status}.")
    except Exception as exc:
        return LocalLLMControlResult(False, str(exc))


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
        LocalLLMProvider.KOBOLDCPP: """
KoboldCPP Setup
===============

1. Download KoboldCPP for your OS
2. Start it with a GGUF model and OpenAI-compatible API enabled
3. Use the default API URL:
   python CherryAI.py config api_url http://localhost:5001/v1
   python CherryAI.py config api_key dummy

Operational notes:
- KoboldCPP model and most runtime settings are command-line options.
- Changing models or core settings requires restarting KoboldCPP.
- CherryAI's controller reports restart_required=True for those operations.
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
        status = "OK" if server.is_healthy else "FAIL"
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

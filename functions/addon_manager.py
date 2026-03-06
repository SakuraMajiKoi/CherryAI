"""Addon management for optional CherryAI components.

Manages the ``user/addons/`` directory and ``user/addons/addon.ini``
registry that tracks installed optional packages (e.g. EasyNMT for
MTL term translation).

Public API
----------
- :func:`get_addons_dir`  — path to ``user/addons/``
- :func:`get_addon_ini`   — path to ``user/addons/addon.ini``
- :func:`list_addons`     — installed addons with name and size
- :func:`is_installed`    — check if a named addon is present
- :func:`register_addon`  — record a newly installed addon
- :func:`delete_addon`    — remove an addon and its registry entry
- :func:`get_addon_path`  — path to a specific addon's directory
"""

from __future__ import annotations

import configparser
import logging
import shutil
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def get_addons_dir() -> Path:
    """Return the canonical ``user/addons/`` directory, creating it if needed."""
    here = Path(__file__).resolve()
    root = here.parent.parent  # …/CherryAI
    addons = root / "user" / "addons"
    addons.mkdir(parents=True, exist_ok=True)
    return addons


def get_addon_ini() -> Path:
    """Return the path to ``user/addons/addon.ini``."""
    return get_addons_dir() / "addon.ini"


# ---------------------------------------------------------------------------
# INI helpers
# ---------------------------------------------------------------------------

def _read_ini() -> configparser.ConfigParser:
    """Read the addon.ini file, creating it if missing."""
    ini_path = get_addon_ini()
    cfg = configparser.ConfigParser()
    if ini_path.exists():
        cfg.read(str(ini_path), encoding="utf-8")
    return cfg


def _write_ini(cfg: configparser.ConfigParser) -> None:
    """Write the config to addon.ini."""
    ini_path = get_addon_ini()
    ini_path.parent.mkdir(parents=True, exist_ok=True)
    with ini_path.open("w", encoding="utf-8") as fh:
        cfg.write(fh)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def list_addons() -> List[Dict[str, str]]:
    """Return a list of installed addons with name and human-readable size.

    Returns:
        List of dicts with ``name`` and ``size`` keys.
    """
    cfg = _read_ini()
    result: List[Dict[str, str]] = []
    for section in cfg.sections():
        addon_path = get_addons_dir() / section
        size = _dir_size_human(addon_path) if addon_path.is_dir() else "N/A"
        result.append({"name": section, "size": size})
    return result


def is_installed(name: str) -> bool:
    """Return True if addon *name* is registered in addon.ini."""
    cfg = _read_ini()
    return cfg.has_section(name)


def register_addon(name: str, **metadata: Any) -> None:
    """Register an addon in addon.ini.

    Args:
        name: Addon identifier (used as INI section name and subdirectory).
        **metadata: Arbitrary key-value pairs stored in the section.
    """
    cfg = _read_ini()
    if not cfg.has_section(name):
        cfg.add_section(name)
    for key, value in metadata.items():
        cfg.set(name, key, str(value))
    _write_ini(cfg)
    logger.info("Registered addon: %s", name)


def delete_addon(name: str) -> None:
    """Delete an addon's directory and its registry entry.

    Args:
        name: Addon identifier.

    Raises:
        FileNotFoundError: If the addon is not registered.
    """
    cfg = _read_ini()
    if not cfg.has_section(name):
        raise FileNotFoundError(f"Addon '{name}' is not registered")

    # Remove directory
    addon_path = get_addons_dir() / name
    if addon_path.is_dir():
        shutil.rmtree(addon_path)
        logger.info("Deleted addon directory: %s", addon_path)

    # Remove INI section
    cfg.remove_section(name)
    _write_ini(cfg)
    logger.info("Unregistered addon: %s", name)


def get_addon_path(name: str) -> Path:
    """Return the directory for a specific addon.

    Args:
        name: Addon identifier.

    Returns:
        Path to ``user/addons/<name>/``.
    """
    path = get_addons_dir() / name
    path.mkdir(parents=True, exist_ok=True)
    return path


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _dir_size_human(path: Path) -> str:
    """Return total size of *path* in human-readable format."""
    total = 0
    try:
        for f in path.rglob("*"):
            if f.is_file():
                total += f.stat().st_size
    except OSError:
        return "?"
    for unit in ("B", "KB", "MB", "GB"):
        if total < 1024:
            return f"{total:.1f} {unit}" if unit != "B" else f"{total} {unit}"
        total /= 1024
    return f"{total:.1f} TB"

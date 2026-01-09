"""Mode plugin system for CherryAI.

Each plugin module must define at least:
  - NAME: str (mode name as shown in UI)
  - PHASE: 'Pre' | 'Post' | 'Both'
Optional attributes:
  - PRIORITY: int (lower runs earlier)
  - USES_REGEX: bool (advisory for UI)
  - INPUTS: list[str] or int count (advisory; maps to in1..in4)
Functions (optional depending on PHASE):
  - apply_pre(processor, lines: list[str], op, stats: dict) -> int
  - apply_post(processor, lines: list[str], op, stats: dict) -> int

Plugins live in this folder. Files starting with '_' and 'template_mode.py' are ignored.
"""

from __future__ import annotations

from pathlib import Path
import importlib.util
import sys
from types import ModuleType
from typing import Dict
import types

MODE_REGISTRY: Dict[str, ModuleType] = {}


def load_modes(root: Path) -> Dict[str, ModuleType]:
    """Dynamically load mode modules from the given root/modi directory.

    Returns a mapping NAME->module.
    """
    global MODE_REGISTRY
    # Purge stale modules loaded under the wrong package name (e.g., 'CherryAI.*')
    stale = [k for k in list(sys.modules.keys()) if k == "CherryAI" or k.startswith("CherryAI.")]
    for k in stale:
        sys.modules.pop(k, None)

    # If registry exists but contains wrongly-named modules, clear it to rebuild
    if MODE_REGISTRY and any(getattr(m, "__name__", "").startswith("CherryAI.") for m in MODE_REGISTRY.values()):
        MODE_REGISTRY = {}
    if MODE_REGISTRY:
        return MODE_REGISTRY
    modi_dir = root / "modi"
    if not modi_dir.exists():
        return MODE_REGISTRY
    # Ensure namespace packages exist for CherryAI and its subpackages so relative imports resolve
    pkg = sys.modules.get("CherryAI")
    if pkg is None:
        pkg = types.ModuleType("CherryAI")
        pkg.__path__ = [str(root)]
        sys.modules["CherryAI"] = pkg
    sub = sys.modules.get("CherryAI.modi")
    if sub is None:
        sub = types.ModuleType("CherryAI.modi")
        sub.__path__ = [str(modi_dir)]
        sys.modules["CherryAI.modi"] = sub
    functions_dir = root / "functions"
    if functions_dir.exists() and "CherryAI.functions" not in sys.modules:
        fsub = types.ModuleType("CherryAI.functions")
        fsub.__path__ = [str(functions_dir)]
        sys.modules["CherryAI.functions"] = fsub
    # Compatibility aliases (lowercase) in case some plugin or environment tries 'CherryAI.*'
    sys.modules.setdefault("CherryAI", sys.modules["CherryAI"])
    if "CherryAI.modi" in sys.modules:
        sys.modules.setdefault("CherryAI.modi", sys.modules["CherryAI.modi"])
    if "CherryAI.functions" in sys.modules:
        sys.modules.setdefault("CherryAI.functions", sys.modules["CherryAI.functions"])
    for p in sorted(modi_dir.glob("*.py")):
        if p.name in ("__init__.py", "template_mode.py") or p.name.startswith("_"):
            continue
        # Use the actual package name (case-sensitive) so relative imports inside
        # plugins (for example '..functions') resolve correctly when modules are
        # exec'ed. The package folder is 'CherryAI', not 'CherryAI'.
        spec = importlib.util.spec_from_file_location(f"CherryAI.modi.{p.stem}", p)
        if not spec or not spec.loader:
            continue
        mod = importlib.util.module_from_spec(spec)
        # Explicitly set package for reliable relative imports inside plugins
        mod.__package__ = "CherryAI.modi"
        try:
            sys.modules[spec.name] = mod
            spec.loader.exec_module(mod)
        except Exception:
            continue
        name = getattr(mod, "NAME", None)
        if isinstance(name, str) and name:
            MODE_REGISTRY[name] = mod
    return MODE_REGISTRY

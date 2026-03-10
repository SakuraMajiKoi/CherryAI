"""Pytest configuration for CherryAI tests.

Sets up the Python path and module aliases so that imports like
`from CherryAI.functions.module import X` work correctly in the
test environment.
"""

import sys
import types
from pathlib import Path

import pytest

# The root directory of the CherryAI package
CHERRYAI_ROOT = Path(__file__).resolve().parent

# Ensure the parent directory (containing CherryAI folder) is in sys.path
# This allows `from functions.module import X` style imports
if str(CHERRYAI_ROOT) not in sys.path:
    sys.path.insert(0, str(CHERRYAI_ROOT))

# Also ensure parent of CherryAI is in path for `from CherryAI.X import Y` style
cherryai_parent = CHERRYAI_ROOT.parent
if str(cherryai_parent) not in sys.path:
    sys.path.insert(0, str(cherryai_parent))


def _setup_cherryai_package():
    """Set up the CherryAI package namespace for imports.
    
    Creates module stubs so that imports like:
    - `from CherryAI.modi import load_modes`
    - `from CherryAI.functions.module import X`
    work correctly even when running tests from the CherryAI directory.
    """
    # Create CherryAI namespace package if needed
    if "CherryAI" not in sys.modules:
        pkg = types.ModuleType("CherryAI")
        pkg.__path__ = [str(CHERRYAI_ROOT)]
        pkg.__file__ = str(CHERRYAI_ROOT / "__init__.py")
        sys.modules["CherryAI"] = pkg
    
    # Create CherryAI.modi namespace
    modi_dir = CHERRYAI_ROOT / "modi"
    if modi_dir.exists():
        # Import the actual modi package and set it up
        try:
            import modi as actual_modi  # type: ignore
            sys.modules["CherryAI.modi"] = actual_modi
        except ImportError:
            pass
    
    # Create CherryAI.functions namespace
    functions_dir = CHERRYAI_ROOT / "functions"
    if functions_dir.exists():
        try:
            import functions as actual_functions  # type: ignore
            sys.modules["CherryAI.functions"] = actual_functions
        except ImportError:
            pass
    
    # Create CherryAI.gui namespace
    gui_dir = CHERRYAI_ROOT / "gui"
    if gui_dir.exists():
        try:
            import gui as actual_gui  # type: ignore
            sys.modules["CherryAI.gui"] = actual_gui
        except ImportError:
            pass
    
    # Create CherryAI.formats namespace
    formats_dir = CHERRYAI_ROOT / "formats"
    if formats_dir.exists():
        try:
            import formats as actual_formats  # type: ignore
            sys.modules["CherryAI.formats"] = actual_formats
        except ImportError:
            pass

    # Create CherryAI.providers namespace
    providers_dir = CHERRYAI_ROOT / "providers"
    if providers_dir.exists():
        try:
            import providers as actual_providers  # type: ignore
            sys.modules["CherryAI.providers"] = actual_providers
        except ImportError:
            pass


# Pytest hook to ensure setup runs before each test session
@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):
    """Called after command-line options have been parsed and all plugins loaded."""
    _setup_cherryai_package()


@pytest.fixture(autouse=True)
def ensure_cherryai_imports():
    """Fixture to ensure CherryAI package aliases are set up before each test."""
    _setup_cherryai_package()
    yield


# Run setup on import as well (for non-pytest usage)
_setup_cherryai_package()

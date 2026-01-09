"""Glossary management modules for CherryAI.

This package contains:
- name_glossary_constants: Constants for name/speaker detection
- name_glossary_functions: Name/speaker detection and processing
- code_glossary_constants: Constants for code pattern detection
- code_glossary_functions: Code pattern detection and processing
"""

from __future__ import annotations

"""Public API surface for glossaries package.

This module intentionally avoids importing function-heavy submodules at
package import time to prevent circular-import problems. Import the
implementation modules directly where needed (for example:

    from CherryAI.functions.glossaries import name_glossary_constants
    from CherryAI.functions.glossaries import code_glossary_constants

) or import the function modules lazily inside functions.
"""

# Re-export only lightweight constants modules to keep package import cheap.
from . import name_glossary_constants as name_glossary_constants
from . import code_glossary_constants as code_glossary_constants

__all__ = [
    "name_glossary_constants",
    "code_glossary_constants",
]

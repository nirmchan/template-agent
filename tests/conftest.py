"""Root test configuration.

Ensures the project root is on sys.path so both ``deep_agent`` and
``aegra`` packages are importable in all test modules.
"""

import sys
from pathlib import Path

_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

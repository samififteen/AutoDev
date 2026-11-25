from __future__ import annotations

import sys
from pathlib import Path

# Make the repository root importable when pytest is invoked from the repo root
# without installing the package.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

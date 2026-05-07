"""Put monorepo root on sys.path so ``edgebox_db`` / ``edgebox_config`` resolve."""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_s = str(_ROOT)
if _s not in sys.path:
    sys.path.insert(0, _s)

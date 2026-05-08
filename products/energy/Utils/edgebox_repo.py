"""Put monorepo root on sys.path so ``edgebox_db`` / ``edgebox_config`` resolve."""
import sys
from pathlib import Path


def _repo_root() -> Path:
    p = Path(__file__).resolve().parent
    for anc in [p, *p.parents]:
        if (anc / "edgebox_config").is_dir():
            return anc
    raise RuntimeError("edgebox-gate root not found (missing edgebox_config/)")


_ROOT = _repo_root()
_s = str(_ROOT)
if _s not in sys.path:
    sys.path.insert(0, _s)

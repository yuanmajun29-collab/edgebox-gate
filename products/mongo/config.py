import sys
from pathlib import Path


def _repo_root() -> Path:
    p = Path(__file__).resolve().parent
    for anc in [p, *p.parents]:
        if (anc / "edgebox_config").is_dir():
            return anc
    raise RuntimeError("edgebox-gate root not found (missing edgebox_config/)")


_REPO_ROOT = _repo_root()
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from edgebox_config.base import *  # noqa: F401,F403

BASE_INFO = {
    **BASE_INFO,
    'web_version': 'v2.3.5.5',
}

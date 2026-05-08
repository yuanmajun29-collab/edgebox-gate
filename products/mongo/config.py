import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from edgebox_config.base import *  # noqa: F401,F403

BASE_INFO = {
    **BASE_INFO,
    'web_version': 'v2.3.5.5',
}

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from edgebox_config.base import *  # noqa: F401,F403

BASE_INFO = {
    **BASE_INFO,
    'web_version': 'v1.0.0.11',
}

NetAgreementType = "https"
DISK_PATH = "/dev/mmcblk0p2"

REGISTER_FLOW_BLUEPRINT = False
REGISTER_DYNAMIC_BLUEPRINT = False

"""维护脚本：向 Mongo 插入算法常量示例。默认将 ``apps/mongo`` 置于路径首位。"""
from pathlib import Path
import sys

_EDGE = Path(__file__).resolve().parents[3]
_REPO = _EDGE.parent
_APP = _EDGE / "apps" / "mongo"
for p in (_REPO, _APP):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)

import Utils.edgebox_repo  # noqa: F401
from Utils.db import ToMongo
from edgebox.db.mongo_collections import (
    WORK_FLOW_ALGORITHM_CONSTANT,
)

my_db = ToMongo('wavedevice')
constant_col = my_db.get_col(WORK_FLOW_ALGORITHM_CONSTANT)

new_item = {
        "algorithm_constant_id": "001573790963861606944",
        "algorithm_constant_name": "攀爬",
        "algorithm_constant_num": "13",
        "algorithm_constant_type": 3,
        "algorithm_constant_status": 1,
        "algorithm_level": 3,
        "algorithm_interval": 30,
        "algorithm_color": "#85C12B",
        "algorithm_model": 3,
        "algorithm_version": "v2.0",
        "rate_num": None
    }

my_db.insert(WORK_FLOW_ALGORITHM_CONSTANT, new_item)

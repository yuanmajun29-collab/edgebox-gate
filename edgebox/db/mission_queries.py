"""按 ``control_id`` / ``control_name`` 查询能耗站布控主表 ``control_manage_mission``。"""
from typing import Any, Dict, Optional

from .mongo_collections import CONTROL_MANAGE_MISSION


def control_mission_collection(my_db: Any):
    return my_db.get_col(CONTROL_MANAGE_MISSION)


def find_control_mission_by_control_id(
        my_db: Any,
        control_id: str,
        projection: Optional[Dict[str, Any]] = None,
):
    q = {'control_id': control_id}
    col = control_mission_collection(my_db)
    if projection is not None:
        return col.find_one(q, projection)
    return col.find_one(q)


def find_control_mission_by_name(
        my_db: Any,
        control_name: str,
        projection: Optional[Dict[str, Any]] = None,
):
    q = {'control_name': control_name}
    col = control_mission_collection(my_db)
    if projection is not None:
        return col.find_one(q, projection)
    return col.find_one(q)

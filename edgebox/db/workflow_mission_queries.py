"""查询 Mongo / ai-spirit 主任务表 ``work_flow_mission``（主键字段 ``mission_id``）。"""
from typing import Any, Dict, Optional

from .mongo_collections import WORK_FLOW_MISSION


def workflow_mission_collection(my_db: Any):
    return my_db.get_col(WORK_FLOW_MISSION)


def find_workflow_mission_by_mission_id(
        my_db: Any,
        mission_id: str,
        projection: Optional[Dict[str, Any]] = None,
):
    q = {'mission_id': mission_id}
    col = workflow_mission_collection(my_db)
    if projection is not None:
        return col.find_one(q, projection)
    return col.find_one(q)

"""
Logical MongoDB collection names.

wave-energy-station 布控与告警主路径统一为 ``control_manage_mission`` +
``control_device_algorithm_associate``；热成像告警（算法号 105）已与主路径对齐，
不再依赖 ``work_flow_mission`` / ``odin_business_control_manage`` 参与关联。
Mongo / wave-ai-spirit 仍可为主 ``work_flow_mission`` Schema，Constants 供跨产品引用。
"""

# --- Energy 布控主表（与 Mongo 线 odin_business_control_manage / work_flow_mission 并存）---
CONTROL_MANAGE_MISSION = "control_manage_mission"
CONTROL_DEVICE_ALGORITHM_ASSOCIATE = "control_device_algorithm_associate"

# --- Workflow 命名（算法示例、多产品线共用片段）---
WORK_FLOW_MISSION = "work_flow_mission"
WORK_FLOW_MISSION_DEVICE_ASSOCIATE = "work_flow_mission_device_associate"
WORK_FLOW_INSIGHT_MODEL_ALGORITHM_INSTANCE = "work_flow_insight_model_algorithm_instance"
WORK_FLOW_ALGORITHM_CONSTANT = "work_flow_algorithm_constant"

# --- Mongo 历史布控汇总表（热成像等路径按 mission_id 反查）---
ODIN_BUSINESS_CONTROL_MANAGE = "odin_business_control_manage"

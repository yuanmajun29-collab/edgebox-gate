import sys
sys.path.append("..")
from Utils.db import ToMongo

import Utils.edgebox_repo  # noqa: F401
from edgebox_db.mongo_collections import (
    WORK_FLOW_ALGORITHM_CONSTANT,
)

my_db = ToMongo('wavedevice')
constant_col = my_db.get_col(WORK_FLOW_ALGORITHM_CONSTANT)

new_item = {
        "algorithm_constant_id" : "001573790963861606944",
        "algorithm_constant_name" : "攀爬",        
        "algorithm_constant_num" : "13",    #算法常量
        "algorithm_constant_type" : 3,       #算法类型  1：异常行为 2：人员检测 3：AI识别模型 4：穿戴识别
        "algorithm_constant_status" : 1,
        "algorithm_level" : 3,
        "algorithm_interval" : 30,
        "algorithm_color" : "#85C12B",
        "algorithm_model" : 3,
        "algorithm_version" : "v2.0",
        "rate_num" : None
    }

my_db.insert(WORK_FLOW_ALGORITHM_CONSTANT,new_item)
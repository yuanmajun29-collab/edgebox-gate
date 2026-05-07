
from datetime import datetime
from Utils.db import ToMongo
from config import PEDESTRIAN_ALG_NUM, VEHICLE_ALG_NUM

import Utils.edgebox_repo  # noqa: F401
from edgebox_db.mongo_collections import (
    WORK_FLOW_INSIGHT_MODEL_ALGORITHM_INSTANCE,
    WORK_FLOW_MISSION_DEVICE_ASSOCIATE,
    WORK_FLOW_MISSION_HIDDEN,
)
class RoadMission:

    def __init__(self, control_id):

        self.param = {}
        self.control_id = control_id
        self.set_param()

    def set_param(self):

        self.param['mission_id'] = self.control_id
        self.param['mission_type'] = 0
        self.param['algorithm_id'] = ""
        self.param['mission_status'] = 0
        self.param['emergency_interval_time'] = 10
        self.param['emergency_music_close_method'] = "1"

        self.param['emergency_audio'] = "alarm1"
        self.param['emergency_level'] = '1'
        self.param['create_time'] = None
        self.param['organization_id'] = None

        self.param['mission_start_time'] = '[{\"time\":\"00:00:00-23:59:59\"}]'
        self.param['mission_end_time'] = '[{\"time\":\"00:00:00-23:59:59\"}]'
    
    def insert_db(self, db: ToMongo):
        col = db.get_col(WORK_FLOW_MISSION_HIDDEN)
        col.insert_one(self.param)


class RoadControlEntity:

    def __init__(self,controlId):

        self.param = {}
        self.control_id = controlId

    def set_param(self):

        self.param['control_id'] = self.control_id
        self.param['control_name'] = "路口行人检测"
        self.param['storage_time'] = 12
        self.param['storage_num'] = 10000
        self.param['device_sn'] = ""
        self.param['create_user'] = None
        self.param['create_time'] = datetime.now()
        self.param['is_record'] = 0
        self.param['organization_id'] = None

    def insert_db(self,db:ToMongo):
        col = db.get_col('odin_business_control_manage')
        col.insert_one(self.param)


class RoadAssoDevice:

    def __init__(self,deviceList,missionId):

        self.param = []
        self.device_list = deviceList
        self.mission_id = missionId
        self.set_param()

    def set_param(self):
        for device_tuple in self.device_list:
            for device_id in device_tuple:
                self.param.append({
                    "device_id": device_id,
                    "mission_id": self.mission_id,
                    "product_key": None
                })

    def insert_db(self, db: ToMongo):
        col = db.get_col(WORK_FLOW_MISSION_DEVICE_ASSOCIATE)
        for item in self.param:
            col.insert_one(item)


class RoadInstance:

    def __init__(self, control_id):

        self.param = {}
        self.control_id = control_id

    def set_param(self, algorithm_id, instance_path):
        item = dict()
        item['instance_id'] = self.control_id
        item['instance_path'] = instance_path
        item['instance_group'] = None
        item['instance_colour'] = "#C90740"
        item['algorithm_constant_num'] = algorithm_id
        item['algorithm_service_num'] = algorithm_id
        item['create_time'] = None
        item['mission_id'] = self.control_id
        item['organization_id'] = None
        item['interval_time'] = 10
        item['last_time'] = None
        item['rate_num'] = None
        item['is_use'] = 1
        item['count_limit'] = None
        item['discern_type'] = None
        item['model_id'] = None
        item['time_range_num'] = None
        return item

    def set_param_pedestrian(self):
        algorithm_id = PEDESTRIAN_ALG_NUM
        instance_path = '路口行人检测'
        return self.set_param(algorithm_id, instance_path)

    def set_param_vehicle(self):
        algorithm_id = VEHICLE_ALG_NUM
        instance_path = '车辆检测'
        return self.set_param(algorithm_id, instance_path)

    def insert_db(self, db: ToMongo):
        col = db.get_col(WORK_FLOW_INSIGHT_MODEL_ALGORITHM_INSTANCE)
        col.insert_one(self.set_param_pedestrian())
        col.insert_one(self.set_param_vehicle())



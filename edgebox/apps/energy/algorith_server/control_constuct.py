import json

import Utils.edgebox_repo  # noqa: F401
from edgebox.db.mission_queries import control_mission_collection
from edgebox.db.mongo_collections import (
    CONTROL_DEVICE_ALGORITHM_ASSOCIATE,
    WORK_FLOW_ALGORITHM_CONSTANT,
)
from .AgreementBuilder import pack_init_agreement,pack_3004_agreement
from Utils.db import ToMongo
from .Algorithmutil import constant_to_str
from personnel.personnel_route import FaceFeatureDBAPI
import Utils.logger as logger

mainlogger = logger.getLogger('main')


def switch_roi(roi_item):
    '''
    数据库查到的转换成需要返回的格式；
    '''
    if not roi_item:
        return
    result={}
    roi_info_item = json.loads(roi_item['roi_area_info'])
    #print("---roi_info_item---",roi_info_item)
    result["roi_id"] = roi_item.get("roi_id")
    result["roi_type"] = roi_item.get("roi_type")
    result["roi_name"] = roi_item.get("roi_name")
    result['source_width'] = roi_info_item['sourceWidth']
    result['source_height'] = roi_info_item['sourceHeight']
    result['top_y'] = roi_info_item.get("top")
    result['left_x'] = roi_info_item.get("left")
    result['enter'] = roi_info_item.get("enter")
    result['leave'] = roi_info_item.get("leave")
    result['passby'] = roi_info_item.get("passby")
    result['points'] = []
    origin_points = roi_info_item['points']
    for point in origin_points:
        result['points'].append(point['x'])
        result['points'].append(point['y'])
    return result

def mission_devices(items):
    #形成item与索引配对的字典
    result = {}
    if items:
        for i,element in enumerate(items):
            device_id = element['device_id']
            result[device_id] = i 
    return  result

def get_camera_url(cameraItems):
    url = cameraItems.get("stream_url")
    if not url:
        url = cameraItems.get("main_url")
    return url

class ControlSqlHelperv2():
    def __init__(self, context,db_mongo:ToMongo):
        self.context = context
        self.my_db = db_mongo
 
    def build_controls_message(self):
        mission_col = control_mission_collection(self.my_db)
        asso_col = self.my_db.get_col(CONTROL_DEVICE_ALGORITHM_ASSOCIATE)
        camera_coll = self.my_db.get_col('odin_device_camera_edit')
        roi_col = self.my_db.get_col('odin_device_roi_area_record')
        constant_col = self.my_db.get_col(WORK_FLOW_ALGORITHM_CONSTANT)
        items = []
        device_asso_alg = {}
        controlMissons = mission_col.find({'mission_status':0})
        if controlMissons:
            for controlItem in controlMissons: 
                mission_id = controlItem['control_id']
                time_list = controlItem.get("emergency_response_time")
                missionDevices = asso_col.distinct("camera_id",{'control_id':mission_id})
                for device_id in missionDevices:
                    devices = mission_devices(items)
                    item = {}
                    cameraItems = camera_coll.find_one({'camera_id':device_id})
                    if not cameraItems:
                        continue
                    item['url'] = get_camera_url(cameraItems)
                    item['device_id'] = device_id
                    match_models = asso_col.distinct("algorithm_constant_id",{'control_id':mission_id})

                    if device_id in devices.keys():                        
                        index = devices[device_id]
                        flag = True
                    else:
                        flag = False
                
                    constant_list = []
                    algorithm_list = []
                    for algorithm_constant_id in match_models:
                        try:
                            iter = {}
                            match_model = constant_col.find_one({"algorithm_constant_id":algorithm_constant_id})
                            service_num = match_model['algorithm_service_num']
                            constant_num = match_model['algorithm_constant_num']
                            constant_list.append(constant_num)
                            roi_items = roi_col.find({"algorithm_constant_id":algorithm_constant_id,
                                                    "camera_id":device_id})
                            iter["algorithm"] = constant_to_str(constant_num)
                            if not iter["algorithm"]:
                                continue
                        except:
                            continue
                        #只有睡岗和离岗有rate_num
                        if constant_num in ['113','114']:
                            try:
                                iter["rate_num"] = match_model['rate_num']  
                            except:
                                iter["rate_num"] = None
                        else:
                            iter["rate_num"] = None
                        algorithm_interval = match_model.get("algorithm_interval")
                        iter["duration_num"] = int(algorithm_interval) if algorithm_interval else None
                        iter["roi_list"] = []
                        for roi_item in roi_items:
                        #    roi_alg_list = roi_item['algorithm_constant_id'].split(',')
                            iter['roi_list'].append(switch_roi(roi_item))
                        iter["person_list"] = []
                        iter['time_list'] = json.loads(time_list)
                       
                        alg_list = device_asso_alg.get(device_id)
                        if not alg_list:
                            device_asso_alg[device_id] = []
                            device_asso_alg[device_id].append(service_num)
                            algorithm_list.append(iter)
                        elif service_num not in alg_list:
                            device_asso_alg[device_id].append(service_num)
                            if flag:
                                items[index]['algorithm_list'].append(iter)
                            else:
                                algorithm_list.append(iter)

                    if not flag:
                        algorithm_str = constant_to_str(constant_list)
                        if not algorithm_str:
                            continue
                        item['algorithm']=algorithm_str
                        item['algorithm_list']=algorithm_list
                        items.append(item)
                    else:
                        alg_param = items[index]['algorithm']
                        algorithm_str = constant_to_str(constant_list,alg_init=alg_param)
                        if not algorithm_str:
                            continue
                        items[index]['algorithm'] = algorithm_str


        missons_message = json.dumps(items)
        message = pack_init_agreement( missons_message)

        return message
    
    def build_cameras_message(self):
        camera_list = self.my_db.get_col('odin_device_camera_edit').find()
        items=[]
        if camera_list:
            for camera_item in camera_list:
                item = {}
                item['url'] = get_camera_url(camera_item)
                item['device_id'] = camera_item['camera_id']
                item['algorithm'] = None
                item['algorithm_list'] = []
                items.append(item)   
        camera_message = json.dumps(items)
        message = pack_3004_agreement(camera_message)

        return message

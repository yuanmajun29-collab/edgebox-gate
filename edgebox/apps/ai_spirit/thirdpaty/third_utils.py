
from Utils.db import ToMongo
from system.system_misc import database_to_dict
from system.sys_config import *

import Utils.edgebox_repo  # noqa: F401
from edgebox.db.mongo_collections import (
    WORK_FLOW_ALGORITHM_CONSTANT,
)

class ThirdPartyOutputService:

    def __init__(self):

        self.my_db = ToMongo('wavedevice')

        self.type = 2
        self.default_organization_id = "001611544223344645607"
        self.default_create_user = "admin"
        self.default_mission_time = "[{\"time\":\"00:00:00-23:59:59\"}]"
        self.default_mission_type = 4
        self.default_mission_status = 0
        self.default_is_use = 1
        self.default_storage_time = 12
        self.default_storage_num = 10000

    def validAuthenticationCode(self,authenticationCode):

        base_col = self.my_db.get_col('public_dict_baseinfo')
        query = {'public_dict_type':self.type}
        base_entity = base_col.find_one(query)
        if base_entity:
            PublicDictParam1 = base_entity.get('public_dict_param1',None)
            if PublicDictParam1:
                if PublicDictParam1 == authenticationCode:
                    return True
        return False


def get_camera_info(my_db:ToMongo):

    camera_col = my_db.get_col("odin_device_camera_edit")
    associate_coll = my_db.get_col('odin_device_device_position_associate')
    position_coll = my_db.get_col('odin_device_position')

    camera_info = []
    format_pattern = '%Y-%m-%d %H:%M:%S.%f'
    res = camera_col.find({},{'_id':0})
    for data in res:
        item = database_to_dict(data,camerakeys_database,camerakeys_server)    
        item['cameraCreateTime'] = item['cameraCreateTime'].strftime(format_pattern) if item['cameraCreateTime'] else None
        item['cameraUpdateTime'] = item['cameraUpdateTime'].strftime(format_pattern) if item['cameraUpdateTime'] else None

        device_id = data['camera_id']
        asso_item = associate_coll.find_one({'device_id':device_id})
        position_id = asso_item.get('position_id',None)
        position_item = position_coll.find_one({'position_id':position_id})
        position_info = database_to_dict(position_item,positionkeys_database,positionkeys_web)
        item.update(position_info)
        camera_info.append(item)
    return camera_info


def get_equips_info(my_db:ToMongo):
    equip_col = my_db.get_col("odin_device_equip")
    res = equip_col.find({},{'_id':0})
    equip_info = []
    for data in res:
        item = database_to_dict(data,equip_database,equip_web)
        del item['createTime']
        del item['updateTime']
        equip_info.append(item)

    return equip_info

def get_constant_info(my_db:ToMongo):
    constant_col = my_db.get_col(WORK_FLOW_ALGORITHM_CONSTANT)
    res = constant_col.find({},{'_id':0})
    constant_info = []
    for data in res:
        item = database_to_dict(data,constant_database,constant_web)
        constant_info.append(item)

    return constant_info

def get_sound_info(my_db:ToMongo):
    sound_col = my_db.get_col("odin_device_sound")
    res = sound_col.find({},{'_id':0})
    sound_info = []
    for data in res:
        item = database_to_dict(data,sound_database,sound_web)
        del item['createTime']
        sound_info.append(item)

    return sound_info

def get_roi_info(my_db:ToMongo,device_id):
    '''
    查询摄像头关联的roi信息
    '''
    roi_col = my_db.get_col('odin_device_roi_area_record')
    query = {'camera_id':device_id}
    roi_items = roi_col.find(query)
    roi_info = []
    for roi_item in roi_items:
        item = database_to_dict(roi_item,roi_database,roi_server)

        roi_need = {'roiName':item['roiName'],
                    'algorithmConstantId':item['algorithmConstantId'],
                    'roiAreaInfo':item['roiAreaInfo']}
        roi_info.append(roi_need)
    return roi_info

def get_control_info(my_db:ToMongo):
    control_col = my_db.get_col('odin_business_control_manage')
    control_items = control_col.find({},{'_id':0})
    control_info = []
    for control_item in control_items:
        item = database_to_dict(control_item,control_database,control_web)
        del item['createTime']
        control_info.append(item)
    return control_info
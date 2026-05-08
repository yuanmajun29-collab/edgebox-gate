from datetime import datetime

from flask import Blueprint, request, jsonify, app, current_app
from Utils.utils import *
import  uuid
from Utils.db import *
from Utils.jwt_verify import *
from system.system_misc import database_to_dict
from system.sys_config import constant_database,constant_web

import Utils.edgebox_repo  # noqa: F401
from edgebox.db.workflow_mission_queries import workflow_mission_collection
from edgebox.db.mongo_collections import (
    WORK_FLOW_ALGORITHM_CONSTANT,
    WORK_FLOW_INSIGHT_MODEL_ALGORITHM_INSTANCE,
    WORK_FLOW_MISSION_DEVICE_ASSOCIATE,
)

bp = Blueprint("algconstant",__name__, url_prefix='/net-web')

# 布控任务
@bp.route('/algorithmConstant/queryAlgorithmList', methods=['GET','POST'])
@login_required
def queryAlgorithmList():

    my_db = ToMongo("wavedevice")
    constant_coll = my_db.get_col(WORK_FLOW_ALGORITHM_CONSTANT)
    res = {'穿戴(A1)':[],'手持(B1)':[],'危险行为(C1)':[],'越界行为(C2)':[],'违规行为(C3)':[],'消防(D1)':[],'设备(E1)':[],'人脸(F1)':[],'摄像机内置算法(G1)':[]}
    index_dict = {'穿戴(A1)':1,'手持(B1)':2,'危险行为(C1)':3,'越界行为(C2)':4,'违规行为(C3)':5,'消防(D1)':6,'设备(E1)':7,'人脸(F1)':8,'摄像机内置算法(G1)':9}

    keys = res.keys()

    for key in keys:
        index = index_dict[key]
        items = constant_coll.find({'algorithm_constant_type':index})
        for item in items:
            item = database_to_dict(item,constant_database,constant_web)
            item['audioValue'] = item['algorithmSoundFile']
            res[key].append(item)
    response = set_success_result()
    response['constantMaps'] = res    
    return  jsonify( response)

@bp.route('/algorithmConstant/updateAlgorithm', methods=['GET','POST'])
@login_required
def updateAlgorithm():
    params = request.get_json()
    my_db = ToMongo('wavedevice')

    constantId = params.get('algorithmConstantId',None)
    algorithmConstantName = params.get('algorithmConstantName',None)
    algorithmColor = params.get('algorithmColor',None)
    algorithmConstantNum = params.get('algorithmConstantNum',None)
    emergencyIntervalTime = params.get('emergencyIntervalTime',None)
    algorithmLevel = params.get('algorithmLevel',None)
    modelName = params.get('modelName',None)
    rateNum = params.get('rateNum',None)

    audioFile = params.get('audioFile',None)
    audioType = params.get('audioType',None)
    audioValue = params.get('audioValue',None)

    rate_num = float(rateNum) if rateNum else None
    query = {'algorithm_constant_id':constantId}

    if rate_num:
        constant_col = my_db.get_col(WORK_FLOW_ALGORITHM_CONSTANT)    
        mission_col = workflow_mission_collection(my_db)  
        origin_item = constant_col.find_one(query)
        rateNum_ori = origin_item['rate_num']
        constant_num = origin_item['algorithm_constant_num']
        mission_query = {'mission_status':0,'algorithm_id':{'$regex':constant_num}}
        mission_item = mission_col.find_one(mission_query)

    if audioType == '1':
        algorithm_sound_file = audioValue
    elif audioType == '2':
        algorithm_sound_file = audioFile

    item = {'algorithm_constant_name':algorithmConstantName,
            'algorithm_color':         algorithmColor,
            'algorithm_level':         int(algorithmLevel),
            'algorithm_interval':      int(emergencyIntervalTime),
            'rate_num':                rate_num,
            'algorithm_sound_type':    int(audioType),
            'algorithm_sound_file':    algorithm_sound_file}
    my_db.update(WORK_FLOW_ALGORITHM_CONSTANT,query,{'$set':item})

    if rate_num and mission_item and rateNum_ori != rate_num:
        from algorith_server.AlgorithServer_new import SenderThread
        sender = SenderThread( current_app.app_context() )
        sender.send_reboot_message()

    response = set_success_result()  
    return  jsonify( response)

@bp.route('/algorithmConstant/queryAllCamera', methods=['GET','POST'])
#@login_required
def queryAllCamera():
    params = request.get_json()
    my_db = ToMongo('wavedevice')
    instance_col = my_db.get_col(WORK_FLOW_INSIGHT_MODEL_ALGORITHM_INSTANCE)
    cam_asso_col = my_db.get_col(WORK_FLOW_MISSION_DEVICE_ASSOCIATE)
    cam_edit_col = my_db.get_col('odin_device_camera_edit')
    position_col = my_db.get_col('odin_device_position')
    constant_col = my_db.get_col(WORK_FLOW_ALGORITHM_CONSTANT)

    page = params.get('page',None)
    pageSize = params.get('pageSize',None)
    algorithmConstantId = params.get('algorithmConstantId',None)

    constant_item = constant_col.find_one({'algorithm_constant_id':algorithmConstantId})
    constant_num = constant_item['algorithm_constant_num']
    query = {'algorithm_constant_num':constant_num}

    mission_list = instance_col.distinct('mission_id',query)
    device_list = cam_asso_col.distinct('device_id',{'mission_id':{'$in':mission_list}})
    
    cameraEntity = []
    if device_list:
        for device_id in device_list:
            item = {}
            query = {'camera_id':device_id}
            caminfo = cam_edit_col.find_one(query)
            position_info = position_col.find_one(query)
            item['cameraIp'] = caminfo['camera_ip']
            item['cameraName'] = caminfo['camera_name']
            item['cameraStatus'] = caminfo['camera_status']
            item['detailedLocation'] = position_info['position_province'] + position_info['position_area']
            item['positionDesc'] = position_info['position_desc']
            cameraEntity.append(item)

    response = set_success_result()  
    response['cameraEntity'] =cameraEntity
    return  jsonify( response)
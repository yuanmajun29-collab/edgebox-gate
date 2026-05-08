from flask import Blueprint,request, jsonify,current_app,send_file

import io,zipfile,xlwt
import Utils.edgebox_repo  # noqa: F401
from edgebox.db.mongo_collections import (
    CONTROL_DEVICE_ALGORITHM_ASSOCIATE,
    CONTROL_MANAGE_MISSION,
    WORK_FLOW_ALGORITHM_CONSTANT,
)
from edgebox.db.mission_queries import (
    control_mission_collection,
    find_control_mission_by_control_id,
    find_control_mission_by_name,
)
from Utils.opencv_utils import draw_frame

from Utils.db import *
from Utils.jwt_verify import *
from Utils.Utils import *
from Utils.datacfg import *
from config import MODEL_DICT,EMERGENCY_IMG_PATH
import Utils.logger as logger

bp = Blueprint("control", __name__, url_prefix='/net-web')

mainlogger = logger.getLogger('main')


@bp.route('/controltask/queryControlTaskList', methods=['GET', 'POST'])
@login_required
def queryControlTaskList():
    '''
    接口描述: 查询布控任务
    '''
    params = request.get_json()
    page = params.get('page', None)
    pageSize = params.get('pageSize', None)
    sortBy = params.get('sortBy', None)
    sortType = params.get('sortType', None)
    missionStatus = params.get('missionStatus', None)  # 任务状态
    groupType = params.get('groupType', None)  # 列表分组类型  1、布控任务  2、按模型  3、按摄像头
    controlName = params.get('controlName', None)  # 布控任务名称

    my_db = ToMongo("wavedevice")
    generate_log(request, db=my_db)

    asso_col = my_db.get_col(CONTROL_DEVICE_ALGORITHM_ASSOCIATE)

    query = {}
    if missionStatus != None and missionStatus != "":
        query["mission_status"] = missionStatus
    if controlName:
        query["control_name"] = {"$regex": controlName}

    num, page, pageSize = get_page_num(page, pageSize)

    controlInfoVoList = []
    if not groupType:
        groupType = "1" 
    if groupType == "1":
        # 按布控任务分组
        mission_col = control_mission_collection(my_db)
        items = mission_col.find(query).skip(num).limit(pageSize)
        for item in items:
            newItem = database_to_dict(item, mission_database, mission_web)
            controlId = newItem.get("controlId")
            qurey_control = {"control_id": controlId}
            algList = asso_col.distinct("algorithm_constant_id", qurey_control)
            camList = asso_col.distinct("camera_id", qurey_control)
            newItem["cameraNum"] = len(camList)
            newItem["algorithNum"] = len(algList)
            newItem["createTime"] = getTimeStamp(newItem["createTime"])
            newItem["updateTime"] = getTimeStamp(newItem["updateTime"])
            controlInfoVoList.append(newItem)

    elif groupType == "2":
        # 按算法模型分组
        constant_col = my_db.get_col(WORK_FLOW_ALGORITHM_CONSTANT)
        constantIdList = asso_col.distinct("algorithm_constant_id")
        items = constant_col.find({"algorithm_constant_id": {"$in": constantIdList}})
        for item in items:
            newItem = dict()
            algId = item.get("algorithm_constant_id")
            algName = item.get("algorithm_constant_name")
            algNum = item.get("algorithm_constant_num")
            newItem["algorithmConstantId"] = algId
            newItem["algorithmConstantName"] = algName
            newItem["algorithmConstantNum"] = algNum
            controlInfoVoList.append(newItem)

    elif groupType == "3":
        # 按摄像头分组
        camera_col = my_db.get_col('odin_device_camera_edit')
        camList = asso_col.distinct("camera_id")
        items = camera_col.find({"camera_id": {"$in": camList}})
        for item in items:
            newItem = database_to_dict(item, camerakeys_database, camerakeys_web)
            controlInfoVoList.append(newItem)

    response = set_success_result()
    response["controlInfoVoList"] = controlInfoVoList
    return jsonify(response)

@bp.route('/control/queryControlTaskList', methods=['GET','POST'])
@login_required
def queryControlTaskList2():
    '''
    接口说明：根据任务id查询任务关联的数据
    '''

    params = request.get_json()
    controlIds = params.get('controlIds',None)
    
    my_db = ToMongo('wavedevice')
    generate_log(request,db=my_db)
    query = {"control_id":{"$in":controlIds}} 
    asso_col = my_db.get_col(CONTROL_DEVICE_ALGORITHM_ASSOCIATE)
    mission_col = control_mission_collection(my_db)
    cam_col = my_db.get_col('odin_device_camera_edit')
    constant_col = my_db.get_col(WORK_FLOW_ALGORITHM_CONSTANT)

    control_items = mission_col.find(query)
    controlInfoVoList = []
    for control_item in control_items:
        item = {}
        controlId = control_item['control_id']
        item['controlId'] = controlId
        item['controlName'] = control_item['control_name']
        item['createTime'] = int(control_item['create_time'].timestamp())*1000
        item['storageNum'] = control_item['storage_num']
        item['storageTime'] = control_item['storage_time']
        item['emergencyResponseTime'] = control_item['emergency_response_time']
        item['missionStatus'] = control_item['mission_status']
        item['emergencyAudio'] = control_item['emergency_audio']
        item['emergencyLevel'] = control_item.get('emergency_level')

        asso_cameras = asso_col.distinct("camera_id",{"control_id":controlId})
        device_associate = cam_col.find({'camera_id':{'$in':asso_cameras}})
        asso_algs = asso_col.distinct("algorithm_constant_id",{"control_id":controlId})
        algorithm_associate = constant_col.find({'algorithm_constant_id':{'$in':asso_algs}})

        item['algorithmCount'] = len(asso_algs)  #绑定的算法数
        item['deviceCount'] = len(asso_cameras)  #绑定的摄像头数
        item['deviceIdList'] = asso_cameras

        item['deviceList'] = []
        for device_item in device_associate:
            ditem={}
            ditem['deviceId'] = device_item['camera_id']
            ditem['missionId'] = controlId
            ditem['productKey'] = device_item['product_key']
            item['deviceList'].append(ditem)

        item['instanceList']=[]
        for algorithm_item in algorithm_associate:
            alitem = {}
            alitem['algorithmConstantNum'] = algorithm_item['algorithm_constant_num']
            alitem['controlId'] = controlId
            alitem['isUse'] = 1
            alitem['missionId'] = controlId
        #    alitem['organizationId'] = algorithm_item['organization_id']
            item['instanceList'].append(alitem)

        controlInfoVoList.append(item)

    response = set_success_result()
    response['list'] = controlInfoVoList   
    return response

@bp.route('/controltask/queryControlTaskInfo', methods=['GET', 'POST'])
@login_required
def queryControlTaskInfo():
    '''
    编辑布控任务时,查询详细的任务信息
    '''
    param = request.get_json()
    controlId = param.get('controlId')

    my_db = ToMongo("wavedevice")
    mission_col = control_mission_collection(my_db)
    asso_col = my_db.get_col(CONTROL_DEVICE_ALGORITHM_ASSOCIATE)
    camera_col = my_db.get_col('odin_device_camera_edit')
    constant_col = my_db.get_col(WORK_FLOW_ALGORITHM_CONSTANT)

    query = {"control_id": controlId}
    mission_item = mission_col.find_one(query)
    mission_item = database_to_dict(mission_item, mission_database, mission_web)

    camerIdList = asso_col.distinct("camera_id", query)
    algIdList = asso_col.distinct("algorithm_constant_id", query)

    cameraItems = camera_col.find({"camera_id": {"$in": camerIdList}})
    mission_item["deviceList"] = []
    for item in cameraItems:
        newItem = database_to_dict(item, camerakeys_database, camerakeys_web)
        mission_item["deviceList"].append(newItem)

    algItems = constant_col.find({"algorithm_constant_id": {"$in": algIdList}})
    mission_item["algorithmList"] = []
    for item in algItems:
        newItem = database_to_dict(item, constant_database, constant_web)
        mission_item["algorithmList"].append(newItem)

    deviceEquInfo = mission_item['deviceEquInfo']
    if deviceEquInfo:
        col = my_db.get_col('odin_dynamic_audio')
        for i,dev in enumerate(deviceEquInfo):
            equipType = dev['equipType']
            equipId = dev['equipId']
            if equipType == 2:
                item = col.find_one({'device_id':equipId})
                equipName = item.get('device_name') if item else None 
                dev['equipName'] = equipName
    #        deviceEquInfo[i] = dev

    response = set_success_result()
    response = dict(mission_item, **response)
    return jsonify(response)


@bp.route('/vidicon/getAlgorithmList', methods=['GET', 'POST'])
@login_required
def getAlgorithmList():
    '''
    接口名称：获取算法服务器支持算法模型列表
    '''
    params = request.get_json()
    searchChoose = params.get("searchChoose", None)

    query = {}
    if searchChoose:
        query['algorithm_constant_name'] = {"$regex": searchChoose}

    my_db = ToMongo("wavedevice")
    algorithm_coll = my_db.get_col(WORK_FLOW_ALGORITHM_CONSTANT).find(query)
    items = []
    for algorithm in algorithm_coll:
        items.append(algorithm['algorithm_constant_num'])
    response = {}
    response['requestId'] = uuid.uuid4().hex
    response['requestStatus'] = "SUCCESS"
    response['timeUsed'] = 40
    response['algorithmList'] = items
    return jsonify(response)


@bp.route('/controltask/addControlTask', methods=['GET', 'POST'])
@login_required
def addControlTask():
    '''
    接口描述: 新增布控任务
    '''
    params = request.get_json()
    controlName = params.get('controlName', None)  # 布控任务名称
    addMode = params.get('addMode', None)  # 任务批量模式
    algorithmConstantIdList = params.get('algorithmConstantIdList', None)  # 关联的算法
    cameraIdList = params.get('cameraIdList', None)  # 关联的摄像头
    storageNum = params.get('storageNum', None)
    storageTime = params.get('storageTime', None)
    emergencyAudio = params.get('emergencyAudio', None)
    emergencyMusicCloseMethod = params.get('emergencyMusicCloseMethod', None)
    missionStatus = params.get('missionStatus', None)
    emergencyResponseTime = params.get('emergencyResponseTime', None)  # 布控时间
    deviceEquInfo = params.get('deviceEquInfo', None)

    if not algorithmConstantIdList or not cameraIdList:
        error_response = set_fail_result()
        error_response["errorCodeDesc"] = "关联的摄像头和算法不能为空"
        return jsonify(error_response)

    my_db = ToMongo("wavedevice")
    controlId = uuid.uuid4().hex
    now = datetime.now()
    user_item = get_user_item(request, my_db)
    user_name = user_item.get("user_real_name")
    item = {
        "control_id": controlId,
        "control_name": controlName,
        "storage_time": int(storageTime),
        "storage_num": int(storageNum),
        "emergency_audio": emergencyAudio,
        "emergency_music_close_method": emergencyMusicCloseMethod,
        "emergency_response_time": emergencyResponseTime,
        "mission_status": int(missionStatus),
        "device_equ_info": deviceEquInfo,
        "add_mode": addMode,
        "create_time": now,
        "update_time": now,
        "update_user": user_name
    }
    my_db.insert(CONTROL_MANAGE_MISSION, item)

    for algId in algorithmConstantIdList:
        for cameraId in cameraIdList:
            newItem = {
                "control_id": controlId,
                "algorithm_constant_id": algId,
                "camera_id": cameraId
            }
            my_db.insert(CONTROL_DEVICE_ALGORITHM_ASSOCIATE, newItem)

    #发送算法重启指令
    from algorith_server.AlgorithServer_v2 import SenderThread
    sender = SenderThread( current_app.app_context() )
    sender.send_reboot_message()

    response = set_success_result()
    return jsonify(response)


@bp.route('/controltask/modifyControlTask', methods=['GET', 'POST'])
@login_required
def modifyControlTask():
    '''
    接口描述: 编辑布控任务
    '''
    params = request.get_json()
    controlName = params.get('controlName', None)  # 布控任务名称
    controlTaskId = params.get('controlId', None)  # 布控任务标识
    addMode = params.get('addMode', None)  # 任务批量模式
    algorithmConstantIdList = params.get('algorithmConstantIdList', None)  # 关联的算法
    cameraIdList = params.get('cameraIdList', None)  # 关联的摄像头
    storageNum = params.get('storageNum', None)
    storageTime = params.get('storageTime', None)
    emergencyAudio = params.get('emergencyAudio', None)
    emergencyMusicCloseMethod = params.get('emergencyMusicCloseMethod', None)
    missionStatus = params.get('missionStatus', None)
    emergencyResponseTime = params.get('emergencyResponseTime', None)  # 布控时间
    deviceEquInfo = params.get('deviceEquInfo', None)

    if not algorithmConstantIdList or not cameraIdList:
        error_response = set_fail_result()
        error_response["errorCodeDesc"] = "关联的摄像头和算法不能为空"
        return jsonify(error_response)

    my_db = ToMongo("wavedevice")

    now = datetime.now()
    user_item = get_user_item(request, my_db)
    user_name = user_item.get("user_real_name")

    item = {
        "control_name": controlName,
        "storage_time": int(storageTime),
        "storage_num": int(storageNum),
        "emergency_audio": emergencyAudio,
        "emergency_music_close_method": emergencyMusicCloseMethod,
        "emergency_response_time": emergencyResponseTime,
        "mission_status": missionStatus,
        "device_equ_info": deviceEquInfo,
        "add_mode": addMode,
        "update_time": now,
        "update_user": user_name
    }
    query = {"control_id": controlTaskId}
    my_db.update(CONTROL_MANAGE_MISSION, query, {"$set": item})

    my_db.delete(CONTROL_DEVICE_ALGORITHM_ASSOCIATE, query, is_one=False)
    for algId in algorithmConstantIdList:
        for cameraId in cameraIdList:
            newItem = {
                "control_id": controlTaskId,
                "algorithm_constant_id": algId,
                "camera_id": cameraId
            }
            my_db.insert(CONTROL_DEVICE_ALGORITHM_ASSOCIATE, newItem)

    #发送算法重启指令
    from algorith_server.AlgorithServer_v2 import SenderThread
    sender = SenderThread( current_app.app_context() )
    sender.send_reboot_message()

    response = set_success_result()
    return jsonify(response)


@bp.route('/controltask/deleteControlTask', methods=['GET', 'POST'])
@login_required
def deleteControlTask():
    '''
    接口描述:删除布控任务
    '''
    params = request.get_json()
    controlID = params.get('controlId', None)

    my_db = ToMongo("wavedevice")
    query = {"control_id": controlID}
    my_db.delete(CONTROL_MANAGE_MISSION, query)
    my_db.delete(CONTROL_DEVICE_ALGORITHM_ASSOCIATE, query, is_one=False)

    #发送算法重启指令
    from algorith_server.AlgorithServer_v2 import SenderThread
    sender = SenderThread( current_app.app_context() )
    sender.send_reboot_message()
    
    response = set_success_result()
    return jsonify(response)


@bp.route('/controltask/modifyControlTaskIsActive', methods=['GET', 'POST'])
@login_required
def modifyControlTaskIsActive():
    '''
    接口描述:布控任务状态开关
    '''
    params = request.get_json()
    controlID = params.get('controlId', None)
    switchOperation = params.get('switchOperation', None)  # 布控开关 0关1开

    my_db = ToMongo('wavedevice')
    generate_log(request, db=my_db)
    item = find_control_mission_by_control_id(my_db, controlID)

    if item:
        my_db.update(CONTROL_MANAGE_MISSION, {"control_id": controlID}, {'$set': {'mission_status': switchOperation}})

    #发送算法重启指令
    from algorith_server.AlgorithServer_v2 import SenderThread
    sender = SenderThread( current_app.app_context() )
    sender.send_reboot_message()

    response = set_success_result()
    return response


@bp.route('/controltask/queryRelatedCameras', methods=['GET', 'POST'])
@login_required
def queryRelatedCameras():
    '''
    接口描述:查询布控任务时,对应算法关联的摄像机
    '''
    params = request.get_json()
    algorithmConstantId = params.get('algorithmConstantId', None)
    queryType = params.get('type', None)  # type=1 查询绑定该算法的摄像机  type=2 查询未绑定该算法的摄像机

    my_db = ToMongo('wavedevice')
    camera_coll = my_db.get_col('odin_device_camera_edit')
    camera_alg_coll = my_db.get_col(CONTROL_DEVICE_ALGORITHM_ASSOCIATE)
    position_coll = my_db.get_col('odin_device_position')

    try:
        camera_list = []
        if queryType == "2":
            relatedCameras = camera_alg_coll.distinct("camera_id", {"algorithm_constant_id": algorithmConstantId})
            items = camera_coll.find({"camera_id": {"$nin": relatedCameras}})
            total = items.count()
            size = 10
            pages = total//size +1
            for item in items:
                newItem = database_to_dict(item, camerakeys_database, camerakeys_web)
                cameraId = newItem.get("cameraId")
                query = {"camera_id": cameraId}
                position_info = position_coll.find_one(query)
                position_item = database_to_dict(position_info, positionkeys_database, positionkeys_web)
                data = dict(newItem, **position_item)
                data['serviceId'] = ''
                data['serviceName'] = ''
                data['serviceState'] = ''
                data['serverIp'] = ''
                data['videotape'] = ''
                camera_list.append(data)

        elif queryType == "1":
            assoItems = camera_alg_coll.find({"algorithm_constant_id": algorithmConstantId})
            mission_col = control_mission_collection(my_db)
            total = assoItems.count()
            size = 10
            pages = total//size +1
            for item in assoItems:
                cameraId = item.get("camera_id")
                controlId = item.get("control_id")
                query_camera = {"camera_id": cameraId}
                query_control = {"control_id": controlId}
                cameraItem = camera_coll.find_one(query_camera)
                missionItem = mission_col.find_one(query_control)
                if not cameraItem or not missionItem:
                    continue
                cameraItem = database_to_dict(cameraItem, camerakeys_database, camerakeys_web)
                position_info = position_coll.find_one(query_camera)
                position_item = database_to_dict(position_info, positionkeys_database, positionkeys_web)

                data = dict(cameraItem, **position_item)
                controlName = missionItem.get("control_name")
                controlId = missionItem.get("control_id")
                missionStatus = missionItem.get("mission_status")
                data["controlName"] = controlName
                data["controlId"] = controlId
                data["missionStatus"] = missionStatus
                camera_list.append(data)
    except Exception as e:
        mainlogger.exception(e)

    PageQueryRepVo = {   'list': camera_list,
                          'pages': pages,
                          'size': 10,
                          'total': total}

    response = set_success_result()
    response["PageQueryRepVo"] = PageQueryRepVo
    return response


@bp.route('/controltask/queryRelateAlg', methods=['GET', 'POST'])
@login_required
def queryRelateAlg():
    '''
    接口描述:多算法添加时，查询未关联的算法
    '''
    params = request.get_json()
    cameraId = params.get('cameraId', None)
    queryType = params.get('type', None)

    my_db = ToMongo('wavedevice')
    camera_alg_coll = my_db.get_col(CONTROL_DEVICE_ALGORITHM_ASSOCIATE)
    constant_col = my_db.get_col(WORK_FLOW_ALGORITHM_CONSTANT)

    response = set_success_result()

    algModelDict = MODEL_DICT.copy()
    tempList = algModelDict.values()

    tempContent = [[],[],[],[],[],[],[],[],[]]
    res = dict(zip(tempList, tempContent))
    
    if queryType == "2":
        relatedAlg = camera_alg_coll.distinct("algorithm_constant_id", {"camera_id": cameraId})
        items = constant_col.find({"algorithm_constant_id": {"$nin": relatedAlg}})       
        for item in items:
            newItem = database_to_dict(item, constant_database, constant_web)
            algorithmConstantType = newItem.get("algorithmConstantType")
            try:
                key = algModelDict[int(algorithmConstantType)]
                res[key].append(newItem)
            except Exception as e:
                mainlogger.exception(e)

    elif queryType == "1":
        assoItems = camera_alg_coll.find({"camera_id": cameraId})
        mission_col = control_mission_collection(my_db)
        for item in assoItems:
            controlId = item.get("control_id")
            algorithm_constant_id = item.get("algorithm_constant_id")
            query_alg = {"algorithm_constant_id": algorithm_constant_id}
            query_control = {"control_id": controlId}
            algorithmItem = constant_col.find_one(query_alg)
            missionItem = mission_col.find_one(query_control)
            if not algorithmItem or not missionItem:
                continue
            newItem = database_to_dict(algorithmItem, constant_database, constant_web)
            algorithmConstantType = newItem.get("algorithmConstantType")
            controlName = missionItem.get("control_name")
            missionStatus = missionItem.get("mission_status")
            iter = {
                    "controlName": controlName,
                    "controlId": controlId,
                    "missionStatus": missionStatus}
            data = dict(newItem,**iter)
            try:
                key = algModelDict[int(algorithmConstantType)]
                res[key].append(data)
            except Exception as e:
                mainlogger.exception(e)
    response["constantMaps"] = res
    return response

@bp.route('/controltask/queryTaskAlg', methods=['GET', 'POST'])
@login_required
def queryTaskAlg():
    '''
    接口描述:编辑多算法任务时，返回摄像头未关联+已绑定算法
    '''
    params = request.get_json()
    cameraId = params.get('cameraId', None)
    controlId = params.get('controlId', None)

    my_db = ToMongo('wavedevice')
    camera_alg_coll = my_db.get_col(CONTROL_DEVICE_ALGORITHM_ASSOCIATE)
    constant_col = my_db.get_col(WORK_FLOW_ALGORITHM_CONSTANT)

    response = set_success_result()

    algModelDict = MODEL_DICT.copy()
    tempList = algModelDict.values()

    tempContent = [[],[],[],[],[],[],[],[],[]]
    res = dict(zip(tempList, tempContent))
    
    query = {"camera_id": cameraId,"control_id":{"$ne":controlId}}
    relatedAlg = camera_alg_coll.distinct("algorithm_constant_id",query)
    mainlogger.info("relatedAlg:%s"%relatedAlg)
    items = constant_col.find({"algorithm_constant_id": {"$nin": relatedAlg}})       
    for item in items:
        newItem = database_to_dict(item, constant_database, constant_web)
        algorithmConstantType = newItem.get("algorithmConstantType")
        try:
            key = algModelDict[int(algorithmConstantType)]
            res[key].append(newItem)
        except Exception as e:
            mainlogger.exception(e)

    response["constantMaps"] = res
    return response

@bp.route('/control/emergencyFalseAlarmStatus', methods=['GET', 'POST'])
@login_required
def emergencyFalseAlarmStatus():
    '''
    接口描述:更新误报标识
    '''
    params = request.get_json()
    emergency_record_id = params.get('emergencyRecordId', None)
    falseAlarmStatus = params.get('falseAlarmStatus', None)
    item = {'is_wrong': int(falseAlarmStatus)}

    my_db = ToMongo('wavedevice')
    query = {'emergency_record_id': emergency_record_id}
    my_db.update('odin_business_emergency_record', query, {'$set': item})

    response = set_success_result()
    return response


@bp.route('/control/emergencyMusicCloseStatus', methods=['GET', 'POST'])
@login_required
def emergencyMusicCloseStatus():
    '''
    接口描述:关闭音频状态
    状态:未完成
    '''

    params = request.get_json()
    emergency_record_id = params.get('emergencyRecordId', None)

    response = set_success_result()
    return response


@bp.route('/control/getRotationTime', methods=['GET', 'POST'])
@login_required
def getRotationTime():
    '''
    接口描述:获取轮询时间间隔
    '''

    my_db = ToMongo('wavedevice')
    rotation_item = my_db.get_col('odin_device_rotation_time').find_one()

    if rotation_item:
        response = set_success_result()
        response['rotationTime'] = rotation_item['rotation_time']
        return response


@bp.route('/control/setRotationTime', methods=['GET', 'POST'])
@login_required
def setRotationTime():
    '''
    接口描述:设置轮询时间间隔
    '''
    params = request.get_json()
    rotationTime = params.get("rotationTime", None)
    my_db = ToMongo('wavedevice')
    now = datetime.now()
    rotation_item = my_db.get_col("odin_device_rotation_time").find_one()
    if rotation_item:
        id = rotation_item['id']

    my_db.update("odin_device_rotation_time", {}, {"$set": {"rotation_time": rotationTime}})

    response = set_success_result()
    return response


@bp.route('/control/queryRotationOnOff', methods=['GET', 'POST'])
@login_required
def queryRotationOnOff():
    '''
    接口描述：查询轮播开关
    '''
    params = request.get_json()
    my_db = ToMongo('wavedevice')
    rotation_col = my_db.get_col("odin_device_rotation_time").find()
    if rotation_col.count() != 0:
        rotation_item = rotation_col[0]
        rotation_onoff = str(rotation_item['rotation_on_off'])
    else:
        rotation_onoff = "1"  # 默认开
    response = set_success_result()
    response['rotationOnOff'] = rotation_onoff
    return jsonify(response)


@bp.route('/control/setRotationOnOff', methods=['GET', 'POST'])
@login_required
def setRotationOnOff():
    '''
    接口描述：设置轮播开关
    '''
    params = request.get_json()
    rotationOnOff = params.get('rotationOnOff', None)
    my_db = ToMongo('wavedevice')
    modify_time = datetime.now()
    my_db.update("odin_device_rotation_time", {"id": 1},
                 {"$set": {"rotation_on_off": rotationOnOff, "modify_time": modify_time}})

    response = set_success_result()
    return jsonify(response)

@bp.route('/control/exportEmergencyItemsByIds', methods=['GET','POST'])
@login_required
def exportEmergencyItemsByIds():
    '''
    接口描述:导出告警纪录-告警图画框
    '''
    params = request.get_json()
    ids = params.get('ids',None)
    startNum = params.get('startNum',None)
    endNum = params.get('endNum',None)
    derive_type = params.get('type',None)  #导出类型   all part select
    begin_time = params.get('beginTime',None)
    controlName = params.get('controlName',None)
    end_time = params.get('endTime',None)
    falseAlarmStatus = params.get('falseAlarmStatus',None)
    model_path = params.get('modelPath',None)
    modelName = params.get('modelName',None)
    page = params.get('page',None)
    pageSize = params.get('pageSize',None)
    searchChoose = params.get('searchChoose',None)
    sortBy = params.get('sortBy',None)
    sortType = params.get('sortType',None)


    my_db = ToMongo('wavedevice') 

    all_zip = io.BytesIO()
    zf = zipfile.ZipFile(all_zip,'w')


    #创建好导出xls的表头
    book = xlwt.Workbook(encoding='utf-8',style_compression=0)
    now = datetime.now()
    timestr = now.strftime("%Y%m%d%H%M%S")
    xls_name = "导出告警纪录-%s"%timestr
    sheet = book.add_sheet('xls_name',cell_overwrite_ok=True)
    col = ("告警时间","识别模型","布控任务","摄像机名称","图片路径")
    for i in range(5):
        sheet.write(0,i,col[i])


    #获取告警事件的数据，写入告警图片
    emergency_record_col = my_db.get_col('odin_business_emergency_record')
    emergency_record_detail_col = my_db.get_col('odin_business_emergency_record_detail_info')
    datalist = [] 
    if derive_type == "select":
        query = {"emergency_record_id" :{"$in":ids}}
        emergency_items = emergency_record_col.find(query)
    else:
        quary = {}
        if  begin_time and  end_time:
            begin_time = int(str(begin_time)[0:10])
            end_time = int(str(end_time)[0:10])
            begin_time = datetime.fromtimestamp(begin_time)
            begin_time = begin_time.strftime("%Y-%m-%d %H:%M:%S")
            end_time = datetime.fromtimestamp(end_time)
            end_time = end_time.strftime("%Y-%m-%d %H:%M:%S")
            quary['emergency_time'] = {"$gte" :begin_time ,"$lte" :end_time}
        if model_path:
            quary['model_path'] = model_path
        if falseAlarmStatus and falseAlarmStatus != "":
            quary['is_wrong'] = int(falseAlarmStatus)
        if searchChoose and searchChoose != "":
            quary['$or'] = [{'emergency_position':{'$regex':searchChoose}},{'device_name':{'$regex':searchChoose}}]
        if controlName:
            control_item = find_control_mission_by_name(my_db, controlName)
            if control_item:
                quary['mission_id'] = control_item['control_id']
        emergency_items = emergency_record_col.find(quary).sort("emergency_time",-1)
        if derive_type == "part":
            emergency_items = emergency_items[startNum-1:endNum]

    for emergency_item in emergency_items:
        record_id = emergency_item['emergency_record_id']
        emergency_time = emergency_item['emergency_time']
        model_path = emergency_item['model_path']
        control_name = emergency_item['control_name']
        device_name = emergency_item['device_name']
        sub_source_id = emergency_item['sub_source_id']
        emeergency_date = emergency_item['create_time'].strftime("%Y%m%d")  

        detail_item = emergency_record_detail_col.find_one({'emergency_record_id':record_id})
        extra_info = detail_item['emergency_image_extra_info'] 
        alg_num = detail_item['algorithm_constant_num']  

        imgpath = EMERGENCY_IMG_PATH + emeergency_date + '/' + sub_source_id + '.jpg'
        img_zf_path = 'img/' + sub_source_id + '_' + alg_num + '.jpg'
        item = [emergency_time,model_path,control_name,device_name,"查看图片",img_zf_path]
        datalist.append(item)

        imgdata = draw_frame(imgpath,extra_info,alg_num,type=0,model_path=model_path)

        zf.writestr(img_zf_path,imgdata)

    #告警事件写入xls
    num = len(datalist)
    for i in range(num):
        data = datalist[i]
        for j in range(4):
            sheet.write(i+1,j,data[j])
        link = data[5]
        sheet.write(i+1,4,xlwt.Formula('HYPERLINK("%s";"查看图片")'%link))

    xls_file = xls_name + ".xls"
    xls_output = io.BytesIO()
    book.save(xls_output)
    zf.writestr(xls_file,xls_output.getvalue())

    zf.close()
    all_zip.seek(0)
    dl_name = xls_name + '.zip'
    return send_file(all_zip, attachment_filename=dl_name, as_attachment=True)

@bp.route('/control/checkExportEmergencyItemsByIds', methods=['GET', 'POST'])
@login_required
def checkExportEmergencyItemsByIds():
    params = request.get_json()
    ids = params.get('ids', None)
    startNum = params.get('startNum', None)
    endNum = params.get('endNum', None)
    derive_type = params.get('type', None)  # 导出类型   all part select
    begin_time = params.get('beginTime', None)
    controlName = params.get('controlName', None)
    end_time = params.get('endTime', None)
    falseAlarmStatus = params.get('falseAlarmStatus', None)
    model_path = params.get('modelPath', None)
    modelName = params.get('modelName', None)
    page = params.get('page', None)
    pageSize = params.get('pageSize', None)
    searchChoose = params.get('searchChoose', None)
    sortBy = params.get('sortBy', None)
    sortType = params.get('sortType', None)

    error_response = set_fail_result()
    error_response['errorCodeDesc'] = "请选择需要删除的警告记录"

    if derive_type == "select" and ids == []:
        return error_response

    response = set_success_result()
    return jsonify(response)


@bp.route('/control/selectWorkFlowAlgorithmConstantPaging', methods=['GET', 'POST'])
@login_required
def selectWorkFlowAlgorithmConstantPaging():
    '''
    接口描述：算法常量分页列表
    '''
    pageSize = request.json.get("pageSize")
    page = request.json.get("page")
    my_db = ToMongo("wavedevice")
    algorithm_coll = my_db.get_col(WORK_FLOW_ALGORITHM_CONSTANT).find()
    items = []
    for algorithm in algorithm_coll:
        item = {}
        item['algorithmConstantId'] = algorithm['algorithm_constant_id']
        item['algorithmConstantName'] = algorithm['algorithm_constant_name']
        item['algorithmConstantNum'] = algorithm['algorithm_constant_num']
        item['algorithmConstantType'] = algorithm['algorithm_constant_type']
        item['algorithmConstantStatus'] = algorithm['algorithm_constant_status']
        item['algorithmModel'] = algorithm['algorithm_model']
        item['algorithmVersion'] = algorithm['algorithm_version']
        item["algorithmServiceNum"] = algorithm["algorithm_service_num"]
        items.append(item)
    respone = {}
    respone['requestStatus'] = "SUCCESS"
    respone['requestId'] = uuid.uuid4().hex
    respone['timeUsed'] = 63
    respone['totalCount'] = len(items)
    respone['algorithmConstantVoList'] = items

    return jsonify(respone)

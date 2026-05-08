from datetime import datetime
from flask import Blueprint, jsonify
from flask import Flask ,request
import uuid
import json
from Utils.jwt_verify import *
from Utils.db import *
from system.sys_config import *
from system.system_misc import database_to_dict
from algorith_server.redis_connect import redis_database
from .temp_service import *

bp = Blueprint('dynamic_device',__name__,url_prefix='/net-web')

mainlogger = logger.getLogger('main')

def get_emergency_status(item,rePool):
  #  "获取动环设备的告警状态"
    if not item:
        return
    device_status = item.get("device_status")
    if device_status != 0:
        return 1
    device_type = item.get("device_type")
    if device_type == 3:
        #温度传感器
        key = item.get("device_num")
    else:
        #浸水传感器和烟雾传感器
        mac_addr = item.get("mac_addr")
        controller_port = item.get("controller_port")
        key = "KNDdevice" + str(controller_port) + ":" + mac_addr
    flag = rePool.exists(key)
    return 0 if flag else 1

@bp.route('/dynamicdevice/queryRotatyDevice', methods=['POST'])
@login_required
def queryRotatyDevice():
    '''
    查询动环设备列表
    '''  
    try:
        params = request.get_json()
        deviceName = params.get("deviceName")
        deviceType = params.get("deviceType")
        page = params.get("page")
        pageSize = params.get("pageSize")
        pointId = params.get("pointId")

        my_db = ToMongo('wavedevice')
        rePool = redis_database
        device_col = my_db.get_col("odin_dynamic_device")
        point_col = my_db.get_col("odin_point")

        query = dict()
        if deviceName:
            query['device_name'] = {"$regex":deviceName}
        if deviceType:
            query['device_type'] = deviceType
        if pointId:
            query['point_id'] = pointId
        if page and pageSize:
            num = pageSize*(page-1)
        else:
            pageSize = 10
            num = 0

        res = device_col.find(query)
        totalNum = res.count()
        pages = totalNum//pageSize + 1
        items = res.skip(num).limit(pageSize)

        rotatyDeviceEntities = []
        for item in items:
            newItem = database_to_dict(item,dynamic_device_database,dynamic_device_web)
            point_id = newItem.get("pointId")
            if point_id:
                query_point = {"point_id":point_id}
                point_item = point_col.find_one(query_point)
                newItem['pointName'] = point_item.get("point_name") if point_item else None
            else:
                newItem['pointName'] = None

            newItem['missionTime'] = json.loads(newItem['missionTime'])
            newItem['emergencyStatus'] = get_emergency_status(item,rePool)
        #    mainlogger.debug('rotatyDeviceEntities：%s'%newItem)
            rotatyDeviceEntities.append(newItem)

        response = set_success_result()
        response['rotatyDeviceEntities'] = rotatyDeviceEntities
        response['page'] = pages
        response['pageSize'] = pageSize
        response['totalCount']  = totalNum

        return jsonify(response)

    except Exception as e:
        error_reponse = set_fail_result()
        error_reponse['errorCodeDesc'] = "查询失败"
        error_reponse['exceptionCodeDesc'] = "Error:%s"%e 
        mainlogger.debug("queryRotatyDevice error:%s"%e)
        return jsonify(error_reponse)

@bp.route('/dynamicdevice/deleteRotatyDevice', methods=['POST'])
@login_required
def deleteRotatyDevice():
    '''
    删除动环设备列表
    '''  
    try:
        params = request.get_json()
        deviceId = params.get("deviceId")
        my_db = ToMongo('wavedevice')
        query = {'device_id':deviceId}
        my_db.delete('odin_dynamic_device',query)
        response = set_success_result()
        return jsonify(response)
        
    except Exception as e:
        error_reponse = set_fail_result()
        error_reponse['errorCodeDesc'] = "删除失败"
        error_reponse['exceptionCodeDesc'] = "Error:%s"%e 
        mainlogger.debug("deleteRotatyDevice error:%s"%e)
        return jsonify(error_reponse)

@bp.route('/dynamicdevice/addRotatyDevice', methods=['POST'])
@login_required
def addRotatyDevice():
    '''
    增加动环设备列表
    '''  
    try:
        params = request.get_json()
        controllerPort = params.get("controllerPort")
        controllerPort = int(controllerPort) if controllerPort else None
        deviceName = params.get("deviceName")
        deviceNum = params.get("deviceNum")
        deviceType = params.get("deviceType")
        emergencyIntervalTime = params.get("emergencyIntervalTime")
        macAddr = params.get("macAddr")
        modelName = params.get("modelName")
        pointId = params.get("pointId")
        soundContext = params.get("soundContext")
        soundId = params.get("soundId")
        soundTimes = params.get("soundTimes")
        missionTime = params.get("missionTime")

        my_db = ToMongo('wavedevice')
        query = {"mac_addr":macAddr,"controller_port":controllerPort}
        device_col = my_db.get_col("odin_dynamic_device")
        result = device_col.find_one(query)

        if result:
            error_response = set_fail_result()
            error_response['errorCodeDesc'] = "设备的端口已被占用！"
            return jsonify(error_response)
            

        deviceId = uuid.uuid4().hex
        createTime = updateTime = datetime.now()

        item= {
               "deviceName":deviceName,
               "emergencyIntervalTime":emergencyIntervalTime,
               "deviceType":deviceType,
               "pointId":pointId,
               "macAddr":macAddr,
               "deviceNum":deviceNum,
               "soundId":soundId,
               "controllerPort":controllerPort,
               "modelName":modelName,
               "soundTimes":soundTimes,
               "soundContext":soundContext,
               "deviceId":deviceId,
               "soundSwitch":0,#音响默认开
               "deviceStatus":1,#设备默认状态为关
               "createTime":createTime,
               "updateTime":updateTime,
               "missionTime":missionTime
               }
        newItem = database_to_dict(item,dynamic_device_web,dynamic_device_database)

        my_db.insert('odin_dynamic_device',newItem)

        response = set_success_result()
        return jsonify(response)
              
    except Exception as e:
        error_reponse = set_fail_result()
        error_reponse['errorCodeDesc'] = "添加失败"
        error_reponse['exceptionCodeDesc'] = "Error:%s"%e 
        mainlogger.debug("addDevice error:%s"%e)
        return jsonify(error_reponse)

@bp.route('/dynamicdevice/updateRotatyDevice', methods=['POST'])
@login_required
def updateRotatyDevice():
    '''
    编辑动环设备列表
    '''  
    try:
        params = request.get_json()
        controllerPort = params.get("controllerPort")
        controllerPort = int(controllerPort) if controllerPort else None
        deviceId = params.get("deviceId")
        deviceName = params.get("deviceName")
        deviceNum = params.get("deviceNum")
        deviceType = params.get("deviceType")
        deviceStatus = params.get("deviceStatus")

        soundSwitch = params.get("soundSwitch")

        emergencyIntervalTime = params.get("emergencyIntervalTime")
      #  emergencyStatus = params.get("emergencyStatus")

        macAddr = params.get("macAddr")
        modelName = params.get("modelName")
        pointId = params.get("pointId")
        soundContext = params.get("soundContext")
        soundId = params.get("soundId")
        soundTimes = params.get("soundTimes")

        missionTime = params.get("missionTime")

        createTime = params.get("createTime")
        createTime = datetime.strptime(createTime,"%Y-%m-%d %H:%M:%S")
        updateTime = params.get("updateTime")

        item= {
               "deviceName":deviceName,
               "emergencyIntervalTime":emergencyIntervalTime,
               "deviceType":deviceType,
               "pointId":pointId,
               "macAddr":macAddr,
               "deviceNum":deviceNum,
               "soundId":soundId,
               "controllerPort":controllerPort,
               "modelName":modelName,
               "soundTimes":soundTimes,
               "soundContext":soundContext,
               "deviceId":deviceId,
               "soundSwitch":soundSwitch,
               "deviceStatus":deviceStatus,
               "createTime":createTime,
               "updateTime":updateTime,
               "missionTime":missionTime
               }
        newItem = database_to_dict(item,dynamic_device_web,dynamic_device_database)

        my_db = ToMongo('wavedevice')
        query = {"device_id":deviceId}
        my_db.update('odin_dynamic_device',query,{"$set":newItem})

        response = set_success_result()
        return jsonify(response)
              
    except Exception as e:
        error_reponse = set_fail_result()
        error_reponse['errorCodeDesc'] = "编辑失败"
        error_reponse['exceptionCodeDesc'] = "Error:%s"%e 
        mainlogger.debug("editDevice error:%s"%e)
        return jsonify(error_reponse)
    
@bp.route('/dynamicdevice/soundSwitch', methods=['POST'])
@login_required
def soundSwitch():
    '''
    开关音箱
    '''  
    try:
        params = request.get_json()
        soundSwitch = params.get("soundSwitch")
        deviceId = params.get("deviceId")

        query = {"device_id":deviceId}

        my_db = ToMongo('wavedevice')
        my_db.update('odin_dynamic_device',query,{'$set':{'sound_switch':soundSwitch}})

        response = set_success_result()
        return jsonify(response)
              
    except Exception as e:
        error_reponse = set_fail_result()
        error_reponse['errorCodeDesc'] = "设置失败"
        error_reponse['exceptionCodeDesc'] = "Error:%s"%e 
        mainlogger.debug("soundSwitch error:%s"%e)
        return jsonify(error_reponse)
    
@bp.route('/dynamicdevice/getThreshold', methods=['POST'])
@login_required
def getThreshold():
    '''
    查询温度阈值
    '''  
    try:
        my_db = ToMongo('wavedevice')
        col = my_db.get_col('odin_business_dynamic_threshold')
        item = col.find_one({})

        data = dict()
        data['organizationId'] = item.get('organization_id')
        data['temperatureMax'] = item.get('temperature_max')
        data['temperatureMin'] = item.get('temperature_min')
        data['thresholdId'] = item.get('threshold_id')
   

        response = set_success_result()
        response['data'] = data
        return jsonify(response)
              
    except Exception as e:
        error_reponse = set_fail_result()
        mainlogger.debug("getThreshold error:%s"%e)
        error_reponse['errorCodeDesc'] = "查询失败"
        error_reponse['exceptionCodeDesc'] = "Error:%s"%e 
        return jsonify(error_reponse)
    
@bp.route('/dynamicdevice/updateThreshold', methods=['POST'])
@login_required
def updateThreshold():
    '''
    更新温度阈值
    '''  
    try:
        params = request.get_json()
        organizationId = params.get("organizationId")
        temperatureMax = params.get("temperatureMax")
        temperatureMin = params.get("temperatureMin")
        thresholdId = params.get("thresholdId")

        my_db = ToMongo('wavedevice')
        
        item= {
               'organization_id':organizationId,
               'temperature_max':temperatureMax,
               'temperature_min':temperatureMin,
               'threshold_id':thresholdId
              }
        my_db.update('odin_business_dynamic_threshold',{},{'$set':item})
        TempInstance = TempServer(context=None)
        TempInstance.set_temp_threhold(temp_max=temperatureMax,temp_min=temperatureMin)
   
        response = set_success_result()
        return jsonify(response)
              
    except Exception as e:
        error_reponse = set_fail_result()
        error_reponse['errorCodeDesc'] = "编辑失败"
        error_reponse['exceptionCodeDesc'] = "Error:%s"%e 
        mainlogger.debug("updateThreshold error:%s"%e)
        return jsonify(error_reponse)

@bp.route('/dynamicemergency/queryDynamicEmergency', methods=['POST'])
@login_required
def queryDynamicEmergency():
    '''
    获取动环告警纪录
    '''  
    try:
        params = request.get_json()
        deviceName = params.get("deviceName")
        deviceType = params.get("deviceType")
        page = params.get("page")
        pageSize = params.get("pageSize")
        pointId = params.get("pointId")

        my_db = ToMongo('wavedevice')
        col = my_db.get_col("odin_business_dynamic_emergency_record")

        query = dict()
        if deviceName:
            query['device_name'] = {"$regex":deviceName}
        if deviceType:
            query['device_type'] = deviceType
        if pointId:
            query['point_id'] = pointId
        if page and pageSize:
            num = pageSize*(page-1)
        else:
            pageSize = 10
            num = 0

        res = col.find(query).sort("emergency_time",-1)
        totalNum = res.count()
        pages = totalNum//pageSize + 1
        items = res.skip(num).limit(pageSize)

        deviceEntityList = []

        for item in items:
            newItem = database_to_dict(item,dynamic_emergency_database,dynamic_emergency_web)
            if newItem['emergencyTime']:
                newItem['emergencyTime'] = int(newItem['emergencyTime'].timestamp()) *1000
            deviceEntityList.append(newItem)

        response = set_success_result()
        response['deviceEntityList'] = deviceEntityList
        response['page'] = pages
        response['pageSize'] = pageSize
        response['totalCount'] = totalNum

        return jsonify(response)
              
    except Exception as e:
        error_reponse = set_fail_result()
        error_reponse['errorCodeDesc'] = "查询失败"
        error_reponse['exceptionCodeDesc'] = "Error:%s"%e 
        mainlogger.debug("queryDynamicEmergency error:%s"%e)
        return jsonify(error_reponse)
    

@bp.route('/odinpoint/queryOdinPoint', methods=['POST'])
@login_required
def queryOdinPoint():
    '''
    查询动环点位列表
    '''  
    try:
        params = request.get_json()
        page = params.get("page")
        pageSize = params.get("pageSize")
        pointName = params.get("pointName")

        query = dict()
        if pointName:
            query['point_name'] = {"$regex":pointName}

        if page and pageSize:
            num = pageSize*(page-1)
        else:
            pageSize = 10
            num = 0

        my_db = ToMongo('wavedevice')
        point_col = my_db.get_col("odin_point")
        device_col = my_db.get_col("odin_dynamic_device")
        
        res = point_col.find(query)

        totalNum = res.count()
        pages = totalNum//pageSize + 1
        items = res.skip(num).limit(pageSize)
   
        data = [] 
        for item in items:
            newItem = database_to_dict(item,dynamic_point_database,dynamic_point_web)
            if newItem['createTime']:
                newItem['createTime'] = int(newItem['createTime'].timestamp())*1000
            if newItem['updateTime']:
                newItem['updateTime'] = int(newItem['updateTime'].timestamp())*1000
            point_id = item.get("point_id")
            newItem["deviceNum"] = device_col.find({"point_id":point_id}).count()
            data.append(newItem)

        response = set_success_result()
        response['odinPointEntityList'] = data
        response['page'] = pages
        response['pageSize'] = pageSize
        response['totalCount']  = totalNum

        return jsonify(response)

    except Exception as e:
        error_reponse = set_fail_result()
        error_reponse['errorCodeDesc'] = "查询失败"
        error_reponse['exceptionCodeDesc'] = "Error:%s"%e 
        mainlogger.debug("query pointList error:%s"%e)
        return jsonify(error_reponse)

@bp.route('/devicemodel/getNetController', methods=['POST'])
@login_required
def getNetController():
    '''
    查询康奈德类型
    '''  
    try:
        params = request.get_json()
        publicDictType = params.get("publicDictType")

        my_db = ToMongo('wavedevice')
        col = my_db.get_col("public_dict_baseinfo")
        query = {"public_dict_type":publicDictType}
        res = col.find_one(query)
        
        newItem = {}
        if res:
            newItem['publicDictId'] = res['public_dict_id']
            newItem['publicDictName'] = res['public_dict_name']
            newItem['publicDictParam1'] = res['public_dict_param1']

        response = set_success_result()
        response['list'] = [newItem]

        return jsonify(response)

    except Exception as e:
        error_reponse = set_fail_result()
        error_reponse['errorCodeDesc'] = "查询失败"
        error_reponse['exceptionCodeDesc'] = "Error:%s"%e 
        mainlogger.debug("getNetController error:%s"%e)
        return jsonify(error_reponse)

@bp.route('/dynamicdevice/modelList', methods=['POST'])
@login_required
def modelList():
    '''
    查询康奈德类型
    '''  
    try:
        
        my_db = ToMongo('wavedevice')
        col = my_db.get_col("odin_dynamic_device_model")
        res = col.find()
   
        data = [] 
        for item in res:
            newItem = database_to_dict(item,kndmode_database,kndmode_web)
            data.append(newItem)

        response = set_success_result()
        response['data'] = data

        return jsonify(response)

    except Exception as e:
        error_reponse = set_fail_result()
        error_reponse['errorCodeDesc'] = "查询失败"
        error_reponse['exceptionCodeDesc'] = "Error:%s"%e 
        mainlogger.debug("query modelList error:%s"%e)
        return jsonify(error_reponse)

@bp.route('/odinpoint/deleteOdinPoint', methods=['POST'])
@login_required
def deleteOdinPoint():
    '''
    删除动环点位
    '''  
    try:
        params = request.get_json()
        pointId = params.get("pointId")
        my_db = ToMongo('wavedevice')
        query = {'point_id':pointId}
        device_col = my_db.get_col("odin_dynamic_device")
        item = device_col.find_one(query)

        if item:
            error_response = set_fail_result()
            error_response['errorCodeDesc'] = "请先删除与该点位绑定的设备！"
            return jsonify(error_response)

        my_db.delete('odin_point',query)
        response = set_success_result()
        return jsonify(response)
        
    except Exception as e:
        error_reponse = set_fail_result()
        error_reponse['errorCodeDesc'] = "删除失败"
        error_reponse['exceptionCodeDesc'] = "Error:%s"%e 
        mainlogger.debug("deletePoint error:%s"%e)
        return jsonify(error_reponse)

@bp.route('/odinpoint/addOdinPoint', methods=['POST'])
@login_required
def addOdinPoint():
    '''
    增加动环设备列表
    '''  
    try:
        params = request.get_json()
        accessToken = params.get("accessToken",None)
        pointName = params.get("pointName")
        remark = params.get("remark")

        my_db = ToMongo('wavedevice')
        col = my_db.get_col("odin_point")
        result = col.find_one({"point_name":pointName})

        if result:
            error_response = set_fail_result()
            error_response['errorCodeDesc'] = "设备名称重复，请重新填写！"
            return jsonify(error_response)
       
        pointId = uuid.uuid4().hex
        createTime = updateTime = datetime.now()
        organizationId = decode_token(accessToken,my_db)

        item= {
               "pointName":pointName,
               "remark":remark,
               "organizationId":organizationId,
               "pointId":pointId,
               "createTime":createTime,
               "updateTime":updateTime
               }
        newItem = database_to_dict(item,dynamic_point_web,dynamic_point_database)

        my_db.insert('odin_point',newItem)
        response = set_success_result()
        response['id'] = pointId
        return jsonify(response)
              
    except Exception as e:
        error_reponse = set_fail_result()
        error_reponse['errorCodeDesc'] = "添加失败"
        error_reponse['exceptionCodeDesc'] = "Error:%s"%e 
        mainlogger.debug("addPoint error:%s"%e)
        return jsonify(error_reponse)

@bp.route('/odinpoint/updateOdinPoint', methods=['POST'])
@login_required
def updateOdinPoint():
    '''
    编辑动环点位
    '''  
    try:
        params = request.get_json()

        pointId = params.get("pointId")
        pointName = params.get("pointName")
        remark = params.get("remark")
        my_db = ToMongo('wavedevice')

        col = col = my_db.get_col("odin_point")
        result = col.find_one({"point_name":pointName,"point_id":pointId})

        if result:
            error_response = set_fail_result()
            error_response['errorCodeDesc'] = "设备名称重复，请重新填写！"
            return jsonify(error_response)

        updateTime = datetime.now()

        item= {
               "point_name":pointName,
               "remark":remark,
               "update_time":updateTime
               }

        query = {'point_id':pointId}
        my_db.update('odin_point',query,{'$set':item})

        response = set_success_result()
        return jsonify(response)
              
    except Exception as e:
        error_reponse = set_fail_result()
        error_reponse['errorCodeDesc'] = "编辑失败"
        error_reponse['exceptionCodeDesc'] = "Error:%s"%e 
        mainlogger.debug("updatePoint error:%s"%e)
        return jsonify(error_reponse)

@bp.route('/threshold/getthreshold', methods=['POST'])
@login_required
def getthreshold():
    '''
    获取温度阈值
    '''  
    try:
        my_db = ToMongo('wavedevice')

        col = col = my_db.get_col("odin_business_dynamic_threshold")
        result = col.find_one({})

        dynamicThresholdEntity = {}
        if result:
            dynamicThresholdEntity['temperatureMax'] = result.get("temperature_max")
            dynamicThresholdEntity['temperatureMin'] = result.get("temperature_min")
            dynamicThresholdEntity['thresholdId'] = result.get("threshold_id")

        response = set_success_result()
        response['dynamicThresholdEntity'] = dynamicThresholdEntity
        return jsonify(response)
              
    except Exception as e:
        error_reponse = set_fail_result()
        error_reponse['errorCodeDesc'] = "查询失败"
        error_reponse['exceptionCodeDesc'] = "Error:%s"%e 
        mainlogger.debug("getthreshold error:%s"%e)
        return jsonify(error_reponse)
    
@bp.route('/threshold/addthreshold', methods=['POST'])
@login_required
def addthreshold():
    '''
    设置温度阈值
    '''  
    try:
        params = request.get_json()
        temperatureMax = params.get("temperatureMax")
        temperatureMin = params.get("temperatureMin")
        thresholdId = params.get("thresholdId")

        my_db = ToMongo('wavedevice')
        query = {"threshold_id":thresholdId}

        item = {"temperature_max":temperatureMax,"temperature_min":temperatureMin}
        my_db.update("odin_business_dynamic_threshold",query,{"$set":item})

        my_db.update('odin_business_dynamic_threshold',{},{'$set':item})
        TempInstance = TempServer(context=None)
        TempInstance.set_temp_threhold(temp_max=temperatureMax,temp_min=temperatureMin)

        response = set_success_result()
        return jsonify(response)
              
    except Exception as e:
        error_reponse = set_fail_result()
        error_reponse['errorCodeDesc'] = "编辑失败"
        error_reponse['exceptionCodeDesc'] = "Error:%s"%e 
        mainlogger.debug("addthreshold error:%s"%e)
        return jsonify(error_reponse)
    
@bp.route('/devicemodel/queryRotatyDevicePort', methods=['POST'])
@login_required
def queryRotatyDevicePort():
    '''
    查询康奈德控制端口
    '''  
    try:
        params = request.get_json()
        deviceType = params.get("deviceType")
        modelName = params.get("modelName")

        my_db = ToMongo('wavedevice')
        query = {"device_type":int(deviceType)}
        col = my_db.get_col("odin_dynamic_device_model")
        item = col.find_one(query)
        deviceModelEntity = {}
        if item:
            deviceModelEntity['devicePort'] = item.get("device_port")
            deviceModelEntity['modelId'] = item.get("model_id")

        response = set_success_result()
        response["deviceModelEntity"] = deviceModelEntity
        return jsonify(response)
              
    except Exception as e:
        error_reponse = set_fail_result()
        error_reponse['errorCodeDesc'] = "查询失败"
        error_reponse['exceptionCodeDesc'] = "Error:%s"%e 
        mainlogger.debug("queryRotatyDevicePort error:%s"%e)
        return jsonify(error_reponse)
    
@bp.route('/dynamicdevice/updateSoundSwitch', methods=['POST'])
@login_required
def updateSoundSwitch():
    '''
    音响开关接口
    '''  
    try:
        params = request.get_json()
        deviceId = params.get("deviceId")
        soundSwitch = params.get("soundSwitch")

        my_db = ToMongo('wavedevice')
        query = {"device_id":deviceId}
        newItem = {"sound_switch":soundSwitch}
        
        my_db.update("odin_dynamic_device",query,{"$set":newItem})

        response = set_success_result()
        return jsonify(response)
              
    except Exception as e:
        error_reponse = set_fail_result()
        error_reponse['errorCodeDesc'] = "编辑失败"
        error_reponse['exceptionCodeDesc'] = "Error:%s"%e 
        mainlogger.debug("updateSoundSwitch error:%s"%e)
        return jsonify(error_reponse)
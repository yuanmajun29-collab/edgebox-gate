from flask import Blueprint
from utils.jwt_verify import *
from utils.datacfg import *
from utils.Utils import set_fail_result, set_success_result
from system.system_misc import database_to_dict,database_to_dict3
from emergency.advise_router import decode_token
from .Tempservice import *
from .Serialnetservice import SerialNetServer
import uuid
from threading import Thread
from msg_queue import audio_queue
from system.sync_model import *

bp = Blueprint('dynamic_device', __name__, url_prefix='/net-web')

mainlogger = logger.getLogger('main')


def get_emergency_status(item, rePool):
    #  "获取动环设备的告警状态"
    if not item:
        return
    # device_status = item.get("device_status")
    # if device_status != '0':
    #     return 1
    device_id = item.get("device_id")
    key = "dynamicemergency:" + device_id
    return 0 if rePool.exists(key) else 1


def get_device_status(item, rePool):
    # "获取动环设备的在线离线状态"
    if not item:
        return
    # device_status = item.get("device_status")
    # if device_status != '0':
    #     return 1
    device_id = item.get("device_id")
    key = "dynamicstatus:" + device_id
    return "0" if rePool.exists(key) else "1"


def get_emergency_status_2(item, rePool):
    #  "获取动环设备的告警状态"
    #  烟雾、温度、浸水等使用这个接口
    if not item:
        return
    device_status = item.get("device_status")
    if device_status != 0:
        return 1
    device_type = item.get("device_type")
    if device_type == 3:
        # 温度传感器
        key = item.get("device_num")
    else:
        # 浸水传感器和烟雾传感器
        mac_addr = item.get("mac_addr")
        controller_port = item.get("controller_port")
        key = "KNDdevice" + str(controller_port) + ":" + mac_addr
    flag = rePool.exists(key)
    return 0 if flag else 1


def get_total_addr(my_db, deviceId, deviceType):
    gas_col = my_db.get_col("odin_dynamic_gas")
    leak_col = my_db.get_col("odin_dynamic_leakage")
    ele_col = my_db.get_col("odin_dynamic_static_electricity")
    audio_col = my_db.get_col("odin_dynamic_audio")
    query = {'device_id': {'$ne': deviceId}}

    gas_addr_list = gas_col.distinct("device_addr", query) if deviceType == '1' else gas_col.distinct("device_addr")
    leak_addr_list = leak_col.distinct("device_addr", query) if deviceType == '2' else leak_col.distinct("device_addr")
    ele_addr_list = ele_col.distinct("device_addr", query) if deviceType == '3' else ele_col.distinct("device_addr")
    aduio_addr_list = audio_col.distinct("device_addr", query) if deviceType == '4' else audio_col.distinct(
        "device_addr")
    total_addr_list = gas_addr_list + leak_addr_list + ele_addr_list + aduio_addr_list

    return total_addr_list


@bp.route('/dynamicdevice/queryDynamicList', methods=['POST'])
# @login_required
def queryDynamicList():
    '''
    查询动环设备列表
    '''
    params = request.get_json()
    deviceName = params.get("deviceName")
    deviceStatus = params.get("deviceStatus")
    deviceType = params.get("deviceType")
    page = params.get("page")
    pageSize = params.get("pageSize")

    my_db = ToMongo('wavedevice')
    rePool = redis_database

    query = dict()
    if deviceName:
        query['device_name'] = {"$regex": deviceName}
    # if deviceStatus:
    #     query['device_status'] = deviceStatus

    if page and pageSize:
        num = pageSize * (page - 1)
    else:
        pageSize = 10
        num = 0

    if deviceType == '1':
        # 气体探测器
        col = my_db.get_col('odin_dynamic_gas')
        device_web = gas_web
        device_db = gas_db
    elif deviceType == '2':
        # 漏电断路器
        col = my_db.get_col('odin_dynamic_leakage')
        device_web = leakage_web
        device_db = leakage_db
    elif deviceType == '3':
        # 静电接地器
        col = my_db.get_col('odin_dynamic_static_electricity')
        device_web = eleground_web
        device_db = eleground_db

    res = col.find(query)
    totalNum = res.count()
    pages = totalNum // pageSize + 1
    items = res.skip(num).limit(pageSize)

    rotatyDeviceEntities = []
    for item in items:
        device_status = get_device_status(item, rePool)
        if deviceStatus and device_status != deviceStatus:
            continue

        newItem = database_to_dict(item, device_db, device_web)
        if deviceType in ['1', '2']:
            newItem['emergencyStatus'] = get_emergency_status(item, rePool)

        newItem['deviceStatus'] = device_status
        createTime = newItem["createTime"]
        newItem["createTime"] = int(createTime.timestamp()) * 1000
        offlineTime = newItem.get("offlineTime")
        if newItem['deviceStatus'] == "1":
            newItem["offlineTime"] = offlineTime.strftime('%Y-%m-%d %H:%M') if offlineTime else None
        else:
            newItem["offlineTime"] = None

        rotatyDeviceEntities.append(newItem)

    response = set_success_result()
    response['rotatyDeviceEntities'] = rotatyDeviceEntities
    response['page'] = pages
    response['pageSize'] = pageSize
    response['totalCount'] = totalNum
    return jsonify(response)


@bp.route('/dynamicdevice/getLeakDeviceInfo', methods=['POST'])
# @login_required
def getLeakDeviceInfo():
    '''
    查询漏电断路器 具体信息
    '''
    params = request.get_json()
    deviceId = params.get('deviceId')

    my_db = ToMongo('wavedevice')
    col = my_db.get_col("odin_dynamic_leakage")
    rePool = redis_database

    item = col.find_one({"device_id": deviceId})
    deviceInfo = {}
    if not item:
        response = set_fail_result()
        response['errorCodeDesc'] = "设备不存在!"
        return jsonify(response)

    deviceInfo = database_to_dict(item, leakage_db, leakage_web)
    deviceInfo["emergencyStatus"] = get_emergency_status(item, rePool)
    deviceInfo['deviceStatus'] = get_device_status(item, rePool)
    createTime = deviceInfo["createTime"]
    deviceInfo["createTime"] = int(createTime.timestamp()) * 1000
    offlineTime = deviceInfo.get("offlineTime")
    if offlineTime:
        deviceInfo["offlineTime"] = offlineTime.strftime('%Y-%m-%d %H:%M')
    else:
        deviceInfo["offlineTime"] = createTime.strftime('%Y-%m-%d %H:%M')

    asso_item = my_db.get_col('odin_dynamic_associate').find_one({'device_id': deviceId})
    deviceInfo['phoneNumber'] = asso_item.get('phone_number') if asso_item else None
    deviceInfo['audioId'] = asso_item.get('audio_id') if asso_item else None
    deviceInfo['smsNumber'] = asso_item.get('sms_number') if asso_item else None

    response = set_success_result()
    response["deviceInfo"] = deviceInfo
    return jsonify(response)


@bp.route('/dynamicdevice/getGasDeviceInfo', methods=['POST'])
# @login_required
def getGasDeviceInfo():
    '''
    查询气体探测器 具体信息
    '''
    params = request.get_json()
    deviceId = params.get('deviceId')

    my_db = ToMongo('wavedevice')
    rePool = redis_database
    col = my_db.get_col("odin_dynamic_gas")

    item = col.find_one({"device_id": deviceId})
    deviceInfo = {}
    if not item:
        response = set_fail_result()
        response['errorCodeDesc'] = "设备不存在!"
        return jsonify(response)

    deviceInfo = database_to_dict(item, gas_db, gas_web)
    deviceInfo["emergencyStatus"] = get_emergency_status(item, rePool)
    deviceInfo['deviceStatus'] = get_device_status(item, rePool)
    createTime = deviceInfo["createTime"]
    deviceInfo["createTime"] = int(createTime.timestamp()) * 1000
    offlineTime = deviceInfo.get("offlineTime")
    if offlineTime:
        deviceInfo["offlineTime"] = offlineTime.strftime('%Y-%m-%d %H:%M')
    else:
        deviceInfo["offlineTime"] = createTime.strftime('%Y-%m-%d %H:%M')

    asso_item = my_db.get_col('odin_dynamic_associate').find_one({'device_id': deviceId})
    deviceInfo['phoneNumber'] = asso_item.get('phone_number') if asso_item else None
    deviceInfo['audioId'] = asso_item.get('audio_id') if asso_item else None
    deviceInfo['smsNumber'] = asso_item.get('sms_number') if asso_item else None

    response = set_success_result()
    response["deviceInfo"] = deviceInfo
    return jsonify(response)


@bp.route('/dynamicdevice/getElectricDeviceInfo', methods=['POST'])
# @login_required
def getElectricDeviceInfo():
    '''
    查询静电接地器 具体信息
    '''
    params = request.get_json()
    deviceId = params.get('deviceId')

    my_db = ToMongo('wavedevice')
    rePool = redis_database
    col = my_db.get_col("odin_dynamic_static_electricity")

    item = col.find_one({"device_id": deviceId})
    deviceInfo = {}
    if not item:
        response = set_fail_result()
        response['errorCodeDesc'] = "设备不存在!"
        return jsonify(response)
    deviceInfo = database_to_dict(item, eleground_db, eleground_web)
    deviceInfo["emergencyStatus"] = get_emergency_status(item, rePool)
    deviceInfo['deviceStatus'] = get_device_status(item, rePool)
    createTime = deviceInfo["createTime"]
    deviceInfo["createTime"] = int(createTime.timestamp()) * 1000
    offlineTime = deviceInfo.get("offlineTime")
    if offlineTime:
        deviceInfo["offlineTime"] = offlineTime.strftime('%Y-%m-%d %H:%M')
    else:
        deviceInfo["offlineTime"] = createTime.strftime('%Y-%m-%d %H:%M')

    response = set_success_result()
    response["deviceInfo"] = deviceInfo
    return jsonify(response)


@bp.route('/dynamicdevice/updateRotatyDevice', methods=['POST'])
# @login_required
def updateRotatyDevice():
    '''
    编辑动环设备列表
    '''
    params = request.get_json()
    deviceName = params.get("deviceName")
    deviceNum = params.get("deviceNum")
    deviceType = params.get("deviceType")
    deviceAddr = params.get("deviceAddr")
    deviceModel = params.get("deviceModel")
    deviceId = params.get("deviceId")

    ip = params.get("ip")
    port = params.get("port")
    connectionType = params.get("connectionType")
    controllerType = params.get("controllerType")

    my_db = ToMongo('wavedevice')

    total_addr_list = get_total_addr(my_db, deviceId, deviceType)
    if deviceAddr in total_addr_list:
        error_reponse = set_fail_result()
        error_reponse["errorCodeDesc"] = "地址位已存在"
        return jsonify(error_reponse)

    updateTime = datetime.now()

    item = {
        "device_name": deviceName,
        "device_addr": deviceAddr,
        "device_num": deviceNum,
        "device_model": deviceModel,
        "update_time": updateTime,
        "ip":ip,
        "port":port,
        "connection_type":connectionType,
        "controller_type":controllerType
    }

    query = {"device_id": deviceId}

    phoneNumber = params.get("phoneNumber")
    smsNumber = params.get("smsNumber")
    audioId = params.get("audioId")
    related_item = {
            "deviceId":deviceId,
            "phoneNumber": phoneNumber,
            "smsNumber": smsNumber,
            "audioId": audioId}

    if deviceType == '1':
        # 气体探测器
        item_extra = {
            "density": params.get("density"),
            "high_density_alarm": params.get("highDensityAlarm")
        }
        item_all = dict(item, **item_extra)
        my_db.update("odin_dynamic_gas", query, {"$set": item_all})

        newItem = database_to_dict3(item_all,gas_db,gas_web)
        newItem['highDensityAlarm'] = json.dumps(newItem['highDensityAlarm'])
        newItem = dict(newItem,**related_item)
        sync_thread = Thread(target=sync_dev,args=[newItem,SYNC_GAS])
        sync_thread.start()
        
    elif deviceType == '2':
        # 漏电断路器
        col = my_db.get_col('odin_dynamic_leakage')
        old_item = col.find_one(query)
        volt_param_new = params.get("volt")
        current_param_new = params.get("current")
        item_extra = {
            "distribution_num": params.get("distributionNum"),
            "volt_type": params.get("voltType"),
            "volt": volt_param_new,
            "current": current_param_new,
            "high_volt_alarm": params.get("highVoltAlarm"),
            "low_volt_alarm": params.get("lowVoltAlarm"),
            "leakage_alarm": params.get("leakageAlarm"),
            "high_cur_alarm": params.get("highCurAlarm")
        }
        item_all = dict(item, **item_extra)
        my_db.update("odin_dynamic_leakage", query, {"$set": item_all})
 
        newItem = database_to_dict3(item_all,leakage_db,leakage_web)
        newItem = dict(newItem,**related_item)
        newItem['highVoltAlarm'] = json.dumps(newItem['highVoltAlarm'])
        newItem['lowVoltAlarm'] = json.dumps(newItem['lowVoltAlarm'])
        newItem['leakageAlarm'] = json.dumps(newItem['leakageAlarm'])
        newItem['highCurAlarm'] = json.dumps(newItem['highCurAlarm'])
        newItem['volt'] = json.dumps(newItem['volt'])
        newItem['current'] = json.dumps(newItem['current'])
        sync_thread = Thread(target=sync_dev,args=[newItem,SYNC_LEAKAGE])
        sync_thread.start()

    elif deviceType == '3':
        # 静电接地器
        my_db.update("odin_dynamic_static_electricity", query, {"$set": item})
        newItem = database_to_dict3(item,eleground_db,eleground_web)
        newItem['deviceId'] = deviceId
        sync_thread = Thread(target=sync_dev,args=[newItem,SYNC_GND])
        sync_thread.start()

    if phoneNumber or smsNumber or audioId:
        asso_item = {
            "phone_number": phoneNumber,
            "sms_number": smsNumber,
            "audio_id": audioId,
            "device_type": deviceType
        }
        col = my_db.get_col("odin_dynamic_associate")
        col.update_one(query, {"$set": asso_item}, upsert=True)
    #    my_db.update("odin_dynamic_associate",query,{"$set":asso_item})

    # 重新拉取动环任务
    instance = SerialNetServer(context=None)
    instance.getTask()

    response = set_success_result()
    return jsonify(response)


@bp.route('/dynamicdevice/deleteRotatyDevice', methods=['POST'])
# @login_required
def deleteRotatyDevice():
    '''
    删除动环设备列表
    '''
    try:
        params = request.get_json()
        deviceId = params.get("deviceId")
        deviceType = params.get("deviceType")
        my_db = ToMongo('wavedevice')
        query = {'device_id': deviceId}
        if deviceType == '1':
            # 气体探测器
            my_db.delete('odin_dynamic_gas', query)
        elif deviceType == '2':
            # 断路器
            my_db.delete('odin_dynamic_leakage', query)
        elif deviceType == '3':
            # 静电接地器
            my_db.delete('odin_dynamic_static_electricity', query)

        my_db.delete('odin_dynamic_associate', query)

        delete_thread = Thread(target=sync_deleteDev,args=[deviceId,deviceType])
        delete_thread.start()

        # 重新拉取动环任务
        instance = SerialNetServer(context=None)
        instance.getTask()

        response = set_success_result()
        return jsonify(response)

    except Exception as e:
        error_reponse = set_fail_result()
        error_reponse['errorCodeDesc'] = "删除失败"
        error_reponse['exceptionCodeDesc'] = "Error:%s" % e
        mainlogger.info("deleteRotatyDevice error:%s" % e)
        return jsonify(error_reponse)


@bp.route('/dynamicdevice/addRotatyDevice', methods=['POST'])
# @login_required
def addRotatyDevice():
    '''
    增加动环设备列表
    '''
    try:
        params = request.get_json()
        deviceName = params.get("deviceName")
        deviceNum = params.get("deviceNum")
        deviceType = params.get("deviceType")
        deviceAddr = params.get("deviceAddr")
        deviceModel = params.get("deviceModel")
        ip = params.get("ip")
        port = params.get("port")
        connectionType = params.get("connectionType")
        controllerType = params.get("controllerType")

        my_db = ToMongo('wavedevice')

        deviceId = uuid.uuid4().hex
        createTime = updateTime = datetime.now()

        item = {
            "device_name": deviceName,
            "device_addr": deviceAddr,
            "device_num": deviceNum,
            "device_status": "1",  # 默认不在线
            "device_model": deviceModel,
            "device_id": deviceId,
            "create_time": createTime,
            "update_time": updateTime,
            "offline_time": createTime,
            "ip":ip,
            "port":port,
            "connection_type":connectionType,
            "controller_type":controllerType
        }

        total_addr_list = get_total_addr(my_db, deviceId, deviceType)
        if deviceAddr in total_addr_list:
            error_reponse = set_fail_result()
            error_reponse["errorCodeDesc"] = "地址位已存在"
            return jsonify(error_reponse)
        
        phoneNumber = params.get("phoneNumber")
        smsNumber = params.get("smsNumber")
        audioId = params.get("audioId")
        related_item =  {"phone_number": phoneNumber,
                        "sms_number": smsNumber,
                        "audio_id": audioId}

        if deviceType == '1':
            # 气体探测器
            item_extra = {
                "density": params.get("density"),
                "high_density_alarm": params.get("highDensityAlarm")
            }
            item_all = dict(item, **item_extra)
            my_db.insert("odin_dynamic_gas", item_all)

            newItem = dict(item_all,**related_item)
            newItem = database_to_dict(newItem,gas_db,gas_web)
            newItem['highDensityAlarm'] = json.dumps(newItem['highDensityAlarm'])
            sync_thread = Thread(target=sync_dev,args=[newItem,SYNC_GAS])
            sync_thread.start()

        elif deviceType == '2':
            # 漏电断路器
            volt_param = params.get("volt")
            current_param = params.get("current") 
            item_extra = {
                "distribution_num": params.get("distributionNum"),
                "volt_type": params.get("voltType"),
                "volt": volt_param,
                "current": current_param,
                "high_volt_alarm": params.get("highVoltAlarm"),
                "low_volt_alarm": params.get("lowVoltAlarm"),
                "leakage_alarm": params.get("leakageAlarm"),
                "high_cur_alarm": params.get("highCurAlarm")
            }
            item_all = dict(item, **item_extra)
            my_db.insert("odin_dynamic_leakage", item_all)

            newItem = dict(item_all,**related_item)
            newItem = database_to_dict(newItem,leakage_db,leakage_web)
            newItem['highVoltAlarm'] = json.dumps(newItem['highVoltAlarm'])
            newItem['lowVoltAlarm'] = json.dumps(newItem['lowVoltAlarm'])
            newItem['leakageAlarm'] = json.dumps(newItem['leakageAlarm'])
            newItem['highCurAlarm'] = json.dumps(newItem['highCurAlarm'])
            newItem['volt'] = json.dumps(newItem['volt'])
            newItem['current'] = json.dumps(newItem['current'])
            sync_thread = Thread(target=sync_dev,args=[newItem,SYNC_LEAKAGE])
            sync_thread.start()

        elif deviceType == '3':
            # 静电接地器
            my_db.insert("odin_dynamic_static_electricity", item)
            newItem = database_to_dict(item,eleground_db,eleground_web)
            sync_thread = Thread(target=sync_dev,args=[newItem,SYNC_GND])
            sync_thread.start()


        if phoneNumber or smsNumber or audioId:
            related_item['device_id'] = deviceId
            related_item['device_type'] = deviceType
            my_db.insert("odin_dynamic_associate", related_item)

        # 重新拉取动环任务
        instance = SerialNetServer(context=None)
        instance.getTask()

        response = set_success_result()
        return jsonify(response)

    except Exception as e:
        error_reponse = set_fail_result()
        error_reponse['errorCodeDesc'] = "添加失败"
        mainlogger.exception(e)
        return jsonify(error_reponse)


@bp.route('/dynamicdevice/addAudioDevice', methods=['POST'])
# @login_required
def addAudioDevice():
    '''
    增加声光告警器
    '''
    try:
        params = request.get_json()
        connectionType = params.get("connectionType")
        controllerType = params.get("controllerType")
        ip = params.get("ip")
        port = params.get("port")
        deviceModel = params.get("deviceModel")
        deviceName = params.get("deviceName")
        deviceNum = params.get("deviceNum")

        my_db = ToMongo('wavedevice')
        deviceId = uuid.uuid4().hex
        createTime = updateTime = datetime.now()

        if connectionType == '1':
            # 485方式                       
            deviceAddr = params.get("deviceAddr")        
            total_addr_list = get_total_addr(my_db, deviceId, deviceType="4")
            if deviceAddr in total_addr_list:
                error_reponse = set_fail_result()
                error_reponse["errorCodeDesc"] = "地址位已存在"
                return jsonify(error_reponse)

            item = {
                "deviceName": deviceName,
                "deviceAddr": deviceAddr,
                "deviceNum": deviceNum,
                "deviceStatus": "1",  # 默认不在线
                "offlineTime":datetime.now(),
                "deviceModel": deviceModel,
                "deviceId": deviceId,
                "createTime": createTime,
                "updateTime": updateTime,
                "connectionType":connectionType,
                "controllerType":controllerType,
                "ip": ip,
                "port": port
            }

        else:
            # 网络控制器
            resetDelayTime = params.get("resetDelayTime")
            channelNumber = params.get("channelNumber")

            item = {
                "ip": ip,
                "port": port,
                "resetDelayTime": resetDelayTime,
                "channelNumber": channelNumber,
                "deviceStatus": "1",  # 默认不在线
                "offlineTime":datetime.now(),
                "deviceModel": deviceModel,
                "deviceId": deviceId,
                "createTime": createTime,
                "updateTime": updateTime,
                "connectionType":connectionType,
                "controllerType":controllerType,
                "deviceName": deviceName,
                "deviceNum": deviceNum,
            }
        # 声光告警器
        sync_thread = Thread(target=sync_dev,args=[item,SYNC_AUDIO])
        sync_thread.start()
        item = database_to_dict(item, audio_web, audio_db)
        my_db.insert("odin_dynamic_audio", item)

        if connectionType == '1':
            # 重新拉取动环任务
            instance = SerialNetServer(context=None)
            instance.get_audio_task()

        response = set_success_result()
        return jsonify(response)

    except Exception as e:
        error_reponse = set_fail_result()
        error_reponse['errorCodeDesc'] = "添加失败"
        mainlogger.exception(e)
        return jsonify(error_reponse)


@bp.route('/dynamicdevice/updateAudioDevice', methods=['POST'])
# @login_required
def updatetAudioDevice():
    '''
    编辑声光告警器
    '''
    params = request.get_json()
    connectionType = params.get("connectionType")
    controllerType = params.get("controllerType")
    ip = params.get("ip")
    port = params.get("port")
    deviceModel = params.get("deviceModel")
    deviceName = params.get("deviceName")
    deviceNum = params.get("deviceNum")

    deviceId = params.get("deviceId")

    my_db = ToMongo('wavedevice')
    updateTime = datetime.now()
    if connectionType == '1':
        # 485方式            
        deviceAddr = params.get("deviceAddr")

        total_addr_list = get_total_addr(my_db, deviceId, deviceType="4")
        if deviceAddr in total_addr_list:
            error_reponse = set_fail_result()
            error_reponse["errorCodeDesc"] = "地址位已存在"
            return jsonify(error_reponse)
       
        item = {
            "device_name": deviceName,
            "device_addr": deviceAddr,
            "device_num": deviceNum,
            "device_model": deviceModel,
            "update_time": updateTime,
            "connection_type":connectionType,
            "controller_type":controllerType,
            "ip": ip,
            "port": port
        }

    else:
        # 网络控制器   
        ip = params.get("ip")
        port = params.get("port")
        resetDelayTime = params.get("resetDelayTime")
        channelNumber = params.get("channelNumber")

        item = {
            "ip": ip,
            "port": port,
            "reset_delay_time": resetDelayTime,
            "channel_number": channelNumber,
            "device_model": deviceModel,
            "update_time": updateTime,
            "connection_type":connectionType,
            "controller_type":controllerType,
            "device_name": deviceName,
            "device_num": deviceNum
        }
    # 声光告警器
    my_db.update("odin_dynamic_audio", {"device_id": deviceId}, {"$set": item})

    newItem = database_to_dict3(item,audio_db,audio_web)
    newItem['deviceId'] = deviceId
    sync_thread = Thread(target=sync_dev,args=[newItem,SYNC_AUDIO])
    sync_thread.start()

    if connectionType == '1':
        # 重新拉取动环任务
        instance = SerialNetServer(context=None)
        instance.get_audio_task()

    response = set_success_result()
    return jsonify(response)


@bp.route('/dynamicdevice/getAudioDeviceInfo', methods=['POST'])
# @login_required
def getAudioDeviceInfo():
    '''
    查询声光告警器
    '''
    params = request.get_json()
    deviceId = params.get('deviceId')

    my_db = ToMongo('wavedevice')
    col = my_db.get_col("odin_dynamic_audio")

    item = col.find_one({"device_id": deviceId})
    deviceInfo = {}
    if item:
        deviceInfo = database_to_dict(item, audio_db, audio_web)
        createTime = deviceInfo["createTime"]
        deviceInfo["createTime"] = int(createTime.timestamp()) * 1000
        offlineTime = deviceInfo.get("offlineTime")
        if offlineTime:
            deviceInfo["offlineTime"] = offlineTime.strftime('%Y-%m-%d %H:%M')
        else:
            deviceInfo["offlineTime"] = createTime.strftime('%Y-%m-%d %H:%M')

    response = set_success_result()
    response["deviceInfo"] = deviceInfo
    return jsonify(response)

@bp.route('/dynamicdevice/getAudioEmergency', methods=['POST'])
# @login_required
def getAudioEmergency():
    '''
    查询声光告警器告警纪录
    '''
    params = request.get_json()
    deviceId = params.get('deviceId')
    page = params.get("page")
    pageSize = params.get("pageSize")
    beginTime = params.get("beginTime")
    endTime = params.get("endTime")

    query = dict()
    if deviceId:
        query['audio_id'] = deviceId
    if beginTime or endTime:
        beginTime = datetime.strptime(beginTime, "%Y-%m-%d %H:%M:%S")
        endTime = datetime.strptime(endTime, "%Y-%m-%d %H:%M:%S")
        query['create_time'] = {"$gte": beginTime, "$lt": endTime}
    if page and pageSize:
        num = pageSize * (page - 1)
    else:
        pageSize = 10
        num = 0

    my_db = ToMongo('wavedevice')
    col = my_db.get_col("odin_bussiness_audio_record")

    res = col.find(query).sort("create_time", -1)
    totalNum = res.count()
    pages = totalNum // pageSize + 1
    items = res.skip(num).limit(pageSize)

    result = []
    for item in items:
        newItem = dict()
        newItem['audioId'] = item['audio_id']
        newItem['emergencyType'] = item['emergency_type']
        createTime = item.get('create_time')
        newItem['createTime'] = int(createTime.timestamp()) * 1000
        result.append(newItem)

    response = set_success_result()
    response["list"] = result
    response["page"] = page
    response["pageSize"] = pageSize
    response["totalCount"] = totalNum
    return jsonify(response)


@bp.route('/dynamicdevice/queryAudioDeviceList', methods=['POST'])
# @login_required
def queryAudioDeviceList():
    '''
    查询声光告警器 列表
    '''
    params = request.get_json()
    deviceName = params.get("deviceName")
    page = params.get("page")
    pageSize = params.get("pageSize")

    my_db = ToMongo('wavedevice')
    col = my_db.get_col("odin_dynamic_audio")

    query = dict()
    if deviceName:
        query['device_name'] = {"$regex": deviceName}

    if page and pageSize:
        num = pageSize * (page - 1)
    else:
        pageSize = 10
        num = 0

    res = col.find(query)
    totalNum = res.count()
    pages = totalNum // pageSize + 1
    items = res.skip(num).limit(pageSize)

    audioDeviceEntities = []
    for item in items:
        newItem = database_to_dict(item, audio_db, audio_web)
        createTime = newItem.get('createTime')
        offlineTime = newItem.get('offlineTime')
        if createTime:
            newItem['createTime'] = int(createTime.timestamp()) * 1000
        newItem['offlineTime'] = offlineTime.strftime('%Y-%m-%d %H:%M') if offlineTime else None
        audioDeviceEntities.append(newItem)

    response = set_success_result()
    response['audioDeviceEntities'] = audioDeviceEntities
    response['page'] = pages
    response['pageSize'] = pageSize
    response['totalCount'] = totalNum
    return jsonify(response)


@bp.route('/dynamicdevice/deleteAudioDevice', methods=['POST'])
# @login_required
def deletetAudioDevice():
    '''
    删除声光告警器
    '''
    params = request.get_json()
    deviceId = params.get('deviceId')

    my_db = ToMongo('wavedevice')

    my_db.delete("odin_dynamic_audio", {"device_id": deviceId})

    delete_thread = Thread(target=sync_deleteDev,args=[deviceId,'4'])
    delete_thread.start()

    # 重新拉取动环任务
    instance = SerialNetServer(context=None)
    instance.get_audio_task()

    response = set_success_result()
    return jsonify(response)


@bp.route('/dynamicdevice/startAudioAlarm', methods=['POST'])
# @login_required
def startAudioAlarm():
    '''
    开始声光告警
    '''
    params = request.get_json()
    deviceId = params.get('deviceId')

    my_db = ToMongo('wavedevice')
    col = my_db.get_col('odin_dynamic_audio')
    item = col.find_one({'device_id': deviceId})

    try:
        add_type = item.get('connection_type')
        if item and add_type == '1':
            # 485方式添加的声光告警器
            deviceAddr = item.get('device_addr')
            equipId = item.get('device_id')
            ip = item.get('ip')
            port = item.get('port')
            addr = (ip,int(port))
            task_item = {'deviceAddr': deviceAddr, 'equipId': equipId, 'stopFlag': -1}
            instance = SerialNetServer(context=None)
            instance.alarm_audio(addr,task_item)
    except Exception as e:
        mainlogger.exception(e)

    response = set_success_result()
    return jsonify(response)


@bp.route('/dynamicdevice/stopAudioAlarm', methods=['POST'])
# @login_required
def stopAudioAlarm():
    '''
    停止声光告警
    '''
    params = request.get_json()
    deviceId = params.get('deviceId')

    my_db = ToMongo('wavedevice')
    col = my_db.get_col('odin_dynamic_audio')
    item = col.find_one({'device_id': deviceId})
    add_type = item.get('connection_type')

    if item and add_type == '1':
        # 485方式添加的声光告警器
        deviceAddr = item.get('device_addr')
        equipId = item.get('device_id')
        ip = item.get('ip')
        port = item.get('port')
        addr = (ip,int(port))
        task_item = {'deviceAddr': deviceAddr, 'equipId': equipId, 'stopFlag': 2}
        instance = SerialNetServer(context=None)
        instance.alarm_audio(addr,task_item)

    response = set_success_result()
    return jsonify(response)


@bp.route('/dynamicemergency/queryDynamicEmergency', methods=['POST'])
# @login_required
def queryDynamicEmergency():
    '''
    获取动环告警纪录
    '''
    try:
        params = request.get_json()
        deviceName = params.get("deviceName")
        deviceType = params.get("deviceType")
        deviceId = params.get("deviceId")
        page = params.get("page")
        pageSize = params.get("pageSize")
        beginTime = params.get("beginTime")
        endTime = params.get("endTime")

        emergencyLevel = params.get("emergencyLevel")
        emergencyType = params.get("emergencyType")

        my_db = ToMongo('wavedevice')
        col = my_db.get_col("odin_business_dynamic_emergency_record")
        if deviceType == '2':
            device_col = my_db.get_col("odin_dynamic_leakage")

        query = dict()
        if deviceName:
            query['device_name'] = {"$regex": deviceName}
        if deviceType:
            query['device_type'] = deviceType
        if deviceId:
            query['device_id'] = deviceId
        if beginTime or endTime:
            beginTime = datetime.strptime(beginTime, "%Y-%m-%d %H:%M:%S")
            endTime = datetime.strptime(endTime, "%Y-%m-%d %H:%M:%S")
            query['emergency_time'] = {"$gte": beginTime, "$lt": endTime}

        if emergencyType:
            query['emergency_type'] = emergencyType
        if emergencyLevel:
            query['emergency_level'] = emergencyLevel

        if page and pageSize:
            num = pageSize * (page - 1)
        else:
            pageSize = 10
            num = 0

        res = col.find(query).sort("emergency_time", -1)
        totalNum = res.count()
        pages = totalNum // pageSize + 1
        items = res.skip(num).limit(pageSize)

        deviceEntityList = []

        for item in items:
            newItem = database_to_dict(item, dynamic_emergency_database, dynamic_emergency_web)
            if newItem['emergencyTime']:
                newItem['emergencyTime'] = int(newItem['emergencyTime'].timestamp()) * 1000
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
        error_reponse['exceptionCodeDesc'] = "Error:%s" % e
        mainlogger.info("queryDynamicEmergency error:%s" % e)
        return jsonify(error_reponse)


@bp.route('/devicemodel/getNetController', methods=['POST'])
# @login_required
def getNetController():
    '''
    查询康奈德类型
    '''
    try:
        params = request.get_json()
        publicDictType = params.get("publicDictType")

        my_db = ToMongo('wavedevice')
        col = my_db.get_col("public_dict_baseinfo")
        query = {"public_dict_type": publicDictType}
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
        error_reponse['exceptionCodeDesc'] = "Error:%s" % e
        mainlogger.info("getNetController error:%s" % e)
        return jsonify(error_reponse)


@bp.route('/dynamicdevice/modelList', methods=['POST'])
# @login_required
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
            newItem = database_to_dict(item, kndmode_database, kndmode_web)
            data.append(newItem)

        response = set_success_result()
        response['data'] = data

        return jsonify(response)

    except Exception as e:
        error_reponse = set_fail_result()
        error_reponse['errorCodeDesc'] = "查询失败"
        error_reponse['exceptionCodeDesc'] = "Error:%s" % e
        mainlogger.info("query modelList error:%s" % e)
        return jsonify(error_reponse)

from Utils.db import ToMongo
from .system_misc import database_to_dict,insert_sound_server,filter_sound_info
from .sys_config import *
from Utils.voicedevice_utils import LingsSound,VoiceBoxUtils
import Utils.logger as logger
from datetime import datetime
from device.temp_service import TempServer

mainlogger = logger.getLogger('main')

def insert_dynamic_info(my_db:ToMongo,dynamicInfo):
    '''
    接口说明：saas同步动环设备信息
    '''
    if not dynamicInfo:
        return
    pointList = dynamicInfo.get("pointList")
    dynamicThreshold = dynamicInfo.get("dynamicThreshold")
    modelList = dynamicInfo.get("modelList")
    dynamicDeviceList = dynamicInfo.get("dynamicDeviceList")
    soundNos = dynamicInfo.get("soundNos")
    soundService = dynamicInfo.get("soundService")

    my_db.delete('odin_point',{},is_one=False)
    if pointList:
        #插入动环点位
        my_db.delete("odin_point",{},is_one=False)
        for pointItem in pointList:
            point_item = database_to_dict(pointItem,dynamic_point_web,dynamic_point_database)
            point_item['update_time'] = datetime.strptime(point_item['update_time'],"%Y-%m-%d %H:%M:%S")
            point_item['create_time'] = datetime.strptime(point_item['create_time'],"%Y-%m-%d %H:%M:%S")
            my_db.insert("odin_point",point_item)

    my_db.delete('odin_business_dynamic_threshold',{},is_one=False)
    if dynamicThreshold:
        #插入动环温度阈值
        threItem = my_db.get_col("odin_business_dynamic_threshold").find_one()
        thre_item = database_to_dict(dynamicThreshold,threhold_web,threhold_database)
        temp_max = thre_item.get("temperature_max")
        temp_min = thre_item.get("temperature_min")
        if temp_max and temp_min:
            TempInstance = TempServer(context=None)
            TempInstance.set_temp_threhold(temp_max=temp_max,temp_min=temp_min)
        if threItem:
            my_db.update("odin_business_dynamic_threshold",{},{"$set":thre_item})
        else:
            my_db.insert("odin_business_dynamic_threshold",thre_item)

    my_db.delete('odin_dynamic_device_model',{},is_one=False)
    if modelList:
        my_db.delete("odin_dynamic_device_model",{},is_one=False)
        for modelItem in modelList:
            model_item = database_to_dict(modelItem,dynamic_model_web,dynamic_model_database)
            my_db.insert("odin_dynamic_device_model",model_item)

    if soundService:
        #插入音响服务
        insert_sound_server(my_db,soundService)

    my_db.delete('odin_device_sound',{"use_by":"1"},is_one=False)
    if soundNos:
        #插入音响设备
        insert_sound_device(my_db,soundNos,soundService)

    my_db.delete('odin_dynamic_device',{},is_one=False)
    if dynamicDeviceList:
        #插入动环设备
        insert_dynamic_device(my_db,dynamicDeviceList)

def insert_sound_device(my_db:ToMongo,soundNos,soundServiceEntity):
    #联网版动环插入音响设备
    if not soundNos or not soundServiceEntity:
        return
    serviceAddress = soundServiceEntity.get('serviceAddress')
    servicePort = soundServiceEntity.get('servicePort')
    serviceType = soundServiceEntity.get('serviceType')
    account = soundServiceEntity.get('account')
    pwd = soundServiceEntity.get('pwd')
    serverUrl = "http://%s:%s"%(serviceAddress,servicePort)
    my_db.delete('odin_device_sound',{"use_by":"1"},is_one=False) # 删除动环关联的音响
    sound_col = my_db.get_col("odin_device_sound")
    sound_id_list = sound_col.distinct('sound_id')

    DeviceSoundEntities = {}
    if serviceType == 2:   
         #菱声音响
        try:
            Linginstance = LingsSound(tts_url=None,server_url=serverUrl,sound_no=None,volume=100)            
            response = Linginstance.login(account=account,password=pwd)
            token = response['user']['token']
            devices_info = Linginstance.getTerminalinfo(token=token)
            if 'rows' in devices_info.keys():
                rows = devices_info['rows']
                for item in rows:
                    type = item['type']
                    if type == '0001':
                        #类型为采集器
                        continue
                    sound_ip = item['extra']['ip']
                    sound_mac = item['sn']
                    soundStatus = "0"
                    res = {"soundIp":sound_ip,
                        "soundNo":sound_mac,
                        "soundStatus":soundStatus,
                        "soundType":"2",
                        'soundPort':8888}
                    DeviceSoundEntities[sound_mac] = res
        except Exception as e:
            mainlogger.debug("--同步菱声告警音响error:%s;\n--serverUrl:%s,account:%s,pwd:%s"%(e,serverUrl,account,pwd))

    elif serviceType == 1:
        #itc音响
        try:
            VoiceInstance = VoiceBoxUtils(serverUrl,account,pwd,volume=70)
            VoiceInstance.login()
            terminal_info = VoiceInstance.getterminalinfo().json()
            result = terminal_info['result']
            if result == 200:
                EndPointsArray = terminal_info['data']['EndPointsArray']
                for item in EndPointsArray:
                    sound_ip = item['EndpointIP']
                    sound_mac = item['EndpointMac']
                    soundStatus = "0"
                    res = {"soundIp":sound_ip,
                        "soundNo":sound_mac,
                        "soundStatus":soundStatus,
                        "soundType":"1"}
                    DeviceSoundEntities[sound_mac] = res
        except Exception as e:
            mainlogger.debug("--同步itc告警音响error:%s;\n--serverUrl:%s,account:%s,pwd:%s"%(e,serverUrl,account,pwd))

    for entity in soundNos:
        soundId = entity.get("soundId")
        if soundId in sound_id_list:
            continue
        equName = entity.get("equName")
        mac = entity.get("mac")
        info = DeviceSoundEntities.get(mac)
        if info:
            soundItem = database_to_dict(info,sound_web,sound_database)
            soundItem["sound_id"] = soundId
            soundItem["sound_name"] = equName
            soundItem["use_by"] = "1" #表示音响是动环使用
            my_db.insert("odin_device_sound",soundItem)

def insert_dynamic_device(my_db:ToMongo,dynamicDeviceList):
    #插入动环设备
    if not dynamicDeviceList:
        return
    for dynamicItem in dynamicDeviceList:
        item = database_to_dict(dynamicItem,dynamic_device_web,dynamic_device_database)
        item['update_time'] = datetime.strptime(item['update_time'],"%Y-%m-%d %H:%M:%S")
        item['create_time'] = datetime.strptime(item['create_time'],"%Y-%m-%d %H:%M:%S")
        my_db.insert("odin_dynamic_device",item)


        
    

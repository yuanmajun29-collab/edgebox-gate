import json
import time
import requests
from datetime import datetime
from threading import Thread
from .system_misc import dt2str,database_to_dict,get_base_info
from .system_sync import register_device,query_edge_service
import utils.logger as logger
import utils.glv as glv
from utils.db import ToMongo
from utils.datacfg import *
from config import NetAgreementType,BASE_INFO

HEART_BEAT ="/business/sync/heartBeat"
REGISTER_DEVICE = "/business/sync/registerDevice"
SYNC_ALL_DATA = "/business/sync/allDevice"

SYNC_ALG_SET = "/business/sync/algorithmModelSetting"   #同步算法模型设置
SYNC_AUDIO = "/business/sync/audio"    #同步声光告警器
SYNC_CAMERA = "/business/sync/camera"   #同步摄像机
SYNC_DELETE_AUDIO = "/business/sync/deleteAudio"  #删除声光告警器
SYNC_DELETE_CAM = "/business/sync/deleteCamera"  #删除摄像机
SYNC_DELETE_GAS = "/business/sync/deleteGas"  #删除气体探测器
SYNC_DELETE_LEAKAGE = "/business/sync/deleteLeakage"  #删除断路器
SYNC_DELETE_GND = "/business/sync/deleteStaticElectricity"   #删除静电接地器

SYNC_AREA = "/business/sync/deviceArea"   #同步设备区域信息
SYNC_GAS = "/business/sync/gas"   #同步气体探测器
SYNC_P2P = "/business/sync/getCtP2pAccountInfo"   #同步穿透P2P账号信息
SYNC_LEAKAGE = "/business/sync/leakage"   #同步断路器
SYNC_GND = "/business/sync/staticElectricity"   #同步静电接地器
SYNC_EMERGENCY = "/business/sync/synAddAllEmergency"   #同步告警接口
SYNC_FILE_MINIO = "/business/sync/synFileToMinio"   #同步告警数据进Minio

SYNC_DYNAMIC_EMERGENCY = "/business/sync/synDynamicEmergencyRecord"
SYNC_DYNAMIC_STATUS = "/business/sync/synDynamicDeviceStatus"

mainlogger = logger.getLogger('main')

def init_param(item):
    address = item.get('service_address')
    model = item.get('model')
    organization_id = item.get('organization_id')
    bind_organization_id = item.get('bind_organization_id')
    device_sn = item.get('device_sn')
    glv.init()
    mainlogger.info('--初始化全局变量 param:%s'%item)
    glv.set_value('remote_url',value=address)
    glv.set_value('model',value=model)
    glv.set_value('device_sn',value=device_sn)
    glv.set_value('organization_id',value=organization_id)
    glv.set_value('bind_organization_id',value=bind_organization_id)
    return

def check_service_addr(address:str):
    try:
        if not address:
            return 
        if address.startswith('http://') or address.startswith('https://'):
            return address
        else:
            result = NetAgreementType + '://' + address
            return result
    except Exception as e:
        mainlogger.exception(e)
        return 

def sync_post(remote_url, content):
    try:
        headers = {'Content-Type': 'application/json'}
        resp = requests.post(remote_url, data=json.dumps(content), headers=headers, verify=False)
        answer = resp.json()
        return answer
    except Exception as e:
        answer = {'error':'%s'%e}
        return answer
    
def sync_delete(remote_url):
    try:
        headers = {'Content-Type': 'application/json'}
        resp = requests.delete(remote_url,headers=headers, verify=False)
        answer = resp.json()
        return answer
    except Exception as e:
        answer = {'error':'%s'%e}
        return answer

def sync_deleteDev(device_id,dev_type):
    '''
    dev_type  1气体探测器 2断路器 3接地器 4声光告警器 5摄像机
    '''
    try:
        model = glv.get_value('model')
        url = glv.get_value('remote_url')
        if model != '1' or not url:
            return
    #    content = {'deviceId':device_id}
        if dev_type == '1':
            remote_url = url + SYNC_DELETE_GAS
        elif dev_type == '2':
            remote_url = url + SYNC_DELETE_LEAKAGE
        elif dev_type == '3':
            remote_url = url + SYNC_DELETE_GND
        elif dev_type == '4':
            remote_url = url + SYNC_DELETE_AUDIO
        else:
            remote_url = url + SYNC_DELETE_CAM
        #    content = {'cameraId':device_id}   
        remote_url = remote_url + '/' + device_id
        resp = sync_delete(remote_url)
        mainlogger.info('--SyncDeleteDev resp:%s'%resp)
    except Exception as e:
        mainlogger.Exception(e)

def sync_postDev(url,content):
    try:
        model = glv.get_value('model')
        plat_url = glv.get_value('remote_url')
        if model != '1' or not plat_url:
            return
        remote_url = plat_url + url
        resp = sync_post(remote_url,content)
    except Exception as e:
        mainlogger.exception(e)

def sync_dev(item,url):
    '''
    新增时,同步设备信息  包括断路器、声光告警器、气体探测器
    、静电接地器、摄像机
    '''
    try:
        model = glv.get_value('model')
        plat_url = glv.get_value('remote_url')
        if model != '1' or not plat_url:
            return     
           
        organizationId = glv.get_value('organization_id')
        bindOrganizationId = glv.get_value('bind_organization_id')
        deviceSn = glv.get_value('device_sn')

        createTime = item.get("createTime")
        offlineTime = item.get("offlineTime")
        if createTime:
            item['createTime'] = dt2str(createTime)
        if offlineTime:
            item['offlineTime'] = dt2str(createTime)
        item['organizationId'] = organizationId
        item['bindOrganizationId'] = bindOrganizationId
        item['deviceSn'] = deviceSn
        remote_url = plat_url + url
        content = [item]
        resp = sync_post(remote_url,content=content)
        mainlogger.info("--SyncDynamicDev resp :%s ;\n content:%s;"%(resp,content))
    except Exception as e:
        mainlogger.exception(e)

def sync_alg_setting(item):
    '''
    同步算法设置
    '''
    try:
        mainlogger.info("glv.global_dict:%s"%glv._global_dict)
        model = glv.get_value('model')
        plat_url = glv.get_value('remote_url')
        if model != '1' or not plat_url:
            return
        organizationId = glv.get_value('organization_id')
        bindOrganizationId = glv.get_value('bind_organization_id')
        deviceSn = glv.get_value('device_sn')
        item['organizationId'] = organizationId
        item['bindOrganizationId'] = bindOrganizationId
        item['deviceSn'] = deviceSn       
        remote_url = plat_url + SYNC_ALG_SET
        resp = sync_post(remote_url,content=item)
        mainlogger.info("--SyncAlgSetting resp :%s ;\n content:%s;"%(resp,item))
    except Exception as e:
        mainlogger.exception(e)
    return

def sync_dev_status(item:list):
    '''
    同步设备状态
    '''
    try:
        model = glv.get_value('model')
        plat_url = glv.get_value('remote_url')
        if model != '1' or not plat_url:
            return     
        
        remote_url = plat_url + SYNC_DYNAMIC_STATUS
        resp = sync_post(remote_url,content=item)
        mainlogger.info("--SyncDynamicStatus resp :%s ;\n content:%s;"%(resp,item))
    except Exception as e:
        mainlogger.exception(e)

def sync_dynamic_emergency(item):
    '''
    同步动环设备告警
    '''
    try:
        model = glv.get_value('model')
        if model != '1':
            return 
        item = database_to_dict(item,dynamic_emergency_database,dynamic_emergency_web)       
        item['emergencyTime'] = dt2str(item['emergencyTime'])
        plat_url = glv.get_value('remote_url')
        remote_url = plat_url + SYNC_DYNAMIC_EMERGENCY
        resp = sync_post(remote_url,content=item)
        mainlogger.info("--SyncDynamicEmergency url :%s ; resp:%s;"%(remote_url,resp))
    except Exception as e:
        mainlogger.exception(e)

def sync_camera(my_db,item):
    try:
        mainlogger.info("glv._global_dict:%s"%glv._global_dict)
        model = glv.get_value('model')
        plat_url = glv.get_value('remote_url')
        if model != '1' or not plat_url:
            return     
        organizationId = glv.get_value('organization_id')
        bindOrganizationId = glv.get_value('bind_organization_id')
        deviceSn = glv.get_value('device_sn')

        newItem = database_to_dict(item,camerakeys_database,camerakeys_web)
        newItem['createTime'] = dt2str(newItem['createTime'])
        newItem['updateTime'] = dt2str(newItem['updateTime'])
        newItem['offlineTime'] = dt2str(newItem['offlineTime'])
        newItem['organizationId'] = organizationId
        newItem['bindOrganizationId'] = bindOrganizationId
        newItem['deviceSn'] = deviceSn
    #    newItem['offlineTime'] = dt2str(newItem['offlineTime'])

        area_col = my_db.get_col('odin_device_area')
        areaId = newItem.get('areaId')
        query = {'area_id':areaId}
        area_item = area_col.find_one(query)
        area_name = area_item.get('area_name') if area_item else None
        newItem['areaName'] = area_name

        remote_url = plat_url + SYNC_CAMERA
        content = [newItem]
        resp = sync_post(remote_url,content=content)
        mainlogger.info("--sync_camera url :%s ; resp:%s; content:%s"%(remote_url,resp,content))
    except Exception as e:
        mainlogger.exception(e)

def sync_area(item):
    '''
    同步设备区域信息
    '''
    try:
        model = glv.get_value('model')
        plat_url = glv.get_value('remote_url')
        if model != '1' or not plat_url:
            return        
        item['createTime'] = dt2str(item['createTime'])
        item['updateTime'] = dt2str(item['updateTime'])       
        remote_url = plat_url + SYNC_AREA
        resp = sync_post(remote_url,content=item)
    except Exception as e:
        mainlogger.exception(e)

def init_box_model():
    '''
    盒子掉电重启后，工作模式为联网模式；
    '''
    my_db = ToMongo('wavedevice')
    model_col = my_db.get_col('authority_work_model')
    item = model_col.find_one()
    model = item.get('model')
    address = item.get('service_address')
    organization_id = item.get('organization_id')
    bind_organization_id = item.get('service_organization_id')

    chip_sn,product_sn,hardware_version = get_base_info()
    num = my_db.get_col("authority_base_info").find().count()
    if num == 0:
        base_config = BASE_INFO     
        base_config['equipment_model'] = chip_sn  
        base_config['equipment_serial_number'] = product_sn
        base_config['hardware_version'] = hardware_version
        base_config['create_time'] = datetime.now()
        base_config['last_modify_time'] = datetime.now()
        my_db.insert('authority_base_info',base_config)
    else:
        print("----------设备基本信息初始化----------")
        print("product_sn : ",product_sn)
        print("chip_sn : ",chip_sn)
        print("hardware_version : ",hardware_version)
        print("web_version : ",BASE_INFO['web_version'],'\n')
        item = {}
        item['equipment_serial_number'] = product_sn
        item['equipment_model'] = chip_sn
        item['hardware_version'] = hardware_version
        item['last_modify_time'] = datetime.now()
        item['web_version'] = BASE_INFO['web_version']
        my_db.update('authority_base_info',{},{"$set":item})

    item = {'model':model,
            'device_sn':chip_sn,
            'service_address':address,
            'organization_id':organization_id,
            'bind_organization_id':bind_organization_id}
    init_param(item)

    if model == '1':
        # 开启轮询心跳接口的进程
        sync_data = SyncTimer()
        sync_data.init_base_info()
        sync_data.heartbeat_thread()
    return

def get_camera_info(my_db:ToMongo):
    col = my_db.get_col('odin_device_camera_edit')
    area_col = my_db.get_col('odin_device_area')
    items = col.find()
    cameraInfoList = []
    for item in items:
        try:
            newItem = database_to_dict(item,camerakeys_database,camerakeys_web)
            newItem['createTime'] = dt2str(newItem['createTime'])
            newItem['updateTime'] = dt2str(newItem['updateTime'])
            newItem['offlineTime'] = dt2str(newItem['offlineTime'])
            area_id = newItem.get('areaId')
            area_item = area_col.find_one({'area_id':area_id})
            newItem['areaName'] = area_item.get('area_name')
            cameraInfoList.append(newItem)
        except Exception as e:
            mainlogger.exception(e)
            continue
    return cameraInfoList

def get_audio_info(my_db:ToMongo):
    col = my_db.get_col('odin_dynamic_audio')
    items = col.find()
    dynamicAudioList = []
    for item in items:
        try:
            newItem = database_to_dict(item,audio_db,audio_web)
            newItem['createTime'] = dt2str(newItem['createTime'])
            newItem['offlineTime'] = dt2str(newItem['offlineTime'])
            dynamicAudioList.append(newItem)
        except Exception as e:
            continue
    return dynamicAudioList
    
def get_gas_info(my_db:ToMongo):
    col = my_db.get_col('odin_dynamic_gas')
    asso_col = my_db.get_col('odin_dynamic_associate')
    items = col.find()
    dynamicGasList = []
    for item in items:
        try:
            newItem = database_to_dict(item,gas_db,gas_web)
            newItem['createTime'] = dt2str(newItem['createTime'])
            newItem['offlineTime'] = dt2str(newItem['offlineTime'])
            newItem['highDensityAlarm'] = json.dumps(newItem["highDensityAlarm"])
            deviceId = newItem.get('deviceId')
            item = asso_col.find_one({'device_id':deviceId})
            asso_item = {} if not item else item
            newItem['smsNumber'] = asso_item.get('sms_number')
            newItem['phoneNumber'] = asso_item.get('phone_number')
            newItem['audioId'] = asso_item.get('audio_id')
            dynamicGasList.append(newItem)
        except Exception as e:
            mainlogger.exception(e)
    return dynamicGasList

def get_leakage_info(my_db:ToMongo):
    col = my_db.get_col('odin_dynamic_leakage')
    asso_col = my_db.get_col('odin_dynamic_associate')
    items = col.find()
    dynamicLeakageList = []
    for item in items:
        try:
            newItem = database_to_dict(item,leakage_db,leakage_web)
            newItem['createTime'] = dt2str(newItem['createTime'])
            newItem['offlineTime'] = dt2str(newItem['offlineTime'])
            newItem["volt"] = json.dumps(newItem["volt"])
            newItem["current"] = json.dumps(newItem["current"])
            newItem["highVoltAlarm"] = json.dumps(newItem["highVoltAlarm"])
            newItem["highCurAlarm"] =  json.dumps(newItem["highCurAlarm"])
            newItem["lowVoltAlarm"] =  json.dumps(newItem["lowVoltAlarm"]) 
            newItem["leakageAlarm"] =  json.dumps(newItem["leakageAlarm"])
            deviceId = newItem.get('deviceId')
            item = asso_col.find_one({'device_id':deviceId})
            asso_item = {} if not item else item
            newItem['smsNumber'] = asso_item.get('sms_number')
            newItem['phoneNumber'] = asso_item.get('phone_number')
            newItem['audioId'] = asso_item.get('audio_id')
            dynamicLeakageList.append(newItem)
        except Exception as e:
            continue
    return dynamicLeakageList

def get_gnd_info(my_db:ToMongo):
    col = my_db.get_col('odin_dynamic_static_electricity')
    items = col.find()
    dynamicStaticElectricityList = []
    for item in items:
        try:
            newItem = database_to_dict(item,eleground_db,eleground_web)
            newItem['createTime'] = dt2str(newItem['createTime'])
            newItem['offlineTime'] = dt2str(newItem['offlineTime'])
            dynamicStaticElectricityList.append(newItem)
        except Exception as e:
            continue
    return dynamicStaticElectricityList

class SyncTimer():

    def __init__(self):
        self.my_db = ToMongo('wavedevice')
        self.interval_time = 30   #定时30s去同步数据
        self.remote_url = ""
        self.device_sn = "" 
        self.work_model = "1" 

    def init_base_info(self):
        edge_info = self.my_db.get_col('authority_work_model').find_one() 
        model_info = self.my_db.get_col('authority_base_info').find_one()
        self.work_model = edge_info['model']
        serviceAddress = edge_info['service_address']
        self.remote_url = serviceAddress
        self.device_sn = model_info['equipment_model']
        self.organization_id = edge_info['organization_id']
        self.bind_organization_id = edge_info['service_organization_id']

    def keep_heartbeat(self):
        try:
            url = self.remote_url + HEART_BEAT
            headers = {'Content-Type': 'application/json'}
            content = {"deviceSn":self.device_sn,"bindOrganizationId":self.bind_organization_id,"organizationId":self.organization_id}
            resp = requests.post(url,data=json.dumps(content),headers=headers,verify=False)
            resp = resp.json()
            mainlogger.info('--HeratBeat resp:%s'%resp)
        except Exception as e:
            mainlogger.info("keep_heartbeat error:%s"%e)

    def heartbeat_thread(self):
        mainlogger.info("--开启平台-盒子同步进程--")
        sync_thread = Thread(target=self.sync_func,args = [])
        sync_thread.start()

    def post_all_data(self):
        try:
            url = self.remote_url + SYNC_ALL_DATA
            headers = {'Content-Type': 'application/json'}
            content = {"deviceSn":self.device_sn,"bindOrganizationId":self.bind_organization_id,"organizationId":self.organization_id}
            content['cameraInfoList'] = get_camera_info(self.my_db)
            content['dynamicAudioList'] = get_audio_info(self.my_db)
            content['dynamicGasList'] = get_gas_info(self.my_db)
            content['dynamicLeakageList'] = get_leakage_info(self.my_db)
            content['dynamicStaticElectricityList'] = get_gnd_info(self.my_db)
            resp = requests.post(url,data=json.dumps(content),headers=headers,verify=False)
            resp = resp.json()
            mainlogger.info('--PostAllData content:%s'%content)
            mainlogger.info('--PostAllData resp:%s'%resp)
        except Exception as e:
            mainlogger.info("PostAllData error:%s"%e)

    def sync_func(self):

        while self.work_model == '1':
            work_model_item = self.my_db.get_col('authority_work_model').find_one() 
            self.work_model = work_model_item['model']
            if self.work_model == '0':
                break           
            # 保持与平台的心跳
            self.keep_heartbeat()
            time.sleep(self.interval_time)

import json
import os
import requests
import shutil
from datetime import datetime
from Utils.db import ToMongo
from config import EMERGENCY_IMG_PATH,PERSON_IMG_URL,FACE_IDENT_URL,BASE_INFO,NetAgreementType
from algorith_server.redis_connect import redis_database
from system.system_misc import *
from system.sys_config import *
from Utils.utils import set_fail_result,set_success_result
from threading import Thread,Timer
import Utils.logger as logger

import urllib3
urllib3.disable_warnings()  #禁用 https认证没有证书的 warning

mainlogger = logger.getLogger('main')

#PHONE_PWD_LOGIN = "/net-web/auth/account_phone_pwd_login"
PHONE_PWD_LOGIN = "/net-web/auth/loginByBox"
REGISTER_DEVICE = "/syn/registerDevice"

HEART_BEAT ="/syn/heartBeat"
SYN_PERSONNEL_INFO ="/net-web/syn/synPersonnelInfo"
SYN_DEVICE_POSITION="/net-web/syn/syncDevicePosition"
SYN_DEVICE_CAMERA="/net-web/syn/syncDeviceCamera"
SYN_CONTROL ="/net-web/syn/syncControlItem"
SYN_ALG_INFO = "/net-web/syn/synAlgorithmConstant"
SYN_DEVICE_ALG = "/syn/synDeviceAlgorithm"
SYN_BOX_STATE = "/syn/updateDeviceEdgeStatus"
format_pattern = '%Y-%m-%d %H:%M:%S'


def request_login_url(params):

    accessToken = params.get("accessToken", None)
    model = params.get("model", None)
    serviceAccount = params.get("serviceAccount", None)
    serviceAddress = params.get("serviceAddress", None)
    servicePort = params.get("servicePort", None)
    servicePwd = params.get("servicePwd", None)

    success_result = set_success_result()
    error_result = set_fail_result()
    
    remote_url = NetAgreementType + "://" + serviceAddress + ":" + servicePort
    url = remote_url + PHONE_PWD_LOGIN

    headers = {'Content-Type': 'application/json'}
    content = {"accountOrPhone":serviceAccount,"userPassword":servicePwd}

    re_pool = redis_database

    key = serviceAccount
    if re_pool.exists(key):
        count = re_pool.get(key).decode()
        count = int(count)
        if count >= 3:
            error_result['errorCodeDesc'] = '超过最大重试次数,请换账号重试'
            return error_result,None,None     

    try:
        ans = requests.post(url,data=json.dumps(content),headers=headers,verify=False)
        ans = ans.json()
        request_status = ans.get("requestStatus")
        organization_id = ans.get("organizationId")
        bind_organization_id = ans.get("bindOrganizationId")
    except:
        error_result['errorCodeDesc'] = '地址+端口号不正确，请确认输入正确的地址'
        return error_result,None,None 

    if request_status == "FAIL":
        overdue_time = 24 * 60 * 60
        if re_pool.exists(key):            
            count = int(re_pool.get(key).decode())
            re_pool.setex(key,overdue_time,count+1)
        else:
            re_pool.setex(key,overdue_time,1)
        error_result['errorCodeDesc'] = '账号/密码有误，请核对后再登陆。超过三次登陆失败，账号会锁住24小时！'
        return error_result,None,None 
    return success_result,organization_id,bind_organization_id

def init_data_version(my_db:ToMongo):
    base_info = my_db.get_col('authority_base_info').find_one() 
    organization_id = base_info['organization_id']
    device_sn = base_info['equipment_model']
    modify_time = datetime.now()
    namelist = ["device","control","personnel","address"]
    version_col = my_db.get_col('system_data_version')
    for name in namelist:
        query = {"name":name}
        x = version_col.find_one(query) 
        if x:
            item = {"version_number":2}
            my_db.update('system_data_version',query,{"$set":item})
        else:
            item = {"name":name,
                    "version_number":2,
                    "organization_id":organization_id,
                    "modify_time":modify_time,
                    "device_sn":device_sn }
            my_db.insert('system_data_version',item)

def init_box_model():
    '''
    盒子掉电重启后，工作模式为联网模式；
    '''
    my_db = ToMongo('wavedevice')
    model_col = my_db.get_col('authority_work_model')
    model = model_col.find_one()['model']
    if model == '1':

        #开启轮询心跳接口的进程
        sync_data = SyncDataTimer()
        sync_data.init_base_info()
        sync_data.check_version_thread()

def deleteAllData(my_db:ToMongo):

    #删除布控任务信息
    my_db.delete("odin_business_control_manage",{},is_one=False)
    my_db.delete("work_flow_mission",{},is_one=False)
    my_db.delete("work_flow_mission_device_associate",{},is_one=False)
    my_db.delete("work_flow_mission_personnel_associate",{},is_one=False)
    my_db.delete("work_flow_mission_personnelgroup_associate",{},is_one=False)
    my_db.delete("work_flow_insight_model_algorithm_instance",{},is_one=False)
    my_db.delete("odin_device_equip",{},is_one=False)

    #删除摄像头信息
    my_db.delete("odin_device_camera_edit",{},is_one=False)
    my_db.delete("odin_device_device_position_associate",{},is_one=False)   
    my_db.delete("odin_device_position",{},is_one=False)
    my_db.delete("centimani_storage_live_choose_record",{},is_one=False)

    #删除音箱设备信息
    my_db.delete("odin_device_itc_server",{},is_one=False)
    my_db.delete("odin_device_lings_server",{},is_one=False)
    my_db.delete("odin_device_sound",{},is_one=False)

    #删除roi信息
    my_db.delete("odin_device_roi_area_record",{},is_one=False)

    #删除用户日志
    my_db.delete("user_logs",{},is_one=False)  

    #删除消息管理中的消息
    my_db.delete("odin_advise_info",{},is_one=False)  

    #删除人脸库
    my_db.delete("work_flow_personnel",{},is_one=False)
    my_db.delete("work_flow_personnel_image",{},is_one=False)
    my_db.delete("work_flow_personnel_personnelgroup_associate",{},is_one=False)
    my_db.delete("work_flow_personnelgroup",{},is_one=False)

    #删除告警纪录
    my_db.delete("odin_business_emergency_record",{},is_one=False)
    my_db.delete("odin_business_emergency_record_detail_info",{},is_one=False)

    #删除短信投递
    my_db.delete("odin_advise_sms_delivery",{},is_one=False)
    my_db.delete("odin_advise_sms_delivery_record",{},is_one=False)

    #删除系统维护-资源表
    my_db.delete("authority_sys_maintain",{},is_one=False)

    #删除告警图片
    pic_dir = EMERGENCY_IMG_PATH
    if os.path.exists(pic_dir):    
        for file in os.listdir(pic_dir):
            filepath = pic_dir + file
            shutil.rmtree(filepath)

    #删除人脸图
    face_dir = PERSON_IMG_URL 
    if os.path.exists(face_dir):    
        for file in os.listdir(face_dir):
            filepath = face_dir + file
            shutil.rmtree(filepath)

    #删除人脸特征
    identification_dir = FACE_IDENT_URL  
    if os.path.exists(identification_dir):   
        for file in os.listdir(identification_dir):
            filepath = identification_dir + file
            shutil.rmtree(filepath)

def get_constant_entity(my_db:ToMongo):
    try:
        items = my_db.get_col('work_flow_algorithm_constant').find()
        entities = list()
        for item in items:
            constant_item = dict()
            constant_item['algorithmConstantName'] = item.get('algorithm_constant_name')
            constant_item['algorithmConstantNum'] = item.get('algorithm_constant_num')
            constant_item['algorithmServiceNum'] = item.get('algorithm_service_num')
            constant_item['algorithmInterval'] =  item.get('algorithm_interval')
            constant_item['algorithmColor'] =  item.get('algorithm_color')
            constant_item['algorithmConstantStatus'] =  item.get('algorithm_constant_status')
            constant_item['algorithmConstantType'] =  item.get('algorithm_constant_type')
            entities.append(constant_item)
    except Exception as e:
        mainlogger.info("get_constant_entity error :%s"%e)
        entities = []
    return entities

def query_edge_service(my_db:ToMongo,ststus="0"):
    baseinfo = my_db.get_col("authority_base_info").find_one()
    edge_service_info = my_db.get_col("authority_work_model").find_one()
    host_ip = get_ip()
    item = { "serviceState": ststus,
            "serviceSerialNumber": baseinfo['equipment_serial_number'],
            "port": 5000,
            "ip": host_ip,
            "deviceModel":1,
            "serviceType": BASE_INFO['equipment_model'],
            "deviceSn":baseinfo['equipment_model'],
            "cameraMaxLimit": 12,#支持的最大路数
            "deviceName": baseinfo['equipment_name'],
            "mac": None,
            "algorithm": "string" }
    name = host_ip.split('.')[3]
    item['deviceName'] = item['deviceName'] + '-' + name
    alg_list = my_db.get_keyvalues("work_flow_algorithm_constant","algorithm_constant_num")
    item['algorithm'] = ";".join(alg_list)
    content = {"deviceSn": item['deviceSn']}
    return item,content

def register_device(serviceState,remote_url,content):
    #向远程服务器发送注册请求
    my_db = ToMongo('wavedevice')
    url = remote_url + REGISTER_DEVICE

    headers = {'Content-Type': 'application/json'}
    content['serviceState'] = serviceState

    err_result = set_fail_result()
    success_result = set_success_result()
    try:
        answer = requests.post(url,data=json.dumps(content),headers=headers,verify=False,timeout=10)
        answer = answer.json()
        mainlogger.info("--切换模式response-- :%s"%answer)
        if answer['code'] == 200:
            return success_result
    except Exception as e:
        mainlogger.info("--切换模式失败 :%s"%e)

    err_result['errorCodeDesc'] = "向平台修改盒子状态不成功，切换工作模式失败"
    return err_result

def switch_state(item,remote_url):
    #向AI精灵平台修改盒子的状态
    try:
        url = remote_url + SYN_BOX_STATE
        headers = {'Content-Type': 'application/json'}
        answer = requests.post(url,data=json.dumps(item),headers=headers,verify=False)
        return answer.json()
    except Exception as e:
        mainlogger.info("修改盒子的状态失败：%s"%e)
        return
    
def sync_camera_device(remote_url,content):
    #向远程服务器发送设备同步请求
    url = remote_url + SYN_DEVICE_CAMERA
    headers = {'Content-Type': 'application/json'}
    answer = requests.post(url,data=json.dumps(content),headers=headers,verify=False)
    return answer.json()

def sync_heartbeat(remote_url,content):
    #向远程服务器发送心跳请求
    url = remote_url + HEART_BEAT
    headers = {'Content-Type': 'application/json'}
    answer = requests.post(url,data=json.dumps(content),headers=headers,verify=False)
    return answer.json()

def sync_position_info(remote_url,content):
    #向远程服务器发送位置信息同步请求
    url = remote_url + SYN_DEVICE_POSITION
    headers = {'Content-Type': 'application/json'}
    answer = requests.post(url,data=json.dumps(content),headers=headers,verify=False)
    return answer.json()

def sync_control_info(remote_url,content):
    #向远程服务器发送布控信息同步请求
    url = remote_url + SYN_CONTROL
    headers = {'Content-Type': 'application/json'}
    answer = requests.post(url,data=json.dumps(content),headers=headers,verify=False)
    return answer.json()
    
def sync_personn_info(remote_url,content):
    #向远程服务器发送布控信息同步请求
    url = remote_url + SYN_PERSONNEL_INFO
    headers = {'Content-Type': 'application/json'}
    answer = requests.post(url,data=json.dumps(content),headers=headers,verify=False)
    return answer.json()

def sync_alg_info(remote_url,content):
    #向远程服务器发送布控信息同步请求
    url = remote_url + SYN_ALG_INFO
    headers = {'Content-Type': 'application/json'}
    answer = requests.post(url,data=json.dumps(content),headers=headers,verify=False)
    return answer.json()

def sync_all_info(remote_url,content):
    #向ai精灵服务器发送同步请求
    url = remote_url + SYN_DEVICE_ALG
    headers = {'Content-Type': 'application/json'}
    answer = requests.post(url,data=json.dumps(content),headers=headers,verify=False)
    return answer.json()

def sync_heartbeat_aispirit(remote_url,content):
    #向ai精灵服务器发送心跳请求
    url = remote_url + HEART_BEAT
    headers = {'Content-Type': 'application/json'}
    answer = requests.post(url,data=json.dumps(content),headers=headers,verify=False)
    return answer.json()

def convert_control_format(msg):
    #转换联网模式下 server传来的布控任务信息
    flowMissionSyncVoList = msg['flowMissionSyncVoList']
    controlTaskEntityList = msg['controlTaskEntityList']
    flowMissionGroupVoList = msg['flowMissionGroupVoList']
    ipAddress = msg.get("ipAddress")

    res = {}
    res['ipAddress'] = ipAddress
    res['controlTaskEntityList'] = controlTaskEntityList
    res['algorithmInstances'] = []
    res['deviceAssociateList'] = []
    res['personnelAssociateList'] = []
    res['personnelGroupAssociateList'] = []
    res['workFlowMissionVos'] = []
    res['workFlowMissionGroupVos'] = []   #布控任务组

    res['algorithmConstantEntityList'] = msg.get('algorithmConstantEntityList')
    res['soundServiceEntity'] = msg.get('soundServiceEntity')
    res['deviceSoundEntitieList'] = msg.get('deviceSoundEntitieList')
    res['soundNos'] = msg.get('soundNos')
    res['soundEntities'] = msg.get('soundEntities')


    if flowMissionSyncVoList:
        for a in flowMissionSyncVoList:
            if a['instanceList']:
                for b in a['instanceList']:
                    res["algorithmInstances"].append(b)

            if a['flowDeviceVoList']:
                for c in a['flowDeviceVoList']:
                    res["deviceAssociateList"].append(c)

            if a['flowMissionPersonnelAssociateVoList']:
                for d in a['flowMissionPersonnelAssociateVoList']:
                    res["personnelAssociateList"].append(d)

            if a['flowMissionPersonnelGroupAssociateVoList']:
                for e in a['flowMissionPersonnelGroupAssociateVoList']:
                    res["personnelGroupAssociateList"].append(e)    

            del a['instanceList']
            del a['flowDeviceVoList']
            del a['flowMissionPersonnelAssociateVoList']
            del a['flowMissionPersonnelGroupAssociateVoList']

            del a['flowMissionJobAssociateList']
            del a['flowMissionModelAssociateList']
            del a['flowMissionGroupMissionAssociateVoList']

            res["workFlowMissionVos"].append(a)
    if flowMissionGroupVoList:
        for x in flowMissionGroupVoList:
            res["workFlowMissionGroupVos"].append(x)  

    return res

class SyncDataTimerPlatform():
    '''
    与平台同步进程
    '''
    def __init__(self):
        self.my_db = ToMongo('wavedevice')
        self.data_version_col = self.my_db.get_col('system_data_version')
        self.interval_time = 10   #定时3s去同步数据
        self.remote_url = ""
        self.device_sn = "" 
        self.work_model = "1" 

    def init_base_info(self):
        edge_info = self.my_db.get_col('authority_work_model').find_one() 
        model_info = self.my_db.get_col('authority_base_info').find_one()
        self.work_model = edge_info['model']
        serviceAddress = edge_info['service_address']
        servicePort = edge_info['service_port']
        self.remote_url = NetAgreementType + "://" + serviceAddress + ":" + servicePort
        self.device_sn = model_info['equipment_model']
        self.organization_id = edge_info['organization_id']
        self.bind_organization_id = edge_info['service_organization_id']

    def query_box_version(self):
        items = self.data_version_col.find()
        res = {}
        for item in items:
            name = item['name']
            res[name] = item['version_number']
        return res

    def query_edge_version(self):
        try:
            url = self.remote_url + HEART_BEAT
            headers = {'Content-Type': 'application/json'}
            content = {"deviceSn":self.device_sn,"bindOrganizationId":self.bind_organization_id,"organizationId":self.organization_id}
            data = requests.post(url,data=json.dumps(content),headers=headers,verify=False)
            data = data.json()
            systemDataVersionList = data["systemDataVersionList"]

            ans = {}
            for item in systemDataVersionList:
                name = item['name']
                ans[name] = item['versionNumber']
        except Exception as e:
            mainlogger.info("query_edge_version error:%s"%e)
            ans = {}
        return ans
    
    def check_version_func(self):

        while self.work_model == '1':

            work_model_item = self.my_db.get_col('authority_work_model').find_one() 
            self.work_model = work_model_item['model']
            if self.work_model == '0':
                break

            box_version = self.query_box_version()
            edge_version = self.query_edge_version()
            content = {"cpuSn": self.device_sn}
            content['organizationId'] = self.bind_organization_id if self.bind_organization_id else self.organization_id

            mainlogger.info("--平台的data version:%s"%edge_version)
            if not edge_version:
                time.sleep(self.interval_time)
                continue

            t1 = Thread(target=self.check_personnel_thread,args=[box_version,edge_version,content])         
            t1.start()
            t1.join(timeout=2.0)

            t2 = Thread(target=self.check_adress_thread,args=[box_version,edge_version,content])
            t2.start()

            t3 = Thread(target=self.check_device_thread,args=[box_version,edge_version,content])
            t3.start()

            t4 = Thread(target=self.check_control_thread,args=[box_version,edge_version,content])
            t4.start()

            t5 = Thread(target=self.check_alg_thread,args=[box_version,edge_version,content])
            t5.start()

            time.sleep(self.interval_time)
       
    def check_version_thread(self):
        mainlogger.info("--开启平台-盒子同步进程--")
        sync_thread = Thread(target=self.check_version_func,args = [])
        sync_thread.start()
    
    def check_adress_thread(self,box_version,edge_version,content):
        if box_version['address'] < edge_version['address']:
            #位置信息同步云平台
            data_position = sync_position_info(self.remote_url,content)
            PositionList = data_position['positionList']
            insert_position_info(self.my_db,PositionList)
            item = {}
            item['version_number'] = edge_version['address']
            query = {'name':'address'}
            self.my_db.update("system_data_version",query,{"$set":item})
            

    def check_control_thread(self,box_version,edge_version,content):
        if box_version['control'] < edge_version['control']:
            #任务信息同步云平台
            data_control = sync_control_info(self.remote_url,content)
            controlManageEntity = convert_control_format(data_control)
            insert_control_info(self.my_db,controlManageEntity)
            minio_addr = data_control.get('ipAddress',None)
            update_minio_address(self.my_db,minio_addr)

            item = {}
            item['version_number'] = edge_version['control']
            query = {'name':'control'}
            self.my_db.update("system_data_version",query,{"$set":item})

            from algorith_server.AlgorithServer_v2 import SenderThread
            sender = SenderThread(context=[])
            sender.send_reboot_message()
            

    def check_device_thread(self,box_version,edge_version,content):
        if box_version['device'] < edge_version['device']:
            #设备信息同步云平台
            data_device = sync_camera_device(self.remote_url,content)
            cameraSyncRepVOList = data_device['cameraSyncRepVOList']
            old_url_list = self.my_db.get_keyvalues("odin_device_camera_edit","main_url")
            cam_url_list = insert_camera_info(self.my_db,cameraSyncRepVOList)
            

            item = {}
            item['version_number'] = edge_version['device']
            query = {'name':'device'}
            self.my_db.update("system_data_version",query,{"$set":item})

            from algorith_server.AlgorithServer_v2 import SenderThread
            sender = SenderThread(context=[])
            sender.send_3007_message()
            # #摄像头的url变了，重新下发摄像头数据
            # if set(old_url_list) != set(cam_url_list):
            #     sender.send_3007_message()
            
    def check_personnel_thread(self,box_version,edge_version,content):
        if box_version['personnel'] < edge_version['personnel']:
            #人脸库信息同步云平台
            data_person = sync_personn_info(self.remote_url,content)
            insert_person_info(self.my_db,data_person)

            item = {}
            item['version_number'] = edge_version['personnel']
            query = {'name':'personnel'}
            self.my_db.update("system_data_version",query,{"$set":item})

    def check_alg_thread(self,box_version,edge_version,content):
        if box_version['algorithm'] < edge_version['algorithm']:
            #算法信息同步云平台
            data_alg = sync_alg_info(self.remote_url,content)
            algorithmConstantEntityList = data_alg.get('algorithmConstantEntityList')
            insert_alg_info(self.my_db,algorithmConstantEntityList)

            item = {}
            item['version_number'] = edge_version['personnel']
            query = {'name':'algorithm'}
            self.my_db.update("system_data_version",query,{"$set":item})

class SyncDeviceP2p():

    def __init__(self):
        self.my_db = ToMongo('wavedevice')
        self.interval_time = 60  #定时任务间隔
        srs_thread = Thread(target = self.p2pThread,args=[])
        srs_thread.start()

    def p2pThread(self):
        while True:
            push_srs_thread = Thread(target=self.scanCameraUpdateP2pConfig,args=[])
            push_srs_thread.start()
            time.sleep(self.interval_time)

    def httpRequestGetP2pAccount(self,url):
        baseinfo_col = self.my_db.get_col('authority_base_info')
        baseinfo_item = baseinfo_col.find_one()
        map = dict()    
        map['deviceSn'] = baseinfo_item.get('equipment_model',None)
        headers = {"Content-Type": "application/json"}
        resp = requests.post(url,data=json.dumps(map),headers=headers,timeout=2)
        return resp.json()
    
    def syncCameraStatus(self,url,cameraIds,cameraStatus):
        header = {'Content-Type': 'application/json'}
        map = dict()
        map['cameraIds'] = cameraIds
        map['cameraStatus'] = cameraStatus
        response = requests.post(url,data=json.dumps(map),headers=header,verify=False)
        response = response.json()
        return response
    
    def getStreamList(self,newCameraInfo,p2pAccount,syncNoUrl,maxVideoId):
        streamList = list()
        keys = newCameraInfo.keys()
        streamCount = maxVideoId + 1 if maxVideoId < 31 else 0
        param = dict() 
        for key in keys:
            obj = dict()
            obj['RtspURL'] = newCameraInfo[key]
            obj['PullMode'] = 2
            obj['CapID'] = p2pAccount
            obj['VideoID'] = streamCount
            obj['AudioID'] = streamCount
            obj['Username'] = ""
            obj['Password'] = ""
            obj['VideoParam'] = "(SendCache){1}(MaxStream){100}"
            obj['AudioParam'] = ""
            obj['Comment'] = "Stream" + str(streamCount)
            temp = key.split("_")
            camera_id = temp[0]
            rtspType = temp[1]
            videoId = param.get(camera_id)
            if not videoId:
                param[camera_id] = str(streamCount)
            elif rtspType == "1":
                #清晰度更高的主码流
                param[camera_id] = ",".join([str(streamCount),videoId])
            elif rtspType == "2":
                #清晰度较低的子码流
                param[camera_id] = ",".join([videoId,str(streamCount)])
            streamCount = streamCount + 1 if streamCount < 31 else 0
            streamList.append(obj)

        #把编号同步到平台
        #同步格式 {camera_id:"1,2"}  "1,2" 前者主码流，后者子码流
        try:
            headers = {'Content-Type': 'application/json'}           
            resp = requests.post(url=syncNoUrl,data=json.dumps(param),verify=False,timeout=2)
            mainlogger.info("sync camera number result:%s"%resp.json())
            mainlogger.info("sync camera number param:%s"%param)
        except Exception as e:
            mainlogger.info("getStreamList Error:%s"%e)

        return streamList
    
    def getLiveCapList(self,p2pAccount,serverAddr):
        liveCapList = list()
        obj = dict()
        obj['CapID'] = p2pAccount
        obj['Password'] = ""
        obj['ServerAddr'] = serverAddr
        obj['RelayAddr'] = ""
        obj['InitParam'] = "(Debug){1}(LanScan){0}"
        liveCapList.append(obj)
        return liveCapList

    def initJsonFile(self,filePath):
        #初始化配置文件
        try:
            with open(filePath,'r',encoding='utf-8') as f:
                jsonObject = json.load(f)
                jsonObject["StreamList"] = []
                f.write(json.dumps(jsonObject))
        except Exception as e:
            mainlogger.exception(e)
        return

    def scanCameraUpdateP2pConfig(self):
        workmodel_col = self.my_db.get_col('authority_work_model')
        workmodel_info = workmodel_col.find_one()
        if not workmodel_info:
            return
        try:
            model = workmodel_info['model']
            if model == "0" or model == None:
                mainlogger.info("盒子工作模式为单机,不同步摄像头状态至云平台")
                pid = getPid(command="pgRtspLiveCapSvc",Toflag="pgRtspLiveCapSvc")
                if pid:
                    closeLinuxProcess(pid)
                    mainlogger.info("p2p进程存在，kill p2p 进程")
                return

            p2pExecuteFilePath = "/data/ctp2p/pgRtspLiveCapSvc"
            jsonConfigFilePath = "/data/ctp2p/pgRtspLiveStreamInfo.json"
            cfgConfigFilePath = "/data/ctp2p/pgRtspLiveCapSvc.cfg"
            if not os.path.exists(p2pExecuteFilePath) or not os.path.exists(jsonConfigFilePath) or not os.path.exists(cfgConfigFilePath):
                mainlogger.info("p2p可执行程序或配置文件不存在，不做处理")
                return
            camera_col = self.my_db.get_col("odin_device_camera_edit")
            camera_infos = camera_col.find({'camera_status':'0'},{'_id':0})

            #查看p2p进程
            pid = getPid("pgRtspLiveCapSvc", "pgRtspLiveCapSvc")
            if camera_infos.count() == 0:
                mainlogger.info("没有可以配置的摄像头，不做处理")
                self.initJsonFile(jsonConfigFilePath)
                if pid:
                    closeLinuxProcess(pid)
                return 
           
            
            #获取当前盒子的p2p账号和p2p服务地址
            remote_url = NetAgreementType +"://" + workmodel_info['service_address'] + ":" + workmodel_info['service_port'] + "/syn/getP2pAccount"
            resp = self.httpRequestGetP2pAccount(remote_url)
            data = resp.get("data")
            p2pAccount = data.get('p2pAccount',None)
            serverAddr = data.get('p2pServiceAddress',None)
            if not p2pAccount or not serverAddr:
                mainlogger.info("当前盒子未配置p2p账号或服务地址")
                return
            with open(jsonConfigFilePath,'r',encoding='utf-8') as f:
                jsonObject = json.load(f)
            jsonArray = jsonObject.get('StreamList',None)
            oldCameraInfo = dict()
            maxVideoId = 0
            for item in jsonArray:
                videoID = item['VideoID']
                rtspURL = item['RtspURL']
                maxVideoId = videoID if videoID > maxVideoId else maxVideoId
                oldCameraInfo[videoID] = rtspURL
            if jsonArray:
                #获取旧的p2p账号
                p2pAccountBefore = jsonArray[0].get("CapID")

            #获取现在的摄像头配置
            newCameraInfo = dict()
            for cam in camera_infos:
                camera_id = cam['camera_id']
                main_url = cam.get("main_url")
                live_url = cam.get("live_url")
                if  main_url:
                    id = camera_id + "_1"
                    newCameraInfo[id] = main_url
                if  live_url:
                    id = camera_id + "_2"
                    newCameraInfo[id] = live_url
            
            #对比新旧摄像头，一致且P2P进程存在，则不处理
            if len(oldCameraInfo) == len(newCameraInfo) and pid and list(oldCameraInfo.values()) == list(newCameraInfo.values()) and p2pAccountBefore == p2pAccount:
                mainlogger.info("盒子摄像头配置未变动，p2p账号未更改，不做处理")
                return
            
            #先杀p2p进程
            if pid:
                mainlogger.info("kill p2p 进程，准备写入配置文件")
                closeLinuxProcess(pid)
            
            mainlogger.info("start write  p2p config")
            syncCameraNoUrl = NetAgreementType + "://" + workmodel_info['service_address'] + ":" + workmodel_info['service_port'] + "/syn/syncCameraNo"
            streamList = self.getStreamList(newCameraInfo,p2pAccount,syncCameraNoUrl,maxVideoId)
            jsonObject['StreamList'] = streamList

            #写入cfg配置文件
            with open(cfgConfigFilePath,'r',encoding='utf-8') as f2:
                cfgObject = json.load(f2)

            liveCapList = self.getLiveCapList(p2pAccount, serverAddr)
            cfgObject['LiveCapList'] = liveCapList

            with open(jsonConfigFilePath,'w',encoding='utf-8') as f3:
                f3.write(json.dumps(jsonObject))
            with open(cfgConfigFilePath,'w',encoding='utf-8') as f4:
                f4.write(json.dumps(cfgObject))
            err,result = execShell(cmd='/bin/sh -c /data/ctp2p/pgRtspLiveCapSvc')

        except Exception as e:
            mainlogger.info("write camera info to p2p config error:%s"%e)

class SyncDataTimer():
    '''
    与AI精灵同步进程
    '''    
    def __init__(self):
        self.my_db = ToMongo('wavedevice')
        self.data_version_col = self.my_db.get_col('system_data_version')
        self.interval_time = 10   #定时3s去同步数据
        self.remote_url = ""
        self.device_sn = "" 
        self.work_model = "1" 

    def init_base_info(self):
        edge_info = self.my_db.get_col('authority_work_model').find_one() 
        model_info = self.my_db.get_col('authority_base_info').find_one()
        self.work_model = edge_info['model']
        serviceAddress = edge_info['service_address']
        servicePort = edge_info['service_port']
        self.remote_url = NetAgreementType + "://" + serviceAddress + ":" + servicePort
        self.device_sn = model_info['equipment_model']

    def query_box_version(self):
        items = self.data_version_col.find()
        res = {}
        for item in items:
            name = item['name']
            res[name] = item['version_number']
        return res

    def query_edge_version(self):
        try:
            url = self.remote_url + HEART_BEAT
            headers = {'Content-Type': 'application/json'}
            content = {"deviceSn":self.device_sn}
            data = requests.post(url,data=json.dumps(content),headers=headers,verify=False)

            data = data.json()
            #mainlogger.info("query_edge_version :%s"%data)
            systemDataVersionList = data.get("data")

            ans = {}
            for item in systemDataVersionList:
                name = item['name']
                ans[name] = item['versionNumber']
        except Exception as e:
            mainlogger.info("query_edge_version error:%s"%e)
            ans = {}
        return ans
    
    def check_version_func(self):

        while self.work_model == '1':

            try:

                work_model_item = self.my_db.get_col('authority_work_model').find_one() 
                self.work_model = work_model_item['model']
                if self.work_model == '0':
                    break

                box_version = self.query_box_version()
                edge_version = self.query_edge_version()
                content = {"deviceSn": self.device_sn}

                mainlogger.info("--平台的data version:%s"%edge_version)
                if not edge_version:
                    time.sleep(self.interval_time)
                    continue

                t1 = Thread(target=self.check_all_thread,args=[box_version,edge_version,content])         
                t1.start()

                time.sleep(self.interval_time)

            except Exception as e:
                mainlogger.info("check_version error:%s"%e)
                time.sleep(self.interval_time)
       
    def check_version_thread(self):
        mainlogger.info("--开启平台-盒子同步进程--")
        sync_thread = Thread(target=self.check_version_func,args = [])
        sync_thread.start()
               

    def check_all_thread(self,box_version,edge_version,content):
        if box_version['device_algorithm'] < edge_version['device_algorithm']:
            #任务信息同步云平台
            resp = sync_all_info(self.remote_url,content)
            data_all = resp.get('data')
            insert_all_info(self.my_db,data_all)

            item = {}
            item['version_number'] = edge_version['device_algorithm']
            query = {'name':'device_algorithm'}
            self.my_db.update("system_data_version",query,{"$set":item})

            from algorith_server.AlgorithServer_v2 import SenderThread
            sender = SenderThread(context=[])
            sender.send_reboot_message()
            
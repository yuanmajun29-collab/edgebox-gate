import subprocess
import threading
import shutil
import os
from datetime import timedelta

from config import BASE_INFO, PEDESTRIAN_ALG_NUM, VEHICLE_ALG_NUM
from .sys_config import *
from config import PERSON_IMG_URL,FACE_IDENT_URL,EMERGENCY_IMG_PATH,DISK_PATH,UNDERLAY_URL,CURVE_CONFIG,CROSSING_CONFIG
import base64
from algorith_server.AgreementBuilder import pack_face_3005
from algorith_server.Alibabasms import SendSmsResqueset
from msg_queue import faceidentification_queue
import Utils.glv as glv
from Utils.voicedevice_utils import *
from Utils.emergencydb import deletefile,get_minio_img
from config import SHELL_DIR
from system.curve_misc import SerialNetServer
from system.crossroads_misc import RoadManage
from system.crossroads_model import *
from system.crossroads_controller import start_listen_radar_v2

import Utils.edgebox_repo  # noqa: F401
from edgebox_db.workflow_mission_queries import workflow_mission_collection
from edgebox_db.mongo_collections import (
    WORK_FLOW_ALGORITHM_CONSTANT,
    WORK_FLOW_INSIGHT_MODEL_ALGORITHM_INSTANCE,
    WORK_FLOW_MISSION,
    WORK_FLOW_MISSION_DEVICE_ASSOCIATE,
    WORK_FLOW_MISSION_HIDDEN,
    WORK_FLOW_MISSION_PERSONNELGROUP_ASSOCIATE,
    WORK_FLOW_MISSION_PERSONNEL_ASSOCIATE,
    WORK_FLOW_PERSONNEL,
    WORK_FLOW_PERSONNELGROUP,
    WORK_FLOW_PERSONNEL_IMAGE,
    WORK_FLOW_PERSONNEL_PERSONNELGROUP_ASSOCIATE,
)

def execShell(cmd):
    err,result = subprocess.getstatusoutput(cmd)
    return err,result

def getPid(command,Toflag):
    try:
        cmd = "ps -ef|grep -v grep|grep " + command + "|grep " + Toflag
        error,resp = execShell(cmd)
        if not resp:
            return None
        else:
            pid = resp.split()[1]
        return pid
    except Exception as e:
        print('error : %s'%e)
        return

def closeLinuxProcess(pid):
    try:
        cmd = "kill -9 " + pid
        err,result = execShell(cmd)
    except Exception as e:
        print('kill process error : %s'%e)   
    return

def database_to_dict2(item,old:list,new:list):
    num = len(old)
    res = {}
    keys = item.keys()
    for i in range(num):
        oldkey = old[i]        
        if oldkey in keys:
            data = item[oldkey]
        else:
            continue
        if data == None:
            continue
        newkey = new[i]
        res[newkey] = data
    return res

def database_to_dict3(item,old:list,new:list):
    num = len(old)
    res = {}
    keys = item.keys()
    for i in range(num):
        oldkey = old[i]        
        if oldkey in keys:
            data = item[oldkey]
            newkey = new[i]
            res[newkey] = data
    return res

def database_to_dict(item,old:list,new:list):
    num = len(old)
    res = {}
    keys = item.keys()
    for i in range(num):
        oldkey = old[i]
        newkey = new[i]
        if oldkey in keys:
            data = item[oldkey]
        else:
            data = None
        res[newkey] = data
    return res

def get_temperature():
    '''
    return : 主板温度和芯片温度
    type float
    '''
    try:
        temperature_cmd = "cat /sys/class/thermal/thermal_zone0/temp"
        err,result=execShell(temperature_cmd)
        chip_temp = int(result) /1000
    except Exception as e:
        chip_temp = None
    return chip_temp

def get_cpu_and_memery():
    try:
        cpu_cmd = "top -bn 1|grep %Cpu"   #不加-b使用nohup会出错
        memory_cmd = "free -m|grep Mem"
        err,res_cpu = execShell(cpu_cmd)
        err,res_mem = execShell(memory_cmd)
        cpu_percent = int(float(res_cpu.split()[1]))
        mem_list = res_mem.split()
        total , used = float(mem_list[1]) ,float(mem_list[2])
        mem_percent = int(100*used/total)
        num_1G = 1024
        total_G = round(total/num_1G,1)
        used_G = round(used/num_1G,1)
    except Exception as e:
        cpu_percent,mem_percent,total_G,used_G = None,None,None,None
    return cpu_percent,mem_percent,total_G,used_G

def get_npu_and_npumem():
    '''
    return 返回tpu占用率和tpu内存占用率
    type float
    '''
    try:
        cmd_npu = "cat /sys/class/bm-tpu/bm-tpu0/device/npu_usage"
        cmd_npu_memery = "cat /sys/kernel/debug/ion/bm_npu_heap_dump/summary |head -2"
        err,npu_result = execShell(cmd_npu)
        err,npu_memery_result = execShell(cmd_npu_memery)
        npu_memery_percent = str(npu_memery_result.split()[8].split(':')[1][:-1]) 
    except Exception as e:
        npu_result,npu_memery_percent = None,None
    return npu_result,npu_memery_percent

def get_disk():
    '''
    return 返回磁盘占用率
    type float
    '''
    try:
        disk_cmd = "df -h|grep " + DISK_PATH
        err,disk_result = execShell(disk_cmd)
        if disk_result:
            disk_percent = int(disk_result.split()[-2].split('%')[0])
            # disk_left = float(disk_result.split()[-3][:-1])
            disk_left = disk_result.split()[-3]
        else:
            disk_percent,disk_left = None,None
    except Exception as e:
        disk_percent,disk_left = None,None
    return disk_percent,disk_left

def get_fanrate():
    '''
    return 返回风扇转速
    '''
    try:
        fan_cmd = "cat /sys/class/bm_fan_speed/bm_fan_speed-0/fan_speed|awk -F : '{ print $2 }'"
        err,fan_result = execShell(fan_cmd)
        fan_rate = int(fan_result)*30/1000
    except Exception as e:
        fan_rate = 0
    return fan_rate

def get_ip():
    '''
    return 返回盒子ipv4地址
    '''
    try:
        err0,result = execShell("/sbin/ifconfig eth0|grep inet")
        result = result.split()[1]
    except Exception as e:
        result = None
    return result

def get_mac():
    '''
    return 返回盒子mac地址
    '''
    try:
        err1,result1 = execShell("/sbin/ifconfig eth0")
        err2,result2 = execShell("/sbin/ifconfig eth1")
        result1 = result1.split("\n")
        result2 = result2.split("\n")
        macRowV4 = result1[3]
        macRowV6 = result2[3]
        macV4 = macRowV4.split()[1] if 'ether' in macRowV4 else None
        macV6 = macRowV6.split()[1] if 'ether' in macRowV6 else None
    except Exception as e:
        macV4 ,macV6 = None,None
    return (macV4,macV6)

def get_nginx_port():
    try:
        cmd = 'cat /etc/nginx/nginx.conf|grep listen'
        error,result = execShell(cmd)
        port = result.split()[1][:-1]
    except Exception as e:
        port = None
    return port

def get_eth0_ipv4():
    '''
    说明:从eth0文件获取ipv4地址和网关等
    '''
    try:
        eth0_path = "/etc/network/interfaces.d/eth0"
        if not os.path.exists(eth0_path):
            return
        fp = open(eth0_path,'r')
        content = fp.readlines()
        ip = content[2].lstrip().split()[1]
        netmask = content[3].lstrip().split()[1]
        gateway = content[4].lstrip().split()[1]
        dns = content[5].lstrip().split()[1]
    except Exception as e:
        ip,netmask,gateway,dns = None,None,None,None
    return (ip,netmask,gateway,dns)

def get_eth1_ipv6():
    '''
    说明:从eth1文件获取ipv6地址和网关等
    '''
    try:
        eth1_path = "/etc/network/interfaces.d/eth1"
        if not os.path.exists(eth1_path):
            return
        fp = open(eth1_path,'r')
        content = fp.readlines()
        ip = content[2].lstrip().split()[1]
        netmask = content[3].lstrip().split()[1]
        dns = content[4].lstrip().split()[1]
    except Exception as e:
        ip,netmask,dns = None,None,None
    return (ip,netmask,dns)

def get_rk_info():
    '''
    查询rk3588S的设备序列号
    '''
    try:
        err1,result1= execShell("cat /proc/cpuinfo|grep Serial")
        res1 = result1.split()
        product_sn = chip_sn = res1[-1].upper()

        err2,result2 = execShell("hostnamectl|grep Kernel")
        res2 = result2.split()
        hardware_version = res2[-1]
    except Exception as e:
        chip_sn,product_sn,hardware_version = None,None,None
    return chip_sn,product_sn,hardware_version

def get_se6_info():
    '''
    return 返回盒子的设备序列号和硬件版本
    '''

    cmd1 = SHELL_DIR + "bm_get_basic_info|grep chip"
    err1,result1= execShell(cmd1)

    if err1 == 0 and result1:
        chip_sn = result1.split()[-1]
    else:
        chip_sn = None

    try:
        cmd2 = SHELL_DIR + 'bm_get_basic_info|grep product' 
        err2,result2= execShell(cmd2)
        if err2 == 0 and result2:
            product_sn = result2.split()[-1]
        else:
            product_sn = None

        cmd3 = SHELL_DIR + 'bm_version|grep "VERSION"' 
        err3,result3 = execShell(cmd3)
        if err3 == 0 and result3:
            hardware_version = result3.split()[-1]
        else:
            hardware_version = None
    except Exception as e:
        product_sn,hardware_version = None,None
    return chip_sn,product_sn,hardware_version

def get_base_info():
    filepath = SHELL_DIR + "bm_get_basic_info"
    if os.path.exists(filepath):
        chip_sn,product_sn,hardware_version = get_se6_info()
    else:
        chip_sn,product_sn,hardware_version = get_rk_info()
    return chip_sn,product_sn,hardware_version

class CleanLogs():
    def __init__(self,organization_id,log_set,my_db):

        self.log_clean_thread = Thread(target = self.clean_logs, args = [organization_id,log_set,my_db])
        self.log_clean_thread.start()
   
    def clean_logs(self,organization_id,log_set,my_db):
        numlist = log_set.split('-')
        num_uplimit = int(float(numlist[0])*10000)
        num_delete =  int(float(numlist[1])*10000)
        while True:
            log_cursor = my_db.get_col("user_logs").find({'organization_id':organization_id})
            totalcount = log_cursor.count()
            time.sleep(10)
            if totalcount >= num_uplimit:
                thresh = totalcount - num_delete-1
                thresh_time = log_cursor.sort("create_time",-1)[thresh]['create_time']
                my_db.delete('user_logs',
                            {'organization_id':organization_id,'create_time':{'$gte':thresh_time}},
                            is_one=False)

class Cleandisk():
    def __init__(self):
        self.phone_list = []
        self.email_list = []
        self.smsClient = SendSmsResqueset()
        self.my_db = ToMongo('wavedevice')
        self.send_time = None
        self.get_config()
        self.check_thread = Thread(target=self.check_func,args=[])
        self.check_thread.start()

    def get_config(self):
        conf_item = self.my_db.get_col('authority_sys_maintain').find_one()
        if conf_item:
            if conf_item['sms_notification_account']:
                self.phone_list = conf_item['sms_notification_account'].split(',')
            if conf_item['email_notification_account']:
                self.email_list = conf_item['email_notification_account'].split(',')

    def check_func(self):
        while True:
            useage,disk_left = get_disk()
            if  useage:
                if useage >= 70:
                    now= datetime.now()
                    now_str = now.strftime("%Y-%m-%d %H:%M:%S")
                    if self.send_time:
                        last_send_time = self.send_time
                        interval = now - last_send_time
                        if interval < timedelta(days=0.5):
                            continue
                    self.send_time = now
                    device_item = self.my_db.get_col('authority_base_info').find_one()
                    device_name = device_item['equipment_name']
                    msg = {"alarm_time":now_str,"device_name":device_name,'free_space':disk_left}
                    self.send_sms(msg)
                    self.send_email(msg)              
                if useage >= 80:
                    print("磁盘占用超过80%，清理前1000条告警数据！")
                    self.clear_disk()
            time.sleep(300)

    def clear_disk(self):
        emergency_col = self.my_db.get_col('odin_business_emergency_record')
        emergency_detail_col = self.my_db.get_col('odin_business_emergency_record_detail_info')
        items = emergency_col.find().sort('emergency_time',1)
        if items.count() <= 1000:
            return
        end_time = items[999]['emergency_time']
        items_1000 = items[:1000]

        #删除告警图片
        for item in items_1000:
            temp = item['emergency_time'].split(" ")[0].split('-')
            filedir = ''.join(temp)
            sub_source_id = item['sub_source_id']
            filepath = EMERGENCY_IMG_PATH + filedir +'/' + sub_source_id + '.jpg'
            if os.path.exists(filepath):
                os.remove(filepath)
            
        #删除告警记录表的相关内容
        query = {'emergency_time':{"$lte" :end_time}}
        self.my_db.delete('odin_business_emergency_record',query,is_one=False)
        query_detail = {'discern_time':{"$lte" :end_time}}
        self.my_db.delete('odin_business_emergency_record_detail_info',query_detail,is_one=False)
                              

    def send_sms(self,msg):
        phone_list = self.phone_list
        if phone_list:       
            self.smsClient.send_sms_disk(msg,phone_list)

    def send_email(self,msg):
        query = {}
        email_item = self.my_db.get_col('authority_mail_service_setting').find_one(query)
        email_list = self.email_list
        if not email_list or not email_item:
            return
        mail_smtp_address = email_item['mail_smtp_address']
        mail_account = email_item['mail_account']
        mail_password = email_item['mail_password']
        mail_send_name = email_item['mail_send_name']
        subject = '"AI算法盒存储空间告警"'
        content = '"[威富视界]AI算法盒存储空间告警!告警内容：存储空间剩余%s,已低于30%%,低于20%%时将自动删除最早的告警纪录,AI算法盒名称:%s,告警时间：%s。"'%(msg['free_space'],msg['device_name'],msg['alarm_time'])
        cmd_mail_part =  'echo ' + content + '|/data/ebox/mail/mailx -s ' + subject + ' -S smtp=' + mail_smtp_address + ' -S from=' + mail_send_name + ' -S smtp-auth-user=' + mail_account + ' -S smtp-auth-password=' + mail_password +' -S smtp-auth="login" '

        for toMail in email_list:
            cmd_mail = cmd_mail_part + toMail
            err,result = execShell(cmd_mail)

def init_base_info():
    chip_sn,product_sn,hardware_version = get_base_info()
    my_db = ToMongo('wavedevice')
    # num = my_db.get_col("authority_base_info").find().count()
    num = my_db.get_col("authority_base_info").estimated_document_count()
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

def get_camera_sysninfo(my_db:ToMongo):
    '''
    导出配置管理中的摄像头信息
    '''
    
    camera_col = my_db.get_col("odin_device_camera_edit")
    associate_coll = my_db.get_col('odin_device_device_position_associate')
    position_coll = my_db.get_col('odin_device_position') 
    roi_coll = my_db.get_col('odin_device_roi_area_record') 

    cameraSyncRepVO = {}
    cameraSyncRepVO['cameraEditEntityList'] = []
    cameraSyncRepVO['cameraPositionAssociateEntityList'] = []
    cameraSyncRepVO['devicePositionList'] = []
    cameraSyncRepVO['areaRecordEntityList'] = []

    format_pattern = '%Y-%m-%d %H:%M:%S.%f'
    res = camera_col.find({},{'_id':0})
    for data in res:
        item = database_to_dict(data,camerakeys_database,camerakeys_server)        
        item['cameraCreateTime'] = item['cameraCreateTime'].strftime(format_pattern) if item['cameraCreateTime'] else None
        item['cameraUpdateTime'] = item['cameraUpdateTime'].strftime(format_pattern) if item['cameraUpdateTime'] else None
        cameraSyncRepVO['cameraEditEntityList'].append(item)

    asso_items = associate_coll.find({},{'_id':0})
    for asso_item in asso_items:
        info = {}
        position_id = info['positionId'] = asso_item['position_id']
        info['createTime'] = int(asso_item['create_time'].timestamp())*1000 if asso_item['create_time'] else None
        info['deviceType'] = asso_item['device_type']
        info['deviceId'] = asso_item['device_id']
        cameraSyncRepVO['cameraPositionAssociateEntityList'].append(info)

        position_item = position_coll.find_one({'position_id':position_id},{"_id":0})
        position_info = {}
        if position_item:
            position_info = database_to_dict(position_item,positionkeys_database,positionkeys_web)
            position_info['createTime'] = int(position_info['createTime'].timestamp())*1000 if position_info['createTime'] else None
            position_info['updateTime'] = int(position_info['updateTime'].timestamp())*1000 if position_info['updateTime'] else None
            cameraSyncRepVO['devicePositionList'].append(position_info)

    #导出摄像头的roi信息
    roi_items = roi_coll.find({},{'_id':0})
    for roi_item in roi_items:
        item = database_to_dict(roi_item,roi_database,roi_server) 
        item['createTime'] = int(item['createTime'].timestamp())*1000 if item['createTime'] else None
        cameraSyncRepVO['areaRecordEntityList'].append(item)

    return cameraSyncRepVO

def get_control_info(my_db:ToMongo):
    '''
    导出配置管理中的布控任务信息
    '''
    instance_col = my_db.get_col(WORK_FLOW_INSIGHT_MODEL_ALGORITHM_INSTANCE)
    control_manage_col = my_db.get_col("odin_business_control_manage")
    device_asso_col = my_db.get_col(WORK_FLOW_MISSION_DEVICE_ASSOCIATE)
    personel_asso_col = my_db.get_col(WORK_FLOW_MISSION_PERSONNEL_ASSOCIATE)
    personel_group_asso_col = my_db.get_col(WORK_FLOW_MISSION_PERSONNELGROUP_ASSOCIATE)
    mission_col = workflow_mission_collection(my_db)

    controlManageEntity = {}
    controlManageEntity['algorithmInstances'] = []
    controlManageEntity['controlTaskEntityList'] = []
    controlManageEntity['deviceAssociateList'] = []
    controlManageEntity['personnelAssociateList'] = []
    controlManageEntity['personnelGroupAssociateList'] = []
    controlManageEntity['workFlowMissionVos'] = []

    instance_items = instance_col.find({},{'_id':0})
    for instance_item in instance_items:
        item = database_to_dict(instance_item,instance_database,instance_web)
        item['createTime'] = int(item['createTime'].timestamp())*1000 if item['createTime'] else None
        controlManageEntity['algorithmInstances'].append(item)

    control_items = control_manage_col.find({},{'_id':0})
    for control_item in control_items:
        item = database_to_dict(control_item,business_control_database,business_control_web)
        item['createTime']=int(item['createTime'].timestamp())*1000 if item['createTime'] else None
        controlManageEntity['controlTaskEntityList'].append(item)

    device_asso_items = device_asso_col.find({},{'_id':0})
    for device_asso_item in device_asso_items:
        item = {}
        item['deviceId'] = device_asso_item['device_id']
        item['missionId'] = device_asso_item['mission_id']
        item['productKey'] = device_asso_item['product_key']       
        controlManageEntity['deviceAssociateList'].append(item)

    personel_asso_items = personel_asso_col.find({},{'_id':0})
    for personel_asso_item in personel_asso_items:
        item = {}
        item['personnelId'] = personel_asso_item['personnel_id']
        item['missionId'] = personel_asso_item['mission_id']
        #item['modelId'] = personel_asso_item['model_id']       
        controlManageEntity['personnelAssociateList'].append(item)

    personel_group_asso_items = personel_group_asso_col.find({},{'_id':0})
    for personel_group_asso_item in personel_group_asso_items:
        item = {}
        item['missionId'] = personel_group_asso_item['mission_id']
        item['personnelGroupId'] = personel_group_asso_item['personnel_group_id'] 
        controlManageEntity['personnelGroupAssociateList'].append(item)

    missions_items = mission_col.find({},{'_id':0})
    for missions_item in missions_items:
        item = database_to_dict(missions_item,mission_database,mission_web)
        item['createTime']=int(item['createTime'].timestamp())*1000 if item['createTime'] else None     
        controlManageEntity['workFlowMissionVos'].append(item)

    return controlManageEntity

def get_person_info(my_db:ToMongo):
    '''
    导出配置管理中的人脸库信息
    '''
    personnel_col = my_db.get_col(WORK_FLOW_PERSONNEL)
    personnel_image_coll = my_db.get_col(WORK_FLOW_PERSONNEL_IMAGE)
    personnelgroup_asso_coll = my_db.get_col(WORK_FLOW_PERSONNEL_PERSONNELGROUP_ASSOCIATE) 
    personnelgroup_coll = my_db.get_col(WORK_FLOW_PERSONNELGROUP) 

    personEntity = {}
    personEntity['groupAssociateList'] = []
    personEntity['imageList'] = []
    personEntity['workFlowPersonnelGroupVoList'] = []
    personEntity['workFlowPersonnelVoList'] = []

    personel_group_asso_items = personnelgroup_asso_coll.find({},{'_id':0})
    for personel_group_asso_item in personel_group_asso_items:
        item = {}
        item['personnelGroupId'] = personel_group_asso_item['personnel_group_id'] 
        item['personnelId'] = personel_group_asso_item['personnel_id'] 
        personEntity['groupAssociateList'].append(item)

    personnel_image_items = personnel_image_coll.find({},{'_id':0})
    for personnel_image_item in personnel_image_items:
        item = database_to_dict(personnel_image_item,personnel_image_database,personnel_image_web)
        item['createTime'] = int(item['createTime'].timestamp())*1000 if item['createTime'] else None
        personEntity['imageList'].append(item)

    personnelgroup_items = personnelgroup_coll.find({},{'_id':0})
    for personnelgroup_item in personnelgroup_items:
        item = database_to_dict(personnelgroup_item,personnel_group_database,personnel_group_web)
        item['createTime'] = int(item['createTime'].timestamp())*1000 if item['createTime'] else None
        personEntity['workFlowPersonnelGroupVoList'].append(item)

    personnel_items = personnel_col.find({},{'_id':0})
    for personnel_item in personnel_items:
        item = database_to_dict(personnel_item,personnel_database,personnel_web)
        item['createTime'] = int(item['createTime'].timestamp())*1000 if item['createTime'] else None
        personEntity['workFlowPersonnelVoList'].append(item)
    return personEntity    
        
def get_workmodel_info(my_db:ToMongo):
    '''
    导出配置管理中的工作模式信息
    '''
    workmodel_col = my_db.get_col("authority_work_model")

    workModelEntity = {}

    workmodel_item = workmodel_col.find_one({},{'_id':0})

    if workmodel_item:
        workModelEntity['account'] = workmodel_item['service_account'] 
        workModelEntity['ipAddress'] = workmodel_item['service_address'] 
        workModelEntity['ipPort'] = workmodel_item['service_port'] 
        workModelEntity['model'] = workmodel_item['model'] 
        workModelEntity['organizationId'] = workmodel_item['organization_id'] 

    return workModelEntity

def get_sms_info(my_db:ToMongo):
    '''
    导出短信投递信息
    '''
    smstask_col = my_db.get_col("odin_advise_sms_delivery")

    smsDeliveryEntity = []

    format_pattern = '%Y-%m-%d %H:%M:%S.%f'
    smstask_items = smstask_col.find({},{'_id':0})
    for smstask_item in smstask_items:
        item = database_to_dict(smstask_item,smsdelivery_database,smsdelivery_web)
        item['createTime'] = item['createTime'].strftime(format_pattern) if item['createTime'] else None
        item['updateTime'] = item['updateTime'].strftime(format_pattern) if item['updateTime'] else None
        smsDeliveryEntity.append(item)

    return smsDeliveryEntity

def get_webhook_info(my_db:ToMongo):
    '''
    导出告警转发任务
    '''
    webhooktask_col = my_db.get_col("odin_advise_webhook_delivery")

    webhookDeliveryEntity = []

    format_pattern = '%Y-%m-%d %H:%M:%S.%f'
    webhook_items = webhooktask_col.find({},{'_id':0})
    for webhook_item in webhook_items:
        item = database_to_dict(webhook_item,webhook_database,webhook_web)
        item['createTime'] = item['createTime'].strftime(format_pattern) if item['createTime'] else None
        item['updateTime'] = item['updateTime'].strftime(format_pattern) if item['updateTime'] else None
        webhookDeliveryEntity.append(item)

    return webhookDeliveryEntity

def insert_workmodel_info(my_db:ToMongo,workModelEntity):
    '''
    接口说明：配置导入时更新工作模式信息
    '''
    if not workModelEntity:
        return
    serviceOrganizationId = workModelEntity.get("serviceOrganizationId",None)
    ipAddress = workModelEntity.get("ipAddress",None)
    account = workModelEntity.get("account",None)
    ipPort = workModelEntity.get("ipPort",None)
    model = workModelEntity.get("model",None)
    organizationId = workModelEntity.get("organizationId",None)

    item = {'service_address': ipAddress, 
            'service_account': account, 
            'service_organization_id': serviceOrganizationId,
            'service_port': ipPort, 
            'last_modify_time': datetime.now(), 
            'model': model, 
            'create_time': datetime.now(),      
            'organization_id': organizationId }
    my_db.delete("authority_work_model",{},is_one=False)
    
    my_db.insert("authority_work_model",item)

def delete_person_info(my_db,imageList):
    imageid_list = []
    if imageList:
        for image in imageList:
            imageid_list.append(image['imageId'])
    query = {'image_id':{'$nin':imageid_list}}
    image_coll = my_db.get_col(WORK_FLOW_PERSONNEL_IMAGE)
    items = image_coll.find(query)
    for item in items:
        imageid = item['image_id']
        imgpath = PERSON_IMG_URL + imageid
        if os.path.exists(imgpath):
            shutil.rmtree(imgpath)
        identpath = FACE_IDENT_URL + imageid
        if os.path.exists(identpath):
            shutil.rmtree(identpath)
    my_db.delete(WORK_FLOW_PERSONNEL_IMAGE,query,is_one=False)
    imgid_list = image_coll.distinct('image_id')
    return imgid_list

def trans2date(timeParam):
    if not timeParam:
        return timeParam
    format_pattern = '%Y-%m-%d %H:%M:%S'
    typeParam = type(timeParam)
    if typeParam == int:
        res = datetime.fromtimestamp(timeParam/1000)
    elif typeParam == str:
        res = datetime.strptime(timeParam,format_pattern)
    else:
        res = datetime.now()
    return res

def insert_alg_info(my_db:ToMongo,algorithmConstantEntityList):
    '''
    接口说明：配置导入时更新算法信息
    '''
    if not algorithmConstantEntityList:
        return
    for entity in algorithmConstantEntityList:
        algorithmServiceNum = entity.get('algorithmServiceNum')
        algorithmSoundType = entity.get('algorithmSoundType')
        rateNum = entity.get('rateNum')
        if algorithmSoundType == 1:
            entity['algorithmSoundType'] = 2
        elif algorithmSoundType == 2:
            entity['algorithmSoundType'] = 1
        query = {'algorithm_service_num':algorithmServiceNum}
        entity['rateNum'] = float(rateNum) if rateNum else None
        item = database_to_dict3(entity,constant_server,constant_database)
        if (CROSSING_CONFIG['use'] == 1) and (algorithmServiceNum == PEDESTRIAN_ALG_NUM or algorithmServiceNum == VEHICLE_ALG_NUM):
            # 当红绿灯项目时，对应识别算法识别时间间隔为1
            mainlogger.debug("=======红绿灯项目保持相关识别模型时间间隔为1s======={}".format(item))
            item['algorithm_interval'] = 1
        my_db.update(WORK_FLOW_ALGORITHM_CONSTANT,query,{'$set':item})
    return

def insert_person_info(my_db:ToMongo,personEntity):
    '''
    接口说明：配置导入时更新人脸库信息
    '''
    if not personEntity:
        return
    groupAssociateList = personEntity.get("groupAssociateList",None)
    imageList = personEntity.get("imageList",None)
    workFlowPersonnelGroupVoList = personEntity.get("workFlowPersonnelGroupVoList",None)
    workFlowPersonnelVoList = personEntity.get("workFlowPersonnelVoList",None)
    imageFileList = personEntity.get("imageFileList",None)

    #不为空才去更新数据库，否则不变   
    my_db.delete(WORK_FLOW_PERSONNEL_PERSONNELGROUP_ASSOCIATE,{},is_one=False)
    if  groupAssociateList:
        for personel_group_asso_item in groupAssociateList:
            #遇到出错的跳过
            try:
                item= {}
                item['personnel_group_id'] = personel_group_asso_item['personnelGroupId']
                item['personnel_id'] = personel_group_asso_item['personnelId']
                my_db.insert(WORK_FLOW_PERSONNEL_PERSONNELGROUP_ASSOCIATE,item)
            except Exception as e:
                print('Insert Error---groupAssociateList:',e)
                continue

    
    imid_list = delete_person_info(my_db,imageList)
    if  imageList:
        for item in imageList:
            try:
                imgid = item['imageId']
                personnel_image_item = database_to_dict(item,personnel_image_web,personnel_image_database)
                personnel_image_item['create_time'] = trans2date(personnel_image_item['create_time'])
                if imgid in imid_list:
                    del personnel_image_item['image_check_url']
                    del personnel_image_item['image_url']
                    query = {'image_id':imgid}
                    my_db.update(WORK_FLOW_PERSONNEL_IMAGE,query,{'$set':personnel_image_item})
                else:
                    my_db.insert(WORK_FLOW_PERSONNEL_IMAGE,personnel_image_item)
                
            except Exception as e:
                print('Insert Error---imageList:',e)
                continue

    
    my_db.delete(WORK_FLOW_PERSONNELGROUP,{},is_one=False)
    if  workFlowPersonnelGroupVoList:
        for item in workFlowPersonnelGroupVoList:
            try:
                personnelgroup_item = database_to_dict(item,personnel_group_web,personnel_group_database)
                personnelgroup_item['create_time'] = trans2date(personnelgroup_item['create_time'])
                my_db.insert(WORK_FLOW_PERSONNELGROUP,personnelgroup_item)
            except Exception as e:
                print('Insert Error---workFlowPersonnelGroupVoList:',e)
                continue

    
    my_db.delete(WORK_FLOW_PERSONNEL,{},is_one=False)
    if  workFlowPersonnelVoList:
        for item in workFlowPersonnelVoList:
            try:
                personnel_item = database_to_dict(item,personnel_web,personnel_database)
                personnel_item['create_time'] = trans2date(personnel_item['create_time'])
                my_db.insert(WORK_FLOW_PERSONNEL,personnel_item)
            except Exception as e:
                print('Insert Error---workFlowPersonnelVoList:',e)
                continue
      
    if imageFileList:
        face_list = []
        for item in imageFileList:
            filename = item['fileName']
            filestr = item['bytes']
            imgid = filename.split('/')[1]
            temp_url = PERSON_IMG_URL + imgid + '/'
            if not os.path.exists(temp_url):
                os.makedirs(temp_url)
                os.chmod(temp_url,0o777)
            img_url =  temp_url + imgid + '.jpg'
            #把人脸图存到本地
            if not os.path.exists(img_url):
                with open(img_url,"wb") as outfile:
                    filebytes = base64.b64decode(filestr)
                    outfile.write(filebytes)

            face_msg = {}
            face_msg['image_id'] = imgid
            face_msg['image_h'] = None
            face_msg['image_w'] = None
            face_msg['image_data'] = filestr
            face_msg['image_type'] = '0'
            face_list.append(face_msg)

        from algorith_server.AlgorithServer_new import SenderThread
        sender = SenderThread(context=[])
        host_ip = glv.get_value('host_ip',None)
        port = glv.get_value('nginx_port',8088)
    #    mainlogger.debug('face_list: %s'%face_list)
        for faceItem in face_list:
            face_msg_str = json.dumps(faceItem)
            total_msg = pack_face_3005(face_msg_str)
            sender.send_face_message(facemsg=total_msg)
            n=0
            while True:
                num = faceidentification_queue.qsize()
                if num == 0:
                    if n == 5:
                        result = None
                        break
                    n+=1
                    time.sleep(1)
                else:
                    result = faceidentification_queue.get()
                    break
            try:
                if not result:
                    continue
                msg_result = json.loads(result)
                face_features = msg_result.get("face_features")
                imgid = msg_result.get("image_id")
                if not face_features:
                    continue
                #把人脸特征存到本地
                feature_dir = FACE_IDENT_URL + imgid + '/'
                feature_url = feature_dir + imgid + ".json"
                # if os.path.exists(feature_url):
                #     return
                if not os.path.exists(feature_dir):
                    os.makedirs(feature_dir)
                img_pathhead = 'http://%s:%s/net-web/face_images/'%(host_ip,port)
                feature_pathhead = 'http://%s:%s/net-web/face_features/'%(host_ip,port)
                face_url = img_pathhead   + imgid + ".jpg"
                image_check_url = feature_pathhead + imgid + ".json"
                if not face_features or  face_features == "":
                    image_operation_statue = 100
                    image_check_url = None
                else:
                    with open(feature_url,"w") as outfile:
                        outfile.write(face_features)
                    image_operation_statue = 0
                image_item = {  'image_operation_statue':image_operation_statue,
                                'image_url':face_url,
                                'image_check_url':image_check_url}
                my_db.update(WORK_FLOW_PERSONNEL_IMAGE,{"image_id":imgid},{"$set":image_item})

            except Exception as e:
                mainlogger.debug("--同步人脸error:%s"%e)       

def insert_sound_server(my_db:ToMongo,soundServiceEntity):
    if not soundServiceEntity:
        return
    serviceType = soundServiceEntity.get('serviceType')
    item = dict()
    if serviceType == 1:  
        server_item = my_db.get_col("odin_device_itc_server").find_one()
        item['itc_server_id'] = soundServiceEntity.get('serviceId')
        item['itc_server_address'] = soundServiceEntity.get('serviceAddress')
        item['itc_server_port'] = soundServiceEntity.get('servicePort')
        item['itc_server_account'] = soundServiceEntity.get('account')
        item['itc_server_password'] = soundServiceEntity.get('pwd')
        if not server_item:
            my_db.insert("odin_device_itc_server",item)
        else:
            my_db.update("odin_device_itc_server",{},{"$set":item})
    elif serviceType == 2:
        server_item = my_db.get_col("odin_device_lings_server").find_one()
        item['lings_server_id'] = soundServiceEntity.get('serviceId')
        item['lings_server_address'] = soundServiceEntity.get('serviceAddress')
        item['lings_server_port'] = soundServiceEntity.get('servicePort')
        item['lings_tts_port'] = 10008
        item['lings_server_account'] = soundServiceEntity.get('account')
        item['lings_server_password'] = soundServiceEntity.get('pwd')
        if not server_item:
            my_db.insert("odin_device_lings_server",item)
        else:
            my_db.update("odin_device_lings_server",{},{"$set":item})
    return

def insert_485sound_device(my_db:ToMongo,deviceSoundEntitieList):
    if not deviceSoundEntitieList:
        return
    for entity in deviceSoundEntitieList:
        newItem = {"equip_name":entity.get('equName'),
                   "equip_ip":entity.get('equIp'),
                   "equip_type":4,  # 4表示485设备
                   "equip_port":entity.get('equPort'),
                   "alarm_mute":entity.get('alarmMute'),
                   "mission_id":entity.get('missionId'),
                   "reset_delay_time":entity.get('resetDelayTime'),
                   "equip_model":entity.get('equipModel'),
                   "connection_method":entity.get('connectionMethod'),
                   "control_type":entity.get('equControlType'),
                   "lighting_method":entity.get('lightingMethod'),
                   "sound_alarm":entity.get('soundAlarm'),
                   "device_addr":entity.get('equ485Address')}
        my_db.insert("odin_device_equip",newItem)
    return

def filter_sound_info(terminalList,mac):
    for item in terminalList:
        EndpointMac = item.get('EndpointMac')
        if EndpointMac == mac:
            return item
    return

def insert_sound_info(my_db:ToMongo,soundNos,soundServiceEntity):
    if not soundNos or not soundServiceEntity:
        return
    my_db.delete('odin_device_sound',{"use_by":"0"},is_one=False)#删除布控任务绑定的音响 1表示动环使用的音响 方便去重
    sound_col = my_db.get_col('odin_device_sound')
    try:
        serviceAddress = soundServiceEntity.get('serviceAddress')
        servicePort = soundServiceEntity.get('servicePort')
        serviceType = soundServiceEntity.get('serviceType')
        serverUrl = "http://%s:%s"%(serviceAddress,servicePort)
        sound_id_list = sound_col.distinct('sound_id')
        if serviceType == 2:
            #菱声音响
            Linginstance = LingsSound(tts_url=None,server_url=serverUrl,sound_no=None,volume=100)
            for entity in soundNos:
                sound_no = entity.get('mac')
                alarmMute = entity.get('alarmMute')
                mission_id = entity.get('missionId')
                soundId = entity.get('soundId')
                name = entity.get('equName')

                detailInfo = Linginstance.getDeviceBySN(sound_no=sound_no)
                mainlogger.debug("Linginstance.getDeviceBySN detailInfo:%s"%detailInfo)
                extra = detailInfo.get('extra')
                config = extra.get('config')
                status = str(detailInfo.get('status'))
                soundIp = config.get('ip')
                item_equip = {'missionId':mission_id,'equipId':soundId,'equipType':2,'equipIp':soundIp,'equipName':name,'alarmMute':alarmMute}
                item_equip = database_to_dict(item_equip,equip_web,equip_database)
                my_db.insert('odin_device_equip',item_equip)
                item_sound = {'soundId':soundId,
                            'soundType':'2',#菱声
                            'soundName':name,
                            'soundNo':sound_no,
                            'soundIp':soundIp,
                            'soundStatus':status,
                            'soundPort':8888,
                            "use_by":"0"
                            }
                if soundId not in sound_id_list:
                  item_sound = database_to_dict(item_sound,sound_web,sound_database)
                  my_db.insert('odin_device_sound',item_sound)
        elif serviceType == 1:
            #itc音响
            account = soundServiceEntity.get('account')
            password = soundServiceEntity.get('pwd')
            VoiceInstance = VoiceBoxUtils(serverUrl,account,password,volume=70)
            VoiceInstance.login()
            resp = VoiceInstance.getterminalinfo().json()
            result = resp.get("result")
            if result != 200:
                mainlogger.debug("获取itc终端失败,response:%s"%resp)
                return
            data = resp.get('data')
            EndPointsArray = data.get('EndPointsArray')
            if not EndPointsArray:
                mainlogger.debug("未查询到itc终端,response:%s"%resp)
                return
            for entity in soundNos:
                sound_no = entity.get('mac')
                alarmMute = entity.get('alarmMute')
                mission_id = entity.get('missionId')
                soundInfo = filter_sound_info(EndPointsArray,sound_no)
                if not soundInfo:
                    return
                name = soundInfo.get('EndpointName')
                EndpointID = soundInfo.get('EndpointID')
                soundIp = soundInfo.get('EndpointIP')
                statusNum = soundInfo.get('Status')
                status = '0' if statusNum == 2 else '1'
                soundId = uuid.uuid4().hex
                item_equip = {'missionId':mission_id,'equipId':soundId,'equipType':3,'equipIp':soundIp,'equipName':name,'alarmMute':alarmMute}
                mainlogger.debug('*****item_equip : %s'%item_equip)
                item_equip = database_to_dict(item_equip,equip_web,equip_database)
                my_db.insert('odin_device_equip',item_equip)
                item_sound = {'soundId':soundId,
                            'soundType':'1',#菱声
                            'soundName':name,
                            'soundNo':sound_no,
                            'soundIp':soundIp,
                            'soundStatus':status
                            }
                item_sound = database_to_dict(item_sound,sound_web,sound_database)
                my_db.insert('odin_device_sound',item_sound)

    except Exception as e:
        import traceback
        mainlogger.debug("insert_sound_info Error:%s"%traceback.format_exc())
    return

def insert_sound_entity(my_db:ToMongo,soundEntities,soundServiceEntity):
    #内网版插入音响信息
    if not soundEntities or not soundServiceEntity:
        return
    my_db.delete('odin_device_equip',{},is_one=False)
    my_db.delete('odin_device_sound',{},is_one=False)
    try:
        serviceAddress = soundServiceEntity.get('serviceAddress')
        servicePort = soundServiceEntity.get('servicePort')
        serviceType = soundServiceEntity.get('serviceType')
        serverUrl = "http://%s:%s"%(serviceAddress,servicePort)
        if serviceType == 2:
            soundType = "2"
            equipType = 3
            equipName = "菱声音响"
            soundPort = 8888
        elif serviceType == 1:
            soundType = "1"
            equipType = 2
            equipName = "itc音响"
            soundPort = None
        for item in soundEntities:
            equip_id = uuid.uuid4().hex
            res = dict()
            res['soundIp'] = item.get('soundIp')
            res['soundNo'] = item.get('soundSn')
            res['soundName'] = item.get('soundName')
            res['soundStatus'] = item.get('soundStatus')
            missionId = item.get('missionId')
            res['soundId'] = equip_id
            res['soundType'] = soundType
            res['soundPort'] = soundPort
            equipEntity = {'missionId':missionId,
                            'equipId':equip_id,
                            'equipType':equipType,
                            'equipIp':item.get('soundIp'),
                            'equipName':equipName}
            item_equip = database_to_dict(equipEntity,equip_web,equip_database)
            item_sound = database_to_dict(res,sound_web,sound_database)

            my_db.insert('odin_device_sound',item_sound)
            my_db.insert('odin_device_equip',item_equip)
    except Exception as e:
        mainlogger.debug("insert_sound_entity error:%s"%e)


def insert_constant_info(my_db:ToMongo,algorithmConstantEntityList):
    '''
    接口说明：同步平台的算法基础设置
    '''
    if not algorithmConstantEntityList:
        return
    try:
        for item in algorithmConstantEntityList:
            item = database_to_dict2(item,constant_web,constant_database)
            rateNum = item.get('rateNum')
            item['rateNum'] = float(rateNum) if rateNum else None
            query = {'algorithm_service_num':item.get('algorithm_service_num')}
            my_db.update(WORK_FLOW_ALGORITHM_CONSTANT,query,{'$set':item})
    except Exception as e:
        mainlogger.debug("同步algorithmConstantEntityList error:%s"%e)
    return


def insert_control_info(my_db:ToMongo,controlManageEntity):
    '''
    接口说明：配置导入时更新布控任务信息
    '''
    if not controlManageEntity:
        return
    algorithmInstances = controlManageEntity.get("algorithmInstances",None)
    controlTaskEntityList = controlManageEntity.get("controlTaskEntityList",None)
    deviceAssociateList = controlManageEntity.get("deviceAssociateList",None)
    personnelAssociateList = controlManageEntity.get("personnelAssociateList",None)
    personnelGroupAssociateList = controlManageEntity.get("personnelGroupAssociateList",None)
    workFlowMissionVos = controlManageEntity.get("workFlowMissionVos",None)
    ipAddress = controlManageEntity.get("ipAddress")

    algorithmConstantEntityList = controlManageEntity.get("algorithmConstantEntityList")
    soundServiceEntity = controlManageEntity.get("soundServiceEntity")
    deviceSoundEntitieList = controlManageEntity.get("deviceSoundEntitieList")
    soundNos = controlManageEntity.get("soundNos")
    soundEntities = controlManageEntity.get("soundEntities")

    #弯道项目
    cornerOvertakingProject = controlManageEntity.get("cornerOvertakingProject",None)
    cornerOvertakingConfigList = controlManageEntity.get("cornerOvertakingConfigList",None)

    #交通灯项目
    trafficLightProject = controlManageEntity.get("trafficLightProject",None)
    trafficLightConfigList = controlManageEntity.get("trafficLightConfigList",None)
    trafficLightRuler = controlManageEntity.get("trafficLightRuler",None)
    
    my_db.delete(WORK_FLOW_INSIGHT_MODEL_ALGORITHM_INSTANCE,{},is_one=False)
    if  algorithmInstances:
        for item in algorithmInstances:
            try:
                instance_item = database_to_dict(item,instance_web,instance_database)     
                instance_item['create_time'] = trans2date(instance_item['create_time'])
                my_db.insert(WORK_FLOW_INSIGHT_MODEL_ALGORITHM_INSTANCE,instance_item)
            except Exception as e:
                print('Insert Error--algorithmInstances:',e)
                continue

    
    my_db.delete("odin_business_control_manage",{},is_one=False)
    if  controlTaskEntityList:
        for item in controlTaskEntityList:
            try:
                if item.get('stallFlag') == 1:
                    continue
                control_item = database_to_dict(item,business_control_web,business_control_database)
                control_item['create_time'] = trans2date(control_item['create_time'])
                my_db.insert("odin_business_control_manage",control_item)
            except Exception as e:
                print('Insert Error---controlTaskEntityList:',e)
                continue

    
    my_db.delete(WORK_FLOW_MISSION_DEVICE_ASSOCIATE,{},is_one=False)
    if  deviceAssociateList:
        for item in deviceAssociateList:
            try:
                device_asso_item = {}
                device_asso_item['device_id'] = item['deviceId']
                device_asso_item['mission_id'] = item['missionId']
                device_asso_item['product_key']  = item['productKey']
                my_db.insert(WORK_FLOW_MISSION_DEVICE_ASSOCIATE,device_asso_item)
            except Exception as e:
                print('Insert Error---deviceAssociateList:',e)
                continue

        
    
    my_db.delete(WORK_FLOW_MISSION_PERSONNEL_ASSOCIATE,{},is_one=False)
    if  personnelAssociateList:
        for item in personnelAssociateList:
            try:
                personel_asso_item = {}
                personel_asso_item['personnel_id'] = item['personnelId']
                personel_asso_item['mission_id'] = item['missionId']
              #  personel_asso_item['model_id']  = item['modelId']
                my_db.insert(WORK_FLOW_MISSION_PERSONNEL_ASSOCIATE,personel_asso_item)
            except Exception as e:
                print('Insert Error-----personnelAssociateList:',e)
                continue

    
    my_db.delete(WORK_FLOW_MISSION_PERSONNELGROUP_ASSOCIATE,{},is_one=False)
    if  personnelGroupAssociateList:
        for item in personnelGroupAssociateList:
            try:
                personel_group_asso_item = {}
                personel_group_asso_item['mission_id'] = item['missionId']
                personel_group_asso_item['personnel_group_id']  = item['personnelGroupId']
                my_db.insert(WORK_FLOW_MISSION_PERSONNELGROUP_ASSOCIATE,personel_group_asso_item)
            except Exception as e:
                print('Insert Error------personnelGroupAssociateList:',e)
                continue

    
    my_db.delete(WORK_FLOW_MISSION,{},is_one=False)
    my_db.delete(WORK_FLOW_MISSION_HIDDEN,{},is_one=False)
    if  workFlowMissionVos:
        for item in workFlowMissionVos:
            try:
                missions_item = database_to_dict(item,mission_web,mission_database)
                missions_item['create_time'] = trans2date(missions_item['create_time'])
                if missions_item.get('algorithm_id') == '173':
                    #三小场所的任务
                    my_db.insert(WORK_FLOW_MISSION_HIDDEN,missions_item)
                else:
                    my_db.insert(WORK_FLOW_MISSION,missions_item)
            except Exception as e:
                print('Insert Error-------workFlowMissionVos:',e)
                continue

    if CURVE_CONFIG['use'] == 1:
        #插入弯道数据
        insert_curve_info(my_db,cornerOvertakingProject,cornerOvertakingConfigList)

    if CROSSING_CONFIG['use'] == 1:
        #插入交通灯项目配置
        insert_crossing_info(my_db,trafficLightProject,trafficLightConfigList,trafficLightRuler)

    if ipAddress:
        #更新minio地址
        update_minio_address(my_db,ipAddress)

    if algorithmConstantEntityList:
        #更新算法基础设置
        insert_constant_info(my_db,algorithmConstantEntityList)

    if soundServiceEntity:
        #插入音响服务器数据
        insert_sound_server(my_db,soundServiceEntity)

    my_db.delete('odin_device_equip',{},is_one=False)
    if soundNos:
        #插入音响设备数据
        insert_sound_info(my_db,soundNos,soundServiceEntity)

    if soundEntities:
        #内网版插入音响
        insert_sound_entity(my_db,soundEntities,soundServiceEntity)

    if deviceSoundEntitieList:
        #  插入联控设备
        insert_485sound_device(my_db,deviceSoundEntitieList)

def insert_camera_info(my_db:ToMongo,cameraSyncRepVO):
    '''
    接口说明：配置导入时更新摄像头信息
    '''
    if not cameraSyncRepVO:
        return
    cameraEditEntityList = cameraSyncRepVO.get("cameraEditEntityList",None)
    cameraPositionAssociateEntityList = cameraSyncRepVO.get("cameraPositionAssociateEntityList",None)
    devicePositionList = cameraSyncRepVO.get("devicePositionList",None)
    areaRecordEntityList = cameraSyncRepVO.get("areaRecordEntityList",None)
    cameraBaseMapList =  cameraSyncRepVO.get("cameraBaseMapList",None) #摄像机底图

    format_pattern = '%Y-%m-%d %H:%M:%S'
    camera_url_list = []
    
    my_db.delete("odin_device_camera_edit",{},is_one=False)
    if  cameraEditEntityList:
        for item in cameraEditEntityList:
            try:
                data = database_to_dict(item,camerakeys_server,camerakeys_database)
                camera_url_list.append(data['main_url'])
                data['camera_status'] = str(data['camera_status'])
                if data['create_time']:
                    data['create_time'] = datetime.strptime(data['create_time'],format_pattern)
                if data['update_time']:
                    data['update_time'] = datetime.strptime(data['update_time'],format_pattern)
                my_db.insert("odin_device_camera_edit",data)
            except Exception as e:
                print('Insert Error---cameraEditEntityList:',e)
                continue

    
    my_db.delete("odin_device_device_position_associate",{},is_one=False)
    if  cameraPositionAssociateEntityList:
        for info in cameraPositionAssociateEntityList:
            try:
                asso_item = {}
                asso_item['device_id'] = info['deviceId']
                asso_item['position_id'] = info['positionId']
                asso_item['create_time'] = trans2date(info['createTime'])
                asso_item['device_type'] = info['deviceType']
                my_db.insert("odin_device_device_position_associate",asso_item)
            except Exception as e:
                print('Insert Error---cameraPositionAssociateEntityList:',e)
                continue

    
    my_db.delete("odin_device_position",{},is_one=False)
    if  devicePositionList:
        for position_info in devicePositionList:
            try:
                position_item = database_to_dict(position_info,positionkeys_web,positionkeys_database)
                position_item['create_time'] = trans2date(position_item['create_time'])
                position_item['update_time'] = trans2date(position_item['update_time'])
                my_db.insert("odin_device_position",position_item)
            except Exception as e:
                print('Insert Error---devicePositionList:',e)
                continue

    #摄像头ROI信息    
    my_db.delete("odin_device_roi_area_record",{},is_one=False)
    if areaRecordEntityList:
        for roi_info in areaRecordEntityList:
            try:
                roi_item = database_to_dict(roi_info,roi_server,roi_database)
                roi_item['create_time'] = trans2date(roi_item['create_time'])
                my_db.insert("odin_device_roi_area_record",roi_item)
            except Exception as e:
                print('Insert Error---:areaRecordEntityList',e)
                continue

    #摄像头对应的底图
    insert_underlay(my_db,cameraBaseMapList)
    
    return 

def insert_underlay(my_db:ToMongo,cameraBaseMapList):
    mainlogger.debug("*********************cameraBaseMapList************%s"%cameraBaseMapList)
    if not cameraBaseMapList:
        my_db.delete("odin_device_underlay",{},is_one=False)
        if os.path.exists(UNDERLAY_URL):
            for file in os.listdir(UNDERLAY_URL):
                filepath = UNDERLAY_URL + file
                shutil.rmtree(filepath) 
    else:
        col = my_db.get_col("odin_device_underlay")
        #新的底图 #数量较多，考虑增量更新
        new_imgList = []
        for item in cameraBaseMapList:
            img_id = item.get("baseMapId")
            new_imgList.append(img_id)
        
        deleteItems = col.find({'img_id':{'$nin':new_imgList}})
        for item in deleteItems:
            camera_id = item.get("camera_id")
            img_id = item.get("img_id")
            if not camera_id or not img_id:
                continue
            imgpath = UNDERLAY_URL + camera_id + '/' + img_id + '.jpg'
            res = col.delete_one({"img_id":img_id})
            deletefile(imgpath)

        #旧的底图
        old_imgList = col.distinct("img_id")  

        for item in cameraBaseMapList:
            img_id = item.get("baseMapId")
            if img_id in old_imgList:
                continue
            camera_id = item.get("cameraId")
            algorithm_constant_num = item.get("algorithmConstantNum")
            minio_url = item.get("baseMapUrl")

            filepath = UNDERLAY_URL + camera_id + '/' + img_id + '.jpg'
            img_thread= Thread(target=get_minio_img,args=[minio_url,filepath])
            img_thread.start()

            newItem = { 'img_id':img_id,'camera_id':camera_id,'algorithm_constant_num':algorithm_constant_num } 
            result = col.insert_one(newItem)

        return

def insert_sms_info(my_db:ToMongo,smsDeliveryEntity):
    '''
    接口说明：配置导入时更新短信投递信息
    '''
    if not smsDeliveryEntity:
        return

    format_pattern = '%Y-%m-%d %H:%M:%S.%f'
    
    my_db.delete("odin_advise_sms_delivery",{},is_one=False)
    for item in smsDeliveryEntity:
        try:
            data = database_to_dict(item,smsdelivery_web,smsdelivery_database)
            if data['create_time']:
                data['create_time'] = datetime.strptime(data['create_time'],format_pattern)
            if data['update_time']:
                data['update_time'] = datetime.strptime(data['update_time'],format_pattern)
            my_db.insert("odin_advise_sms_delivery",data)
        except Exception as e:
            print('Insert Error---smsDeliveryEntity:',e)
            continue

def insert_webhook_info(my_db:ToMongo,webhookDeliveryEntity):
    '''
    接口说明：配置导入时更新短信投递信息
    '''
    if not webhookDeliveryEntity:
        return

    format_pattern = '%Y-%m-%d %H:%M:%S.%f'
    
    my_db.delete("odin_advise_webhook_delivery",{},is_one=False)
    for item in webhookDeliveryEntity:
        try:
            data = database_to_dict(item,webhook_web,webhook_database)
            if data['create_time']:
                data['create_time'] = datetime.strptime(data['create_time'],format_pattern)
            if data['update_time']:
                data['update_time'] = datetime.strptime(data['update_time'],format_pattern)
            my_db.insert("odin_advise_webhook_delivery",data)
        except Exception as e:
            print('Insert Error---webhookDeliveryEntity:',e)
            continue

def insert_position_info(my_db:ToMongo,positionList):
    '''
    从云平台同步位置信息；
    '''
    
    my_db.delete("odin_device_position",{},is_one=False)
    if  positionList:
        for position_info in positionList:
            try:
                position_item = database_to_dict(position_info,positionkeys_web,positionkeys_database)

                position_item['create_time'] = trans2date(position_item['create_time'])

                position_item['update_time'] = trans2date(position_item['update_time'])
                my_db.insert("odin_device_position",position_item)
            except Exception as e:
                print('Insert Error---positionList:',e)
                continue
            
def insert_version_info(my_db:ToMongo,versionList):
    '''
    从云平台同步版本信息；
    '''
    if not versionList:
        return
    my_db.delete("system_data_version",{},is_one=False)  
    for version_item in versionList:     
        try:    
            item = database_to_dict(version_item,version_server,version_database)
            item['modify_time'] = trans2date(item['modify_time'])
            my_db.insert("system_data_version",item)
        except Exception as e:
            print('Insert Error---versionList:',e)
            continue

def insert_curve_info(my_db:ToMongo,cornerOvertakingProject,cornerOvertakingConfigList):
    '''
    从云平台同步弯道信息;
    cornerOvertakingProject:弯道项目信息
    cornerOvertakingConfigList:弯道详细配置
    '''
    col_project = my_db.get_col('corner_overtaking_project')
    col_config =  my_db.get_col('corner_overtaking_config')

    # 删除旧的弯道配置
    col_project.delete_many({})
    col_config.delete_many({})

    # 插入新弯道配置
    if cornerOvertakingProject:     
        try:    
            item = database_to_dict(cornerOvertakingProject,curve_project_server,curve_project_database)
            col_project.insert_one(item)
        except Exception as e:
            mainlogger.exception(e)
        
        for item in cornerOvertakingConfigList:     
            try:    
                item = database_to_dict(item,curve_config_server,curve_config_database)
                col_config.insert_one(item)
            except Exception as e:
                mainlogger.exception(e)
                continue

    # 重新拉取弯道任务
    instance = SerialNetServer(context=None)
    instance.get_all_task()   
    return

def insert_crossing_info(my_db:ToMongo,crossProject,crossConfigList,crossRuler):
    '''
    从云平台同步路口信息;
    crossProject:路口项目信息
    crossConfigList:路口详细配置
    crossRuler:红绿灯规则
    '''
    col_project = my_db.get_col('traffic_light_project')
    col_config =  my_db.get_col('traffic_light_config')
    col_ruler =  my_db.get_col('traffic_light_ruler')

    # 删除旧的弯道配置
    col_project.delete_many({})
    col_config.delete_many({})
    col_ruler.delete_many({})

    # 插入新路口配置
    if crossProject:     
        try:    
            item = database_to_dict(crossProject,cross_project_server,cross_project_database)
            col_project.insert_one(item)
        except Exception as e:
            mainlogger.exception(e)

    mainlogger.debug("开始进行数据同步==========begin====={}====".format(crossConfigList))
    if  crossConfigList: 
        deviceList = []
        for item in crossConfigList:
            mainlogger.debug("=======crossConfigList item: {}".format(item))
            try:    
                item = database_to_dict(item,cross_config_server,cross_config_database)
                insert_result = col_config.insert_one(item)
                mainlogger.debug("=======摄像头信息 写入结果: {} {}".format(item, insert_result))
                deviceList.append((item['camera_id'], item['camera_id2']))
            except Exception as e:
                mainlogger.exception(e)
                continue

        control_id = uuid.uuid4().hex
        mainlogger.debug("--------插入红绿灯任务------{}".format(control_id))
        instance_1 = RoadMission(control_id)
        instance_1.insert_db(my_db)
        instance_2 = RoadAssoDevice(deviceList, control_id)
        instance_2.insert_db(my_db)
        instance_3 = RoadInstance(control_id)
        instance_3.insert_db(my_db)
    mainlogger.debug("开始进行数据同步==========end=========")

    if crossRuler:
        try:
            item = database_to_dict(crossRuler,cross_ruler_server,cross_ruler_database)
            col_ruler.insert_one(item)
        except Exception as e:
             mainlogger.exception(e)

    # 重新监听雷达消息(雷达配置可能会有变动)
    # thread_radar = threading.Thread(target=start_listen_radar_v2)
    # thread_radar.start()
    return

def update_minio_address(my_db:ToMongo,minio_addr):
    '''
    更新云平台的minio同步地址
    '''
    if not minio_addr:
        return
    try:
        item = {"service_minio_address":minio_addr}
        my_db.update('authority_work_model',query={},new={'$set':item})
    except:
        pass
    return

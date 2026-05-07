import subprocess
from threading import Thread
import time
import shutil
import os
import json
from Utils.db import ToMongo
from config import BASE_INFO
from datetime import datetime,timedelta
from .sys_config import *
from config import PERSON_IMG_URL,FACE_IDENT_URL,EMERGENCY_IMG_PATH,DISK_PATH
import base64
from algorith_server.AgreementBuilder import pack_face_3005
from algorith_server.Alibabasms import SendSmsResqueset
from msg_queue import faceidentification_queue
import Utils.glv as glv
from Utils.voicedevice_utils import *

import Utils.edgebox_repo  # noqa: F401
from edgebox_db.mongo_collections import (
    WORK_FLOW_ALGORITHM_CONSTANT,
    WORK_FLOW_INSIGHT_MODEL_ALGORITHM_INSTANCE,
    WORK_FLOW_MISSION,
    WORK_FLOW_MISSION_DEVICE_ASSOCIATE,
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
        disk_percent = int(disk_result.split()[-2].split('%')[0])
        # disk_left = float(disk_result.split()[-3][:-1])
        disk_left = disk_result.split()[-3]
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
        err0,result = execShell("/sbin/ifconfig eth0")
        result = result.split()
    except Exception as e:
        result = None
    return result[5]

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
    try:
        err1,result1= execShell("/bm_bin/bm_get_basic_info")
        err2,result2 = execShell("/bm_bin/bm_version")

        hardware_version = result2.split()[4]

        info = result1.split('\n')        
        chipsn_row = info[4]
        if 'chip' in chipsn_row:
            chip_sn = chipsn_row.split()[-1]
        else:
            chip_sn = None
        
        productsn_row = info[5]
        if 'product' in productsn_row:
            product_sn = productsn_row.split()[-1]
        else:
            product_sn = None
    except Exception as e:
        chip_sn,product_sn,hardware_version = None,None,None
    return chip_sn,product_sn,hardware_version

def get_base_info():
    filepath = "/bm_bin/bm_get_basic_info"
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
    mission_col = my_db.get_col(WORK_FLOW_MISSION)

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
        if os.path.exists(imgpath):
            shutil.rmtree(identpath)
    my_db.delete(WORK_FLOW_PERSONNEL_IMAGE,query,is_one=False)
    imgid_list = image_coll.distinct('image_id')
    return imgid_list

def insert_alg_info(my_db:ToMongo,algorithmConstantEntityList):
    '''
    接口说明：配置导入时更新算法信息
    '''
    if not algorithmConstantEntityList:
        return
    for entity in algorithmConstantEntityList:
        algorithmServiceNum = entity.get('algorithmServiceNum')
        algorithmSoundType = entity.get('algorithmSoundType')
        if algorithmSoundType == 1:
            entity['algorithmSoundType'] = 2
        elif algorithmSoundType == 2:
            entity['algorithmSoundType'] = 1
        query = {'algorithm_service_num':algorithmServiceNum}
        item = database_to_dict3(entity,constant_web,constant_database)
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
                if personnel_image_item['create_time']:
                    personnel_image_item['create_time'] = datetime.fromtimestamp(personnel_image_item['create_time']/1000)
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
                if personnelgroup_item['create_time']:
                    personnelgroup_item['create_time'] = datetime.fromtimestamp(personnelgroup_item['create_time']/1000)
                my_db.insert(WORK_FLOW_PERSONNELGROUP,personnelgroup_item)
            except Exception as e:
                print('Insert Error---workFlowPersonnelGroupVoList:',e)
                continue

    
    my_db.delete(WORK_FLOW_PERSONNEL,{},is_one=False)
    if  workFlowPersonnelVoList:
        for item in workFlowPersonnelVoList:
            try:
                personnel_item = database_to_dict(item,personnel_web,personnel_database)
                if personnel_item['create_time']:
                    personnel_item['create_time'] = datetime.fromtimestamp(personnel_item['create_time']/1000)
                my_db.insert(WORK_FLOW_PERSONNEL,personnel_item)
            except Exception as e:
                print('Insert Error---workFlowPersonnelVoList:',e)
                continue
    
    if imageFileList:
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
            if os.path.exists(img_url):
                continue
            with open(img_url,"wb") as outfile:
                filebytes = base64.b64decode(filestr)
                outfile.write(filebytes) 
            
            face_msg = {}
            face_msg['image_id'] = imgid
            face_msg['image_h'] = None
            face_msg['image_w'] = None
            face_msg['image_data'] = filestr
            face_msg['image_type'] = '0'

            face_msg_str = json.dumps(face_msg)
            total_msg = pack_face_3005(face_msg_str)

            from algorith_server.AlgorithServer_v2 import SenderThread
            sender = SenderThread(context=[])
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
                msg_result = json.loads(result)
                face_features = msg_result['face_features']
            except:
                face_features = ""
            #把人脸特征存到本地
            feature_dir = FACE_IDENT_URL + imgid + '/'
            feature_url = feature_dir + imgid + ".json"
            if os.path.exists(feature_url):
                continue
            if not os.path.exists(feature_dir):
                os.makedirs(feature_dir)
            host_ip = get_ip()
            port = glv.get_value('nginx_port',8088)
            img_pathhead = 'http://%s:%s/net-web/face_images/'%(host_ip,port)
            feature_pathhead = 'http://%s:%s/net-web/face_features/'%(host_ip,port)
            face_url = img_pathhead   +imgid + ".jpg"
            image_check_url = feature_pathhead + imgid + ".json"
            if not face_features or  face_features == "":
                image_operation_statue = 100
                image_check_url = None
            else:
                with open(feature_url,"a") as outfile:
                    outfile.write(face_features)
                image_operation_statue = 0
            image_item = {'image_operation_statue':image_operation_statue,
                          'image_url':face_url,
                          'image_check_url':image_check_url}
            my_db.update(WORK_FLOW_PERSONNEL_IMAGE,{"image_id":imgid},{"$set":image_item})

def insert_sound_server(my_db:ToMongo,soundServiceEntity):
    if not soundServiceEntity:
        return
    serviceType = soundServiceEntity.get('serviceType')
    item = dict()
    if serviceType == 1:  
        my_db.delete("odin_device_itc_server",{},is_one=False)
        item['itc_server_id'] = soundServiceEntity.get('serviceId')
        item['itc_server_address'] = soundServiceEntity.get('serviceAddress')
        item['itc_server_port'] = soundServiceEntity.get('servicePort')
        item['itc_server_account'] = soundServiceEntity.get('account')
        item['itc_server_password'] = soundServiceEntity.get('pwd')
        my_db.insert("odin_device_itc_server",item)
    elif serviceType == 2:
        my_db.delete("odin_device_lings_server",{},is_one=False) 
        item['lings_server_id'] = soundServiceEntity.get('serviceId')
        item['lings_server_address'] = soundServiceEntity.get('serviceAddress')
        item['lings_server_port'] = soundServiceEntity.get('servicePort')
        item['lings_tts_port'] = 10008
        item['lings_server_account'] = soundServiceEntity.get('account')
        item['lings_server_password'] = soundServiceEntity.get('pwd')
        my_db.insert("odin_device_lings_server",item)
    return

def insert_sound_device(my_db:ToMongo,deviceSoundEntitieList):
    if not deviceSoundEntitieList:
        return
    for entity in deviceSoundEntitieList:
        entity['equipName'] = entity['equName']
        entity['equipIp'] =   entity['equIp']
        entity['equipPort'] = entity['equPort']
    #    entity['']
        del entity['equName'],entity['equIp'],entity['equPort']
        soundEquip = database_to_dict(entity,equip_web,equip_database)
        my_db.insert("odin_device_equip",soundEquip)
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
    my_db.delete('odin_device_equip',{},is_one=False)
    my_db.delete('odin_device_sound',{},is_one=False)
    try:
        serviceAddress = soundServiceEntity.get('serviceAddress')
        servicePort = soundServiceEntity.get('servicePort')
        serviceType = soundServiceEntity.get('serviceType')
        serverUrl = "http://%s:%s"%(serviceAddress,servicePort)
        if serviceType == 2:
            #菱声音响
            Linginstance = LingsSound(client_url=None,server_url=serverUrl,sound_no=None,volume=100)
            for entity in soundNos:
                sound_no = entity.get('mac')
                mission_id = entity.get('missionId')
                detailInfo = Linginstance.getDeviceBySN(sound_no=sound_no)
                mainlogger.info("Linginstance.getDeviceBySN detailInfo:%s"%detailInfo)
                extra = detailInfo.get('extra')
                config = extra.get('config')
                status = str(detailInfo.get('status'))
                name = detailInfo.get('name')
                soundId = uuid.uuid4().hex
                soundIp = config.get('ip')
                item_equip = {'missionId':mission_id,'equipId':soundId,'equipType':3,'equipIp':soundIp,'equipName':name}
                item_equip = database_to_dict(item_equip,equip_web,equip_database)
                my_db.insert('odin_device_equip',item_equip)
                item_sound = {'soundId':soundId,
                            'soundType':'2',#菱声
                            'soundName':name,
                            'soundNo':sound_no,
                            'soundIp':soundIp,
                            'soundStatus':status,
                            'soundPort':8888
                            }
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
                mainlogger.info("获取itc终端失败,response:%s"%resp)
                return
            data = resp.get('data')
            EndPointsArray = data.get('EndPointsArray')
            if not EndPointsArray:
                mainlogger.info("未查询到itc终端,response:%s"%resp)
                return
            for entity in soundNos:
                sound_no = entity.get('mac')
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
                item_equip = {'missionId':mission_id,'equipId':soundId,'equipType':2,'equipIp':soundIp,'equipName':name}
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
        mainlogger.info("insert_sound_info Error:%s"%traceback.format_exc())
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
        mainlogger.info("insert_sound_entity error:%s"%e)


def insert_constant_info(my_db:ToMongo,algorithmConstantEntityList):
    '''
    接口说明：同步平台的算法基础设置
    '''
    if not algorithmConstantEntityList:
        return
    try:
        for item in algorithmConstantEntityList:
            item = database_to_dict2(item,constant_web,constant_database)
            query = {'algorithm_service_num':item.get('algorithm_service_num')}
            my_db.update(WORK_FLOW_ALGORITHM_CONSTANT,query,{'$set':item})
    except Exception as e:
        mainlogger.info("同步algorithmConstantEntityList error:%s"%e)
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
    
    my_db.delete(WORK_FLOW_INSIGHT_MODEL_ALGORITHM_INSTANCE,{},is_one=False)
    if  algorithmInstances:
        for item in algorithmInstances:
            try:
                instance_item = database_to_dict(item,instance_web,instance_database)     
                if  instance_item['create_time']:
                    instance_item['create_time'] = datetime.fromtimestamp(instance_item['create_time']/1000)
                my_db.insert(WORK_FLOW_INSIGHT_MODEL_ALGORITHM_INSTANCE,instance_item)
            except Exception as e:
                print('Insert Error--algorithmInstances:',e)
                continue

    
    my_db.delete("odin_business_control_manage",{},is_one=False)
    if  controlTaskEntityList:
        for item in controlTaskEntityList:
            try:
                control_item = database_to_dict(item,business_control_web,business_control_database)
                if control_item['create_time']:
                    control_item['create_time'] = datetime.fromtimestamp(control_item['create_time']/1000)
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
    if  workFlowMissionVos:
        for item in workFlowMissionVos:
            try:
                missions_item = database_to_dict(item,mission_web,mission_database)
                if missions_item['create_time']:
                    missions_item['create_time'] = datetime.fromtimestamp(missions_item['create_time']/1000)
                my_db.insert(WORK_FLOW_MISSION,missions_item)
            except Exception as e:
                print('Insert Error-------workFlowMissionVos:',e)
                continue

    if ipAddress:
        #更新minio地址
        update_minio_address(my_db,ipAddress)

    if algorithmConstantEntityList:
        #更新算法基础设置
        insert_constant_info(my_db,algorithmConstantEntityList)

    if soundServiceEntity:
        #插入音响服务器数据
        insert_sound_server(my_db,soundServiceEntity)

    if soundNos:
        #插入音响设备数据
        insert_sound_info(my_db,soundNos,soundServiceEntity)

    if soundEntities:
        #内网版插入音响
        insert_sound_entity(my_db,soundEntities,soundServiceEntity)

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

    format_pattern = '%Y-%m-%d %H:%M:%S.%f'
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
                if info['createTime']:
                    asso_item['create_time'] = datetime.fromtimestamp(info['createTime']/1000)
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
                if position_item['create_time']:
                    position_item['create_time'] = datetime.fromtimestamp(position_item['create_time']/1000)
                if position_item['update_time']:
                    position_item['update_time'] = datetime.fromtimestamp(position_item['update_time']/1000)
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
                if roi_item['create_time']:
                    roi_item['create_time'] = datetime.fromtimestamp(roi_item['create_time']/1000)
                my_db.insert("odin_device_roi_area_record",roi_item)
            except Exception as e:
                print('Insert Error---:areaRecordEntityList',e)
                continue

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
                if position_item['create_time']:
                    position_item['create_time'] = datetime.fromtimestamp(position_item['create_time']/1000)
                if position_item['update_time']:
                    position_item['update_time'] = datetime.fromtimestamp(position_item['update_time']/1000)
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
            my_db.insert("system_data_version",item)
        except Exception as e:
            print('Insert Error---versionList:',e)
            continue

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

def insert_roi_info(my_db:ToMongo,cameraId,algorithmConstantId,roiId,roiItem):
    #转化AI精灵传过来的数据，插入roi信息
    if not roiItem or not cameraId or not roiItem:
        return
    create_time = datetime.now()
    roi_area_record_id = uuid.uuid4().hex
    res_item = {
                "camera_id":cameraId,
                "roi_area_info":roiItem,
                "roi_name":"roi_%s"%roiId,
                "algorithm_constant_id":algorithmConstantId,
                "roi_id":roiId,
                "create_time":create_time,
                "roi_area_record_id":roi_area_record_id,
                "organization_id":None
                }    
    my_db.insert("odin_device_roi_area_record",res_item)
    return

def insert_all_info(my_db:ToMongo,data):
    #插入AI精灵数据
    if not data:
        return
    
    mainlogger.info("insert_all_info /data:%s"%data)
    
    format_pattern = '%Y-%m-%d %H:%M:%S.%f'

    try:

        my_db.delete("odin_device_camera_edit",{},is_one=False)
        my_db.delete("odin_device_roi_area_record",{},is_one=False)

        my_db.delete(WORK_FLOW_MISSION_DEVICE_ASSOCIATE,{},is_one=False)
        my_db.delete("odin_business_control_manage",{},is_one=False)
        my_db.delete(WORK_FLOW_MISSION,{},is_one=False)
        my_db.delete(WORK_FLOW_INSIGHT_MODEL_ALGORITHM_INSTANCE,{},is_one=False)
        
        constant_col = my_db.get_col(WORK_FLOW_ALGORITHM_CONSTANT)

        n1 = len(data)
        for j in range(n1):
            item = data[j]
            cameraId = item.get("cameraId")
            mainUrl = item.get("mainUrl")
            if not mainUrl:
                cameraNum = item.get("cameraNum")
                mainlogger.info("Error :摄像头的ISC地址为空,cameraId:%s,cameraNum:%s"%(cameraId,cameraNum))
                continue
            camera_data = database_to_dict(item,camerakeys_server,camerakeys_database)
            camera_data['camera_status'] = str(camera_data['camera_status'])
            if camera_data['create_time']:
                camera_data['create_time'] = datetime.strptime(camera_data['create_time'],format_pattern)
            if camera_data['update_time']:
                camera_data['update_time'] = datetime.strptime(camera_data['update_time'],format_pattern)
            my_db.insert("odin_device_camera_edit",camera_data)

            algorithmInstanceList = item.get("algorithmInstanceList")
            if not algorithmInstanceList:
                continue

            #插入任务信息
            controlId = uuid.uuid4().hex
            control_info = {"controlId":controlId,"controlName":"control_%s"%(j),"storageNum":10000,"storageTime":12}
            control_item = database_to_dict(control_info,control_web,control_database)
            my_db.insert("odin_business_control_manage",control_item)

            #插入任务设备关联表
            asso_item = {'device_id':cameraId,'mission_id':controlId,"product_key":None}
            my_db.insert(WORK_FLOW_MISSION_DEVICE_ASSOCIATE,asso_item)
            
            alg_list = list()
            num = len(algorithmInstanceList)
            for i in range(num):
                algorithmInstance = algorithmInstanceList[i]
                algorithmConstantNum = algorithmInstance.get("algorithmConstantNum")
                alg_list.append(algorithmConstantNum)
                roiAreaJson = algorithmInstance.get("roiAreaJson")
                query = {"algorithm_constant_num":algorithmConstantNum}
                constant_item = constant_col.find_one(query)
                if roiAreaJson and roiAreaJson != "[]":
                    #插入roi信息
                    insert_roi_info(my_db,cameraId,algorithmConstantNum,roiId=i+1,roiItem=roiAreaJson)

                #插入instance信息
                instance_item = database_to_dict(algorithmInstance,instance_web,instance_database)
                instance_item['algorithm_service_num'] = algorithmConstantNum
                instance_item['mission_id'] = controlId
                instance_item['is_use'] = 1
                instance_item['last_time'] = algorithmInstance.get("timeParamJson")
                my_db.insert(WORK_FLOW_INSIGHT_MODEL_ALGORITHM_INSTANCE,instance_item)


            #插入mission信息
            algorithm_id = ",".join(alg_list)
            data_mission = {"missionId":controlId,"algorithmId":algorithm_id,"missionStatus":0}
            item_mission = database_to_dict(data_mission,mission_web,mission_database)
            my_db.insert(WORK_FLOW_MISSION,item_mission)

    except Exception as e:
        mainlogger.info("insert_all_info Error:%s"%e)
    
import subprocess
from threading import Thread
import time
import json
import shutil
import os
from Utils.db import ToMongo
import Utils.glv as glv
from datetime import datetime, timedelta
from Utils.datacfg import *
import Utils.logger as logger
from config import PERSON_IMG_URL, FACE_IDENT_URL, EMERGENCY_IMG_PATH, DISK_PATH,BASE_INFO
import Utils.edgebox_repo  # noqa: F401
from edgebox_db.mongo_collections import (
    CONTROL_DEVICE_ALGORITHM_ASSOCIATE,
    CONTROL_MANAGE_MISSION,
    WORK_FLOW_ALGORITHM_CONSTANT,
)
from edgebox_db.mission_queries import control_mission_collection
from algorith_server.Alibabasms import SendSmsResqueset

mainlogger = logger.getLogger("main")


def execShell(cmd):
    err, result = subprocess.getstatusoutput(cmd)
    return err, result


def getPid(command, Toflag):
    try:
        cmd = "ps -ef|grep -v grep|grep " + command + "|grep " + Toflag
        error, resp = execShell(cmd)
        if not resp:
            return None
        else:
            pid = resp.split()[1]
        return pid
    except Exception as e:
        print('error : %s' % e)
        return


def closeLinuxProcess(pid):
    try:
        cmd = "kill -9 " + pid
        err, result = execShell(cmd)
    except Exception as e:
        print('kill process error : %s' % e)
    return


def database_to_dict2(item, old: list, new: list):
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


def database_to_dict3(item, old: list, new: list):
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


def database_to_dict(item, old: list, new: list):
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
        err, result = execShell(temperature_cmd)
        chip_temp = int(result) / 1000
    except Exception as e:
        chip_temp = None
    return chip_temp


def get_cpu_and_memery():
    try:
        cpu_cmd = "top -bn 1|grep %Cpu"  # 不加-b使用nohup会出错
        memory_cmd = "free -m|grep Mem"
        err, res_cpu = execShell(cpu_cmd)
        err, res_mem = execShell(memory_cmd)
        cpu_percent = int(float(res_cpu.split()[1]))
        mem_list = res_mem.split()
        total, used = float(mem_list[1]), float(mem_list[2])
        mem_percent = int(100 * used / total)
        num_1G = 1024
        total_G = round(total / num_1G, 1)
        used_G = round(used / num_1G, 1)
    except Exception as e:
        cpu_percent, mem_percent, total_G, used_G = None, None, None, None
    return cpu_percent, mem_percent, total_G, used_G


def get_npu_and_npumem():
    '''
    return 返回tpu占用率和tpu内存占用率
    type float
    '''
    try:
        cmd_npu = "cat /sys/class/bm-tpu/bm-tpu0/device/npu_usage"
        cmd_npu_memery = "cat /sys/kernel/debug/ion/bm_npu_heap_dump/summary |head -2"
        err, npu_result = execShell(cmd_npu)
        err, npu_memery_result = execShell(cmd_npu_memery)
        npu_memery_percent = str(npu_memery_result.split()[8].split(':')[1][:-1])
    except Exception as e:
        npu_result, npu_memery_percent = None, None
    return npu_result, npu_memery_percent


def get_disk():
    '''
    return 返回磁盘占用率
    type float
    '''
    try:
        disk_cmd = "df -h|grep " + DISK_PATH
        err, disk_result = execShell(disk_cmd)
        if disk_result:
            disk_percent = int(disk_result.split()[-2].split('%')[0])
            # disk_left = float(disk_result.split()[-3][:-1])
            disk_left = disk_result.split()[-3]
        else:
            disk_percent, disk_left = None, None
    except Exception as e:
        disk_percent, disk_left = None, None
    return disk_percent, disk_left


def get_fanrate():
    '''
    return 返回风扇转速
    '''
    try:
        fan_cmd = "cat /sys/class/bm_fan_speed/bm_fan_speed-0/fan_speed|awk -F : '{ print $2 }'"
        err, fan_result = execShell(fan_cmd)
        fan_rate = int(fan_result) * 30 / 1000
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
    def __init__(self, organization_id, log_set, my_db):

        self.log_clean_thread = Thread(target=self.clean_logs, args=[organization_id, log_set, my_db])
        self.log_clean_thread.start()

    def clean_logs(self, organization_id, log_set, my_db):
        numlist = log_set.split('-')
        num_uplimit = int(float(numlist[0]) * 10000)
        num_delete = int(float(numlist[1]) * 10000)
        while True:
            log_cursor = my_db.get_col("user_logs").find({'organization_id': organization_id})
            totalcount = log_cursor.count()
            time.sleep(10)
            if totalcount >= num_uplimit:
                thresh = totalcount - num_delete - 1
                thresh_time = log_cursor.sort("create_time", -1)[thresh]['create_time']
                my_db.delete('user_logs',
                             {'organization_id': organization_id, 'create_time': {'$gte': thresh_time}},
                             is_one=False)


class Cleandisk():
    def __init__(self):
        self.phone_list = []
        self.email_list = []
        self.smsClient = SendSmsResqueset()
        self.my_db = ToMongo('wavedevice')
        self.send_time = None
        self.get_config()
        self.check_thread = Thread(target=self.check_func, args=[])
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
            useage, disk_left = get_disk()
            if useage:
                if useage >= 70:
                    now = datetime.now()
                    now_str = now.strftime("%Y-%m-%d %H:%M:%S")
                    if self.send_time:
                        last_send_time = self.send_time
                        interval = now - last_send_time
                        if interval < timedelta(days=0.5):
                            continue
                    self.send_time = now
                    device_item = self.my_db.get_col('authority_base_info').find_one()
                    device_name = device_item['equipment_name']
                    msg = {"alarm_time": now_str, "device_name": device_name, 'free_space': disk_left}
                    self.send_sms(msg)
                    self.send_email(msg)
                if useage >= 80:
                    print("磁盘占用超过80%，清理前1000条告警数据！")
                    self.clear_disk()
            time.sleep(300)

    def clear_disk(self):
        emergency_col = self.my_db.get_col('odin_business_emergency_record')
        emergency_detail_col = self.my_db.get_col('odin_business_emergency_record_detail_info')
        items = emergency_col.find().sort('emergency_time', 1)
        if items.count() <= 1000:
            return
        end_time = items[999]['emergency_time']
        items_1000 = items[:1000]

        # 删除告警图片
        for item in items_1000:
            temp = item['emergency_time'].split(" ")[0].split('-')
            filedir = ''.join(temp)
            sub_source_id = item['sub_source_id']
            filepath = EMERGENCY_IMG_PATH + filedir + '/' + sub_source_id + '.jpg'
            if os.path.exists(filepath):
                os.remove(filepath)

        # 删除告警记录表的相关内容
        query = {'emergency_time': {"$lte": end_time}}
        self.my_db.delete('odin_business_emergency_record', query, is_one=False)
        query_detail = {'discern_time': {"$lte": end_time}}
        self.my_db.delete('odin_business_emergency_record_detail_info', query_detail, is_one=False)

    def send_sms(self, msg):
        phone_list = self.phone_list
        if phone_list:
            self.smsClient.send_sms_disk(msg, phone_list)

    def send_email(self, msg):
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
        content = '"[威富视界]AI算法盒存储空间告警!告警内容：存储空间剩余%s,已低于30%%,低于20%%时将自动删除最早的告警纪录,AI算法盒名称:%s,告警时间：%s。"' % (
            msg['free_space'], msg['device_name'], msg['alarm_time'])
        cmd_mail_part = 'echo ' + content + '|/data/ebox/mail/mailx -s ' + subject + ' -S smtp=' + mail_smtp_address + ' -S from=' + mail_send_name + ' -S smtp-auth-user=' + mail_account + ' -S smtp-auth-password=' + mail_password + ' -S smtp-auth="login" '

        for toMail in email_list:
            cmd_mail = cmd_mail_part + toMail
            err, result = execShell(cmd_mail)

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
        return base_config
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
        return item

def get_camera_sysninfo(my_db: ToMongo):
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
    res = camera_col.find({}, {'_id': 0})
    for data in res:
        item = database_to_dict(data, camerakeys_database, camerakeys_server)
        item['cameraCreateTime'] = item['cameraCreateTime'].strftime(format_pattern) if item[
            'cameraCreateTime'] else None
        item['cameraUpdateTime'] = item['cameraUpdateTime'].strftime(format_pattern) if item[
            'cameraUpdateTime'] else None
        cameraSyncRepVO['cameraEditEntityList'].append(item)

    asso_items = associate_coll.find({}, {'_id': 0})
    for asso_item in asso_items:
        info = {}
        position_id = info['positionId'] = asso_item['position_id']
        info['createTime'] = int(asso_item['create_time'].timestamp()) * 1000 if asso_item['create_time'] else None
        info['deviceType'] = asso_item['device_type']
        info['deviceId'] = asso_item['device_id']
        cameraSyncRepVO['cameraPositionAssociateEntityList'].append(info)

        position_item = position_coll.find_one({'position_id': position_id}, {"_id": 0})
        position_info = {}
        if position_item:
            position_info = database_to_dict(position_item, positionkeys_database, positionkeys_web)
            position_info['createTime'] = int(position_info['createTime'].timestamp()) * 1000 if position_info[
                'createTime'] else None
            position_info['updateTime'] = int(position_info['updateTime'].timestamp()) * 1000 if position_info[
                'updateTime'] else None
            cameraSyncRepVO['devicePositionList'].append(position_info)

    # 导出摄像头的roi信息
    roi_items = roi_coll.find({}, {'_id': 0})
    for roi_item in roi_items:
        item = database_to_dict(roi_item, roi_database, roi_server)
        item['createTime'] = int(item['createTime'].timestamp()) * 1000 if item['createTime'] else None
        cameraSyncRepVO['areaRecordEntityList'].append(item)

    return cameraSyncRepVO

def get_control_info(my_db:ToMongo):
    """
    导出配置管理中的布控信息
    """
    mission_col = control_mission_collection(my_db)
    device_asso_col = my_db.get_col(CONTROL_DEVICE_ALGORITHM_ASSOCIATE)

    controlManageEntity = {}
    controlManageEntity['workFlowMissionVos'] = []
    controlManageEntity['deviceAssociateList'] = []

    mission_items = mission_col.find({}, {'_id': 0})
    for item in mission_items:
        newItem = database_to_dict(item,mission_database,mission_web)
        newItem['createTime'] = int(newItem['createTime'].timestamp()) * 1000 if newItem['createTime'] else None
        newItem['updateTime'] = int(newItem['updateTime'].timestamp()) * 1000 if newItem['updateTime'] else None
        controlManageEntity['workFlowMissionVos'].append(newItem)

    asso_items = device_asso_col.find({}, {'_id': 0})
    for item in asso_items:
        newItem = database_to_dict(item,mission_asso_database,mission_asso_web)
        controlManageEntity['deviceAssociateList'].append(newItem)

    gas_col = my_db.get_col("odin_dynamic_gas")
    leakage_col = my_db.get_col("odin_dynamic_leakage")
    gnd_col = my_db.get_col("odin_dynamic_static_electricity")
    audio_col = my_db.get_col("odin_dynamic_audio")
    asso_col = my_db.get_col("odin_dynamic_associate")

    controlManageEntity['gasDeviceList'] = []
    gas_items = gas_col.find({}, {'_id': 0})
    for item in gas_items:
        newItem = database_to_dict(item,gas_db,gas_web)
        newItem["highDensityAlarm"] = json.dumps(newItem["highDensityAlarm"])
        newItem['createTime'] = dt2str(newItem['createTime'])
        newItem['offlineTime'] = dt2str(newItem['offlineTime'])
        controlManageEntity['gasDeviceList'].append(newItem)

    controlManageEntity['leakageDeviceList'] = []
    leak_items = leakage_col.find({}, {'_id': 0})
    for item in leak_items:
        newItem = database_to_dict(item,leakage_db,leakage_web)
        newItem["volt"] = json.dumps(newItem["volt"])
        newItem["current"] = json.dumps(newItem["current"])
        newItem["highVoltAlarm"] = json.dumps(newItem["highVoltAlarm"])
        newItem["highCurAlarm"] =  json.dumps(newItem["highCurAlarm"])
        newItem["lowVoltAlarm"] =  json.dumps(newItem["lowVoltAlarm"]) 
        newItem["leakageAlarm"] =  json.dumps(newItem["leakageAlarm"])
        newItem['createTime'] = dt2str(newItem['createTime'])
        newItem['offlineTime'] = dt2str(newItem['offlineTime'])
        controlManageEntity['leakageDeviceList'].append(newItem)

    controlManageEntity['gndDeviceList'] = []
    gnd_items = gnd_col.find({}, {'_id': 0})
    for item in gnd_items:
        newItem = database_to_dict(item,eleground_db,eleground_web)
        newItem['createTime'] = dt2str(newItem['createTime'])
        newItem['offlineTime'] = dt2str(newItem['offlineTime'])
        controlManageEntity['gndDeviceList'].append(newItem)

    controlManageEntity['audioDeviceList'] = []
    audio_items = audio_col.find({}, {'_id': 0})
    for item in audio_items:
        newItem = database_to_dict(item,audio_db,audio_web)
        newItem['createTime'] = dt2str(newItem['createTime'])
        newItem['offlineTime'] = dt2str(newItem['offlineTime'])
        controlManageEntity['audioDeviceList'].append(newItem)

    controlManageEntity['dynamicAssoList'] = []
    items = asso_col.find({}, {'_id': 0})
    for item in items:
        newItem = database_to_dict(item,dynamic_asso_db,dynamic_asso_web)
        controlManageEntity['dynamicAssoList'].append(newItem)

    return controlManageEntity

def get_person_info(my_db: ToMongo):
    '''
    导出配置管理中的人脸库信息
    '''
    personnel_col = my_db.get_col("work_flow_personnel")
    personnel_image_coll = my_db.get_col('work_flow_personnel_image')
    personnelgroup_asso_coll = my_db.get_col('work_flow_personnel_personnelgroup_associate')
    personnelgroup_coll = my_db.get_col('work_flow_personnelgroup')

    personEntity = {}
    personEntity['groupAssociateList'] = []
    personEntity['imageList'] = []
    personEntity['workFlowPersonnelGroupVoList'] = []
    personEntity['workFlowPersonnelVoList'] = []

    personel_group_asso_items = personnelgroup_asso_coll.find({}, {'_id': 0})
    for personel_group_asso_item in personel_group_asso_items:
        item = {}
        item['personnelGroupId'] = personel_group_asso_item['personnel_group_id']
        item['personnelId'] = personel_group_asso_item['personnel_id']
        personEntity['groupAssociateList'].append(item)

    personnel_image_items = personnel_image_coll.find({}, {'_id': 0})
    for personnel_image_item in personnel_image_items:
        item = database_to_dict(personnel_image_item, personnel_image_database, personnel_image_web)
        item['createTime'] = int(item['createTime'].timestamp()) * 1000 if item['createTime'] else None
        personEntity['imageList'].append(item)

    personnelgroup_items = personnelgroup_coll.find({}, {'_id': 0})
    for personnelgroup_item in personnelgroup_items:
        item = database_to_dict(personnelgroup_item, personnel_group_database, personnel_group_web)
        item['createTime'] = int(item['createTime'].timestamp()) * 1000 if item['createTime'] else None
        personEntity['workFlowPersonnelGroupVoList'].append(item)

    personnel_items = personnel_col.find({}, {'_id': 0})
    for personnel_item in personnel_items:
        item = database_to_dict(personnel_item, personnel_database, personnel_web)
        item['createTime'] = int(item['createTime'].timestamp()) * 1000 if item['createTime'] else None
        personEntity['workFlowPersonnelVoList'].append(item)
    return personEntity


def get_workmodel_info(my_db: ToMongo):
    '''
    导出配置管理中的工作模式信息
    '''
    workmodel_col = my_db.get_col("authority_work_model")

    workModelEntity = {}

    workmodel_item = workmodel_col.find_one({}, {'_id': 0})

    if workmodel_item:
        workModelEntity['account'] = workmodel_item['service_account']
        workModelEntity['ipAddress'] = workmodel_item['service_address']
        workModelEntity['ipPort'] = workmodel_item['service_port']
        workModelEntity['model'] = workmodel_item['model']
        workModelEntity['organizationId'] = workmodel_item['organization_id']

    return workModelEntity


def get_sms_info(my_db: ToMongo):
    '''
    导出短信投递信息
    '''
    smstask_col = my_db.get_col("odin_advise_sms_delivery")

    smsDeliveryEntity = []

    format_pattern = '%Y-%m-%d %H:%M:%S.%f'
    smstask_items = smstask_col.find({}, {'_id': 0})
    for smstask_item in smstask_items:
        item = database_to_dict(smstask_item, smsdelivery_database, smsdelivery_web)
        item['createTime'] = item['createTime'].strftime(format_pattern) if item['createTime'] else None
        item['updateTime'] = item['updateTime'].strftime(format_pattern) if item['updateTime'] else None
        smsDeliveryEntity.append(item)

    return smsDeliveryEntity


def get_webhook_info(my_db: ToMongo):
    '''
    导出告警转发任务
    '''
    webhooktask_col = my_db.get_col("odin_advise_webhook_delivery")

    webhookDeliveryEntity = []

    format_pattern = '%Y-%m-%d %H:%M:%S.%f'
    webhook_items = webhooktask_col.find({}, {'_id': 0})
    for webhook_item in webhook_items:
        item = database_to_dict(webhook_item, webhook_database, webhook_web)
        item['createTime'] = item['createTime'].strftime(format_pattern) if item['createTime'] else None
        item['updateTime'] = item['updateTime'].strftime(format_pattern) if item['updateTime'] else None
        webhookDeliveryEntity.append(item)

    return webhookDeliveryEntity


def insert_workmodel_info(my_db: ToMongo, workModelEntity):
    '''
    接口说明：配置导入时更新工作模式信息
    '''
    if not workModelEntity:
        return
    serviceOrganizationId = workModelEntity.get("serviceOrganizationId", None)
    ipAddress = workModelEntity.get("ipAddress", None)
    account = workModelEntity.get("account", None)
    ipPort = workModelEntity.get("ipPort", None)
    model = workModelEntity.get("model", None)
    organizationId = workModelEntity.get("organizationId", None)

    item = {'service_address': ipAddress,
            'service_account': account,
            'service_organization_id': serviceOrganizationId,
            'service_port': ipPort,
            'last_modify_time': datetime.now(),
            'model': model,
            'create_time': datetime.now(),
            'organization_id': organizationId}
    my_db.delete("authority_work_model", {}, is_one=False)

    my_db.insert("authority_work_model", item)


def delete_person_info(my_db, imageList):
    imageid_list = []
    if imageList:
        for image in imageList:
            imageid_list.append(image['imageId'])
    query = {'image_id': {'$nin': imageid_list}}
    image_coll = my_db.get_col('work_flow_personnel_image')
    items = image_coll.find(query)
    for item in items:
        imageid = item['image_id']
        imgpath = PERSON_IMG_URL + imageid
        if os.path.exists(imgpath):
            shutil.rmtree(imgpath)
        identpath = FACE_IDENT_URL + imageid
        if os.path.exists(imgpath):
            shutil.rmtree(identpath)
    my_db.delete('work_flow_personnel_image', query, is_one=False)
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

def dt2str(timeParam:datetime):
    if not timeParam:
        return timeParam
    format_pattern = '%Y-%m-%d %H:%M:%S'
    return timeParam.strftime(format_pattern)
    
def insert_alg_info(my_db: ToMongo, algorithmConstantEntityList):
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
        query = {'algorithm_service_num': algorithmServiceNum}
        item = database_to_dict3(entity, constant_web, constant_database)
        my_db.update(WORK_FLOW_ALGORITHM_CONSTANT, query, {'$set': item})
    return


def insert_sound_server(my_db: ToMongo, soundServiceEntity):
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
            my_db.insert("odin_device_itc_server", item)
        else:
            my_db.update("odin_device_itc_server", {}, {"$set": item})
    elif serviceType == 2:
        server_item = my_db.get_col("odin_device_lings_server").find_one()
        item['lings_server_id'] = soundServiceEntity.get('serviceId')
        item['lings_server_address'] = soundServiceEntity.get('serviceAddress')
        item['lings_server_port'] = soundServiceEntity.get('servicePort')
        item['lings_tts_port'] = 10008
        item['lings_server_account'] = soundServiceEntity.get('account')
        item['lings_server_password'] = soundServiceEntity.get('pwd')
        if not server_item:
            my_db.insert("odin_device_lings_server", item)
        else:
            my_db.update("odin_device_lings_server", {}, {"$set": item})
    return


def insert_sound_device(my_db: ToMongo, deviceSoundEntitieList):
    if not deviceSoundEntitieList:
        return
    for entity in deviceSoundEntitieList:
        entity['equipName'] = entity['equName']
        entity['equipIp'] = entity['equIp']
        entity['equipPort'] = entity['equPort']
        #    entity['']
        del entity['equName'], entity['equIp'], entity['equPort']
        soundEquip = database_to_dict(entity, equip_web, equip_database)
        my_db.insert("odin_device_equip", soundEquip)
    return


def filter_sound_info(terminalList, mac):
    for item in terminalList:
        EndpointMac = item.get('EndpointMac')
        if EndpointMac == mac:
            return item
    return


def insert_constant_info(my_db: ToMongo, algorithmConstantEntityList):
    '''
    接口说明：同步平台的算法基础设置
    '''
    if not algorithmConstantEntityList:
        return
    try:
        for item in algorithmConstantEntityList:
            item = database_to_dict2(item, constant_web, constant_database)
            query = {'algorithm_service_num': item.get('algorithm_service_num')}
            my_db.update(WORK_FLOW_ALGORITHM_CONSTANT, query, {'$set': item})
    except Exception as e:
        mainlogger.info("同步algorithmConstantEntityList error:%s" % e)
    return

def insert_control_info(my_db:ToMongo,controlManageEntity):
    '''
    接口说明：配置导入时更新布控任务信息
    '''
    workFlowMissionVos = controlManageEntity.get("workFlowMissionVos",None)
    deviceAssociateList = controlManageEntity.get("deviceAssociateList",None)

    gasDeviceList = controlManageEntity.get("gasDeviceList",None)
    gndDeviceList = controlManageEntity.get("gndDeviceList",None)
    leakageDeviceList = controlManageEntity.get("leakageDeviceList",None)
    audioDeviceList = controlManageEntity.get("audioDeviceList",None)
    dynamicAssoList = controlManageEntity.get("dynamicAssoList",None)

    my_db.delete(CONTROL_MANAGE_MISSION,{},is_one=False)
    if  workFlowMissionVos:
        for item in workFlowMissionVos:
            try:
                missions_item = database_to_dict(item,mission_web,mission_database)
                missions_item['create_time'] = trans2date(missions_item['create_time'])
                missions_item['update_time'] = trans2date(missions_item['update_time'])
                my_db.insert(CONTROL_MANAGE_MISSION,missions_item)
            except Exception as e:
                print('Insert Error---' + CONTROL_MANAGE_MISSION + ':',e)
                continue
    
    my_db.delete(CONTROL_DEVICE_ALGORITHM_ASSOCIATE,{},is_one=False)
    if  deviceAssociateList:
        for item in deviceAssociateList:
            try:
                asso_item = database_to_dict(item,mission_asso_web,mission_asso_database)
                my_db.insert(CONTROL_DEVICE_ALGORITHM_ASSOCIATE,asso_item)
            except Exception as e:
                print('Insert Error---' + CONTROL_DEVICE_ALGORITHM_ASSOCIATE + ':',e)
                continue

    my_db.delete("odin_dynamic_gas",{},is_one=False)
    if  gasDeviceList:
        for item in gasDeviceList:
            try:
                gas_item = database_to_dict(item,gas_web,gas_db)
                gas_item['high_density_alarm'] = json.loads(gas_item['high_density_alarm'])
                gas_item['create_time'] = trans2date(gas_item['create_time'])
                gas_item['offline_time'] = trans2date(gas_item['offline_time'])
                my_db.insert("odin_dynamic_gas",gas_item)
            except Exception as e:
                print('Insert Error---odin_dynamic_gas:',e)
                continue

    my_db.delete("odin_dynamic_leakage",{},is_one=False)
    if  leakageDeviceList:
        for item in leakageDeviceList:
            try:
                leak_item = database_to_dict(item,leakage_web,leakage_db)
                leak_item['volt'] = json.loads(leak_item['volt'])
                leak_item['current'] = json.loads(leak_item['current'])
                leak_item['high_volt_alarm'] = json.loads(leak_item['high_volt_alarm'])
                leak_item['high_cur_alarm'] = json.loads(leak_item['high_cur_alarm'])
                leak_item['low_volt_alarm'] = json.loads(leak_item['low_volt_alarm'])
                leak_item['leakage_alarm'] = json.loads(leak_item['leakage_alarm'])
                leak_item['create_time'] = trans2date(leak_item['create_time'])
                leak_item['offline_time'] = trans2date(leak_item['offline_time'])
                my_db.insert("odin_dynamic_leakage",leak_item)
            except Exception as e:
                print('Insert Error---odin_dynamic_leakage:',e)
                continue

    my_db.delete("odin_dynamic_static_electricity",{},is_one=False)
    if  gndDeviceList:
        for item in gndDeviceList:
            try:
                gnd_item = database_to_dict(item,eleground_web,eleground_db)
                gnd_item['create_time'] = trans2date(gnd_item['create_time'])
                gnd_item['offline_time'] = trans2date(gnd_item['offline_time'])
                my_db.insert("odin_dynamic_static_electricity",gnd_item)
            except Exception as e:
                print('Insert Error---odin_dynamic_static_electricity:',e)
                continue

    my_db.delete("odin_dynamic_audio",{},is_one=False)
    if  audioDeviceList:
        for item in audioDeviceList:
            try:
                asso_item = database_to_dict(item,audio_web,audio_db)
                asso_item['create_time'] = trans2date(asso_item['create_time'])
                asso_item['offline_time'] = trans2date(asso_item['offline_time'])
                my_db.insert("odin_dynamic_audio",asso_item)
            except Exception as e:
                print('Insert Error---odin_dynamic_audio:',e)
                continue

    my_db.delete("odin_dynamic_associate",{},is_one=False)
    if  dynamicAssoList:
        for item in dynamicAssoList:
            try:
                asso_item = database_to_dict(item,dynamic_asso_web,dynamic_asso_db)
                my_db.insert("odin_dynamic_associate",asso_item)
            except Exception as e:
                print('Insert Error---odin_dynamic_associate:',e)
                continue

    return

def insert_camera_info(my_db: ToMongo, cameraSyncRepVO):
    '''
    接口说明：配置导入时更新摄像头信息
    '''
    if not cameraSyncRepVO:
        return
    cameraEditEntityList = cameraSyncRepVO.get("cameraEditEntityList", None)
    cameraPositionAssociateEntityList = cameraSyncRepVO.get("cameraPositionAssociateEntityList", None)
    devicePositionList = cameraSyncRepVO.get("devicePositionList", None)
    areaRecordEntityList = cameraSyncRepVO.get("areaRecordEntityList", None)

    format_pattern = '%Y-%m-%d %H:%M:%S.%f'
    camera_url_list = []

    my_db.delete("odin_device_camera_edit", {}, is_one=False)
    if cameraEditEntityList:
        for item in cameraEditEntityList:
            try:
                data = database_to_dict(item, camerakeys_server, camerakeys_database)
                camera_url_list.append(data['main_url'])
                data['camera_status'] = str(data['camera_status'])
                if data['create_time']:
                    data['create_time'] = datetime.strptime(data['create_time'], format_pattern)
                if data['update_time']:
                    data['update_time'] = datetime.strptime(data['update_time'], format_pattern)
                my_db.insert("odin_device_camera_edit", data)
            except Exception as e:
                print('Insert Error---cameraEditEntityList:', e)
                continue

    my_db.delete("odin_device_device_position_associate", {}, is_one=False)
    if cameraPositionAssociateEntityList:
        for info in cameraPositionAssociateEntityList:
            try:
                asso_item = {}
                asso_item['device_id'] = info['deviceId']
                asso_item['position_id'] = info['positionId']
                if info['createTime']:
                    asso_item['create_time'] = datetime.fromtimestamp(info['createTime'] / 1000)
                asso_item['device_type'] = info['deviceType']
                my_db.insert("odin_device_device_position_associate", asso_item)
            except Exception as e:
                print('Insert Error---cameraPositionAssociateEntityList:', e)
                continue

    my_db.delete("odin_device_position", {}, is_one=False)
    if devicePositionList:
        for position_info in devicePositionList:
            try:
                position_item = database_to_dict(position_info, positionkeys_web, positionkeys_database)
                if position_item['create_time']:
                    position_item['create_time'] = datetime.fromtimestamp(position_item['create_time'] / 1000)
                if position_item['update_time']:
                    position_item['update_time'] = datetime.fromtimestamp(position_item['update_time'] / 1000)
                my_db.insert("odin_device_position", position_item)
            except Exception as e:
                print('Insert Error---devicePositionList:', e)
                continue

    # 摄像头ROI信息
    my_db.delete("odin_device_roi_area_record", {}, is_one=False)
    if areaRecordEntityList:
        for roi_info in areaRecordEntityList:
            try:
                roi_item = database_to_dict(roi_info, roi_server, roi_database)
                if roi_item['create_time']:
                    roi_item['create_time'] = datetime.fromtimestamp(roi_item['create_time'] / 1000)
                my_db.insert("odin_device_roi_area_record", roi_item)
            except Exception as e:
                print('Insert Error---:areaRecordEntityList', e)
                continue

    return


def insert_sms_info(my_db: ToMongo, smsDeliveryEntity):
    '''
    接口说明：配置导入时更新短信投递信息
    '''
    if not smsDeliveryEntity:
        return

    format_pattern = '%Y-%m-%d %H:%M:%S.%f'

    my_db.delete("odin_advise_sms_delivery", {}, is_one=False)
    for item in smsDeliveryEntity:
        try:
            data = database_to_dict(item, smsdelivery_web, smsdelivery_database)
            if data['create_time']:
                data['create_time'] = datetime.strptime(data['create_time'], format_pattern)
            if data['update_time']:
                data['update_time'] = datetime.strptime(data['update_time'], format_pattern)
            my_db.insert("odin_advise_sms_delivery", data)
        except Exception as e:
            print('Insert Error---smsDeliveryEntity:', e)
            continue


def insert_webhook_info(my_db: ToMongo, webhookDeliveryEntity):
    '''
    接口说明：配置导入时更新短信投递信息
    '''
    if not webhookDeliveryEntity:
        return

    format_pattern = '%Y-%m-%d %H:%M:%S.%f'

    my_db.delete("odin_advise_webhook_delivery", {}, is_one=False)
    for item in webhookDeliveryEntity:
        try:
            data = database_to_dict(item, webhook_web, webhook_database)
            if data['create_time']:
                data['create_time'] = datetime.strptime(data['create_time'], format_pattern)
            if data['update_time']:
                data['update_time'] = datetime.strptime(data['update_time'], format_pattern)
            my_db.insert("odin_advise_webhook_delivery", data)
        except Exception as e:
            print('Insert Error---webhookDeliveryEntity:', e)
            continue


def insert_position_info(my_db: ToMongo, positionList):
    '''
    从云平台同步位置信息；
    '''

    my_db.delete("odin_device_position", {}, is_one=False)
    if positionList:
        for position_info in positionList:
            try:
                position_item = database_to_dict(position_info, positionkeys_web, positionkeys_database)
                if position_item['create_time']:
                    position_item['create_time'] = datetime.fromtimestamp(position_item['create_time'] / 1000)
                if position_item['update_time']:
                    position_item['update_time'] = datetime.fromtimestamp(position_item['update_time'] / 1000)
                my_db.insert("odin_device_position", position_item)
            except Exception as e:
                print('Insert Error---positionList:', e)
                continue


def insert_version_info(my_db: ToMongo, versionList):
    '''
    从云平台同步版本信息；
    '''
    if not versionList:
        return
    my_db.delete("system_data_version", {}, is_one=False)
    for version_item in versionList:
        try:
            item = database_to_dict(version_item, version_server, version_database)
            if item['modify_time']:
                item['modify_time'] = datetime.fromtimestamp(item['modify_time'] / 1000)
            my_db.insert("system_data_version", item)
        except Exception as e:
            print('Insert Error---versionList:', e)
            continue


def update_minio_address(my_db: ToMongo, minio_addr):
    '''
    更新云平台的minio同步地址
    '''
    if not minio_addr:
        return
    try:
        item = {"service_minio_address": minio_addr}
        my_db.update('authority_work_model', query={}, new={'$set': item})
    except:
        pass
    return

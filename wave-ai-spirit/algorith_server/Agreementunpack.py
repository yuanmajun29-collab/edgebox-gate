
from datetime import datetime,timedelta
import os
import json
import uuid
import base64
import socket
import time
from .Algorithmutil import Identifier_to_constant, get_algorithm_num ,modelnamemap
from Utils.db import ToMongo
from Utils.advise_func import insert_emergency_advise
import paho.mqtt.client as mqtt
import redis
from system.system_route import emergencyPop_queue
from system.system_misc import get_ip,get_nginx_port,get_workmodel_info
from .Alibabasms import SendSmsResqueset
from .RelayEmergency import Sendwebrequest
from emergency.advise_router import smsdelivery_queue,webdelivery_queue
from msg_queue import faceidentification_queue
from system.system_route import smsconfig_queue
from config import BASE_INFO,EMERGENCY_IMG_PATH
from system.sys_config import *
import requests
from threading import Thread
from config import EMERGENCY_IMG_PATH,PLATFORM_MINIO_URL,NetAgreementType
import sys
import Utils.logger as logger
import traceback
import Utils.glv as glv
from Utils.voicedevice_utils import *
from flask import request
import xmltodict
import re

import urllib3
urllib3.disable_warnings()  #禁用 https认证没有证书的 warning

mainlogger = logger.getLogger('main')


host_ip = get_ip()
nginx_port = get_nginx_port()
glv.init()
glv.set_value('nginx_port',nginx_port)
pathhead = 'http://%s:%s/net-web/control/event_images/'%(host_ip,nginx_port)

image_dir = EMERGENCY_IMG_PATH
SYN_EMERGENCY = '/syn/synAddAllEmergency'
SYN_MINIO_DATA = '/syn/syncEmergencyImage'

def write_image(image_id,emergency_dir,image_byte):
    if not os.path.exists(image_dir):
        os.mkdir(image_dir)
    second_dir_path = os.path.join(image_dir,emergency_dir)
    per_image_name = image_id + '.jpg'
    image_path = os.path.join(second_dir_path,per_image_name)   #图片最终路径 = image_dir + 当前日期 + image_id  http://10.0.14.49/SophonFace/api/event_images/001651048287.0372102?datetime=1651048284.9022
    if os.path.exists(image_path):
        return
    if not os.path.exists(second_dir_path):
        os.makedirs(second_dir_path)
        os.chmod(second_dir_path,0o777)   
    with open(image_path,'wb') as fp:
        fp.write(image_byte)
    del image_byte
    return

def write_hot_image(image_id,emergency_dir,hot_jpg):
    if not os.path.exists(image_dir):
        os.mkdir(image_dir)
    second_dir_path = os.path.join(image_dir,emergency_dir)
    per_image_name = image_id + '.jpg'
    image_path = os.path.join(second_dir_path,per_image_name) 
    if os.path.exists(image_path):
        return
    if not os.path.exists(second_dir_path):
        os.makedirs(second_dir_path)
        os.chmod(second_dir_path,0o777)   
    hot_jpg.save(image_path)
    return 

def judge_cache(msg_cache,mongo,mqtt_client,sms,webhook,re_pool):
        while msg_cache:
            cache_head = msg_cache[0:2]
            msg_left = msg_cache[2:]
            if cache_head != b'#!':
                num = msg_cache.find(b'#!')
                if num == -1:
                    msg_cache = b""
                    return msg_cache
                else:
                    msg_cache = msg_cache[num:]

            else:
                num = msg_left.find(b'#!')
                if num == -1:
                    len_msg = len(msg_cache)
                    if len_msg >= 55:
                        len_body = int(msg_cache[8:18])
                        length = 55 + len_body
                        if len_msg >= length:
                            msg_body = msg_cache[55:length]
                            msg_type = msg_cache[18:23]
                            mainlogger.info('--msg_type : %s' % (msg_type,))
                            if msg_type == b"03008":
                                #人脸特征信息存入队列
                                faceidentification_queue.put(msg_body)
                            if msg_type == b"03001":
                                mainlogger.info('----msg_body : %s' % msg_body)
                                mode = handle_3001_msg(msg_body,mongo)
                                from algorith_server.AlgorithServer_v2 import SenderThread
                                sender = SenderThread(context=None)
                                sender.start_controls_message(mode)
                            if msg_type == b"04002":
                                result = handle_msg(msg_body,mongo,mqtt_client,sms,webhook,re_pool)
                            msg_cache = msg_cache[length:]
                        else:
                            return msg_cache
                    else:
                        return msg_cache

                elif num <= 53:
                    msg_cache = msg_cache[num+2:]
                else:
                    len_body = int(msg_cache[8:18])
                    if num >= len_body +53:
                        length = len_body+55
                        msg_body = msg_cache[55:length]
                        msg_type = msg_cache[18:23]
                        mainlogger.info('--msg_type : %s' % (msg_type,))
                        if msg_type == b"03008":
                            #人脸特征信息存入队列
                            faceidentification_queue.put(msg_body)
                        if msg_type == b"03001":
                            mode = handle_3001_msg(msg_body,mongo)
                            from algorith_server.AlgorithServer_v2 import SenderThread
                            sender = SenderThread(context=None)
                            sender.start_controls_message(mode)
                        if msg_type == b"04002":
                            result = handle_msg(msg_body,mongo,mqtt_client,sms,webhook,re_pool)
                        msg_cache = msg_cache[length:]
                    else:
                        msg_cache = msg_cache[num+2:]
        else:
            msg_cache = b""
            return msg_cache

def handle_msg(msg_body,mongo:ToMongo,mqtt_client:mqtt.Client,sms:SendSmsResqueset,webhook:Sendwebrequest,re_pool:redis.Redis):

        my_db = mongo
        msg_body = json.loads(msg_body)

        emergency_time_stamp = msg_body['algorithm_time']
        emergency_datetime = datetime.fromtimestamp(int(emergency_time_stamp/1000))
        accumulated_flag = accumulated_msg(emergency_datetime)
        #防止告警产生堆积，直接删除相差时间超过3分钟的告警
        if accumulated_flag:
            return
        emergency_time = emergency_datetime.strftime("%Y-%m-%d %H:%M:%S")
        emergency_dir = emergency_datetime.strftime("%Y%m%d")

        #查数据库的表
        camera_edit_col =        my_db.get_col("odin_device_camera_edit")
        position_associate_col = my_db.get_col("odin_device_device_position_associate")
        position_col =           my_db.get_col("odin_device_position")
        work_model_col =         my_db.get_col('authority_work_model')
        mission_associate_col =  my_db.get_col('work_flow_mission_device_associate')
        alg_col =                my_db.get_col('work_flow_insight_model_algorithm_instance')
        mission_col =            my_db.get_col('work_flow_mission')
        emergency_col =          my_db.get_col('odin_business_emergency_record')
        emergency_detail_col =   my_db.get_col('odin_business_emergency_record_detail_info')
        alg_constant_col =       my_db.get_col('work_flow_algorithm_constant')
        # equipment_col =          my_db.get_col('odin_device_equip')
        # sound_col =              my_db.get_col('odin_device_sound')

        #查询组织id信息
        organization_id = get_organizationId(work_model_col)

        #查询告警摄像头信息和位置信息
        device_id = msg_body['device_id']
        query_device = {'camera_id':device_id}
        query_position = {'device_id':device_id}
        device_item = camera_edit_col.find_one(query_device)
        if not device_item:
            return
        device_name = device_item['camera_name']
        position_item = position_associate_col.find_one(query_position)
        position_id = position_item['position_id'] if position_item else None
        query_detail = {'position_id':position_id}
        position_info = position_col.find_one(query_detail)
        if position_info:
            emergency_position = position_info['position_city'] + ',' + position_info['position_area'] + ',' + position_info['position_desc']
            emergency_lon_and_lat = position_info['lon_and_lat']
        else:
            emergency_position = ''
            emergency_lon_and_lat = ''

        query = {'device_id':device_id}
        mission_items = mission_associate_col.find(query)
        if mission_items.count() == 0:
            return
        mission_list = list(mission_items)

        alarm_status = "1"  #默认为1
        create_time = datetime.now()


        emergency_image_extra_info={"imageWidth":1920,
                                    "imageHeight":1080,
                                    "width":0,"height":0,"x":0,"y":0,"flag":2,
                                    "top_y":None,"left_x":None,
                                    "points":[],
                                    "recognitionTime":"2023-01-14 08:33:36 386",
                                    "processEndTime":"2023-01-14 08:33:36 386",
                                    "nettyReceiveTime":"2023-01-14 08:33:36 540",
                                    "faceFeature":None,
                                    "instanceColor":"#C90740"}
        emergency_image_extra_info['imageWidth'] = msg_body['img_w']
        emergency_image_extra_info['imageHeight'] = msg_body['img_h']

        emergency_image_extra_info['recognitionTime'] = msg_body['algorithm_time']
        emergency_image_extra_info['processEndTime'] = msg_body['algorithm_time']
        time_d = datetime.fromtimestamp(int(msg_body['send_time'])/1000)
        emergency_image_extra_info['nettyReceiveTime'] = time_d.strftime("%Y-%m-%d %H:%M:%S")

        
        # 协议中的图片字段base64解码拿到告警图片的二进制数据
        image_base64 = msg_body['img_data_jpeg']
        image_byte = base64.b64decode(image_base64)  

        # 生成告警图的路径
        sub_source_id = uuid.uuid4().hex
        emergency_image = pathhead + sub_source_id + '?' + 'date=%s'%emergency_dir

        #整理来自算法的告警，将同类型算法告警放在一起
        result = {}
        target_list = msg_body['target_list']
        for x in target_list:
            for item in x:
                # item['type'] : 算法的识别码
                Identifier = item['type']
                algorithm_constant_num = Identifier_to_constant(str(Identifier))

                temp = emergency_image_extra_info.copy()
                temp['x'] = item['x']
                temp['y'] = item['y'] 
                temp['width'] = item['w']
                temp['height'] = item['h']
                #尾随和离岗的处理方式不同
                if algorithm_constant_num in ["5","114",'128','15']: #尾随、离岗、人流量密度,单人作业
                    roi_list = item['roi_list']
                    if not roi_list:
                        continue
                    for x in roi_list:
                        temp_po = temp.copy()
                        temp_po['points']= points_transform(x['points'])
                        temp_po['left_x'] = x['left_x']
                        temp_po['top_y'] = x['top_y']
                        if Identifier in  result.keys():
                            result[Identifier].append(temp_po)
                        else:
                            result[Identifier] = []
                            result[Identifier].append(temp_po)
                else:                                           
                    if Identifier in  result.keys():
                        result[Identifier].append(temp)
                    else:
                        result[Identifier] = []
                        result[Identifier].append(temp)
        # 不同算法分开处理
        alarm_algs = []
        for identifer in result.keys():         
            algorithm_constant_num = Identifier_to_constant(str(identifer))
            #查布控任务信息
            mission_id_list = find_associate_mission3(device_id,algorithm_constant_num,alg_col,mission_col,mission_associate_col)
            if not mission_id_list :
                continue
            for mission_id in mission_id_list:
                missioncol_item = mission_col.find_one({'mission_id':mission_id})
                #一个任务绑定多个同种算法
                instance_items = alg_col.find({'mission_id':mission_id,'algorithm_constant_num':algorithm_constant_num})
                if not instance_items or not missioncol_item:
                    continue
                for instance_item in instance_items:
                    alg_service_num = instance_item.get('algorithm_service_num',None)
                    constant_item = alg_constant_col.find_one({'algorithm_service_num':alg_service_num})

                    ######注释内容
                    model_path = constant_item['algorithm_constant_name']
                    alarm_algs.append(model_path)

                    if not constant_item:
                        continue

                    emergency_level = instance_item.get("emergency_level")
                    missionWorkTime = missioncol_item['mission_start_time']
                    timeParamJson = instance_item.get("last_time")
                    emergencyIntervalTime = instance_item.get("interval_time")
                    algorithm_color = constant_item['algorithm_color']

                    if emergencyIntervalTime:
                        emergencyIntervalTime = int(emergencyIntervalTime) * 60
                    
                    #过滤不在感知时段的告警事件
                    flag_in_timeperiod = emergency_in_period(timeParamJson,emergency_datetime)   
                    if not flag_in_timeperiod:
                        continue
                    res = filter_emergency(device_id,mission_id,alg_service_num,re_pool,emergencyIntervalTime)
                    if res:
                        #print('不满足%s秒告警间隔:'%str(emergencyIntervalTime))
                        continue

                    control_info = my_db.get_col('odin_business_control_manage').find_one({'control_id':mission_id})
                    if not control_info:
                        continue

                    #将告警图存入磁盘
                    writepic_thread = Thread(target=write_image,args=[sub_source_id,emergency_dir,image_byte])
                    writepic_thread.start()
                    
                    control_name = control_info['control_name']
                    storage_time = control_info['storage_time']
                    storage_num = control_info['storage_num']
                    
                    info_list = result[identifer]
                    num = len(info_list) #图片框选数
                    for extra_info in info_list:
                        extra_info['instanceColor'] = algorithm_color
                        extra_info['shortName'] = model_path

                    emergency_record_id = uuid.uuid4().hex
                    emergency_record_detail_info_id = uuid.uuid4().hex

                    time_alg = msg_body['algorithm_time']
                    time_alg = datetime.fromtimestamp(int(time_alg/1000))
                    discern_time = time_alg.strftime("%Y-%m-%d %H:%M:%S")
                    
                    data1 = {'emergency_record_id':emergency_record_id,
                            'emergency_level':emergency_level,
                            'emergency_position':emergency_position,
                            'emergency_media_info':None,   #媒体视频信息
                            'mission_id':mission_id,
                            'emergency_time':emergency_time,
                            'alarm_status':alarm_status,
                            'emergency_lon_and_lat':emergency_lon_and_lat,
                            'organization_id':organization_id,
                            'create_time':create_time,
                            'model_name': model_path,
                            'model_path': model_path,
                            'emergency_audio':'alarm1',  #默认
                            'position_id':position_id,
                            'control_name':control_name,
                            'tid':None,
                            'trid':None,
                            'device_num':None,
                            'storage_time':storage_time,
                            'storage_num':storage_num,
                            'device_id':device_id,
                            'device_name':device_name,
                            'emergency_exec_name':None,
                            'emergency_exec_desc':None,
                            'emergency_exec_result':None,
                            'emergency_exec_flag':0,
                            'emergency_music_close_method':1,
                            'emergency_music_close_status':1,
                            'sub_source_id':sub_source_id,
                            'is_wrong':0
                            }

                    data2 = {'emergency_record_detail_info_id':emergency_record_detail_info_id,
                            'emergency_record_id':emergency_record_id,
                            'video_preview_image': emergency_image,
                            'discern_time': discern_time,
                            'group_num': None,
                            'group_matter_name': model_path,
                            'emergency_image': emergency_image,
                            'base_personnel_image': None,
                            'base_personnel_name': None,
                            'base_personnel_id': None,
                            'base_personnel_sex': None,
                            'base_personnel_nation': None,
                            'base_personnel_birth': None,
                            'num': num ,
                            'algorithm_constant_num' : algorithm_constant_num,
                            'emergency_image_extra_info' : json.dumps(info_list,ensure_ascii=False),
                            'step_time':None  ,     
                            'step_num':None   
                            }
                    

                    my_db.insert('odin_business_emergency_record_detail_info',
                                    data2
                                )

                    my_db.insert('odin_business_emergency_record',
                                    data1
                                    )
                    #判断工作模式，是否需要提交到远程
                    work_model,url,minio_url = get_sync_url(work_model_col)
                    if work_model == '1':
                        submit_thread = Thread(target=emergency_sync,args=[url,minio_url,emergency_dir,image_byte,data1,data2])
                        submit_thread.start()                    

        mainlogger.info('--alarm_type: ' + str(alarm_algs))
        return

def accumulated_msg(emergency_time):
    '''
    过滤堆积的消息
    method:当告警时间与当前时间相差超过3分钟,选择舍弃这条消息
    '''
    now = datetime.now()
    time_interval = now - emergency_time
    if time_interval >= timedelta(minutes=3):
        return True
    return False

def get_sync_url(work_model_col):
    '''
    #获取工作模式和联网模式同步告警接口
    '''   
    work_model_item = work_model_col.find_one()
    work_model = work_model_item['model']
    serviceAddress = work_model_item['service_address']
    servicePort = work_model_item['service_port']
    url = NetAgreementType + "://" + serviceAddress + ":" + servicePort
    minio_url = work_model_item.get('service_minio_address',None)
    return work_model , url , minio_url

def get_organizationId(work_model_col):
    '''
    #获取工作模式表中的组织id
    '''   
    work_model_item = work_model_col.find_one()
    
    organization_id = work_model_item.get('organization_id',None)

    return organization_id

def points_transform(pt:list):
    '''
    说明：尾随和离岗算法，处理方式不同
    '''
    num = len(pt)
    points = []
    for i in range(0,num,2):
        item = {"x":pt[i],"y":pt[i+1]}
        points.append(item)
    return points


def find_associate_mission3(device_id,alg_num,alg_col,mission_col,asso_col):
    '''
    说明：算法发来的告警信息，找到匹配的布控任务
    '''
    res = list()
    mission_items = mission_col.find({'mission_status':0})
    for mission_item in mission_items:
        mission_id = mission_item['mission_id']
        query1 = {'device_id':device_id,'mission_id':mission_id}
        asso_item = asso_col.find_one(query1)
        if not asso_item:
            continue
        query2 = {'algorithm_constant_num':alg_num,"is_use":1,'mission_id':mission_id}
        alg_items = alg_col.find_one(query2)
        if not alg_items:
            continue
        res.append(mission_item['mission_id'])
    return res    

def emergency_popchoice():
    '''
    说明：是否弹窗的条件
    '''

    pop_stat = glv.get_value('pop_state',0)

    if emergencyPop_queue.qsize()==0:
        return True if pop_stat==0 else False
    else:
        num = emergencyPop_queue.get()
        glv.set_value('pop_state',num) 
        return True if num==0 else False


def sms_repull():
    '''
    说明：是否重新拉取投递任务的条件
    '''
    pull_stat = False 

    if smsdelivery_queue.qsize()==0:
        return pull_stat
    else:
        num = smsdelivery_queue.get()
        if num == 1:
            return True
        elif num == 0:
            return False

def smsconfig_repull():
    '''
    说明：是否重新拉取转发配置的条件
    '''
    config_pull_stat = False 

    if smsconfig_queue.qsize()==0:
        return config_pull_stat
    else:
        num = smsconfig_queue.get()
        if num == 1:
            return True
        elif num == 0:
            return False

def webhook_repull():
    '''
    说明：是否重新拉取转发任务的条件
    '''
    pull_stat = False 

    if webdelivery_queue.qsize()==0:
        return pull_stat
    else:
        num = webdelivery_queue.get()
        if num == 1:
            return True
        elif num == 0:
            return False
    
def filter_emergency(device_id,mission_id,algorithm_constant_num,re_pool:redis.Redis,emergencyIntervalTime=3):
    '''
    告警间隔内过滤告警事件；
    过滤条件：同一个摄像机，同一个任务，同一个算法
    '''
    if not emergencyIntervalTime:
        return False
    if type(emergencyIntervalTime) == str:
        emergencyIntervalTime = int(emergencyIntervalTime)
    key = device_id  + ":" + algorithm_constant_num
    value = "true"
    flag = re_pool.exists(key)
    if flag:
        return True
    else:
        mainlogger.info("写告警到Redis:{key：%s,emergencyIntervalTime：%s,value：%s}"%(key,emergencyIntervalTime,value))
        re_pool.setex(key,emergencyIntervalTime,value)
        return False

def emergency_timeperiod(missionWorkTime,emergency_time):
    '''
    过滤布控任务感知时间段外的告警事件;
    '''
    timelist = []
    if not missionWorkTime:
        return True
    missionWorkTime = json.loads(missionWorkTime)
    for item in missionWorkTime:
        a = item['time']
        b = a.split('-')
        timelist.append(b)

    timepoint = emergency_time.split(" ")[1]
    for item in timelist:
        if timepoint >= item[0] and timepoint <= item[1]:
            return True
    return False    

def emergency_in_period(missionWorkTime,emergency_time):
    if not missionWorkTime or missionWorkTime=="[]":
        return True
    weekday = emergency_time.weekday() + 1
    missionWorkTime = json.loads(missionWorkTime)
    if not missionWorkTime:
        return
    for item in missionWorkTime:
        status = item.get('status')
        if status == 1:
            continue
        week = item.get('week')
        if not week or str(weekday) in week:            
            timeRange = item.get('timeRange')
            timeRangeList = timeRange.split('-')
            localTtime = emergency_time.strftime("%H:%M")
            if localTtime >= timeRangeList[0] and localTtime <= timeRangeList[1]:
                return True
            if timeRangeList[0] == timeRangeList[1]:
                return True
    return False

def delete_pic(items,emergency_col):
    '''
    参数：items  odin_business_emergency_record表查到的
    '''
    for item in items:
        try:
            sub_source_id = item['sub_source_id']
            query = {'sub_source_id':sub_source_id}
            samepic_items = emergency_col.find(query)
            if samepic_items.count() > 1:
                continue
            emergency_time = item['emergency_time']
            temp = emergency_time.split(" ")[0].split('-')
            filedir = ''.join(temp)
            filepath = EMERGENCY_IMG_PATH + filedir +'/' + sub_source_id + '.jpg'
            if not os.path.exists(filepath):
                continue
            os.remove(filepath)
        except Exception as e:
            mainlogger.info('Delete Error : %s'%e)

def handle_3001_msg(msg_body,mongo:ToMongo):
    msg = json.loads(msg_body)
    max_camera = msg['max_camera']
    server_version = msg['server_version']
    my_db = mongo
    num = my_db.get_col("authority_base_info").find().count()
    if num == 0:
        base_config = BASE_INFO       
        base_config['algorithm_server_version'] = server_version
        base_config['video_camera_num'] = int(max_camera)
        base_config['create_time'] = datetime.now()
        base_config['last_modify_time'] = datetime.now()
        my_db.insert('authority_base_info',base_config)
    else:
        item = {}
        item['algorithm_server_version'] = server_version
        item['video_camera_num'] = int(max_camera)
        item['last_modify_time'] = datetime.now()
        my_db.update('authority_base_info',{},{"$set":item})

    work_info = my_db.get_col("authority_work_model").find_one({})
    mode = work_info.get("model")
    return mode

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


def emergency_sync(url,minio_address,emergency_dir,image_bytes,data1,data2):
    url_syn_emergency = url + SYN_EMERGENCY
    url_syn_pic = url + SYN_MINIO_DATA

    sub_source_id = data1['sub_source_id']
    filename =  '/EmergencyImage/%s/%s.jpg'%(emergency_dir,sub_source_id)
    if minio_address:
        minio_url = minio_address + '/wave-odin-business' + filename
    else:
        minio_url = PLATFORM_MINIO_URL + '/wave-odin-business' + filename

    try:
        item = {'fileName':filename,"emergencyRecordId":data1['emergency_record_id']}
        emergency_to_platform(url_syn_emergency,minio_url,data1,data2) 
        emergency_to_minio(url_syn_pic,image_bytes,content=item)               
    except Exception as e:
        mainlogger.info('--同步告警出错，%s'%e)
    return

def emergency_to_platform(remote_url,minio_url,data_emergency,data_emergency_detail):
    '''
    联网模式下告警数据同步到云平台
    '''
    headers = {'Content-Type': 'application/json'}
    data1 = database_to_dict(data_emergency,emergency_database,emergency_server)
    data1['createTime'] = data1['createTime'].strftime("%Y-%m-%d %H:%M:%S")
    data2 = database_to_dict(data_emergency_detail,emergency_detail_database,emergency_detail_server)
    
    data2['falseAlarmStatus'] = data1['falseAlarmStatus']
    data2['emergencyImage'] = minio_url
    data2['videoPreviewImage'] = minio_url
    content = {
                "emergencyRecordInfo": data1,
                "emergencyRecordDetailInfo" : data2
                }
    result = requests.post(remote_url,data=json.dumps(content),headers=headers,verify=False)
    return

def emergency_to_minio(remote_url,file,content):
    '''
    联网模式下告警图片同步进云平台的minio
    '''
    filetype = type(file)
    if filetype == bytes:
        picfile = {'file':(content['fileName'],file,'images/jpg')}
    elif filetype == str and os.path.exists(file):
        filebytes = open(file,'rb',encoding='utf-8')
        picfile = {'file':(content['fileName'],file,'images/jpg')}
    else:
        mainlogger.info('同步到minio错误,文件不存在或文件不不支持的格式！')
        return
    try:
        result = requests.post(remote_url,data=content,files=picfile,verify=False)
        mainlogger.info("同步图片到平台resp:%s"%result.json())
    except Exception as e:
        mainlogger.info('--同步失败，%s'%e)
    return   


def format_datestr_with_zone(datetime_str: str):
    """
    格式化带时区时间字符串，返回datetime类型时间
    :param datetime_str: 2022-06-14T15:16:31+00:00
    :return: datetime
    """
    format_ = '%Y-%m-%d %H:%M:%S'
    if '.' in datetime_str:
        format_ = format_ + '.%f'
    if '+' in datetime_str:
        datetime_str = datetime_str.split('+')[0]
    if 'T' in datetime_str:
        format_ = format_.replace(' ', 'T')
    return datetime.strptime(datetime_str, format_)


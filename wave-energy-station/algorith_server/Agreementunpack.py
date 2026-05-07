
from datetime import datetime,timedelta
import os
import json
import uuid
import base64
import socket
import time
from .Algorithmutil import Identifier_to_constant, get_algorithm_num
from Utils.db import ToMongo
import paho.mqtt.client as mqtt
import redis
from system.system_route import emergencyPop_queue
from system.system_misc import get_ip,get_nginx_port
from .Alibabasms import SendSmsResqueset
from .RelayEmergency import Sendwebrequest
from emergency.advise_router import smsdelivery_queue,webdelivery_queue
from msg_queue import faceidentification_queue
from system.system_route import smsconfig_queue
from config import BASE_INFO,EMERGENCY_IMG_PATH
from Utils.datacfg import *
import requests
from threading import Thread
from config import EMERGENCY_IMG_PATH,PLATFORM_MINIO_URL
import sys
import Utils.logger as logger
import Utils.edgebox_repo  # noqa: F401
from edgebox_db.mongo_collections import (
    CONTROL_DEVICE_ALGORITHM_ASSOCIATE,
    CONTROL_MANAGE_MISSION,
    WORK_FLOW_ALGORITHM_CONSTANT,
)
import traceback
import Utils.glv as glv
from Utils.voicedevice_utils import *
from flask import request
import xmltodict
import re
from system.sync_model import check_service_addr

from device.Serialnetservice import SerialNetServer

mainlogger = logger.getLogger('main')


host_ip = get_ip()
nginx_port = get_nginx_port()
#glv.init()
glv.set_value('nginx_port',nginx_port)
pathhead = 'http://%s:%s/net-web/control/event_images/'%(host_ip,nginx_port)

image_dir = EMERGENCY_IMG_PATH
SYN_EMERGENCY = '/business/sync/synAddAllEmergency'
SYN_MINIO_DATA = '/business/sync/synFileToMinio'

# 热成像温度告警固定走算法常量号 105（与 find_associate_mission4 / 布控关联表一致）
THERMAL_ALGORITHM_CONSTANT_NUM = '105'


def _json_loads_message_body(msg_body):
    """协议帧 body 常为 bytes，Python3 的 json.loads 需要 str。"""
    if isinstance(msg_body, (bytes, bytearray)):
        msg_body = msg_body.decode('utf-8')
    return json.loads(msg_body)


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
                           # mainlogger.info('--msg_total : ' + msg_body)
                            if msg_type == b"03008":
                                #人脸特征信息存入队列
                                faceidentification_queue.put(msg_body)
                            if msg_type == b"03001":
                                mainlogger.info('----msg_body : %s' % msg_body)
                                result = handle_3001_msg(msg_body,mongo)
                                from .AlgorithServer_v2 import SenderThread
                                sender = SenderThread(context=None)
                                sender.start_controls_message()
                            if msg_type == b"04002":
                                result = handle_msg(msg_body,mongo,mqtt_client,sms,webhook,re_pool)
                            if msg_type == b"04003":
                                msg = _json_loads_message_body(msg_body)
                                mainlogger.info("--crowdEmergency:%s"%msg)
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
                            result = handle_3001_msg(msg_body,mongo)
                            from .AlgorithServer_v2 import SenderThread
                            sender = SenderThread(context=None)
                            sender.start_controls_message()
                        if msg_type == b"04002":
                            result = handle_msg(msg_body,mongo,mqtt_client,sms,webhook,re_pool)
                        if msg_type == b"04003":
                            msg = _json_loads_message_body(msg_body)
                            mainlogger.info("--crowdEmergency:%s"%msg)
                        msg_cache = msg_cache[length:]
                    else:
                        msg_cache = msg_cache[num+2:]
        else:
            msg_cache = b""
            return msg_cache

def handle_msg(msg_body,mongo:ToMongo,mqtt_client:mqtt.Client,sms:SendSmsResqueset,webhook:Sendwebrequest,re_pool:redis.Redis):

        my_db = mongo
        msg_body = _json_loads_message_body(msg_body)

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
        asso_col =               my_db.get_col(CONTROL_DEVICE_ALGORITHM_ASSOCIATE)
        mission_col =            my_db.get_col(CONTROL_MANAGE_MISSION)
        emergency_col =          my_db.get_col('odin_business_emergency_record')
        emergency_detail_col =   my_db.get_col('odin_business_emergency_record_detail_info')
        alg_constant_col =       my_db.get_col(WORK_FLOW_ALGORITHM_CONSTANT)

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
            constant_item = alg_constant_col.find_one({'algorithm_constant_num':algorithm_constant_num})
            if not constant_item:
                continue
            constant_id = constant_item.get("algorithm_constant_id")

            #查布控任务信息
            mission_id_list = find_associate_mission4(device_id,constant_id,mission_col,asso_col)
            if not mission_id_list :
                continue
            for mission_id in mission_id_list:
                missioncol_item = mission_col.find_one({'control_id':mission_id})

                model_path = constant_item['algorithm_constant_name']
                alarm_algs.append(model_path)

                if missioncol_item:
                    emergency_level = constant_item['algorithm_level']
                    missionWorkTime = missioncol_item['emergency_response_time']
                    emergencyIntervalTime = constant_item['algorithm_interval']
                else:
                    emergency_level = 1   #默认为1
                    missionWorkTime = None
                    emergencyIntervalTime = 5
                
                # #过滤不在感知时段的告警事件
                # flag_in_timeperiod = emergency_timeperiod(missionWorkTime,emergency_time)   
                # if not flag_in_timeperiod:
                #     continue
                res = filter_emergency(device_id,mission_id,algorithm_constant_num,re_pool,emergencyIntervalTime)
                if res:
                    #print('不满足%s秒告警间隔:'%str(emergencyIntervalTime))
                    continue
         
                #将告警图存入磁盘
                writepic_thread = Thread(target=write_image,args=[sub_source_id,emergency_dir,image_byte])
                writepic_thread.start()

                control_name = missioncol_item['control_name']
                storage_time = missioncol_item['storage_time']
                storage_num = missioncol_item['storage_num']

                algorithm_color = constant_item['algorithm_color']

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
                work_model,url,minio_url,bind_organizationid = get_sync_url(work_model_col)
                service_address = check_service_addr(url)
                if work_model == '1':
                    submit_thread = Thread(target=emergency_sync,args=[service_address,emergency_dir,image_byte,data1,data2,bind_organizationid])
                    submit_thread.start()
                
                #删除过期告警和超过存储数目的告警
                delete_thread = Thread(target=delete_overdate_emergency,args=[emergency_col,emergency_detail_col,mission_id,storage_time,storage_num])
                delete_thread.start()

                #发送声光告警
                # Alarm_thread = Thread(target=equip_alarm,args=[my_db,mission_id,constant_item])
                # Alarm_thread.start()

                #发送声光告警
                device_equ_info = missioncol_item.get('device_equ_info')
                Alarm_thread = Thread(target=deal_equip,args=[my_db,device_equ_info])
                Alarm_thread.start()

                if emergency_popchoice():
                    #发布弹窗
                    publish_mqtt_thread = Thread(target=publish_mqtt,args=[mqtt_client,info_list,data1,data2,organization_id])
                    publish_mqtt_thread.start()

                if smsconfig_repull():
                    mainlogger.info("---重新拉取短信sms配置---")
                    sms.get_sms_config()

                if sms_repull():
                    mainlogger.info("---重新拉取短信投递任务---")
                    sms.get_sms_delivery()

                sms_msg =  {"controlName":control_name,
                            "modelName":model_path,
                            "modelPath":model_path,
                            "deviceName":device_name,
                            "adress":emergency_position,
                            "time":emergency_time,
                            "emergencyImage":image_base64,
                            "emergencyImageUrls":emergency_image,
                            'controlId':mission_id,
                            'deviceId':device_id,
                            'modelId':constant_item['algorithm_constant_id'],
                            'emergencyId':emergency_record_id,
                            'positionId':position_id,
                            }
                params_dict = {'organization_id':organization_id,
                            'emergency_record_id':emergency_record_id}
                sms.send_sms_thread(sms_msg,params_dict)
                        
                if webhook_repull():
                    mainlogger.info("---重新拉取告警转发任务---")
                    webhook.get_webhook_delivery()
                webhook.send_webhook_thread(sms_msg,params_dict)
                
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
    bind_organizationid = work_model_item['service_organization_id']
    serviceAddress = work_model_item['service_address']
    servicePort = work_model_item['service_port']
    minio_url = work_model_item.get('service_minio_address',None)
    return work_model , serviceAddress , minio_url, bind_organizationid

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

def points_transform(pt:list):
    '''
    说明：算法发来的告警信息，找到匹配的布控任务
    '''
    query = {"camera_id":device_id,"algorithm_constant_id":algorithm_constant_id}
    assItems = asso_col.find(query)
    if not assItems:
        return
    res = []
    for item in assItems:
        mission_id = item.get("control_id")
        if mission_id:
            res.append(mission_id)
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
    key = device_id +":" +mission_id  +":" + algorithm_constant_num
    value = "true"
    flag = re_pool.exists(key)
    if flag:
        return True
    else:
        re_pool.setex(key,emergencyIntervalTime,value)
        return False

def emergency_timeperiod(missionWorkTime,emergency_time):
    '''
    过滤布控任务感知时间段外的告警事件;
    '''
    timelist = []
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
    
def delete_overdate_emergency(emergency_col,emergency_detail_col,mission_id,storage_time,storage_num):
    '''
    删除过期过期数据和超过存储数目的告警
    '''
    emergency_items = emergency_col.find({"mission_id":mission_id}).sort("emergency_time")
    emergency_nums = emergency_items.count()
    if emergency_nums > storage_num:   
        num = emergency_nums - storage_num -1
        timepoint1 = emergency_items[num]['emergency_time']
        query = {'mission_id':mission_id,'emergency_time':{"$lte":timepoint1}}
        items = emergency_col.find(query)
        if items.count() == 0:
            return
        emergency_list = list(items).copy()
        emergency_col.delete_many(query)
        delete_pic(emergency_list,emergency_col)        
        for item in emergency_list:
            record_id = item['emergency_record_id']
            emergency_detail_col.delete_one({'emergency_record_id':record_id})
    now = datetime.now()
    daynums = storage_time*30
    timepoint2 = now-timedelta(days=daynums)
    timepoint2 = timepoint2.strftime("%Y-%m-%d %H:%M:%S")
    if emergency_nums != 0:
        if emergency_items[0]['emergency_time'] < timepoint2:
            query_overdate = {'mission_id':mission_id,'emergency_time':{"$lte":timepoint2}}
            items = emergency_col.find(query_overdate)
            if items.count() == 0:
                return
            emergency_list = list(items).copy()
            emergency_col.delete_many(query_overdate)
            delete_pic(emergency_list,emergency_col)            
            for item in emergency_list:
                record_id = item['emergency_record_id']
                emergency_detail_col.delete_one({'emergency_record_id':record_id})

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
    msg = _json_loads_message_body(msg_body)
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

def publish_mqtt(mqtt_client,info_list,data1,data2,organization_id):
    if not mqtt_client:
        mainlogger.info('Mqtt服务离线')
        return
    else:
        status = mqtt_client.is_connected()
        if not status:
            mainlogger.info('Mqtt失去连接 %s'%mqtt_client.is_connected())
            return
    mainlogger.info('Mqtt连接在线 %s'%mqtt_client.is_connected())

    topic = "advise-web-topic/" + organization_id + "/emergencyAdviseTag"
    mainlogger.info('Mqtt publish topic : %s'%topic)

    emergency_record_detail_info = []
    iter = {}
    iter['videoPreviewImage'] = data2['video_preview_image']
    iter['discernTime'] = data2['discern_time']
    iter['groupMatterName'] = data1['model_path']
    iter['num'] = data2['num']
    if not info_list:
        iter['emergencyImageExtraInfo'] = None
    else:
        iter['emergencyImageExtraInfo'] = json.dumps(info_list)
    iter['groupNum'] = data2['group_num']
    iter['emergencyImage'] = data2['emergency_image']
    iter['algorithmConstantNum'] = data2['algorithm_constant_num']
    emergency_record_detail_info.append(iter)

    advise_content = {}
    advise_content['emergencyRecordId'] = data1['emergency_record_id']
    advise_content['deviceNum'] = data1['device_num']
    advise_content['adress'] = data1['emergency_position']
    advise_content['modelName'] = data1['model_path']
    advise_content['emergencyRecordDetailInfos'] = emergency_record_detail_info
    advise_content['level'] = data1['emergency_level']
    advise_content['cameraId'] = data1['device_id']
    advise_content['emergencyImageUrls'] = data2['emergency_image']
    advise_content['adviseServiceTime'] = data1['create_time'].strftime("%Y-%m-%d %H:%M:%S")
    advise_content['modelPath'] = data1['model_path']
    advise_content['controlName'] = data1['control_name']
    advise_content['time'] = data1['emergency_time']
    advise_content['deviceName'] = data1['device_name']

    parameter = {}
    parameter['emergencyRecordId'] = data1['emergency_record_id']
    parameter['cameraId'] = data1['device_id']

    mqtt_msg = {}
    mqtt_msg['adviseContent'] = json.dumps(advise_content)
    mqtt_msg['sourceType'] = 0
    mqtt_msg['adviseType'] = 0
    mqtt_msg['audioType'] = data1['emergency_audio']
    mqtt_msg['birthTime'] = data1['create_time'].strftime("%Y-%m-%d %H:%M:%S")
    mqtt_msg['emergencyMusicCloseMethod'] = data1['emergency_music_close_method']
    mqtt_msg['organizationId'] = organization_id
    mqtt_msg['parameter'] = json.dumps(parameter)


    mqtt_client.publish(topic,
                json.dumps(mqtt_msg, ensure_ascii=False),
                qos=0,
                )
    return

def emergency_sync(url,emergency_dir,image_bytes,data1,data2,bind_organizationid):
    url_syn_emergency = url + SYN_EMERGENCY
    url_syn_minio = url + SYN_MINIO_DATA

    sub_source_id = data1['sub_source_id']
    filename =  '/EmergencyImage/%s/%s.jpg'%(emergency_dir,sub_source_id)  
    minio_url =  '/wave-odin-business' + filename
    try:
        emergency_to_minio(url_syn_minio,image_bytes,filename)
        emergency_to_platform(url_syn_emergency,minio_url,data1,data2,bind_organizationid)        
    except Exception as e:
        mainlogger.info('--同步告警出错，%s'%e)
    return

def emergency_to_platform(remote_url,minio_url,data_emergency,data_emergency_detail,bind_organizationid):
    '''
    联网模式下告警数据同步到云平台
    '''
    headers = {'Content-Type': 'application/json'}
    data1 = database_to_dict(data_emergency,emergency_database,emergency_server)
    data1['createTime'] = data1['createTime'].strftime("%Y-%m-%d %H:%M:%S")
    data1['bindOrganizationId'] = bind_organizationid
    data2 = database_to_dict(data_emergency_detail,emergency_detail_database,emergency_detail_server)
    
    data2['falseAlarmStatus'] = data1['falseAlarmStatus']
    data2['emergencyImage'] = minio_url
    data2['videoPreviewImage'] = minio_url
    content = {
                "emergencyRecordInfo": data1,
                "emergencyRecordDetailInfo" : data2
                }
    result = requests.post(remote_url,data=json.dumps(content),headers=headers,verify=False)
    resp = result.json() 
    mainlogger.info('--同步告警到平台成功,resp:%s ；'%resp)
    return

def emergency_to_minio(remote_url,file,fileName):
    '''
    联网模式下告警图片同步进云平台的minio
    '''
    filetype = type(file)
    if filetype == bytes:
        picfile = {'file':file}
    elif filetype == str and os.path.exists(file):
        filebytes = open(file,'rb')
        picfile = {'file':filebytes}
    else:
        mainlogger.info('--同步到minio错误,文件不存在或文件不不支持的格式！')
        return
    item = {'fileName':fileName}
    try:
        result = requests.post(remote_url,data=item,files=picfile,verify=False)
        mainlogger.info('--同步到minio成功,url:%s'%remote_url)
    except Exception as e:
        mainlogger.info('--同步失败，%s'%e)
    return   

def sendKonnadmessage(ip,port,chanel_num,delay_time):
    try:

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        ADDR = (ip,port)
        s.connect(ADDR)

        if chanel_num == 1:
            turnOnKey = "000100000006FF050064FF00"
            turnOffKey = "000100000006FF0500640000"
        elif chanel_num == 2:
            turnOnKey = "000100000006FF050065FF00"
            turnOffKey = "000100000006FF0500650000"
        else:
            return
        s.send(bytes.fromhex(turnOnKey))
        if delay_time > 0:
            time.sleep(delay_time)
        else:
            time.sleep(3)
        s.send(bytes.fromhex(turnOffKey))
        s.close()
    except Exception as e:
        mainlogger.info('Error:康奈德声光告警失败,Reason:%s'%e)
    return

def equip_alarm(my_db,mission_id,constant_item):

    equip_col = my_db.get_col('odin_device_equip')
    sound_col = my_db.get_col('odin_device_sound')
    
    query = {'mission_id':mission_id,'alarm_mute':'0'}
    items = equip_col.find(query)
    if items.count() == 0:
        return
    for item in items:
        equip_type = item['equip_type']
        
        if equip_type == 1:
            #康奈德声光告警
            ip = item['equip_ip']
            port = item['equip_port']
            chanel_num = item['channel_number']
            delay_time = item['reset_delay_time']
            result = sendKonnadmessage(ip,port,chanel_num,delay_time)
        elif equip_type == 2:
            #Itc音响
            equip_id = item['equip_id']
            sound_type = constant_item.get('algorithm_sound_type',None)
            sound_file = constant_item.get('algorithm_sound_file',None)
            itc_server_col = my_db.get_col('odin_device_itc_server')
            server_item = itc_server_col.find_one()
            if server_item:
                itc_server_address = server_item['itc_server_address']
                itc_server_port = server_item['itc_server_port']
                account = server_item['itc_server_account']
                password = server_item['itc_server_password']
                server_url = 'http://%s:%s'%(itc_server_address,itc_server_port)
                result = sendSoundmessage(sound_col,equip_id,sound_type,sound_file,server_url,account,password)
        elif equip_type == 3:
            #菱声音响
            equip_id = item['equip_id']
            sound_type = constant_item.get('algorithm_sound_type',None)
            sound_file = constant_item.get('algorithm_sound_file',None)
            lings_server_col = my_db.get_col('odin_device_lings_server')
            server_item = lings_server_col.find_one()
            if server_item:
                lings_server_address = server_item['lings_server_address']
                lings_server_port = server_item['lings_server_port']
                lings_tts_port = server_item['lings_tts_port']
                server_url = 'http://%s:%s'%(lings_server_address,lings_server_port)
                tts_server_url = 'http://%s:%s'%(lings_server_address,lings_tts_port)
                result = sendSoundmessage(sound_col,equip_id,sound_type,sound_file,server_url=server_url,tts_url=tts_server_url)

def deal_equip(my_db,equip_info):
    if not equip_info:
        return
    audio_col = my_db.get_col('odin_dynamic_audio')
    for equip_item in equip_info:
        try:
            alarmMute = equip_item.get("alarmMute")
            if alarmMute == '1':
                continue
            equipType = equip_item.get("equipType")
            if equipType == 1:
                #康奈德声光告警
                ip = equip_item['equipIp']
                port = equip_item['equipPort']
                chanel_num = equip_item['channelNumber']
                delay_time = equip_item['resetDelayTime']
                result = sendKonnadmessage(ip,port,chanel_num,delay_time)
            elif equipType == 2:
                #485设备声光告警
                equipId = equip_item.get("equipId")
                audio_item = audio_col.find_one({'device_id':equipId})
                deviceAddr = audio_item.get('device_addr')
                ip = audio_item.get('ip')
                port = audio_item.get('port')
                if not deviceAddr:
                    continue
                newItem = equip_item.copy()
                newItem['deviceAddr'] = deviceAddr
                newItem['stopFlag'] = 1
                addr = (ip,int(port))
                instance = SerialNetServer(context=None)
                instance.alarm_audio(addr,newItem)

        except Exception as e:
            mainlogger.exception(e)
            continue

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
    # zone_ = re.search(r'[+-]\d{2}:\d{2}', datetime_str)
    # if zone_:
    #     format_ = format_ + '%z'
    if 'T' in datetime_str:
        format_ = format_.replace(' ', 'T')
    return datetime.strptime(datetime_str, format_)

def handle_hikhotcam(req,mongo:ToMongo,mqtt_client:mqtt.Client,sms:SendSmsResqueset,webhook:Sendwebrequest,re_pool:redis.Redis):
    try:
        mainlogger.info('===开始接受热成像告警===')
        my_db = mongo

        #获取告警报文
        f = req[1]
        fdict = dict(f.lists())
        flist = fdict.get('TMA')
        if not flist:
            #如果不是温度告警，直接不处理
            return
        
        #获取报文中xml
        xmldata = req[0].get('TMA')
        if not xmldata:
            return
        jsondata = xmltodict.parse(xmldata)

        EventNotificationAlert = jsondata.get('EventNotificationAlert')
        emergency_datetime = format_datestr_with_zone(EventNotificationAlert.get('dateTime'))
        emergency_time = emergency_datetime.strftime("%Y-%m-%d %H:%M:%S")
        emergency_dir = emergency_datetime.strftime("%Y%m%d")
        cam_ip = EventNotificationAlert.get('ipAddress')


        device_col = my_db.get_col('odin_device_camera_edit')
        query = {"camera_ip":cam_ip}
        device_item = device_col.find_one(query)
        if not device_item:
            return

        device_id = device_item.get('camera_id')

        asso_col = my_db.get_col(CONTROL_DEVICE_ALGORITHM_ASSOCIATE)
        mission_col = my_db.get_col(CONTROL_MANAGE_MISSION)
        alg_constant_col = my_db.get_col(WORK_FLOW_ALGORITHM_CONSTANT)
        constant_item = alg_constant_col.find_one(
            {'algorithm_constant_num': THERMAL_ALGORITHM_CONSTANT_NUM})
        if not constant_item:
            return
        thermal_algorithm_constant_id = constant_item['algorithm_constant_id']
        mission_id_list = find_associate_mission4(
            device_id, thermal_algorithm_constant_id, mission_col, asso_col)
        if not mission_id_list:
            return

        position_associate_col = my_db.get_col("odin_device_device_position_associate")
        position_col =           my_db.get_col("odin_device_position")
        work_model_col =         my_db.get_col('authority_work_model')
        emergency_col =          my_db.get_col('odin_business_emergency_record')
        emergency_detail_col =   my_db.get_col('odin_business_emergency_record_detail_info')

        #查询组织id信息
        organization_id = get_organizationId(work_model_col)

        # 生成告警图的路径
        sub_source_id = uuid.uuid4().hex
        emergency_image = pathhead + sub_source_id + '?' + 'date=%s'%emergency_dir


        # 查询关联的位置信息
        query_device = {'device_id':device_id}
        position_item = position_associate_col.find_one(query_device)
        position_id = position_item['position_id'] if position_item else None
        query_position = {'position_id':position_id}
        position_info = position_col.find_one(query_position)
        if position_info:
            emergency_position = position_info['position_city'] + ',' + position_info['position_area'] + ',' + position_info['position_desc']
            emergency_lon_and_lat = position_info['lon_and_lat']
        else:
            emergency_position = ''
            emergency_lon_and_lat = ''


        for mission_id in mission_id_list:
            missioncol_item = mission_col.find_one({'control_id': mission_id})
            if not missioncol_item:
                continue

            emergency_level = constant_item['algorithm_level']
            missionWorkTime = missioncol_item.get('emergency_response_time')
            if not missionWorkTime:
                missionWorkTime = '[{"time":"00:00:00-23:59:59"}]'
            alg_interval = constant_item.get('algorithm_interval')
            emergencyIntervalTime = int(alg_interval) if alg_interval is not None else 5

            flag_in_timeperiod = emergency_timeperiod(missionWorkTime, emergency_time)
            if not flag_in_timeperiod:
                continue
            res = filter_emergency(
                device_id, mission_id, THERMAL_ALGORITHM_CONSTANT_NUM, re_pool, emergencyIntervalTime)
            if res:
                continue

            #将告警图存入磁盘
            hot_image = flist[1]  #0是普通摄像机  1是热成像摄像机
            writepic_thread = Thread(target=write_hot_image,args=[sub_source_id,emergency_dir,hot_image])
            writepic_thread.start()
            img_path = image_dir + emergency_dir + '/' + sub_source_id + '.jpg'

            control_name = missioncol_item['control_name']
            storage_time = missioncol_item['storage_time']
            storage_num = missioncol_item['storage_num']

            model_path = constant_item['algorithm_constant_name']

            num = None #图片框选数

            emergency_record_id = uuid.uuid4().hex
            emergency_record_detail_info_id = uuid.uuid4().hex

            data1 = {'emergency_record_id':emergency_record_id,
                    'emergency_level':emergency_level,
                    'emergency_position':emergency_position,
                    'emergency_media_info':None,   #媒体视频信息
                    'mission_id':mission_id,
                    'emergency_time':emergency_time,
                    'alarm_status':"1",
                    'emergency_lon_and_lat':emergency_lon_and_lat,
                    'organization_id':organization_id,
                    'create_time':datetime.now(),
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
                    'device_name':device_item.get('camera_name'),
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
                    'discern_time': emergency_time,
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
                    'algorithm_constant_num' : THERMAL_ALGORITHM_CONSTANT_NUM,
                    'emergency_image_extra_info' : None,
                    'step_time':None  ,     
                    'step_num':None   
                    }

            my_db.insert('odin_business_emergency_record_detail_info',
                         data2)

            my_db.insert('odin_business_emergency_record',
                         data1)

            #判断工作模式，是否需要提交到远程
            work_model, url, minio_url, bind_organizationid = get_sync_url(work_model_col)
            if work_model == '1':
                submit_thread = Thread(
                    target=emergency_sync,
                    args=[url, minio_url, emergency_dir, img_path, data1, data2, bind_organizationid])
                submit_thread.start()

            #删除过期告警和超过存储数目的告警
            delete_thread = Thread(
                target=delete_overdate_emergency,
                args=[emergency_col, emergency_detail_col, mission_id, storage_time, storage_num])
            delete_thread.start()

            Alarm_thread = Thread(target=equip_alarm, args=[my_db, mission_id, constant_item])
            Alarm_thread.start()

            if emergency_popchoice():
                publish_mqtt_thread = Thread(
                    target=publish_mqtt, args=[mqtt_client, None, data1, data2, organization_id])
                publish_mqtt_thread.start()

            if smsconfig_repull():
                mainlogger.info("---重新拉取短信sms配置---")
                sms.get_sms_config()

            if sms_repull():
                mainlogger.info("---重新拉取短信投递任务---")
                sms.get_sms_delivery()

            sms_msg = {"controlName": control_name,
                       "modelName": model_path,
                       "modelPath": model_path,
                       "deviceName": data1['device_name'],
                       "adress": emergency_position,
                       "time": emergency_time,
                       "emergencyImage": None,
                       "emergencyImageUrls": emergency_image,
                       'controlId': mission_id,
                       'deviceId': device_id,
                       'modelId': constant_item['algorithm_constant_id'],
                       'emergencyId': emergency_record_id,
                       'positionId': position_id,
                       }
            params_dict = {'organization_id': organization_id,
                           'emergency_record_id': emergency_record_id}
            sms.send_sms_thread(sms_msg, params_dict)

            if webhook_repull():
                mainlogger.info("---重新拉取告警转发任务---")
                webhook.get_webhook_delivery()
            webhook.send_webhook_thread(sms_msg, params_dict)

    except Exception as e:
        import traceback
        mainlogger.info(''+traceback.format_exc())
        return

    return

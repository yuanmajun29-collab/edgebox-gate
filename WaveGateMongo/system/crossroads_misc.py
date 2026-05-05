import socket
import serial
import json
import uuid
import time
import requests
import subprocess
from .curve_misc import *
from queue import Queue

crosslogger = logger.getLogger("cross")

#交通灯对应的字节
lightColorMap = {0:b'\x98', 1:b'\x96', 2:b'\x97'}  

chanelMap = {0:b'\x02', 1:b'\x00', 2:b'\x01'}

SYN_CROSSROAD_STATUS = "/business/syn/synCrossroadDeviceStatus" #同步红绿灯设备状态

def convert_road_ruler(light_ruler_item):
    # 转换红绿灯规则
    light_ruler = light_ruler_item.get('traffic_light_ruler_json')
    light_ruler_list = json.loads(light_ruler)
    yellow_light_time = light_ruler_item.get('yellow_light_time')  #黄灯闪烁时间
    result = {}
    for item in light_ruler_list:
        weeks = item.get('weeks')
        controlTime = item.get('controlTime')
        greenLightTimeGroup1 = item.get('greenLightTimeGroup1')
        greenLightTimeGroup2 = item.get('greenLightTimeGroup2')
        greenLightTime = item.get('greenLightTime')

        for week in weeks:
            subItem = {}
            controlType = item.get('controlType')
            direction = item.get('direction')
            crossroad_type = item.get('crossroadType')
            subItem['controlType'] = controlType   #混合放行/单向放行
            subItem['roadType'] =  crossroad_type #十字路口/叉字路口
            subItem['direction'] = direction #方向分组          
            subItem['controlTime'] = json.loads(controlTime)          

            if controlType == '1':
                #混合放行
                subItem['timeGroup1'] = {'green':greenLightTimeGroup1,
                                        'yellow':yellow_light_time,
                                        'red':greenLightTimeGroup2+yellow_light_time}
                subItem['timeGroup2'] = {'green':greenLightTimeGroup2,
                                        'yellow':yellow_light_time,
                                        'red':greenLightTimeGroup1+yellow_light_time}
            else:
                #单向放行和智能通行
                timeDict = dict(zip(direction,greenLightTime))
                total_green = sum(greenLightTime)
                subItem['greenLightTime'] = timeDict
                subItem['yellowLightTime'] = yellow_light_time
                
                subItem['timeGroup1'] = {'green':timeDict['1'],
                                        'yellow':yellow_light_time,
                                        'red':total_green + yellow_light_time*3 - timeDict['1']}
                subItem['timeGroup2'] = {'green':timeDict['2'],
                                        'yellow':yellow_light_time,
                                        'red':total_green - timeDict['2'] + yellow_light_time*3}
                subItem['timeGroup3'] = {'green':timeDict['3'],
                                        'yellow':yellow_light_time,
                                        'red':total_green - timeDict['3'] + yellow_light_time*3}
                if crossroad_type == '0':
                    #十字路口才有四个方向，叉字路口只有三个方向
                    subItem['timeGroup4'] = {'green':timeDict['4'],
                                            'yellow':yellow_light_time,
                                            'red':total_green - timeDict['4'] + yellow_light_time*3}
                    
                if controlType == '3':
                    #智能通行
                    subItem['vehicleTrafficTime'] = item.get('vehicleTrafficTime')
                    subItem['pedestrianTrafficTime'] = item.get('pedestrianTrafficTime')
                    subItem['yellowLightTime'] = yellow_light_time

            content = result.get(week)
            if not content:
                result[week] = [subItem]
            else:
                content.append(subItem)
                result[week] = content

    return result

def get_current_weekday():
    '''
    获取今天是星期几；
    '''
    now = datetime.now()
    current_date = now.date()
    current_weekday = current_date.weekday() + 1
    return current_weekday

def get_ruler_now(rulerList):
    '''
    判断当前时间的红绿灯规则；
    '''
    if not rulerList:
        return None
    now = datetime.now()
    now_str = now.strftime("%H:%M")
    for rulerItem in rulerList:
        controlTime = rulerItem.get('controlTime')
        startTime = controlTime.get('startTime')
        endTime = controlTime.get('endTime')
        if startTime <= now_str and endTime > now_str:
            return rulerItem
    return None

def set_radar(socketServer,speed,sensitivity,anti_jam,direction,angle):
    '''
    设置雷达参数
    speed:速度阈值
    sensitivity:检测灵敏度
    anti_jam:抗干扰参数
    direction:目标检测方向  0-双向 1-来向 2-去向
    '''
    try:
        #设置速度阈值
        hex_speed = int2hex(speed)
        cmd1 = '0106025600' + hex_speed
        msg1 = {"mb":cmd1,"sn":1,"ack":1,"crc":1}
        json_msg1 = json.dumps(msg1)
        bytes_msg1 = json_msg1.encode('utf-8')
        socketServer.send(bytes_msg1)

        #设置检测方向
        time.sleep(0.5)
        hex_direction = int2hex(direction)
        cmd2 = '0106025400' + hex_direction
        msg2 = {"mb":cmd2,"sn":1,"ack":1,"crc":1}
        json_msg2 = json.dumps(msg2)
        bytes_msg2 = json_msg2.encode('utf-8')
        socketServer.send(bytes_msg2)

        #设置灵敏度
        time.sleep(0.5)
        hex_sensitivity = int2hex(sensitivity)
        cmd3 = '0106025000' + hex_sensitivity
        msg3 = {"mb":cmd3,"sn":1,"ack":1,"crc":1}
        json_msg3 = json.dumps(msg3)
        bytes_msg3 = json_msg3.encode('utf-8')
        socketServer.send(bytes_msg3)

        #设置抗干扰
        time.sleep(0.5)
        hex_jam = int2hex(anti_jam)
        cmd4 = '0106025800' + hex_jam
        msg4 = {"mb":cmd4,"sn":1,"ack":1,"crc":1}
        json_msg4 = json.dumps(msg4)
        bytes_msg4 = json_msg4.encode('utf-8')
        socketServer.send(bytes_msg4)

        #设置补偿角
        time.sleep(0.5)
        hex_angle = int2hex(angle)
        cmd5 = '0106025200' + hex_angle
        msg5 = {"mb":cmd5,"sn":1,"ack":1,"crc":1}
        json_msg5 = json.dumps(msg5)
        bytes_msg5 = json_msg5.encode('utf-8')
        socketServer.send(bytes_msg5)

    except Exception as e:
        crosslogger.exception(e)

def redis_fuzzy_query(rePool,keyword):
    fuzzy_key = keyword + "*"
    keys_list = rePool.keys(pattern = fuzzy_key)
    result = []
    for key in keys_list:
        newItem = key.decode()
        result.append(newItem)
    return result

def get_min_expire_time(rePool,keysList):
    '''
    获取到keysList中最短的过期时间;
    '''
    try:
        min_ttl = 0
        min_ttl_key = None
        for key in keysList:
            expiretime = rePool.pttl(name=key)
            if min_ttl == 0 or expiretime < min_ttl:
                min_ttl = expiretime
                min_ttl_key = key
        return min_ttl_key
    except Exception as e:
        crosslogger.exception(e)

def get_key_by_value(dictionary, value, default=None):
    for key, val in dictionary.items():
        if val == value:
            return key
    return default

def radar_msg_cache(msgCache:str):
    n = msgCache.find('}')
    if n == '-1':
        return msgCache,None
    return msgCache[n+1:],msgCache[:n+1]

class RoadManage:
    __instance = None
    __flag = False

    def __new__(cls, *args, **kwargs):
        # super().__new__(cls)
        if cls.__instance is None:
            cls.__instance = super().__new__(cls)
        return cls.__instance 
    
    def __init__(self, context):
        if not RoadManage.__flag:
            RoadManage.__flag = True
            self.context = context

            self.deviceMap = {}
            self.lightRuler = {}  #红绿灯规则
            self.mainRuler = {}   #控制开关和各种规则
            self.ruleNow = {}     #当前时间的红绿灯规则
            self.lightOrderMap = {}   #交通灯播放顺序

            self.lightDirectionMap = {}  #交通灯和方向的对应关系
            self.camDirectionMap = {}    #摄像机和方向的对应关系

            #声光告警器相关变量
            self.socketMap = {}
            self.taskListAudio = []
            self.taskRadar = [] 
            self.socketClosedMap = {}

            self.radarStatusMap = {} #雷达状态
            self.soundStatusMap = {} #声光告警器状态
       
            self.my_db = ToMongo('wavedevice')         
            self.rePool = redis_database

            self.get_all_task()

            # 控制交通灯
            cronssing_manage_thread = Thread(target=self.crossing_control,args=[])
            cronssing_manage_thread.start()

            # 维护弯道声光告警器状态
            threadAudioStatus = Timer(function=self.get_audio_status,interval=5,args=[])
            threadAudioStatus.start()

            # 维护弯道雷达状态
            threadRadarStatus = Thread(target=self.get_radar_status,args=[])
            threadRadarStatus.start()

            # 维护弯道红绿灯状态
            threadRadarStatus = Thread(target=self.get_traffic_light_status, args=[])
            threadRadarStatus.start()

            # 每分钟同步设备状态
            threadSyncStatus = Thread(target=self.sync_status_thread,args=[])
            threadSyncStatus.start()

    def socket_process(self,addr):
               
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(addr)
            crosslogger.info("雷达 socket connection success,ip:%s"%addr[0])
        except:
            self.socketMap[addr] = None
            close_flag = self.socketClosedMap.get(addr)
            if close_flag == 1:
                del self.socketClosedMap[addr]
                return
            crosslogger.info("雷达 socket connection failed,ip:%s"%addr[0])
            reconnect_thread = Timer(interval=30,function=self.socket_process,args=[addr])
            reconnect_thread.start()
            return

        devItem = self.deviceMap.get(addr)
    #    crosslogger.info("--self.deviceMap:%s;\n"%self.deviceMap)
        crosslogger.info("开始设置雷达参数:(速度 :%s,检测距离:%s,抗干扰：%s,方向:%s,补偿角度:%s)"%(devItem['speed'],devItem['distance'],devItem['antijam'],devItem['direction'],devItem['angle']))
        set_radar(s,devItem['speed'],devItem['distance'],devItem['antijam'],devItem['direction'],devItem['angle'])  #初始化设置雷达参数
        crosslogger.info("485设备socket-增加连接:(%s,%s)"%(addr[0],addr[1]))
        self.socketMap[addr] = s

        msg_cache = ""
        while True:
            try:
                #查询状态的间隔为50s，所以超时时间设为60s
                s.settimeout(60)  
                data = s.recv(50)               
                msg = data.decode('utf-8')

                msg_cache += msg
                msg_cache,recv_msg = radar_msg_cache(msg_cache)
                recv_msg = json.loads(recv_msg) if recv_msg else None
            except Exception as e:
                close_flag = self.socketClosedMap.get(addr)
                if close_flag == 1:
                    del self.socketClosedMap[addr]
                    return
                reconnect_thread = Timer(interval=20,function=self.socket_process,args=[addr])
                reconnect_thread.start()
                crosslogger.exception(e)
                break
            
            result = self.deal_msg(recv_msg,devItem)

    def get_all_task(self):
        
        self.close_all_socket()

        config_col = self.my_db.get_col("traffic_light_config")
        project_col = self.my_db.get_col("traffic_light_project")
        ruler_col = self.my_db.get_col("traffic_light_ruler")

        config_items = config_col.find({}, {'_id': 0})
        ruler_item = ruler_col.find_one({}, {'_id': 0})

        taskListAudio = []
        radarTaskList = []
        addr_set = set()
        self.deviceMap = {}
        self.radarStatusMap = {} #雷达状态
        self.soundStatusMap = {} #声光告警器状态
        self.lightStatusMap = {}
        self.lightDirectionMap = {}

        if config_items.count() == 0:
            return
        
        project_item = project_col.find_one()
        if not project_item:
            return
        
        crossroad_no = project_item.get('crossroad_no')     #路口编号
        crossroad_type = project_item.get('crossroad_type') #路口类型
        voice_horn = project_item.get('voice_horn')         #路口绑定的喇叭

        self.mainRuler = ruler_item
        self.mainRuler['crossroad_type'] = crossroad_type

        self.lightRuler = convert_road_ruler(ruler_item)

        for item in config_items:

            traffic_light = item.get('traffic_light')
            direction = item.get('direction')
            radar_ip = item.get('radar_ip')
            config_id = item.get('config_id')
            project_id = item.get('project_id')
            camera_id = item.get('camera_id')

            self.camDirectionMap[direction] = camera_id
 
            if traffic_light and '#' in traffic_light:
                list_a = traffic_light.split('#')
                ip_a = list_a[0]
                port_a = list_a[1]
                if len(list_a) >= 3:
                    device_addr = list_a[2]
                else:
                    device_addr = None

                addr_a = (ip_a,int(port_a))
                if addr_a not in addr_set:
                    addr_set.add(addr_a)
                    newItem= {'addr':addr_a,
                              'road_direction':item.get('direction'),
                              'crossroad_no':crossroad_no,
                              'device_addr':device_addr,
                              'config_id':config_id}
                    
                    status_before = item.get('traffic_light_status')
                    self.soundStatusMap[addr_a] = status_before
                    taskListAudio.append(newItem)
                    self.deviceMap[addr_a] = newItem
                    self.lightDirectionMap[direction] = addr_a


            if  radar_ip and '#' in radar_ip:
                list_radar_b = radar_ip.split('#')
                ip_b = list_radar_b[0]
                port_b = list_radar_b[1]
                addr_b = (ip_b,int(port_b))
                if addr_b not in addr_set:
                    addr_set.add(addr_b)
                    radar_test_direction = item.get('radar_test_direction') # 方向
                    radar_speed_threshold = item.get('radar_speed_threshold')
                    radar_anti_jam = item.get('radar_anti_jam')
                    radar_angle = item.get('radar_angle')
                    radar_sensitivity = item.get('radar_sensitivity')
                    status_before = item.get('radar_status')

                    newItem= {'addr':addr_b,
                              'crossroad_no':crossroad_no,
                              'road_direction':direction,
                              'speed':radar_speed_threshold,
                              'distance':5,'antijam':radar_anti_jam,
                              'angle':radar_angle,
                              'sensitivity':radar_sensitivity,
                              'project_id':project_id,
                              'direction':radar_test_direction,
                              'config_id':config_id}
                    self.radarStatusMap[addr_b] = status_before
                    radarTaskList.append(newItem)
                    self.deviceMap[addr_b] = newItem

        self.taskRadar = radarTaskList
        self.taskListAudio = taskListAudio
       
        crosslogger.info("重新拉取交通灯;\n light_task:%s"%taskListAudio)
        crosslogger.info("重新拉取雷达设备;\n radar_task:%s"%radarTaskList)

        # # 初始化声光告警器,发送一个停止播放的指令
        # init_audio_thread = Thread(target=self.init_all_audio,args=[])
        # init_audio_thread.start()

        addrList = []
        for item in radarTaskList:
            addr = item.get('addr')
            if addr in addrList:
                continue
            addrList.append(addr)
            serial_thread = Thread(target=self.socket_process,args=[addr])
            serial_thread.start()

    def get_work_model(self):
        col = self.my_db.get_col("authority_work_model")
        item = col.find_one()
        mode = item.get('model','0')
        if mode == 0:
            return mode,None
        
        serviceAddress = item.get('service_address')
        servicePort = item.get('service_port')
        url = "http://" + serviceAddress + ":" + servicePort
        return mode,url

    def deal_msg(self,msg:dict,dev:dict):
        '''
        处理雷达回过来的消息
        '''
        if not msg :
            return
        
        addr = dev.get('addr')
        ip = addr[0]
        status_key = "dynamicstatus:" + ip
        self.rePool.setex(status_key,60,'0')
    
        if not self.ruleNow:
            return
        
        if "Radar_1ch_speed" in msg.keys():
            radar_speed = msg.get('Radar_1ch_speed')[-1]
            if radar_speed > 0:
                road_direction = dev.get('road_direction')
                
                crossroad_no = dev.get('crossroad_no')
                crosslogger.info("--(%s)RecvRadar msg:%s;"%(ip,msg))
                crosslogger.info("雷达(%s)产生超速告警-速度:%s, 方向:%s, 路口编号:%s;\n"%(ip,radar_speed,road_direction,crossroad_no))

                control_type = self.ruleNow.get('controlType')
                redis_key = "radarEmergency:" + road_direction
                if self.rePool.exists(redis_key) or control_type != '3':
                    return
                
                radar_keys_list = redis_fuzzy_query(self.rePool,keyword='radarEmergency')
                self.rePool.setex(redis_key,10,value='1')

                emergency_keys_list = redis_fuzzy_query(self.rePool,keyword='crossEmergency')
                except_key = 'crossEmergency:' + road_direction
                if except_key in emergency_keys_list:
                    emergency_keys_list.remove(except_key)

                if not radar_keys_list and not emergency_keys_list:
                    #单向来车，并且无人的情形
                    crosslogger.info("**********当前路口状态: 路口无人,来车方向-%s**********\n"%road_direction)
                    self.control_normal(self.ruleNow,road_direction)
                elif radar_keys_list and not emergency_keys_list:
                    #多方向来车，无人通过马路的情形
                    crosslogger.info("**********当前路口状态: 路口无人,多方向来车**********\n")
                    early_direction = get_min_expire_time(self.rePool,radar_keys_list)
                    early_direction = early_direction.split(":")[-1]
                    self.control_single_direction_recovery(self.ruleNow,pass_direction = early_direction)
                elif not radar_keys_list and emergency_keys_list:
                    #单向来车，有人通过马路
                    crosslogger.info("**********当前路口状态: 路口有人,单向来车-%s**********\n"%road_direction)
                    self.control_with_pedestrian(self.ruleNow,road_direction)
                else:
                    #多方向来车，且有人通过马路
                    crosslogger.info("**********当前路口状态: 路口有人,多方向来车**********\n")
                    radar_keys_list.append(redis_key)
                    for radar_key in radar_keys_list:
                        dire = radar_key.split(":")[-1]
                        self.control_with_pedestrian(self.ruleNow,dire)

        return
    
    def deal_alg_emergency(self,camera_id):
        '''
        当摄像头识别到人时，触发
        '''
        road_direction = get_key_by_value(self.camDirectionMap,value=camera_id)
        redis_key = "radarEmergency:" + road_direction
        radar_keys_list = redis_fuzzy_query(self.rePool,keyword='radarEmergency')

        if redis_key in radar_keys_list:
            #与行人同方向的车辆不受影响
            radar_keys_list.remove(redis_key)

        if not radar_keys_list:
            #路口有人通行，但是无车
            return
        
        for radar_key in radar_keys_list:
            direction = radar_key.split(':')[-1]
            self.control_with_pedestrian(self.ruleNow,direction)
        return
        
    def close_all_socket(self):
         
        closedList = self.socketMap.keys()
        self.socketClosedMap = {}
        for addr in closedList:
            try:
                s = self.socketMap.get(addr)
                self.socketClosedMap[addr] = 1
                if not s:
                    continue
                s.close()
                
            except Exception as e:
                crosslogger.exception(e)  

        self.socketMap = {}
        self.taskListAudio = []
        self.taskRadar = [] 

    def send_and_recv_close(self,socketClient,cmd,addr):
        try:
            crccode = calculate_crc16(cmd)
            cmd_all = cmd + bytes.fromhex(crccode)
            socketClient.send(cmd_all)
            socketClient.settimeout(0.2)
            recv_data = socketClient.recv(8)
            recv_data_str = byte2str(recv_data)

            if recv_data_str[2:4] != "10":
                self.send_and_recv_close(socketClient,cmd,addr)

        except socket.timeout:
            crosslogger.info("--(%s)接收超时---------------"%addr[0])
            self.send_and_recv_close(socketClient,cmd,addr)

        except Exception as e:
            crosslogger.exception(e)

    def send_and_recv(self,socketClient,cmd,addr):
        try:
            crccode = calculate_crc16(cmd)
            cmd_all = cmd + bytes.fromhex(crccode)
            socketClient.send(cmd_all)
            str_cmd = byte2str(cmd_all)
            socketClient.settimeout(0.2)
            recv_data = socketClient.recv(8)
            recv_data_str = byte2str(recv_data)

            if recv_data_str[2:4] == "04":
                #交通灯在线
                status_before = self.soundStatusMap.get(addr)
                redis_key = 'dynamicstatus:' + addr[0]
                flag = self.rePool.get(name=redis_key)
                if not flag or status_before == 1:
                    item = self.deviceMap.get(addr)
                    config_id = item.get('config_id')
                    self.soundStatusMap[addr] = 0
                    self.my_db.update('traffic_light_config',
                                      {'config_id':config_id},
                                      {'$set':{'traffic_light_status':0}})
                self.rePool.setex(redis_key,60,value='0')
            elif  recv_data_str != str_cmd:
                self.send_and_recv(socketClient,cmd,addr)

        except socket.timeout:

            crosslogger.info("--(%s)接收超时---------------"%addr[0])
            self.send_and_recv(socketClient,cmd,addr)

        except Exception as e:
            cmd_str = byte2str(cmd)
            if cmd_str[2:4] == '04':
                status_before = self.soundStatusMap.get(addr)
                redis_key = 'dynamicstatus:' + addr[0] 
                if  self.rePool.get(name=redis_key) or status_before == 0:
                    item = self.deviceMap.get(addr)
                    config_id = item.get('config_id')
                    self.soundStatusMap[addr] = 1
                    self.my_db.update('traffic_light_config',
                                      {'config_id':config_id},
                                      {'$set':{'traffic_light_status':1}})
            crosslogger.exception(e)

    def close_output(self,byte_addr,socketClient,addr):
        try:
            # 三路先切换回正常模式
            bytecode_3 = byte_addr + b'\x10\x00\x96\x00\x03\x06\x00\x00\x00\x00\x00\x00' 
            self.send_and_recv_close(socketClient,bytecode_3,addr)    

            # 关闭所有输出
            bytecode_stop = byte_addr + b'\x06\x00\x34\x00\x00'
            self.send_and_recv(socketClient,bytecode_stop,addr)

        except socket.TimeoutError:
            #捕获超时错误，开启重试进程
            retry_thread = Thread(target=self.close_output,args=[byte_addr,socketClient,addr])
            retry_thread.start()

        except Exception as e:
            crosslogger.exception(e)

    def close_output_separated(self,byte_addr,socketClient,addr):
        try:
            # 三路先切换回正常模式
            # 第一路
            bytecode_1 = byte_addr + b'\x06\x00\x96\x00\x00' 
            self.send_and_recv(socketClient,bytecode_1,addr)

            #第二路
            bytecode_2 = byte_addr + b'\x06\x00\x97\x00\x00' 
            self.send_and_recv(socketClient,bytecode_2,addr)

            # 第三路
            bytecode_3 = byte_addr + b'\x06\x00\x98\x00\x00' 
            self.send_and_recv(socketClient,bytecode_3,addr)    

            # 关闭所有输出
            bytecode_stop = byte_addr + b'\x06\x00\x34\x00\x00'
            self.send_and_recv(socketClient,bytecode_stop,addr)

            # 禁止输出
            bytecode_forbid = byte_addr + b'\x06\x00\x35\x00\x00'
            self.send_and_recv(socketClient,bytecode_forbid,addr)

        except socket.TimeoutError:
            #捕获超时错误，开启重试进程
            retry_thread = Thread(target=self.close_output,args=[byte_addr,socketClient,addr])
            retry_thread.start()

        except Exception as e:
            dynamiclogger.exception(e)

    def get_audio_status(self):

        for item in self.taskListAudio:
            addr = item.get('addr')
            device_addr = item.get('device_addr')
          
            if addr in self.socketMap.keys():
                socketClient = self.socketMap.get(addr)
            else:
                socketClient = None

            try:
                if not socketClient:
                    socketClient = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    socketClient.connect(addr)
                    dynamiclogger.info('交通灯 socket connection success:ip:%s'%addr[0])
            except:
                dynamiclogger.info('交通灯 socket connection failed:ip:%s'%addr[0])
                socketClient = None
            self.socketMap[addr] = socketClient
            
            macAddr = int2hex(device_addr)
            bytedata = bytes.fromhex(macAddr) + b'\x04\x00\x00\x00\x01'   
            self.send_and_recv(socketClient,bytedata,addr)

        instance_timer = Timer(interval = 50,function=self.get_audio_status,args=[])
        instance_timer.start()

    def get_radar_status(self):
        # 维护雷达的状态
        for item in self.taskRadar:
            
            addr = item.get('addr')
            ip = addr[0]

            redis_key = "dynamicstatus:" + ip
            flag = self.rePool.exists(redis_key)
            status = self.radarStatusMap.get(addr)
            config_id = item.get('config_id')

            if not flag and status == 0:
                self.radarStatusMap[addr] = 1
                self.my_db.update('traffic_light_config',
                                    {'config_id':config_id},
                                    {'$set':{'radar_status':1}})
            elif flag and status == 1:
                self.radarStatusMap[addr] = 0
                self.my_db.update('traffic_light_config',
                                    {'config_id':config_id},
                                    {'$set':{'radar_status':0}})

                      
                    
        instance_timer = Timer(interval = 50,function=self.get_radar_status,args=[])
        instance_timer.start()

    def get_traffic_light_status(self):
        # 维护交通灯的状态
        for item in self.taskListAudio:

            addr = item.get('addr')
            ip = addr[0]

            redis_key = "dynamicstatus:" + ip
            flag = self.rePool.exists(redis_key)
            status = self.soundStatusMap.get(addr)
            config_id = item.get('config_id')

            if not flag and status == 0:
                self.soundStatusMap[addr] = 1
                self.my_db.update('traffic_light_config',
                                  {'config_id': config_id},
                                  {'$set': {'traffic_light_status': 1}})
            elif flag and status == 1:
                self.soundStatusMap[addr] = 0
                self.my_db.update('traffic_light_config',
                                  {'config_id': config_id},
                                  {'$set': {'traffic_light_status': 0}})

        instance_timer = Timer(interval=50, function=self.get_traffic_light_status, args=[])
        instance_timer.start()

    def crossing_control(self):
        week_now = str(get_current_weekday())
        ruler_today = self.lightRuler.get(week_now)
        ruler_now = get_ruler_now(ruler_today)
        road_type = self.mainRuler.get('crossroad_type')
        control_type = ruler_now.get('controlType') if ruler_now else None
        interval_time = 60 #默认定时60秒
        last_control_type = self.ruleNow.get('controlType') #上次轮询的控制模式
        self.ruleNow = ruler_now
        crosslogger.info("--今天的红绿灯规则: %s;\n"%ruler_now)

        if not ruler_now:
            #当前无红绿灯规则，则灯保持黄灯闪烁
            control_thread = Thread(target=self.control_idle_time,args=[])
            control_thread.start()
            interval_time = 60

        elif control_type == '1':
            #混合放行
            control_thread = Thread(target=self.control_mixed_direction,args=[ruler_now])
            control_thread.start()
            timeGroup1 = ruler_now.get('timeGroup1')
            interval_time = sum(timeGroup1.values())

        elif control_type == '2':
            #单向放行
            control_thread = Thread(target=self.control_single_direction,args=[ruler_now])
            control_thread.start()
            timeGroup1 = ruler_now.get('timeGroup1')
            interval_time = sum(timeGroup1.values())

        elif last_control_type != '3':
            #从其他模式切换到智能通行
            control_thread = Thread(target=self.control_idle_time,args=[])
            control_thread.start()
            interval_time = 60
            
        next_control_timer = Timer(interval=interval_time,function=self.crossing_control,args=[])
        next_control_timer.start()
    
    def control_idle_time(self):
        '''
        #### Rule: 当前无规则时,方向1保持黄灯闪烁,其他方向不亮
        '''        
        for key,value in self.lightDirectionMap.items():
            device_item = self.deviceMap.get(value)
            deviceAddr = device_item.get('device_addr')
            version = self.lightOrderMap.get(value,0) + 1
            self.lightOrderMap[value] = version

            if key == '1':
                task_item = {   'color':2,  #黄灯
                                'mode':0,  #爆闪
                                'resetTime':0,
                                'times':2,
                                'deviceAddr':deviceAddr,
                                'version':version}
            else:
                task_item = {'deviceAddr':deviceAddr,
                             'version':version,
                             'stopFlag':1}
            
            light_thread = Thread(target=self.control_light,args=[value,task_item])
            light_thread.start()
        return


    def control_single_direction_recovery(self,ruler_now,pass_direction='1'):
        '''
        单向放行控制路口交通灯，
        最后恢复到一个方向黄闪的状态
        '''        
        relationMap = {'1':'timeGroup1', '2':'timeGroup2' ,'3':'timeGroup3' ,'4':'timeGroup4'}
        crossing_num = len(self.lightDirectionMap.values())  #路口的数量

        greenLightTime = ruler_now.get("greenLightTime")
        yellowLightTime = ruler_now.get("yellowLightTime")

        dire_pass = int(pass_direction)
        wait_time = 0
        order_default = [0,2,1]

        for i in range(dire_pass,dire_pass+crossing_num):
            dire = i % crossing_num  #实际方向
            if dire == 0:
                dire = crossing_num 

            dire_str = str(dire) if dire != 0 else str(crossing_num)
            timekey = relationMap.get(dire_str)
            timeGroup = ruler_now.get(timekey)

            addr = self.lightDirectionMap.get(dire_str)
            device_item = self.deviceMap.get(addr)
            crosslogger.info("--------dire_str:%s,addr:%s;\n"%(dire_str,addr))
            deviceAddr = device_item.get('device_addr')

            if dire == dire_pass:
                #通行方向： 绿-黄-红
                if dire == 1:
                    order = [0,2,1,2] 
                    timeset = [timeGroup['green'],timeGroup['yellow'],timeGroup['red'],0]    
                else:
                    order = [0,2,1]
                    timeset = [timeGroup['green'],timeGroup['yellow'],timeGroup['red']] 

                task_item = {'color':0,
                             'mode':1,
                             'resetTime':timeGroup.get('green'),
                             'deviceAddr':deviceAddr,
                             'round':0,
                             'order':order,
                             'timeset':timeset}
                
            else:
                #非通行方向： 红-绿-黄-红  
                if timeGroup['red'] == wait_time:
                    order = [1,0,2]
                    timeset = [wait_time,timeGroup['green'],0] 
                    timeset[-1] = 0 if dire == 1 else timeGroup['yellow']
                elif dire == 1:
                    order = [1,0,2,1,2]
                    timeset = [wait_time,timeGroup['green'],timeGroup['yellow'],timeGroup['red']-wait_time,0] 
                else:
                    order = [1,0,2,1]
                    timeset = [wait_time,timeGroup['green'],timeGroup['yellow'],timeGroup['red']-wait_time] 
            
                task_item = {'color':1,'mode':1,'resetTime':wait_time,'deviceAddr':deviceAddr,
                            'round':0,'order':order ,'timeset':timeset}
               
            version = self.lightOrderMap.get(addr,0) +1 
            self.lightOrderMap[addr] = version 
            task_item['version'] = version

            sub_thread = Thread(target=self.control_light,args=[addr,task_item])
            sub_thread.start()

            wait_time += (yellowLightTime + greenLightTime.get(dire_str))  
        return

    def control_single_direction(self,ruler_now,pass_direction='1'):
        '''
        #### 单向放行控制路口交通灯
             最后不恢复状态
        '''        
        relationMap = {'1':'timeGroup1', '2':'timeGroup2' ,'3':'timeGroup3' ,'4':'timeGroup4'}
        crossing_num = len(self.lightDirectionMap.values())

        greenLightTime = ruler_now.get("greenLightTime")
        yellowLightTime = ruler_now.get("yellowLightTime")

        dire_pass = int(pass_direction)
        wait_time = 0
        order_default = [0,2,1]

        for i in range(dire_pass,dire_pass+crossing_num):
            dire = i % crossing_num  #实际方向
            if dire == 0:
                dire = crossing_num 

            dire_str = str(dire) if dire != 0 else str(crossing_num)
            timekey = relationMap.get(dire_str)
            timeGroup = ruler_now.get(timekey)

            addr = self.lightDirectionMap.get(dire_str)
            if not addr:
                crosslogger.info("---error:未找到设备,lightDirectionMap:%s;\n"%self.lightDirectionMap)
                continue
            device_item = self.deviceMap.get(addr)
            deviceAddr = device_item.get('device_addr')

            if dire == dire_pass:
                #通行方向： 绿-黄-红               
                order = order_default
                timeset = [timeGroup['green'],timeGroup['yellow'],0] 

                task_item = {'color':0,
                             'mode':1,
                             'resetTime':timeGroup.get('green'),
                             'deviceAddr':deviceAddr,
                             'round':0,
                             'order':order,
                             'timeset':timeset}
                
            else:
                #非通行方向： 红-绿-黄-红               
                order = [1,0,2,1]
                timeset = [wait_time,timeGroup['green'],timeGroup['yellow'],0] 
            
                task_item = {'color':1,'mode':1,'resetTime':wait_time,'deviceAddr':deviceAddr,
                            'round':0,'order':order ,'timeset':timeset}
                
            version = self.lightOrderMap.get(addr,0) +1 
            self.lightOrderMap[addr] = version 
            task_item['version'] = version

            sub_thread = Thread(target=self.control_light,args=[addr,task_item])
            sub_thread.start()

            wait_time += (yellowLightTime + greenLightTime.get(dire_str))  
        return


    def control_mixed_direction(self,ruler_now):
        # 混合放行模式
        crosslogger.info("--模式：混合放行模式")
        directionGroup = ruler_now.get('direction') #方向分组
        for key,value in self.lightDirectionMap.items():
            device_item = self.deviceMap.get(value)
            deviceAddr = device_item.get('device_addr')
            addr = self.lightDirectionMap.get(key)

            timeGroup1 = ruler_now.get('timeGroup1')
            timeGroup2 = ruler_now.get('timeGroup2')
            if key in   directionGroup:
                
                color = 1
                timeset = [timeGroup1['red'],timeGroup1['green'],0]
                task_item = {'color':color,
                             'mode':1,
                             'resetTime':timeset[0],
                             'deviceAddr':deviceAddr,
                             'round':0,
                             'timeset':timeset,
                             'order':[1,0,2]}
            else:
                timeset = [timeGroup2['green'],timeGroup2['yellow'],0]
                color = 0
                task_item = {'color':color,
                             'mode':1,
                             'resetTime':timeset[0],
                             'deviceAddr':deviceAddr,
                             'round':0,
                             'timeset':timeset,
                             'order':[0,2,1]}
            version = self.lightOrderMap.get(value,0) + 1
            self.lightOrderMap[value] = version
            task_item['version'] = version

            light_thread = Thread(target=self.control_light,args=[addr,task_item])
            light_thread.start()

        return
    
    def control_normal(self,ruler_now,direction):
        '''
        单向来车,无人的情形；
        '''
        addr = self.lightDirectionMap.get(direction)
        device_item = self.deviceMap.get(addr)
        deviceAddr = device_item.get('device_addr')
        vehicleTrafficTime = ruler_now.get('vehicleTrafficTime')
        yellow_light_time = ruler_now.get('yellowLightTime')

        timeset = {'green':vehicleTrafficTime,
                    'yellow':yellow_light_time,
                    'red':vehicleTrafficTime+yellow_light_time}
        task_item = {'color':0,
                     'mode':1,
                     'resetTime':vehicleTrafficTime,
                     'deviceAddr':deviceAddr,
                     'timeset':timeset,
                     'round':0}
        if direction == '1':
            task_item['order'] = [0,2]
            task_item['timeset'] = [timeset['green'],0]
        else:
            task_item['order'] = [0,2]
            task_item['timeset'] = [timeset['green'],timeset['yellow']]

        version = self.lightOrderMap.get(addr,0) +1 
        self.lightOrderMap[addr] = version 
        task_item['version'] = version
        
        light_thread = Thread(target=self.control_light,args=[addr,task_item])
        light_thread.start()

        for key,value in self.lightDirectionMap.items():
            if key == direction:
                continue
            task_item = {'color':1,
                         'mode':1,
                         'resetTime':timeset['red'],
                         'deviceAddr':deviceAddr,
                         'timeset':timeset,
                         'order':[1],
                         'round':0}
            
            if key == '1':
                task_item['order'] = [1,2]
                task_item['timeset'] = [timeset['red'],0]
            else:
                task_item['order'] = [1]
                task_item['timeset'] = [timeset['red']]

            addr_dire = self.lightDirectionMap.get(key)

            version = self.lightOrderMap.get(addr_dire,0) + 1
            self.lightOrderMap[addr_dire] = version
            task_item['version'] = version

            otherlight_thread = Thread(target=self.control_light,args=[value,task_item])
            otherlight_thread.start()

        crosslogger.info("--路口红绿灯亮灯顺序：%s;\n"%self.lightOrderMap)
        return
    
    def control_with_pedestrian(self,ruler_now,direction):
        '''
        来车,且其他方向有人通行
        '''
        addr = self.lightDirectionMap.get(direction)
        device_item = self.deviceMap.get(addr)
        deviceAddr = device_item.get('device_addr')
        pedestrianTrafficTime = ruler_now.get('pedestrianTrafficTime')

        timeset = [pedestrianTrafficTime]
        task_item = {'color':2,'mode':0,'resetTime':pedestrianTrafficTime,
                     'deviceAddr':deviceAddr,'timeset':timeset,'order':[2],'round':0}
        light_thread = Thread(target=self.control_light,args=[addr,task_item])
        light_thread.start()

    def control_light(self,addr,item):
        socketClient = self.socketMap.get(addr)
        if not socketClient:
            try:
                socketClient = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                socketClient.connect(addr)
            except:
                crosslogger.info('交通灯 connection failed: ip:%s'%addr[0])
                stopFlag = item.get("stopFlag")  # 是否停止播放
                stopTimes = item.get("stopTimes",0)
                if stopFlag == 1 and stopTimes <= 3:
                    crosslogger.info('--交通灯停止失败,3s后第%s次重试!'%(stopTimes+1))
                    item['stopTimes'] = stopTimes + 1
                    retry_thread = Timer(function=self.control_light,interval=3,args=[addr,item])
                    retry_thread.start()
                return
        
        if not socketClient:
            return
        
        version = item.get('version')
        now_version = self.lightOrderMap.get(addr)
        if version != now_version:
            return
        
        deviceAddr = item.get("deviceAddr")
        macAddr = int2hex(deviceAddr)
        byte_addr = bytes.fromhex(macAddr)
        stopFlag = item.get("stopFlag")  # 是否停止播放

        if stopFlag == 1:
            # stopFlag == 1 表示停止告警
            self.close_output(byte_addr,socketClient,addr)
        else:
            color = item.get("color")        # 灯光控制  0:绿灯  1：红灯  2：黄灯  3:熄灭
            mode =  item.get("mode")         # 闪烁方式  0:爆闪  1：常亮  2：闪烁
            resetTime = item.get("resetTime") #报警时间
            #先关闭所有输出
            self.close_output(byte_addr,socketClient,addr)

            if color == 3:
                return
            
            lightbit = lightColorMap.get(color)
            bytecode_setmode = byte_addr + b'\x06\x00' + lightbit + b'\x00\x00'

            try:
                if mode == 1:
                    # 设置对应通道为普通模式
                    self.send_and_recv(socketClient,bytecode_setmode,addr)
                    chanelbit = chanelMap.get(color)
                    lightcode = byte_addr + b'\x06\x00' + chanelbit + b'\x00\x01'
                    self.send_and_recv(socketClient,lightcode,addr)

                else:
                    # 设置对应通道为循环开关模式
                    bytecode_setmode = byte_addr + b'\x06\x00' + lightbit + b'\x00\x03'
                    self.send_and_recv(socketClient,bytecode_setmode,addr)

                    flashingbit = b'\x97' if mode == 2 else b'\x15'
                    chanelbit = chanelMap.get(color)
                    lightcode = byte_addr + b'\x06\x00'+ chanelbit +b'\x00' + flashingbit
                    self.send_and_recv(socketClient,lightcode,addr)

            except Exception as e:
                crosslogger.exception(e)

        if stopFlag != 1 and resetTime != 0:
            order = item.get('order')         
            round = item.get('round')

            if round + 1 > len(order):
                return
            elif round + 1 == len(order):
                task_item = {
                             'deviceAddr':deviceAddr,
                             'stopFlag':1,
                             'order':order,
                             'version':version
                            }
            else:
                color_now = order[round+1]
                timeset = item.get('timeset')
                mode_new = 0 if color_now == 2 else 1

                resetTimeNew = timeset[round+1]
                task_item = {'color':color_now,
                            'mode':mode_new,
                            'resetTime':resetTimeNew,
                            'order':order,
                            'deviceAddr':deviceAddr,
                            'round':round+1,
                            'timeset':timeset,
                            'version':version}
            thread_queue = Timer(resetTime, function=self.control_light, args=[addr, task_item])
            thread_queue.start()
        return

    def sync_status_thread(self):
        """
        同步路口摄像机、雷达和声光告警器的状态
        """
        mode,url = self.get_work_model()
        if mode == "1":
            config_col = self.my_db.get_col('traffic_light_config')
            crossroadNo = self.my_db.get_col('traffic_light_project').find_one()['crossroad_no']
            config_items = config_col.find()   
            statusList = []  
            project_id =  None      
            for config_item in config_items:
                project_id = config_item.get('project_id')
                radarStatus = config_item.get('radar_status')
                trafficLightStatus = config_item.get('traffic_light_status')

                newItem = {}
                newItem['id'] = config_item.get('config_id')
                newItem['radarStatus'] = radarStatus if radarStatus != None else 1
                newItem['trafficLightStatus'] = trafficLightStatus if trafficLightStatus != None else 1
                statusList.append(newItem)

            content= {"crossroadNo": crossroadNo,
                    "deviceStatusVoList": statusList}
            resp = sync_cross_status(url,content)

            if resp.get('code') != 200:
                crosslogger.info("同步弯道设备状态 error:%s;\n入参:%s\n"%(resp,content))
            else:
                crosslogger.info("同步弯道设备状态 :%s\n"%resp)
        status_thread = Timer(60,function=self.sync_status_thread, args=[])
        status_thread.start()

def sync_cross_status(url,content):
    # 同步弯道告警到平台
    try:
        url = url + SYN_CROSSROAD_STATUS
        headers = {'Content-Type': 'application/json'}
        answer = requests.post(url,data=json.dumps(content),headers=headers,verify=False)
        return answer.json()
    except Exception as e:
        answer = {'error':'%s'%e}
        return answer
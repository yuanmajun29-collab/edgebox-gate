import socket
import serial
import json
import uuid
import time
import requests
import subprocess
from datetime import datetime,timedelta
from threading import Timer,Thread
import  Utils.logger as logger
from Utils.db import ToMongo
from algorith_server.redis_connect import redis_database

SYN_CURVE_STATUS = "/business/syn/synCurveDeviceStatus" #同步弯道设备状态
SYN_CURVE_EMERGENCY = "/business/syn/synCurveEmergencyRecord" #同步弯道告警记录

dynamiclogger = logger.getLogger("dynamic")


# 声光告警器不同控制方式对应的字节
lightMap = {1:b'\x13',2:b'\x23',3:b'\x33',
            4:b'\x11',5:b'\x21',6:b'\x31',
            7:b'\x12',8:b'\x22',9:b'\x32',
            10:b'\x60'}

voiceLengthMap = {1:2.473,  #前方来车，请减速慢行
                  2:2.334,  #注意行人，请减速慢行
                  3:1.961, #前方事故，请注意
                  4:2.483, #前方事故，请减速慢行
                  5:1.985, #前方落石，请注意
                  6:2.435, #摄像头被遮挡，请处理
                  7:2.404} #雨雾天气，请减速慢行

def int2hex(n):
    """
    int类型地址码转16进制字符串
    """
    if type(n) == str:
        n = int(n)
    return hex(n)[2:] if n >= 16 else '0{:X}'.format(n)

def execShell(cmd):
    err,result = subprocess.getstatusoutput(cmd)
    return err,result

def byte2str(data: bytes):
    """
    字节转16进制字符串
    example: b"\81\1b" --> "811b"
    """
    res = []
    for byte in data:
        if byte < 16:
            res.append('0' + hex(byte)[2:])
        else:
            res.append(hex(byte)[2:])
    result = ''.join(res)
    return result

# CRC-16-MODBUS
def calculate_crc16(data: bytes) -> str:
    """
    计算crc-16 modbus 校验码；
    """
    # 初始化crc为0xFFFF
    crc = 0xFFFF
    # 循环处理每个数据字节
    for byte in data:
        # 将每个数据字节与crc进行异或操作
        crc ^= byte
        # 对crc的每一位进行处理
        for _ in range(8):
            # 如果最低位为1，则右移一位并执行异或0xA001操作(即0x8005按位颠倒后的结果)
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            # 如果最低位为0，则仅将crc右移一位
            else:
                crc = crc >> 1
    number = ((crc & 0xff) << 8) + (crc >> 8)
    result = '%04X'%(number)
    # 返回最终的crc值
    return result

def send485message_old(item):
    '''
    发送485声光告警器告警
    '''
    try:
        ip = item.get('equip_ip')
        port = item.get('equip_port')
        stop_flag = item.get('stop_flag')
        addr = (ip,int(port))
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(addr)

        deviceAddr = item.get("device_addr")
        macAddr = int2hex(deviceAddr)
        byte_addr = bytes.fromhex(macAddr)

        if stop_flag == 1:
            # 发送声光告警停止指令
            bytecode = byte_addr + b'\x06\x00\x16\x00\x01'        
            crccode = calculate_crc16(bytecode)
            bytecode = bytecode + bytes.fromhex(crccode)
            s.send(bytecode)
            return

        reset_delay_time = item.get("reset_delay_time")
        # reset_delay_time N秒后关闭声光告警器
        reset_delay_time = int(reset_delay_time) if reset_delay_time else 10

        soundType = item.get("sound_alarm")
        # 01 前方来车，请减速慢行   02 注意行人，请减速慢行  03 前方事故，请注意
        # 04 前方事故，请减速慢行   05 前方落石，请注意   06 摄像头被遮挡，请处理  
        # 07 雨雾天气，请减速慢行

        byte_sound_type = bytes.fromhex(soundType)
        bytecode = byte_addr + b'\x06\x40\x08\x00' + byte_sound_type
        crccode = calculate_crc16(bytecode)
        bytecode = bytecode + bytes.fromhex(crccode)

        s.send(bytecode)

        task_item = {'equip_ip': ip,
                     'equip_port': port,
                     'device_addr': deviceAddr,
                     'stop_flag': 1}
        thread_queue = Timer(reset_delay_time, function=send485message, args=[task_item])
        thread_queue.start()
 
    except Exception as e:
        dynamiclogger.info('Error:485声光告警失败,Reason:%s'%e)
    return

def send485message(item):
    '''
    发送485声光告警器告警
    '''
    try:
        ip = item.get('equip_ip')
        port = item.get('equip_port')
        stop_flag = item.get('stop_flag')
        deviceAddr = item.get("device_addr")      
        soundAlarm = item.get("sound_alarm")  # 报警声音
        lightingMethod = item.get("lighting_method")  #灯光控制
        resetDelayTime = item.get("reset_delay_time") #报警时间
        newItem = {'deviceAddr':deviceAddr,
                   'soundAlarm':int(soundAlarm),
                   'lightingMethod':lightingMethod,
                   'resetDelayTime':resetDelayTime,
                   'stopFlag':0,
                   'alarm_type':2}
        addr = (ip,int(port))
        instance = SerialNetServer(context=None)
        instance.alarm_audio(addr,item=newItem)
 
    except Exception as e:
        dynamiclogger.info('Error:485声光告警失败,Reason:%s'%e)
    return

def set_radar_param(socketServer,speed,sensitivity,anti_jam,direction,angle):
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
        dynamiclogger.exception(e)

def sync_emergency(url,content):
    # 同步弯道告警到平台
    try:
        url = url + SYN_CURVE_EMERGENCY
        headers = {'Content-Type': 'application/json'}
        answer = requests.post(url,data=json.dumps(content),headers=headers,verify=False)
        return answer.json()
    except Exception as e:
        answer = None
        return answer
    
def sync_status(url,content):
    # 同步弯道告警到平台
    try:
        url = url + SYN_CURVE_STATUS
        headers = {'Content-Type': 'application/json'}
        answer = requests.post(url,data=json.dumps(content),headers=headers,verify=False)
        return answer.json()
    except Exception as e:
        answer = {'error':'%s'%e}
        return answer
    
def time_judge(powerConfig):
    switchMode = powerConfig.get('switchMode')    
    if switchMode == 1:
        #省电模式关闭
        dynamiclogger.info('--SavingPower Switch : off')
        return False
    
    startTime = powerConfig.get('startTime')
    endTime = powerConfig.get('endTime')            
    time_now_str = datetime.now().strftime("%H:%M")

    flag1 = time_now_str > startTime
    flag2 = time_now_str < endTime
    if startTime <= endTime:
        if flag1 and flag2:
            return True
    else:
        if flag1 or flag2:
            return True
    return False
      
def emergency_judge(db:ToMongo):
    col = db.get_col('odin_business_emergency_record')
    now = datetime.now()
    timepoint = now - timedelta(minutes=5)
    query = {'create_time':{'$gt':timepoint},'model_path':{'$in':['弯道落石','弯道树木','弯道(roi)车','车通道占用']}}
    item = col.find_one(query)
    if item:
        return True 
    else:
        return False

def deal_Interval(time_now:datetime,endTime,interval):
    try:
        endtime_str = time_now.strftime("%Y-%m-%d") + '+' + endTime
        endtime_dt = datetime.strptime(endtime_str,"%Y-%m-%d+%H:%M")
        if time_now > endtime_dt:
            endtime_dt += timedelta(days=1)
        time_interval = int((endtime_dt - time_now).total_seconds())
        time_minutes = time_interval //60
        if time_minutes <= 1:
            result = 0
        else:
            result = min(interval,time_minutes-1)
        dynamiclogger.info("SavingPower MinuteInterval (set:%s ,send:%s)"%(interval,result))
        return result
    except Exception as e:
        dynamiclogger.exception(e)
    return

def get_voice_interval(soundType,timeRange):
    '''
    获取播放文本的时间间隔
    '''
    soundLength = voiceLengthMap.get(soundType)
    if not soundLength:
        return timeRange
    playTimes = timeRange // soundLength
    if playTimes == 0:
        playTimes = 1
    actualTime = playTimes * soundLength
    return actualTime

class SerialNetServer:
    __instance = None
    __flag = False

    def __new__(cls, *args, **kwargs):
        # super().__new__(cls)
        if cls.__instance is None:
            cls.__instance = super().__new__(cls)
        return cls.__instance 
    
    def __init__(self, context):
        if not SerialNetServer.__flag:
            SerialNetServer.__flag = True
            self.context = context

            self.deviceMap = {}

            #声光告警器相关变量
            self.socketMap = {}
            self.taskListAudio = []
            self.taskRadar = [] 
            self.socketClosedMap = {}

            self.radarStatusMap = {} #雷达状态
            self.soundStatusMap = {} #声光告警器状态

            #省电配置
            self.powerSaveConfig = {}
            timer_init = Timer(function=self.saving_power_timer,interval=300,args=[])
            timer_init.start()
           
            self.my_db = ToMongo('wavedevice')         
            self.rePool = redis_database

            self.get_all_task()
            self.socketClosedMap = {}

            # 维护弯道声光告警器状态
            threadAudioStatus = Thread(target=self.get_audio_status,args=[])
            threadAudioStatus.start()

            # 维护弯道雷达状态
            threadRadarStatus = Thread(target=self.get_radar_status,args=[])
            threadRadarStatus.start()

            # 每分钟同步弯道设备状态
            threadSyncStatus = Thread(target=self.sync_status_thread,args=[])
            threadSyncStatus.start()

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

    def socket_process(self,addr):
               
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(addr)
            dynamiclogger.info("雷达 socket connection success,ip:%s"%addr[0])
        except:
            self.socketMap[addr] = None
            close_flag = self.socketClosedMap.get(addr)
            if close_flag == 1:
                del self.socketClosedMap[addr]
                return
            dynamiclogger.info("雷达 socket connection failed,ip:%s"%addr[0])
            reconnect_thread = Timer(interval=30,function=self.socket_process,args=[addr])
            reconnect_thread.start()
            return

        devItem = self.deviceMap.get(addr)
        dynamiclogger.info("开始设置雷达参数:(速度 :%s,检测距离:%s,抗干扰：%s,方向:%s,补偿角度:%s)"%(devItem['speed'],devItem['distance'],devItem['antijam'],devItem['direction'],devItem['angle']))
        set_radar_param(s,devItem['speed'],devItem['distance'],devItem['antijam'],devItem['direction'],devItem['angle'])  #初始化设置雷达参数
        dynamiclogger.info("485设备socket-增加连接:(%s,%s)"%(addr[0],addr[1]))
        self.socketMap[addr] = s

        while True:
            try:
                #查询状态的间隔为50s，所以超时时间设为60s
                s.settimeout(60)  
                data = s.recv(13)               
                msg = byte2str(data)
            except Exception as e:
                close_flag = self.socketClosedMap.get(addr)
                if close_flag == 1:
                    del self.socketClosedMap[addr]
                    return
                reconnect_thread = Timer(interval=20,function=self.socket_process,args=[addr])
                reconnect_thread.start()
                dynamiclogger.exception(e)
                break
            
            result = self.deal_msg(msg,devItem)

    def get_all_task(self):
        
        self.close_all_socket()

        corner_col = self.my_db.get_col("corner_overtaking_config")
        project_col = self.my_db.get_col("corner_overtaking_project")

        corner_items = corner_col.find({}, {'_id': 0})
        taskListAudio = []
        radarTaskList = []
        addr_set = set()
        self.deviceMap = {}
        self.radarStatusMap = {} #雷达状态
        self.soundStatusMap = {} #声光告警器状态
        if corner_items.count() == 0:
            return
        
        project_item = project_col.find_one()
        if not project_item:
            return
        curve_no = project_item.get('curve_no')   #弯道编号
        power_config = project_item.get('power_saving_mode') #省电配置

        if not power_config:
            self.powerSaveConfig = {}
        else:
            self.powerSaveConfig = json.loads(power_config)
        dynamiclogger.info('--SavingPower PowerConfig init:%s'%self.powerSaveConfig)

        for item in corner_items:
            sound = item.get('sound_light_alarm_ip')
            radar = item.get('radar_ip')
            direction = item.get('direction') #方向 A or B
            project_id = item.get('project_id') #弯道id
            config_id = item.get('config_id') #弯道配置id

            query = {'project_id':project_id}
            radar_warning_status = project_item.get('radar_warning_status')  #雷达预警状态     

            if sound and '#' in sound:
                list_a = sound.split('#')
                ip_a = list_a[0]
                port_a = list_a[1]
                if len(list_a) >= 3:
                    device_addr = list_a[2]
                else:
                    device_addr = None
                addr_a = (ip_a,int(port_a))
                if addr_a not in addr_set:
                    addr_set.add(addr_a)
                    newItem= {'ip':ip_a,'port':port_a,'type':direction,'curve_no':curve_no,
                              'device_addr':device_addr,'config_id':config_id}
                    status_before = item.get('sound_light_alarm_status')
                    self.soundStatusMap[addr_a] = status_before
                    taskListAudio.append(newItem)

            if radar_warning_status == 0 and radar and '#' in radar:
                list_radar_b = radar.split('#')
                ip_b = list_radar_b[0]
                port_b = list_radar_b[1]
                addr_b = (ip_b,int(port_b))
                if addr_b not in addr_set:
                    addr_set.add(addr_b)
                    soundIp = item.get('sound_light_alarm_ip')
                    radar_test_direction = item.get('radar_test_direction') # 方向
                    radar_speed_threshold = item.get('radar_speed_threshold')
                    radar_anti_jam = item.get('radar_anti_jam')
                    radar_angle = item.get('radar_angle')
                    radar_sensitivity = item.get('radar_sensitivity')
                    status_before = item.get('radar_status')
                    deviceId = str(uuid.uuid4().int)[:21]
                    newItem= {'ip':ip_b,'port':port_b,'curve_no':curve_no,'type':direction,
                              'speed':radar_speed_threshold,'distance':5,'antijam':radar_anti_jam,
                              'angle':radar_angle,'sensitivity':radar_sensitivity,'project_id':project_id,
                              'sound':soundIp,'direction':radar_test_direction,'device_id':deviceId,
                              'config_id':config_id}
                    self.radarStatusMap[addr_b] = status_before
                    radarTaskList.append(newItem)
                    self.deviceMap[addr_b] = newItem

        self.taskRadar = radarTaskList
        self.taskListAudio = taskListAudio
       
        dynamiclogger.info("重新拉取声光告警器;\n audio_task:%s"%taskListAudio)
        dynamiclogger.info("重新拉取雷达设备;\n radar_task:%s"%radarTaskList)

        # 初始化声光告警器,发送一个停止播放的指令
        init_audio_thread = Thread(target=self.init_all_audio,args=[])
        init_audio_thread.start()

        addrList = []
        for item in radarTaskList:
            ip = item.get('ip')
            port = item.get('port')
            addr = (ip,1030) #网络控制器固定端口：1030
            if addr in addrList:
                continue
            addrList.append(addr)
            serial_thread = Thread(target=self.socket_process,args=[addr])
            serial_thread.start()

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
                dynamiclogger.exception(e)  

        self.socketMap = {}
        self.taskListAudio = []
        self.taskRadar = []   

    def get_audio_status(self):

        for item in self.taskListAudio:
            ip = item.get('ip')
            port = item.get('port')
            device_addr = item.get('device_addr')
            addr = (ip,1030) #网络控制器固定端口：1030

            
            if addr in self.socketMap.keys():
                socketClient = self.socketMap.get(addr)
            else:
                socketClient = None

            try:
                if not socketClient:
                    socketClient = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    socketClient.connect(addr)
                    dynamiclogger.info('声光告警器 socket connection success：ip:%s'%addr[0])
            except:
                dynamiclogger.info('声光告警器 socket connection failed：ip:%s'%addr[0])
                socketClient = None
            self.socketMap[addr] = socketClient
            
            if device_addr:
                macAddr = int2hex(device_addr)
                bytedata = bytes.fromhex(macAddr) + b'\x03\x00\x43\x00\x00'
                crccode = calculate_crc16(bytedata)
                bytedata += bytes.fromhex(crccode)

                try:
                    socketClient.send(bytedata)
                    socketClient.settimeout(1)
                    recv_data = socketClient.recv(8)
                except Exception as e:
                    dynamiclogger.info("error :%s"%e)
                    self.socketMap[addr] = None
                    recv_data = None
            else:
                recv_data = None

        #    dynamiclogger.info('audio recv_data:%s'%recv_data)  
            redis_key = "dynamicstatus:" + ip + ":" + device_addr
            status_before = self.soundStatusMap.get(addr)
            if recv_data:   
                dynamiclogger.info('audio status :online, ip :%s ,device_addr:%s'%(ip,device_addr))        
                if not self.rePool.exists(redis_key) or status_before == 1:
                    config_id = item.get('config_id')
                    self.my_db.update('corner_overtaking_config',
                                      {'config_id':config_id},
                                      {'$set':{'sound_light_alarm_status':0}})
                self.soundStatusMap[addr] = 0
                self.rePool.setex(redis_key,60,0) 
            else:
                dynamiclogger.info('audio status :offline,device_addr:%s\n'%device_addr) 
                if self.rePool.exists(redis_key) or status_before == 0:
                    self.rePool.delete(redis_key)
                    config_id = item.get('config_id')
                    self.my_db.update('corner_overtaking_config',
                                      {'config_id':config_id},
                                      {'$set':{'sound_light_alarm_status':1}})
                    self.soundStatusMap[addr] = 1
                    
        instance_timer = Timer(interval = 50,function=self.get_audio_status,args=[])
        instance_timer.start()

    def get_radar_status(self):
        # 维护雷达的状态
        for item in self.taskRadar:
            ip = item.get('ip')
            port = item.get('port')
            addr = (ip,1030) #网络控制器固定端口：1030

            if addr in self.socketMap.keys():
                socketClient = self.socketMap.get(addr)
            else:
                socketClient = None

            bytedata = b'\x43\x46\x04\x00\x00\x00\x0D\x0A'
            try:
                socketClient = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                socketClient.connect(addr)
                socketClient.send(bytedata)
                recvflag = 1
            except Exception as e:
                dynamiclogger.info("error :%s"%e)
                recvflag = 0

            if recvflag == 0:
                redis_key = "dynamicstatus:" + ip
                dynamiclogger.info('radar status :offline,device_addr:%s'%ip) 
                if self.rePool.exists(redis_key):
                    self.rePool.delete(redis_key)
                    config_id = item.get('config_id')
                    self.radarStatusMap[addr] = 1
                    self.my_db.update('corner_overtaking_config',
                                      {'config_id':config_id},
                                      {'$set':{'radar_status':1}})
                else:
                    status = self.radarStatusMap.get(addr)
                    if status == 0:
                        config_id = item.get('config_id')
                        self.radarStatusMap[addr] = 1
                        self.my_db.update('corner_overtaking_config',
                                        {'config_id':config_id},
                                        {'$set':{'radar_status':1}})
                        
                    
        instance_timer = Timer(interval = 50,function=self.get_radar_status,args=[])
        instance_timer.start()

    def deal_msg(self,msg,dev):

        soundItem = dev.get('sound')
        device_id = dev.get('device_id')
        if not soundItem or '#' not in soundItem:
            return
        
        if msg[0:2] == "fc":
            # 雷达告警
            key = "radarEmergency:" + device_id
            if self.rePool.exists(key):               
                return
            dynamiclogger.info("雷达产生超速告警 : %s"%msg)
            self.rePool.setex(key,4,value='1')           
               
            infolist = soundItem.split('#')
            ip,port,device_addr = infolist[0] ,infolist[1] ,infolist[2]
            addr = (ip,int(port))
            audioItem = {'deviceAddr':device_addr,'stopFlag':0,'soundAlarm':1,'lightingMethod':9,'resetDelayTime':20,'alarm_type':1} #alarm_type=1 表示是来自雷达的告警
            timeInRangeFlag = time_judge(self.powerSaveConfig)
            if timeInRangeFlag:
                # 省电时间段内 只爆闪不发声
                audioItem['soundAlarm'] = 0
            
            thread_alarm = Thread(target=self.alarm_audio,args=[addr,audioItem])
            thread_alarm.start()

        elif msg[0:2] == "46":
            # 读取雷达配置参数
            ip = dev.get('ip')
            port = dev.get("port")
            dynamiclogger.info("雷达查询状态回复 : %s ,ip :%s"%(msg,ip))
            addr = (ip,int(port))
            redis_key = "dynamicstatus:" + ip
            dynamiclogger.info('radar status :online,ip:%s\n'%ip)  
            status = self.radarStatusMap.get(addr)          
            if not self.rePool.exists(redis_key) or status == 1:
                config_id = dev.get('config_id')
                self.radarStatusMap[addr] = 0
                self.my_db.update('corner_overtaking_config',
                                    {'config_id':config_id},
                                    {'$set':{'radar_status':0}})

            self.rePool.setex(redis_key,60,0) 

    def alarm_audio(self,addr,item):
        socketClient = self.socketMap.get(addr)
        if not socketClient:
            try:
                socketClient = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                socketClient.connect(addr)
            except:
                dynamiclogger.info('声光告警器connection failed: ip:%s'%addr[0])
                stopFlag = item.get("stopFlag")  # 是否停止播放
                stopTimes = item.get("stopTimes",0)
                if stopFlag == 1 and stopTimes <= 3:
                    dynamiclogger.info('--SavingPower :声光告警器停止失败,3s后第%s次重试!'%(stopTimes+1))
                    item['stopTimes'] = stopTimes + 1
                    retry_thread = Timer(function=self.alarm_audio,interval=3,args=[addr,item])
                    retry_thread.start()
                return
        
        if not socketClient:
            return
        
        deviceAddr = item.get("deviceAddr")
        if not deviceAddr:
            dynamiclogger.info('声光告警器地址为不能为空:%s'%addr[0])
            return
        macAddr = int2hex(deviceAddr)
        byte_addr = bytes.fromhex(macAddr)
        stopFlag = item.get("stopFlag")  # 是否停止播放

        ip = addr[0] #ip
        redis_key = 'audiobusy:' + ip
        rePool = self.rePool
        flag = rePool.exists(redis_key)
        if stopFlag == 1:
            # stopFlag == 1 表示停止告警
            if flag:
                return
            bytecode = byte_addr + b'\x06\x13\x08\x00\x00' #表示绿灯常亮，无声音
        #    bytecode = byte_addr + b'\x06\x00\x16\x00\x01' #表示停止告警，灯也不闪，也无声音
        else:
            soundAlarm = item.get("soundAlarm")  # 报警声音
            lightingMethod = item.get("lightingMethod")  # 灯光控制
            resetDelayTime = item.get("resetDelayTime") #报警时间
            interval_time = int(resetDelayTime)
            actualInterval = get_voice_interval(soundAlarm,interval_time) 
            if actualInterval > 0:
                rePool.setex(redis_key,actualInterval-1,value='1')     
            alarm_type = item.get("alarm_type") #报警来源  alarm_type=1 表示来自雷达的告警  2表示来自算法的告警
            if flag and alarm_type == 1:
                task_item = {'deviceAddr': deviceAddr,'stopFlag': 1}
                thread_queue = Timer(actualInterval, function=self.alarm_audio, args=[addr, task_item])
                thread_queue.start()
                return
            lightByte = lightMap.get(int(lightingMethod))         
            soundByte = bytes.fromhex(int2hex(soundAlarm))
            bytecode = byte_addr + b'\x06' + lightByte + b'\x08\x00' + soundByte
        #    bytecode = byte_addr + b'\x06\x00\x08\x00' + soundByte #扩音声光告警器

        crccode = calculate_crc16(bytecode)
        bytecode = bytecode + bytes.fromhex(crccode)

        try:
            dynamiclogger.info("***雷达告警发给声光告警器：%s" % bytecode)
            socketClient.send(bytecode)
            recv_data = socketClient.recv(8)
            dynamiclogger.info("***声光告警器-收到的数据：%s" % recv_data)
            if len(recv_data) != len(bytecode) or recv_data != bytecode:
                dynamiclogger.info("***声光告警器返回的数据错误")
                if stopFlag == 1 :
                    retryTimes = item.get("retryTimes",0)
                    if retryTimes < 3:
                        item['retryTimes'] = retryTimes + 1
                        dynamiclogger.info("***声光告警器控制指令重发，第%s次"%(retryTimes))
                    else:
                        socketClient.close()
                        del self.socketMap[addr]
                        dynamiclogger.info("***声光告警器控制指令重发3次失败,socket关闭重连")           
                    self.alarm_audio(addr,item)

        except:
            dynamiclogger.info("alarm audio failed %s  deviceAddr:%s" % (addr[0],deviceAddr))

        if stopFlag != 1 and actualInterval != 0:
            task_item = {'deviceAddr': deviceAddr,'stopFlag': 1}
            thread_queue = Timer(actualInterval, function=self.alarm_audio, args=[addr, task_item])
            thread_queue.start()
        return
    
    def sync_status_thread(self):
        """
        同步弯道摄像机、雷达和声光告警器的状态
        """
        mode,url = self.get_work_model()
        if mode == '1':
            curve_config_col = self.my_db.get_col('corner_overtaking_config')
            curve_project_col = self.my_db.get_col('corner_overtaking_project')
            curve_items = curve_project_col.find()           
            for curve_item in curve_items:
                curve_no = curve_item.get('curve_no')
                project_id = curve_item.get('project_id')
                config_items = curve_config_col.find({'project_id':project_id})
                statusList = []
                for config in config_items:
                    radarStatus = config.get('radar_status')
                    sound_status = config.get('sound_light_alarm_status')
                    newitem = {}
                    newitem['id'] = config.get('config_id')                            
                    newitem['radarStatus'] = radarStatus if radarStatus != None else 1
                    newitem['soundLightAlarmStatus'] = sound_status if sound_status != None else 1
                    statusList.append(newitem)
                content= {"curveNo": curve_no,
                          "deviceStatusVoList": statusList}
                resp = sync_status(url,content)
                if resp.get('code') != 200:
                    dynamiclogger.info("同步弯道设备状态 error:%s;\n入参:%s\n"%(resp,content))
                else:
                    dynamiclogger.info("同步弯道设备状态 :%s\n"%resp)
        status_thread = Timer(60,function=self.sync_status_thread, args=[])
        status_thread.start()

    def alarm_all_audio(self):
        try:
            dynamiclogger.info("--SavingPower : --声光告警器黄灯慢闪模式开启--")
            for item in self.taskListAudio:
                ip = item['ip']
                port = int(item['port'])
                addr = (ip,port)
                device_addr = item['device_addr']
                taskItem = {'deviceAddr':device_addr,
                            'stopFlag':0,
                            'soundAlarm':0,
                            'lightingMethod':8,
                            'resetDelayTime':0,
                            'alarm_type':2} 
                self.alarm_audio(addr,taskItem)
            self.close_all_socket()
        except Exception as e:
            dynamiclogger.exception(e)

    def init_all_audio(self):
        try:
            dynamiclogger.info('--SavingPower : --声光告警器初始化')
            for item in self.taskListAudio:
                ip = item['ip']
                port = int(item['port'])
                addr = (ip,port)
                device_addr = item['device_addr']
                taskItem = {'deviceAddr':device_addr,
                            'stopFlag':1} 
                self.alarm_audio(addr,taskItem)
        except Exception as e:
            dynamiclogger.exception(e)

    def saving_power_function(self):
        try:      
            power_config =  self.powerSaveConfig   
            dynamiclogger.info('--SavingPower PowerConfig :%s'%power_config)
            if not power_config:
                return      
                   
            timeInRangeFlag =  time_judge(power_config)
            if  timeInRangeFlag:
                #时间处于 省电开启时间段内
                flag = emergency_judge(db=self.my_db)
                if flag:
                    dynamiclogger.info('--SavingPower Emergency : 5分钟内有告警产生,不断电')
                    return
                time_now = datetime.now()
                NowStamp = int(time_now.timestamp())
                MinuteInterval = power_config.get('frequency',30)
                endTime = power_config.get('endTime')
                MinuteInterval = deal_Interval(time_now,endTime,MinuteInterval)
                if MinuteInterval == 0:
                    return
                command = {"box_send":"do_power_off",
                        "NowStamp":NowStamp,
                        "MinuteInterval":MinuteInterval,
                        "request_type":"1002"}
                json_data = json.dumps(command)
                dynamiclogger.info("--SavingPower SerialSend:%s"%json_data)
                serialClient = serial.Serial('/dev/ttyUSB0', 115200, timeout=1.0)

                #串口写断电指令
                serialClient.write(json_data.encode('utf-8'))

                #串口读mcu断电响应
                recv_data = serialClient.read(50)
                dynamiclogger.info("--SavingPower SerialResp:%s"%recv_data)
                recv_data = recv_data.decode('utf-8')
                recv_json = json.loads(recv_data)
                resp_status = recv_json.get('mcu_send')
                if resp_status == 'ok':
                    # 预备断电：1、声光告警器爆闪提示  2、关闭所有服务
                    self.alarm_all_audio()
                    dynamiclogger.info("--SavingPower : --关闭所有服务 ./scripts/stop_service.sh--")
                    err,result = execShell(cmd="/bin/bash /data/ebox/wavegate/WaveGateMongo/scripts/stop_service.sh")
            else:
                dynamiclogger.info('--SavingPower TimeInPeriod : 不在省电模式工作时间范围')

        except serial.serialutil.SerialException:
            dynamiclogger.info("--SavingPower SerialDev: cannot find dev '/dev/ttyUSB0';")
        except Exception as e:
            dynamiclogger.exception(e)

    def saving_power_timer(self):
        self.saving_power_function()
        timer_power = Timer(function=self.saving_power_timer,interval=300,args=[])
        timer_power.start()
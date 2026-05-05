import socket
import uuid
import json
from datetime import datetime
from threading import Thread,Timer

from utils.db import ToMongo
import utils.logger as logger
from alg.redis_connect import redis_database
from utils.aliyun_voice_phone import send_voice_phone
from system.sync_model import sync_dynamic_emergency,sync_dev_status


devicelogger = logger.getLogger('dynamic')


leakageMap = {'高电压告警':'high_volt_alarm',
              '低电压告警':'low_volt_alarm',
              '高电流告警':'high_cur_alarm',
              '漏电告警':'leakage_alarm'}

deviceSoundMap = {'1':b'\x02','2':b'\x01','3':b'\x03'}  #为设备对应的声光告警器音频文件
# deviceSoundMap = {"001":b'\x02',#断路器电压过高
#                   "002":b'\x02',#断路器电压偏低
#                   "003":b'\x02',#断路器剩余电流异常
#                   "004":b'\x02',#断路器工作电流异常
#                   "005":b'\x02',#可燃气体泄露
#                   "006":b'\x02',#请正确连接静电接地仪
#                   "007":b'\x02',#静电接地仪异常
#                   "008":b'\x02',#呜喔呜喔
#                   "009":b'\x02',#危险区域，禁止吸烟
#                   "010":b'\x02',#危险区域，禁止打电话
#                   "011":b'\x02',#疑似火灾，请迅速报警
#                   "012":b'\x02',#危险区域，未经允许禁止闯入
#                   "013":b'\x02'#灭火器缺失，请及时处理
#                   }

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

def de2binary(num:int):
    '''
    10进制转 8位二进制
    '''
    return '{:08b}'.format(num)


def int2hex(n):
    """
    int类型地址码转16进制字符串
    """
    if type(n) == str:
        n = int(n)
    return hex(n)[2:] if n >= 16 else '0{:X}'.format(n)

def is_all_zero(arr):
    for num in arr:
        if num != 0:
            return False
    return True

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

    # 返回最终的crc值
    return hex(((crc & 0xff) << 8) + (crc >> 8))[2:]

def set_leakage_param(item,volt_param,cur_param,socket_server):

    if not socket_server:
        return

    overvolt_param = volt_param.get('volt_max')
    undervolt_param = volt_param.get('volt_min')
    overcur_param = cur_param.get('cur_max')
    leakage_param = cur_param.get('cur_leak')

    volt = item.get('volt')
    cur = item.get('current')
    volt_max = volt.get('volt_max')
    volt_min = volt.get('volt_min')
    cur_leak = cur.get('cur_leak')
    cur_max = cur.get('cur_max')
    
    device_addr = item.get('device_addr')
    addr = int2hex(device_addr) 

    if overvolt_param and overvolt_param != volt_max:
        # 设置过压参数
        value = '{:04x}'.format(volt_max)
        cmd = addr + '063006' + value
        msg = {"mb":cmd,"sn":1,"ack":1,"crc":1}
        json_msg = json.dumps(msg)
        bytes_msg = json_msg.encode('utf-8')
        socket_server.send(bytes_msg)
        recv_data = socket_server.recv(100)
      #  devicelogger.info('set_leak msg:%s ; resp:%s'%recv_data)

    if undervolt_param and undervolt_param != volt_min:
        # 设置欠压参数
        value = '{:04x}'.format(volt_min)
        cmd = addr + '063004' + value
        msg = {"mb":cmd,"sn":1,"ack":1,"crc":1}
        json_msg = json.dumps(msg)
        bytes_msg = json_msg.encode('utf-8')
        socket_server.send(bytes_msg)
        recv_data = socket_server.recv(100)
        devicelogger.info('set_leak msg:%s ; resp:%s'%recv_data)

    if overcur_param and overcur_param != cur_max:
        # 设置过流参数
        value = '{:04x}'.format(cur_max)
        cmd = addr + '063012' + value
        msg = {"mb":cmd,"sn":1,"ack":1,"crc":1}
        json_msg = json.dumps(msg)
        bytes_msg = json_msg.encode('utf-8')
        socket_server.send(bytes_msg)
        recv_data = socket_server.recv(100)
     #   devicelogger.info('set_leak msg:%s ; resp:%s'%recv_data)

    if leakage_param and leakage_param != cur_leak:
        # 设置剩余电流参数
        value = '{:04x}'.format(cur_leak)
        cmd = addr + '06300B' + value
        msg = {"mb":cmd,"sn":1,"ack":1,"crc":1}
        json_msg = json.dumps(msg)
        bytes_msg = json_msg.encode('utf-8')
        socket_server.send(bytes_msg)
        recv_data = socket_server.recv(100)
      #  devicelogger.info('set_leak msg:%s ; resp:%s'%recv_data)

    return

def delay_audio_queue(msgQueue, task):
    if msgQueue.full():
        # 队列满了，取出最早的任务
        msgQueue.get()
    devicelogger.info("########stopcode放入队列")
    msgQueue.put([2, task])


def verify_crc(content: bytes) -> bool:
    """
    验证 返回数据的crc校验码
    """
    msg = content[:-2]
    crccode = calculate_crc16(msg)
    temp = byte2str(content[-2:])

    origin_code = temp.lstrip("0")
    if crccode == origin_code:
        return True
    else:
        return False


def deal_status_redis(rePool, deviceId,value):
    """
    判断redis中是否存在key，不存在就存60s
    """
    key = "dynamicstatus:" + deviceId
    if not rePool.exists(key):
        rePool.setex(key, 60, value)
    return

def deal_phone_num(rePool, deviceId, phone):
    """
    判断redis中是否存在key，不存在就添加，保存12h
    """
    key = deviceId + phone
    if not rePool.exists(key):
        value = "1"
        rePool.setex(key, 12 * 60 * 60, value)
        return True
    value = rePool.get(key)
    if int(value) > 5:
        return False
    else:
        rePool.setex(key, 12 * 60 * 60, str(int(value) + 1))
        return True


def deal_emergency_redis(rePool, deviceId):
    """
    判断redis中是否存在key，不存在就存上
    """
    key = "dynamicemergency:" + deviceId
    if rePool.exists(key):
        return True
    else:
        value = "true"
        rePool.setex(key, 30, value)
        return False

def get_asso_item(asso_col, audio_col, device_id):
    item = asso_col.find_one({'device_id': device_id}, {'_id': 0})
    if not item:
        return
    
    audio_id = item.get('audio_id')
    audio_item = audio_col.find_one({'device_id': audio_id}, {'_id': 0})

    if not audio_item:
        audioInfo = None
    else:
        deviceAddr = audio_item.get('device_addr')
        ip = audio_item.get('ip')
        port = audio_item.get('port')
        audioInfo = {'deviceAddr':deviceAddr,'ip':ip,'port':int(port),'audioId':audio_id}

    newItem = dict()
    newItem['audio_item'] = audioInfo
    newItem['sms'] = item.get('sms_number')
    newItem['phone'] = item.get('phone_number')
    return newItem

def deal_gas(content,wordList,sub_dev,my_db,rePool):
    device_addr = wordList[1]
    item = sub_dev.get(int(device_addr))
    if not item:
        return
    msg_type = wordList[2]

    deviceId = item.get("device_id")
     
    if msg_type == "Density":
        
        density_value_list = content[1::2]
        density_set = item.get("density")  # 告警浓度值
        if not density_set:
            return
        density_set = float(density_set) * 100

        devicelogger.info("deal_gas: %s,density_set:%s;" % (density_value_list, density_set))

        if max(density_value_list) >= density_set:
            # 触发可燃气体告警
            flag = deal_emergency_redis(rePool, deviceId)
            if flag:
                # 未达到30s间隔  避免告警太频繁
                return
            
            emergencyItem = dict()
            emergencyItem["emergency_record_id"] = uuid.uuid4().hex
            emergencyItem["emergency_time"] = datetime.now()
            emergencyItem["emergency_context"] = "可燃气体高于阈值%s%%" % density_set
            emergencyItem["emergency_type"] = "气体浓度告警"
            emergencyItem["emergency_level"] = None
            emergencyItem["device_name"] = item.get("device_name")
            emergencyItem["device_type"] = item.get("device_type")
            emergencyItem["device_id"] = deviceId
            my_db.insert("odin_business_dynamic_emergency_record", emergencyItem)

            #同步告警到平台
            sync_thread = Thread(target=sync_dynamic_emergency,args=[emergencyItem])
            sync_thread.start()

            alarm_conf = item.get('high_density_alarm')
            alarm_flag = alarm_conf.get('audio')
            phone_flag = alarm_conf.get('phone')
            if alarm_flag == '0':
                audioItem = item.get('audio_item')
                if audioItem: 
                    ip = audioItem.get('ip')
                    port = audioItem.get('port')
                    addr = (ip,port)
                    ins = SerialNetServer(context=None)
                    audioItem['stopFlag'] = 0
                    audioItem['deviceType'] = '1'
                    ins.alarm_audio(addr,audioItem)

            if phone_flag == '0':
                dynamic_associate_info = my_db.get_col('odin_dynamic_associate').find_one({"device_id": deviceId})
                data = {'deviceType': '气体告警器', 'pointName': '威富集团'}
                called_number = dynamic_associate_info.get('phone_number')
                devicelogger.info("气体告警器电话: %s,phone_info:%s;\n" % (data, called_number))
                if called_number:
                    if '/' in called_number:
                        arr = called_number.split('/')
                        for p in arr:
                            flag = deal_phone_num(rePool, deviceId, p)
                            devicelogger.info("气体告警器电话：flag=%s;\n" % flag)
                            if flag:
                                send_voice_phone(data, p, 3)
                    else:
                        flag = deal_phone_num(rePool, deviceId, called_number)
                        devicelogger.info("气体告警器电话：flag=%s;\n" % flag)
                        if flag:
                            send_voice_phone(data, called_number, 3)
    
    elif msg_type == "Range":
        # 气体探测器量程
        rangeList = content[1::2]
        if not is_all_zero(rangeList):
            deal_status_redis(rePool,deviceId,value=0)
            devicelogger.info('deal gas: Range--%s'%rangeList)
            return
        devicelogger.info("气体告警器的四个探头均未接或者异常；\n")
        deal_status_redis(rePool,deviceId,value=3)


def deal_leakage_new(content,wordList,sub_dev,my_db,rePool):
    device_addr = wordList[1]
    item = sub_dev.get(int(device_addr))
    if not item:
        return
    deviceId = item.get('device_id')
    deal_status_redis(rePool,deviceId,value=0)
    msg_type = wordList[2]
    if msg_type == "StatusAll":
        high_bit_num,low_bit_num = content[4],content[5]
        devicelogger.info("deal_leakage :%s"%[high_bit_num,low_bit_num])
        if high_bit_num == 0 and low_bit_num == 0:
            devicelogger.info("deal_leakage :未产生用电告警")
            return
        str_high_bit = de2binary(high_bit_num) #高字节
        str_low_bit = de2binary(low_bit_num) #低字节

        # 告警原因 bit 0~15
        # bit8 过流
        # bit5 剩余电流
        # bit2 过压
        # bit1 欠压

        overcur_bit = str_high_bit[7]
        leakage_bit = str_low_bit[2]
        overvolt_bit = str_low_bit[5]
        undervolt_bit = str_low_bit[6]

        emergencyItem = dict()

        volParm = item.get("volt")
        curParam = item.get("current")
        
        if overcur_bit == '1':
            #触发过流告警
            cur_max = curParam.get('cur_max')
            emergencyItem["emergency_record_id"] = uuid.uuid4().hex
            emergencyItem["emergency_time"] = datetime.now()
            emergencyItem["emergency_context"] = "电流高于阈值%sA" % cur_max
            emergencyItem["emergency_type"] = "高电流告警"
            emergencyItem["emergency_level"] = None
            emergencyItem["device_name"] = item.get("device_name")
            emergencyItem["device_type"] = item.get("device_type")
            emergencyItem["device_id"] = deviceId
        
        elif leakage_bit == '1':
            #触发漏电告警
            cur_leak = curParam.get('cur_leak')
            emergencyItem["emergency_record_id"] = uuid.uuid4().hex
            emergencyItem["emergency_time"] = datetime.now()
            emergencyItem["emergency_context"] = "漏电高于阈值%smA" % cur_leak
            emergencyItem["emergency_type"] = "漏电告警"
            emergencyItem["emergency_level"] = None
            emergencyItem["device_name"] = item.get("device_name")
            emergencyItem["device_type"] = item.get("device_type")
            emergencyItem["device_id"] = deviceId

        elif overvolt_bit == '1':
            #触发过压告警
            volt_max = volParm.get("volt_max")
            emergencyItem["emergency_record_id"] = uuid.uuid4().hex
            emergencyItem["emergency_time"] = datetime.now()
            emergencyItem["emergency_context"] = "电压高于阈值%sV" % volt_max
            emergencyItem["emergency_type"] = "高电压告警"
            emergencyItem["emergency_level"] = 2
            emergencyItem["device_name"] = item.get("device_name")
            emergencyItem["device_type"] = item.get("device_type")
            emergencyItem["device_id"] = deviceId
        
        elif undervolt_bit == '1':
            #触发欠压告警
            volt_min = volParm.get("volt_min")
            emergencyItem["emergency_record_id"] = uuid.uuid4().hex
            emergencyItem["emergency_time"] = datetime.now()
            emergencyItem["emergency_context"] = "电压低于阈值%sV" % volt_min
            emergencyItem["emergency_type"] = "低电压告警"
            emergencyItem["emergency_level"] = 1
            emergencyItem["device_name"] = item.get("device_name")
            emergencyItem["device_type"] = item.get("device_type")
            emergencyItem["device_id"] = deviceId
        else:
            return

        devicelogger.info("断路器产生%s;str_high_bit:%s str_low_bit:%s"%(emergencyItem["emergency_type"],str_high_bit,str_low_bit))

        flag = deal_emergency_redis(rePool, deviceId)
        if not flag:
            emergencyItem['distributionNum'] = item.get('distribution_num')
            my_db.insert("odin_business_dynamic_emergency_record", emergencyItem)

            #同步告警到平台
            sync_thread = Thread(target=sync_dynamic_emergency,args=[emergencyItem])
            sync_thread.start()

            emergency_type = emergencyItem["emergency_type"]           
            conf_type = leakageMap.get(emergency_type,{})

            alarm_conf = item.get(conf_type)
            audio_flag = alarm_conf.get('audio')
            phone_flag = alarm_conf.get('phone')

            if audio_flag == '0':
                audioItem = item.get('audio_item')
                if audioItem: 
                    ip = audioItem.get('ip')
                    port = audioItem.get('port')
                    addr = (ip,port)
                    ins = SerialNetServer(context=None)
                    audioItem['stopFlag'] = 0
                    audioItem['deviceType'] = '2'
                    ins.alarm_audio(addr,audioItem)

            devicelogger.info("漏电断路器电话：phone_flag=%s;\n" % phone_flag)
            if phone_flag == '0':
                dynamic_associate_info = my_db.get_col('odin_dynamic_associate').find_one({"device_id": deviceId})
                data = {'deviceType': emergency_type, 'pointName': '威富集团'}
                called_number = dynamic_associate_info.get('phone_number')
                devicelogger.info("漏电断路器电话: data=%s,phone_info:%s;\n" % (data, called_number))
                if called_number:
                    if '/' in called_number:
                        arr = called_number.split('/')
                        for p in arr:
                            flag = deal_phone_num(rePool, deviceId, p)
                            devicelogger.info("漏电断路器电话：flag=%s;\n" % flag)
                            if flag:
                                send_voice_phone(data, p, 3)
                    else:
                        flag = deal_phone_num(rePool, deviceId, called_number)
                        devicelogger.info("漏电断路器电话：flag=%s;\n" % flag)
                        if flag:
                            send_voice_phone(data, called_number, 3)
        return
        
def deal_leakage(content,wordList,sub_dev,my_db,rePool):
    device_addr = wordList[1]
    item = sub_dev.get(int(device_addr))
#    devicelogger.info("item:%s"%item)
    if not item:
        return
    deviceId = item.get('device_id')
    deal_status_redis(rePool,deviceId,value=0)
    msg_type = wordList[2]
    if msg_type == "StatusAll":
        
        voltA = (content[6] * 256 + content[7])/10
        voltB = (content[8] * 256 + content[9])/10
        voltC = (content[10] * 256 + content[11])/10

        curA = (content[12] * 256 + content[13])/10
        curB = (content[14] * 256 + content[15])/10
        curC = (content[16] * 256 + content[17])/10

        residual_current = content[18] * 256 + content[19]   #剩余电流值

        devicelogger.info("deal_leakage [%sV,%sA,%smA]"%(voltA,curA,residual_current))

        volParm = item.get("volt")
        volt_max = volParm.get("volt_max")
        volt_min = volParm.get("volt_min")

        curParam = item.get("current")
        cur_leak = curParam.get('cur_leak')
        cur_max = curParam.get('cur_max') 

        deviceId = item.get("device_id")
        emergencyItem = dict()
        emergencyFlag = False

        if not volt_max or not volt_min or not cur_max or not cur_leak:
            return

        if cur_leak and residual_current > cur_leak:
            # 触发漏电告警
            emergencyItem["emergency_record_id"] = uuid.uuid4().hex
            emergencyItem["emergency_time"] = datetime.now()
            emergencyItem["emergency_context"] = "漏电高于阈值%smA" % cur_leak
            emergencyItem["emergency_type"] = "漏电告警"
            emergencyItem["emergency_level"] = None
            emergencyItem["device_name"] = item.get("device_name")
            emergencyItem["device_type"] = item.get("device_type")
            emergencyItem["device_id"] =   item.get("device_id")
            emergencyFlag = True

        elif cur_max and ( curA > cur_max or curB > cur_max or curC > cur_max ):
            # 触发高电流告警
            emergencyItem["emergency_record_id"] = uuid.uuid4().hex
            emergencyItem["emergency_time"] = datetime.now()
            emergencyItem["emergency_context"] = "电流高于阈值%sA" % cur_max
            emergencyItem["emergency_type"] = "高电流告警"
            emergencyItem["emergency_level"] = None
            emergencyItem["device_name"] = item.get("device_name")
            emergencyItem["device_type"] = item.get("device_type")
            emergencyItem["device_id"] = item.get("device_id")
            emergencyFlag = True

        elif voltA > volt_max or voltB > volt_max or voltC > volt_max:
            # 触发高电压告警
            emergencyItem["emergency_record_id"] = uuid.uuid4().hex
            emergencyItem["emergency_time"] = datetime.now()
            emergencyItem["emergency_context"] = "电压高于阈值%sV" % volt_max
            emergencyItem["emergency_type"] = "高电压告警"
            emergencyItem["emergency_level"] = None
            emergencyItem["device_name"] = item.get("device_name")
            emergencyItem["device_type"] = item.get("device_type")
            emergencyItem["device_id"] = item.get("device_id")
            emergencyFlag = True

        elif voltA < volt_min or voltB < volt_min or voltC < volt_min:
            # 触发低电压告警
            emergencyItem["emergency_record_id"] = uuid.uuid4().hex
            emergencyItem["emergency_time"] = datetime.now()
            emergencyItem["emergency_context"] = "电压低于阈值%sV" % volt_min
            emergencyItem["emergency_type"] = "低电压告警"
            emergencyItem["emergency_level"] = None
            emergencyItem["device_name"] = item.get("device_name")
            emergencyItem["device_type"] = item.get("device_type")
            emergencyItem["device_id"] = item.get("device_id")
            emergencyFlag = True


        if not emergencyFlag:
            devicelogger.info("断路器电压正常,volt=%s,电流正常,cur=%s;未产生漏电,res_cur=%s\n" % ((voltA, voltB, voltC), (curA, curB, curC),residual_current))
            return
        else:
            devicelogger.info("断路器产生用电告警;volt=%s,cur=%s;res_cur=%s\n" % ((voltA, voltB, voltC), (curA, curB, curC),residual_current))

        flag = deal_emergency_redis(rePool, deviceId)
        if not flag:
            emergencyItem['distribution_num'] = item.get('distribution_num')
            my_db.insert("odin_business_dynamic_emergency_record", emergencyItem)

            #同步告警到平台
            sync_thread = Thread(target=sync_dynamic_emergency,args=[emergencyItem])
            sync_thread.start()

            emergency_type = emergencyItem["emergency_type"]
            conf_type = leakageMap.get(emergency_type,{})
          #  devicelogger.info('******%s'%item)
            alarm_conf = item.get(conf_type)

            if not alarm_conf:
                return

            audio_flag = alarm_conf.get('audio')
            phone_flag = alarm_conf.get('phone')
            if audio_flag == '0':
                audioItem = item.get('audio_item')
                if audioItem:
                    ip = audioItem.get('ip')
                    port = audioItem.get('port')
                    addr = (ip,port)
                    ins = SerialNetServer(context=None)
                    audioItem['stopFlag'] = 0
                    audioItem['deviceType'] = '2'
                    ins.alarm_audio(addr,audioItem)

            devicelogger.info("漏电断路器电话：phone_flag=%s;\n" % phone_flag)
            if phone_flag == '0':
                dynamic_associate_info = my_db.get_col('odin_dynamic_associate').find_one({"device_id": deviceId})
                data = {'deviceType': emergency_type, 'pointName': '威富集团'}
                called_number = dynamic_associate_info.get('phone_number')
                devicelogger.info("漏电断路器电话: data=%s,phone_info:%s;\n" % (data, called_number))
                if called_number:
                    if '/' in called_number:
                        arr = called_number.split('/')
                        for p in arr:
                            flag = deal_phone_num(rePool, deviceId, p)
                            devicelogger.info("漏电断路器电话：flag=%s;\n" % flag)
                            if flag:
                                send_voice_phone(data, p, 3)
                    else:
                        flag = deal_phone_num(rePool, deviceId, called_number)
                        devicelogger.info("漏电断路器电话：flag=%s;\n" % flag)
                        if flag:
                            send_voice_phone(data, called_number, 3)
        return

def deal_static_ele(content,wordList,sub_dev,my_db:ToMongo,rePool):
    device_addr = wordList[1]
    item = sub_dev.get(int(device_addr))
    devicelogger.info('deal_GndMeter :%s'%(content))
    if not item:
        return
    
    statusbit = content[1]
    deviceId = item.get("device_id")
    redis_key = "dynamicstatus:" + deviceId
    
    status_flag = rePool.exists(redis_key)
    if not status_flag:
        rePool.setex(redis_key,60,statusbit)
    else:
        value = rePool.get(redis_key).decode()
        if value != str(statusbit):
            rePool.setex(redis_key,60,statusbit)

    emergencyItem = dict()
    if statusbit == 1:
        # 静电接地器触发状态           
        emergencyItem["emergency_record_id"] = uuid.uuid4().hex
        emergencyItem["emergency_time"] = datetime.now()
        emergencyItem["emergency_context"] = "触发状态"
        emergencyItem["emergency_type"] = "静电接地触发"
        emergencyItem["emergency_level"] = None
        emergencyItem["device_name"] = item.get("device_name")
        emergencyItem["device_type"] = item.get("device_type")
        emergencyItem["device_id"] = deviceId
        devicelogger.info("##静电接地器进入触发状态,name:%s" % item.get("device_name"))
    elif statusbit == 2:
        #静电接地器告警状态
        emergencyItem = dict()
        emergencyItem["emergency_record_id"] = uuid.uuid4().hex
        emergencyItem["emergency_time"] = datetime.now()
        emergencyItem["emergency_context"] = "告警状态"
        emergencyItem["emergency_type"] = "静电接地告警"
        emergencyItem["emergency_level"] = None
        emergencyItem["device_name"] = item.get("device_name")
        emergencyItem["device_type"] = item.get("device_type")
        emergencyItem["device_id"] = deviceId
        devicelogger.info("##静电接地器进入告警状态,name:%s" % item.get("device_name"))
    elif statusbit == 3:
        #静电接地器故障状态
        col = my_db.get_col('odin_dynamic_static_electricity')
        query = {'device_id':deviceId}
        item = col.find_one(query)
        status = item.get('device_status')
        if status != '2':
            new = {'device_status':'2','offline_time':datetime.now()}
            col.update_one(query,new,upsert=False)
        return
    
    if statusbit != 0:
        result = deal_emergency_redis(rePool,deviceId)
        if not result:
            my_db.insert("odin_business_dynamic_emergency_record", emergencyItem)

            #同步告警到平台
            sync_thread = Thread(target=sync_dynamic_emergency,args=[emergencyItem])
            sync_thread.start()

    return

def deal_msg(msg,sub_dev,my_db,rePool):
  #  devicelogger.info('recv msg:%s'%msg)
    keysList = msg.keys()
    for keyword in keysList:
        if keyword == 'id':
            continue
        elif keyword == 'time':
            emergency_time = msg.get('time')
            continue
        wordList = keyword.split('_')
        deviceType = wordList[0]
        content = msg.get(keyword)
        if deviceType == "Switch":
            result = deal_leakage(content,wordList,sub_dev,my_db,rePool)
        elif deviceType == "Gas":
            result = deal_gas(content,wordList,sub_dev,my_db,rePool)
        elif deviceType == "GndMeter":
            result = deal_static_ele(content,wordList,sub_dev,my_db,rePool)
        
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
            self.conn_list = []
            self.socketMap = {}

            self.deviceMap = {}
            self.dynamic_task = []

            self.audioSocketMap = {}
            self.taskListAudio = []

            self.my_db = ToMongo('wavedevice')
            self.rePool = redis_database
            self.getTask()
            self.socketClosedMap = {}
            self.get_audio_task()
            threadAudioStatus = Thread(target=self.get_audio_status,args=[])
            threadAudioStatus.start()
         
            thread1 = Thread(target=self.query_dynamic_status,args=[])
            thread1.start()
    
    def close_all(self):
        closedList = self.socketMap.keys()
        # socketServiceList = self.socketMap.values()
        # if not socketServiceList:
        #     return
        self.socketClosedMap = {}
        for addr in closedList:
            try:
                s = self.socketMap.get(addr)
                s.close()
                self.socketClosedMap[addr] = 1
            except Exception as e:
                devicelogger.exception(e)

        self.conn_list = []
        self.socketMap = {}
        self.deviceMap = {}
        self.dynamic_task = []

    def close_all_audio(self):
        socketServiceList = self.audioSocketMap.values()
        if not socketServiceList:
            return
        
        self.audioSocketMap = {}
        self.taskListAudio = []

        for s in socketServiceList:
            try:
                s.close()
            except Exception as e:
                devicelogger.exception(e)

    def query_dynamic_status(self):
        if self.dynamic_task:     
            colmatch = {'1':'odin_dynamic_gas','2':'odin_dynamic_leakage','3':'odin_dynamic_static_electricity'}  
            statusEntity = []    
            for item in self.dynamic_task:
                deviceId = item.get('device_id')
                device_type = item.get('device_type')
                colName = colmatch.get(device_type)
                originStatus = self.dynamicStatusMap.get(deviceId)
                query = {'device_id':deviceId}

                redis_key = 'dynamicstatus:' + deviceId
                flag = self.rePool.exists(redis_key)
                
                map = {'deviceId':deviceId,'deviceType':device_type}
                map['deviceStatus'] = '0' if flag else '1'
                statusEntity.append(map)

                if not flag and originStatus != '1':
                    now = datetime.now()
                    self.my_db.update(colName,query,{'$set':{'device_status':'1','offline_time':now}})
                    status_now = '1'
                    self.dynamicStatusMap[deviceId] = status_now
                    map['offlineTime'] = now.strftime("")

                elif flag and originStatus == '1':
                    value = self.rePool.get(redis_key).decode()
                    status_now = '0' if value in ['0','1','2'] else '2'
                    self.my_db.update(colName,query,{'$set':{'device_status':status_now}})
                    self.dynamicStatusMap[deviceId] = status_now
            sync_dev_status(statusEntity)
        timer1 = Timer(interval=60,function=self.query_dynamic_status,args=[])
        timer1.start()
     
    def socket_process(self,addr):
        
        devicelogger.info('self.conn_list:%s'%self.conn_list)        
        sub_device = self.deviceMap.get(addr)

        if not sub_device:
            devicelogger.info("%s 没有下属设备；"%addr[0])
            return
        
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(addr)
            devicelogger.info("socket connection success,ip:%s"%addr[0])
        except:
            devicelogger.info("socket connection failed,ip:%s"%addr[0])
            reconnect_thread = Timer(interval=30,function=self.socket_process,args=[addr])
            reconnect_thread.start()
            return

        devicelogger.info("485设备socket-增加连接:(%s,%s)"%(addr[0],addr[1]))
        self.conn_list.append(addr)
        self.socketMap[addr] = s

        while True:
            try:
                s.settimeout(5)
                data = s.recv(1024)
                msg = data.decode()
                msg = json.loads(msg)
            except Exception as e:
                close_flag = self.socketClosedMap.get(addr)
                if close_flag == 1:
                    del self.socketClosedMap[addr]
                    return
                reconnect_thread = Timer(interval=20,function=self.socket_process,args=[addr])
                reconnect_thread.start()
                devicelogger.exception(e)
                break
            
            result = deal_msg(msg,sub_device,self.my_db,self.rePool)

    def add2map(self,item):
        keysList = self.deviceMap.keys()
        ip = item.get('ip')
        port = item.get('port')
        if not ip or not port:
            return
        addr = (ip,int(port))
        if addr not in keysList:
            self.deviceMap[addr] = {}
        newItem = self.deviceMap[addr]
        device_addr = item.get('device_addr')
        newItem[device_addr] = item
        self.deviceMap[addr] = newItem
       
    def getTask(self):
        '''
        重新获取动环任务
        type: 1 2 3 气体探测器/断路器/静电接地器
        '''
        # 关闭所有连接
        self.close_all() 

        leak_col = self.my_db.get_col("odin_dynamic_leakage")
        gas_col = self.my_db.get_col("odin_dynamic_gas")
        elec_col = self.my_db.get_col("odin_dynamic_static_electricity")
        asso_col = self.my_db.get_col("odin_dynamic_associate")
        audio_col = self.my_db.get_col("odin_dynamic_audio")

        leak_items = leak_col.find({}, {'_id': 0})
        gas_items = gas_col.find({}, {'_id': 0})
        elec_item = elec_col.find({}, {'_id': 0})

        taskList = []
        statusMap = {}
        if leak_items.count() != 0:
            for item in leak_items:
                item["device_type"] = "2"
                asso_item = get_asso_item(asso_col, audio_col, device_id=item['device_id'])
                if asso_item:
                    item = dict(item,**asso_item)
                self.add2map(item)
                taskList.append(item)
                device_id = item.get('device_id')
                statusMap[device_id] = item.get('device_status')

        if gas_items.count() != 0:
            for item in gas_items:
                item["device_type"] = "1"
                asso_item = get_asso_item(asso_col, audio_col, device_id=item['device_id'])
                if asso_item:
                    item = dict(item,**asso_item)
                self.add2map(item)
                taskList.append(item)
                device_id = item.get('device_id')
                statusMap[device_id] = item.get('device_status')

        if elec_item.count() != 0:
            for item in elec_item:
                item["device_type"] = "3"
                self.add2map(item)
                taskList.append(item)
                device_id = item.get('device_id')
                statusMap[device_id] = item.get('device_status')
        self.dynamic_task = taskList
        self.dynamicStatusMap = statusMap
        devicelogger.info("重新拉取动环任务;\ndynamic_task:%s,设备deviceMap:%s" % (taskList,self.deviceMap))

        addrList = []
        for item in taskList:
            ip = item.get('ip')
            port = item.get('port')
            device_addr = item.get('device_addr')
            addr = (ip,1030) #网络控制器固定端口：1030
            if addr in addrList:
                continue
            addrList.append(addr)
            serial_thread = Thread(target=self.socket_process,args=[addr])
            serial_thread.start()

    def get_audio_status(self):

        for item in self.taskListAudio:
            ip = item.get('ip')
            port = item.get('port')
            device_addr = item.get('device_addr')

            addr = (ip,1030) #网络控制器固定端口：1030
            
            if addr in self.audioSocketMap.keys():
                socketClient = self.audioSocketMap.get(addr)
            else:
                socketClient = None

            try:
                socketClient = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                socketClient.connect(addr)
                devicelogger.info('声光告警器 socket connection success：ip:%s'%addr[0])
            except:
                devicelogger.info('声光告警器 socket connection failed：ip:%s'%addr[0])
                socketClient = None
            self.audioSocketMap[addr] = socketClient
            

            macAddr = int2hex(device_addr)
            bytedata = bytes.fromhex(macAddr) + b'\x03\x00\x43\x00\x00'
            crccode = calculate_crc16(bytedata)
            bytedata += bytes.fromhex(crccode)

            try:
                socketClient.send(bytedata)
                socketClient.settimeout(1)
                recv_data = socketClient.recv(8)
            except Exception as e:
                devicelogger.info("error :%s"%e)
                recv_data = None

            devicelogger.info('audio recv_data:%s'%recv_data)  
            deviceId = item.get('device_id')
            redis_key = "dynamicstatus:" + deviceId
            if recv_data:   
                devicelogger.info('audio status :online,device_addr:%s'%device_addr)            
                if not self.rePool.exists(redis_key):
                    self.my_db.update('odin_dynamic_audio',
                                      {'device_id':deviceId},
                                      {'$set':{'device_status':'0'}})

                self.rePool.setex(redis_key,60,0) 
            else:
                devicelogger.info('audio status :offline,device_addr:%s'%device_addr) 
                if self.rePool.exists(redis_key):
                    self.rePool.delete(redis_key)
                    self.my_db.update('odin_dynamic_audio',
                                      {'device_id':deviceId},
                                      {'$set':{'device_status':'1','offline_time':datetime.now()}})
                    

        instance_timer = Timer(interval = 50,function=self.get_audio_status,args=[])
        instance_timer.start()

    def get_audio_task(self):
        '''
        负责声光告警器的状态和告警
        '''
        self.close_all_audio()

        audio_col = self.my_db.get_col("odin_dynamic_audio")
        audio_items = audio_col.find({'connection_type':'1'}, {'_id': 0})

        taskListAudio = []
        if audio_items.count() != 0:
            for item in audio_items:
                item["device_type"] = "4"
                taskListAudio.append(item)
        self.taskListAudio = taskListAudio

        devicelogger.info("重新拉取声光告警器;\n audio_task:%s"%taskListAudio)


    def alarm_audio(self,addr,item):

        socketClient = self.audioSocketMap.get(addr)
        if not socketClient:
            try:
                socketClient = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                socketClient.connect(addr)
            except:
                devicelogger.info('声光告警器connection failed：ip:%s'%addr[0])
                return
        
        if not socketClient:
            return
        
        deviceAddr = item.get("deviceAddr")
        macAddr = int2hex(deviceAddr)
        byte_addr = bytes.fromhex(macAddr)
        stopFlag = item.get("stopFlag")  # 是否停止播放

        if stopFlag == 2:
            # stopFlag == 2 表示停止告警
            bytecode = byte_addr + b'\x06\x00\x16\x00\x01'
            emergency_type = 0
        elif stopFlag == -1:
            # stopFlag == -1 表示开始告警
            bytecode = byte_addr + b'\x06\x40\x08\x00\x05'
            emergency_type = 1
        elif stopFlag == 0:
            deviceType = item.get("deviceType")
            sound_byte = deviceSoundMap.get(deviceType)
            bytecode = byte_addr + b'\x06\x00\x03\x00' + sound_byte
            emergency_type = 1
        else:
            controlType = item.get("controlType")  # 控制方式
            lightType = item.get("lightType")  # 灯光控制
            alarmPattern = item.get("alarmPattern")  # 灯光和声音
            voice = alarmPattern.get("voice")
            light = alarmPattern.get("light")
            if voice == 0 and light == 0:
                # 不发光也无声音
                return

            bytecode = byte_addr + b'\x06'
            if lightType == 1:
                # 慢闪 播完后熄灭
                bytecode += b'\x40'
            else:
                # 爆闪 播完后熄灭
                bytecode += b'\x30'

            if not voice:
                # 只发光 不发声
                bytecode += b'\x0F\x02\x02'
                emergency_type = 2
            else:
                # 发光也发声  循环播放
                bytecode += b'\x08\x00\x05'
                emergency_type = 1

        crccode = calculate_crc16(bytecode)
        bytecode = bytecode + bytes.fromhex(crccode)
        try:
            socketClient.send(bytecode)
            recv_data = socketClient.recv(8)
            devicelogger.info("***声光告警器-收到的数据：%s" % recv_data)

            if emergency_type != 0:
                newItem = {}
                newItem['audio_id'] = item.get('audioId')
                newItem['emergency_type'] = emergency_type
                newItem['create_time'] = datetime.now()
                self.my_db.insert('odin_bussiness_audio_record',newItem)
        except:
            devicelogger.info("alarm audio failed %s  deviceAddr:%s" % (addr[0],deviceAddr))
        if stopFlag == 1 and controlType != 0:
            interval_time = int(controlType)
            equipId = item.get("equipId")
            task_item = {'deviceAddr': deviceAddr, 'equipId': equipId, 'stopFlag': 2}
            thread_queue = Timer(interval_time, function=self.alarm_audio, args=[addr, task_item])
            thread_queue.start()
        return
        
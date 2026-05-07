import serial
import uuid
import time
from datetime import datetime
from threading import Thread, Timer

from Utils.aliyun_voice_phone import send_voice_phone
from Utils.db import ToMongo
from algorith_server.redis_connect import redis_database
import Utils.logger as logger
from msg_queue import audio_queue
from algorith_server.Alibabasms import SendSmsResqueset

devicelogger = logger.getLogger('dynamic')

    
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


def int2hex(n):
    """
    int类型地址码转16进制字符串
    """
    if type(n) == str:
        n = int(n)
    return hex(n)[2:] if n >= 16 else '0{:X}'.format(n)


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


def deal_status_redis(rePool, deviceId):
    """
    判断redis中是否存在key，不存在就存60s
    """
    key = "dynamicstatus:" + deviceId
    if not rePool.exists(key):
        value = "true"
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


def judge_gas_msg(data, datalength):
    if not data:
        return False
    length = len(data)
    if length != datalength:
        # 气体探测器回码为7位
        devicelogger.info('气体探测器状态返回数据错误,长度不正确,recv_data:%s' % data)
        return False
    crc_result = verify_crc(data)  # 计算crc校验码是否准确
    if not crc_result:
        devicelogger.info('气体探测器返回数据CRC校验错误,recv_data:%s' % data)
        return False
    return True


def deal_leakage(my_db: ToMongo, rePool, ser, strData, item):
    """
    处理漏电断路 告警
    """
    # 三相电
    voltA = int(strData[6:10], 16) / 10
    voltB = int(strData[10:14], 16) / 10
    voltC = int(strData[14:18], 16) / 10

    curA = int(strData[18:22], 16) / 10
    curB = int(strData[22:26], 16) / 10
    curC = int(strData[26:30], 16) / 10

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

    if voltA > volt_max or voltB > volt_max or voltC > volt_max:
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


    elif curA > cur_max or curB > cur_max or curC > cur_max:
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

    elif curA > cur_leak or curB > cur_leak or curC > cur_leak:
        # 触发漏电告警
        emergencyItem["emergency_record_id"] = uuid.uuid4().hex
        emergencyItem["emergency_time"] = datetime.now()
        emergencyItem["emergency_context"] = "漏电高于阈值%sA" % cur_leak
        emergencyItem["emergency_type"] = "漏电告警"
        emergencyItem["emergency_level"] = None
        emergencyItem["device_name"] = item.get("device_name")
        emergencyItem["device_type"] = item.get("device_type")
        emergencyItem["device_id"] = item.get("device_id")
        emergencyFlag = True

    if not emergencyFlag:
        devicelogger.info("断路器电压正常,volt=%s，电流正常,cur=%s;\n" % ((voltA, voltB, voltC), (curA, curB, curC)))
        return
    else:
        devicelogger.info("断路器产生用电告警;volt=%s,cur=%s;\n" % ((voltA, voltB, voltC), (curA, curB, curC)))

    flag = deal_emergency_redis(rePool, deviceId)
    if not flag:
        emergencyItem['distributionNum'] = item.get('distribution_num')
        my_db.insert("odin_business_dynamic_emergency_record", emergencyItem)
        emergency_type = emergencyItem["emergency_type"]
        if emergency_type == "高电压告警":
            alarm_conf = item.get('high_volt_alarm')
        elif emergency_type == "低电压告警":
            alarm_conf = item.get('low_volt_alarm')
        elif emergency_type == "高电流告警":
            alarm_conf = item.get('high_cur_alarm')
        else:
            alarm_conf = item.get('leakage_alarm')
        audio_flag = alarm_conf.get('audio')
        phone_flag = alarm_conf.get('phone')
        if audio_flag == '0':
            audioItem = item.get('audio_item')
            audioAddr = audioItem.get('device_addr')
            if not audioAddr:
                return
            audioAddr = int2hex(audioAddr)
            command = bytes.fromhex(audioAddr) + b'\x06\x00\x03\x00\x01'
            crc = calculate_crc16(command)
            totalCmd = command + bytes.fromhex(crc)
            devicelogger.info("断路器告警-声光告警器指令为: %s\n" % totalCmd)
            time.sleep(0.1)
            ser.write(totalCmd)
            ser.read(8)

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


def deal_gas(my_db: ToMongo, rePool, ser, strData, item):
    """
    处理可燃气体 告警
    """
    densitybit = strData[6:10]
    density_value = int(densitybit, 16)

    density_set = item.get("density")  # 告警浓度值
    density_set = float(density_set) * 100

    devicelogger.info("收-气体告警器的浓度: %s,density_set:%s;\n" % (density_value, density_set))
    if density_value >= density_set:
        # 触发可燃气体告警
        deviceId = item.get("device_id")
        emergencyItem = dict()
        emergencyItem["emergency_record_id"] = uuid.uuid4().hex
        emergencyItem["emergency_time"] = datetime.now()
        emergencyItem["emergency_context"] = "可燃气体高于阈值%s%%" % density_set
        emergencyItem["emergency_type"] = "气体浓度告警"
        emergencyItem["emergency_level"] = None
        emergencyItem["device_name"] = item.get("device_name")
        emergencyItem["device_type"] = item.get("device_type")
        emergencyItem["device_id"] = deviceId

        flag = deal_emergency_redis(rePool, deviceId)
        if not flag:
            my_db.insert("odin_business_dynamic_emergency_record", emergencyItem)
            alarm_conf = item.get('high_density_alarm')
            alarm_flag = alarm_conf.get('audio')
            phone_flag = alarm_conf.get('phone')
            if alarm_flag == '0':
                audioItem = item.get('audio_item')
                audioAddr = audioItem.get('device_addr')
                if not audioAddr:
                    return
                audioAddr = int2hex(audioAddr)
                command = bytes.fromhex(audioAddr) + b'\x06\x00\x03\x00\x02'
                crc = calculate_crc16(command)
                totalCmd = command + bytes.fromhex(crc)
                devicelogger.info("气体告警-声光告警器指令为: %s\n" % totalCmd)
                ser.write(totalCmd)
                ser.read(8)

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
    return


def deal_static_ele(my_db: ToMongo, rePool, strData, item, statusList):
    """
    处理静电接地器 告警
    """
    statusbit = strData[8:10]  # 返回数据的第7个字节为 result

    # 状态位 00-正常  01-触发状态 02-报警状态
    last_status = statusList[-1] if statusList else None

    emergencyItem = dict()

    deviceId = item.get("device_id")
    redis_key = "dynamicstatus:" + deviceId
    if statusbit == "03":
        # 静电接地器故障
        if rePool.exists(redis_key):
            value = rePool.get(redis_key).decode()
            if value != '2':  # 2表示故障  1表示在线
                rePool.setex(redis_key, 60, '2')
        else:
            rePool.setex(redis_key, 60, '2')
        return

    elif not last_status:
        result = [statusbit]
        return result

    elif last_status == "00" and statusbit == "01":
        # 静电接地器进入触发状态
        emergencyItem["emergency_record_id"] = uuid.uuid4().hex
        emergencyItem["emergency_time"] = datetime.now()
        emergencyItem["emergency_context"] = "触发状态"
        emergencyItem["emergency_type"] = "静电接地触发"
        emergencyItem["emergency_level"] = None
        emergencyItem["device_name"] = item.get("device_name")
        emergencyItem["device_type"] = item.get("device_type")
        emergencyItem["device_id"] = deviceId
        devicelogger.info("##静电接地器进入触发状态,name:%s" % item.get("device_name"))

    elif last_status == "01" and statusbit == "02":
        # 静电接地器进入告警状态
        emergencyItem["emergency_record_id"] = uuid.uuid4().hex
        emergencyItem["emergency_time"] = datetime.now()
        emergencyItem["emergency_context"] = "告警状态"
        emergencyItem["emergency_type"] = "静电接地告警"
        emergencyItem["emergency_level"] = None
        emergencyItem["device_name"] = item.get("device_name")
        emergencyItem["device_type"] = item.get("device_type")
        emergencyItem["device_id"] = deviceId
        devicelogger.info("##静电接地器进入告警状态,name:%s" % item.get("device_name"))

    statusList.append(statusbit)
    devicelogger.info("##静电接地器的状态位为: %s" % statusbit)
    if len(statusList) > 10:
        statusList = statusList[-10:]

    if emergencyItem:
        my_db.insert("odin_business_dynamic_emergency_record", emergencyItem)

    return statusList


def get_asso_item(asso_col, audio_col, device_id):
    item = asso_col.find_one({'device_id': device_id}, {'_id': 0})
    if not item:
        return
    audio_id = item.get('audio_id')
    audio_item = audio_col.find_one({'device_id': audio_id}, {'_id': 0})

    newItem = dict()
    newItem['audio_addr'] = audio_item.get('device_addr')
    newItem['sms'] = item.get('sms_number')
    newItem['phone'] = item.get('phone_number')
    return newItem


def recv_leak_msg(ser):
    recv_data = ser.read(17)
    length = len(recv_data)
    if not recv_data or length == 17:
        return recv_data
    recv_again = ser.read(17)
    if not recv_again:
        return recv_data
    total = recv_data + recv_again
    return total


class SerialServer():
    __instance = None
    __flag = False

    def __new__(cls, *args, **kwargs):
        # super().__new__(cls)
        if cls.__instance is None:
            cls.__instance = super().__new__(cls)
        return cls.__instance

    def __init__(self, context):
        if not SerialServer.__flag:
            SerialServer.__flag = True
            self.context = context
            self.ser = serial.Serial('/dev/ttyS1', 9600, timeout=0.11)
            #    self.ser.parity = serial.PARITY_NONE  # 默认无校验
            self.my_db = ToMongo('wavedevice')
            self.rePool = redis_database
            self.task = []  # 动环任务
            self.eleStatusDict = {}

            # 初始化动环任务
            init_thread = Thread(target=self.getTask, args=[])
            init_thread.start()

            # 开启任务消化进程
            deal_thread = Thread(target=self.deal_task, args=[])
            deal_thread.start()

            sms_client = SendSmsResqueset()

    def process_queue(self):
        if audio_queue.qsize() == 0:
            return
        # 先进先出队列
        early_task = audio_queue.get()[1]
        self.sendAudioData(early_task)

    def deal_task(self):
        if not self.task:
            # 空闲时，定时任务的间隔 设为30s
            interval_time = 5
        else:
            devicelogger.info("---------------开启动环任务消化进程---------------")
            interval_time = 1
            self.process_queue()
            for task in self.task:
                device_type = task.get("device_type")
                if device_type == '1':
                    # 气体探测器
                    self.sendGasData(task)
                elif device_type == '2':
                    # 漏电断路器
                    self.sendLeakageData(task)
                elif device_type == '3':
                    # 静电接地器
                    self.sendStaticEleData(task)
                else:
                    # 声光告警器
                    self.getAudioStatus(task)

        thread_idle = Timer(interval=interval_time, function=self.deal_task, args=[])
        thread_idle.start()

    def getTask(self):
        '''
        重新获取动环任务
        type: 1 2 3 气体探测器/断路器/静电接地器
        '''
        leak_col = self.my_db.get_col("odin_dynamic_leakage")
        gas_col = self.my_db.get_col("odin_dynamic_gas")
        elec_col = self.my_db.get_col("odin_dynamic_static_electricity")
        asso_col = self.my_db.get_col("odin_dynamic_associate")
        audio_col = self.my_db.get_col("odin_dynamic_audio")

        leak_items = leak_col.find({}, {'_id': 0})
        gas_items = gas_col.find({}, {'_id': 0})
        elec_item = elec_col.find({}, {'_id': 0})
        audio_items = audio_col.find({'add_type': 0}, {'_id': 0})

        taskList = []
        if leak_items.count() != 0:
            for item in leak_items:
                item["device_type"] = "2"
                item["device_addr"] = int2hex(item["device_addr"])
                asso_item = get_asso_item(asso_col, audio_col, device_id=item['device_id'])
                item = dict(item,**asso_item)
                taskList.append(item)

        if gas_items.count() != 0:
            for item in gas_items:
                item["device_type"] = "1"
                item["device_addr"] = int2hex(item["device_addr"])
                asso_item = get_asso_item(asso_col, audio_col, device_id=item['device_id'])
                item = dict(item,**asso_item)
                taskList.append(item)

        if elec_item.count() != 0:
            for item in elec_item:
                item["device_type"] = "3"
                item["device_addr"] = int2hex(item["device_addr"])
                taskList.append(item)

        if audio_items.count() != 0:
            for item in audio_items:
                newItem = {}
                newItem["device_type"] = "4"
                newItem["device_id"] = item['device_id']
                newItem["device_addr"] = int2hex(item["device_addr"])
                taskList.append(newItem)
        self.task = taskList
        devicelogger.info("重新拉取动环任务;\ndynamic_task:%s" % self.task)

    def sendLeakageData(self, item):
        """
        漏电断路器的收发
        """
        try:
            macAddr = item.get("device_addr")
            bytedata = bytes.fromhex(macAddr) + b'\x04\x40\x03\x00\x06'
            crccode = calculate_crc16(bytedata)
            bytedata += bytes.fromhex(crccode)
            self.ser.write(bytedata)
            recv_data = recv_leak_msg(self.ser)
            devicelogger.info("**断路器的地址码为：%s;" % macAddr)
            deviceId = item.get("device_id")

            if not recv_data:
                devicelogger.info("收-断路器返回数据为空：%s\n" % recv_data)
                key = "dynamicstatus:" + deviceId
                if self.rePool.exists(key):
                    # 存离线时间
                    now = datetime.now()
                    self.my_db.update("odin_dynamic_leakage", {"device_id": deviceId},
                                      {"$set": {"offline_time": now, "device_status": "1"}})
                return

            # 收到状态返回数据，存redis
            deal_status_redis(self.rePool, deviceId)

            length = len(recv_data)
            if length != 17:
                devicelogger.info('**断路器返回数据错误,recv_data:%s\n' % recv_data)
                return
            crc_result = verify_crc(recv_data)  # 计算crc校验码是否准确
            if not crc_result:
                devicelogger.info('**断路器返回数据CRC校验错误,recv_data:%s\n' % recv_data)
                return

            strData = byte2str(recv_data)
            devicelogger.info("**收-断路器的电压电流为：%s;" % strData)

            result = deal_leakage(my_db=self.my_db, rePool=self.rePool, ser=self.ser, strData=strData, item=item)
        except Exception as e:
            devicelogger.exception(e)

        return

    def sendGasData(self, item):
        """
        气体探测器的收发
        """
        try:
            macAddr = item.get("device_addr")
            byte_addr = bytes.fromhex(macAddr)
            devicelogger.info("--气体探测器的地址码为：%s" % macAddr)

            cmd_status = byte_addr + b'\x03\x01\x00\x00\x01'  # 获取探测器状态
            crccode_status = calculate_crc16(cmd_status)
            cmd_status = cmd_status + bytes.fromhex(crccode_status)
            #    devicelogger.info("--发送指令查询探测器状态：%s"%cmd_status)

            self.ser.write(cmd_status)
            recv_status = self.ser.read(8)
            deviceId = item.get("device_id")
            if not recv_status:
                devicelogger.info("收-气体告警器返回数据为空：%s" % recv_status)
                key = "dynamicstatus:" + deviceId
                if self.rePool.exists(key):
                    # 触发第一次离线
                    now = datetime.now()
                    self.my_db.update("odin_dynamic_gas", {"device_id": deviceId},
                                      {"$set": {"offline_time": now, "device_status": "1"}})
                return

            # 收到状态返回数据，存redis
            deal_status_redis(self.rePool, deviceId)

            gass_status_flag = judge_gas_msg(recv_status, 7)
            if not gass_status_flag:
                return

            strData = byte2str(recv_status)
            devicelogger.info("收-气体告警器的状态: %s" % recv_status)
            # 探测器的状态位
            # 00-预热  01-正常 03-传感器故障 05-一级告警  06-二级告警  07-探头故障
            statusbit = strData[8:10]
            statusdict = {'03': '传感器故障', '07': '探头故障', '00': '预热中'}
            if statusbit in ['03', '07', '00']:
                devicelogger.info('气体探测器%s,recv_data:%s' % (statusdict.get(statusbit), recv_status))
                return

            cmd_density = byte_addr + b'\x03\x00\x00\x00\x01'  # 获取可燃气体浓度
            crccode_density = calculate_crc16(cmd_density)
            cmd_density = cmd_density + bytes.fromhex(crccode_density)

            self.ser.write(cmd_density)
            recv_density = self.ser.read(20)

            gas_density_flag = judge_gas_msg(recv_density, 7)
            if not gas_density_flag:
                return
            densityData = byte2str(recv_density)
            result = deal_gas(self.my_db, self.rePool, self.ser, densityData, item)
        except Exception as e:
            devicelogger.exception(e)

        return

    def sendAudioData(self, item):
        """
        控制声光告警器
        """
        try:
            deviceAddr = item.get("deviceAddr")
            macAddr = int2hex(deviceAddr)
            byte_addr = bytes.fromhex(macAddr)
            stopFlag = item.get("stopFlag")  # 是否停止播放
            equipId = item.get("equipId")

            key = "dynamicemergency:" + equipId
            if stopFlag == 1:
                if not self.rePool.exists(key):
                    stopCode = byte_addr + b'\x06\x00\x16\x00\x01'
                    crc = calculate_crc16(stopCode)
                    stopCode = stopCode + bytes.fromhex(crc)
                    devicelogger.info("***声光告警器-停止-发送,macAddr：%s" % macAddr)
                    self.ser.write(stopCode)
                    recvdata = self.ser.read(8)
                    devicelogger.info('***声光告警器-停止-返回数据:%s' % recvdata)
                return

            elif stopFlag == 2:
                stopCode = byte_addr + b'\x06\x00\x16\x00\x01'
                crc = calculate_crc16(stopCode)
                stopCode = stopCode + bytes.fromhex(crc)
                devicelogger.info("***声光告警器-停止-发送,macAddr：%s" % macAddr)
                self.ser.write(stopCode)
                recvdata = self.ser.read(8)
                devicelogger.info('***声光告警器-停止-返回数据:%s' % recvdata)

            elif stopFlag == -1:
                # 开始告警
                startCode = byte_addr + b'\x06\x40\x08\x00\x05'
                crc = calculate_crc16(startCode)
                startCode = startCode + bytes.fromhex(crc)
                devicelogger.info("***声光告警器-开始告警-发送,macAddr：%s" % macAddr)
                self.ser.write(startCode)
                recvdata = self.ser.read(8)
                devicelogger.info('***声光告警器-停止告警-返回数据:%s' % recvdata)

            controlType = item.get("controlType")  # 控制方式
            lightType = item.get("lightType")  # 灯光控制
            alarmPattern = item.get("alarmPattern")  # 灯光和声音
            voice = alarmPattern.get("voice")

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
            else:
                # 发光也发声  循环播放
                bytecode += b'\x08\x00\x05'

            crccode = calculate_crc16(bytecode)
            bytecode = bytecode + bytes.fromhex(crccode)
            #    devicelogger.info("***声光告警器-发送数据：%s;"%bytecode)
            self.ser.write(bytecode)
            recv_data = self.ser.read(8)
            devicelogger.info("***声光告警器-收到的数据：%s" % recv_data)
            if controlType != 0:
                interval_time = int(controlType)
                equipId = item.get("equipId")
                key = "dynamicemergency:" + equipId
                self.rePool.setex(key, interval_time, value='true')
                task_item = {'deviceAddr': deviceAddr, 'equipId': equipId, 'stopFlag': 1}
                thread_queue = Timer(interval_time, function=delay_audio_queue, args=[audio_queue, task_item])
                thread_queue.start()


        except Exception as e:
            devicelogger.exception(e)
        return

    def sendStaticEleData(self, item):
        """
        静电接地器 的收发
        """
        try:
            macAddr = item.get("device_addr")
            # header--a6 a6 6a  总长度-06
            bytedata = bytes.fromhex(macAddr) + b'\x03\x00\x02\x21\x00'
            crccode = calculate_crc16(bytedata)
            bytedata += bytes.fromhex(crccode)
            self.ser.write(bytedata)
            recv_data = self.ser.read(8)

            deviceId = item.get("device_id")
            if not recv_data:
                if self.eleStatusDict.get(deviceId):
                    del self.eleStatusDict[deviceId]
                devicelogger.info("收-静电接地器器返回数据为空;send_data: %s" % bytedata)
                key = "dynamicstatus:" + deviceId
                if self.rePool.exists(key):
                    # 触发第一次离线
                    now = datetime.now()
                    self.my_db.update("odin_dynamic_gas", {"device_id": deviceId},
                                      {"$set": {"offline_time": now, "device_status": "1"}})
                return

            # 收到状态返回数据，存redis
            deal_status_redis(self.rePool, deviceId)

            crc_result = verify_crc(recv_data)  # 计算crc校验码是否准确
            if not crc_result:
                devicelogger.info('静电报警器CRC校验错误,recv_data:%s' % recv_data)
                return

            strData = byte2str(recv_data)

            status_list = self.eleStatusDict.get(deviceId)
            result = deal_static_ele(my_db=self.my_db, rePool=self.rePool, strData=strData, item=item,
                                     statusList=status_list)

            self.eleStatusDict[deviceId] = result

        except Exception as e:
            devicelogger.exception(e)
        return

    def getAudioStatus(self, item):
        """
        查询声光告警器的状态
        """
        try:
            macAddr = item.get("device_addr")
            deviceId = item.get("device_id")
            key = "dynamicstatus:" + deviceId
            if self.rePool.exists(key):
                return
            bytedata = bytes.fromhex(macAddr) + b'\x03\x00\x43\x00\x00'
            crccode = calculate_crc16(bytedata)
            bytedata += bytes.fromhex(crccode)
            self.ser.write(bytedata)
            recv_data = self.ser.read(8)
            devicelogger.info("声光告警器收到的数据：%s" % recv_data)

            self.rePool.setex(key, 60, value='0')
            if not recv_data:
                devicelogger.info("收-声光告警器返回数据为空;send_data: %s" % bytedata)
                # 触发第一次离线
                now = datetime.now()
                col = self.my_db.get_col('odin_dynamic_audio')
                query = {"device_id": deviceId}
                status = col.find_one(query).get('device_status')
                newItem = {"offline_time": now, "device_status": "1"} if status == "0" else {"device_status": "1"}
                self.my_db.update("odin_dynamic_audio", {"device_id": deviceId}, {"$set": newItem})

            else:
                self.my_db.update("odin_dynamic_audio", {"device_id": deviceId}, {"$set": {"device_status": "0"}})

        except Exception as e:
            devicelogger.exception(e)

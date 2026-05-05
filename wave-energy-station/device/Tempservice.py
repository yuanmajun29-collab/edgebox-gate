import socket
import threading
import time
import struct
from utils.db import ToMongo
from alg.redis_connect import redis_database
import traceback
import utils.logger as logger
from device.KNDservice import insert_to_database, sync_device_status, sync_emergency, sync_temperature
from utils.CheckdeviceStatus import CheckDeviceStatus

mainlogger = logger.getLogger('main')


def calc_crc(string):
    """CRCM计算"""
    data = bytearray.fromhex(string)
    crc = 0xFFFF
    for pos in data:
        crc ^= pos
        for i in range(8):
            if ((crc & 1) != 0):
                crc >>= 1
                crc ^= 0xA001
            else:
                crc >>= 1
    return hex(((crc & 0xff) << 8) + (crc >> 8) + 4660)[-4:]


def send_out(udp_socket, recv_ip, sn, functionCode, temp_max, temp_min):
    """回复数据"""
    dLen = bytes([0, 1])  # 数据长度
    state = bytes([0])  # 状态
    oOptions = bytes([0, 0])  # 操作选项
    currentTime = bytes(list(map(int, time.strftime("%y,%m,%d,%H,%M,%S", time.localtime()).split(","))))  # 实时时间
    HDReporT = bytes([0, 0])  # 历史数据上报时刻

    RTReporInterval = 1  # 实时数据上报间隔(分钟,1-1440)
    RecorInterval = 1  # 数据记录间隔(分钟,1-1440)
    HDRepor = 0  # 历史数据上报间隔(小时,0代表随实时数据上报)
    HTAlarm = int(temp_max)  # 高温告警值(℃)
    LTAlarm = int(temp_min)  # 低温告警值(℃)
    TBuffer = 0.1  # 温度缓冲值(℃)
    HHAlarm = 75  # 高湿告警值(rh%)
    LHAlarm = 15  # 低湿告警值(rh%)
    HBuffer = 0.1  # 湿度缓冲值(rh%)

    # 根据SN号判断设备类型回复配置数据,SN号C0开头为,80开头为单温度
    if sn[0:1] == b'\xC0':
        cdata = (oOptions + currentTime + (RTReporInterval).to_bytes(2, byteorder='big') + (RecorInterval).to_bytes(2,
                                                                                                                    byteorder='big') + HDReporT +
                 (HDRepor).to_bytes(1, byteorder='big') + struct.pack('>h', int(HTAlarm * 10)) + struct.pack('>h',
                                                                                                             int(LTAlarm * 10)) + (
                     int(TBuffer * 10)).to_bytes(2, byteorder='big') +
                 (int(HHAlarm * 10)).to_bytes(2, byteorder='big') + (int(LHAlarm * 10)).to_bytes(2, byteorder='big') + (
                     int(HBuffer * 10)).to_bytes(2, byteorder='big'))
    elif sn[0:1] == b'\x80':
        cdata = (oOptions + currentTime + (RTReporInterval).to_bytes(2, byteorder='big') + (RecorInterval).to_bytes(2,
                                                                                                                    byteorder='big') + HDReporT +
                 (HDRepor).to_bytes(1, byteorder='big') + struct.pack('>h', int(HTAlarm * 10)) + struct.pack('>h',
                                                                                                             int(LTAlarm * 10)) + (
                     int(TBuffer * 10)).to_bytes(2, byteorder='big'))
    # 判断功能码,如果是实时数据带配置参数回复
    if functionCode == b'\x01' or functionCode == b'\x0B':
        cLen = bytes([0, len(cdata)])  # 配置长度
        CRCM = bytearray.fromhex(
            (calc_crc((b'\x7e' + sn + functionCode + dLen + state + cLen + cdata).hex())))  # 计算CRC校验码
        sendBytes = b'\x7e' + sn + functionCode + dLen + state + cLen + cdata + CRCM + b'\x0D'
    else:
        cLen = bytes([0, 0])  # 配置长度
        CRCM = bytearray.fromhex((calc_crc((b'\x7e' + sn + functionCode + dLen + state + cLen).hex())))  # 计算CRC校验码
        sendBytes = b'\x7e' + sn + functionCode + dLen + state + cLen + CRCM + b'\x0D'
    dest_ip = recv_ip[0]
    dest_port = recv_ip[1]
    udp_socket.sendto(sendBytes, (dest_ip, dest_port))


def deal_msg(db: ToMongo, rePool, sn, temperature, mode, url):
    try:
        device_col = db.get_col("odin_dynamic_device")
        query = {"device_num": sn}
        item = device_col.find_one(query)
        if not item:
            return

        flag = rePool.exists(sn)
        if flag:
            return
        else:
            value = 'true'
            emergency_interval_time = item.get("emergency_interval_time")
            interval_time_int = int(emergency_interval_time) * 60  # 单位：秒
            rePool.setex(sn, interval_time_int, value)

        # 插入到告警数据库
        insert_to_database(db, item)

        if mode == "1":
            # 联网模式 同步动环告警
            content = dict()
            content["deviceNum"] = sn
            content["macAddr"] = None
            content["controllerPort"] = 100
            content["temperature"] = temperature
            sync_emergency(url, content)

    except Exception as e:
        mainlogger.info("温度告警器deal_msg error:%s" % traceback.format_exc())


class TempServer():
    __instance = None
    __flag = False

    def __new__(cls, *args, **kwargs):
        # super().__new__(cls)
        if cls.__instance is None:
            cls.__instance = super().__new__(cls)
        return cls.__instance

    def __init__(self, context):
        if not TempServer.__flag:
            TempServer.__flag = True
            self.context = context
            self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

            mainlogger.info("温度传感器进程绑定 IP 0.0.0.0 , 端口 5555")
            self.udp_socket.bind(("", 5555))

            self.socketMacMap = {}
            self.portMap = {}

            self.my_db = ToMongo('wavedevice')
            self.rePool = redis_database

            self.check_status()  # 定时一分钟查询动环设备的状态

            self.temp_max = None
            self.temp_min = None
            self.tempMap = {}

            self.mode, self.url = self.get_mode()

            self.report_temp()  # 定时一分钟查询动环设备的状态

    def get_mode(self):
        # 获取工作模式
        modelItem = self.my_db.get_col("authority_work_model").find_one()
        model = modelItem.get("model")
        service_address = modelItem.get("service_address")
        service_port = modelItem.get("service_port")
        remote_url = "http://%s:%s" % (service_address, service_port)
        self.mode = model
        self.url = remote_url
        return model, remote_url

    def set_temp_threhold(self, temp_max, temp_min):
        self.temp_max = temp_max
        self.temp_min = temp_min
        keys = self.socketMacMap.keys()
        mainlogger.info("设置温度阈值,max:%s,min:%s,socketMacMap:%s" % (temp_max, temp_min, self.socketMacMap))
        for ip in keys:
            macSn = self.socketMacMap.get(ip)
            port = self.portMap.get(ip)
            send_out(self.udp_socket, (ip, port), macSn, functionCode=b'\x01', temp_max=temp_max, temp_min=temp_min)

    def recv_data(self):
        while True:
            recv_data = self.udp_socket.recvfrom(1024)
            recv_ip = recv_data[1]  # 设备IP 端口
            data = recv_data[0]  # 设备上报的数据
            sn = data[1:7]  # 设备SN号
            ip = recv_ip[0]
            macSn = self.socketMacMap.get(ip)
            port = self.portMap.get(ip)
            if not macSn:
                self.socketMacMap[ip] = sn
                self.portMap[ip] = recv_ip[1]
            if port != recv_ip[1]:
                self.portMap[ip] = recv_ip[1]
            if data[0:1] == b'\x7e' and data[len(data) - 1:len(data)] == b'\x0D':  # 判断是否包头为7E,包尾为0D
                #            mainlogger.info("--接收温度传感器数据:%s,传感器IP:%s"%(data.hex(),recv_ip))
                snStr = sn.hex()
                functionCode = data[7:8]  # 功能码
                emergencyCode = data[18:19]  # 告警标志位
                # 功能码01和0B为实时数据
                if functionCode == b'\x01' or functionCode == b'\x0B':
                    temperature = struct.unpack('>h', data[10:12])[0] / 10  # 温度值
                    humidity = int.from_bytes(data[12:14], byteorder='big') / 10  # 湿度值
                    content = {}
                    content["temperature"] = temperature
                    content["humidity"] = humidity
                    content["deviceNum"] = snStr
                    self.tempMap[snStr] = content
                    if emergencyCode != b'\x01' or emergencyCode != b'\x02':  # '\x01' 和 '\x02' 表示高温告警和低温告警  
                        continue
                        # 根据SN号判断设备类型,SN号C0开头为,80开头为单温度
                    if sn[0:1] == b'\xC0':
                        mainlogger.info(
                            "--接收温度传感器数据解析:SN号:%s,温度:%s,湿度:%s" % (snStr, temperature, humidity))
                    deal_msg(self.my_db, self.rePool, snStr, str(temperature), self.mode, self.url)

    def report_temp(self):
        try:
            if not self.tempMap or self.mode != "1":
                return
            dynamic_col = self.my_db.get_col("odin_dynamic_device")
            contentMap = self.tempMap.copy()
            sns = contentMap.keys()
            if not sns:
                return
            for sn in sns:
                content = contentMap.get(sn)
                query = {"device_num": sn}
                item = dynamic_col.find_one(query)
                if item:
                    # 如果有绑定该设备
                    result = sync_temperature(self.url, content)
                else:
                    del self.tempMap[sn]
        except Exception as e:
            mainlogger.info("--温度上报error:%s" % e)
        finally:
            report_thread = threading.Timer(600, self.report_temp)
            report_thread.start()

    def check_status(self):
        try:
            #    mainlogger.info("--self.socketMacMap:%s"%self.socketMacMap)
            if not self.socketMacMap:
                return
            ipsMap = self.socketMacMap.copy()
            ips = ipsMap.keys()
            data = []
            for ip in ips:
                mac = self.socketMacMap.get(ip).hex()
                result = CheckDeviceStatus(ip)
                status = 0 if result else 1
                item = {"device_status": status}
                query = {"device_num": mac}
                #    mainlogger.info("--动环设备状态：%s,mac:%s,ip:%s"%(status,mac,ip))
                self.my_db.update("odin_dynamic_device", query, {"$set": item}, is_one=False)
                if status == 1:
                    del self.socketMacMap[ip]
                    del self.portMap[ip]
                if self.mode == "1":
                    item = dict()
                    item["key"] = mac
                    item["status"] = str(status)
                    data.append(item)
            if self.mode == "1":
                sync_device_status(self.url, data)
        except Exception as e:
            mainlogger.info("温度告警器check_status_error :%s" % e)
        finally:
            check_thread = threading.Timer(60, self.check_status)
            check_thread.start()

    def start(self):
        thread1 = threading.Thread(target=self.recv_data, args=())
        thread1.start()
        mainlogger.info("--开启温度告警发送接收线程")

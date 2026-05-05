import socket
from alg.redis_connect import redis_database
from utils.voicedevice_utils import *
import threading
from utils.CheckdeviceStatus import CheckDeviceStatus
import traceback

mainlogger = logger.getLogger('main')

SYNC_DYNAMIC_STATUS = "/net-web/syn/synDynamicDeviceStatus"
SYNC_DYNAMIC_EMERGENCY = "/net-web/dynamic/emergency"
SYNC_TEMPERATURE = "/net-web/dynamic/synTemperature"


def toBinary(num):
    # 十进制数转化为二进制，如3->"0011"
    binary_number = bin(num)
    binary_string = binary_number[2:]
    while len(binary_string) < 4:
        binary_string = "0" + binary_string
    return binary_string


def sync_device_status(url, data):
    url = url + SYNC_DYNAMIC_STATUS
    headers = {'Content-Type': 'application/json'}
    content = {"data": data}
    resp = requests.post(url, data=json.dumps(content), headers=headers, verify=False)
    mainlogger.info("--动环设备状态同步:%s" % resp.json())
    return


def sync_temperature(url, content):
    try:
        url = url + SYNC_TEMPERATURE
        headers = {'Content-Type': 'application/json'}
        resp = requests.post(url, data=json.dumps(content), headers=headers, verify=False)
        mainlogger.info("--动环温湿度上报:%s;\n--温度上报入参：%s" % (resp.json(), content))
    except Exception as e:
        mainlogger.info("--动环温湿度上报error:%s" % e)
    return


def sync_emergency(url, content):
    url = url + SYNC_DYNAMIC_EMERGENCY
    headers = {'Content-Type': 'application/json'}
    resp = requests.post(url, params=content, headers=headers, verify=False)
    mainlogger.info("--动环设备告警同步:%s;\n--告警同步入参：%s" % (resp.json(), content))
    return


def insert_to_database(db: ToMongo, item: dict()):
    try:
        if not item:
            return
        point_col = db.get_col('odin_point')
        point_id = item.get('point_id')
        point_item = point_col.find_one({'point_id': point_id})
        sound_switch = item['sound_switch']
        if sound_switch == 0:
            # 控制音响
            sound_control(db, item)
        data = {
            "emergency_record_id": uuid.uuid4().hex,
            "point_id": point_id,
            "point_name": point_item.get('point_name'),
            "device_id": item.get('device_id'),
            "device_type": item.get('device_type'),
            "device_name": item.get('device_name'),
            "emergency_context": item.get('sound_context'),
            "emergency_time": datetime.now(),
            "organization_id": item.get('organization_id')
        }
        db.insert('odin_business_dynamic_emergency_record', data)

    except Exception as e:
        mainlogger.info('insert_to_database error:%s' % e)


def sound_control(db: ToMongo, item):
    try:
        sound_id = item.get('sound_id')
        sound_times = item.get('sound_times')
        sound_context = item.get('sound_context')
        if not sound_id or not sound_times or not sound_context:
            return

        sound_id_list = sound_id.split(',')
        sound_col = db.get_col('odin_device_sound')
        for soundId in sound_id_list:
            query = {"sound_id": sound_id}
            sound_item = sound_col.find_one(query)
            sound_type = sound_item.get('sound_type')

            sound_context_list = [sound_context] * int(sound_times)
            sound_file = ",".join(sound_context_list)

            # itc
            if sound_type == '1':
                itc_server_col = db.get_col('odin_device_itc_server')
                server_item = itc_server_col.find_one()
                if server_item:
                    itc_server_address = server_item['itc_server_address']
                    itc_server_port = server_item['itc_server_port']
                    account = server_item['itc_server_account']
                    password = server_item['itc_server_password']
                    server_url = 'http://%s:%s' % (itc_server_address, itc_server_port)
                    result = sendSoundmessage(sound_col, sound_id, sound_type=1, sound_file=sound_file,
                                              server_url=server_url, account=account, password=password)

            # 菱声
            elif sound_type == '2':
                lings_server_col = db.get_col('odin_device_lings_server')
                server_item = lings_server_col.find_one()
                if server_item:
                    lings_server_address = server_item['lings_server_address']
                    lings_server_port = server_item['lings_server_port']
                    lings_tts_port = server_item['lings_tts_port']
                    server_url = 'http://%s:%s' % (lings_server_address, lings_server_port)
                    tts_server_url = 'http://%s:%s' % (lings_server_address, lings_tts_port)
                    result = sendSoundmessage(sound_col, sound_id, sound_type=1, sound_file=sound_file,
                                              server_url=server_url, tts_url=tts_server_url)
            else:
                continue

    except Exception as e:
        mainlogger.info("动环音箱告警失败,error:%s" % e)


def deal_msg(db: ToMongo, rePool, conn, socketMacMap, mode, url, msg):
    try:
        if not msg or not conn:
            return socketMacMap
        ip, port = conn.getpeername()
        res = msg[-1]  # 截取最后一位
        num = int(res, 16)  # 16进制字符串->10进制整数
        binary_string = toBinary(num)  # 10进制 -> 二进制
        if socketMacMap:
            mac = socketMacMap.get(ip)
        else:
            socketMacMap = {}
            mac = None
        if not mac:
            conn.send(bytes.fromhex("000100000006FF0300640003"))
            data = conn.recv(1024)
            m = data.hex()[-12:]
            mac = ":".join([m[:2], m[2:4], m[4:6], m[6:8], m[8:10], m[10:12]])
            socketMacMap[ip] = mac
        if binary_string == "0000":
            return socketMacMap
        col = db.get_col('odin_dynamic_device')
        for i in range(4):
            # 1,2控制口是烟雾告警器，3,4控制口是浸水告警器
            if binary_string[i] == "0":
                continue
            controller_port = 4 - i
            query = {'mac_addr': mac, 'controller_port': controller_port}
            item = col.find_one(query)
            if not item:
                mainlogger.info("--无动环设备绑定，query：%s" % query)
                # 如果无动环设备绑定，则直接返回
                continue
            interval_time = item.get("emergency_interval_time")
            interval_time = int(interval_time) * 60 if interval_time else 2
            key = "KNDdevice" + str(controller_port) + ":" + mac
            flag = rePool.exists(key)
            if flag:
                # 同个康耐德-同个控制口，限制告警间隔2s
                continue
            else:
                value = 'true'
                rePool.setex(key, interval_time, value)

            # 插入到告警数据库
            insert_to_database(db, item)

            if mode == "1":
                # 联网模式 同步动环告警
                content = dict()
                content["macAddr"] = mac
                content["deviceNum"] = None
                content["controllerPort"] = controller_port
                sync_emergency(url, content)
        return socketMacMap

    except Exception as e:
        mainlogger.info("动环deal_msg error:%s" % traceback.format_exc())


class KNDserver:
    __instance = None
    __flag = False

    def __new__(cls, *args, **kwargs):
        # super().__new__(cls)
        if cls.__instance is None:
            cls.__instance = super().__new__(cls)
        return cls.__instance

    def __init__(self, context):
        if not KNDserver.__flag:
            KNDserver.__flag = True
            self.context = context
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            self.ip = "0.0.0.0"
            self.socket.bind((self.ip, 502))
            self.socket.listen(10)
            self.conn_list = []

            self.socketMacMap = {}
            self.my_db = ToMongo('wavedevice')

            self.rePool = redis_database

            self.check_status()  # 定时一分钟查询动环设备的状态

            self.mode, self.url = self.get_mode()  # 工作模式：0单机 1联网

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

    def accept_conn(self):
        while True:
            conn, add = self.socket.accept()
            mainlogger.info("--接收到康耐德连接请求： %s" % str(conn.getpeername()))
            self.conn_list = []
            self.conn_list.append(conn)

    def recv_message(self):
        mainlogger.info("--接收康耐德告警信息--")
        while True:
            if len(self.conn_list) > 0:
                for conn in self.conn_list:
                    while True:
                        try:
                            ip, port = conn.getpeername()
                            data = conn.recv(1024)
                            result = data.hex()  # 接收的康耐德信息 字节转16进制字符串
                            mainlogger.info("--接收的康奈德信息，ip:%s,message:%s" % (ip, result))
                            self.socketMacMap = deal_msg(self.my_db, self.rePool, conn, self.socketMacMap, self.mode,
                                                         self.url, result)
                        except Exception as e:
                            self.conn_list.remove(conn)
                            mac = self.socketMacMap.get(ip)
                            mainlogger.info("error:%s,客户端下线了,ip:%s,mac:%s" % (e, ip, mac))
                            continue

    def check_status(self):
        try:
            if not self.socketMacMap:
                return
            ipsMap = self.socketMacMap.copy()
            ips = ipsMap.keys()
            data = []
            for ip in ips:
                mac = self.socketMacMap.get(ip)
                result = CheckDeviceStatus(ip)
                status = 0 if result else 1
                item = {"device_status": status}
                query = {"mac_addr": mac}
                self.my_db.update("odin_dynamic_device", query, {"$set": item}, is_one=False)
                if status == 1:
                    del self.socketMacMap[ip]
                if self.mode == "1":
                    item = dict()
                    item["key"] = mac
                    item["status"] = str(status)
                    data.append(item)
            if self.mode == "1":
                sync_device_status(self.url, data)
        except Exception as e:
            mainlogger.info("动环check_status_error :%s" % e)
        finally:
            check_thread = threading.Timer(60, self.check_status)
            check_thread.start()

    def start(self):
        thread1 = KnadAcceptThread(self.context)
        thread2 = KnadRecvThread(self.context)
        # 开启新线程
        thread1.start()
        thread2.start()

        mainlogger.info("--开启发送接收线程")


class KnadAcceptThread(threading.Thread):
    def __init__(self, context):
        threading.Thread.__init__(self)

        self.context = context
        self.server = KNDserver(self.context)

    def run(self):
        self.server.accept_conn()


class KnadRecvThread(threading.Thread):
    def __init__(self, context):
        threading.Thread.__init__(self)

        self.context = context
        self.server = KNDserver(self.context)

    def run(self):
        self.server.recv_message()


if __name__ == '__main__':
    t = KNDserver()
    st = t.recv_message()

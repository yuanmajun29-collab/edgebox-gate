import socket
import threading
from Utils.utils import *
from .control_constuct import ControlSqlHelperv2

from Utils.db import ToMongo
from .Agreementunpack import *
from algorith_server.AgreementBuilder import *
from .redis_connect import redis_database
from .mqtt_service import MqttInstance

import Utils.logger as logger

mainlogger = logger.getLogger('main')


class AlgorithServer():
    __instance = None
    __flag = False

    def __new__(cls, *args, **kwargs):
        # super().__new__(cls)
        if cls.__instance is None:
            cls.__instance = super().__new__(cls)
        return cls.__instance

    def __init__(self, context):
        if not AlgorithServer.__flag:
            AlgorithServer.__flag = True
            self.context = context
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            self.ip = "0.0.0.0"
            self.socket.bind((self.ip, 6666))
            mainlogger.debug("绑定 IP %s , 端口 %s" % (self.ip, 6666))
            self.socket.listen(10)
            self.conn_list = []

            self.mqtt_instance = MqttInstance()
            self.client = self.mqtt_instance.client
            self.check_mqtt_status()

            self.my_db = ToMongo('wavedevice')

            self.Sms_sender = SendSmsResqueset()
            self.Sms_sender.get_sms_delivery()  # 启动时从数据库拉取短信投递任务

            self.web_sender = Sendwebrequest()
            self.web_sender.get_webhook_delivery()  # 启动时从数据库拉取告警转发任务

            self.re_pool = redis_database

    def check_mqtt_status(self):
        try:
            status = self.client.is_connected()
            if not status:
                self.client.reconnect()
                self.client.loop_start()
        except:
            self.mqtt_instance.mqtt_init()
            self.client = self.mqtt_instance.client
        check_thread = threading.Timer(10, self.check_mqtt_status)
        check_thread.start()

    def accept_conn(self):
        while True:
            conn, add = self.socket.accept()
            mainlogger.debug("接收到连接请求 %s" % str(conn.getpeername()))
            self.conn_list = []
            if conn.getpeername()[0] == "192.168.5.48":
                self.conn_list.append(conn)

    # 此处只能处理一个ALG的消息，需要优化
    def recv_message(self):
        mainlogger.debug("receive message")
        while True:
            if len(self.conn_list) > 0:
                for conn in self.conn_list:
                    msg_cache = b""
                    while True:
                        try:
                            data = conn.recv(65536)
                            conn_ip = conn.getpeername()[0]
                            mainlogger.debug(
                                "===============接收到alg端{}数据长度:{},前缀hex:{}".format(
                                    conn_ip, len(data), data[:64].hex() if data else ""
                                )
                            )
                            if not data:
                                break
                        except Exception as e:
                            mainlogger.debug('接受告警数据出错:%s' % e)
                            break
                        msg_head = data[0:2]
                        if msg_head == b'#!' and msg_cache:
                            msg_cache = b""
                            msg_cache += data
                        else:
                            msg_cache = msg_cache + data

                        msg_cache = judge_cache(msg_cache, mongo=self.my_db, mqtt_client=self.client,
                                                sms=self.Sms_sender, webhook=self.web_sender, re_pool=self.re_pool)

    def recv_hot_message(self, req):

        instance = handle_hikhotcam(req, mongo=self.my_db, mqtt_client=self.client, sms=self.Sms_sender,
                                    webhook=self.web_sender, re_pool=self.re_pool)

    def send_message(self, message, msgType=0):
        mainlogger.debug("send message")
        # 浅拷贝，防止过程中连接对象发生改变
        conn_list = self.conn_list.copy()

        if len(conn_list) == 0:
            mainlogger.debug("没有客户端连接 %s" % (conn_list))
            return

        for conn in conn_list:

            try:
                conn_name = conn.getpeername()
                mainlogger.debug('--连接有效，发送信息--')
            except:
                mainlogger.debug('--连接失效，移除连接--')
                self.conn_list.remove(conn)
                continue

            if msgType == 0:
                mainlogger.debug("发送信息 %s 消息内容: %s" % (conn_name, message))
            elif msgType == 1:
                mainlogger.debug("发送信息: 3005 消息内容: 提取人脸特征")
            elif msgType == 2:
                mainlogger.debug("发送信息: %s 消息类型: 3006" % str(conn_name))
                self.conn_list.remove(conn)

            conn.send(message.encode())

    def start(self):
        thread1 = AcceptThread(self.context)
        thread2 = RecvThread(self.context)
        # 开启新线程
        thread1.start()
        thread2.start()

        mainlogger.debug("开启发送接收线程")


class AcceptThread(threading.Thread):
    def __init__(self, context):
        threading.Thread.__init__(self)

        self.context = context
        self.server = AlgorithServer(self.context)

    def run(self):
        self.server.accept_conn()


class RecvThread(threading.Thread):
    def __init__(self, context):
        threading.Thread.__init__(self)

        self.context = context
        self.server = AlgorithServer(self.context)

    def run(self):
        self.server.recv_message()


class SenderThread(threading.Thread):
    def __init__(self, context):
        threading.Thread.__init__(self)
        self.context = context
        self.server = AlgorithServer(context)
        self.my_db = ToMongo('wavedevice')

    def start_controls_message(self):
        self.target = self.send_controls_message()
        self.start()

    def send_controls_message(self):
        helper = ControlSqlHelperv2(self.context, db_mongo=self.my_db)
        control_message = helper.build_controls_message()
        camera_message = helper.build_cameras_message()
        mainlogger.debug("发送布控信息--")
        mainlogger.debug("======布控信息control_message====={}".format(control_message))
        self.server.send_message(control_message)
        mainlogger.debug("发送布控信息完成--")

        mainlogger.debug("发送摄像头信息--")
        self.server.send_message(camera_message)
        mainlogger.debug("摄像头信息发送完毕--")

    def send_empty_control(self):
        empty_msg = []
        json_msg = json.dumps(empty_msg)
        camera_message = pack_3004_agreement(json_body=json_msg)
        mission_message = pack_init_agreement(json_body=json_msg)

        mainlogger.debug("发送布控信息--")
        self.server.send_message(mission_message)
        mainlogger.debug("发送布控信息完成--")

        mainlogger.debug("发送摄像头信息--")
        self.server.send_message(camera_message)
        mainlogger.debug("摄像头信息发送完毕--")

    def send_reboot_message(self):
        mainlogger.debug("发送算法重启信息--")
        reboot_message = alg_reboot()
        self.server.send_message(reboot_message, msgType=2)
        mainlogger.debug("算法重启信息发送完毕--")

    def send_face_message(self, facemsg: str):
        mainlogger.debug("发送人脸信息--")
        self.server.send_message(facemsg, msgType=1)
        mainlogger.debug("人脸信息发送完毕--")

    def send_3007_message(self):
        camera_change_message = pack_3007_agreement()
        self.server.send_message(camera_change_message)
        self.server.conn_list = []


class RecvHikHotThread(threading.Thread):
    def __init__(self, context, req):
        threading.Thread.__init__(self)

        self.context = context
        self.req = req
        self.server = AlgorithServer(self.context)

    def run(self):
        self.server.recv_hot_message(self.req)

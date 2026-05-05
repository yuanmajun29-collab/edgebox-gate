import socket
import selectors
import threading
from Utils.utils import *
from .control_constuct import ControlSqlHelperv2

from Utils.db import ToMongo
from .AgreementunpackV2 import *
from algorith_server.AgreementBuilder import *
from .redis_connect import redis_database
from .mqtt_service import MqttInstance

import Utils.logger as logger

mainlogger = logger.getLogger('main')

alg_selectors = selectors.DefaultSelector()


class AlgorithServerNew(threading.Thread):
    __instance = None
    __flag = False

    def __new__(cls, *args, **kwargs):
        # super().__new__(cls)
        if cls.__instance is None:
            cls.__instance = super().__new__(cls)
        return cls.__instance

    def __init__(self, context):
        if not AlgorithServerNew.__flag:
            AlgorithServerNew.__flag = True
            self.message_header_length = 55
            self.conn_list = []
            self.alg_msg_head = "#!0155"
            self.alg_socket_cache = dict()
            self.context = context
            self.my_db = ToMongo('wavedevice')

            self.mqtt_instance = MqttInstance()
            self.client = self.mqtt_instance.client
            self.check_mqtt_status()

            self.Sms_sender = SendSmsResqueset()
            self.Sms_sender.get_sms_delivery()  # 启动时从数据库拉取短信投递任务

            self.web_sender = Sendwebrequest()
            self.web_sender.get_webhook_delivery()  # 启动时从数据库拉取告警转发任务

            self.re_pool = redis_database
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            self.ip = "0.0.0.0"
            self.port = 6666
            self.socket.bind((self.ip, self.port))
            mainlogger.debug("绑定 IP %s , 端口 %s" % (self.ip, self.port))
            alg_selectors.register(self.socket, selectors.EVENT_READ, self.accept_conn)
            self.socket.listen(10)

        super(AlgorithServerNew, self).__init__()

    def start_handle_alg_message(self):
        mainlogger.debug("已启动socket server:{}:{}进行alg事件监听".format(self.ip, self.port))
        while True:
            events = alg_selectors.select()
            for key, mask in events:
                callback = key.data
                callback(key.fileobj)

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

    def accept_conn(self, server_socket):
        conn, client_addr = server_socket.accept()
        self.conn_list.append(conn)
        conn.setblocking(False)
        mainlogger.debug("接收到ALG连接请求: {}".format(client_addr))
        alg_selectors.register(conn, selectors.EVENT_READ, self.receive_alg_message)

    # 判断alg数据是否已接收完毕
    def judge_receive_complete(self, alg_data):
        # 判断数据是否可以进行处理分析
        alg_data_complete, can_handle_data, rest_data = False, None, None
        if len(alg_data) < self.message_header_length:
            return alg_data_complete, alg_data, rest_data
        message_body_length = int(alg_data[8:18])
        if len(alg_data[self.message_header_length:]) >= message_body_length:
            alg_data_complete = True
            can_handle_data = alg_data[: self.message_header_length + message_body_length]
            rest_data = alg_data[len(can_handle_data):]

        return alg_data_complete, can_handle_data, rest_data

    # 根据消息头进行消息切片
    def handle_message_splice(self, recv_message):
        last_message, new_message = "", ""
        # 判断是否包含消息头
        if self.alg_msg_head in recv_message:
            head_index = recv_message.index(self.alg_msg_head)
            if head_index != 0:
                last_message = recv_message[:head_index]
                new_message = recv_message[head_index:]
            else:
                new_message = recv_message
        else:
            last_message = recv_message

        return last_message, new_message

    def cache_handle_alg_message(self, client_socket, recv_message):
        last_message, new_message = self.handle_message_splice(recv_message)
        # 缓存消息中不包含该客户端的缓存信息
        if client_socket not in self.alg_socket_cache:
            if last_message:
                mainlogger.debug(
                    "未缓存该客户端数据,丢弃不合法数据:{},丢弃长度:{}。".format(last_message, len(last_message)))
        else:
            cached_item = self.alg_socket_cache[client_socket]
            cached_message = cached_item["msg_cache"]
            if last_message:
                cached_message += last_message
                # 未记录消息体长度
                cached_dict = {
                    "msg_cache": cached_message
                }
                if "msg_length" not in cached_item:
                    if len(cached_message) >= self.message_header_length:
                        msg_length = int(cached_message[8:18]) + self.message_header_length
                        cached_dict.update({
                            "msg_length": msg_length
                        })
                cached_item.update(cached_dict)

            # 判断上次的数据是否接收完整
            if "msg_cache" in cached_item and "msg_length" in cached_item:
                msg_cache = cached_item["msg_cache"]
                msg_length = cached_item["msg_length"]
                if len(msg_cache) == msg_length:
                    mainlogger.debug("缓存数据长度与数据总长度一致，正常处理。")
                    handle_alg_send_message(msg_cache, mongo=self.my_db, mqtt_client=self.client,
                                            sms=self.Sms_sender, webhook=self.web_sender, re_pool=self.re_pool)
                    del self.alg_socket_cache[client_socket]
                elif len(msg_cache) > msg_length:
                    mainlogger.debug("缓存数据长度:{},数据总长度:{}".format(len(msg_cache), msg_length))
                    handle_message = msg_cache[:msg_length]
                    handle_alg_send_message(handle_message, mongo=self.my_db, mqtt_client=self.client,
                                            sms=self.Sms_sender, webhook=self.web_sender, re_pool=self.re_pool)
                    if new_message:
                        mainlogger.debug("ALG缓存字节超过数据总字节，丢弃字节:{}".format(len(msg_cache) - msg_length))
                    else:
                        left_cache = msg_cache[msg_length:]
                        if len(left_cache) >= self.message_header_length:
                            # 剩下未处理的数据不合法，直接过滤
                            if not left_cache.startswith(self.alg_msg_head):
                                mainlogger.debug("ALG多出的字节不合法，丢弃字节:{}".format(len(msg_cache) - msg_length))
                            else:
                                left_cache_length = int(left_cache[8:18]) + self.message_header_length
                                self.alg_socket_cache.update({
                                    client_socket: {
                                        "msg_cache": msg_cache,
                                        "msg_length": left_cache_length
                                    }
                                })
                        else:
                            header_length = min(len(left_cache), len(self.alg_msg_head))
                            if left_cache[:header_length] != self.alg_msg_head[:header_length]:
                                pass
                            else:
                                self.alg_socket_cache.update({
                                    client_socket: {
                                        "msg_cache": msg_cache
                                    }
                                })
                else:
                    if new_message:
                        mainlogger.error("本次接收ALG消息失败，应接收:{},实际接收:{}".format(msg_length, len(msg_cache)))
                        del self.alg_socket_cache[client_socket]
                    else:
                        mainlogger.debug(
                            "ALG消息等待下一次接收，应接收数据总长度:{}，已接收数据长度:{}".format(msg_length,
                                                                                                 len(msg_cache)))

        # 为避免socket消息粘包，进行循环处理
        while new_message:
            cached_dict = {
                "msg_cache": new_message
            }
            msg_length = None
            if len(new_message) >= self.message_header_length:
                msg_length = int(new_message[8:18]) + self.message_header_length
                cached_dict.update({
                    "msg_length": msg_length
                })
            if not msg_length or len(new_message) < msg_length:
                self.alg_socket_cache.update({
                    client_socket: cached_dict
                })
                break

            handle_message = new_message[:msg_length]
            mainlogger.debug("接收到新数据长度与数据总长度一致，正常处理。")
            handle_alg_send_message(handle_message, mongo=self.my_db, mqtt_client=self.client,
                                    sms=self.Sms_sender, webhook=self.web_sender, re_pool=self.re_pool)
            new_message = new_message[msg_length:]

    # 处理alg客户端关闭
    def handle_alg_client_close(self, client_socket):
        try:
            if client_socket in self.alg_socket_cache:
                del self.alg_socket_cache[client_socket]
            if client_socket in self.conn_list:
                self.conn_list.remove(client_socket)
            alg_selectors.unregister(client_socket)
            client_socket.close()
        except Exception as e:
            mainlogger.error("handle_alg_client_close error: {}".format(e))

    def receive_alg_message(self, client_socket):
        try:
            mainlogger.debug("========receive alg message============")
            recv_data = client_socket.recv(65536)
            mainlogger.debug("接收到ALG客户端消息，消息内容：{}，消息长度：{}".format(recv_data, len(recv_data)))
            if not recv_data:
                mainlogger.debug("ALG客户端{}已经断开连接。".format(client_socket))
                self.handle_alg_client_close(client_socket)
            else:
                alg_decode_data = recv_data.decode()
                self.cache_handle_alg_message(client_socket, alg_decode_data)
                
                # errors="replace" 防止半包截断中文时崩溃，
                # 用 U+FFFD (?) 替代无法解码的字节
                # alg_decode_data = recv_data.decode("utf-8", errors="replace")
                # mainlogger.debug(
                #     "解码后字符长度:{}, 内容:{}".format(len(alg_decode_data), alg_decode_data)
                # )
                # self.cache_handle_alg_message(client_socket, alg_decode_data)
        except ConnectionResetError:
            mainlogger.error("alg客户端连接被重置。")
            self.handle_alg_client_close(client_socket)
        except Exception as e:
            mainlogger.error("处理alg消息异常:{}".format(e))
            self.handle_alg_client_close(client_socket)

    def recv_hot_message(self, req):

        instance = handle_hikhotcam(req, mongo=self.my_db, mqtt_client=self.client, sms=self.Sms_sender,
                                    webhook=self.web_sender, re_pool=self.re_pool)

    def send_alg_control_message(self, alg_conn, message):
        alg_conn.send(message.encode())

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

    def run(self):
        mainlogger.debug("已启动socket:{}进行alg事件监听".format(self.socket))
        try:
            while True:
                events = alg_selectors.select()
                for key, mask in events:
                    callback = key.data
                    callback(key.fileobj)
        except Exception as e:
            mainlogger.error("alg server error:{}".format(e))
        finally:
            alg_selectors.close()
            self.socket.close()


class SenderThread(threading.Thread):
    def __init__(self, context):
        threading.Thread.__init__(self)
        self.context = context
        self.server = AlgorithServerNew(context)
        self.my_db = ToMongo('wavedevice')

    def start_controls_message(self):
        self.target = self.send_controls_message()
        self.start()

    # 根据方向获取摄像头编号
    def query_camera_by_direction(self, directions):
        traffic_items = self.my_db.get_col("traffic_light_config").find()
        camera_list = list()
        for traffic_item in traffic_items:
            camera_direction = traffic_item['direction']
            camera_id_1 = traffic_item['camera_id']
            camera_id_2 = traffic_item['camera_id2']
            if camera_direction in directions:
                camera_list.append(camera_id_1)
                camera_list.append(camera_id_2)

        return camera_list

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
        self.server = AlgorithServerNew(self.context)

    def run(self):
        self.server.recv_hot_message(self.req)

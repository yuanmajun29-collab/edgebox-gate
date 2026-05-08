import uuid
import time
import socket
import selectors
import threading
from Utils import logger
from algorith_server.redis_connect import redis_database

cross_logger = logger.getLogger("cross")


class LightMessageController(threading.Thread):
    def __init__(self, direction, light_server_ip, light_server_port):
        self.client_socket = None
        self.direction = direction
        self.send_message = None
        self.recv_message = None
        self.handle_success = False
        self.send_message_uuid = None
        self.yellow_light_mode = None  # 1 普通模式 2 循环模式
        self.light_server_ip = light_server_ip
        self.light_server_port = light_server_port
        self.light_alive_interval = 30
        self.light_alive_thread = None
        self.client_socket = None
        self.light_selector = selectors.DefaultSelector()
        self.light_command_list = self.light_send_recv_list()
        super(LightMessageController, self).__init__()

    @staticmethod
    def light_send_recv_list():
        return [
            {
                "id": 1,
                "send": "01 10 00 96 00 03 06 00 00 00 00 00 00 00 E2",
                "recv": "01 10 00 96 00 03 60 24",
                "remark": "设置3路灯为普通模式"
            },
            {
                "id": 2,
                "send": "01 06 00 97 00 03 78 27",
                "recv": "01 06 00 97 00 03 78 27",
                "remark": "设置黄灯为循环模式"
            },
            {
                "id": 3,
                "send": "01 06 00 34 00 00 C8 04",
                "recv": "01 06 00 34 00 00 C8 04",
                "remark": "关闭所有"
            },
            {
                "id": 4,
                "send": "01 06 00 00 00 15 48 05",
                "recv": "01 06 00 00 00 15 48 05",
                "remark": "常亮红灯"
            },
            {
                "id": 5,
                "send": "01 06 00 01 00 97 99 A4",
                "recv": "01 06 00 01 00 97 99 A4",
                "remark": "慢闪黄灯"
            },
            {
                "id": 6,
                "send": "01 06 00 01 00 15 19 C5",
                "recv": "01 06 00 01 00 15 19 C5",
                "remark": "快闪黄灯"
            },
            {
                "id": 7,
                "send": "01 06 00 02 00 01 E9 CA",
                "recv": "01 06 00 02 00 01 E9 CA",
                "remark": "常亮绿灯"
            },
            {
                "id": 8,
                "send": "01 04 00 00 00 01 31 CA",
                "recv": "01 04 02 00 00 B9 30",
                "remark": "状态查询"
            }
        ]

    # 创建并注册socket客户端，处理红绿灯上报消息
    def create_register_socket_client(self):
        try:
            self.client_socket = self.create_client_socket()
            self.light_selector.register(self.client_socket, selectors.EVENT_READ, self.receive_light_message)
            # 首次建立socket客户端后，重置红绿灯服务端的模式设置
            self.init_light_mode()
            # 首次建立socket客户端后，启动子线程进行灯的状态检测
            self.light_alive_thread = threading.Thread(target=self.light_alive_check_thread)
            self.light_alive_thread.start()
        except Exception as e:
            cross_logger.error("create_register_socket_client error:{}".format(e))

    # 字节类型转成16进制字符串
    @staticmethod
    def bytes_to_hex_data(byte_list):
        hex_list = list()
        for byte_num in byte_list:
            hex_str = hex(byte_num)[2:].zfill(2).upper()
            hex_list.append(hex_str)

        return " ".join(hex_list)

    # 处理控制灯的指令，规定时间内未收到回复需要进行重试
    def handle_control_light_command(self, send_message):
        try:
            send_hex_data = self.bytes_to_hex_data(send_message)
            self.send_message = send_hex_data
            self.send_message_uuid = uuid.uuid1()
            self.client_socket.send(send_message)
            cross_logger.debug("{}路口首次发送指令{}。".format(self.direction, send_hex_data))
            # 每100ms检测一次消息回复的状态，每300ms进行一次重试，最多重试3次
            count = 0
            while count < 10:
                if count and not (count % 3):
                    cross_logger.debug("{}路口发送指令{}重试第{}次。".format(self.direction, send_hex_data, count // 3))
                    self.client_socket.send(send_message)
                if self.handle_success:
                    cross_logger.debug("{}路口指令{}已收到回复响应。".format(self.direction, send_hex_data))
                    break
                count += 1
                time.sleep(.1)
            # 重置收发消息缓存信息
            self.reset_message_cache()
        except Exception as e:
            cross_logger.error("handle_control_light_command error:{}".format(e))

    # 首次初始化灯的模式，红灯/绿灯：普通模式  黄灯：循环模式
    def init_light_mode(self):
        # 1.设置3路灯为普通模式
        common_mode_command = self.query_open_light_command(1)
        # 2.设置黄灯为循环模式
        yellow_cycle_command = self.query_open_light_command(2)
        for send_command in [common_mode_command, yellow_cycle_command]:
            self.handle_control_light_command(send_command)

    def execute_open_light(self, light_color, light_mode):
        try:
            if self.client_socket is None:
                cross_logger.debug("当前{}方向未建立socket连接，不处理开灯指令。".format(self.direction))
                return

            if light_color == 3:
                cross_logger.info("===========触发红绿灯开启绿灯 begin==========。".format(self.direction))

            open_light_commands = self.query_open_light_commands(light_color, light_mode)
            if not open_light_commands:
                return

            for open_light_command in open_light_commands:
                self.handle_control_light_command(open_light_command)

            if light_color == 3:
                cross_logger.info("===========触发红绿灯开启绿灯 end==========。".format(self.direction))
        except Exception as e:
            cross_logger.error("execute_open_light error:{}".format(e))

    def execute_close_light(self):
        # 关灯前先设置模式
        try:
            if self.client_socket is None:
                cross_logger.debug("当前{}方向未建立socket连接，不处理关灯指令。".format(self.direction))
                return
            common_mode_command = self.query_open_light_command(1)
            light_close_command = self.query_open_light_command(3)
            for send_command in [common_mode_command, light_close_command]:
                self.handle_control_light_command(send_command)
        except Exception as e:
            cross_logger.error("execute_close_light error:{}".format(e))

    # 获取开灯需要发送的指令列表
    def query_open_light_commands(self, light_color, light_mode):
        """
        light_color: 1:红灯 2:黄灯 3:绿灯
        light_mode: 1:常亮 2:闪烁
        """
        if light_color not in [1, 2, 3]:
            cross_logger.debug("未知的开灯指令：{}".format(light_color))
            return
        # 仅处理红灯/绿灯常亮，以及黄灯快闪
        if light_color == 1 and light_mode == 1:  # 红灯常亮
            light_on_command = self.query_open_light_command(4)
        elif light_color == 2 and light_mode == 2:  # 黄灯快闪
            light_on_command = self.query_open_light_command(6)
        elif light_color == 3 and light_mode == 1:  # 绿灯常亮
            light_on_command = self.query_open_light_command(7)
        else:
            cross_logger.debug("亮灯模式不合法，已过滤：{} {}".format(light_color, light_mode))
            return list()

        command_list = list()
        # 开启的是黄灯，设置为循环模式，其它灯设置为普通模式
        if light_color == 2:
            mode_command = self.query_open_light_command(2)
            command_list.append(mode_command)
        else:
            mode_command = self.query_open_light_command(1)
            command_list.append(mode_command)
        # 开灯之前先进行关灯
        close_command = self.query_open_light_command(3)
        command_list.append(close_command)
        command_list.append(light_on_command)

        return command_list

    # 获取指令编号对应的字节发送指令
    def query_open_light_command(self, cmd_id):
        send_command = None
        for light_send_recv_item in self.light_command_list:
            command_id = light_send_recv_item["id"]
            command_hex = light_send_recv_item["send"]
            if command_id == cmd_id:
                send_command = bytes.fromhex(command_hex)
                break
        return send_command

    # 重置消息缓存信息
    def reset_message_cache(self):
        self.send_message = None
        self.recv_message = None
        self.handle_success = False
        self.send_message_uuid = None

    def create_client_socket(self):
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect((self.light_server_ip, self.light_server_port))
        return client_socket

    def receive_light_message(self, client_socket):
        recv_data = client_socket.recv(8)
        # 对客户端消息进行解析，收到空字符串说明客户端已经断开连接
        if not recv_data:
            cross_logger.debug(
                "====light====路口：{}红绿灯服务端主动断开连接: {}:{}".format(self.direction, self.light_server_ip,
                                                                             self.light_server_port))
            self.light_selector.unregister(client_socket)
            client_socket.close()
            self.client_socket = None
        else:
            hex_data = self.bytes_to_hex_data(recv_data)
            cross_logger.debug("====light====路口：{}接收到红绿灯服务端消息：{},长度:{}".format(self.direction, hex_data,
                                                                                             len(recv_data)))
            # 将收到的信息转成16进制进行存储
            self.recv_message = hex_data
            self.judge_light_stay_alive()
            self.judge_light_mode_message()
            self.judge_message_handle_success()

    # 判断是否是灯在线回复
    def judge_light_stay_alive(self):
        light_alive_message = self.light_command_list[-1]["recv"]
        if self.recv_message == light_alive_message:
            redis_database.setex("{}_is_alive".format(self.light_server_ip), 60, value='1')

    # 判断是否是灯模式消息，需更新当前黄灯的模式
    def judge_light_mode_message(self):
        normal_mode_message = self.light_command_list[0]["recv"]
        cycle_mode_message = self.light_command_list[1]["recv"]
        if self.recv_message == normal_mode_message:
            self.yellow_light_mode = 1
        elif self.recv_message == cycle_mode_message:
            self.yellow_light_mode = 2

    # 判断消息正确处理
    def judge_message_handle_success(self):
        if not self.send_message or not self.recv_message or not self.send_message_uuid:
            return
        cross_logger.debug("=====judge_message_handle_success send_message:{} recv_message:{}".format(
            self.send_message,
            self.recv_message
        ))
        for light_send_recv_dict in self.light_command_list:
            send_message = light_send_recv_dict["send"]
            recv_message = light_send_recv_dict["recv"]
            if self.send_message == send_message and self.recv_message == recv_message:
                self.handle_success = True
                break
        return self.handle_success

    def light_alive_check_thread(self):
        while self.client_socket:
            check_status_command = self.query_open_light_command(8)
            if check_status_command:
                send_hex_data = self.bytes_to_hex_data(check_status_command)
                cross_logger.debug("====alive check thread send: {} {}====".format(self.light_server_ip, send_hex_data))
                self.client_socket.send(check_status_command)
            time.sleep(self.light_alive_interval)
        cross_logger.debug("====客户端socket关闭，退出灯状态检测====")

    def run(self):
        self.create_register_socket_client()
        while True:
            events = self.light_selector.select()
            for key, mask in events:
                callback = key.data
                callback(key.fileobj)

import json
import time
import socket
import threading
import datetime
import pytz

from Utils import logger
from Utils.db import ToMongo
from algorith_server.redis_connect import redis_database

beijing_tz = pytz.timezone('Asia/Shanghai')

cross_logger = logger.getLogger("cross")


class RadarClient:
    _instance = None  # 类变量，用于存储唯一的实例

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(RadarClient, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, 'initialized'):  # 确保只初始化一次
            self.should_run = True
            self.threads = []
            self.initialized = True  # 标记已初始化
            self.db = ToMongo('wavedevice')

    def create_connection(self, host, port, retry_delay=30):
        while self.should_run:
            try:
                client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                client_socket.connect((host, port))
                cross_logger.debug("----------连接到 {}:{} 成功----------".format(host, port))
                return client_socket
            except Exception as e:
                if not self.should_run:
                    break
                cross_logger.debug("连接{}:{}失败：{}，将在 {} 秒后重试...".format(host, port, e,retry_delay))
                time.sleep(retry_delay)
        return None

    def listen_for_messages(self, connection):
        try:
            while self.should_run:
                connection.settimeout(30)
                response = connection.recv(1024)
                if not response:
                    cross_logger.debug("连接已关闭或服务器无响应")
                    return True
                # 在这里维护雷达状态，用Redis设置超时时间
                server_ip = connection.getpeername()[0]
                redis_key = "{}_is_alive".format(server_ip)
                redis_database.setex(redis_key, 60, value='1')
                # Todo 在此根据红绿灯时间规则判断是否要写入数据库
                self.parse_json2save_mongo(server_ip, response)
        except Exception as e:
            if self.should_run:
                cross_logger.debug("监听消息失败：{}".format(e))
            return True
        return False

    def parse_json2save_mongo(self, server_ip, buffer):
        # cross_logger.debug(f"完整消息：{buffer.decode('utf-8')}")
        while True:
            try:
                # 尝试解析 JSON
                data, index = json.JSONDecoder().raw_decode(buffer.decode('utf-8'))
                # cross_logger.debug(f"收到来自服务器的消息：{data}")
                # 移除已处理的部分
                self.save2mongo(server_ip, data)
                buffer = buffer[index:].lstrip()
            except json.JSONDecodeError:
                # 如果无法解析，说明 buffer 中可能还没有完整的 JSON 消息
                # print("无法解析 JSON 消息，可能消息不完整")
                break

    def connect2radar(self, host, port, speed, sensitivity, anti_jam, direction, angle):
        while self.should_run:
            connection = self.create_connection(host, port)
            if connection:
                reconnect = False
                try:
                    self.set_radar(connection, speed, sensitivity, anti_jam, direction, angle)
                    reconnect = self.listen_for_messages(connection)
                    if not reconnect:
                        break
                except Exception as e:
                    cross_logger.debug("----------{}:{}通信失败：{}----------".format(host, port, e))
                finally:
                    if reconnect:
                        connection.close()
                        cross_logger.debug("----------{}:{}连接已关闭----------".format(host, port))
            else:
                cross_logger.debug("----------{}:{}无效的连接对象----------".format(host, port))
                time.sleep(2)
        cross_logger.debug("----------雷达{}:{}结束监听----------".format(host, port))

    def int2hex(self, n):
        if isinstance(n, str):
            n = int(n)
        return hex(n)[2:] if n >= 16 else '0{:X}'.format(n)

    def send_command(self, socket_server, cmd_code, param):
        try:
            hex_param = self.int2hex(param)
            cmd = cmd_code + hex_param
            msg = {"mb": cmd, "sn": 1, "ack": 1, "crc": 1}
            json_msg = json.dumps(msg)
            bytes_msg = json_msg.encode('utf-8')
            socket_server.send(bytes_msg)
            time.sleep(0.5)
        except Exception as e:
            raise Exception("Failed to send command {}: {}".format(cmd_code, e))

    def set_radar(self, socket_server, speed, sensitivity, anti_jam, direction, angle):
        try:
            # cross_logger.debug("{}设置雷达参数".format(socket_server), speed, sensitivity, anti_jam, direction, angle)
            cross_logger.debug("{}设置雷达参数: {} {} {} {} {}".format(socket_server, speed, sensitivity, anti_jam,
                                                                      direction, angle))
            commands = [
                ('0106025600', speed),
                ('0106025400', direction),
                ('0106025000', sensitivity),
                ('0106025800', anti_jam),
                ('0106025200', angle)
            ]
            for cmd_code, param in commands:
                self.send_command(socket_server, cmd_code, param)
        except Exception as e:
            raise Exception("Failed to set radar parameters: {}".format(e))

    def connect_to_multiple_servers(self, radar_configs):
        self.threads = []
        for radar_info in radar_configs:
            host = radar_info['host']
            port = radar_info['port']
            speed = radar_info['speed']
            sensitivity = radar_info['sensitivity']
            anti_jam = radar_info['anti_jam']
            direction = radar_info['direction']
            angle = radar_info['angle']
            thread = threading.Thread(target=self.connect2radar,
                                      args=(host, port, speed, sensitivity, anti_jam, direction, angle))
            thread.start()
            self.threads.append(thread)

    def stop_all_connections(self):
        self.should_run = False
        for thread in self.threads:
            thread.join()
        cross_logger.debug("----------雷达所有连接已关闭----------")

    def start_all_connections(self, radar_configs):
        self.should_run = True
        self.connect_to_multiple_servers(radar_configs)

    def save2mongo(self, server_ip, msg):
        # 只存这样的数据
        # {'id': '10c87eb3051607151a', 'time': '2024-07-30 16:22:49', 'Radar_1ch_speed': [0, 17]}
        if 'Radar_1ch_speed' in msg:
            speed = msg['Radar_1ch_speed'][1]
            if speed > 0:
                alert_time = datetime.datetime.strptime(msg['time'], '%Y-%m-%d %H:%M:%S')
                # 创建一个本地时间（北京时间）
                local_alert_time = alert_time  # 北京时间
                local_receive_at = datetime.datetime.now()  # 北京时间

                # 转换为UTC时间
                alert_time_utc = local_alert_time.astimezone(pytz.utc)
                receive_at_utc = local_receive_at.astimezone(pytz.utc)
                data = {
                    'device_identification': server_ip,
                    'alert_type': 'radar',
                    'alert_time': alert_time_utc,
                    'remark': speed,
                    'receive_at': receive_at_utc,
                }
                self.db.insert('alert_log', data)


if __name__ == "__main__":
    radar_client0 = RadarClient()
    print(id(radar_client0))
    radar_client0.stop_all_connections()
    time.sleep(1)
    # speed = 10, sensitivity = 5, anti_jam = 20, direction = 1, angle = 0
    radar_client1 = RadarClient()
    print(id(radar_client1))
    radar_configs = [
        {
            'host': '192.168.5.128',
            'port': 1030,
            'speed': 1,
            'sensitivity': 5,
            'anti_jam': 20,
            'direction': 1,
            'angle': 0
        },
        {
            'host': '192.168.5.129',
            'port': 1030,
            'speed': 1,
            'sensitivity': 5,
            'anti_jam': 20,
            'direction': 1,
            'angle': 0
        },
        {
            'host': '192.168.5.132',
            'port': 1030,
            'speed': 1,
            'sensitivity': 5,
            'anti_jam': 20,
            'direction': 1,
            'angle': 0
        },
        {
            'host': '192.168.5.133',
            'port': 1030,
            'speed': 1,
            'sensitivity': 5,
            'anti_jam': 20,
            'direction': 1,
            'angle': 0
        },
    ]
    radar_client1.start_all_connections(radar_configs)

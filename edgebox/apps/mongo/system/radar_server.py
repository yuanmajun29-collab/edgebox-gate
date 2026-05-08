import socket
import threading
import datetime
import time

import pytz
import selectors
import struct

from Utils import logger
from Utils.db import ToMongo
from config import MESSAGE_RADAR_VEHICLES
from algorith_server.redis_connect import redis_database
from msg_queue import radar_message_receive_queue, vehicle_pedestrian_events_queue

beijing_tz = pytz.timezone('Asia/Shanghai')

cross_logger = logger.getLogger("cross")

choose_selectors = selectors.DefaultSelector()


class RadarServer:
    _instance = None  # 类变量，用于存储唯一的实例

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(RadarServer, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, 'initialized'):  # 确保只初始化一次
            self.should_run = True
            self.threads = []
            self.server_socket = None
            self.initialized = True  # 标记已初始化
            self.db = ToMongo('wavedevice')
            self.message_recv_queue = radar_message_receive_queue
            self.start_radar_bytes = self.radar_header_bytes()

    # 在redis中记录雷达的在线状态0 离线 1 在线
    @staticmethod
    def save_redis_radar_status(radar_ip, is_online):
        redis_key = "{}_is_alive".format(radar_ip)
        redis_value = "1" if is_online else "0"
        redis_database.set(redis_key, redis_value)

    def handle_radar_receive_queue(self):
        while True:
            try:
                radar_client_tuple, receive_bytes = self.message_recv_queue.get()
                self.cycle_handle_radar_data(radar_client_tuple, receive_bytes)
            except Exception as e:
                cross_logger.error("handle_radar_receive_queue error: {}".format(e))

    def start_radar_message_thread(self):
        recv_threads = list()
        for i in range(4):
            recv_thread = threading.Thread(target=self.handle_radar_receive_queue)
            recv_threads.append(recv_thread)
        for recv_thread in recv_threads:
            recv_thread.start()

    def start_socket_server(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_tuple = ("0.0.0.0", 10086)
        self.server_socket.bind(server_tuple)
        self.server_socket.listen(10)
        self.server_socket.setblocking(False)
        cross_logger.debug("服务端socket服务建立成功。")
        self.start_radar_message_thread()
        # 注册文件描述符，文件描述符可读时进行处理
        choose_selectors.register(self.server_socket, selectors.EVENT_READ, self.listen_client_socket)
        try:
            while True:
                events = choose_selectors.select()
                for key, mask in events:
                    callback = key.data
                    callback(key.fileobj)
        except Exception as e:
            cross_logger.error("start_socket_server error: {}".format(e))
        finally:
            choose_selectors.close()
            self.server_socket.close()
        return True

    # 获取雷达数据开始的字节流
    def radar_header_bytes(self):
        header_hex = "53 5A 30"
        header_bytes = bytes.fromhex(header_hex)
        return header_bytes

    # 监听客户端信息，并记录客户端的套接字信息
    def listen_client_socket(self, server_socket):
        cross_logger.debug("处理客户端连接请求")
        conn, client_addr = server_socket.accept()
        conn.setblocking(False)
        cross_logger.debug("接收到客户端连接请求: {} {}".format(conn, client_addr))
        # 写入雷达的在线状态
        radar_ip = client_addr[0]
        # self.save_redis_radar_status(radar_ip, True)
        choose_selectors.register(conn, selectors.EVENT_READ, self.handle_client_message)

    def query_header_index_list(self, radar_data):
        start, indexes = 0, list()
        while True:
            start = radar_data.find(self.start_radar_bytes, start)
            cross_logger.debug("=========cycle_handle_radar_data 索引位置: {}=================".format(start))
            if start == -1:
                break
            indexes.append(start)
            start += 1

        return indexes

    # 为防止粘包或者接收不完整，进行循环处理
    def cycle_handle_radar_data(self, radar_client_tuple, radar_bytes_data):
        # 获取所有消息头开始的索引
        radar_head_indexes = self.query_header_index_list(radar_bytes_data)
        last_index = None
        for radar_head_index in radar_head_indexes:
            if last_index is None:
                last_index = radar_head_index
            else:
                handle_message = radar_bytes_data[last_index:radar_head_index]
                last_index = radar_head_index
                # 小于11个字节代表没车，不处理
                if len(handle_message) > 11:
                    self.parser_handle_radar_data(radar_client_tuple, handle_message)
        else:
            if last_index is not None:
                handle_message = radar_bytes_data[last_index:]
                if len(handle_message) > 11:
                    self.parser_handle_radar_data(radar_client_tuple, handle_message)

    def parser_handle_radar_data(self, radar_client_tuple, radar_message):
        parser_info = self.parser_byte_message(radar_message)
        # 进行数据解析，返回解析结果
        if parser_info:
            # 获取雷达的ip信息
            cross_logger.debug("===================准备存储雷达信息=================")
            radar_client_ip, radar_client_port = radar_client_tuple
            self.radar_message_into_queue(radar_client_ip, radar_client_port, parser_info)
            # 测试环境需要记录雷达客户端的端口，不能单独通过ip进行区分
            # self.save_radar_data_mongodb(radar_client_ip, parser_info, radar_client_port)

    # 处理socket客户端的发送消息
    def handle_client_message(self, client_socket):
        try:
            recv_data = client_socket.recv(64)
            # 对客户端消息进行解析，收到空字符串说明客户端已经断开连接
            radar_client_ip = client_socket.getpeername()[0]
            radar_client_port = int(client_socket.getpeername()[1])
            radar_client_tuple = (radar_client_ip, radar_client_port)
            if not recv_data:
                cross_logger.debug("雷达客户端{}已经断开连接。".format(client_socket))
                # self.save_redis_radar_status(radar_client_ip, False)
                choose_selectors.unregister(client_socket)
                client_socket.close()
            else:
                recv_data_hex = self.bytes_to_hex_data(recv_data)
                cross_logger.debug("接收到雷达客户端{}消息：{},长度:{}".format(radar_client_ip,
                                                                          recv_data_hex,
                                                                          len(recv_data)))
                if len(recv_data) > 11:
                    self.message_recv_queue.put((radar_client_tuple, recv_data))
        except ConnectionResetError as e:
            cross_logger.error("socket客户端连接被重置: {}".format(e))
            choose_selectors.unregister(client_socket)
            client_socket.close()
        except Exception as e:
            cross_logger.error("handle_client_message error: {}".format(e))
            choose_selectors.unregister(client_socket)
            client_socket.close()

    # 根据时间戳获取标准时间
    @staticmethod
    def query_standard_time(timestamp):
        standard_time = datetime.datetime.fromtimestamp(timestamp, tz=beijing_tz)
        standard_time = datetime.datetime.strftime(standard_time, "%Y-%m-%d %H:%M:%S")
        return standard_time

    def query_timestamp(self, first_data):
        occur_time_list = [hex(first_data[i])[2:].zfill(2) for i in range(3, 9)]
        occur_time_list.reverse()
        cross_logger.debug("16进制: {}".format(''.join(occur_time_list)))
        occur_time = int(''.join(occur_time_list), base=16)
        return occur_time

    @staticmethod
    def bytes_to_hex_data(byte_list):
        hex_list = list()
        for byte_num in byte_list:
            hex_str = hex(byte_num)[2:].zfill(2).upper()
            hex_list.append(hex_str)

        return " ".join(hex_list)

    # 获取车辆与雷达的水平和垂直距离，单位：米
    @staticmethod
    def query_vehicle_distance(vehicle_bytes_info):
        # h_list = [hex(vehicle_bytes_info[i])[2:].zfill(2) for i in range(0, 2)]
        v_list = [hex(vehicle_bytes_info[i])[2:].zfill(2) for i in range(2, 4)]
        # h_list.reverse()
        v_list.reverse()
        # h_distance = int(''.join(h_list), base=16) / 10
        v_distance = int(''.join(v_list), base=16) / 10
        unpack_tuple = struct.unpack("<h", vehicle_bytes_info[:2])
        h_distance = unpack_tuple[0] / 10
        return h_distance, v_distance

    def parser_byte_message(self, buffer):
        """
        雷达数据解析有车场景30字节的数据为例：
        53 5A 30 50 3A 27 9F 93 01 01 0A 00 DF 03 00 00 00 00 00 00 00 00 3C 00 00 01 2D 01 01 1A
        有车场景，字节范围说明：
        1-3: 固定消息头，3个字节
        4-9: 事件时间，6个字节
        10：车辆类型
        从第11个字节开始往后一共19个字节为单个车的数据信息：
        11-12: 雷达水平距离，2个字节，单位：分米(按有符号整型解析)
        13-14: 雷达垂直距离，2个字节，单位：分米(按无符号整型解析)
        15-22: 未知
        23: 车辆速度
        24-25：车辆航向角
        26：车道号
        27：车辆长度，单位：米
        28：车辆编号
        29：车辆类型 0 非机动车 1 小型车
        30：标志位
        """
        parser_result = dict()
        try:
            buffer_len = len(buffer)
            if buffer_len < 30:
                cross_logger.debug("不处理无车场景。")
                return parser_result
            # 查看时间戳信息
            event_timestamp = self.query_timestamp(buffer)
            standard_time = self.query_standard_time(event_timestamp // 1000)
            parser_result.update({
                "event_timestamp": event_timestamp,
                "event_time": standard_time,
                "vehicle_list": list()
            })
            # 未发现机动车或行人
            vehicle_info = buffer[10:]
            cross_logger.debug("=========解析信息 begin============")
            cross_logger.debug("事件时间：{}".format(standard_time))
            start_index = 1
            while len(vehicle_info) >= 19:
                split_info = vehicle_info[:19]
                # 车辆编号
                vehicle_id = split_info[-2]
                # 车辆类型
                vehicle_type = split_info[-1]
                # 车辆速度
                vehicle_speed = split_info[12]
                # 车辆长度
                vehicle_length = split_info[-3]
                # 车道号
                vehicle_road_id = split_info[-4]
                # 车辆距离雷达的水平距离、垂直距离
                vehicle_distance_h, vehicle_distance_v = self.query_vehicle_distance(split_info)
                cross_logger.debug("第{}辆车信息".format(start_index))
                cross_logger.debug("车辆信息：{}".format(split_info[-1]))
                cross_logger.debug("车辆水平位置离雷达中心线距离：{}m".format(vehicle_distance_h))
                cross_logger.debug("车辆垂直位置离雷达距离：{}m".format(vehicle_distance_v))
                cross_logger.debug("车辆速度：{}km/h".format(vehicle_speed))
                cross_logger.debug("车道号：{}".format(vehicle_road_id))
                cross_logger.debug("车辆长度：{}m".format(vehicle_length))
                cross_logger.debug("车辆编号：{}".format(vehicle_id))
                vehicle_info = vehicle_info[19:]
                parser_result["vehicle_list"].append({
                    "vehicle_id": vehicle_id,
                    "vehicle_type": vehicle_type,
                    "vehicle_speed": vehicle_speed,
                    "vehicle_length": vehicle_length,
                    "vehicle_road_id": vehicle_road_id,
                    "vehicle_distance_h": vehicle_distance_h,
                    "vehicle_distance_v": vehicle_distance_v
                })
                start_index += 1
            cross_logger.debug("=========解析信息 end============")
        except Exception as e:
            cross_logger.debug(e)
        return parser_result

    # 获取雷达的方向信息
    def query_radar_direction(self, radar_client_ip, radar_client_port):
        radar_direction = None
        config_col = self.db.get_col("traffic_light_config")
        config_items = config_col.find({}, {'_id': 0})
        query_key = "{}:{}".format(radar_client_ip, radar_client_port)
        for config_item in config_items:
            # 如果端口未配置，根据ip地址进行雷达信息匹配
            direction = config_item["direction"]
            radar_ip, radar_port, _ = config_item["radar_ip"].split("#")
            if radar_port:
                if query_key == "{}:{}".format(radar_ip, radar_port):
                    radar_direction = direction
                    break
            else:
                if radar_client_ip == radar_ip:
                    radar_direction = direction
                    break

        return radar_direction

    # 将雷达来车消息放到队列里面
    def radar_message_into_queue(self, radar_client_ip, radar_client_port, parser_info):
        # event_timestamp = parser_info["event_timestamp"]
        event_timestamp = int(time.time() * 1000)
        vehicle_list = parser_info["vehicle_list"]
        for vehicle_item in vehicle_list:
            vehicle_id = vehicle_item["vehicle_id"]
            vehicle_distance_v = vehicle_item["vehicle_distance_v"]
            # 放到队列里面的消息依次为：发送ip和port元组、车辆编号、雷达垂直距离、事件时间戳、消息类型
            radar_queue_message = ((radar_client_ip, radar_client_port), vehicle_id, vehicle_distance_v,
                                   event_timestamp, MESSAGE_RADAR_VEHICLES)
            vehicle_pedestrian_events_queue.put(radar_queue_message)

    # 存储雷达客户端上报的数据
    def save_radar_data_mongodb(self, radar_client_ip, parser_info, radar_client_port):
        # 获取当前时间
        receive_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        save_mongo_data = {
            "radar_ip": radar_client_ip,
            "event_timestamp": parser_info["event_timestamp"],
            "event_time": parser_info["event_time"],
            "receive_time": receive_time,
            "radar_port": radar_client_port
        }
        vehicle_list = parser_info["vehicle_list"]
        if vehicle_list:
            for vehicle_item in vehicle_list:
                additional_dict = {
                    "vehicle_id": vehicle_item["vehicle_id"],
                    "vehicle_type": vehicle_item["vehicle_type"],
                    "vehicle_speed": vehicle_item["vehicle_speed"],
                    "vehicle_length": vehicle_item["vehicle_length"],
                    "vehicle_road_id": vehicle_item["vehicle_road_id"],
                    "vehicle_distance_h": vehicle_item["vehicle_distance_h"],
                    "vehicle_distance_v": vehicle_item["vehicle_distance_v"]
                }
                self.db.insert('radar_data_record', dict({**save_mongo_data, **additional_dict}))

    def int2hex(self, n):
        if isinstance(n, str):
            n = int(n)
        return hex(n)[2:] if n >= 16 else '0{:X}'.format(n)


if __name__ == "__main__":
    try:
        radar_server = RadarServer()
        radar_server.start_socket_server()
    except Exception as e:
        cross_logger.debug(e)

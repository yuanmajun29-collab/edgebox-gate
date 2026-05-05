import socket
import time
import threading

from Utils import logger
from algorith_server.redis_connect import redis_database
from system.mongo_search import recognize_road_conditions

cross_logger = logger.getLogger("cross")


def calculate_crc16(data: bytes) -> str:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc = crc >> 1
    number = ((crc & 0xff) << 8) + (crc >> 8)
    return '%04X' % (number)


def byte2str(data: bytes) -> str:
    res = []
    for byte in data:
        if byte < 16:
            res.append('0' + hex(byte)[2:])
        else:
            res.append(hex(byte)[2:])
    return ''.join(res)


class TrafficLightClient:
    # 0:红灯 1:绿灯 2:黄灯
    LIGHT_COLOR_MAP = {0: b'\x98', 1: b'\x96', 2: b'\x97'}

    CHANEL_MAP = {0: b'\x02', 1: b'\x00', 2: b'\x01'}

    def __init__(self, host, port, byte_addr):
        self.host = host
        self.port = port
        self.byte_addr = byte_addr
        self.socket_client = None
        redis_database.delete('light_status_{}'.format(host))
        redis_database.delete('road_condition')

    def connect(self, retry_delay=1, max_retries=50):
        retry_times = 0
        while retry_times < max_retries:
            try:
                self.socket_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.socket_client.connect((self.host, self.port))
                cross_logger.debug("红绿灯 {}:{} 连接成功".format(self.host, self.port))
                return True
            except Exception as e:
                retry_times += 1
                cross_logger.debug(
                    "红绿灯 {}:{} 连接失败：{}，将在{}秒后第{}次重试...".format(self.host, self.port, e, retry_delay, retry_times))
                time.sleep(retry_delay)

        raise ConnectionError("无法连接到红绿灯 {}:{}，已达到最大重试次数".format(self.host, self.port))

    def send_and_recv(self, cmd, max_retries=20):
        if not self.socket_client:
            raise RuntimeError("尚未建立连接，请先调用 connect() 方法")
        cmd_str = byte2str(cmd)
        for attempt in range(max_retries):
            cross_logger.debug("{}次尝试发送命令：{}到{}:{}".format(attempt + 1, cmd_str, self.host, self.port))
            try:
                crccode = calculate_crc16(cmd)
                cmd_all = cmd + bytes.fromhex(crccode)
                self.socket_client.send(cmd_all)
                str_cmd = byte2str(cmd_all)
                self.socket_client.settimeout(0.2)
                recv_data = self.socket_client.recv(8)
                recv_data_str = byte2str(recv_data)
                cross_logger.debug("发送命令：{}到{}:{}，返回数据：{}".format(cmd_str,self.host,self.port,recv_data_str))
                if cmd_str[2:4] == "04" and recv_data_str[2:4] == "04":
                    # 对于查询请求
                    # todo 交通灯在线，执行相应操作
                    redis_database.setex("{}_is_alive".format(self.host), 60, value='1')
                    cross_logger.debug("{}交通灯在线，更新交通灯状态".format(self.host))
                    pass
                elif cmd_str[2:4] == "10" and recv_data_str[2:4] != "10":
                    # 切换回正常模式的请求，如果失败，则重新尝试发送
                    cross_logger.debug('{}切换回正常模式的请求，如果失败，则重新尝试发送'.format(self.host))
                    continue  # 重新尝试发送
                elif recv_data_str != str_cmd:
                    if str_cmd == '0110009600030600000000000000e2' and recv_data_str == '0110009600036024':
                        '''
                           X1. 设置1~3路为普通模式
                        [10:56:15.526]发→◇01 10 00 96 00 03 06 00 00 00 00 00 00 00 E2 
                        [10:56:15.579]收←◆01 10 00 96 00 03 60 24 
                        '''
                        break  # 成功退出循环
                    continue  # 重新尝试发送
                break  # 成功退出循环

            except socket.timeout:
                cross_logger.debug(
                    "----------第{}次尝试发送命令：{}到{}:{} 接收超时---------------".format(attempt + 1,cmd_str, self.host, self.port))
            except Exception as e:
                cross_logger.debug(
                    "----------第{}次尝试发送命令：{}到{}:{}通讯失败：{}---------------".format(attempt + 1, cmd_str, self.host, self.port,e))
            if attempt == max_retries - 1:
                cross_logger.debug(
                    "----------第{}次尝试发送命令,{}到{}:{}达到最大重试次数，重新连接---------------".format(attempt+1, cmd_str, self.host, self.port))
                self.connect()

    def set_light(self, color, mode):
        # 设置红绿灯颜色及闪烁方式
        color_intro = {0: '绿灯', 1: '红灯', 2: '黄灯'}
        mode_intro = {0: '爆闪', 1: '常亮', 2: '闪烁'}

        if color not in (0, 1, 2) or mode not in (0, 1, 2):
            raise ValueError("color or mode must be 0, 1, or 2")
        cross_logger.debug(
            "尝试设置地址 {}:{} 的灯光: 【{} | {}】".format(self.host, self.port, color_intro.get(color), mode_intro.get(mode)))
        light_bit = self.LIGHT_COLOR_MAP.get(color)
        if mode == 1:
            bytecode_setmode = self.byte_addr + b'\x06\x00' + light_bit + b'\x00\x00'
            self.send_and_recv(bytecode_setmode)
            chanel_bit = self.CHANEL_MAP.get(color)
            light_code = self.byte_addr + b'\x06\x00' + chanel_bit + b'\x00\x01'
            self.send_and_recv(light_code)
        else:
            bytecode_setmode = self.byte_addr + b'\x06\x00' + light_bit + b'\x00\x03'
            self.send_and_recv(bytecode_setmode)
            if mode == 2:
                flashing_bit = b'\x97'
            else:
                flashing_bit = b'\x15'
            chanel_bit = self.CHANEL_MAP.get(color)
            light_code = self.byte_addr + b'\x06\x00' + chanel_bit + b'\x00' + flashing_bit
            self.send_and_recv(light_code)
        redis_database.set('light_status_{}'.format(self.host), color)

    def close_light(self):
        cross_logger.debug("尝试关闭地址 {}:{} 的灯光".format(self.host, self.port))
        # 三路先切换回正常模式
        bytecode_return_normal = self.byte_addr + b'\x10\x00\x96\x00\x03\x06\x00\x00\x00\x00\x00\x00'
        self.send_and_recv(bytecode_return_normal)
        # 关闭所有输出
        bytecode_stop = self.byte_addr + b'\x06\x00\x34\x00\x00'
        self.send_and_recv(bytecode_stop)
        redis_database.set('light_status_{}'.format(self.host), -1)

    def check_light_status(self):
        bytecode = self.byte_addr + b'\x04\x00\x00\x00\x01'
        cross_logger.debug('====== {}:{} 检查红绿灯状态======'.format(self.host, self.port))
        self.send_and_recv(bytecode)

    def open_light(self, color, mode):
        # 开灯前先从Redis查看当前灯光颜色
        current_color = redis_database.get('light_status_{}'.format(self.host))
        if current_color is None:
            cross_logger.debug('====== {}:{} 当前灯光状态为空，直接开灯======'.format(self.host, self.port))
            self.set_light(color, mode)
        elif int(current_color) == color:
            cross_logger.debug('====== {}:{}当前灯光颜色与目标颜色相同，保持不变======'.format(self.host, self.port))
        else:
            cross_logger.debug('====== {}:{}先关灯，再开灯======'.format(self.host, self.port))
            self.close_light()
            self.set_light(color, mode)

    def control_light(self, color, mode, duration):
        def light_thread():
            self.set_light(color, mode)
            time.sleep(duration)
            self.close_light()

        thread = threading.Thread(target=light_thread)
        thread.start()
        return thread  # 返回线程对象，以便调用者可以选择等待它完成

    def open_light_thread(self, color, mode):
        def light_thread():
            self.open_light(color, mode)

        thread = threading.Thread(target=light_thread)
        thread.start()
        return thread  # 返回线程对象，以便调用者可以选择等待它完成

    def close_light_thread(self):
        thread = threading.Thread(target=self.close_light)
        thread.start()
        return thread  # 返回线程对象，以便调用者可以选择等待它完成


def connect_all_lights(light_configs):
    cross_logger.debug("开始连接所有灯")
    threads = []
    clients = {}
    for config in light_configs:
        # 创建线程
        t = TrafficLightClient(config['host'], config['port'], config['byte_addr'])
        thread = threading.Thread(target=t.connect, args=(config,))
        thread.start()
        threads.append(thread)
        clients[config.get('direction')] = t
    # 等待所有线程完成
    for thread in threads:
        thread.join()
    # 关闭所有灯
    threads = []
    for t in clients.values():
        thread = threading.Thread(target=t.close_light())
        thread.start()
        threads.append(thread)
    for thread in threads:
        thread.join()
    return clients


def single_direction(main_client, other_clients, green_time, yellow_time):
    thread_main = main_client.open_light_thread(0, 1)
    for another_client in other_clients:
        another_client.open_light_thread(1, 1)
    time.sleep(green_time)
    thread_main.join()
    thread_main = main_client.open_light_thread(2, 0)
    time.sleep(yellow_time)
    thread_main.join()


def mixed_direction(main_group_clients, other_group_clients, green_time, yellow_time):
    thread_mains_1 = []
    for main_client in main_group_clients:
        m_t = main_client.open_light_thread(0, 1)
        thread_mains_1.append(m_t)
    thread_others = []
    for another_client in other_group_clients:
        o_t = another_client.open_light_thread(1, 1)
        thread_others.append(o_t)
    time.sleep(green_time)
    for t_m in thread_mains_1:
        t_m.join()
    thread_mains_2 = []
    for main_client in main_group_clients:
        m_t2 = main_client.open_light_thread(2, 0)
        thread_mains_2.append(m_t2)
    for t_m2 in thread_mains_2:
        t_m2.join()
    for t_o in thread_others:
        t_o.join()
    time.sleep(int(yellow_time))


def sort_clients(clients, directions):
    # 默认顺时针排序，有方向信息时取第一个方向顺时针排序
    order = ['1', '2', '3', '4']
    if not directions:
        first_direction = '1'
    else:
        first_direction = directions[0]
    start_index = order.index(first_direction)
    sorted_keys = order[start_index:] + order[:start_index]
    return {key: clients[key] for key in sorted_keys if key in clients}


def run_single_direction(clients, ruler, directions=None):
    cross_logger.debug("开始进行单向通行")
    redis_database.set('road_condition', 'run_single_direction')
    direction_setting = ruler.get('direction_setting')
    yellow_time = ruler.get('yellow_light_time')
    clients = sort_clients(clients, directions)
    for c in clients:
        other_clients = [clients[i] for i in clients if i != c]
        green_time = direction_setting[c]
        single_direction(clients[c], other_clients, green_time, yellow_time)


def run_mixed_direction(clients, ruler, directions=None):
    cross_logger.debug("开始进行混合通行")
    redis_database.set('road_condition', 'run_mixed_direction')
    direction_setting = ruler.get('direction_setting')
    yellow_time = ruler.get('yellow_light_time')
    main_direction_group = direction_setting['main_direction_group']
    main_direction_group_time = direction_setting['main_direction_group_time']
    other_direction_group_time = direction_setting['other_direction_group_time']
    cross_logger.debug(
        "主方向组：{}, 主方向组时间：{}, 其他方向组时间：{}".format(main_direction_group, main_direction_group_time,other_direction_group_time))
    main_group_clients = [clients[d] for d in direction_setting['main_direction_group']]
    other_group_clients = [clients[d] for d in set(clients.keys()) - set(main_direction_group)]
    cross_logger.debug("当前路面车辆方向为：{}".format(directions))
    if directions is None:
        directions = []
    if (not directions) or (len(directions) > 2) or set(main_direction_group) == set(directions):
        mixed_direction(main_group_clients, other_group_clients, main_direction_group_time, yellow_time)
        mixed_direction(other_group_clients, main_group_clients, other_direction_group_time, yellow_time)
    else:
        mixed_direction(other_group_clients, main_group_clients, other_direction_group_time, yellow_time)
        mixed_direction(main_group_clients, other_group_clients, main_direction_group_time, yellow_time)


def light_all_direction_yellow(clients, time_seconds):
    yellow_time = time_seconds
    thread_list = []
    for main_client in clients.values():
        m = main_client.open_light_thread(2, 0)
        thread_list.append(m)
    for m in thread_list:
        m.join()
    time.sleep(yellow_time)


def light_one_direction_green_other_red(clients, direction, time_seconds):
    # 一个方向亮绿灯，其他方向亮红灯
    main_client = clients[direction]
    other_client_list = [clients[i] for i in clients if i != direction]
    thread_main = main_client.open_light_thread(0, 1)
    for other_client in other_client_list:
        other_client.open_light_thread(1, 1)
    thread_main.join()
    time.sleep(time_seconds)


def light_one_direction_yellow(clients, direction, time_seconds):
    # 一个方向亮黄闪,其他关闭
    main_client = clients[direction]
    thread_main = main_client.open_light_thread(2, 0)
    other_client_list = [clients[i] for i in clients if i != direction]
    for other_client in other_client_list:
        other_client.close_light_thread()
    thread_main.join()
    time.sleep(time_seconds)


def run_normal_mode(clients):
    # 全部黄闪
    redis_database.set('road_condition', 'run_normal_mode')
    light_all_direction_yellow(clients, time_seconds=30)


def smart_mode_pre_recognition(clients):
    # 进入智能通行，黄闪5秒
    road_condition_before = redis_database.get('road_condition')
    # 注意从Redis读取到的是bytes类型
    cross_logger.debug("----------road_condition_before{}----------".format(road_condition_before))
    if road_condition_before != b'no_pedestrian_no_vehicle':
        yellow_time = 1
        light_all_direction_yellow(clients, yellow_time)
    else:
        yellow_time = 1
        light_one_direction_yellow(clients, '1', yellow_time)
    condition = recognize_road_conditions()
    road_condition_now = condition.get('road_condition')
    cross_logger.debug("----------road_condition_now{}----------".format(road_condition_now))
    if road_condition_before == b'no_pedestrian_no_vehicle' and road_condition_now != 'no_pedestrian_no_vehicle':
        cross_logger.debug("============之前无人无车，现在有人或车============")
        yellow_time = 1
        light_all_direction_yellow(clients, yellow_time)
        condition = recognize_road_conditions()
    return condition


def run_smart_mode(clients, ruler):
    cross_logger.debug("开始进行智能通行")
    cross_logger.debug('=======ruler:{}======='.format(ruler))
    condition = smart_mode_pre_recognition(clients)
    cross_logger.debug("----------当前路面情况{}----------".format(condition))
    road_condition = condition.get('road_condition')
    directions = condition.get('directions')
    redis_database.set('road_condition', road_condition)
    if road_condition == 'has_pedestrian':
        cross_logger.debug('有行人')
        pedestrian_traffic_time = ruler.get('pedestrian_traffic_time')
        light_all_direction_yellow(clients, time_seconds=pedestrian_traffic_time)
    elif road_condition == 'one_direction_vehicle':
        cross_logger.debug('一个方向有来车')
        vehicle_traffic_time = ruler.get('vehicle_traffic_time')
        light_one_direction_green_other_red(clients, direction=directions[0], time_seconds=vehicle_traffic_time)
    elif road_condition == 'multi_direction_vehicles':
        cross_logger.debug('多个方向有来车')
        traffic_mode = ruler.get('traffic_mode')
        if traffic_mode == 2:
            run_single_direction(clients, ruler, directions)
        else:
            run_mixed_direction(clients, ruler, directions)
    else:
        cross_logger.debug('无人无车')


def check_all_light_status(clients):
    cross_logger.debug("30秒发送一次检测指令，检测所有灯是否存活，Redis写入状态TTL为60秒")
    while 1:
        for client in clients.values():
            thread = threading.Thread(target=client.check_light_status)
            thread.start()
        time.sleep(30)


def check_all_light_status_thead(clients):
    thread = threading.Thread(target=check_all_light_status, args=(clients,))
    thread.start()

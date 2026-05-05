import time
import pytz
import datetime
import threading
from Utils import logger
from Utils.db import ToMongo
from msg_queue import vehicle_pedestrian_events_queue
from system.mongo_search_v2 import HandleRoadCondition
from algorith_server.redis_connect import redis_database
from config import MESSAGE_RADAR_VEHICLES, MESSAGE_CAMERA_VEHICLES, MESSAGE_CAMERA_PEDESTRIAN

cross_logger = logger.getLogger("cross")

beijing_tz = pytz.timezone('Asia/Shanghai')


class CrossRoadsAccessControl:
    _instance = None

    def __init__(self, light_controls, ruler_now, power_save_modify, first_enter_mode):
        self.my_db = ToMongo('wavedevice')
        self.light_controls = light_controls
        self.ruler_now = ruler_now
        self.power_save_modify = power_save_modify
        self.first_enter_mode = first_enter_mode
        self.light_directions = self.query_all_light_directions()
        self.light_color_maps = {1: "红灯", 2: "黄灯", 3: "绿灯"}
        self.light_mode_maps = {1: "常亮", 2: "闪烁"}
        self.redis_vehicle_timeout = 5
        self.radar_vehicle_distance = 40  # 雷达检测到有车的有效距离
        # 0代表省电模式开启 1代表省电模式关闭
        self.power_save = int(self.ruler_now.get("power_save", "1"))
        self.power_save_enable = True if not self.power_save else False
        self.pedestrian_traffic_time = self.ruler_now.get('pedestrian_traffic_time')
        self.vehicle_traffic_time = self.ruler_now.get('vehicle_traffic_time')
        self.yellow_light_time = self.ruler_now.get('yellow_light_time')
        self.camera_maps, self.radar_maps = self.query_camera_direction_map()
        # 只初始化一次
        if not hasattr(self, 'initialized'):
            self.initialized = True
            self.radar_vehicle_near_mode = False
            self.radar_vehicle_near = list()
            self.start_thread_handle_queue()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @staticmethod
    def query_standard_time(timestamp):
        standard_time = datetime.datetime.fromtimestamp(timestamp, tz=beijing_tz)
        standard_time = datetime.datetime.strftime(standard_time, "%Y-%m-%d %H:%M:%S.%f")
        return standard_time

    @staticmethod
    def query_redis_camera_direction(redis_camera_keys, cache_timeout):
        camera_directions = list()
        for redis_camera_key in redis_camera_keys:
            redis_camera_key = redis_camera_key.decode("utf-8")
            vehicle_direction = redis_camera_key.split(":")[-1]
            camera_timestamp = redis_database.get(redis_camera_key)
            if camera_timestamp:
                camera_timestamp = camera_timestamp.decode("utf-8")
                if int(camera_timestamp) >= cache_timeout:
                    camera_directions.append(vehicle_direction)
        return camera_directions

    def start_thread_handle_queue(self):
        t = threading.Thread(target=self.handle_vehicle_pedestrian_queue)
        t.start()

    # 获取摄像头编号和方向的映射关系
    def query_camera_direction_map(self):
        config_col = self.my_db.get_col("traffic_light_config")
        config_items = config_col.find({}, {'_id': 0})
        camera_maps, radar_maps = dict(), dict()
        for config_item in config_items:
            radar_info = config_item["radar_ip"]
            radar_ip, radar_port, _ = radar_info.split("#")
            camera_id_1 = config_item["camera_id"]
            camera_id_2 = config_item["camera_id2"]
            direction = config_item["direction"]
            # 元组的最后一个数值标识摄像头的位置
            camera_maps.update({
                camera_id_1: (direction, 1),
                camera_id_2: (direction, 2)
            })
            # 对于雷达，配置了端口的话根据ip:port确定雷达客户端唯一性
            if radar_port:
                radar_key = "{}:{}".format(radar_ip, radar_port)
                radar_maps.update({
                    radar_key: direction
                })
            else:
                radar_maps.update({
                    radar_ip: direction
                })
        return camera_maps, radar_maps

    # 根据雷达客户端的ip和端口确定雷达的方向
    def query_radar_direction(self, radar_ip, radar_port):
        radar_direction = None
        radar_ip_port = "{}:{}".format(radar_ip, radar_port)
        for radar_config, radar_config_direction in self.radar_maps.items():
            # 配置表中未配置端口，根据ip确定雷达方向
            if ":" not in radar_config:
                if radar_config == radar_ip:
                    radar_direction = radar_config_direction
                    break
            else:
                if radar_config == radar_ip_port:
                    radar_direction = radar_config_direction
                    break
        return radar_direction

    def handle_vehicle_pedestrian_queue(self):
        while True:
            try:
                receive_tuple = vehicle_pedestrian_events_queue.get()
                message_type = receive_tuple[-1]
                if message_type == MESSAGE_RADAR_VEHICLES:
                    addr_tuple, vehicle_id, vehicle_distance, event_timestamp = receive_tuple[:4]
                    radar_ip, radar_port = addr_tuple
                    radar_direction = self.query_radar_direction(radar_ip, radar_port)
                    if radar_direction:
                        self.save_cache_radar_vehicles(radar_direction, vehicle_id, vehicle_distance, event_timestamp)
                elif message_type == MESSAGE_CAMERA_VEHICLES:
                    camera_id, event_timestamp = receive_tuple[:2]
                    if camera_id not in self.camera_maps:
                        cross_logger.debug("算法传递的设备编号不存在，已过滤")
                        continue
                    direction, camera_position = self.camera_maps[camera_id]
                    self.save_cache_camera_vehicles(direction, camera_position, event_timestamp)
                elif message_type == MESSAGE_CAMERA_PEDESTRIAN:
                    camera_id, event_timestamp = receive_tuple[:2]
                    if camera_id not in self.camera_maps:
                        cross_logger.debug("算法传递的设备编号不存在，已过滤")
                        continue
                    direction, camera_position = self.camera_maps[camera_id]
                    self.save_redis_camera_pedestrian(direction, camera_position, event_timestamp)
            except Exception as e:
                cross_logger.error("handle_vehicle_pedestrian_queue error: {}".format(e))

    # 将雷达消息保存到redis
    def save_cache_radar_vehicles(self, direction, vehicle_id, vehicle_distance, event_timestamp):
        redis_key = "radar_vehicles:{}-{}".format(direction, vehicle_id)
        radar_value = redis_database.get(redis_key)
        cache_timeout = int((time.time() - self.redis_vehicle_timeout) * 1000)
        if radar_value:
            radar_value = radar_value.decode()
            radar_records = radar_value.split(",")
            append_list = list()
            for radar_record in radar_records:
                radar_timestamp, _ = radar_record.split("-")
                if cache_timeout <= int(radar_timestamp):
                    append_list.append(radar_record)
            add_val = "{}-{}".format(event_timestamp, vehicle_distance)
            append_list.append(add_val)
            # 至多存储两条
            set_val = ",".join(append_list[-2:])
            redis_database.setex(redis_key, self.redis_vehicle_timeout, set_val)
        else:
            set_val = "{}-{}".format(event_timestamp, vehicle_distance)
            redis_database.setex(redis_key, self.redis_vehicle_timeout, set_val)

    # 摄像头检测到车
    def save_cache_camera_vehicles(self, direction, camera_position, event_timestamp):
        if camera_position == 1:
            query_key = "camera_near_vehicle:{}".format(direction)
        else:
            query_key = "camera_far_vehicle:{}".format(direction)

        redis_database.setex(query_key, self.redis_vehicle_timeout, event_timestamp)

    def save_redis_camera_pedestrian(self, direction, camera_position, event_timestamp):
        cross_logger.debug("摄像头{}检测到{}方向有行人".format(camera_position, direction))
        if camera_position == 1:
            redis_database.setex("camera_near_pedestrian", self.redis_vehicle_timeout, event_timestamp)

    # 获取当前路况
    def query_current_road_condition_v2(self):
        # 只判定redis中是否有数据，不判断时间戳
        road_condition_result = {
            "road_condition": "no_pedestrian_no_vehicle",
            "vehicle_directions": list(),  # 车辆来车方向，结合雷达和摄像头的判定结果
            "radar_vehicles": list(),
            "near_camera_vehicles": list(),
            "radar_near_vehicles": list(),
            "camera_far_vehicles": list()
        }

        # 先判断是否有行人
        pedestrian_timestamp = redis_database.get("camera_near_pedestrian")
        if pedestrian_timestamp:
            road_condition_result.update({
                "road_condition": "has_pedestrian"
            })
            return road_condition_result

        # 判断近点摄像头检测到车辆
        vehicle_near_directions = list()  # 雷达判断即将来车方向
        vehicle_directions = list()
        far_camera_vehicles = list()
        near_camera_vehicles = list()
        radar_vehicles = list()
        camera_near_vehicle_keys = redis_database.keys("camera_near_vehicle*")
        for camera_near_vehicle_key in camera_near_vehicle_keys:
            camera_near_vehicle_key = camera_near_vehicle_key.decode()
            vehicle_direction = camera_near_vehicle_key.split(":")[-1]
            radar_record = redis_database.get(camera_near_vehicle_key)
            if radar_record:
                vehicle_timestamp = radar_record.decode()
                vehicle_timestamp = int(vehicle_timestamp) / 1000
                camera_occur_time = self.query_standard_time(vehicle_timestamp)
                near_camera_vehicles.append((vehicle_direction, camera_occur_time))
            vehicle_directions.append(vehicle_direction)

        road_condition_result.update({
            "near_camera_vehicles": near_camera_vehicles
        })

        # 判断雷达检测到车辆
        radar_vehicle_keys = redis_database.keys("radar_vehicles:*")
        for radar_vehicle_key in radar_vehicle_keys:
            radar_vehicle = radar_vehicle_key.decode("utf-8")
            radar_detail = radar_vehicle.split(":")[-1]
            radar_direction, vehicle_id = radar_detail.split("-")
            # 近点摄像头已判定该方向有车，不用继续判断雷达
            if radar_direction in vehicle_directions:
                continue
            radar_record = redis_database.get(radar_vehicle_key)
            if radar_record:
                radar_record = radar_record.decode("utf-8")
                radar_save_list = radar_record.split(",")
                radar_save_list = radar_save_list[-2:]
                # 数据不足两条，无法分析来向去向，直接过滤
                if len(radar_save_list) < 2:
                    continue
                # 来向才进行处理
                radar_analytic_list = list()
                for radar_save_info in radar_save_list:
                    radar_event_timestamp, radar_distance = radar_save_info.split("-")
                    radar_analytic_list.append((int(radar_event_timestamp), float(radar_distance)))

                radar_first_time = radar_analytic_list[0][0] / 1000
                radar_second_time = radar_analytic_list[-1][0] / 1000
                radar_current_distance = radar_analytic_list[-1][-1]
                is_near = radar_current_distance < radar_analytic_list[0][-1]
                radar_first_time = self.query_standard_time(radar_first_time)
                radar_second_time = self.query_standard_time(radar_second_time)
                if is_near:
                    if radar_current_distance < self.radar_vehicle_distance:
                        radar_vehicles.append(
                            (radar_direction, radar_current_distance, radar_first_time, radar_second_time))
                        vehicle_directions.append(radar_direction)
                    else:
                        vehicle_near_directions.append(radar_direction)

        road_condition_result.update({
            "radar_vehicles": radar_vehicles
        })

        # 雷达和近点摄像头已经判断有车辆，无需进行远点摄像头判断
        if vehicle_directions:
            # 方向去重
            vehicle_directions = list(set(vehicle_directions))
            if len(vehicle_directions) > 1:
                road_condition_result.update({
                    "road_condition": "multi_direction_vehicles",
                    "vehicle_directions": vehicle_directions
                })
            else:
                road_condition_result.update({
                    "road_condition": "one_direction_vehicle",
                    "vehicle_directions": vehicle_directions
                })
            return road_condition_result

        # 判断远点摄像头检测到车辆
        camera_far_keys = redis_database.keys("camera_far_vehicle:*")
        for camera_far_key in camera_far_keys:
            camera_far_key = camera_far_key.decode()
            camera_far_direction = camera_far_key.split(":")[-1]
            far_camera_vehicles.append(camera_far_direction)

        road_condition_result.update({
            "radar_near_vehicles": vehicle_near_directions,
            "camera_far_vehicles": far_camera_vehicles
        })

        return road_condition_result

    # 获取当前路况
    def query_current_road_condition(self):
        # 可能存在redis中依然有数据，但是事件发生的时间戳已经超过了判定时间戳，要结合redis中的数据和数据的时间戳综合判断
        road_condition_result = {
            "road_condition": "no_pedestrian_no_vehicle",
            "vehicle_directions": list(),
            "radar_near_vehicles": list(),
            "camera_far_vehicles": list()
        }
        cache_timeout = int((time.time() - self.redis_vehicle_timeout) * 1000)

        # 先判断是否有行人
        pedestrian_timestamp = redis_database.get("camera_near_pedestrian")
        if pedestrian_timestamp:
            pedestrian_timestamp = pedestrian_timestamp.decode()
            if int(pedestrian_timestamp) >= cache_timeout:
                road_condition_result.update({
                    "road_condition": "has_pedestrian"
                })
                return road_condition_result

        # 判断近点摄像头检测到车辆
        vehicle_near_directions = list()  # 雷达判断即将来车方向
        camera_near_vehicle_keys = redis_database.keys("camera_near_vehicle*")
        vehicle_directions = self.query_redis_camera_direction(camera_near_vehicle_keys, cache_timeout)

        # 判断雷达检测到车辆
        radar_vehicle_keys = redis_database.keys("radar_vehicles:*")
        for radar_vehicle_key in radar_vehicle_keys:
            radar_vehicle = radar_vehicle_key.decode("utf-8")
            radar_detail = radar_vehicle.split(":")[-1]
            radar_direction, vehicle_id = radar_detail.split("-")
            # 近点摄像头已判定该方向有车，不用继续判断雷达
            if radar_direction in vehicle_directions:
                continue
            radar_record = redis_database.get(radar_vehicle_key)
            if radar_record:
                radar_record = radar_record.decode("utf-8")
                radar_save_list = radar_record.split(",")
                radar_save_list = radar_save_list[-2:]
                # 数据不足两条，无法分析来向去向，直接过滤
                if len(radar_save_list) < 2:
                    continue
                # 来向才进行处理
                radar_analytic_list = list()
                for radar_save_info in radar_save_list:
                    radar_event_timestamp, radar_distance = radar_save_info.split("-")
                    radar_analytic_list.append((int(radar_event_timestamp), float(radar_distance)))

                radar_analytic_list = sorted(radar_analytic_list, key=lambda x: x[0])
                # redis中记录的时间戳小于判定时间戳，直接过滤
                min_timestamp = radar_analytic_list[0][0]
                if int(min_timestamp) < cache_timeout:
                    continue
                radar_current_distance = radar_analytic_list[-1][-1]
                is_near = radar_current_distance < radar_analytic_list[0][-1]
                if is_near:
                    if radar_current_distance < self.radar_vehicle_distance:
                        vehicle_directions.append(radar_direction)
                    else:
                        vehicle_near_directions.append(radar_direction)

        # 雷达和近点摄像头已经判断有车辆，无需进行远点摄像头判断
        if vehicle_directions:
            # 方向去重
            vehicle_directions = list(set(vehicle_directions))
            if len(vehicle_directions) > 1:
                road_condition_result.update({
                    "road_condition": "multi_direction_vehicles",
                    "vehicle_directions": vehicle_directions
                })
            else:
                road_condition_result.update({
                    "road_condition": "one_direction_vehicle",
                    "vehicle_directions": vehicle_directions
                })
            return road_condition_result

        # 判断远点摄像头检测到车辆
        camera_far_keys = redis_database.keys("camera_far_vehicle:*")
        far_camera_vehicles = self.query_redis_camera_direction(camera_far_keys, cache_timeout)

        road_condition_result.update({
            "radar_near_vehicles": vehicle_near_directions,
            "camera_far_vehicles": far_camera_vehicles
        })

        return road_condition_result

    # 获取所有灯的方向
    def query_all_light_directions(self):
        return list(self.light_controls.keys())

    # 解析道路状态查询数据
    def parser_road_collect_data(self, collect_data):
        road_condition_result = {
            "road_condition": "no_pedestrian_no_vehicle",
            "directions": list(),
            "radar_detail": dict(),
            "camera_far_vehicles": list()
        }
        if collect_data.get("pedestrian"):
            road_condition_result.update({
                "road_condition": "has_pedestrian"
            })
            return road_condition_result

        near_vehicles = collect_data["camera_near_vehicles"]
        far_vehicles = collect_data["camera_far_vehicles"]
        radar_vehicles = collect_data["radar_vehicles"]
        # 远点摄像头识别到车不判定有车，需结合雷达判断
        road_condition_result.update({
            "camera_far_vehicles": far_vehicles
        })
        # 记录识别到车的方向
        vehicle_directions = near_vehicles
        for radar_direction, radar_distance in radar_vehicles:
            road_condition_result["radar_detail"].update({
                radar_direction: radar_distance
            })
            # 雷达检测距离小于车辆检测距离，判定为有车
            if float(radar_distance) <= self.radar_vehicle_distance:
                vehicle_directions.append(radar_direction)

        # 对检测到有车的方向进行去重
        vehicle_unique_directions = list(set(vehicle_directions))
        road_condition_result.update({
            "directions": vehicle_unique_directions
        })
        if len(vehicle_unique_directions) > 1:
            road_condition_result.update({
                "road_condition": "multi_direction_vehicles"
            })
        elif len(vehicle_unique_directions) == 1:
            road_condition_result.update({
                "road_condition": "one_direction_vehicle"
            })
        else:
            road_condition_result.update({
                "road_condition": "no_pedestrian_no_vehicle"
            })

        return road_condition_result

    # 获取当前道路分析结果
    def query_road_analytic_result(self):
        start_time = datetime.datetime.now()
        cross_logger.debug("查询分析结果begin: {}".format(start_time.strftime("%Y-%m-%d %H:%M:%S.%f")))
        collect_data = HandleRoadCondition().query_current_road_state()
        road_condition_result = self.parser_road_collect_data(collect_data)
        end_time = datetime.datetime.now()
        cross_logger.debug("查询分析结果end: {}".format(end_time.strftime("%Y-%m-%d %H:%M:%S.%f")))
        cross_logger.debug("查询分析结果耗时: {}s".format((end_time - start_time).total_seconds()))
        cross_logger.debug("=============人和车采集结果：{}".format(collect_data))
        # 单方向来车需要休眠0.5s进行二次数据采集
        if road_condition_result["road_condition"] == "one_direction_vehicle":
            cross_logger.debug("当前分析结果为单方向来车，休眠0.5s后进行二次数据采集。")
            time.sleep(0.5)
            collect_data = HandleRoadCondition().query_current_road_state()
            road_condition_result = self.parser_road_collect_data(collect_data)
            return road_condition_result

        return road_condition_result

    # 进行普通模式通行
    def run_normal_mode_access(self):
        redis_database.set('road_condition', 'run_normal_mode')
        self.handle_light_multi_threads(self.light_directions, 2, 2)
        time.sleep(30)

    # 获取执行单向通行的通行顺序
    def query_direction_orders(self, access_directions):
        if not access_directions:
            run_directions = self.light_directions
        elif len(access_directions) == 1:
            access_direction = access_directions[0]
            start_index = self.light_directions.index(access_direction)
            run_directions = self.light_directions[start_index:] + self.light_directions[:start_index]
        else:
            sorted_access_directions = sorted(access_directions)
            start_direction, walk_steps = sorted_access_directions[0], 0
            for sorted_access_direction in sorted_access_directions:
                start_index = self.light_directions.index(sorted_access_direction)
                handle_list = self.light_directions[start_index:] + self.light_directions[:start_index]
                need_steps, judge_list = 1, list()
                for handle_direction in handle_list:
                    judge_list.append(handle_direction)
                    if not (set(access_directions) - set(judge_list)):
                        break
                    need_steps += 1
                if not walk_steps or need_steps < walk_steps:
                    start_direction = sorted_access_direction
                    walk_steps = need_steps
            start_index = self.light_directions.index(start_direction)
            run_directions = self.light_directions[start_index:] + self.light_directions[:start_index]

        return run_directions

    # 进行单向通行
    def run_one_direction_access(self, access_directions=None):
        cross_logger.debug("开始进行单向通行")
        redis_database.set('road_condition', 'run_single_direction')
        direction_setting = self.ruler_now.get('direction_setting')
        if not access_directions:
            run_directions = self.light_directions
        else:
            # 确保等待时间最短，从没车的最大方向往后开始亮灯
            run_directions = self.query_direction_orders(access_directions)

        # 记录已经处于红灯状态的方向
        red_light_dict = dict()
        for light_direction in self.light_directions:
            red_light_dict.update({
                light_direction: False
            })
        for run_direction in run_directions:
            green_time = direction_setting[run_direction]
            # 先其它方向进入红灯状态
            red_directions = [light_direction for light_direction in self.light_directions if
                              light_direction != run_direction and not red_light_dict[light_direction]]
            for red_direction in red_directions:
                red_light_dict.update({
                    red_direction: True
                })
            self.handle_light_multi_threads(red_directions, 1, 1)
            # 当前方向绿灯之后进入黄闪，由于只处理一个方向，不开启线程
            self.light_controls[run_direction].execute_open_light(3, 1)
            time.sleep(green_time)
            self.light_controls[run_direction].execute_open_light(2, 2)
            time.sleep(self.yellow_light_time)
            red_light_dict.update({
                run_direction: False
            })

    # 批量处理亮绿灯到黄闪
    def batch_handle_green_lights(self, red_directions, green_directions, green_time, yellow_time):
        self.handle_light_multi_threads(red_directions, 1, 1)
        self.handle_light_multi_threads(green_directions, 3, 1)
        time.sleep(green_time)
        self.handle_light_multi_threads(green_directions, 2, 2)
        time.sleep(yellow_time)

    # 进行混合通行
    def run_mix_directions_access(self, access_directions=None):
        cross_logger.debug("开始进行混合通行")
        redis_database.set('road_condition', 'run_mixed_direction')
        direction_setting = self.ruler_now.get('direction_setting')
        main_direction_group = direction_setting['main_direction_group']
        main_direction_group_time = direction_setting['main_direction_group_time']
        other_direction_group_time = direction_setting['other_direction_group_time']
        cross_logger.debug(
            "主方向组：{}, 主方向组时间：{}, 其他方向组时间：{}".format(main_direction_group, main_direction_group_time,
                                                                     other_direction_group_time))

        main_directions = [d for d in self.light_directions if d in direction_setting['main_direction_group']]
        other_directions = list(set(self.light_directions) - set(main_directions))
        cross_logger.debug("当前路面车辆方向为：{}".format(access_directions))
        # 最先来车方向是主方向，则主方向先亮灯，否则其它方向先亮灯
        if not access_directions or access_directions[-1] in main_directions:
            self.batch_handle_green_lights(other_directions, main_directions, main_direction_group_time,
                                           self.yellow_light_time)
            self.batch_handle_green_lights(main_directions, other_directions, other_direction_group_time,
                                           self.yellow_light_time)
        else:
            self.batch_handle_green_lights(main_directions, other_directions, other_direction_group_time,
                                           self.yellow_light_time)
            self.batch_handle_green_lights(other_directions, main_directions, main_direction_group_time,
                                           self.yellow_light_time)

    # 处理单方向来车通行
    def handle_one_direction_access(self, access_direction):
        red_directions = [light_direction for light_direction in self.light_directions if
                          light_direction != access_direction]
        self.handle_light_multi_threads(red_directions, 1, 1)
        self.light_controls[access_direction].execute_open_light(3, 1)
        time.sleep(self.vehicle_traffic_time)

    # 处理多方向来车通行
    def handle_multi_directions_access(self, access_directions):
        traffic_mode = self.ruler_now.get('traffic_mode')
        if traffic_mode == 2:
            self.run_one_direction_access(access_directions)
        else:
            self.run_mix_directions_access(access_directions)

    # 多线程处理控制灯指令
    def handle_light_multi_threads(self, directions, color, mode, need_wait=True):
        new_threads = list()
        for direction in directions:
            handle_control_obj = self.light_controls[direction]
            new_thread = threading.Thread(target=handle_control_obj.execute_open_light, args=(color, mode))
            new_threads.append(new_thread)
        for new_thread in new_threads:
            new_thread.start()
        if need_wait:
            for new_thread in new_threads:
                new_thread.join()

    # 处理智能通行逻辑
    def run_smart_mode(self):
        if self.first_enter_mode:
            cross_logger.debug("首次进入智能通行，四灯黄闪10s。")
            for direction in self.light_directions:
                handle_light_obj = self.light_controls[direction]
                handle_light_obj.execute_open_light(2, 2)
            time.sleep(10)
        cross_logger.debug('=======ruler:{}======='.format(self.ruler_now))
        # 获取上一次道路的情况
        last_road_condition = redis_database.get('road_condition')
        last_vehicle_directions = redis_database.lrange("vehicle_directions", 0, -1)
        # 从redis读取出来的是byte类型，需要进行类型转化
        last_road_condition = last_road_condition.decode() if last_road_condition else ""
        last_vehicle_directions = list(map(lambda x: x.decode(), last_vehicle_directions))
        road_condition_result = self.query_current_road_condition_v2()
        cross_logger.debug("----------当前路面情况{}----------".format(road_condition_result))
        road_condition = road_condition_result.get('road_condition')
        radar_vehicles = road_condition_result.get('radar_vehicles')
        near_camera_vehicles = road_condition_result.get('near_camera_vehicles')
        vehicle_directions = road_condition_result.get('vehicle_directions')
        radar_near_vehicles = road_condition_result.get("radar_near_vehicles")
        camera_far_vehicles = road_condition_result.get("camera_far_vehicles")
        # 将当前的道路情况记录到redis
        redis_database.set('road_condition', road_condition)
        if vehicle_directions:
            while True:
                del_direction = redis_database.rpop("vehicle_directions")
                if del_direction is None:
                    break
            redis_database.rpush('vehicle_directions', *vehicle_directions)
        cross_logger.debug("前一次路况: {}, 本次路况: {}".format(last_road_condition, road_condition))
        cross_logger.debug(
            "last_vehicle_directions: {}, now_vehicle_directions: {}".format(last_vehicle_directions,
                                                                             vehicle_directions))
        # 当前有人或有车，重置黄闪超时时间以及雷达即将来车方向
        if road_condition == 'has_pedestrian':
            cross_logger.debug('检测到有行人')
            # 所有方向亮黄闪，维持10s
            self.handle_light_multi_threads(self.light_directions, 2, 2)
            time.sleep(self.pedestrian_traffic_time)
        # 一个方向有来车
        elif road_condition == 'one_direction_vehicle':
            vehicle_direction = vehicle_directions[0]
            cross_logger.info(
                '路口判断结果: 单方向有来车: {}，雷达识别：{}，近点摄像头识别：{}'.format(vehicle_direction,
                                                                                      radar_vehicles,
                                                                                      near_camera_vehicles))
            # 判断该方向上一次是否也为有车，且记录了上次来车的方向信息
            if last_road_condition == "one_direction_vehicle" and last_vehicle_directions:
                # 上一次来车方向和本次来车方向一致，由于上次亮的就是绿灯，可不处理
                last_vehicle_direction = last_vehicle_directions[0]
                cross_logger.debug(
                    '前次来车方向: {} type: {}'.format(last_vehicle_direction, type(last_vehicle_direction)))
                if last_vehicle_direction == vehicle_direction:
                    time.sleep(self.vehicle_traffic_time)
                else:
                    # 前次来车方向设置为黄闪
                    self.light_controls[last_vehicle_direction].execute_open_light(2, 2)
                    time.sleep(self.yellow_light_time)
                    self.handle_one_direction_access(vehicle_direction)
            else:
                # 前次无车或者前次多方向来车，此时没有灯处于绿灯状态，处理逻辑一致
                self.handle_one_direction_access(vehicle_direction)
        elif road_condition == 'multi_direction_vehicles':
            cross_logger.info(
                '路口判断结果: 多方向有来车: {}，雷达识别：{}，近点摄像头识别：{}'.format(",".join(vehicle_directions),
                                                                                      radar_vehicles,
                                                                                      near_camera_vehicles))
            # 由于只有前次单方向来车时，才会有绿灯，此时需要操作该绿灯进入黄闪
            if last_road_condition == "one_direction_vehicle" and last_vehicle_directions:
                last_vehicle_direction = last_vehicle_directions[0]
                self.light_controls[last_vehicle_direction].execute_open_light(2, 2)
                time.sleep(self.yellow_light_time)
                # 前次来车方向黄闪4s后正常处理多方向来车逻辑
                self.handle_multi_directions_access(vehicle_directions)
            # 前次也为多方向来车，需要保持和前次亮灯顺序一致
            elif last_road_condition == "multi_direction_vehicles" and last_vehicle_directions:
                self.handle_multi_directions_access(last_vehicle_directions)
            else:
                self.handle_multi_directions_access(vehicle_directions)
        else:
            cross_logger.debug('处理未检测到行人和车逻辑')
            # 远点摄像头识别到车，且雷达也识别到该方向有来车，当前处于等待雷达来车模式，直接判定该方向有车
            judge_vehicle_directions = list(set(camera_far_vehicles) & set(radar_near_vehicles))
            if judge_vehicle_directions:
                cross_logger.info(
                    "路口判断结果: 检测到路口雷达和远点摄像头都识别到有车，雷达识别：{}，远点摄像头识别：{}".format(
                        radar_near_vehicles,
                        camera_far_vehicles)
                )
                while True:
                    del_direction = redis_database.rpop("vehicle_directions")
                    if del_direction is None:
                        break
                redis_database.rpush('vehicle_directions', *judge_vehicle_directions)
                if len(judge_vehicle_directions) > 1:
                    redis_database.set('road_condition', "multi_direction_vehicles")
                    self.handle_multi_directions_access(judge_vehicle_directions)
                else:
                    redis_database.set('road_condition', "one_direction_vehicle")
                    self.handle_one_direction_access(judge_vehicle_directions[0])
                self.radar_vehicle_near_mode = False
                return
            else:
                if self.power_save_enable:
                    # 雷达检测到有来车，且未进入等待雷达来车模式，进入四灯黄闪
                    if radar_near_vehicles and not self.radar_vehicle_near_mode:
                        cross_logger.info(
                            "路口判断结果: 省电模式下，雷达识别到{}方向即将来车".format(radar_near_vehicles))
                        self.radar_vehicle_near_mode = True
                        cross_logger.debug(
                            "省电模式进入等待雷达来车模式，来车方向：{}，保持四灯黄闪，最多持续{}s。".format(
                                radar_near_vehicles, self.vehicle_traffic_time))
                        for direction in self.light_directions:
                            handle_light_obj = self.light_controls[direction]
                            handle_light_obj.execute_open_light(2, 2)
                        return
                    # 雷达未检测到有来车，当前等待雷达来车模式等待超时，重置回省电模式状态
                    elif not radar_near_vehicles and self.radar_vehicle_near_mode:
                        cross_logger.info("路口判断结果: 省电模式下，等待雷达方向来车，四灯黄闪超时。")
                        yellow_direction = self.light_directions[0]
                        close_directions = self.light_directions[1:]
                        self.light_controls[yellow_direction].execute_open_light(2, 2)
                        for light_direction in close_directions:
                            self.light_controls[light_direction].execute_close_light()
                        self.radar_vehicle_near_mode = False
                        return

            # 前一次也是未检测到人和车，且省电模式未改变，不进行操作
            if last_road_condition == "no_pedestrian_no_vehicle" and not self.power_save_modify:
                cross_logger.debug("前次无人无车，本次无人无车，且省电模式未改变，不进行处理。")
                return
            # 上一次是单方向来车，由于上次方向此时还是处于绿灯状态，需要进入黄闪
            elif last_road_condition == "one_direction_vehicle" and last_vehicle_directions:
                last_vehicle_direction = last_vehicle_directions[0]
                self.light_controls[last_vehicle_direction].execute_open_light(2, 2)
                time.sleep(self.yellow_light_time)
            redis_database.delete('vehicle_directions')
            # 检查省电模式是否开启
            if self.power_save_enable:
                cross_logger.debug('省电模式已开启，处理省电模式逻辑')
                # 方向1黄闪，其他方向灯灭
                yellow_direction = self.light_directions[0]
                close_directions = set(self.light_directions)
                close_directions.remove(yellow_direction)
                self.light_controls[yellow_direction].execute_open_light(2, 2)
                for light_direction in close_directions:
                    self.light_controls[light_direction].execute_close_light()
            else:
                cross_logger.debug('=======开始控制灯颜色')
                # 进行四灯黄闪10S
                for direction in self.light_directions:
                    self.light_controls[direction].execute_open_light(2, 2)

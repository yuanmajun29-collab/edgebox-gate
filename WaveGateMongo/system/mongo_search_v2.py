from datetime import datetime, timedelta, timezone
from Utils.db import ToMongo
from Utils import logger

cross_logger = logger.getLogger("cross")


class HandleRoadCondition:
    def __init__(self):
        self.my_db = ToMongo('wavedevice')
        self.query_before_seconds = 10
        self.camera_maps, self.radar_maps = self.query_camera_direction_map()
        self.search_start_timestamp = self.query_search_start_timestamp()

    # 获取查询开始的时间戳(单位：毫秒数值)
    def query_search_start_timestamp(self):
        current_time = datetime.now() - timedelta(seconds=self.query_before_seconds)
        micro_timestamp = current_time.timestamp() * 1000
        return micro_timestamp

    # 获取当前路口的运行状态，包括：有人、有车、无人无车
    def query_current_road_state(self):
        road_state = {
            "pedestrian": False,
            "camera_near_vehicles": list(),
            "camera_far_vehicles": list(),
            "radar_vehicles": list()
        }
        # 摄像头识别结果
        camera_recognition = self.query_alg_analytic_result()
        if "camera_pedestrian" in camera_recognition and camera_recognition["camera_pedestrian"]:
            road_state.update({
                "pedestrian": True
            })
            return road_state
        elif "camera_vehicles" in camera_recognition and camera_recognition["camera_vehicles"]:
            camera_vehicles = camera_recognition["camera_vehicles"]
            # 摄像头1识别到有车，直接判定该方向有车
            for camera_vehicle in camera_vehicles:
                camera_direction = camera_vehicle["direction"]
                camera_position = camera_vehicle["camera_position"]
                if camera_position == 1:
                    if camera_direction not in road_state["camera_near_vehicles"]:
                        road_state["camera_near_vehicles"].append(camera_direction)
                # 省电模式下需要判断摄像头2
                elif camera_position == 2:
                    if camera_direction not in road_state["camera_far_vehicles"]:
                        road_state["camera_far_vehicles"].append(camera_direction)

        # 雷达识别结果
        radar_recognition = self.query_vehicle_radar_info()
        for radar_conn, radar_detect_tuple in radar_recognition.items():
            radar_direction, radar_distance = radar_detect_tuple
            road_state["radar_vehicles"].append(
                (radar_direction, radar_distance)
            )

        return road_state

    # 查询路口行人情况
    def query_alg_list(self):
        pipeline = [
            {
                '$match': {
                    'remark': {
                        '$gte': self.search_start_timestamp
                    },
                    'alert_type': {
                        '$in': ["pedestrian", "vehicle"]
                    }
                }
            },
            {
                '$project': {
                    '_id': 0
                }
            }
        ]
        alg_list = list(self.my_db.mydb.alert_log.aggregate(pipeline))
        return alg_list

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

    # 获取alg的分析结果
    def query_alg_analytic_result(self):
        alg_list = self.query_alg_list()
        cross_logger.debug("alg_list: {}".format(alg_list))
        if not alg_list:
            return dict()

        # 识别到行人，且识别摄像头为1号摄像头，直接返回
        alg_analytic_result = dict()
        for alg_item in alg_list:
            alert_type = alg_item["alert_type"]
            device_id = alg_item["device_identification"]
            if device_id not in self.camera_maps:
                cross_logger.debug("算法传递的设备编号不存在，已过滤")
                continue
            direction, camera_position = self.camera_maps[device_id]
            # 获取当前摄像头的位置，1或者2
            if alert_type == "pedestrian":
                if camera_position == 1:
                    alg_analytic_result.update({
                        "camera_pedestrian": {
                            "device_id": device_id,
                            "direction": direction,
                            "camera_position": camera_position
                        }
                    })
                    # 存在1号摄像头识别到行人的场景，优先级最高，直接返回
                    break
                else:
                    cross_logger.debug("摄像头2识别到行人信息，请检查配置是否正确。")
            # 识别到车辆，记录识别的摄像头信息
            elif alert_type == "vehicle":
                if "camera_vehicles" not in alg_analytic_result:
                    alg_analytic_result.update({
                        "camera_vehicles": [{
                            "device_id": device_id,
                            "direction": direction,
                            "camera_position": camera_position
                        }]
                    })
                else:
                    alg_analytic_result["camera_vehicles"].append({
                        "device_id": device_id,
                        "direction": direction,
                        "camera_position": camera_position
                    })

        return alg_analytic_result

    # 获取驶进的车辆信息，以及车辆对应的雷达方向
    def query_vehicle_radar_info(self):
        radar_list = self.query_radar_data()
        cross_logger.debug("radar_list: {}".format(radar_list))
        # 根据ip:port对雷达数据进行归类分析
        radar_conns = list(set(map(lambda x: "{}:{}".format(x["radar_ip"], x["radar_port"]), radar_list)))
        radar_dict = dict()
        for radar_conn in radar_conns:
            match_items = list(
                filter(lambda x: "{}:{}".format(x["radar_ip"], x["radar_port"]) == radar_conn, radar_list))
            sorted_items = sorted(match_items, key=lambda x: x["event_timestamp"], reverse=True)
            cross_logger.debug("radar_conn: {}, sorted_items: {}".format(radar_conn, sorted_items))
            is_near, radar_direction, radar_distance = self.query_vehicle_near(radar_conn, sorted_items)
            cross_logger.debug("is_near: {}, radar_direction: {}, radar_distance: {}".format(
                is_near, radar_direction, radar_distance))
            if is_near and radar_direction and radar_distance:
                cross_logger.debug(
                    "=========={}路口检测到车辆正在驶进，与雷达距离:{}=========".format(radar_direction, radar_distance))
                radar_dict.update({
                    radar_conn: (radar_direction, radar_distance)
                })

        return radar_dict

    # 获取当前路段的信息数据
    def recognize_road_conditions_v2(self):
        radar_detail = self.query_vehicle_radar_info()
        cross_logger.debug("================雷达数据分析详情: {}".format(radar_detail))
        directions = list()
        if not radar_detail:
            road_condition = "no_pedestrian_no_vehicle"
        else:
            # 查看雷达的数据
            vehicle_directions = len(radar_detail)
            if vehicle_directions > 1:
                road_condition = "multi_direction_vehicles"
            else:
                road_condition = 'one_direction_vehicle'
            for radar_conn, radar_direction in radar_detail.items():
                # 进行去重
                if radar_direction not in directions:
                    directions.append(radar_direction)

        road_condition_info = {
            "road_condition": road_condition,
            "directions": directions
        }

        return road_condition_info

    # 获取雷达数据
    def query_radar_data(self):
        pipeline = [
            {
                '$match': {
                    'event_timestamp': {
                        '$gte': self.search_start_timestamp
                    }
                }
            },
            {
                '$project': {
                    '_id': 0,
                    'event_time': 0,
                    'receive_time': 0
                }
            }
        ]
        radar_list = list(self.my_db.mydb.radar_data_record.aggregate(pipeline))
        return radar_list

    # 对来向的数据进行分析处理
    def query_vehicle_near(self, radar_ip, sorted_radar_data):
        # 返回车辆是否为驶进，以及雷达的方向
        is_near, vehicle_direction, vehicle_distance = None, None, None
        cross_logger.debug("======radar_ip: {}=====sorted_radar_data:{}======".format(radar_ip, sorted_radar_data))
        for radar_config, radar_direction in self.radar_maps.items():
            # 配置表中未配置端口，根据ip确定雷达方向
            if ":" not in radar_config:
                radar_ip = radar_ip.split(":")[0]
            if radar_config == radar_ip:
                vehicle_direction = radar_direction
                break
        cross_logger.debug("========vehicle_direction: {}=========".format(vehicle_direction))
        if vehicle_direction is None:
            return is_near, vehicle_direction, vehicle_distance

        vehicle_dict = dict()
        for sorted_radar_info in sorted_radar_data:
            vehicle_id = sorted_radar_info["vehicle_id"]
            v_distance = sorted_radar_info["vehicle_distance_v"]
            # 对雷达数据进行解析时，雷达数据应不小于两条
            if vehicle_id not in vehicle_dict:
                vehicle_dict.update({
                    vehicle_id: v_distance
                })
            else:
                # y值没变化，不能判断驶进还是驶离
                last_v_distance = vehicle_dict[vehicle_id]
                if v_distance == last_v_distance:
                    continue
                # 如果发现y值变小，说明车辆在驶进
                is_near = v_distance > last_v_distance
                # 如果车辆驶进，需要记录车辆距离雷达的距离
                if is_near:
                    vehicle_distance = last_v_distance
                    break

        return is_near, vehicle_direction, vehicle_distance

    # 获取雷达数据，统计来车情况、来车方向等信息
    def query_radar_detail(self):
        radar_detail = dict()
        radar_list = self.query_radar_data()
        # 获取最近时间的两条数据
        # 根据雷达IP对数据进行切片
        # 获取数据中记录的所有ip信息
        radar_ips = list(set(map(lambda x: x["radar_ip"] + ":" + str(x["radar_port"]), radar_list)))
        radar_dict = dict()
        for radar_ip in radar_ips:
            match_items = list(filter(lambda x: x["radar_ip"] + ":" + str(x["radar_port"]) == radar_ip, radar_list))
            sorted_items = sorted(match_items, key=lambda x: x["event_timestamp"], reverse=True)
            is_near, radar_direction, radar_distance = self.query_vehicle_near(radar_ip, sorted_items)
            if is_near and radar_direction and radar_distance:
                radar_dict.update({
                    radar_ip: sorted_items
                })

        for radar_ip, radar_items in radar_dict.items():
            vehicle_detail = dict()
            for radar_item in radar_items:
                vehicle_id = radar_item["vehicle_id"]
                vehicle_distance_h = radar_item["vehicle_distance_h"]
                if vehicle_id not in vehicle_detail:
                    vehicle_detail.update({
                        vehicle_id: {
                            "vehicle_direction": radar_item["radar_direction"],
                            "vehicle_type": radar_item["vehicle_type"],
                            "vehicle_speed": radar_item["vehicle_speed"],
                            "vehicle_length": radar_item["vehicle_length"],
                            "vehicle_distance_h": vehicle_distance_h,
                            "vehicle_distance_v": radar_item["vehicle_distance_v"],
                        }
                    })
                else:
                    if "vehicle_near" not in vehicle_detail:
                        latest_distance = vehicle_detail[vehicle_id]["vehicle_distance_h"]
                        vehicle_near = vehicle_distance_h > latest_distance
                        vehicle_detail[vehicle_id].update({
                            "vehicle_near": vehicle_near
                        })

            radar_detail.update({
                radar_ip: vehicle_detail
            })

        return radar_detail


def recognize_road_conditions():
    my_db = ToMongo('wavedevice')
    db = my_db.mydb  # 替换为您的数
    # 当前时间（UTC）
    current_time = datetime.now(timezone.utc)
    common_time_range_start = current_time - timedelta(seconds=10)  # 前10秒
    vehicle_time_range_start = current_time - timedelta(seconds=13)  # 前13秒
    vehicle_time_range_end = current_time - timedelta(seconds=3)  # 前3秒

    # 构建聚合查询
    pipeline = [
        {
            '$facet': {
                'radar': [
                    {
                        '$match': {
                            'alert_time': {
                                '$gte': common_time_range_start,  # 当前时间前10秒
                                '$lt': current_time  # 当前时间
                            },
                            'alert_type': 'radar'  # 只匹配 radar 类型
                        }
                    },
                    {
                        '$group': {
                            '_id': '$device_identification',
                            'has_radar': {
                                '$max': {
                                    '$cond': [{'$eq': ['$alert_type', 'radar']}, 1, 0]
                                }
                            }
                        }
                    }
                ],
                'pedestrian': [
                    {
                        '$match': {
                            'alert_time': {
                                '$gte': common_time_range_start,  # 当前时间前10秒
                                '$lt': current_time  # 当前时间
                            },
                            'alert_type': 'pedestrian'  # 只匹配 pedestrian 类型
                        }
                    },
                    {
                        '$group': {
                            '_id': '$device_identification',
                            'has_pedestrian': {
                                '$max': {
                                    '$cond': [{'$eq': ['$alert_type', 'pedestrian']}, 1, 0]
                                }
                            }
                        }
                    }
                ],
                'vehicle_near': [
                    {
                        '$match': {
                            'alert_time': {
                                '$gte': vehicle_time_range_start,  # 当前时间前13秒
                                '$lt': vehicle_time_range_end  # 当前时间前3秒
                            },
                            'alert_type': 'vehicle_near'  # 只匹配 vehicle_near 类型
                        }
                    },
                    {
                        '$group': {
                            '_id': '$device_identification',
                            'has_vehicle': {
                                '$max': {
                                    '$cond': [{'$eq': ['$alert_type', 'vehicle_near']}, 1, 0]
                                }
                            }
                        }
                    }
                ],
                'vehicle_far': [
                    {
                        '$match': {
                            'alert_time': {
                                '$gte': vehicle_time_range_start,  # 当前时间前13秒
                                '$lt': vehicle_time_range_end  # 当前时间前3秒
                            },
                            'alert_type': 'vehicle_far'  # 只匹配 vehicle_far 类型
                        }
                    },
                    {
                        '$group': {
                            '_id': '$device_identification',
                            'has_vehicle': {
                                '$max': {
                                    '$cond': [{'$eq': ['$alert_type', 'vehicle_far']}, 1, 0]
                                }
                            }
                        }
                    }
                ]
            }
        },
        {
            '$project': {
                'radar': 1,
                'pedestrian': 1,
                'vehicle_near': 1,
                'vehicle_far': 1
            }
        }
    ]

    # 执行聚合查询
    result = list(db.alert_log.aggregate(pipeline))[0]

    config_col = my_db.get_col("traffic_light_config")
    config_items = config_col.find({}, {'_id': 0})
    device_direction_map = {}
    for i in config_items:
        device_direction_map[i['camera_id']] = i['direction']
        device_direction_map[i['radar_ip'].split("#")[0]] = i['direction']

    pedestrian = result.get("pedestrian")
    vehicle_near = result.get("vehicle_near")
    vehicle_far = result.get("vehicle_far")

    if pedestrian:
        road_condition = 'has_pedestrian'
        directions = []
    else:
        if vehicle_near:
            # 近处有车，直接认为有车
            vehicle_directions = {device_direction_map[item['_id']] for item in vehicle_near if
                                  item['_id'] in device_direction_map}
        else:
            # 远处有车，要和雷达一起判断确认是否有车
            radar = result.get('radar')
            radar_directions = {device_direction_map[item['_id']] for item in radar if
                                item['_id'] in device_direction_map}
            vehicle_far_directions = {device_direction_map[item['_id']] for item in vehicle_far if
                                      item['_id'] in device_direction_map}
            vehicle_directions = radar_directions & vehicle_far_directions
        if vehicle_directions:
            # 根据摄像头和雷达都有信号才认为当前方向有车
            if len(vehicle_directions) > 1:
                road_condition = 'multi_direction_vehicles'
            else:
                road_condition = 'one_direction_vehicle'
        else:
            road_condition = 'no_pedestrian_no_vehicle'
        directions = list(vehicle_directions)
        # 按方向从小到大排序
        directions.sort()
    road_condition_info = {
        "road_condition": road_condition,
        "directions": directions
    }
    return road_condition_info


if __name__ == "__main__":
    handle_road = HandleRoadCondition()
    radar_data = handle_road.query_current_road_state()
    print("radar_detail:", radar_data)

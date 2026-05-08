from datetime import datetime, timedelta, timezone
from Utils.db import ToMongo


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
            radar_directions = {device_direction_map[item['_id']] for item in radar if item['_id'] in device_direction_map}
            vehicle_far_directions = {device_direction_map[item['_id']] for item in vehicle_far if item['_id'] in device_direction_map}
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

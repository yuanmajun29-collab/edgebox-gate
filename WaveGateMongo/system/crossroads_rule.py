from datetime import datetime, time
import json

from Utils.db import ToMongo
from Utils import logger

cross_logger = logger.getLogger("cross")

my_db = ToMongo('wavedevice')


def int2hex(n):
    """
    int类型地址码转16进制字符串
    """
    if type(n) == str:
        n = int(n)
    return hex(n)[2:] if n >= 16 else '0{:X}'.format(n)


def is_within_time_range(current_time, start_time, end_time):
    """检查当前时间是否在给定的时间范围内"""
    return start_time <= current_time <= end_time


def match_traffic_rules(current_datetime, traffic_rules):
    """匹配当前时间与交通信号控制规则"""
    current_weekday = current_datetime.strftime("%u")  # 获取星期几，1=星期一，7=星期天
    current_time = current_datetime.time()

    for rule in traffic_rules:
        # 检查周数是否匹配
        if current_weekday not in rule['weeks']:
            continue

        # 解析控制时间
        control_time = rule['controlTime']
        start_time_str = control_time.split('"')[3]
        end_time_str = control_time.split('"')[7]
        start_time = time.fromisoformat(start_time_str)
        end_time = time.fromisoformat(end_time_str)

        # 检查时间范围
        if is_within_time_range(current_time, start_time, end_time):
            return rule


def get_direction_setting(traffic_mode, rule):
    if traffic_mode == 1:
        # 混合通行
        direction_setting = {
            "main_direction_group": rule.get('direction'),
            "main_direction_group_time": rule.get('greenLightTimeGroup1'),
            "other_direction_group_time": rule.get('greenLightTimeGroup2')
        }
    else:
        # 单向通行
        direction_setting = dict(zip(rule.get('direction'), rule.get('greenLightTime')))
    return direction_setting


def parse_ruler(rule):
    control_map = {
        '1': '混合通行',
        '3': '智能通行',
        '2': '单向通行'
    }
    control_type = rule['controlType']
    if control_type == '3':
        # 智能通行下  trafficMode=1 -> 混合通行， trafficMode=2 -> 单向通行
        traffic_mode_map = {
            1: '混合通行',
            2: '单向通行'
        }
        traffic_mode = rule.get('trafficMode')
        cross_logger.debug(
            "当前控制类型：{} | 多方向来车时通行模式：{}".format(control_map.get(control_type),traffic_mode_map.get(traffic_mode)))
        direction_setting = get_direction_setting(traffic_mode, rule)
    else:
        cross_logger.debug("当前控制类型：{}".format(control_map.get(control_type)))
        if control_type == '1':
            traffic_mode = 1
            direction_setting = get_direction_setting(traffic_mode, rule)
        else:
            traffic_mode = 2
            direction_setting = get_direction_setting(traffic_mode, rule)
    cross_logger.debug(direction_setting)
    rule_info = {
        "crossroadType": rule.get('crossroadType'),
        "control_type": control_type,
        "control_type_name": control_map.get(control_type),
        "direction_setting": direction_setting,
        "vehicle_traffic_time": rule.get('vehicleTrafficTime'),
        "pedestrian_traffic_time": rule.get('pedestrianTrafficTime'),
        "traffic_mode": traffic_mode
    }
    return rule_info


def check_ruler_now():
    ruler_col = my_db.get_col("traffic_light_ruler")
    ruler_item = ruler_col.find_one({}, {'_id': 0})
    if not ruler_item:
        cross_logger.debug("未找到规则配置")
        rule_info = {
            "control_type": '-1',
        }
    else:
        light_ruler = ruler_item.get('traffic_light_ruler_json')
        traffic_rules = json.loads(light_ruler)
        yellow_light_time = ruler_item.get('yellow_light_time')  # 黄灯闪烁时间
        current_datetime = datetime.now()  # 获取当前日期和时间
        matched_rules = match_traffic_rules(current_datetime, traffic_rules)
        if not matched_rules:
            cross_logger.debug("未匹配到任何规则")
            rule_info = {
                "control_type": '-1',
            }
        else:
            rule_info = parse_ruler(matched_rules)
            rule_info["power_save"] = ruler_item.get('power_save')
            rule_info['yellow_light_time'] = int(yellow_light_time)
    return rule_info


def get_light_configs():
    light_configs = []
    config_col = my_db.get_col("traffic_light_config")
    config_items = config_col.find({}, {'_id': 0})
    for i in config_items:
        traffic_light = i.get('traffic_light')
        host, port, addr = traffic_light.split('#')
        byte_addr = bytes.fromhex(int2hex(int(addr)))
        info = {
            'direction': i.get('direction'),
            'host': host,
            'port': int(port),
            'byte_addr': byte_addr
        }
        light_configs.append(info)
    return light_configs

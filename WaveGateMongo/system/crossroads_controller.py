import time
import datetime
import threading
import requests

from Utils.db import ToMongo
from Utils import logger
from algorith_server.redis_connect import redis_database
from system.radar_server import RadarServer
from system.radar_controller import RadarClient
from system.crossroads_rule import get_light_configs, check_ruler_now
from system.crossroads_access_controller import CrossRoadsAccessControl
from system.light_controller_v2 import (
    connect_all_lights,
    run_mixed_direction,
    run_single_direction,
    run_smart_mode,
    run_normal_mode,
    check_all_light_status_thead,
)
from system.light_message_controller import LightMessageController
from Utils.CheckdeviceStatus import CheckDeviceStatus

cross_logger = logger.getLogger("cross")


def start_listen_radar_v2():
    cross_logger.debug('==========进行雷达数据监听==========')
    radar_listen = RadarServer()
    radar_listen.start_socket_server()


def start_listen_radar():
    cross_logger.debug('==========开始监听雷达，监听前先断开所有连接再开始==========')
    my_db = ToMongo('wavedevice')
    config_col = my_db.get_col("traffic_light_config")
    config_items = config_col.find({}, {'_id': 0})
    radar_configs = []
    for item in config_items:
        radar_ip = item.get('radar_ip')
        host, port, _ = radar_ip.split('#')
        radar_info = {
            'host': host,
            'port': int(port),
            'speed': item['radar_speed_threshold'],
            'sensitivity': item['radar_sensitivity'],
            'anti_jam': item['radar_anti_jam'],
            'direction': item['radar_test_direction'],
            'angle': item['radar_angle']
        }
        radar_configs.append(radar_info)
    radar_client = RadarClient()
    radar_client.stop_all_connections()
    time.sleep(0.5)
    radar_client.start_all_connections(radar_configs)


def start_run_light_control_v2():
    light_configs = get_light_configs()
    cross_logger.debug("==============start_run_light_control_v2 start================")
    cross_logger.debug("获取灯控配置为：{}".format(light_configs))
    handle_light_objects = dict()
    for config in light_configs:
        light_host = config['host']
        light_port = config['port']
        light_direction = config["direction"]
        handle_light_obj = LightMessageController(light_direction, light_host, int(light_port))
        handle_light_obj.start()
        handle_light_objects.update({
            light_direction: handle_light_obj
        })
    rule_power_save = None
    current_mode = None
    while True:
        cross_logger.debug("获取规则配置...")
        ruler_now = check_ruler_now()
        cross_logger.debug("当前规则配置: {}".format(ruler_now))
        power_save = ruler_now.get('power_save', '1')
        # 查看省电模式是否有变化
        if rule_power_save is not None and rule_power_save == power_save:
            power_save_modify = False
        else:
            power_save_modify = True
        rule_power_save = power_save
        control_type = ruler_now.get('control_type')
        # 查看是否首次进入该通行模式
        if current_mode and current_mode == control_type:
            first_enter_mode = False
        else:
            first_enter_mode = True
        current_mode = control_type
        cross_road_obj = CrossRoadsAccessControl(handle_light_objects, ruler_now, power_save_modify, first_enter_mode)
        # 开始通行
        if control_type == '1':
            cross_road_obj.run_mix_directions_access()
        elif control_type == '2':
            cross_road_obj.run_one_direction_access()
        elif control_type == '3':
            smart_mode_start = datetime.datetime.now()
            cross_logger.debug("开始进行智能通行 begin time:{}".format(smart_mode_start.strftime("%Y-%m-%d %H:%M:%S")))
            cross_road_obj.run_smart_mode()
            smart_mode_end = datetime.datetime.now()
            cross_logger.debug(
                "本次智能通行结束 end time:{}, 耗时:{}s".format(smart_mode_end.strftime("%Y-%m-%d %H:%M:%S"),
                                                                (smart_mode_end - smart_mode_start).seconds))
        else:
            cross_road_obj.run_normal_mode_access()


def start_run_light_control():
    # 这里认为红绿灯的配置不会变化，所以直接获取一次，不用每次都获取，如果变化，需重启服务
    light_configs = get_light_configs()
    cross_logger.debug("获取灯控配置为：{}".format(light_configs))
    clients = connect_all_lights(light_configs)
    cross_logger.debug("===============红绿灯服务器信息: {}".format(clients))
    check_all_light_status_thead(clients)
    while 1:
        cross_logger.debug("获取规则配置...")
        ruler_now = check_ruler_now()
        cross_logger.debug("当前规则配置: {}".format(ruler_now))
        control_type = ruler_now.get('control_type')
        # todo: 通行模式改变时需要进行初始化红绿灯操作
        if control_type == '1':
            run_mixed_direction(clients, ruler_now)
        elif control_type == '2':
            run_single_direction(clients, ruler_now)
        elif control_type == '3':
            run_smart_mode(clients, ruler_now)
        else:
            run_normal_mode(clients)


def update_device_status():
    # 50秒上报一次状态
    while 1:
        cross_logger.debug('==========同步设备状态到平台==========')
        my_db = ToMongo('wavedevice')
        config_col = my_db.get_col("traffic_light_config")
        config_items = config_col.find({}, {'_id': 0})
        crossroad_no = my_db.get_col('traffic_light_project').find_one()['crossroad_no']
        status_list = []
        for i in config_items:
            radar_ip = i.get('radar_ip').split("#")[0]
            traffic_light = i.get('traffic_light').split("#")[0]
            # radar_ip_is_alive = redis_database.exists("{}_is_alive".format(radar_ip))
            radar_ip_is_alive = CheckDeviceStatus(radar_ip)
            traffic_light_is_alive = redis_database.exists("{}_is_alive".format(traffic_light))
            config_id = i.get('config_id')
            radar_status = 0 if radar_ip_is_alive else 1
            traffic_light_status = 0 if traffic_light_is_alive else 1
            my_db.update('traffic_light_config',
                         {'config_id': config_id},
                         {'$set': {'traffic_light_status': traffic_light_status, 'radar_status': radar_status}})
            device_status_item = {
                'id': config_id,
                'radarStatus': radar_status,
                'trafficLightStatus': traffic_light_status
            }
            status_list.append(device_status_item)
        content = {
            "crossroadNo": crossroad_no,
            "deviceStatusVoList": status_list
        }
        try:
            item = my_db.get_col("authority_work_model").find_one()
            api_host = "http://" + item.get('service_address') + ":" + item.get('service_port')
            url = api_host + "/business/syn/synCrossroadDeviceStatus"  # 同步红绿灯设备状态
            cross_logger.debug("同步红绿灯设备状态 url:{}入参:{}".format(url, content))
            resp = requests.post(url, json=content, verify=False).json()
            cross_logger.debug("同步红绿灯设备状态结果: {}".format(resp))
        except Exception as e:
            cross_logger.error("同步红绿灯设备状态出错 {}".format(e))
        time.sleep(50)


def run_crossroads_control():
    cross_logger.debug('==========开始弯道红绿灯控制==========')
    # thread_radar = threading.Thread(target=start_listen_radar)
    thread_radar = threading.Thread(target=start_listen_radar_v2)
    thread_radar.start()
    thread_light = threading.Thread(target=start_run_light_control_v2)
    thread_light.start()
    thread_update_device_status = threading.Thread(target=update_device_status)
    thread_update_device_status.start()


if __name__ == "__main__":
    run_crossroads_control()

import uuid
from flask import jsonify, Blueprint
from Utils.cal_datetime import *
from Utils.db import ToMongo

bp = Blueprint("homepage", __name__, url_prefix='/net-web')


@bp.route('/homepage/today_alarm_top_5', methods=['POST'])
def today_alarm_top_5():
    """今日报警排名"""
    # 选择数据库
    my_db = ToMongo('wavedevice')

    # 计算今天的开始时间（00:00:00）
    start_of_day, end_of_day = calculating_today_time()
    query = calculating_time('create_time', start_of_day, end_of_day)
    query_dy = calculating_time('emergency_time', start_of_day, end_of_day)
    # 定义聚合管道
    pipeline = query_group_by_field_limit5(query, "$model_name")
    pipeline_dynamic = query_group_by_field_limit5(query_dy, "$emergency_type")
    # 执行聚合管道查询
    cursor_device = my_db.get_col('odin_business_emergency_record').aggregate(pipeline)
    cursor_dynamic = my_db.get_col('odin_business_dynamic_emergency_record').aggregate(pipeline_dynamic)

    top_five = merge_command_cursor_to_list(cursor_device, cursor_dynamic, 'count')
    items = []
    if len(top_five) > 0:
        for result in top_five:
            item = {'id': result['_id'], 'count': result['count']}
            items.append(item)

    response_data = {'data': items, 'requestId': uuid.uuid4().hex, 'requestStatus': 'SUCCESS',
                     'timeUsed': 10}
    return response_data


@bp.route('/homepage/countDynamicEmergency', methods=['POST'])
def count_dynamic_emergency():
    """报警数据统计"""
    my_db = ToMongo('wavedevice')

    # 计算今天的开始时间（00:00:00）
    start_of_day, end_of_day = calculating_today_time()
    query_day = query_group_none(start_of_day, end_of_day, 'create_time')
    query_day_dy = query_group_none(start_of_day, end_of_day, 'emergency_time')

    # 本月时间
    first_day_of_month, last_day_of_month = calculating_month_time()
    query_month = query_group_none(first_day_of_month, last_day_of_month, 'create_time')
    query_month_dy = query_group_none(first_day_of_month, last_day_of_month, 'emergency_time')

    # 计算本年的第一天和最后一天
    first_day_of_year, last_day_of_year = calculating_year_time()
    query_year = query_group_none(first_day_of_year, last_day_of_year, 'create_time')
    query_year_dy = query_group_none(first_day_of_year, last_day_of_year, 'emergency_time')

    today_emergency_count_1 = my_db.get_col('odin_business_emergency_record').aggregate(query_day)
    today_dynamic_emergency_count = my_db.get_col('odin_business_dynamic_emergency_record').aggregate(query_day_dy)
    today_count = cal_command_cursor_value_addition(today_emergency_count_1, today_dynamic_emergency_count)

    month_emergency_count = my_db.get_col('odin_business_emergency_record').aggregate(query_month)
    month_dynamic_emergency_count = my_db.get_col('odin_business_dynamic_emergency_record').aggregate(query_month_dy)
    month_count = cal_command_cursor_value_addition(month_emergency_count, month_dynamic_emergency_count)

    year_emergency_count = my_db.get_col('odin_business_emergency_record').aggregate(query_year)
    year_dynamic_emergency_count = my_db.get_col('odin_business_dynamic_emergency_record').aggregate(query_year_dy)
    year_count = cal_command_cursor_value_addition(year_emergency_count, year_dynamic_emergency_count)

    # 已处理/未处理告警数
    emergency_1_num = 0
    emergency_0_num = 0
    pipeline_emergency = query_group_by_field({}, "$emergency_exec_flag")
    cursor_emergency = my_db.get_col('odin_business_emergency_record').aggregate(pipeline_emergency)
    if cursor_emergency.alive:
        for c in cursor_emergency:
            if c['_id'] == 1:
                emergency_1_num = c['count']
            elif c['_id'] == 0:
                emergency_0_num = c['count']

    response_data = {'today': today_count, 'month': month_count, 'year': year_count,
                     'emergencyProcessed': emergency_1_num, 'emergencyUnprocessed': emergency_0_num,
                     'requestId': uuid.uuid4().hex, 'requestStatus': 'SUCCESS', 'timeUsed': 10}
    return jsonify(response_data)


@bp.route('/homepage/query_all_device_status', methods=['POST'])
def query_all_device_status():
    """设备状态数据"""
    my_db = ToMongo('wavedevice')

    # 根据device_status分组查询所有设备数量
    dynamic_num = 0
    dynamic_on_num = 0
    dynamic_off_num = 0
    camera_num = 0
    pipeline = query_group_by_field({}, "$device_status")
    cursor_audio = my_db.get_col('odin_dynamic_audio').aggregate(pipeline)
    cursor_gas = my_db.get_col('odin_dynamic_gas').aggregate(pipeline)
    cursor_leakage = my_db.get_col('odin_dynamic_leakage').aggregate(pipeline)
    cursor_static = my_db.get_col('odin_dynamic_static_electricity').aggregate(pipeline)

    pipeline_camera = query_group_by_field({}, "$camera_status")
    cursor_camera = my_db.get_col('odin_device_camera_edit').aggregate(pipeline_camera)

    pipeline_sound = query_group_by_field({}, "$sound_status")
    cursor_sound = my_db.get_col('odin_device_sound').aggregate(pipeline_sound)

    dynamic_num, dynamic_on_num, dynamic_off_num = ergodic_cursor(cursor_audio, dynamic_num, dynamic_on_num,
                                                                  dynamic_off_num)
    dynamic_num, dynamic_on_num, dynamic_off_num = ergodic_cursor(cursor_gas, dynamic_num, dynamic_on_num,
                                                                  dynamic_off_num)
    dynamic_num, dynamic_on_num, dynamic_off_num = ergodic_cursor(cursor_leakage, dynamic_num, dynamic_on_num,
                                                                  dynamic_off_num)
    dynamic_num, dynamic_on_num, dynamic_off_num, camera_num = ergodic_edit_cursor(cursor_camera, dynamic_num,
                                                                                   dynamic_on_num, dynamic_off_num,
                                                                                   camera_num)
    dynamic_num, dynamic_on_num, dynamic_off_num = ergodic_cursor(cursor_sound, dynamic_num, dynamic_on_num,
                                                                  dynamic_off_num)
    dynamic_num, dynamic_on_num, dynamic_off_num = ergodic_cursor(cursor_static, dynamic_num, dynamic_on_num,
                                                                  dynamic_off_num)
    response_data = {'deviceNum': dynamic_num, 'deviceOn': dynamic_on_num, 'deviceOff': dynamic_off_num,
                     'deviceEmergency': 0, 'requestId': uuid.uuid4().hex, 'requestStatus': 'SUCCESS',
                     'cameraNum': camera_num, 'timeUsed': 10}
    return response_data


@bp.route('/homepage/today_alarm_dynamic_limit5', methods=['POST'])
def today_alarm_dynamic():
    """今日报警动态"""
    my_db = ToMongo('wavedevice')

    start_of_day, end_day = calculating_today_time()
    # 查询视频告警：
    cursor_device = my_db.get_col('odin_business_emergency_record').find(
        {'create_time': {'$gte': start_of_day, '$lte': end_day}}).sort('create_time', -1).limit(5)
    # 查询设备告警：
    cursor_dynamic = my_db.get_col('odin_business_dynamic_emergency_record').find(
        {'emergency_time': {'$gte': start_of_day, '$lte': end_day}}).sort('emergency_time', -1).limit(5)

    items = []
    if cursor_device.count() and cursor_dynamic.count():
        emergency_items = []
        for devices in cursor_device:
            emergency_items.append(
                {'emergencyTime': devices['create_time'].strftime("%H:%M"), 'emergencyContext': devices['model_name']})
        for dynamic in cursor_dynamic:
            emergency_items.append(
                {'emergencyTime': dynamic['emergency_time'].strftime("%H:%M"),
                 'emergencyContext': dynamic['emergency_context']})
        cursor = sorted(emergency_items, key=lambda doc: doc.get('emergencyTime'), reverse=True)
        items = cursor[:5]
    elif cursor_device.count():
        for result in cursor_device:
            items.append(
                {'emergencyTime': result['create_time'].strftime("%H:%M"), 'emergencyContext': result['model_name']})
    elif cursor_dynamic.count():
        for result in cursor_dynamic:
            items.append(
                {'emergencyTime': result['emergency_time'].strftime("%H:%M"),
                 'emergencyContext': result['emergency_context']})
    response_data = {'dynamics': items, 'requestId': uuid.uuid4().hex, 'requestStatus': 'SUCCESS', 'timeUsed': 10}
    return response_data


@bp.route('/homepage/today_alarm_12h_sum', methods=['POST'])
def today_alarm_12h_sum():
    """今日报警动态(近12个小时)"""
    my_db = ToMongo('wavedevice')

    # 获取当前时间，将时间转换为ISO格式的字符串
    iso_date = datetime.now() - timedelta(hours=12)
    iso_date_time = datetime(iso_date.year, iso_date.month, iso_date.day, iso_date.hour, 0, 0)

    query = {'$match': {
        'create_time': {
            '$gte': iso_date_time
        }
    }}
    query_dy = {'$match': {
        'emergency_time': {
            '$gte': iso_date_time
        }
    }}

    # 按照小时分组查询数据，并输出结果
    cursor_device = my_db.get_col('odin_business_emergency_record').aggregate(
        [query, {'$group': {'_id': {'hour': {'$hour': '$create_time'}}, 'count': {'$sum': 1}}},
         {'$sort': {'_id': 1}}])
    cursor_dynamic = my_db.get_col('odin_business_dynamic_emergency_record').aggregate(
        [query_dy, {'$group': {'_id': {'hour': {'$hour': '$emergency_time'}}, 'count': {'$sum': 1}}},
         {'$sort': {'_id': 1}}])

    device_list = list(cursor_device)
    dynamic_list = list(cursor_dynamic)
    items = []

    for i in range(12):
        # 计算前一天的日期
        date = datetime.now() - timedelta(hours=(12 - i - 1))
        count = 0
        if device_list:
            for j in device_list:
                if int(date.strftime("%H")) < j['_id']['hour']:
                    break
                if int(date.strftime("%H")) == j['_id']['hour']:
                    count += j['count']
                    break
        if dynamic_list:
            for k in dynamic_list:
                if int(date.strftime("%H")) < k['_id']['hour']:
                    break
                if int(date.strftime("%H")) == k['_id']['hour']:
                    count += k['count']
                    break
        item = {'id': date.strftime("%H"), 'count': count}
        items.append(item)

    response_data = {'data': items, 'requestId': uuid.uuid4().hex, 'requestStatus': 'SUCCESS',
                     'timeUsed': 10}
    return response_data


@bp.route('/homepage/today_alarm_15day', methods=['POST'])
def today_alarm_15day():
    """近十五日报警"""
    my_db = ToMongo('wavedevice')

    # 获取当前时间，将时间转换为ISO格式的字符串
    iso_date = datetime.now() - timedelta(days=14)
    iso_date_time = datetime(iso_date.year, iso_date.month, iso_date.day, 0, 0, 0)

    query = {'$match': {
        'create_time': {
            '$gte': iso_date_time
        }
    }}
    query_dy = {'$match': {
        'emergency_time': {
            '$gte': iso_date_time
        }
    }}

    # 按照天分组查询数据，并输出结果
    cursor_device = my_db.get_col('odin_business_emergency_record').aggregate(
        [query, {'$group': {'_id': {'day': {'$dayOfMonth': '$create_time'}}, 'count': {'$sum': 1}}},
         {'$sort': {'_id': 1}}])
    cursor_dynamic = my_db.get_col('odin_business_dynamic_emergency_record').aggregate(
        [query_dy, {'$group': {'_id': {'day': {'$dayOfMonth': '$emergency_time'}}, 'count': {'$sum': 1}}},
         {'$sort': {'_id': 1}}])
    device_list = list(cursor_device)
    dynamic_list = list(cursor_dynamic)
    items = []
    for i in range(15):
        # 计算前一天的日期
        date = datetime.now() - timedelta(days=(15 - i - 1))
        count = 0
        if device_list:
            for j in device_list:
                if int(date.strftime("%d")) < j['_id']['day']:
                    break
                if int(date.strftime("%d")) == j['_id']['day']:
                    count += j['count']
                    break
        if dynamic_list:
            for k in dynamic_list:
                if int(date.strftime("%d")) < k['_id']['day']:
                    break
                if int(date.strftime("%d")) == k['_id']['day']:
                    count += k['count']
                    break
        item = {'id': date.strftime("%m-%d"), 'count': count}
        items.append(item)

    response_data = {'data': items, 'requestId': uuid.uuid4().hex, 'requestStatus': 'SUCCESS',
                     'timeUsed': 10}
    return response_data


@bp.route('/homepage/today_alarm_top_5_percent', methods=['POST'])
def today_alarm_top_5_percent():
    """报警类型所占半分比"""
    my_db = ToMongo('wavedevice')

    pipeline = query_group_by_field({}, '$device_type')
    dynamic_emergency_list = my_db.get_col('odin_business_dynamic_emergency_record').aggregate(pipeline)

    alarm_sum = 0
    smokeAlarm = 0
    leakageAlarm = 0
    voltageAlarm = 0
    currentAlarm = 0
    channelBlock = 0

    if dynamic_emergency_list.alive:
        for result in dynamic_emergency_list:
            # 电压报警数 # 电流报警数# 通道堵塞报警数
            if result['_id'] == 1:  # 烟感报警数
                smokeAlarm = result['count']
                alarm_sum += result['count']
                continue
            elif result['_id'] == 4:  # 漏电报警数
                leakageAlarm = result['count']
                alarm_sum += result['count']
                continue
    response_data = {'sum': alarm_sum, 'smokeAlarm': smokeAlarm, 'leakageAlarm': leakageAlarm,
                     'voltageAlarm': voltageAlarm,
                     'currentAlarm': currentAlarm, 'channelBlock': channelBlock, 'requestId': uuid.uuid4().hex,
                     'requestStatus': 'SUCCESS',
                     'timeUsed': 10}

    return response_data


@bp.route('/homepage/all_alarm_percent', methods=['POST'])
def all_alarm_percent():
    """报警类型占比"""
    my_db = ToMongo('wavedevice')

    emergency_list = my_db.get_col('odin_business_emergency_record').aggregate(query_group_by_field({}, '$model_name'))
    dynamic_emergency_list = my_db.get_col('odin_business_dynamic_emergency_record').aggregate(
        query_group_by_field({}, '$emergency_type'))

    items = []
    alarm_sum = 0
    if emergency_list.alive and dynamic_emergency_list.alive:
        alarm_sum_1 = traversal_command_cursor(1, emergency_list, items, alarm_sum)
        alarm_sum_2 = traversal_command_cursor(2, dynamic_emergency_list, items, alarm_sum)
        alarm_sum = alarm_sum_1 + alarm_sum_2
    elif emergency_list.alive:
        alarm_sum = traversal_command_cursor(1, emergency_list, items, alarm_sum)
    elif dynamic_emergency_list.alive:
        alarm_sum = traversal_command_cursor(2, dynamic_emergency_list, items, alarm_sum)

    response = {'sum': alarm_sum, 'data': items, 'requestId': uuid.uuid4().hex,
                'requestStatus': 'SUCCESS', 'timeUsed': 10}

    return response


def ergodic_cursor(cursor, dynamic_num, dynamic_on_num, dynamic_off_num):
    if cursor.alive:
        for c in cursor:
            dynamic_num += c['count']
            if c['_id'] == '0' or c['_id'] == 0:
                dynamic_on_num += c['count']
            elif c['_id'] == '1' or c['_id'] == 1:
                dynamic_off_num += c['count']
    return dynamic_num, dynamic_on_num, dynamic_off_num


def ergodic_edit_cursor(cursor, dynamic_num, dynamic_on_num, dynamic_off_num, camera_num):
    if cursor.alive:
        for c in cursor:
            dynamic_num += c['count']
            camera_num = c['count']
            if c['_id'] == '0' or c['_id'] == 0:
                dynamic_on_num += c['count']
            elif c['_id'] == '1' or c['_id'] == 1:
                dynamic_off_num += c['count']
    return dynamic_num, dynamic_on_num, dynamic_off_num, camera_num


def traversal_command_cursor(flag, cursor, items, alarm_sum):
    if not cursor.alive:
        return
    if flag == 1:
        for result in cursor:
            item = {'id': result['_id'], "num": result['count']}
            alarm_sum += result['count']
            items.append(item)
        return alarm_sum
    else:
        for result in cursor:
            item = {'id': result['_id'].replace('1', '烟雾传感器').replace('2', '浸水传感器').replace('3',
                                                                                                      '温度传感器').replace(
                '4', '漏电断路器').replace('5', '气体探测器').replace('6', '静电接地器'), "num": result['count']}
            alarm_sum += result['count']
            items.append(item)
        return alarm_sum


def query_group_by_field_limit5(query, field_name):
    pipeline = [
        {'$match': query},  # 查询条件
        {'$group': {
            '_id': field_name,  # 替换为你要分组的字段名
            'count': {'$sum': 1}  # 计算每个组中的文档数量
        }
        },
        {
            '$sort': {'count': -1}  # 按计数降序排序
        },
        {
            '$limit': 5  # 取前五条文档
        }
    ]
    return pipeline


def query_group_by_field(query, field_name):
    pipeline = [
        {'$match': query},  # 查询条件
        {'$group': {
            '_id': field_name,  # 替换为你要分组的字段名
            'count': {'$sum': 1}  # 计算每个组中的文档数量
        }
        },
        {
            '$sort': {'count': -1}  # 按计数降序排序
        },
    ]
    return pipeline


def calculating_time(your_date_field, frist_time, second_time):
    """查询某字段之间的数据"""
    query = {
        your_date_field: {
            "$gte": frist_time,
            "$lte": second_time
        }
    }
    return query


def query_group_by_field_15day(start_date, end_date, field_name):
    pipeline = [
        {'$match': {field_name: {'$dateToString': {'$gte': start_date, '$lte': end_date}}}},
        {'$group': {'_id': {'$year': '$timestamp', '$month': '$timestamp', '$day': '$timestamp'},
                    'count': {'$sum': 1}}},
        {'$sort': {'_id': 1}}
    ]
    return pipeline


def merge_command_cursor_to_list(cursor_device, cursor_dynamic, field_name):
    top_five = []
    if cursor_device.alive and cursor_dynamic.alive:
        cursor = list(cursor_device) + list(cursor_dynamic)
        cursor = sorted(cursor, key=lambda doc: doc.get(field_name), reverse=True)
        top_five = cursor[:5]
    elif cursor_device.alive:
        top_five = list(cursor_device)
    elif cursor_dynamic.alive:
        top_five = list(cursor_dynamic)
    return top_five


def query_group_none(start_of_day, end_of_day, field_name):
    pipeline = [
        {'$match': {field_name: {'$gte': start_of_day, '$lte': end_of_day}}},
        {'$group': {'_id': 'null', 'total': {'$sum': 1}}}
    ]
    return pipeline


def cal_command_cursor_value_addition(cursor_device, cursor_dynamic):
    count = 0
    if cursor_device.alive and cursor_dynamic.alive:
        for cursor_d in cursor_device:
            for cursor_dy in cursor_dynamic:
                count = cursor_d['total'] + cursor_dy['total']
    elif cursor_device.alive:
        for cursor_d in cursor_device:
            count = cursor_d['total']
    elif cursor_dynamic.alive:
        for cursor_dy in cursor_dynamic:
            count = cursor_dy['total']
    return count

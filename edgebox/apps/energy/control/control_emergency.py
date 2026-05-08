import uuid
from datetime import datetime, timedelta
from flask import Blueprint, request
from Utils.cal_cursor2_list import merge_command_cursor_addition_list,merge_emergency,merge_emergency_by_month
from Utils.cal_datetime import days_of_the_month
from Utils.db import ToMongo
import Utils.logger as logger
mainlogger = logger.getLogger('main')

bp = Blueprint("emergency", __name__, url_prefix='/net-web')

@bp.route('/emergency/query_24h_emergency_day', methods=['POST'])
def query_24h_emergency():
    """按日分组查询每日告警数"""
    my_db = ToMongo('wavedevice')
    params = request.get_json()
    date = params.get("date", None)
    constant_num = params.get("algorithmConstantNum", None)

    dict1 = {}  #视频告警查询条件
    dict2 = {}  #动环告警查询条件

    if date:
        dict1['emergency_time'] = {'$regex': date}
        format = "%Y-%m-%d"
        date_0 = datetime.strptime(date,format)
        date_24 = date_0 + timedelta(days=1)
        dict2['emergency_time'] = {'$gte': date_0,'$lt':date_24}

    if constant_num:
        dict1['model_name'] = constant_num
        dict2['emergency_type'] = constant_num

    query1 = {'$match':dict1}
    query2 = {'$match':dict2}

    cursor_device = my_db.get_col('odin_business_emergency_record').aggregate(
        [query1, {'$group': {'_id': {'$hour': '$create_time'}, 'count': {'$sum': 1}}},{'$project':{'hour':'$_id',"_id":0,"count": 1}},
         {'$sort': {'_id': 1}}])
    cursor_dynamic = my_db.get_col('odin_business_dynamic_emergency_record').aggregate(
        [query2, {'$group': {'_id': {'$hour': '$emergency_time'}, 'count': {'$sum': 1}}},{'$project':{'hour':'$_id',"_id":0,"count": 1}},
         {'$sort': {'_id': 1}}])
    
    items = merge_emergency(cursor_device,cursor_dynamic)

    response_data = {'data': items, 'requestId': uuid.uuid4().hex, 'requestStatus': 'SUCCESS',
                     'timeUsed': 10}
    return response_data


@bp.route('/emergency/query_month_emergency', methods=['POST'])
def query_month_emergency():
    """按月分组查询每月告警数"""
    my_db = ToMongo('wavedevice')
    params = request.get_json()
    date = params.get("date", None)
    constant_num = params.get("algorithmConstantNum", None)

    if constant_num:
        query1 = {
            '$match': {
                'emergency_time': {'$regex': date},
                'model_name': constant_num
            }
        }
    else:
        query1 = {
            '$match': {
                'emergency_time': {'$regex': date}
            }
        }

    date_begin = datetime.strptime(date,"%Y-%m")
    date_end = datetime(date_begin.year,date_begin.month+1,date_begin.day)

    dict2 = {'emergency_time': {'$gte': date_begin,'$lt':date_end}}
    if constant_num:
        dict2['emergency_type'] = constant_num

    query2 = {'$match': dict2}

    cursor_device = my_db.get_col('odin_business_emergency_record').aggregate(
        [query1, {'$group': {'_id': {'$dayOfMonth': '$create_time'}, 'count': {'$sum': 1}}},
         {'$sort': {'_id': 1}}])
    cursor_dynamic = my_db.get_col('odin_business_dynamic_emergency_record').aggregate(
        [query2, {'$group': {'_id': {'$dayOfMonth': '$emergency_time'}, 'count': {'$sum': 1}}},
         {'$sort': {'_id': 1}}])
    items = merge_emergency_by_month(cursor_device, cursor_dynamic,date_begin)
   
    response_data = {'data': items, 'requestId': uuid.uuid4().hex, 'requestStatus': 'SUCCESS',
                     'timeUsed': 10}
    return response_data



@bp.route('/emergency/query_emergency_num_day', methods=['POST'])
def query_emergency_num_day():
    """查询告警数前十"""
    my_db = ToMongo('wavedevice')
    params = request.get_json()
    date = params.get("date", None)
    query1 = {
        '$match': {
            'emergency_time': {'$regex': date}
        }
    }
    if not date:
        query2 = {}
    else:
        datelist = date.split('-')
        if len(datelist) == 3:
            date_begin = datetime.strptime(date,"%Y-%m-%d")
            date_end = date_begin + timedelta(days=1)
        else:
            date_begin = datetime.strptime(date,"%Y-%m")
            date_end = datetime(date_begin.year,date_begin.month+1,date_begin.day)

        query2 = {
            '$match': {
                'emergency_time': {'$gte': date_begin,'$lt':date_end}
            }
        }

    # 查询视频告警：
    cursor_device = my_db.get_col('odin_business_emergency_record').aggregate(
        [query1, {'$group': {'_id': '$model_path', 'count': {'$sum': 1}}},
         {'$sort': {'count': -1}}, {'$limit': 10}])
    # 查询设备告警：
    cursor_dynamic = my_db.get_col('odin_business_dynamic_emergency_record').aggregate(
        [query2, {'$group': {'_id': '$emergency_type', 'count': {'$sum': 1}}},
         {'$sort': {'count': -1}}, {'$limit': 10}])

    top_five = merge_cursor_to_list(cursor_device, cursor_dynamic, 'count')
    items = []
    if len(top_five) > 0:
        for result in top_five:
            item = {'modelName': result['_id'],
                    'count': result['count']}
            items.append(item)
    response_data = {'dynamics': items, 'requestId': uuid.uuid4().hex, 'requestStatus': 'SUCCESS', 'timeUsed': 10}
    return response_data

@bp.route('/emergency/query_emergency_type', methods=['POST'])
def query_emergency_type():

    my_db = ToMongo('wavedevice')
    params = request.get_json()
    date = params.get("date", None)

    query1 = {'emergency_time': {'$regex': date}}

    if not date:
        query2 = {}
    else:
        datelist = date.split('-')
        if len(datelist) == 3:
            date_begin = datetime.strptime(date,"%Y-%m-%d")
            date_end = date_begin + timedelta(days=1)
        else:
            date_begin = datetime.strptime(date,"%Y-%m")
            date_end = datetime(date_begin.year,date_begin.month+1,date_begin.day)

        query2 = {'emergency_time': {'$gte': date_begin,'$lt':date_end}}


    # 查询视频告警：
    emergency = my_db.get_col('odin_business_emergency_record').distinct('model_path',query1)
    
    # 查询设备告警：
    dynamic = my_db.get_col('odin_business_dynamic_emergency_record').distinct('emergency_type',query2)
        
    mainlogger.info("告警类型-视频告警：%s;设备告警：%s"%(emergency,dynamic))
    result = list(emergency) + list(dynamic)

    response_data = {'typeList': result, 'requestId': uuid.uuid4().hex, 'requestStatus': 'SUCCESS', 'timeUsed': 10}

    return response_data


def merge_cursor_to_list(cursor_device, cursor_dynamic, field_name):
    top_five = []
    if cursor_device.alive and cursor_dynamic.alive:
        cursor = list(cursor_device) + list(cursor_dynamic)
        cursor = sorted(cursor, key=lambda doc: doc.get(field_name), reverse=True)
#        mainlogger.info("cursor:%s"%cursor)
        top_five = list(cursor)
    elif cursor_device.alive:
        top_five = list(cursor_device)
    elif cursor_dynamic.alive:
        top_five = list(cursor_dynamic)
    return top_five

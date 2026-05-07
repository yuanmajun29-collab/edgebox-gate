import uuid

from flask import Blueprint, request, jsonify, json

from Utils.Utils import set_fail_result, set_success_result
from Utils.db import ToMongo
from Utils.Utils import *
from Utils.datacfg import area_db,area_web

bp = Blueprint("area", __name__, url_prefix='/net-web')


def findPidArea(area_id,area_col):
    if not area_id:
        return
    children = []
    areaItems = area_col.find({"area_pid":area_id})
    if not areaItems:
        return
    for item in areaItems:
        areainfo = database_to_dict(item,area_db,area_web)
        areaId = areainfo.get("areaId")
        areainfo["children"] = findPidArea(areaId,area_col)
        children.append(areainfo)
    return children

def valid_param_required(area_name, area_pid, sort_code, error_response):
    if not area_name:
        error_response['errorCodeDesc'] = "areaName 不能为空"
        raise Exception(BaseException(error_response))
    if not area_pid:
        error_response['errorCodeDesc'] = "areaPid 不能为空"
        raise Exception(BaseException(error_response))
    if not sort_code:
        error_response['errorCodeDesc'] = "sortCode 不能为空"
        raise Exception(BaseException(error_response))
    return
  
@bp.route('/area/findTree', methods=['POST'])
def findTree():
    # 查询出所有数据，分组归类
    my_db = ToMongo('wavedevice')
    area_col = my_db.get_col("odin_device_area")
    treeList = findPidArea("-1",area_col)

    response = set_success_result()   
    response["treeList"] = treeList
    return jsonify(response)


@bp.route('/area/update', methods=['POST'])
def upd_area_info():
    '''修改区域'''
    my_db = ToMongo('wavedevice')
    params = request.get_json()
    area_id = params.get("areaId", None)
    area_name = params.get("areaName", None)
    area_desc = params.get("areaDesc", None)

    col = my_db.get_col('odin_device_area')
    query = {'area_id':{'$ne':area_id}}
    area_name_list = col.distinct('area_name',query)

    # 非空参数检验
    error_response = set_fail_result()
    if not area_id:
        error_response['errorCodeDesc'] = "区域id不能为空"
        return jsonify(error_response)
    if not area_name:
        error_response['errorCodeDesc'] = "区域名称不能为空"
        return jsonify(error_response)
    if area_name in area_name_list:
        error_response['errorCodeDesc'] = "区域名称不能重复"
        return jsonify(error_response)


    item = {'area_name': area_name, 'area_desc': area_desc}
    my_db.update('odin_device_area', {'area_id': area_id}, {'$set': item})
    response_data = set_success_result()
    return jsonify(response_data)


@bp.route('/area/delete', methods=['POST'])
def del_area_info():
    '''删除区域'''
    my_db = ToMongo('wavedevice')
    params = request.get_json()
    area_id = params.get("areaId", None)
    if not area_id:
        error_response = set_fail_result()
        error_response['errorCodeDesc'] = "areaId 不能为空"
        return jsonify(error_response)
    my_db.delete('odin_device_area', {'area_id': area_id})
    response_data = set_success_result()
    return jsonify(response_data)


@bp.route('/area/add', methods=['POST'])
def add_area_info():
    '''新增区域'''
    my_db = ToMongo('wavedevice')
    params = request.get_json()
    area_name = params.get("areaName", None)
    area_desc = params.get("areaDesc", None)
    area_pid = params.get("areaPid", None)
    sort_code = params.get("sortCode", None)
    error_response = set_fail_result()

    # 校验参数不能为空:
    try:
        valid_param_required(area_name, area_pid, sort_code, error_response)
    except Exception as e:
        return json.loads(str(e).replace("'", "\""))
    # 名称重复检验：
    value_list = my_db.query_collection_count_by_field('odin_device_area', {"area_name": area_name})
    try:
        next(value_list)
        error_response['errorCodeDesc'] = "areaName 不能重复"
        return jsonify(error_response)
    except StopIteration:
        area_id = uuid.uuid4().hex
        item = {'area_id': area_id, 'area_name': area_name, 'area_pid': area_pid, 'area_desc': area_desc,
                'sort_code': sort_code}
        my_db.insert('odin_device_area', item)
        success_response = set_success_result()
        success_response['userId'] = area_id
        return jsonify(success_response)



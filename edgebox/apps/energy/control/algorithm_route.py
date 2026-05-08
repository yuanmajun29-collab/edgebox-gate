from datetime import datetime
from threading import Thread

from flask import Blueprint
import Utils.edgebox_repo  # noqa: F401
from edgebox.db.mongo_collections import WORK_FLOW_ALGORITHM_CONSTANT
from Utils.Utils import *
from Utils.db import *
from Utils.jwt_verify import *
from Utils.datacfg import constant_database, constant_web
from system.sync_model import sync_alg_setting

bp = Blueprint("algconstant", __name__, url_prefix='/net-web')


# 布控任务
@bp.route('/algorithmConstant/queryAlgorithmList', methods=['GET', 'POST'])
@login_required
def queryAlgorithmList():
    my_db = ToMongo("wavedevice")
    constant_coll = my_db.get_col(WORK_FLOW_ALGORITHM_CONSTANT)
    res = {'穿戴(A1)': [], '手持(B1)': [], '危险行为(C1)': [], '越界行为(C2)': [], '违规行为(C3)': [], '消防(D1)': [],
           '设备(E1)': [], '人脸(F1)': [], '摄像机内置算法(G1)': []}
    index_dict = {'穿戴(A1)': 1, '手持(B1)': 2, '危险行为(C1)': 3, '越界行为(C2)': 4, '违规行为(C3)': 5, '消防(D1)': 6,
                  '设备(E1)': 7, '人脸(F1)': 8, '摄像机内置算法(G1)': 9}

    keys = res.keys()

    for key in keys:
        index = index_dict[key]
        items = constant_coll.find({'algorithm_constant_type': index})
        for item in items:
            item = database_to_dict(item, constant_database, constant_web)
            item['audioValue'] = item['algorithmSoundFile']
            res[key].append(item)
    response = set_success_result()
    response['constantMaps'] = res
    return jsonify(response)


@bp.route('/algorithmConstant/updateAlgorithm', methods=['GET', 'POST'])
@login_required
def updateAlgorithm():
    params = request.get_json()
    my_db = ToMongo('wavedevice')

    constantId = params.get('algorithmConstantId', None)
    algorithmConstantName = params.get('algorithmConstantName', None)
    algorithmColor = params.get('algorithmColor', None)
    algorithmConstantNum = params.get('algorithmConstantNum', None)
    algorithmServiceNum = params.get('algorithmServiceNum', None)
    emergencyIntervalTime = params.get('emergencyIntervalTime', None)
    algorithmLevel = params.get('algorithmLevel', None)
    modelName = params.get('modelName', None)
    rateNum = params.get('rateNum', None)

    audioFile = params.get('audioFile', None)
    audioType = params.get('audioType', None)
    audioValue = params.get('audioValue', None)

    rate_num = float(rateNum) if rateNum else None
    query = {'algorithm_constant_id': constantId}

    if rate_num:
        constant_col = my_db.get_col(WORK_FLOW_ALGORITHM_CONSTANT)
        origin_item = constant_col.find_one(query)
        rateNum_ori = origin_item['rate_num']
        constant_num = origin_item['algorithm_constant_num']
        mission_query = {'mission_status': 0, 'algorithm_id': {'$regex': constant_num}}

    if audioType == '1':
        algorithm_sound_file = audioValue
    elif audioType == '2':
        algorithm_sound_file = audioFile

    item = {'algorithm_constant_name': algorithmConstantName,
            'algorithm_color': algorithmColor,
            'algorithm_level': int(algorithmLevel),
            'algorithm_interval': int(emergencyIntervalTime),
            'rate_num': rate_num,
            'algorithm_sound_type': int(audioType),
            'algorithm_sound_file': algorithm_sound_file}
    my_db.update(WORK_FLOW_ALGORITHM_CONSTANT, query, {'$set': item})

    newItem = database_to_dict3(item,constant_database,constant_web)
    newItem['algorithmServiceNum'] = algorithmServiceNum
    newItem['algorithmConstantNum'] = algorithmConstantNum
    sync_thread = Thread(target=sync_alg_setting,args=[newItem])
    sync_thread.start()

    response = set_success_result()
    return jsonify(response)

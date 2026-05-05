from flask import Blueprint, jsonify, request
from utils.db import ToMongo
import uuid
import json
from utils.jwt_verify import *

bp = Blueprint('device_roiapi', __name__, url_prefix='/net-web')


def roi_area(points):
    if points:
        xlist = []
        ylist = []
        result = {}
        for iter in points:
            xlist.append(iter['x'])
            ylist.append(iter['y'])
        result['x'] = min(xlist)
        result['y'] = min(ylist)
        result['width'] = max(xlist) - min(xlist)
        result['height'] = max(ylist) - min(ylist)
        return result
    else:
        return


@bp.route('/roiArea/addRoiArea', methods=['POST'])
@login_required
def addRoiArea():
    '''
    接口:添加视频ROI区域
    '''
    my_db = ToMongo("wavedevice")
    params = request.get_json()
    camera_id = params.get("cameraId", None)
    roi_info = params.get("roiAreaInfo", None)
    roi_info = json.loads(roi_info)
    roi_name = params.get("roiName", None)
    algorithms_id = params.get("algorithmConstantId", None)
    #  roi_id = params.get("roiId",None)
    create_time = datetime.now()
    roi_area_record_id = str(uuid.uuid4())

    roi_area_info = {}
    roi_area_info['sourceWidth'] = roi_info['sourceWidth']
    roi_area_info['sourceHeight'] = roi_info['sourceHeight']
    roi_area_info['left'] = roi_info['left']
    roi_area_info['top'] = roi_info['top']
    roi_area_info['points'] = roi_info['points']

    position_id = my_db.get_col("odin_device_device_position_associate").find_one({"device_id": camera_id})[
        "position_id"]
    organization_id = my_db.get_col("odin_device_position").find_one({"position_id": position_id})["organization_id"]
    res = my_db.get_col("odin_device_roi_area_record").find({"camera_id": camera_id}).sort("roi_id", -1)

    if res.count() == 0:
        num_max = 0
    else:
        num_max = res[0]['roi_id']

    res_item = {"camera_id": camera_id, "roi_area_info": json.dumps(roi_area_info), "roi_name": roi_name,
                "algorithm_constant_id": algorithms_id,
                "roi_id": num_max + 1, "create_time": create_time, "roi_area_record_id": roi_area_record_id,
                "organization_id": organization_id}

    result = my_db.insert("odin_device_roi_area_record", res_item)

    from alg.AlgorithServer_v2 import SenderThread
    sender = SenderThread(current_app.app_context())
    sender.send_3007_message()

    response_data = {"roiAreaAddRecordId": roi_area_record_id}
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 556

    return jsonify(response_data)


@bp.route('/roi/deleteRoi', methods=['POST'])
@login_required
def deleteRoi():
    '''
    接口:删除ROI区域
    '''
    my_db = ToMongo("wavedevice")
    params = request.get_json()
    camera_id = params.get("cameraId", None)
    roi_id = params.get("roiId", None)
    roiAreaRecordId = params.get("roiAreaRecordId", None)

    res = my_db.delete("odin_device_roi_area_record", {"camera_id": camera_id, "roi_id": roi_id})

    from alg.AlgorithServer_v2 import SenderThread
    sender = SenderThread(current_app.app_context())
    sender.send_3007_message()

    response_data = {}
    response_data['failCameraList'] = []
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 556
    return jsonify(response_data)


@bp.route('/roiArea/getRoiAreaInfo', methods=['POST'])
# @login_required
def getRoiAreaInfo():
    '''
    接口:查询ROI区域
    '''
    my_db = ToMongo("wavedevice")
    params = request.get_json()
    camera_id = params.get("cameraId", None)
    algorithms_id = params.get("algorithmConstantId", None)

    result = my_db.get_col("odin_device_roi_area_record").find({"camera_id": camera_id, "algorithm_constant_id": algorithms_id},
                                                               {"_id": 0})

    roi_list = []
    if result:
        for res in result:
            roi_iter = {'cameraId': camera_id, 'roiName': res['roi_name'],
                        'algorithmConstantId': res['algorithm_constant_id'],
                        'createTime': int(res['create_time'].timestamp()) * 1000,
                        'organizationId': res['organization_id'],
                        'roiAreaInfo': res['roi_area_info'], 'roiAreaRecordId': res['roi_area_record_id'],
                        'roiId': res['roi_id']}
            roi_list.append(roi_iter)

    response_data = {'roiAreaDetailInfoVoList': roi_list, 'requestId': uuid.uuid4().hex, 'requestStatus': "SUCCESS",
                     'timeUsed': 556}
    return jsonify(response_data)


@bp.route('/roiArea/modifyRoiStatus', methods=['POST'])
@login_required
def modifyRoiStatus():
    '''
    接口:roi开关
    '''
    my_db = ToMongo("wavedevice")
    params = request.get_json()
    roiStatus = params.get("roiStatus", None)
    roiId = params.get("roiId", None)

    query = {"roi_id": roiId}
    newItem = {"roi_status": roiStatus}
    res = my_db.update("odin_device_roi_area_record", query, {"$set": newItem})

    from alg.AlgorithServer_v2 import SenderThread
    sender = SenderThread(current_app.app_context())
    sender.send_3007_message()

    response_data = {}
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 556
    return jsonify(response_data)


@bp.route('/roi/queryRoi', methods=['POST'])
@login_required
def queryRoi():
    '''
    接口:查询ROI区域
    '''
    my_db = ToMongo("wavedevice")
    params = request.get_json()
    cameraId = params.get("cameraId", None)
    roiType = params.get("roiType", None)
    algorithmConstantId = params.get("algorithmConstantId", None)
    roiId = params.get("roiId", None)

    roi_list = []

    query = {}
    if cameraId:
        query['camera_id'] = cameraId
    if algorithmConstantId:
        query['algorithm_constant_id'] = algorithmConstantId
    if roiId:
        query['roi_id'] = roiId

    result = my_db.get_col("odin_device_roi_area_record").find(query, {"_id": 0})
    if result:
        for res in result:
            iter = {}
            iter['cameraId'] = cameraId
            iter['roiName'] = res['roi_name']
            iter['algorithmConstantId'] = res['algorithm_constant_id']
            iter['createTime'] = int(res['create_time'].timestamp()) * 1000
            iter['organizationId'] = res['organization_id']
            iter['roiAreaInfo'] = res['roi_area_info']
            iter['roiAreaRecordId'] = res['roi_area_record_id']
            iter['roiId'] = res['roi_id']
            iter['roiType'] = res['roi_type']
            roi_list.append(iter)

    response_data = {}
    response_data['roiAreaDetailInfoVoList'] = roi_list
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 556
    return jsonify(response_data)


@bp.route('/roi/addRoi', methods=['POST'])
@login_required
def addRoi():
    '''
    接口:添加视频ROI区域
    '''
    my_db = ToMongo("wavedevice")
    params = request.get_json()
    camera_id = params.get("cameraId", None)
    roi_info = params.get("roiAreaInfo", None)
    roi_id = params.get("roiId", None)
    algorithms_id = params.get("algorithmConstantId", None)
    create_time = datetime.now()
    roi_area_record_id = str(uuid.uuid4())

    roi_info = json.loads(roi_info)
    roi_area_info = {'sourceWidth': roi_info['sourceWidth'], 'sourceHeight': roi_info['sourceHeight'],
                     'left': roi_info['left'], 'top': roi_info['top'], 'points': roi_info['points']}

    res_item = {"camera_id": camera_id, "roi_area_info": json.dumps(roi_area_info), "roi_name": None,
                "algorithm_constant_id": algorithms_id,
                "roi_id": roi_id, "create_time": create_time, "roi_area_record_id": roi_area_record_id,
                "organization_id": None, "roi_type": None}

    my_db.insert("odin_device_roi_area_record", res_item)

    from alg.AlgorithServer_v2 import SenderThread
    sender = SenderThread(current_app.app_context())
    sender.send_3007_message()
    
    response_data = {"roiAreaAddRecordId": roi_area_record_id, 'requestId': uuid.uuid4().hex,
                     'requestStatus': "SUCCESS", 'timeUsed': 556}
    return jsonify(response_data)

from crypt import methods
from datetime import datetime
from flask import Blueprint, jsonify, Flask ,request
from Utils.db import ToMongo
import uuid
import json
from Utils.jwt_verify import *

bp = Blueprint('device_roiapi',__name__,url_prefix='/net-web/roiArea')

def roi_area(points):
    if points:
        xlist=[]
        ylist=[]
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
    


@bp.route('/addRoiArea',methods=['POST'])
@login_required
def addRoiArea():
    '''
    接口:添加视频ROI区域
    '''
    my_db = ToMongo("wavedevice")
    params = request.get_json()
    camera_id = params.get("cameraId",None)   
    roi_info = params.get("roiAreaInfo",None)   
    roi_info = json.loads(roi_info)
    roi_name = params.get("roiName",None)
    algorithms_id = params.get("algorithmConstantId",None)
  #  roi_id = params.get("roiId",None)
    create_time = datetime.now()
    roi_area_record_id = str(uuid.uuid4())

    roi_area_info = {}
    roi_area_info['sourceWidth'] = roi_info['sourceWidth']
    roi_area_info['sourceHeight'] = roi_info['sourceHeight']
    roi_area_info['left'] = roi_info['left']
    roi_area_info['top'] = roi_info['top']
    roi_area_info['points'] = roi_info['points']

    position_id = my_db.get_col("odin_device_device_position_associate").find_one({"device_id":camera_id})["position_id"]
    organization_id = my_db.get_col("odin_device_position").find_one({"position_id":position_id})["organization_id"]
    res = my_db.get_col("odin_device_roi_area_record").find({"camera_id":camera_id}).sort("roi_id",-1)

    if res.count() == 0:
        num_max =0
    else:
        num_max = res[0]['roi_id']



    res_item = {"camera_id":camera_id,"roi_area_info":json.dumps(roi_area_info),"roi_name":roi_name,"algorithm_constant_id":algorithms_id,
           "roi_id":num_max+1,"create_time":create_time,"roi_area_record_id":roi_area_record_id,"organization_id":organization_id}    

    result = my_db.insert("odin_device_roi_area_record",res_item)

    from algorith_server.AlgorithServer_v2 import SenderThread
    sender = SenderThread( current_app.app_context() )
    sender.send_3007_message()

    response_data = {"roiAreaAddRecordId":roi_area_record_id}
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 556

    return jsonify(response_data)

@bp.route('/delRoiArea', methods=['POST'])
@login_required
def delRoiArea():
    '''
    接口:删除ROI区域
    '''
    my_db = ToMongo("wavedevice")
    params = request.get_json()
    camera_id = params.get("cameraId",None)
    roi_id = params.get("roiId",None)

    res = my_db.delete("odin_device_roi_area_record",{"camera_id":camera_id,"roi_id":roi_id})

    from algorith_server.AlgorithServer_v2 import SenderThread
    sender = SenderThread( current_app.app_context() )
    sender.send_3007_message()

    response_data = {}
    response_data['failCameraList'] = []
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 556
    return jsonify(response_data)

@bp.route('/getRoiAreaInfo', methods=['POST'])
@login_required
def getRoiAreaInfo():
    '''
    接口:查询ROI区域
    '''
    my_db = ToMongo("wavedevice")
    params = request.get_json()
    camera_id_list = params.get("cameraIdList",None) 

    roi_list = []
    for camera_id in camera_id_list:
        result = my_db.get_col("odin_device_roi_area_record").find({"camera_id":camera_id},{"_id":0})
        if result:
            for res in result:
                iter = {}
                iter['cameraId']  = camera_id
                iter['roiName']  = res['roi_name']
                iter['algorithmConstantId']  = res['algorithm_constant_id']
                iter['createTime']  = int(res['create_time'].timestamp())*1000
                iter['organizationId']  = res['organization_id']
                iter['roiAreaInfo']  = res['roi_area_info']
                iter['roiAreaRecordId']  = res['roi_area_record_id']
                iter['roiId']  = res['roi_id']
                roi_list.append(iter)
    response_data = {}
    response_data['roiAreaDetailInfoVoList'] = roi_list
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 556
    return jsonify(response_data)

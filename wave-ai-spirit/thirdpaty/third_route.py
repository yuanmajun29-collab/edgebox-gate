from flask import Blueprint,request,jsonify
from .third_utils import *
import uuid

bp = Blueprint("thirdoutput",__name__, url_prefix='/net-web')
@bp.route('/thirdoutput/queryAllDeviceInfo', methods=['GET','POST'])
def queryAllDeviceInfo():
    '''
    接口注释：查询算力设备列表，算力设备支持的识别模型、绑定的摄像机
    '''
    params = request.get_json()
    authenticationCode = params.get('authenticationCode',None)

    instance = ThirdPartyOutputService()
    result = instance.validAuthenticationCode(authenticationCode)

    if not result:
        return "authenticationCode无效"

    my_db = ToMongo('wavedevice')
    cameraInfos = get_camera_info(my_db)
    workFlowAlgorithmConstants = get_constant_info(my_db)
    soundDeviceVos = get_sound_info(my_db)
    deviceEquips = get_equips_info(my_db)
    data = {
            'deviceEquips':deviceEquips,
            'cameraInfos':cameraInfos,
            'soundDeviceVos':soundDeviceVos,
            'workFlowAlgorithmConstants':workFlowAlgorithmConstants
            }

    response_data = {}
    response_data['data'] = data
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 556
    return jsonify(response_data)

@bp.route('/thirdoutput/queryCameraEdit', methods=['GET','POST'])
def queryCameraEdit():
    '''
    接口注释：查询摄像机列表及摄像机参数
    '''
    params = request.get_json()
    authenticationCode = params.get('authenticationCode',None)

    instance = ThirdPartyOutputService()
    result = instance.validAuthenticationCode(authenticationCode)

    if not result:
        return "authenticationCode无效"

    my_db = ToMongo('wavedevice')
    cameraInfos = get_camera_info(my_db)
    for cam in cameraInfos:
        device_id = cam['cameraId']
        roiinfo = get_roi_info(my_db,device_id)
        cam['roiInfo'] = roiinfo
   
    response_data = {}
    response_data['data'] = cameraInfos
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 556
    return jsonify(response_data)

@bp.route('/thirdoutput/queryControlManage', methods=['GET','POST'])
def queryControlManage():
    '''
    接口注释： 查询布控任务列表及任务内容
    '''
    params = request.get_json()
    authenticationCode = params.get('authenticationCode',None)

    instance = ThirdPartyOutputService()
    result = instance.validAuthenticationCode(authenticationCode)

    if not result:
        return "authenticationCode无效"

    my_db = ToMongo('wavedevice')
    controlInfos = get_control_info(my_db)
       
    response_data = {}
    response_data['data'] = controlInfos
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 556
    return jsonify(response_data)
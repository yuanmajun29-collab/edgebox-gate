from flask import Blueprint, request, jsonify
from Utils.Utils import generate_log
import uuid
from Utils.db import ToMongo
from datetime import datetime

bp = Blueprint("positions", __name__, url_prefix='/net-web')


@bp.route('/position/getpositionlist', methods=['POST'])
def getpositionlist():
    '''
    接口注释：新增摄像头时,
             返回摄像头的位置信息、每个位置关联的摄像头；
    '''
    response_data = {}
    positionInfos = []
    my_db = ToMongo('wavedevice')
    camera_coll = my_db.get_col('odin_device_position')
    position_coll = my_db.get_col('odin_device_device_position_associate')
    datas = camera_coll.find({}, {'_id': 0})
    for data in datas:
        item = {}
        cameraIdList = []
        positionid = data['position_id']
        reslist = position_coll.find({'position_id': positionid})
        for res in reslist:
            cameraIdList.append(res['device_id'])
        item['cameraIdList'] = cameraIdList
        item['lonAndLat'] = data['lon_and_lat']
        item['personCardIdList'] = None
        item['positionArea'] = data['position_area']
        item['positionCity'] = data['position_city']
        item['positionCounty'] = data['position_county']
        item['positionDesc'] = data['position_desc']
        item['positionId'] = data['position_id']
        item['positionNum'] = data['position_num']
        item['positionProvince'] = data['position_province']

        positionInfos.append(item)
    response_data['positionInfos'] = positionInfos
    response_data['totalCount'] = len(positionInfos)
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 40

    return jsonify(response_data)


@bp.route('/position/batchaddposition', methods=['GET', 'POST'])
def batchAddPosition():
    '''
    接口描述：用户通过页面，可以批量添加位置
    '''
    positionInfos = request.json.get('postionInfos')
    successsList = []
    my_db = ToMongo('wavedevice')
    generate_log(request, db=my_db)
    position_assoiate_coll = my_db.get_col('odin_device_device_position_associate')
    for position in positionInfos:
        cameraId = position['cameraId']
        formattedAddress = position['formattedAddress']
        lonAndLat = position['lonAndLat']
        organizationId = position['organizationId']
        positionArea = position['positionArea']
        positionCity = position['positionCity']
        positionCounty = position['positionCounty']
        positionDesc = position['positionDesc']
        positionProvince = position['positionProvince']
        positionId = position_assoiate_coll.find_one({"device_id": cameraId})['position_id']
        item = {"lonAndLat": lonAndLat, "organizationId": organizationId, "positionArea": positionArea,
                "positionCity": positionCity, "positionCounty": positionCounty, "positionDesc": positionDesc,
                "positionId": positionId, "positionProvince": positionProvince}
        successsList.append(item)
        item_database = {"position_id": positionId, "position_desc": positionDesc, "position_city": positionCity,
                         "position_area": positionArea, "create_time": None, "update_time": None,
                         "position_num": None, "organization_id": organizationId, "lon_and_lat": lonAndLat,
                         "position_province": positionProvince, "position_county": positionCounty,
                         'camera_id': cameraId}
        item_database['create_time'] = item_database['update_time'] = datetime.now()

    my_db.insert('odin_device_position', item_database)

    response = {}
    response['requestId'] = uuid.uuid4().hex
    response['requestStatus'] = "SUCCESS"
    response['timeUsed'] = 40
    response['failList'] = []
    response['successsList'] = successsList
    return jsonify(response)


@bp.route('/position/getpositioninfo', methods=['POST'])
def getpositioninfo():
    '''
    接口注释：用户通过页面，获取位置详情
    '''
    params = request.get_json()
    positionIdList = params.get('positionIdList', None)
    my_db = ToMongo('wavedevice')
    position_col = my_db.get_col('odin_device_position')

    positionInfos = []
    for positionId in positionIdList:
        position_item = position_col.find_one({'position_id': positionId})
        item = {}
        item['positionDesc'] = position_item['position_desc']
        item['positionProvince'] = position_item['position_province']
        item['positionCity'] = position_item['position_city']
        item['positionCounty'] = position_item['position_county']
        item['positionArea'] = position_item['position_area']
        item['lonAndLat'] = position_item['lon_and_lat']
        item['positionId'] = positionId
        item['positionNum'] = str(position_item['position_num'])
        item['updateTime'] = position_item['update_time'].strftime('%Y-%m-%d %H:%M:%S')
        positionInfos.append(item)

    response_data = {}
    response_data['positionInfos'] = positionInfos
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 40

    return jsonify(response_data)


@bp.route('/position/updateposition', methods=['POST'])
def updateposition():
    '''
    接口注释：更新摄像头的位置信息
    '''
    params = request.get_json()
    cameraId = params.get('cameraId', None)
    formattedAddress = params.get('formattedAddress', None)
    lonAndLat = params.get('lonAndLat', None)
    organizationId = params.get('organizationId', None)
    positionArea = params.get('positionArea', None)
    positionCity = params.get('positionCity', None)
    positionCounty = params.get('positionCounty', None)
    positionDesc = params.get('positionDesc', None)
    positionId = params.get('positionId', None)
    positionProvince = params.get('positionProvince', None)

    my_db = ToMongo('wavedevice')
    generate_log(request, db=my_db)
    update_item = {"position_desc": positionDesc, "position_city": positionCity, "position_area": positionArea,
                   "update_time": datetime.now(), "organization_id": organizationId, "position_county": positionCounty,
                   "position_province": positionProvince, "lon_and_lat": lonAndLat, "camera_id": cameraId}
    if positionId:
        my_db.update("odin_device_position",
                     {"position_id": positionId}, {'$set': update_item})
    else:
        positionId = uuid.uuid4().hex
        update_item['position_id'] = positionId
        my_db.insert("odin_device_position", update_item)

    response_data = {}
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 40

    return jsonify(response_data)

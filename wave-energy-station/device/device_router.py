from flask import Blueprint, Flask
from utils.db import *
import cv2
from threading import Thread
from utils.CheckdeviceStatus import CheckInService
from utils.Utils import *
from utils.jwt_verify import *
from utils.datacfg import positionkeys_database, positionkeys_web, area_db, area_web, camerakeys_database, \
    camerakeys_web
from system.sync_model import *

bp = Blueprint('device_api', __name__, url_prefix='/net-web')


def position_asso_cam(position_col, position_asso_col, info):
    position_list = position_col.find({'position_area': {"$regex": info}})
    result = []
    if position_list.count() == 0:
        return result
    for item in position_list:
        res = position_asso_col.find_one({"position_id": item['position_id']})
        if res:
            result.append(res['device_id'])
    return result


def findPidAreaIdList(area_id, area_col, subIdList):
    '''
    查找所有子区域id
    '''
    if not area_id:
        return subIdList
    areaItems = area_col.find({"area_pid": area_id})
    for item in areaItems:
        areaId = item.get("area_id")
        subIdList.append(areaId)
        subIdList = findPidAreaIdList(areaId, area_col, subIdList)
    subIdList.append(area_id)
    return subIdList


def findAreaCamera(area_id, area_col, camera_col, position_col):
    if not area_id:
        return
    children = []
    areaItems = area_col.find({"area_pid": area_id})
    if not areaItems:
        return
    for item in areaItems:
        areainfo = database_to_dict(item, area_db, area_web)
        areaId = areainfo.get("areaId")
        areainfo["children"] = findAreaCamera(areaId, area_col, camera_col, position_col)
        areainfo["type"] = "1"
        children.append(areainfo)
    cameraItems = camera_col.find({"area_id": area_id})
    areaItem = area_col.find_one({"area_id": area_id})
    for devItem in cameraItems:
        cameraInfo = database_to_dict(devItem, camerakeys_database, camerakeys_web)
        cameraIp = cameraInfo.get("cameraIp")
        cameraId = cameraInfo.get("cameraId")
        cameraName = cameraInfo.get("cameraName")
        areaName = areaItem.get("area_name")
        positionItem = position_col.find_one({"camera_id": cameraId})
        position_info = database_to_dict(positionItem, positionkeys_database, positionkeys_web)
        cameraInfo = dict(cameraInfo, **position_info)
        cameraInfo["areaName"] = areaName
        info = {"cameraIp": cameraIp,
                "cameraInfo": cameraInfo,
                "cameraId": cameraId,
                "cameraName": cameraName,
                "pid": area_id,
                "type": "2"}
        children.append(info)
    return children


@bp.route('/vidicon/findAreaCameraTree', methods=['POST'])
def findAreaCameraTree():
    my_db = ToMongo('wavedevice')
    area_col = my_db.get_col("odin_device_area")
    camera_col = my_db.get_col("odin_device_camera_edit")
    position_col = my_db.get_col("odin_device_position")
    treeList = findAreaCamera("-1", area_col, camera_col, position_col)

    response = set_success_result()
    response["areaTreeVo"] = treeList
    return jsonify(response)


@bp.route('/vidicon/pageQueryCameraEdit', methods=['POST'])
@login_required
def pageQueryCameraEdit():
    '''
    查询摄像机列表
    '''
    try:
        params = request.get_json()
        sorttype = params.get("sortType", None)  # DESC 降序 ；  ASC 升序
        sortBy = params.get("sortBy", None)
        page = int(params.get("page", None))
        pageSize = params.get("pageSize", None)
        keywords = params.get("cameraNameOrPositionOrIp", None)
        camera_status = params.get("cameraStatus", None)
        cameraNum = params.get("cameraNum", None)
        areaId = params.get("areaId", None)
        queryType = params.get("queryType", None)  # 是否包含下级区域的摄像头

        if sorttype == 'DESC':
            KEY = -1
        elif sorttype == 'ASC':
            KEY = 1
        else:
            KEY = -1  # 默认降序排列

        my_db = ToMongo('wavedevice')
        camera_coll = my_db.get_col('odin_device_camera_edit')
        associate_coll = my_db.get_col('odin_device_device_position_associate')
        position_coll = my_db.get_col('odin_device_position')
        # control_associate_coll = my_db.get_col('work_flow_mission_device_associate')
        # control_manage_coll = my_db.get_col('odin_business_control_manage')
        mission_col = my_db.get_col('control_manage_mission')
        asso_col = my_db.get_col('control_device_algorithm_associate')

        query = {}
        if cameraNum:
            query['camera_num'] = {'$regex': cameraNum}

        if areaId:
            if queryType == 0:
                area_col = my_db.get_col('odin_device_area')
                subIdList = findPidAreaIdList(areaId, area_col, subIdList=[])
                query['area_id'] = {"$in": subIdList}
            else:
                query['area_id'] = areaId

        if keywords:
            assocam = position_asso_cam(position_coll, associate_coll, keywords)
            query['$or'] = [{'camera_name': {'$regex': keywords}}, {'camera_ip': {'$regex': keywords}},
                            {'camera_id': {'$in': assocam}}]

        if page and pageSize:
            num = (page - 1) * pageSize
            res = camera_coll.find(query).sort(sortBy, KEY).skip(num).limit(pageSize)
        else:
            res = camera_coll.find(query).sort(sortBy, KEY)

        camera_list = []
        camera_status_dict = cs.device_status_list

        for data in res:
            item = {}
            format_pattern = '%Y-%m-%d %H:%M:%S'
            item['cameraAccount'] = data['camera_account']
            item['cameraCreateTime'] = data['create_time'].strftime(format_pattern) if data['create_time'] else None
            item['cameraId'] = data['camera_id']
            item['cameraIp'] = data['camera_ip']
            item['cameraIpLabel'] = data['camera_ip_label']
            item['cameraMac'] = data['camera_mac']
            item['cameraName'] = data['camera_name']
            item['cameraNum'] = data['camera_num']
            item['cameraPassword'] = data['camera_password']
            item['cameraRemarks'] = data['camera_remarks']
            item['cameraSource'] = data['camera_source']
            item['cameraStatus'] = data['camera_status']
            item['cameraType'] = data['camera_type']
            item['cameraUpdateTime'] = data['update_time'].strftime(format_pattern) if data['update_time'] else None
            item['extendInfo'] = data['extend_info']
            stream_url = data.get("stream_url")
            item['mainUrl'] = stream_url if stream_url else data['main_url']
            item['organizationId'] = data['organization_id']
            item['rtspPort'] = data['rtsp_port']
            item['productKey'] = data['product_key']
            item['setType'] = data['set_type']
            item['encodingFormat'] = data['encoding_format']
            item['codeStream'] = data['code_stream']
            item['areaId'] = data.get("area_id")
            item['nvrChannel'] = data.get("nvr_channel")

            if item['extendInfo']:
                item['cameraProductType'] = int(item['extendInfo'].split("=")[-1])
            offline_time = data.get("offline_time")

            data = item
            try:
                device_status = camera_status_dict[data["cameraIp"]]
            except:
                device_status = data["cameraStatus"]
            if device_status == "1":
                data["cameraStatus"] = 1
                item['offlineTime'] = offline_time.strftime('%Y-%m-%d %H:%M') if offline_time else None
            else:
                data["cameraStatus"] = 0

            if camera_status == "" or camera_status == None or data["cameraStatus"] == int(camera_status):

                device_id = data['cameraId']
                try:
                    position_id = associate_coll.find_one({"device_id": device_id})['position_id']
                    position_doc = position_coll.find_one({"position_id": position_id}, {"_id": 0})
                except:
                    position_doc = {}
                control_associate = asso_col.distinct("control_id", {"camera_id": device_id})
                position_info = database_to_dict(position_doc, positionkeys_database, positionkeys_web)
                data = dict(data, **position_info)
                data['serviceId'] = ''
                data['serviceName'] = ''
                data['serviceState'] = ''
                data['serverIp'] = ''
                data['videotape'] = ''

                data['controlList'] = []
                for control_id in control_associate:
                    item = mission_col.find_one({'control_id': control_id})['control_name']
                    data['controlList'].append(item)

                camera_list.append(data)
        total = my_db.get_aggregate("odin_device_camera_edit", {})
        size = int(pageSize) if pageSize else total
        if size == 0:
            pages = 0
        elif total % size == 0:
            pages = total // size
        else:
            pages = total // size + 1

        PageQueryRepVo = {'list': camera_list,
                          'pages': pages,
                          'size': size,
                          'total': total}
    except Exception as e:
        mainlogger.exception(e)
        PageQueryRepVo = {}
    response_data = {}
    response_data['cameraEditPageQueryRepVo'] = PageQueryRepVo
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 40
    return jsonify(response_data)


@bp.route('/vidicon/getCameraInfo', methods=['POST'])
@login_required
def getCameraInfo():
    '''
    接口注释:编辑摄像头时,从前端收到cameraid信息,
            返回摄像头的具体信息
    '''
    my_db = ToMongo('wavedevice')
    response_data = {}
    params = request.get_json()
    devices_list = params.get("cameraIdList", None)

    device_coll = my_db.get_col('odin_device_camera_edit')
    associate_coll = my_db.get_col('odin_device_device_position_associate')
    position_coll = my_db.get_col('odin_device_position')

    device_id = devices_list[0]
    data = device_coll.find_one({"camera_id": device_id}, {'_id': 0})
    item = {}
    format_pattern = '%Y-%m-%d %H:%M:%S'
    item['cameraAccount'] = data['camera_account']
    item['cameraCreateTime'] = data['create_time'].strftime(format_pattern) if data['create_time'] else None
    item['cameraId'] = data['camera_id']
    item['cameraIp'] = data['camera_ip']
    item['cameraIpLabel'] = data['camera_ip_label']
    item['cameraMac'] = data['camera_mac']
    item['cameraName'] = data['camera_name']
    item['cameraNum'] = data['camera_num']
    item['cameraPassword'] = data['camera_password']
    item['cameraRemarks'] = data['camera_remarks']
    item['cameraSource'] = data['camera_source']
    item['cameraStatus'] = data['camera_status']
    item['cameraType'] = data['camera_type']
    item['cameraUpdateTime'] = data['update_time'].strftime(format_pattern) if data['update_time'] else None
    item['extendInfo'] = data['extend_info']
    item['mainUrl'] = data['main_url']
    item['organizationId'] = data['organization_id']
    item['rtspPort'] = data['rtsp_port']
    item['productKey'] = data['product_key']

    item['reportFrequency'] = None
    item['port'] = None
    item['encodingFormat'] = data['encoding_format']
    item['codeStream'] = data['code_stream']
    item['controlList'] = None
    item['setType'] = data['set_type']
    item['liveUrl'] = data.get('live_url', None)
    item['areaId'] = data.get('area_id', None)
    item['nvrChannel'] = data.get('nvr_channel', None)

    if item['extendInfo']:
        item['cameraProductType'] = int(item['extendInfo'].split("=")[-1])
    else:
        item['cameraProductType'] = None
    try:
        position_id = associate_coll.find_one({"device_id": device_id})['position_id']
        position_doc = position_coll.find_one({"position_id": position_id}, {"_id": 0})
    except:
        position_doc = {}
    position_info = database_to_dict(position_doc, positionkeys_database, positionkeys_web)
    item = dict(item, **position_info)
    item['serviceId'] = None
    item['serviceName'] = None
    item['serviceState'] = None
    item['sreverIp'] = None
    item['videotape'] = None

    result = []
    result.append(item)
    response_data['cameraInfoList'] = result
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 11

    return jsonify(response_data)


@bp.route('/vidicon/updateCameraEdit', methods=['POST'])
@login_required
def updateCameraEdit():
    '''
    接口注释:编辑完摄像头之后,从前端收到cameraid具体信息,
            将具体信息更新到数据库；
    '''
    my_db = ToMongo('wavedevice')
    generate_log(request, db=my_db)
    response_data = {}
    params = request.get_json()
    camera_Name = params.get("cameraName", None)
    cameraAccount = params.get("cameraAccount", None)
    cameraId = params.get("cameraId", None)
    cameraIp = params.get("cameraIp", None)
    rtsp_port = params.get("rtspPort", None)
    if rtsp_port:
        rtsp_port = int(rtsp_port)
    cameraPassword = params.get("cameraPassword", None)
    cameraRemarks = params.get("cameraRemarks", None)
    cameraType = params.get("cameraType", None)  # 摄像头类型 0 固定摄像头  1  可移动摄像头
    positionId = params.get("positionId", None)
    serviceId = params.get("serviceId", None)
    nvrChannel = params.get("nvrChannel", None)
    encoding_format = params.get("encodingFormat", None)  # 编码格式 0 h264 1 h265
    if encoding_format:
        encoding_format = int(encoding_format)

    cameraProductType = params.get('cameraProductType', None)
    if cameraProductType:
        extendInfo = "cameraProductType=" + cameraProductType
    else:
        extendInfo = None

    code_stream = params.get("codeStream", None)  # 码流 0 主码流 1 子码流 2 第三码流
    if code_stream:
        code_stream = int(code_stream)

    main_url = params.get("mainUrl", None)  # 拉流地址
    areaId = params.get("areaId", None)  # 关联区域

    camera_num = params.get("cameraNum", None)  # 摄像头序列号

    setType = params.get("setType", None)  # 配置方式
    if setType == "1":
        cameraIp = main_url.split("@")[1].split(":")[0]
        temp = main_url.split("@")[0].split("//")[1]
        cameraAccount = temp.split(':')[0]
        cameraPassword = temp.split(':')[1]
    if setType:
        setType = int(setType)
    device_item = my_db.get_col('odin_device_camera_edit').find_one({'camera_id': cameraId})
    origin_name = device_item['camera_name']
    if camera_Name != origin_name:
        camera_name_list = my_db.get_keyvalues("odin_device_camera_edit", "camera_name")
        if camera_Name in camera_name_list:
            response_data = {}
            response_data['errorCode'] = "CAMERA_NAME_EXIST"
            response_data['errorCodeDesc'] = "摄像机名称已存在"
            response_data['exceptionCodeDesc'] = ""
            response_data['requestId'] = uuid.uuid4().hex
            response_data['requestStatus'] = "FAIL"
            response_data['timeUsed'] = 107
            return response_data

    origin_ip = device_item['camera_ip']
    origin_url = device_item['main_url']
    if cameraIp != origin_ip:
        camera_ip_list = my_db.get_keyvalues("odin_device_camera_edit", "camera_ip")
        if cameraIp in camera_ip_list:
            response_data = {}
            response_data['errorCode'] = "CAMERA_IP_EXIST"
            response_data['errorCodeDesc'] = "该摄像机的IP已存在!"
            response_data['exceptionCodeDesc'] = ""
            response_data['requestId'] = uuid.uuid4().hex
            response_data['requestStatus'] = "FAIL"
            response_data['timeUsed'] = 143
            return response_data

    res = {'camera_name': camera_Name, 'camera_account': cameraAccount, 'camera_id': cameraId,
           'extend_info': extendInfo, 'set_type': setType,
           'camera_ip': cameraIp, 'rtsp_port': rtsp_port, 'camera_password': cameraPassword,
           'camera_remarks': cameraRemarks, 'camera_type': cameraType,
           'service_id': serviceId, 'encoding_format': encoding_format, 'code_stream': code_stream,
           'main_url': main_url, 'camera_num': camera_num, 'area_id': areaId, 'nvr_channel': nvrChannel}

    my_db.update('odin_device_camera_edit',
                 {'camera_id': cameraId},
                 {'$set': res})

    my_db.update('odin_device_device_position_associate',
                 {'device_id': cameraId},
                 {'$set': {"position_id": positionId}})

    sync_camera_thread = Thread(target=sync_camera,args=[my_db,res])
    sync_camera_thread.start()

    if origin_url != res['main_url']:
        from alg.AlgorithServer_v2 import SenderThread
        sender = SenderThread(current_app.app_context())
        sender.send_3007_message()

    response_data = {'requestId': uuid.uuid4().hex, 'requestStatus': "SUCCESS", 'timeUsed': 56}

    return jsonify(response_data)


@bp.route('/vidicon/getpositionlist', methods=['POST'])
@login_required
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
        item['personCardIdList'] = data['person_card_id_list']
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

    return jsonify(response_data)


@bp.route('/vidicon/saveCameraEdit', methods=['POST'])
@login_required
def saveCameraEdit():
    '''
    接口注释：新增完摄像头，
             从前端收到新增摄像头的具体信息，
             后端将信息新增至数据库；
    '''
    my_db = ToMongo('wavedevice')
    generate_log(request, db=my_db)
    a = {}
    b = {}
    params = request.get_json()
    a['camera_name'] = params.get('cameraName')
    set_type = a['set_type'] = int(params.get('setType'))
    a['camera_ip'] = params.get('cameraIp')
    a['rtsp_port'] = int(params.get('rtspPort'))
    a['camera_account'] = params.get('cameraAccount')
    a['camera_password'] = params.get('cameraPassword')
    encodingFormat = params.get('encodingFormat', None)
    a['encoding_format'] = int(encodingFormat) if encodingFormat else None
    codeStream = params.get('codeStream', None)
    a['code_stream'] = int(codeStream) if codeStream else None
    a['camera_num'] = params.get('cameraNum')
    a['main_url'] = params.get('mainUrl')
    a['camera_type'] = params.get('cameraType', None)
    a['camera_id'] = str(uuid.uuid4().int)[:21]
    a['camera_status'] = '1'  # 初始化在线状态
    a['camera_mac'] = None
    a['camera_remarks'] = None
    a['create_time'] = a['update_time'] = a['offline_time'] = datetime.now()
    a['camera_ip_label'] = None
    a['videotape'] = None
    a['product_key'] = None
    a['report_frequency'] = None
    a['camera_source'] = 1  # 手动添加
    a['service_id'] = None
    a['area_id'] = params.get('areaId')  # 摄像头关联区域
    a['nvr_channel'] = params.get('nvrChannel')

    if set_type == 1:
        main_url = a["main_url"]
        symbol = "@"
        if symbol not in main_url:
            account, password = None, None
            temp = main_url.split("//")[1].split("/")[0].split(":")
            ip = temp[0]
            port = temp[1]
        else:
            temp = a["main_url"].split("@")
            account, password = temp[0].split("//")[1].split(":")
            ip, port = temp[1].split("/")[0].split(":")

        a['camera_ip'] = ip
        a['rtsp_port'] = int(port) if port else None
        a['camera_account'] = account
        a['camera_password'] = password

    cameraProductType = params.get('cameraProductType', None)
    a['extend_info'] = "cameraProductType=" + cameraProductType if cameraProductType else None

    b['position_id'] = params.get('positionId')
    if not b['position_id']:
        b['position_id'] = uuid.uuid4().hex

    position_coll = my_db.get_col('odin_device_position')
    position_item = position_coll.find_one({'position_id': b['position_id']})
    if position_item:
        a['organization_id'] = position_item['organization_id']
    else:
        a['organization_id'] = "001611544223344645607"

    b['device_id'] = a['camera_id']
    b['create_time'] = datetime.now()
    b['device_type'] = 1

    camera_coll = my_db.get_col('odin_device_camera_edit')
    camera_name_list = camera_coll.distinct("camera_name")
    error_response = set_fail_result()
    if a['camera_name'] in camera_name_list:
        error_response['errorCode'] = "CAMERA_NAME_EXIST"
        error_response['errorCodeDesc'] = "摄像机名称已存在"
        return error_response

    url_list = camera_coll.distinct("main_url")
    if a['main_url'] in url_list:
        error_response['errorCode'] = "CAMERA_URL_EXIST"
        error_response['errorCodeDesc'] = "摄像机的流地址已存在!"
        return error_response

    check_thread = Thread(target=cs.check_device, args=[a['camera_ip']])
    check_thread.start()

    my_db.insert('odin_device_camera_edit', a)
    my_db.insert('odin_device_device_position_associate', b)

    sync_camera_thread = Thread(target=sync_camera,args=[my_db,a])
    sync_camera_thread.start()

    from alg.AlgorithServer_v2 import SenderThread
    sender = SenderThread(current_app.app_context())
    sender.send_3007_message()

    response_data = set_success_result()
    response_data['cameraId'] = a['camera_id']
    return jsonify(response_data)


@bp.route('/vidicon/deleteCameraEdit', methods=['POST'])
@login_required
def deleteCameraEdit():
    '''
    接口描述:删除摄像头时,从前端收到camera_id,返回任务状态；
    '''
    params = request.get_json()
    camera_id = params.get("cameraId")
    my_db = ToMongo("wavedevice")
    generate_log(request, db=my_db)
    mission_device_col = my_db.get_col("control_device_algorithm_associate")
    items = mission_device_col.find({"camera_id": camera_id})
    if items.count() != 0:
        error_response = set_fail_result()
        error_response['errorCode'] = "CAMERA_NOT_DEL"
        error_response['errorCodeDesc'] = "摄像机已绑定布控任务，不能删除"
        return jsonify(error_response)

    crowd_asso_col = my_db.get_col("crowd_entrance_camera_associate")
    assoItem = crowd_asso_col.find_one({"camera_id": camera_id})
    if assoItem:
        error_response = set_fail_result()
        error_response['errorCode'] = "CAMERA_NOT_DEL"
        error_response['errorCodeDesc'] = "摄像机已绑定人流项目，不能删除"
        return jsonify(error_response)

    res_cam = my_db.delete("odin_device_camera_edit", {"camera_id": camera_id})
    res_aso = my_db.delete("odin_device_device_position_associate", {"device_id": camera_id})
    res_pos = my_db.delete("odin_device_position", {"camera_id": camera_id})
    res_pos = my_db.delete("odin_device_roi_area_record", {"camera_id": camera_id},is_one=False)

    delete_thread = Thread(target=sync_deleteDev,args=[camera_id,'5'])
    delete_thread.start()

    from alg.AlgorithServer_v2 import SenderThread
    sender = SenderThread(current_app.app_context())
    sender.send_3007_message()

    response_data = {}
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 556

    return jsonify(response_data)


@bp.route('/vidicon/videoOnOrOff', methods=['POST'])
def videoOnOrOff():
    params = request.get_json()
    deviceId = params.get("deviceId")
    isOpen = params.get("isOpen")

    query = {'device_id': deviceId}
    my_db = ToMongo('wavedevice')
    user_item = get_user_item(request, db=my_db)
    user_id = user_item.get("user_id")

    if isOpen == 1:
        my_db.delete('centimani_storage_live_choose_record', query)
    elif isOpen == 0:
        query['user_id'] = user_id
        my_db.insert('centimani_storage_live_choose_record', query)
    response_data = set_success_result()
    return jsonify(response_data)


@bp.route('/vidicon/deviceLive', methods=['POST'])
@login_required
def deviceLive():
    params = request.get_json()
    deviceLiveList = params.get("deviceLiveList")
    device_id = deviceLiveList[0]['deviceId']
    effective_time = deviceLiveList[0]['effectiveTime']
    my_db = ToMongo('wavedevice')
    camera_coll = my_db.get_col('odin_device_camera_edit').find_one({'camera_id': device_id})
    url = camera_coll['main_url']
    if not url:
        ip = camera_coll['camera_ip']
        camera_account = camera_coll['camera_account']
        camera_password = camera_coll['camera_password']
        url = 'rtsp://' + camera_account + ':' + camera_password + '@' + ip

    response_data = {}
    response_data['deviceLiveList'] = []
    item = {}
    item['deviceId'] = device_id
    item['effectiveTime'] = effective_time
    item['pullStreamUrl'] = url
    item['url'] = url
    response_data['deviceLiveList'].append(item)
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 556
    return jsonify(response_data)


@bp.route('/vidicon/getLiveRecordList', methods=['POST'])
@login_required
def getLiveRecordList():
    my_db = ToMongo('wavedevice')
    # generate_log(request,db=my_db)
    user_item = get_user_item(request, db=my_db)
    user_id = user_item.get("user_id")
    liverecord_col = my_db.get_col('centimani_storage_live_choose_record')
    query = {'user_id': user_id}
    deviceid_list = liverecord_col.distinct('device_id', query)
    response_data = set_success_result()
    response_data['liveRecordList'] = deviceid_list
    return jsonify(response_data)


@bp.route('/control/cameraCountStatistics', methods=['GET', 'POST'])
@login_required
def cameraCountStatistics():
    '''
    接口说明：摄像机设备数量统计
    '''
    my_db = ToMongo('wavedevice')
    camera_coll = my_db.get_col('odin_device_camera_edit')
    cameraTotalCount = camera_coll.find().count()
    # camera_status_dict = cs.device_status_list
    # result = [k for k, v in camera_status_dict.items() if v == "0"]
    # cameraNormalCount = len(result)
    cameraNormalCount = camera_coll.find({"camera_status": "0"}).count()
    if cameraTotalCount == 0:
        cameraNormalCount = 0

    response_data = {}
    response_data['cameraTotalCount'] = cameraTotalCount
    response_data['cameraNormalCount'] = cameraNormalCount
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 56
    return jsonify(response_data)


@bp.route('/vidicon/testRtspStream', methods=['GET', 'POST'])
@login_required
def testRtspStream():
    '''
    接口说明：验证视频流
    状态：未完成
    '''
    params = request.get_json()
    rtspUrl = params.get("rtspUrl", None)

    cap = cv2.VideoCapture(rtspUrl)
    if cap.isOpened():
        response_data = {}
        response_data['requestId'] = uuid.uuid4().hex
        response_data['requestStatus'] = "SUCCESS"
        response_data['timeUsed'] = 56
        cap.release()
    else:
        response_data = {}
        response_data['errorCode'] = "FAIL"
        response_data['errorCodeDesc'] = "验证不通过"
        response_data['exceptionCodeDesc'] = None
        response_data['requestId'] = uuid.uuid4().hex
        response_data['requestStatus'] = "FAIL"
        response_data['timeUsed'] = 56
    return jsonify(response_data)


@bp.route('/vidicon/getNvrUrl', methods=['GET', 'POST'])
@login_required
def getNvrUrl():
    '''
    接口说明：查询nvr系统地址
    '''
    my_db = ToMongo('wavedevice')
    item = my_db.get_col('system_setting').find_one({"file_type": 0})
    nvrUrl = item.get('nvr_url')
    response = set_success_result()
    response['nvrUrl'] = nvrUrl
    return jsonify(response)


@bp.route('/vidicon/saveNvrUrl', methods=['GET', 'POST'])
@login_required
def saveNvrUrl():
    '''
    接口说明：保存nvr系统地址
    '''
    params = request.get_json()
    nvrUrl = params.get("nvrUrl", None)

    my_db = ToMongo('wavedevice')
    my_db.update('system_setting', {'file_type': 0}, {'$set': {'nvr_url': nvrUrl}})

    response = set_success_result()
    return jsonify(response)


# @bp.route('/vidicon/testwebhook', methods=['GET','POST'])
# def testwebhook():
#     '''
#     接口说明：验证告警转发
#     '''
#     params = request.get_json()

#     print("-------webhook test!!!!")
#     print(params)
#     response_data = {"code":1234}
#     return jsonify(response_data)

cs = CheckInService()  # 启动查询摄像头状态进程
if __name__ == '__main__':
    app = Flask(__name__, static_url_path='')
    app.register_blueprint(bp)
    cs = CheckInService()  # 启动查询摄像头状态进程
    app.run('127.0.0.1', 5004, debug=True)

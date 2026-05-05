from flask import Blueprint
from utils.db import ToMongo
from .db_router import EventImageDBAPI, transfer_img_url
import uuid
from utils.Utils import generate_log
from utils.jwt_verify import *
from alg.Agreementunpack import delete_pic
from threading import Thread

bp_alert = Blueprint('emergency_api', __name__, url_prefix='/net-web/control')


@bp_alert.route('/getEmergencyItems', methods=['POST'])
@login_required
def getEmergencyItems():
    '''
    接口注释:获取告警纪录列表
    '''
    response_data = {}
    my_db = ToMongo("wavedevice")
    params = request.get_json()
    url_referer = request.headers['Referer']

    generate_log(request, db=my_db)
    page = int(params.get("page", None))
    size = int(params.get("pageSize", None))
    sorttype = params.get("sortType", None)  # DESC 降序 ；  ASC 升序
    sortBy = params.get("sortBy", None)
    falseAlarmStatus = params.get("falseAlarmStatus", None)  # 误报标识
    controlName = params.get("controlName", None)  # 布控任务名称

    begin_time = params.get("beginTime", None)
    end_time = params.get("endTime", None)

    model_name = params.get("modelName", None)
    model_path = params.get("modelPath", None)

    control_id = params.get("controlId", None)
    search_choose = params.get("searchChoose", None)  # 告警位置或摄像机名称

    ipAddress = params.get("ipAddress", None)

    quary = {}
    if control_id:
        quary['mission_id'] = control_id
    if begin_time and end_time:
        begin_time = int(str(begin_time)[0:10])
        end_time = int(str(end_time)[0:10])
        begin_time = datetime.fromtimestamp(begin_time)
        begin_time = begin_time.strftime("%Y-%m-%d %H:%M:%S")
        end_time = datetime.fromtimestamp(end_time)
        end_time = end_time.strftime("%Y-%m-%d %H:%M:%S")
        quary['emergency_time'] = {"$gte": begin_time, "$lte": end_time}
    if model_path:
        quary['model_path'] = model_path
    if falseAlarmStatus and falseAlarmStatus != "":
        quary['is_wrong'] = int(falseAlarmStatus)
    if search_choose and search_choose != "":
        quary['$or'] = [{'emergency_position': {'$regex': search_choose}}, {'device_name': {'$regex': search_choose}}]
    if controlName:
        quary['control_name'] = controlName

    num = (page - 1) * size
    emergency_result = my_db.get_col("odin_business_emergency_record").aggregate(
        [{"$match": quary},
         {"$sort": {"emergency_time": -1}},
         {"$skip": num},
         {"$limit": size},
         {'$lookup': {"from": "odin_business_emergency_record_detail_info",
                      "localField": "emergency_record_id",
                      "foreignField": "emergency_record_id",
                      "as": "detail_docs"}},
         {"$project": {'_id': 0}},
         ])

    totalcount = my_db.get_aggregate("odin_business_emergency_record", quary)

    emergencyRecordVoList = []
    for emergency in emergency_result:
        item = {}
        item['alarmStatus'] = emergency['alarm_status']
        item['controlName'] = emergency['control_name']
        item['deviceName'] = emergency['device_name']
        item['emergencyLevel'] = emergency['emergency_level']
        item['emergencyMediaInfo'] = emergency['emergency_media_info']
        item['emergencyMusicCloseMethod'] = emergency['emergency_music_close_method']
        item['emergencyMusicCloseStatus'] = emergency['emergency_music_close_status']
        item['emergencyPosition'] = emergency['emergency_position']
        item['emergencyRecordId'] = emergency['emergency_record_id']
        item['emergencyTime'] = emergency['emergency_time']
        item['missionType'] = ""
        item['modelName'] = emergency['model_name']
        item['modelPath'] = emergency['model_path']
        item['emergencyRecordDetailInfos'] = []

        iter = {}
        detail_docs = emergency['detail_docs']
        if detail_docs:
            a = detail_docs[0]
            img_url = transfer_img_url(url_referer, a['emergency_image'])
            iter['algorithmConstantNum'] = a['algorithm_constant_num']
            iter['basePersonnelBirth'] = a['base_personnel_birth']
            iter['basePersonnelId'] = a['base_personnel_id']
            iter['basePersonnelImage'] = a['base_personnel_image']
            iter['basePersonnelName'] = a['base_personnel_name']
            iter['basePersonnelNation'] = a['base_personnel_nation']
            iter['basePersonnelSex'] = a['base_personnel_sex']
            iter['discernTime'] = a['discern_time']
            iter['emergencyImage'] = img_url
            iter['emergencyImageExtraInfo'] = a['emergency_image_extra_info']

            iter['emergencyRecordDetailInfoId'] = a['emergency_record_detail_info_id']
            iter['emergencyRecordId'] = a['emergency_record_id']
            iter['groupMatterName'] = a['group_matter_name']
            iter['groupNum'] = a['group_num']
            iter['num'] = a['num']
            iter['stepNum'] = a['step_num']
            iter['stepTime'] = a['step_time']
            iter['videoPreviewImage'] = img_url

            item["emergencyRecordDetailInfos"].append(iter)
        emergencyRecordVoList.append(item)

    response_data["emergencyRecordVoList"] = emergencyRecordVoList
    response_data["page"] = 0
    response_data["totalCount"] = totalcount
    response_data["requestId"] = uuid.uuid4().hex
    response_data["timeUsed"] = 90
    response_data["requestStatus"] = 'SUCCESS'
    return jsonify(response_data)


@bp_alert.route('/getEmergencyDetailInfo', methods=['POST'])
@login_required
def getEmergencyDetailInfo():
    '''
    接口注释:获取告警纪录详情
    '''
    response_data = {}
    params = request.get_json()
    emergencyRecordId = params.get("emergencyRecordId", None)
    ipAddress = params.get("ipAddress", None)
    url_head = request.headers['Referer']
    my_db = ToMongo("wavedevice")
    generate_log(request, db=my_db)
    emergency_info = my_db.get_col("odin_business_emergency_record").find_one(
        {"emergency_record_id": emergencyRecordId}, {"_id": 0})
    detail_info = my_db.get_col("odin_business_emergency_record_detail_info").find_one(
        {"emergency_record_id": emergencyRecordId}, {"_id": 0})
    if emergency_info:
        control_info = my_db.get_col("control_manage_mission").find_one(
            {"control_id": emergency_info['mission_id']}, {"_id": 0})
    else:
        control_info = None

    response_data["alarmStatus"] = emergency_info['alarm_status']
    response_data["controlName"] = control_info['control_name'] if control_info else None
    response_data["emergencyDeviceName"] = emergency_info['device_name']
    response_data["emergencyExecDesc"] = emergency_info['emergency_exec_desc']
    response_data["emergencyExecFlag"] = emergency_info['emergency_exec_flag']
    response_data["emergencyExecName"] = emergency_info['emergency_exec_name']
    response_data["emergencyExecResult"] = emergency_info['emergency_exec_result']
    response_data["emergencyLevel"] = emergency_info['emergency_level']
    response_data["emergencyMediaInfo"] = emergency_info['emergency_media_info']
    response_data["emergencyMusicCloseStatus"] = emergency_info['emergency_music_close_status']
    response_data["emergencyPosition"] = emergency_info['emergency_position']
    response_data["emergencyTime"] = emergency_info['emergency_time']
    response_data["emergencyrecordId"] = emergency_info['emergency_record_id']
    response_data["falseAlarmStatus"] = str(emergency_info['is_wrong'])
    response_data["modelName"] = emergency_info['model_name']
    response_data["modelPath"] = emergency_info['model_path']
    response_data["requestId"] = uuid.uuid4().hex
    response_data["requestStatus"] = "SUCCESS"
    response_data["timeUsed"] = 13

    response_data["emergencyRecordDetailInfos"] = []
    item = {}
    item['algorithmConstantNum'] = detail_info['algorithm_constant_num']
    item['basePersonnelBirth'] = detail_info['base_personnel_birth']
    item['basePersonnelId'] = detail_info['base_personnel_id']
    item['basePersonnelImage'] = detail_info['base_personnel_image']
    item['basePersonnelName'] = detail_info['base_personnel_name']
    item['basePersonnelNation'] = detail_info['base_personnel_nation']
    item['basePersonnelSex'] = detail_info['base_personnel_sex']
    item['discernTime'] = detail_info['discern_time']
    img_url = transfer_img_url(url_head, detail_info['emergency_image'])
    item['emergencyImage'] = img_url
    item['emergencyImageExtraInfo'] = detail_info['emergency_image_extra_info']
    item['emergencyRecordDetailInfoId'] = detail_info['emergency_record_detail_info_id']
    item['emergencyRecordId'] = detail_info['emergency_record_id']
    item['groupMatterName'] = detail_info['group_matter_name']
    item['groupNum'] = detail_info['group_num']
    item['num'] = detail_info['num']
    item['stepNum'] = detail_info['step_num']
    item['stepTime'] = detail_info['step_time']
    item['videoPreviewImage'] = img_url
    response_data["emergencyRecordDetailInfos"].append(item)

    return jsonify(response_data)


@bp_alert.route('/saveEmergencyExecute', methods=['POST'])
@login_required
def saveEmergencyExecute():
    '''
    接口注释:保存告警处理信息；
    '''
    my_db = ToMongo("wavedevice")
    params = request.get_json()
    is_wrong = params.get("isWrong", None)
    emergencyExecDesc = params.get("emergencyExecDesc", None)
    emergencyExecName = params.get("emergencyExecName", None)
    emergencyExecResult = params.get("emergencyExecResult", None)
    emergencyRecordId = params.get("emergencyRecordId", None)

    emergency_exec_flag = 0
    if emergencyExecDesc or emergencyExecName or emergencyExecResult:
        emergency_exec_flag = 1

    item = {"emergency_exec_desc": emergencyExecDesc, "emergency_exec_name": emergencyExecName,
            "emergency_exec_result": emergencyExecResult,"emergency_exec_flag":emergency_exec_flag}
    if is_wrong:
        item['is_wrong'] = is_wrong
    result = my_db.update("odin_business_emergency_record",
                          {"emergency_record_id": emergencyRecordId},
                          {'$set': item}
                          )

    response_data = {}
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 18
    return jsonify(response_data)


@bp_alert.route('/delEmergencyItemsByIds', methods=['POST'])
@login_required
def delEmergencyItemsByIds():
    '''
    接口注释:删除告警信息；
    '''
    my_db = ToMongo("wavedevice")
    params = request.get_json()
    ids = params.get("ids", None)
    delete_type = params.get("type", None)  # all/select
    accessToken = params.get("accessToken", None)
    begin_time = params.get("beginTime", None)
    controlName = params.get("controlName", None)
    end_time = params.get("endTime", None)
    falseAlarmStatus = params.get("falseAlarmStatus", None)
    modelName = params.get("modelName", None)
    model_path = params.get("modelPath", None)
    page = params.get("page", None)
    pageSize = params.get("pageSize", None)
    search_choose = params.get("searchChoose", None)
    sortBy = params.get("sortBy", None)
    sortType = params.get("sortType", None)
    emergency_col = my_db.get_col("odin_business_emergency_record")

    if ids:
        # 删除告警纪录时同时删除 表1：告警纪录 和 表2：告警纪录详情的相关内容
        emergency_items = emergency_col.find({"emergency_record_id": {"$in": ids}}, {"_id": 0})
        if emergency_col.count() != 0:
            emergency_list = list(emergency_items).copy()
            delete_pic_thread = Thread(target=delete_pic, args=[emergency_list, emergency_col])
            delete_pic_thread.start()
        my_db.delete("odin_business_emergency_record",
                     {"emergency_record_id": {"$in": ids}},
                     is_one=False)

        my_db.delete("odin_business_emergency_record_detail_info",
                     {"emergency_record_id": {"$in": ids}},
                     is_one=False)

    if delete_type == "all":

        quary = {}
        if begin_time and end_time:
            begin_time = int(str(begin_time)[0:10])
            end_time = int(str(end_time)[0:10])
            begin_time = datetime.fromtimestamp(begin_time)
            begin_time = begin_time.strftime("%Y-%m-%d %H:%M:%S")
            end_time = datetime.fromtimestamp(end_time)
            end_time = end_time.strftime("%Y-%m-%d %H:%M:%S")
            quary['emergency_time'] = {"$gte": begin_time, "$lte": end_time}
        if model_path:
            quary['model_path'] = model_path
        if falseAlarmStatus and falseAlarmStatus != "":
            quary['is_wrong'] = int(falseAlarmStatus)
        if search_choose and search_choose != "":
            quary['$or'] = [{'emergency_position': {'$regex': search_choose}},
                            {'device_name': {'$regex': search_choose}}]
        if controlName:
            control_item = my_db.get_col("odin_business_control_manage").find_one({'control_name': controlName})
            if control_item:
                quary['mission_id'] = control_item['control_id']

        emergency_items = emergency_col.find(quary, {"_id": 0})
        emergency_list = list(emergency_items).copy()

        my_db.delete("odin_business_emergency_record",
                     quary,
                     is_one=False)

        my_db.delete("odin_business_emergency_record_detail_info",
                     quary,
                     is_one=False)

        delete_pic_thread = Thread(target=delete_pic, args=[emergency_list, emergency_col])
        delete_pic_thread.start()

    response_data = {}
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 18
    return jsonify(response_data)


view_func = EventImageDBAPI.as_view(('{}_api').format('event_images'))
bp_alert.add_url_rule(('/{}/<string:{}>').format('event_images', 'image_id'), view_func=view_func,
                      methods=['GET', 'PUT', 'DELETE'])

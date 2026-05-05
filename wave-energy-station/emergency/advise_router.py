from flask import Blueprint
from utils.db import ToMongo
import uuid
from utils.Utils import set_success_result,get_user_item
from utils.jwt_verify import *
import utils.logger as logger
from alg.Alibabasms import SendSmsResqueset
import requests
import json
from msg_queue import smsdelivery_queue, webdelivery_queue

bp_advise = Blueprint('advise_api', __name__, url_prefix='/net-web')

mainlogger = logger.getLogger("main")


def decode_token(access_token, db: ToMongo):
    current_user = jwt.decode(access_token, JWT_KEY, options={'verify_exp': False})['user_account']
    organization_id = db.get_col('authority_user').find_one({'user_account': current_user})['organization_id']
    return organization_id


@bp_advise.route('/smsdeliver/getSmsDeliveryList', methods=['POST'])
@login_required
def getSmsDeliveryList():
    '''
    接口说明:短信投递任务查询
    '''
    params = request.get_json()
    accessToken = params.get("accessToken", None)
    page = params.get("page", None)
    pageSize = params.get("pageSize", None)
    smsDeliveryName = params.get("smsDeliveryName", None)
    sortBy = params.get("sortBy", None)
    sortType = params.get("sortType", None)

    my_db = ToMongo('wavedevice')
    sms_delivery_col = my_db.get_col('odin_advise_sms_delivery')

    organization_id = decode_token(accessToken, my_db)

    if sortType == 'DESC':
        KEY = -1
    elif sortType == 'ASC':
        KEY = 1
    else:
        KEY = -1  # 默认降序排列

    if not sortBy:
        sortBy = "sms_delivery_name"

    if page and pageSize:
        num = (page - 1) * pageSize
    else:
        num = 0

    query = {}
    if smsDeliveryName:
        query['sms_delivery_name'] = {"$regex": smsDeliveryName}

    sms_cursor = sms_delivery_col.find(query).sort(sortBy, KEY).skip(num).limit(pageSize)

    smsInfoVoList = []
    for sms_item in sms_cursor:
        item = {}
        item['deliveryContent'] = sms_item['delivery_content']
        item['deliveryPhones'] = sms_item['delivery_phones']
        item['smsDeliveryId'] = sms_item['sms_delivery_id']
        item['smsDeliveryName'] = sms_item['sms_delivery_name']
        item['triggerCondition'] = sms_item['trigger_condition']
        item['controlName'] = sms_item['control_name']
        item['createTime'] = int(sms_item['create_time'].timestamp()) * 1000
        item['modelPath'] = sms_item['model_path']
        item['organizationId'] = sms_item['organization_id']
        item['updateTime'] = int(sms_item['update_time'].timestamp()) * 1000
        item['deviceName'] = sms_item['device_name']
        item['isUse'] = sms_item['is_use']
        item['creater'] = sms_item['creater']
        smsInfoVoList.append(item)

    response_data = {}
    response_data['page'] = page
    response_data['pageSize'] = pageSize
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['smsInfoRecordVoList'] = smsInfoVoList
    response_data['totalCount'] = sms_cursor.count()
    response_data['timeUsed'] = 7
    return jsonify(response_data)


@bp_advise.route('/smsdeliver/addSmsDelivery', methods=['POST'])
@login_required
def addSmsDelivery():
    '''
    接口说明:添加短信投递任务
    '''
    params = request.get_json()
    accessToken = params.get("accessToken", None)
    deliveryContent = params.get("deliveryContent", None)
    deliveryPhones = params.get("deliveryPhones", None)
    smsDeliveryName = params.get("smsDeliveryName", None)
    triggerCondition = params.get("triggerCondition", None)
    controlName = params.get("controlName", None)
    deviceName = params.get("deviceName", None)
    modelPath = params.get("modelPath", None)

    my_db = ToMongo('wavedevice')
    organization_id = decode_token(accessToken, my_db)

    user_item = get_user_item(request, my_db)
    user_name = user_item.get("user_real_name")

    create_time = update_time = datetime.now()
    sms_delivery_id = uuid.uuid4().hex
    item = {"sms_delivery_id": sms_delivery_id, "sms_delivery_name": smsDeliveryName,
            "delivery_content": deliveryContent,
            "delivery_phones": deliveryPhones, "trigger_condition": triggerCondition,
            "organization_id": organization_id,
            "control_name": controlName, "device_name": deviceName, "model_path": modelPath,
            "create_time": create_time, "update_time": update_time,'is_use':0,'creater':user_name}

    my_db.insert("odin_advise_sms_delivery", item)

    smstask_state = 1
    smsdelivery_queue.put(smstask_state)  # 短信投递重启信号存入消息队列 0不变  1重新拉取

    response_data = {}
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['smshookDeliveryId'] = sms_delivery_id
    response_data['timeUsed'] = 7
    return jsonify(response_data)

@bp_advise.route('/advise/setIsUserSms', methods=['POST'])
@login_required
def setIsUserSms():
    '''
    接口说明:短信投递任务开关
    '''
    params = request.get_json()
    smsDeliveryId = params.get("smsDeliveryId", None)
    isUse = params.get("isUse", None)
    
    my_db = ToMongo('wavedevice')
    query = {'sms_delivery_id':smsDeliveryId}
    my_db.update('odin_advise_sms_delivery',query,{'$set':{'is_use':isUse}})

    response_data = {}
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 7
    return jsonify(response_data)

@bp_advise.route('/smsdeliver/getSmsDeliveryDetailInfo', methods=['POST'])
@login_required
def getSmsDeliveryDetailInfo():
    '''
    接口说明:查询短信投递任务详情
    '''
    params = request.get_json()
    accessToken = params.get("accessToken", None)
    smsDeliveryId = params.get("smsDeliveryId", None)

    my_db = ToMongo('wavedevice')
    if smsDeliveryId:
        sms_item = my_db.get_col("odin_advise_sms_delivery").find_one({"sms_delivery_id": smsDeliveryId})

    if smsDeliveryId:
        response_data = {}
        response_data['requestId'] = uuid.uuid4().hex
        response_data['requestStatus'] = "SUCCESS"
        response_data['smshookDeliveryId'] = smsDeliveryId
        response_data['deliveryContent'] = sms_item['delivery_content']
        response_data['deliveryPhones'] = sms_item['delivery_phones']
        response_data['triggerCondition'] = sms_item['trigger_condition']
        response_data['smsDeliveryName'] = sms_item['sms_delivery_name']
        response_data['controlName'] = sms_item['control_name']
        response_data['deviceName'] = sms_item['device_name']
        response_data['modelPath'] = sms_item['model_path']
        response_data['timeUsed'] = 7
        return jsonify(response_data)
    else:
        response_data = {}
        response_data['requestId'] = uuid.uuid4().hex
        response_data['requestStatus'] = "FAIL"
        response_data['errorCode'] = "BAD_ARGUMENTS"
        response_data['errorCodeDesc'] = "短信投递任务标识不能为空"
        response_data['exceptionCodeDesc'] = ""
        response_data['timeUsed'] = 7
        return jsonify(response_data)


@bp_advise.route('/smsdeliver/getSmsDeliveryRecordList', methods=['POST'])
@login_required
def getSmsDeliveryRecordList():
    '''
    接口说明:查询短信投递任务转发记录
    '''
    params = request.get_json()
    accessToken = params.get("accessToken", None)
    smsDeliveryId = params.get("smsDeliveryId", None)
    page = params.get("page", None)
    pageSize = params.get("pageSize", None)
    sortBy = params.get("sortBy", None)
    sortType = params.get("sortType", None)
    deliveryStatus = params.get("deliveryStatus", None)

    if sortType == 'DESC':
        KEY = -1
    elif sortType == 'ASC':
        KEY = 1
    else:
        KEY = -1  # 默认降序排列

    query = {"delivery_id": smsDeliveryId}
    if deliveryStatus:
        query['delivery_status'] = deliveryStatus

    num = (page - 1) * pageSize
    my_db = ToMongo('wavedevice')
    sms_records_col = my_db.get_col("odin_advise_sms_delivery_record").find(query)
    sms_records = sms_records_col.sort("delivery_time", KEY).skip(num).limit(pageSize)

    smsInfoRecordVoList = []
    for sms_record_item in sms_records:
        item = {}
        item['controlName'] = sms_record_item['control_name']
        item['deliveryId'] = sms_record_item['delivery_id']
        item['deliveryPhones'] = sms_record_item['delivery_phones']
        item['deliveryRecordId'] = sms_record_item['delivery_record_id']
        item['deliveryStatus'] = sms_record_item['delivery_status']
        item['deliveryTime'] = sms_record_item['delivery_time']
        item['deviceName'] = sms_record_item['device_name']
        item['emergencyPosition'] = sms_record_item['emergency_position']
        item['emergencyRecordId'] = sms_record_item['emergency_record_id']
        item['emergencyTime'] = sms_record_item['emergency_time']
        item['modelName'] = sms_record_item['model_name']
        item['modelPath'] = sms_record_item['model_path']
        smsInfoRecordVoList.append(item)

    response_data = {}
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['page'] = page
    response_data['pageSize'] = pageSize
    response_data['smsInfoRecordVoList'] = smsInfoRecordVoList
    response_data['totalCount'] = sms_records_col.count()
    response_data['timeUsed'] = 7
    return jsonify(response_data)


@bp_advise.route('/smsdeliver/deleteSmsDelivery', methods=['POST'])
@login_required
def deleteSmsDelivery():
    '''
    接口说明:删除短信投递任务
    '''
    params = request.get_json()
    accessToken = params.get("accessToken", None)
    smsDeliveryId = params.get("smsDeliveryId", None)

    my_db = ToMongo('wavedevice')
    my_db.delete("odin_advise_sms_delivery", {"sms_delivery_id": smsDeliveryId})
    my_db.delete("odin_advise_sms_delivery_record", {"delivery_id": smsDeliveryId})
    smstask_state = 1
    smsdelivery_queue.put(smstask_state)  # 短信投递重启信号存入消息队列 0不变  1重新拉取
    response_data = {}
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 7
    return jsonify(response_data)


@bp_advise.route('/smsdeliver/updateSmsDelivery', methods=['POST'])
@login_required
def updateSmsDelivery():
    '''
    接口说明:编辑短信投递任务
    '''
    params = request.get_json()
    accessToken = params.get("accessToken", None)
    smsDeliveryId = params.get("smsDeliveryId", None)
    deliveryContent = params.get("deliveryContent", None)
    deliveryPhones = params.get("deliveryPhones", None)
    smsDeliveryName = params.get("smsDeliveryName", None)
    triggerCondition = params.get("triggerCondition", None)

    controlName = params.get("controlName", None)
    deviceName = params.get("deviceName", None)
    modelPath = params.get("modelPath", None)

    item = {"sms_delivery_name": smsDeliveryName, "delivery_content": deliveryContent,
            "delivery_phones": deliveryPhones, "trigger_condition": triggerCondition,
            "control_name": controlName, "device_name": deviceName, "model_path": modelPath,
            "update_time": datetime.now()}
    my_db = ToMongo('wavedevice')
    query = {"sms_delivery_id": smsDeliveryId}
    my_db.update("odin_advise_sms_delivery", query, {'$set': item})

    smstask_state = 1
    smsdelivery_queue.put(smstask_state)  # 短信投递重启信号存入消息队列 0不变  1重新拉取

    response_data = {}
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 7
    return jsonify(response_data)


@bp_advise.route('/smsdeliver/retrySmsDelivery', methods=['POST'])
@login_required
def retrySmsDelivery():
    '''
    接口说明:短信重投递
    '''
    params = request.get_json()
    smsDeliveryRecordId = params.get("smsDeliveryRecordId", None)

    my_db = ToMongo('wavedevice')
    delivery_record_col = my_db.get_col('odin_advise_sms_delivery_record')
    delivery_item = delivery_record_col.find_one({'delivery_record_id': smsDeliveryRecordId}, {'_id': 0})

    response_data = {}
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = ""
    response_data['timeUsed'] = 7

    if delivery_item:
        sms_sender = SendSmsResqueset()
        sms_sender.get_sms_config()
        result = sms_sender.resend_sms_delivery(delivery_item)
        if result == '1':
            my_db.update('odin_advise_sms_delivery_record', {'delivery_record_id': smsDeliveryRecordId},
                         {"$set": {'delivery_status': '1'}})
            response_data['requestStatus'] = "SUCCESS"
        else:
            response_data['requestStatus'] = "FAIL"
    else:
        response_data['requestStatus'] = "FAIL"

    return jsonify(response_data)


# webhook相关接口
@bp_advise.route('/advise/getWebhookDeliveryList', methods=['POST'])
@login_required
def getWebhookDeliveryList():
    '''
    接口说明:查询webhook投递任务列表
    '''
    params = request.get_json()
    accessToken = params.get("accessToken", None)
    page = params.get("page", None)
    pageSize = params.get("pageSize", None)
    sortBy = params.get("sortBy", None)
    sortType = params.get("sortType", None)
    requestType = params.get("requestType", None)
    frequencyType = params.get("frequencyType", None)
    webhookDeliveryName = params.get("webhookDeliveryName", None)

    if not sortBy:
        sortBy = "webhook_delivery_name"

    if sortType == 'DESC':
        KEY = -1
    elif sortType == 'ASC':
        KEY = 1
    else:
        KEY = -1  # 默认降序排列

    if page <= 0:
        page = 1

    query = {}
    if requestType:
        query['request_type'] = requestType
    if frequencyType:
        query['frequency_type'] = frequencyType
    if webhookDeliveryName:
        query['webhook_delivery_name'] = {"$regex": webhookDeliveryName}

    my_db = ToMongo('wavedevice')
    webhooks = my_db.get_col("odin_advise_webhook_delivery").find(query)
    num = (page - 1) * pageSize
    results = webhooks.sort(sortBy, KEY).skip(num).limit(pageSize)

    webhookInfoVoList = []
    for webhook in results:
        item = {}
        item['deliveryContent'] = webhook['delivery_content']
        item['frequencyCount'] = webhook['frequency_count']
        item['frequencyDateFormat'] = webhook['frequency_date_format']
        item['frequencyType'] = webhook['frequency_type']
        item['requestHeaders'] = webhook['request_headers']
        item['requestType'] = webhook['request_type']
        item['timeout'] = webhook['timeout']
        item['triggerCondition'] = webhook['trigger_condition']
        item['webhookDeliveryAddress'] = webhook['webhook_delivery_address']
        item['webhookDeliveryId'] = webhook['webhook_delivery_id']
        item['webhookDeliveryName'] = webhook['webhook_delivery_name']
        webhookInfoVoList.append(item)

    response_data = {}
    response_data['totalCount'] = webhooks.count()
    response_data['page'] = page
    response_data['pageSize'] = pageSize
    response_data['webhookInfoVoList'] = webhookInfoVoList
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 7
    return jsonify(response_data)


@bp_advise.route('/advise/addWebhookDelivery', methods=['POST'])
@login_required
def addWebhookDelivery():
    '''
    接口说明:添加webhook告警转发任务
    '''
    params = request.get_json()
    accessToken = params.get("accessToken", None)
    deliveryContent = params.get("deliveryContent", None)
    frequencyDateFormat = params.get("frequencyDateFormat", None)
    frequencyType = params.get("frequencyType", None)
    requestHeaders = params.get("requestHeaders", None)
    requestType = params.get("requestType", None)
    frequencyCount = params.get("frequencyCount", None)
    timeout = params.get("timeout", None)
    triggerCondition = params.get("triggerCondition", None)
    webhookDeliveryAddress = params.get("webhookDeliveryAddress", None)
    webhookDeliveryName = params.get("webhookDeliveryName", None)
    controlName = params.get("controlName", None)
    deviceName = params.get("deviceName", None)
    modelPath = params.get("modelPath", None)

    if not frequencyCount:
        frequencyCount = 0
    else:
        frequencyCount = int(frequencyCount)

    my_db = ToMongo('wavedevice')
    organization_id = decode_token(accessToken, my_db)

    create_time = update_time = datetime.now()
    webhook_delivery_id = uuid.uuid4().hex

    item = {"webhook_delivery_id": webhook_delivery_id, "webhook_delivery_name": webhookDeliveryName,
            "webhook_delivery_address": webhookDeliveryAddress,
            "request_type": requestType, "request_headers": requestHeaders, "frequency_type": frequencyType,
            "frequency_date_format": frequencyDateFormat,
            "frequency_count": frequencyCount, "timeout": timeout, "trigger_condition": triggerCondition,
            "delivery_content": deliveryContent,
            "create_time": create_time, "update_time": update_time,
            "control_name": controlName, "device_name": deviceName, "model_path": modelPath,
            "job_id": None, "organization_id": organization_id}

    my_db.insert("odin_advise_webhook_delivery", item)

    webhooktask_state = 1
    webdelivery_queue.put(webhooktask_state)  # 告警转发重启信号存入消息队列 0不变  1重新拉取

    response_data = {}
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['webhookDeliveryId'] = webhook_delivery_id
    response_data['timeUsed'] = 7
    return jsonify(response_data)


@bp_advise.route('/advise/deleteWebhookDelivery', methods=['POST'])
@login_required
def deleteWebhookDelivery():
    '''
    接口说明:删除webhook告警妆发任务
    '''
    params = request.get_json()
    accessToken = params.get("accessToken", None)
    webhookDeliveryId = params.get("webhookDeliveryId", None)

    my_db = ToMongo('wavedevice')
    my_db.delete("odin_advise_webhook_delivery", {"webhook_delivery_id": webhookDeliveryId})

    webhooktask_state = 1
    webdelivery_queue.put(webhooktask_state)  # 告警转发重启信号存入消息队列 0不变  1重新拉取

    response_data = {}
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 7
    return jsonify(response_data)


@bp_advise.route('/advise/updateWebhookDelivery', methods=['POST'])
@login_required
def updateWebhookDelivery():
    '''
    接口说明:编辑webhook告警转发任务
    '''
    params = request.get_json()
    accessToken = params.get("accessToken", None)
    webhookDeliveryId = params.get("webhookDeliveryId", None)
    webhookDeliveryName = params.get("webhookDeliveryName", None)
    webhookDeliveryAddress = params.get("webhookDeliveryAddress", None)

    deliveryContent = params.get("deliveryContent", None)
    triggerCondition = params.get("triggerCondition", None)

    frequencyCount = params.get("frequencyCount", None)
    frequencyDateFormat = params.get("frequencyDateFormat", None)
    frequencyType = params.get("frequencyType", None)

    requestHeaders = params.get("requestHeaders", None)
    requestType = params.get("requestType", None)

    controlName = params.get("controlName", None)
    deviceName = params.get("deviceName", None)
    modelPath = params.get("modelPath", None)

    item = {"webhook_delivery_name": webhookDeliveryName,
            "delivery_content": deliveryContent,
            "webhook_delivery_address": webhookDeliveryAddress,
            "trigger_condition": triggerCondition,
            "control_name": controlName,
            "device_name": deviceName,
            "model_path": modelPath,
            "request_headers": requestHeaders,
            "request_type": requestType,
            "frequency_count": frequencyCount,
            "frequency_date_format": frequencyDateFormat,
            "frequency_type": frequencyType,
            "update_time": datetime.now()}
    my_db = ToMongo('wavedevice')
    query = {"webhook_delivery_id": webhookDeliveryId}
    my_db.update("odin_advise_webhook_delivery", query, {'$set': item})

    webhooktask_state = 1
    webdelivery_queue.put(webhooktask_state)  # 告警转发重启信号存入消息队列 0不变  1重新拉取

    response_data = {}
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 7
    return jsonify(response_data)


@bp_advise.route('/advise/getWebhookDeliveryDetail', methods=['POST'])
@login_required
def getWebhookDeliveryDetail():
    '''
    接口说明:查询webhook告警转发详情
    '''
    params = request.get_json()
    accessToken = params.get("accessToken", None)
    webhookDeliveryId = params.get("webhookDeliveryId", None)

    my_db = ToMongo('wavedevice')
    if webhookDeliveryId:
        webhook_item = my_db.get_col("odin_advise_webhook_delivery").find_one(
            {"webhook_delivery_id": webhookDeliveryId})

    if webhookDeliveryId:
        response_data = {}
        response_data['deliveryContent'] = webhook_item['delivery_content']
        response_data['frequencyCount'] = webhook_item['frequency_count']
        response_data['frequencyDateFormat'] = webhook_item['frequency_date_format']
        response_data['frequencyType'] = webhook_item['frequency_type']
        response_data['requestHeaders'] = webhook_item['request_headers']
        response_data['requestType'] = webhook_item['request_type']
        response_data['timeout'] = webhook_item['timeout']
        response_data['triggerCondition'] = webhook_item['trigger_condition']
        response_data['webhookDeliveryAddress'] = webhook_item['webhook_delivery_address']
        response_data['webhookDeliveryId'] = webhookDeliveryId
        response_data['webhookDeliveryName'] = webhook_item['webhook_delivery_name']
        response_data['requestId'] = uuid.uuid4().hex
        response_data['requestStatus'] = "SUCCESS"
        response_data['timeUsed'] = 7
        return jsonify(response_data)


@bp_advise.route('/advise/getWebhookDeliveryRecordList', methods=['POST'])
@login_required
def getWebhookDeliveryRecordList():
    '''
    接口说明:webhook投递记录查询
    '''
    params = request.get_json()
    accessToken = params.get("accessToken", None)
    page = params.get("page", None)
    pageSize = params.get("pageSize", None)
    sortBy = params.get("sortBy", None)
    sortType = params.get("sortType", None)
    webhookDeliveryId = params.get("webhookDeliveryId", None)

    if sortType == 'DESC':
        KEY = -1
    elif sortType == 'ASC':
        KEY = 1
    else:
        KEY = -1  # 默认降序排列

    query = {"delivery_id": webhookDeliveryId}

    num = (page - 1) * pageSize
    my_db = ToMongo('wavedevice')
    webhook_records = my_db.get_col("odin_advise_webhook_delivery_record").find(query)
    webhook_items = webhook_records.sort("delivery_time", KEY).skip(num).limit(pageSize)

    webhookInfoRecordVoList = []
    for webhook_record_item in webhook_items:
        item = {}
        item['controlName'] = webhook_record_item['control_name']
        item['deliveryId'] = webhook_record_item['delivery_id']
        item['deliveryRecordId'] = webhook_record_item['delivery_record_id']
        item['deliveryStatus'] = webhook_record_item['delivery_status']
        item['deliveryTime'] = webhook_record_item['delivery_time']
        item['deviceName'] = webhook_record_item['device_name']
        item['emergencyImageUrls'] = webhook_record_item['emergency_image_urls']
        item['emergencyPosition'] = webhook_record_item['emergency_position']
        item['emergencyRecordId'] = webhook_record_item['emergency_record_id']
        item['emergencyTime'] = webhook_record_item['emergency_time']
        item['modelName'] = webhook_record_item['model_name']
        item['modelPath'] = webhook_record_item['model_path']
        webhookInfoRecordVoList.append(item)

    response_data = {}
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['page'] = page
    response_data['pageSize'] = pageSize
    response_data['webhookInfoRecordVoList'] = webhookInfoRecordVoList
    response_data['totalCount'] = webhook_records.count()
    response_data['timeUsed'] = 7
    return jsonify(response_data)


@bp_advise.route('/advise/testWebhookDelivery', methods=['POST'])
@login_required
def testWebhookDelivery():
    '''
    接口说明:webhook测试转发
    '''
    params = request.get_json()
    accessToken = params.get("accessToken", None)
    webhookDeliveryAddress = params.get("webhookDeliveryAddress", None)

    success_response = set_success_result()
    error_response = set_fail_result()

    content = {"data": "test"}
    try:
        result = requests.post(url=webhookDeliveryAddress, data=json.dumps(content), verify=False, timeout=1)
        if result.status_code == 200:
            return jsonify(success_response)
        else:
            error_response['errorCodeDesc'] = "测试转发失败"
            return jsonify(error_response)
    except:
        error_response['errorCodeDesc'] = "测试转发失败"
        return jsonify(error_response)


@bp_advise.route('/advise/retryWebhookDelivery', methods=['POST'])
@login_required
def retryWebhookDelivery():
    '''
    接口说明:转发重投递
    '''
    params = request.get_json()
    webhookDeliveryRecordId = params.get("webhookDeliveryRecordId", None)

    my_db = ToMongo('wavedevice')
    delivery_record_col = my_db.get_col('odin_advise_webhook_delivery_record')
    delivery_item = delivery_record_col.find_one({'webhook_delivery_id': webhookDeliveryRecordId}, {'_id': 0})

    response_data = set_success_result()

    if delivery_item:
        sms_sender = SendSmsResqueset()
        sms_sender.get_sms_config()
        result = sms_sender.resend_sms_delivery(delivery_item)
        if result == '1':
            my_db.update('odin_advise_sms_delivery_record', {'delivery_record_id': webhookDeliveryRecordId},
                         {"$set": {'delivery_status': '1'}})
            response_data['requestStatus'] = "SUCCESS"
        else:
            response_data['requestStatus'] = "FAIL"
    else:
        response_data['requestStatus'] = "FAIL"

    return jsonify(response_data)


@bp_advise.route('/advise/testWebhook', methods=['POST'])
# @login_required
def testWebhook():
    '''
    接口说明:webhook测试转发-收
    '''
    # /net-web/advise/testWebhook
    # params = request.get_json()
    try:
        # a = request.get_json()
        b = request.data
        mainlogger.info('原始内容 : %s' % b)
    except:
        import traceback
        mainlogger.info('内容格式不对 %s' % traceback.format_exc())

    response = set_success_result()
    return jsonify(response)

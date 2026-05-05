from datetime import datetime
from flask import Blueprint, render_template, request , jsonify ,g
import json
from Utils.db import ToMongo
from Utils.jwt_verify import *
import uuid
from .system_misc import *
import os
from system.system_misc import Cleandisk
from system.system_sync import deleteAllData
from config import SYSTEM_CFG_URL
from algorith_server.redis_connect import redis_database
import hashlib

init_clear_box = Cleandisk()


bp = Blueprint("log",__name__, url_prefix='/net-web')
@bp.route('/auth/queryLogs', methods=['GET','POST'])
@login_required
def queryLogs():
    '''
    接口注释：获取用户日志;
    '''
    params = request.get_json()
    userName = params.get("userName", None)
    userAccount = params.get("userAccount", None)
    url = params.get("url", None)
    startDate = params.get("startDate", None)
    endDate = params.get("endDate", None)
    page = params.get("page", None)
    pageSize = params.get("pageSize", None)
    operateMenu = params.get("operateMenu", None)

    query = {}
    if startDate and endDate:
        startDate = datetime.strptime(startDate, "%Y-%m-%d %H:%M:%S")
        endDate = datetime.strptime(endDate, "%Y-%m-%d %H:%M:%S")
        query['create_time'] = {"$gte" :startDate ,"$lte" :endDate}
    if operateMenu:
        query['operate_menu'] = {"$regex":operateMenu}
    if url:
        query['url'] = {"$regex":url}
    if userName:
        query['user_name'] = {"$regex":userName}
    if userAccount:
        query['user_account'] = {"$regex":userAccount}

    my_db = ToMongo('wavedevice')
    logs_coll = my_db.get_col('user_logs').find(query).sort('create_time',-1)
    pageQueryResult = {}
    total = pageQueryResult['total'] = logs_coll.count()
    pageQueryResult['size'] = pageSize
    c_flag = total % pageSize
    if c_flag != 0:
        pages = total // pageSize + 1
    elif c_flag == 0:
        pages = total // pageSize
    pageQueryResult['pages'] = pages
    pageQueryResult['list'] = []

    num = (page-1)*pageSize
    log_list = logs_coll.skip(num).limit(pageSize)

    for log in log_list:
        item = {}
        item['createTime'] = log['create_time'].strftime('%Y-%m-%d %H:%M:%S')
        item['department'] = log['department']
        item['ip'] = log['ip']
        item['logId'] = log['log_id']
        item['method'] = log['method']
        item['operateMenu'] = log['operate_menu']
        item['organizationId'] = log['organization_id']
        item['url'] = log['url']
        item['userAccount'] = log['user_account']
        item['userId'] = log['user_id']
        item['userName'] = log['user_name']
        pageQueryResult['list'].append(item)

    response_data = {}
    response_data['pageQueryResult'] = pageQueryResult
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 556
    return jsonify(response_data)

@bp.route('/auth/getUserLogsSet', methods=['GET','POST'])
@login_required
def getUserLogsSet():   
    '''
    接口注释：查询用户日志清理规则
    '''
    params = request.get_json()
    accesstoken = params.get('accessToken',None)
    current_user = g.user_account
    my_db = ToMongo('wavedevice')
    organization_id = my_db.get_col('authority_user').find_one({'user_account':current_user})['organization_id']
    rule_text = my_db.get_col('user_logs_set').find_one({'organization_id':organization_id})['rule_text']
    response_data = {}
    response_data['ruleText'] = rule_text
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 56

    return jsonify(response_data)

@bp.route('/auth/setUserLogsSet', methods=['GET','POST'])
@login_required
def setUserLogsSet():   
    '''
    接口注释：设置用户日志清理规则
    '''
    params = request.get_json()
    accesstoken = params.get('accessToken',None)
    rule_text = params.get('ruleText',None)
    current_user = g.user_account
    my_db = ToMongo('wavedevice')
    organization_id = my_db.get_col('authority_user').find_one({'user_account':current_user})['organization_id']
    my_db.update('user_logs_set',{'organization_id':organization_id},{'$set':{'rule_text':rule_text}})
    Clean_userlog = CleanLogs(organization_id=organization_id,
                               log_set=rule_text,
                               my_db=my_db)

    response_data = {}
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 56

    return jsonify(response_data)


@bp.route('/maintain/SysResourcesDetails', methods=['GET','POST'])
@login_required
def SysResourcesDetails():   
    '''
    接口注释：系统维护-系统资源详情信息
    '''
    coreTemperature = str(get_temperature())   #芯片温度
    res = get_cpu_and_memery()
    cpu = str(100-res[0])
    memHardDisk = "usedtotal:%.1fG,total%.1fG,%.4f"%(res[3],res[2],res[1]) +'%'
    diskUsage = str(get_disk()[0])

    fan_rate = get_fanrate()

    my_db = ToMongo('wavedevice')
    sys_item = my_db.get_col('authority_sys_maintain').find_one()
    iter={}
    iter['coreTemperature'] = coreTemperature
    iter['cpu'] = cpu
    iter['diskUsage'] = diskUsage
    iter['email'] = sys_item['email_notification_account'] if sys_item else None
    iter['externalExpansionHardDisk'] = None
    iter['fanRate'] = fan_rate
    iter['memHardDisk'] = memHardDisk
    iter['memUsage'] = "69.56"
    iter['phone'] = sys_item['sms_notification_account'] if sys_item else None
    
    response_data = {}
    response_data['object'] = iter
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 556

    return jsonify(response_data)

@bp.route('/maintain/SysResources', methods=['GET','POST'])
@login_required
def SysResources():
    params = request.get_json()
    accesstoken = params.get('accessToken',None) 
    alarmStorageLocation = params.get('alarmStorageLocation',None) 
    diskSpace = params.get('diskSpace',None) 
    emailNotificationAccount = params.get('emailNotificationAccount',None) 
    smsNotificationAccount = params.get('smsNotificationAccount',None) 

    my_db = ToMongo('wavedevice') 
    current_user = g.user_account
    user_item = my_db.get_col('authority_user').find_one({'user_account':current_user})
    organization_id = user_item['organization_id']
    current_userid = user_item['user_id']

    sys_item = my_db.get_col('authority_sys_maintain').find_one()
    now = datetime.now()

    if not sys_item:
        item = {'device_id':None,'device_name':None,'organization_id':organization_id,
                'alarm_storage_location':alarmStorageLocation,'disk_space':diskSpace,'sms_notification_account':smsNotificationAccount,
                'email_notification_account':emailNotificationAccount,'create_by':current_userid,'create_time':now,
                'modify_by':current_userid,'modify_time':now,'del_flag':0}
        my_db.insert('authority_sys_maintain',item)
    else:
        item_update={'alarm_storage_location':alarmStorageLocation,'disk_space':diskSpace,'sms_notification_account':smsNotificationAccount,
                    'email_notification_account':emailNotificationAccount,'modify_by':current_userid,'modify_time':now}
        my_db.update('authority_sys_maintain',{},{"$set":item_update})

    init_clear_box.get_config()   #重新拉取短信号码和邮件地址
    response_data = {}
    response_data['object'] = None
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 556
    return jsonify(response_data)


@bp.route('/maintain/downloadData', methods=['GET','POST'])
@login_required
def downloadData():   
    '''
    接口注释：配置管理导出
    '''
    params = request.get_json()
    accessToken = params.get('accessToken',None)
    my_db = ToMongo('wavedevice')

    cameraSyncRepVO = get_camera_sysninfo(my_db)

    controlManageEntity = get_control_info(my_db) 

    personEntity = get_person_info(my_db)

    workModelEntity = get_workmodel_info(my_db)

    smsDeliveryEntity = get_sms_info(my_db)
    webhookDeliveryEntity = get_webhook_info(my_db)

    response_data = {}
    response_data['cameraSyncRepVO'] = cameraSyncRepVO
    response_data['controlManageEntity'] = controlManageEntity
    response_data['personEntity'] = personEntity
    response_data['workModelEntity'] = workModelEntity
    response_data['smsDeliveryEntity'] = smsDeliveryEntity
    response_data['webhookDeliveryEntity'] = webhookDeliveryEntity
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 556

    return jsonify(response_data)


@bp.route('/maintain/delBusinessData', methods=['GET','POST'])
@login_required
def delBusinessData():   
    '''
    接口注释：清除业务数据
    '''
    params = request.get_json()
    accessToken = params.get('accessToken',None)
    operationType = params.get('operationType',None)
    my_db = ToMongo('wavedevice')

    try:
        result = deleteAllData(my_db)
    except Exception as e:
        print(e)

    if operationType == "SYSTEM":
        redis_database.flushall()

    response_data = {}
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 556
    return jsonify(response_data)

@bp.route('/maintain/fileUpload', methods=['GET','POST'])
def fileUpload():   
    '''
    接口注释：系统维护-恢复设置-上传文件
    '''
    config_file_bytes = request.files['file'].stream.read()
    filedir = SYSTEM_CFG_URL
    if not os.path.exists(filedir):
        os.mkdir(filedir)
    filepath = filedir + 'config.txt'
    with open(filepath,'wb') as fp:
        fp.write(config_file_bytes)

    response_data = {}
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 56
    return jsonify(response_data)
    
@bp.route('/maintain/uploadData', methods=['GET','POST'])
@login_required
def uploadData():   
    '''
    接口注释：系统维护-恢复设置-提交配置并修改数据库
    '''
    params = request.get_json()
    accessToken = params.get('accessToken',None)
    jsonStr = params.get('jsonStr',None)

    config = json.loads(jsonStr)
    cameraSyncRepVO = config.get("cameraSyncRepVO",None)
    controlManageEntity = config.get("controlManageEntity",None)
    personEntity = config.get("personEntity",None)
    workModelEntity = config.get("workModelEntity",None)
    smsDeliveryEntity = config.get("smsDeliveryEntity",None)
    webhookDeliveryEntity = config.get("webhookDeliveryEntity",None)

    my_db = ToMongo('wavedevice')

    insert_camera_info(my_db,cameraSyncRepVO)
    insert_control_info(my_db,controlManageEntity)
    insert_person_info(my_db,personEntity)
    insert_workmodel_info(my_db,workModelEntity)
    insert_sms_info(my_db,smsDeliveryEntity)
    insert_webhook_info(my_db,webhookDeliveryEntity)

    from algorith_server.AlgorithServer_new import SenderThread
    sender = SenderThread(context=[])
    sender.send_reboot_message()

    response_data = {}
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 56
    return jsonify(response_data)

@bp.route('/setting/uploadFile', methods=['GET','POST'])
def uploadFile():   
    '''
    接口注释：系统维护-升级管理
    '''
    algFile = request.files['file'].stream.read()
    params = request.form
    md5sum = params.get("md5sum",None)
    filename = params.get("filename",None)

    filetype = filename.split('.')[-1]
    filepath = "/data/ebox/alg." + filetype

    #文件写入
    with open(filepath,'wb') as fp:
        fp.write(algFile)

    error_response = set_fail_result()
    #计算文件的md5值
    if md5sum:
        #MD5校验
        with open(filepath,'rb') as f:
            data = f.read()
        md5_value = hashlib.md5(data).hexdigest()
        if md5_value != md5sum:
            error_response['errorCodeDesc'] = "上传文件md5校验失败"
            return error_response

    if filetype == "rar":
        cmd = "unrar x " + filepath
    elif filetype == "zip":
        cmd = "unzip " + filepath + "-d /data/ebox/"
    else:
        mainlogger.debug("upgradeAlg  文件类型不支持")

    cmd_stop = "/bin/bash /data/ebox/wavegate/WaveGateMongo/scripts/stopAlg.sh"
    err1,res1 = execShell(cmd_stop)

    err2,res2 = execShell(cmd)

    cmd_startAlg = "nohup /data/ebox/alg/monitor.sh EcalculateBox backgroud >/dev/null 2>&1  &"
    err3,res3 = execShell(cmd_startAlg)

    response_data = set_success_result()
    return jsonify(response_data)
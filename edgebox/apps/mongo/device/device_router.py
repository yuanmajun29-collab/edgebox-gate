from datetime import datetime
from flask import Blueprint, jsonify
from flask import Flask ,request,current_app
from Utils.db import *
import uuid
import cv2
import os
from threading import Thread
from Utils.CheckdeviceStatus import CheckInService
from Utils.utils import *
from Utils.jwt_verify import *
from config import UNDERLAY_URL
from system.system_misc import get_ip
import Utils.glv as glv
from .underlay_misc import UnderlayImageDBAPI,restartAlg

import Utils.edgebox_repo  # noqa: F401
from edgebox.db.mongo_collections import (
    WORK_FLOW_MISSION_DEVICE_ASSOCIATE,
)


bp = Blueprint('device_api',__name__,url_prefix='/net-web')

def position_asso_cam(position_col,position_asso_col,info):
    position_list = position_col.find({'position_area':{"$regex":info}})
    result = []
    if position_list.count() == 0:
        return result
    for item in position_list:
        res = position_asso_col.find_one({"position_id":item['position_id']})
        if res:
            result.append(res['device_id'])
    return result

@bp.route('/vidicon/pageQueryCameraEdit', methods=['POST'])
@login_required
def pageQueryCameraEdit():
    '''
    查询摄像机列表
    '''  
    try:
        params = request.get_json()
        sorttype = params.get("sortType", None)       #DESC 降序 ；  ASC 升序
        sortBy = params.get("sortBy", None)
        page = int(params.get("page", None))
        pageSize = params.get("pageSize", None)
        keywords = params.get("cameraNameOrPositionOrIp", None)
        camera_status =  params.get("cameraStatus", None) 
        cameraNum = params.get("cameraNum", None) 

        if sorttype == 'DESC':
            KEY = -1
        elif sorttype == 'ASC':
            KEY = 1
        else:
            KEY = -1     #默认降序排列

        my_db = ToMongo('wavedevice')
        camera_coll = my_db.get_col('odin_device_camera_edit')
        associate_coll = my_db.get_col('odin_device_device_position_associate')
        position_coll = my_db.get_col('odin_device_position') 
        control_associate_coll = my_db.get_col(WORK_FLOW_MISSION_DEVICE_ASSOCIATE) 
        control_manage_coll = my_db.get_col('odin_business_control_manage') 
        
        query = {}
        if cameraNum:
            query['camera_num'] = {'$regex':cameraNum}

        if keywords:    
            assocam = position_asso_cam(position_coll,associate_coll,keywords)
            query['$or'] = [{'camera_name':{'$regex':keywords}},{'camera_ip':{'$regex':keywords}},{'camera_id':{'$in':assocam}}]

        if page and pageSize:
            num = (page-1)*pageSize
            res = camera_coll.find(query).sort(sortBy,KEY).skip(num).limit(pageSize)
        else:
            res = camera_coll.find(query).sort(sortBy,KEY)

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
            if item['extendInfo']:
                item['cameraProductType'] = int(item['extendInfo'].split("=")[-1])

            data = item
            try:
                device_status = camera_status_dict[data["cameraIp"]]
            except:
                device_status = data["cameraStatus"]
            if device_status == "1":
                data["cameraStatus"] = 1           
            else:
                data["cameraStatus"] = 0

            if camera_status == "" or camera_status == None or data["cameraStatus"] == int(camera_status):

                device_id = data['cameraId']
                try:
                    position_id =associate_coll.find_one({"device_id":device_id})['position_id']
                    position_doc = position_coll.find_one({"position_id":position_id},{"_id":0})
                except:
                    position_doc = {}
                control_associate = control_associate_coll.find({"device_id":device_id})
                position_info = position_switch(position_doc)
                data = dict(data , **position_info)
                data['serviceId'] = ''
                data['serviceName'] = ''
                data['serviceState'] = ''
                data['serverIp'] = ''
                data['videotape'] = ''

                data['controlList']=[]
                for control_item in control_associate:
                    control_id = control_item['mission_id']
                    item = control_manage_coll.find_one({'control_id':control_id})
                    if not item:
                        continue
                    control_name = item['control_name']
                    data['controlList'].append(control_name)

                camera_list.append(data)
        total = my_db.get_aggregate("odin_device_camera_edit",{})
        size = int(pageSize) if pageSize else total
        if size == 0:
            pages=0
        elif total % size == 0:
            pages = total // size
        else:
            pages = total //size + 1 

        PageQueryRepVo = {'list':camera_list,
                            'pages':pages,
                            'size' :size,
                            'total' :total }
    except Exception as e:
        mainlogger.exception(e)
        PageQueryRepVo = {}
    response_data = {}
    response_data['cameraEditPageQueryRepVo'] = PageQueryRepVo
    response_data['requestId']=uuid.uuid4().hex
    response_data['requestStatus']="SUCCESS"
    response_data['timeUsed']=40
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
    data = device_coll.find_one({"camera_id":device_id},{'_id':  0})
    item={}
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
    item['liveUrl'] = data.get('live_url',None)

    if item['extendInfo']:
        item['cameraProductType'] = int(item['extendInfo'].split("=")[-1])
    else:
        item['cameraProductType'] = None
    try:
        position_id =associate_coll.find_one({"device_id":device_id})['position_id']
        position_doc = position_coll.find_one({"position_id":position_id},{"_id":0})
    except:
        position_doc = {}
    position_info = position_switch(position_doc)
    item = dict(item , **position_info)
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
    generate_log(request,db=my_db)
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
    cameraType = params.get("cameraType", None)  #摄像头类型 0 固定摄像头  1  可移动摄像头
    positionId = params.get("positionId", None)
    serviceId = params.get("serviceId", None)
    encoding_format = params.get("encodingFormat", None)    #编码格式 0 h264 1 h265
    if encoding_format:
        encoding_format = int(encoding_format) 

    cameraProductType = params.get('cameraProductType',None)
    if cameraProductType:
        extendInfo = "cameraProductType=" + cameraProductType
    else:
        extendInfo = None  

    code_stream = params.get("codeStream", None)    # 码流 0 主码流 1 子码流 2 第三码流
    if code_stream:
        code_stream = int(code_stream) 

    main_url = params.get("mainUrl", None)  #拉流地址

    camera_num = params.get("cameraNum", None)   #摄像头序列号

    setType = params.get("setType", None)  #配置方式
    if setType == "1":
        cameraIp = main_url.split("@")[1].split(":")[0]
        temp = main_url.split("@")[0].split("//")[1]
        cameraAccount = temp.split(':')[0]
        cameraPassword = temp.split(':')[1]
    if setType:
        setType = int(setType)
    device_item = my_db.get_col('odin_device_camera_edit').find_one({'camera_id':cameraId})
    origin_name = device_item['camera_name']
    if camera_Name != origin_name:
        camera_name_list = my_db.get_keyvalues("odin_device_camera_edit","camera_name")
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
        camera_ip_list = my_db.get_keyvalues("odin_device_camera_edit","camera_ip")
        if cameraIp in camera_ip_list:
            response_data = {}
            response_data['errorCode'] = "CAMERA_IP_EXIST"
            response_data['errorCodeDesc'] = "该摄像机的IP已存在!"
            response_data['exceptionCodeDesc'] = ""
            response_data['requestId'] = uuid.uuid4().hex
            response_data['requestStatus'] = "FAIL"
            response_data['timeUsed'] = 143
            return response_data

    res ={'camera_name':camera_Name,'camera_account':cameraAccount,'camera_id':cameraId,'extend_info':extendInfo,'set_type':setType,
            'camera_ip': cameraIp,'rtsp_port':rtsp_port,'camera_password':cameraPassword,'camera_remarks':cameraRemarks,'camera_type':cameraType,
            'service_id':serviceId ,'encoding_format':encoding_format ,'code_stream':code_stream ,'main_url':main_url ,'camera_num':camera_num        
         }

    result = my_db.update('odin_device_camera_edit',
                    {'camera_id':cameraId},
                    {'$set':res}
                )

    result = my_db.update('odin_device_device_position_associate',
                    {'device_id':cameraId},
                    {'$set':{"position_id":positionId}}
                )              
    if origin_url != res['main_url']:
        from algorith_server.AlgorithServer_new import SenderThread
        sender = SenderThread(current_app.app_context())
        sender.send_3007_message()

    response_data = {}
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 56

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
    datas = camera_coll.find({},{'_id':  0})
    for data in datas:
        item = {}
        cameraIdList = []
        positionid = data['position_id']
        reslist = position_coll.find({'position_id':positionid})
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
    generate_log(request,db=my_db)
    a = {} ; b ={} 
    params = request.get_json()
    a['camera_name'] = params.get('cameraName')
    set_type = a['set_type'] = int(params.get('setType'))
    a['camera_ip'] = params.get('cameraIp')
    a['rtsp_port'] = int(params.get('rtspPort'))
    a['camera_account'] = params.get('cameraAccount')
    a['camera_password'] = params.get('cameraPassword')
    encodingFormat = params.get('encodingFormat',None)
    a['encoding_format'] = int(encodingFormat) if encodingFormat else None
    codeStream = params.get('codeStream',None)
    a['code_stream'] = int(codeStream) if codeStream else None
    a['camera_num'] = params.get('cameraNum')
    a['main_url'] = params.get('mainUrl')
    a['camera_type'] = params.get('cameraType',None)
    a['camera_id'] = str(uuid.uuid4().int)[:21]
    a['camera_status'] = '1'  #初始化在线状态
    a['camera_mac'] = None
    a['camera_remarks'] = None
    a['create_time'] = a['update_time'] = datetime.now()
    a['camera_ip_label'] = None
    a['videotape'] = None
    a['product_key'] = None
    a['report_frequency'] = None
    a['camera_source'] = 1 #手动添加
    a['service_id'] = None

    if set_type == 1:
        main_url = a["main_url"]
        symbol = "@"
        if symbol not in main_url:
            account,password = None,None
            temp = main_url.split("//")[1].split("/")[0].split(":")
            ip = temp[0]
            port = temp[1]
        else:
            temp = a["main_url"].split("@")
            account , password = temp[0].split("//")[1].split(":")  
            ip,port = temp[1].split("/")[0].split(":")

        a['camera_ip'] = ip   
        a['rtsp_port'] = int(port) if port else None
        a['camera_account'] = account
        a['camera_password'] = password
    
    cameraProductType = params.get('cameraProductType',None)    
    a['extend_info'] = "cameraProductType=" + cameraProductType if cameraProductType else None
   
    b['position_id']= params.get('positionId')
    if not b['position_id']:
        b['position_id'] = uuid.uuid4().hex

    position_coll = my_db.get_col('odin_device_position')
    position_item = position_coll.find_one({'position_id':b['position_id']})
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

    check_thread = Thread(target=cs.check_device,args=[a['camera_ip']])
    check_thread.start()
    
    result1 = my_db.insert('odin_device_camera_edit',a)
    result2 = my_db.insert('odin_device_device_position_associate', b)

    from algorith_server.AlgorithServer_new import SenderThread
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
    generate_log(request,db=my_db)
    mission_device_col = my_db.get_col(WORK_FLOW_MISSION_DEVICE_ASSOCIATE)    
    items = mission_device_col.find({"device_id":camera_id})
    if items.count() != 0:
        error_response = set_fail_result()
        error_response['errorCode'] = "CAMERA_NOT_DEL"
        error_response['errorCodeDesc'] = "摄像机已绑定布控任务，不能删除"
        return jsonify(error_response)
    
    crowd_asso_col = my_db.get_col("crowd_entrance_camera_associate")
    assoItem = crowd_asso_col.find_one({"camera_id":camera_id})
    if  assoItem:
        error_response = set_fail_result()
        error_response['errorCode'] = "CAMERA_NOT_DEL"
        error_response['errorCodeDesc'] = "摄像机已绑定人流项目，不能删除"
        return jsonify(error_response)

    res_cam = my_db.delete("odin_device_camera_edit",{"camera_id" :camera_id})
    res_aso = my_db.delete("odin_device_device_position_associate",{"device_id" :camera_id})
    res_pos = my_db.delete("odin_device_position",{"camera_id" :camera_id})

    from algorith_server.AlgorithServer_new import SenderThread
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

    query = {'device_id':deviceId}
    my_db = ToMongo('wavedevice')
    user_id = get_user_id(request,db=my_db)

    if isOpen == 1:
        my_db.delete('centimani_storage_live_choose_record',query)
    elif isOpen == 0:
        query['user_id'] =user_id
        my_db.insert('centimani_storage_live_choose_record',query)
    response_data =set_success_result()
    return jsonify(response_data)

@bp.route('/vidicon/deviceLive', methods=['POST'])   
@login_required
def deviceLive():
    params = request.get_json()
    deviceLiveList = params.get("deviceLiveList")
    device_id = deviceLiveList[0]['deviceId']
    effective_time = deviceLiveList[0]['effectiveTime']
    my_db = ToMongo('wavedevice')
    camera_coll = my_db.get_col('odin_device_camera_edit').find_one({'camera_id':device_id})
    url = camera_coll['main_url']
    if not url:
        ip = camera_coll['camera_ip']
        camera_account = camera_coll['camera_account']
        camera_password = camera_coll['camera_password']
        url='rtsp://' + camera_account + ':' + camera_password + '@' + ip


    response_data = {}
    response_data['deviceLiveList'] = []
    item={}
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
    user_id = get_user_id(request,db=my_db)
    liverecord_col = my_db.get_col('centimani_storage_live_choose_record')
    query = {'user_id':user_id}
    deviceid_list = liverecord_col.distinct('device_id',query)
    response_data = set_success_result()
    response_data['liveRecordList'] = deviceid_list
    return jsonify(response_data)

@bp.route('/control/cameraCountStatistics', methods=['GET','POST'])
@login_required
def cameraCountStatistics():
    '''
    接口说明：摄像机设备数量统计
    '''
    my_db = ToMongo('wavedevice')
    camera_coll = my_db.get_col('odin_device_camera_edit')
    result = camera_coll.aggregate([{'$match':{}},{'$group':{'_id':'$camera_status','count':{'$sum':1}}}
                           ,{'$project':{'status':'$_id',"_id":0,"count": 1}}])
    cameraTotalCount = 0
    cameraNormalCount = 0
    for item in result:
        status = item['status']
        num = item['count']
        cameraTotalCount += num
        if status == '0':
            cameraNormalCount = num

    response_data = {}
    response_data['cameraTotalCount'] = cameraTotalCount
    response_data['cameraNormalCount'] = cameraNormalCount
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 56
    return jsonify(response_data)


@bp.route('/vidicon/testRtspStream', methods=['GET','POST'])
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

@bp.route('/vidicon/uploadUnderlay', methods=['GET','POST'])
#@login_required
def uploadUnderlay():
    '''
    接口说明：上传摄像机对应底图
    '''
    params = request.form
    imageH = params.get("imageH")
    imageW = params.get("imageW")
    imgtype = params.get("type")
    cameraId = params.get("cameraId")
    algorithmConstantNum = params.get("algorithmConstantNum")

    imgfile = request.files['file'].stream.read()

    underlay_path = UNDERLAY_URL
    if not os.path.exists(underlay_path):
        # 创建底图根路径
        os.makedirs(underlay_path)
    
    camera_path = underlay_path + cameraId
    if not os.path.exists(camera_path):
        # 创建底图-摄像机路径
        os.makedirs(camera_path)

    imgid = str(uuid.uuid4().int)[:21]
    imgpath = camera_path + '/' + imgid + ".jpg"

    #把底图存到本地
    with open(imgpath,"wb") as outfile:
        outfile.write(imgfile)

    item = {'img_id':imgid,
            'camera_id':cameraId,
            'algorithm_constant_num':algorithmConstantNum}

    my_db = ToMongo('wavedevice')
    my_db.insert("odin_device_underlay",item)

    #是否有任务绑定摄像机和该算法，有则重启算法
    threadRe = Thread(target=restartAlg,args=[my_db,cameraId,algorithmConstantNum])
    threadRe.start()

    response_data = set_success_result()
    response_data['underlayId'] = imgid
    return jsonify(response_data)

@bp.route('/vidicon/batchUploadUnderlay', methods=['GET','POST'])
#@login_required
def batchUploadUnderlay():
    '''
    接口说明：批量上传摄像机对应底图
    '''
    params = request.form
    cameraId = params.get("cameraId")
    algorithmConstantNum = params.get("algorithmConstantNum")

    upload_files = request.files.getlist('file')

    underlay_path = UNDERLAY_URL
    if not os.path.exists(underlay_path):
        # 创建底图根路径
        os.makedirs(underlay_path)

    error_filenames = []
    my_db = ToMongo('wavedevice')
    for file in  upload_files:
        filename = file.filename
        if '.' in filename and filename.rsplit('.',1)[1] in ['png','jpg']:
            img_id = uuid.uuid4().hex
            img_url = UNDERLAY_URL + cameraId + '/' + img_id + '.jpg'
            img_dir = UNDERLAY_URL + cameraId
            if not os.path.exists(img_dir):
                # 创建底图子路径
                os.makedirs(img_dir)
            file.save(img_url)
            item = { 'img_id':img_id,'camera_id':cameraId,'algorithm_constant_num':algorithmConstantNum } 
            my_db.insert("odin_device_underlay",item)
        else:
            error_filenames.append(filename)

    #是否有任务绑定摄像机和该算法，有则重启算法
    threadRe = Thread(target=restartAlg,args=[my_db,cameraId,algorithmConstantNum])
    threadRe.start()
    response_data = set_success_result()
    response_data['errorFilenameList'] = error_filenames
    return jsonify(response_data)

@bp.route('/vidicon/queryUnderlay', methods=['GET','POST'])
@login_required
def queryUnderlay():
    '''
    接口说明：查询摄像机对应底图
    '''
    params = request.get_json()
    cameraId = params.get("cameraId", None) 
    algorithmConstantNum = params.get("algorithmConstantNum")

    port = glv.get_value('nginx_port','8088')
    host_ip = glv.get_value('host_ip',None)
    if not host_ip:
        host_ip = get_ip()

    img_pathhead = 'http://%s:%s/net-web/underlay/'%(host_ip,port)

    my_db = ToMongo('wavedevice')
    col = my_db.get_col('odin_device_underlay')
    query = {'camera_id':cameraId,'algorithm_constant_num':algorithmConstantNum}
    items = col.find(query)

    underlayList = []
    response = set_success_result()
    if items.count() == 0:
        response['underlayList'] = underlayList
        return jsonify(response)
    
    for item in items:
        img_id = item.get('img_id')
        url = img_pathhead + img_id  + '?' + 'id=%s'%cameraId
        newitem = {
                    'imgId':item.get('img_id'),
                    'cameraId':item.get('camera_id'),
                    'algorithmConstantNum':item.get('algorithm_constant_num'),
                    'imgUrl':url}
        underlayList.append(newitem)

    response['underlayList'] = underlayList
    return jsonify(response) 


@bp.route('/vidicon/deleteUnderlay', methods=['GET','POST'])
@login_required
def deleteUnderlay():
    '''
    接口说明：删除摄像机对应底图
    '''
    params = request.get_json()
    underlayId = params.get("underlayId", None)  #底图id
    cameraId = params.get("cameraId")
    algorithmConstantNum = params.get("algorithmConstantNum")

    imgpath = UNDERLAY_URL + cameraId + '/' + underlayId + '.jpg'

    my_db = ToMongo('wavedevice')
    query = {'camera_id':cameraId,"img_id":underlayId}
    my_db.delete('odin_device_underlay',query)

    if os.path.exists(imgpath):
        #删除底图
        os.remove(imgpath)

    #是否有任务绑定摄像机和该算法，有则重启算法
    threadRe = Thread(target=restartAlg,args=[my_db,cameraId,algorithmConstantNum])
    threadRe.start()
    response_data = set_success_result()
    return jsonify(response_data)

view_func = UnderlayImageDBAPI.as_view(('{}_api').format('underlay'))
bp.add_url_rule(('/{}/<string:{}>').format('underlay', 'image_id'), view_func=view_func,methods=['GET', 'PUT', 'DELETE'])

cs = CheckInService()         #启动查询摄像头状态进程
if __name__  == '__main__':
    app = Flask(__name__, static_url_path='')
    app.register_blueprint(bp)
    cs = CheckInService()         #启动查询摄像头状态进程
    app.run('127.0.0.1',5004,debug=True)
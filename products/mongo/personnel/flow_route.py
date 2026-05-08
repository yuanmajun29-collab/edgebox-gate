from datetime import datetime
from flask import Blueprint, jsonify
from flask import Flask ,request
import uuid
from Utils.jwt_verify import *
from Utils.db import *
from system.sys_config import *
from system.system_misc import database_to_dict

bp = Blueprint('marketProject',__name__,url_prefix='/net-web')

mainlogger = logger.getLogger('main')

@bp.route('/crowdinfo/queryProjectInfo', methods=['POST'])
@login_required
def queryProjectInfo():
    '''
    查询人流项目
    '''  

    params = request.get_json()
    page = params.get("page")
    pageSize = params.get("pageSize")
    projectId = params.get("projectId")

    my_db = ToMongo('wavedevice')
    col = my_db.get_col("crowd_project_info")
    asso_col = my_db.get_col("crowd_entrance_camera_associate")

    if page and pageSize:
        num = pageSize*(page-1)
    else:
        pageSize = 10
        num = 0

    query = {}
    if projectId:
        query["project_id"] = projectId

    res = col.find(query)
    totalNum = res.count()
    pages = totalNum//pageSize + 1
    items = res.skip(num).limit(pageSize)

    projectCrowdInfoEntityList = []
    for item in items:
        newItem = dict()
        projectId = item['project_id']
        newItem['projectId'] = projectId
        newItem['projectName'] = item['project_name']
        createTime = item['create_time']
        updateTime = item['update_time']
        if createTime:
            newItem['createTime'] = int(createTime.timestamp()) *1000
        if updateTime:
            newItem['updateTime'] = int(updateTime.timestamp()) *1000
        
        query_project = {"project_id":projectId}
        camList = asso_col.distinct("camera_id",query_project)
        newItem['deviceNum'] = str(len(camList))
        projectCrowdInfoEntityList.append(newItem)

    response = set_success_result()
    response['projectCrowdInfoEntityList'] = projectCrowdInfoEntityList
    response['page'] = pages
    response['pageSize'] = pageSize
    response['totalCount'] = totalNum
    return jsonify(response)

@bp.route('/crowdinfo/queryProjectList', methods=['POST'])
@login_required
def queryProjectList():
  
    params = request.get_json()

    my_db = ToMongo('wavedevice')
    col = my_db.get_col("crowd_project_info")
    items = col.find({})

    crowdProjectInfoEntities = []
    for item in items:
        newItem = database_to_dict(item,project_database,project_web)
        crowdProjectInfoEntities.append(newItem)

    response = set_success_result()
    response["crowdProjectInfoEntities"] = crowdProjectInfoEntities
    return jsonify(response)

@bp.route('/exitinfo/queryProjectDetail', methods=['POST'])
@login_required
def queryProjectDetail():
    '''
    查询人流项目详情
    '''
    params = request.get_json()
    entranceName = params.get("entranceName")
    projectId = params.get("projectId")

    query = {}
    if entranceName:
        query["entrance_name"] = {"$regex":entranceName}
    if projectId:
        query["project_id"] = projectId
    my_db = ToMongo("wavedevice")
    col = my_db.get_col("crowd_entrance_exit_info")

    items = col.find(query)
    crowdEntranceExitInfoEntities = []
    for item in items:
        newItem = database_to_dict(item,entrance_database,entrance_web)
        crowdEntranceExitInfoEntities.append(newItem)
    response = set_success_result()
    response["crowdEntranceExitInfoEntities"] = crowdEntranceExitInfoEntities
    return jsonify(response)

@bp.route('/crowdinfo/deleteProjectInfo', methods=['POST'])
@login_required
def deleteProjectInfo():
    '''
    删除人流项目
    '''  
    params = request.get_json()
    projectId = params.get("projectId")
    my_db = ToMongo('wavedevice')

    query = {'project_id':projectId}

    col = my_db.get_col("crowd_entrance_exit_info")
    entrance_list = col.distinct("entrance_id",query)

    query_entrance = {"entrance_id":{"$in":entrance_list}}
    my_db.delete('crowd_entrance_camera_associate',query_entrance,is_one=False)
    my_db.delete('crowd_entrance_exit_info',query,is_one=False)
    my_db.delete('crowd_project_info',query,is_one=False)
    response = set_success_result()
    return jsonify(response)
        

@bp.route('/crowdinfo/addProjectInfo', methods=['POST'])
@login_required
def addProjectInfo():
    '''
    增加人流项目
    '''  

    params = request.get_json()
    projectName = params.get("projectName")

    id = uuid.uuid4().hex
    createTime  = datetime.now()

    item= {
            "project_id":id,
            "create_time":createTime,
            "project_name":projectName,
            "update_time":createTime
            }

    my_db = ToMongo('wavedevice')
    my_db.insert('crowd_project_info',item)

    response = set_success_result()
    return jsonify(response)
              
   
@bp.route('/crowdinfo/updateProjectInfo', methods=['POST'])
@login_required
def updateProjectInfo():
    '''
    编辑人流项目
    '''  

    params = request.get_json()
    projectId = params.get("projectId")
    projectName = params.get("projectName")

    update_time = datetime.now()
    item= {"project_name":projectName,"update_time":update_time}

    my_db = ToMongo('wavedevice')
    query={"project_id":projectId}

    my_db.update('crowd_project_info',query,{"$set":item})
    response = set_success_result()
    return jsonify(response)
              

@bp.route('/crowddetail/queryCrowdDetail', methods=['POST'])
@login_required
def queryCrowdDetail():
    '''
    查询人流项目绑定的摄像机
    '''
    params = request.get_json()
    page = params.get("page")
    pageSize = params.get("pageSize")
    projectId = params.get("projectId")
    entranceId = params.get("entranceId")

    my_db = ToMongo('wavedevice')
    entrance_col = my_db.get_col("crowd_entrance_exit_info")
    assoCam_col = my_db.get_col("crowd_entrance_camera_associate")
    device_col = my_db.get_col("odin_device_camera_edit")
    position_col = my_db.get_col("odin_device_position")

    if page and pageSize:
        num = pageSize*(page-1)
    else:
        pageSize = 10
        num = 0

    projectCrowdDetailEntityList = []
    if entranceId:
        query = {"entrance_id":entranceId}
        items = assoCam_col.find(query).skip(num).limit(pageSize)
    else:
        query = {"project_id":projectId}
        entrance_list = entrance_col.distinct("entrance_id",query)
        query_detail = {"entrance_id":{"$in":entrance_list}}
        items = assoCam_col.find(query_detail).skip(num).limit(pageSize)

    for item in items:
        camera_id = item.get("camera_id")
        entranceId = item.get("entrance_id")
        query = {"camera_id":camera_id}
        deviceItem = device_col.find_one(query)
        cameraName = deviceItem.get("camera_name")
        position_item = position_col.find_one({"camera_id":camera_id})
        positionId = position_item.get("position_id")
        positionName = position_item.get("position_area")
        positionDesc = position_item.get("position_desc")

        entranceItem = entrance_col.find_one({"entrance_id":entranceId})
        entranceExitName = entranceItem.get("entrance_name")
        newItem = {"cameraId":camera_id,
                   "cameraName":cameraName,
                   "crowdType":None,
                   "entranceExitName":entranceExitName,
                   "entranceId":entranceId,
                   "positionDesc":positionDesc,
                   "positionName":positionName,
                   "positionId":positionId}
        projectCrowdDetailEntityList.append(newItem)

    response = set_success_result()
    response["projectCrowdDetailEntityList"] = projectCrowdDetailEntityList

    return jsonify(response)

@bp.route('/exitinfo/addProjectDetail', methods=['POST'])
@login_required
def addProjectDetail():
   
    params = request.get_json()
    entranceName = params.get("entranceName")
    projectId = params.get("projectId")
    projectName = params.get("projectName")

    my_db = ToMongo('wavedevice')

    create_time = datetime.now()
    entrance_id = uuid.uuid4().hex

    item = {
        "entrance_id":entrance_id,
        "create_time":create_time,
        "update_time":create_time,
        "entrance_name":entranceName,
        "project_id":projectId,
        "project_name":projectName
    }

    my_db.insert("crowd_entrance_exit_info",item)

    response = set_success_result()
    return jsonify(response)

@bp.route('/exitinfo/updateProjectDetail', methods=['POST'])
@login_required
def updateProjectDetail():
   
    params = request.get_json()
    entranceName = params.get("entranceName")
    entranceId =  params.get("entranceId")
    projectId =  params.get("projectId")
    projectName = params.get("projectName")

    my_db = ToMongo('wavedevice')

    query = {"project_id":projectId,"entrance_id":entranceId}
    item = {"entrance_name":entranceName}

    my_db.update("crowd_entrance_exit_info",query,{"$set":item})

    response = set_success_result()
    return jsonify(response)

@bp.route('/exitinfo/deleteProjectDetail', methods=['POST'])
@login_required
def deleteProjectDetail():
   
    params = request.get_json()
    entranceId = params.get("entranceId")
    projectId = params.get("projectId")

    my_db = ToMongo('wavedevice')

    query = {"entrance_id":entranceId}
    my_db.delete("crowd_entrance_camera_associate",query,is_one=False)
    my_db.delete("crowd_entrance_exit_info",query,is_one=False)

    response = set_success_result()
    return jsonify(response)


@bp.route('/crowddetail/addCrowdCamera', methods=['POST'])
@login_required
def addCrowdCamera():
   
    params = request.get_json()
    entranceId = params.get("entranceId")
    projectId = params.get("projectId")
    entranceName = params.get("entranceName")
    cameraList = params.get("cameraList")

    my_db = ToMongo('wavedevice')

    if not entranceId:
        error_response = set_fail_result()
        error_response["errorCodeDesc"] = "请选择绑定的出入口"
        return jsonify(error_response)

    now = datetime.now()
    for cameraItem in cameraList:
        camera_id = cameraItem.get("cameraId")
                
        newItem = {       
                    "entrance_id":entranceId,
                    "camera_id":camera_id,
                    "project_id":projectId,
                    "create_time":now,
                    "update_time":now
                  }
        
        my_db.insert("crowd_entrance_camera_associate",newItem)


    response = set_success_result()
    return jsonify(response)


@bp.route('/crowddetail/deleteCrowdCamera', methods=['POST'])
@login_required
def deleteCrowdCamera():
   
    params = request.get_json()
    cameraId = params.get("cameraId")
    entranceDetailId = params.get("entranceDetailId")
    entranceId = params.get("entranceId")

    my_db = ToMongo('wavedevice')
    query = {"entrance_id":entranceId,"camera_id":cameraId}
    my_db.delete("crowd_entrance_camera_associate",query,is_one=True)

    response = set_success_result()
    return jsonify(response)


    
@bp.route('/flowanalysis/queryPassCrowd', methods=['POST'])
@login_required
def queryPassCrowd():
    '''
    查询路过人流
    '''  
    params = request.get_json()
    emergencyRecordDate = params.get("emergencyRecordDate")
    reportType = params.get("reportType")    # 日报 and 月报
    detailType = params.get("detailType")   # 汇总 and 明细
    date = params.get("date")
    crowdType = params.get("crowdType")
    projectId = params.get("projectId")

    query = {"project_id":projectId,"crowd_type":crowdType}
    my_db = ToMongo('wavedevice')
    col = my_db.get_col('crowd_emergency_record')
    emergencyRecordEntityList = []

    response = set_success_result()
    response['emergencyRecordEntityList'] = emergencyRecordEntityList
    return jsonify(response)              
    
@bp.route('/flowanalysis/queryEnterCrowd', methods=['POST'])
@login_required
def queryEnterCrowd():
    '''
    查询进店率
    '''  

    params = request.get_json()
    emergencyRecordDate = params.get("emergencyRecordDate")
    reportType = params.get("reportType")    # 日报 and 月报
    date = params.get("date")
    crowdType = params.get("crowdType")
    projectId = params.get("projectId")

    my_db = ToMongo('wavedevice')
    col = my_db.get_col('crowd_emergency_record')
    query = {"project_id":projectId}
    emergencyRecordEntityList = []
    
    response = set_success_result()
    response['emergencyRecordEntityList'] = emergencyRecordEntityList
    return jsonify(response)
              

@bp.route('/flowanalysis/queryPresenceCrowd', methods=['POST'])
@login_required
def queryPresenceCrowd():
    '''
    查询在场人流
    '''  
    params = request.get_json()
    emergencyRecordDate = params.get("emergencyRecordDate")
    date = params.get("date")
    crowdType = params.get("crowdType")
    projectId = params.get("projectId")

    my_db = ToMongo('wavedevice')
    col = my_db.get_col('crowd_emergency_record')
    query = {"project_id":projectId}

            
    response = set_success_result()
    response['presenceCrowdMap'] = []
    return jsonify(response)
            

import  uuid
from datetime import datetime
import io,zipfile,os,xlwt
from flask import Blueprint,request, jsonify,current_app,send_file

from Utils.db import *
from Utils.jwt_verify import *
from Utils.utils import generate_log,set_fail_result,set_success_result
from system.sys_config import *
from system.system_misc import database_to_dict
from config import EMERGENCY_IMG_PATH
from Utils.opencv_utils import draw_frame
from Utils.voicedevice_utils import VoiceBoxUtils,LingsSound
from algorith_server.Agreementunpack import *

import Utils.edgebox_repo  # noqa: F401
from edgebox.db.workflow_mission_queries import workflow_mission_collection, find_workflow_mission_by_mission_id
from edgebox.db.mongo_collections import (
    WORK_FLOW_ALGORITHM_CONSTANT,
    WORK_FLOW_INSIGHT_MODEL,
    WORK_FLOW_INSIGHT_MODEL_ALGORITHM_INSTANCE,
    WORK_FLOW_MISSION,
    WORK_FLOW_MISSION_DEVICE_ASSOCIATE,
    WORK_FLOW_MISSION_MODEL_ASSOCIATE,
    WORK_FLOW_MISSION_PERSONNELGROUP_ASSOCIATE,
    WORK_FLOW_MISSION_PERSONNEL_ASSOCIATE,
    WORK_FLOW_PERSONNEL,
    WORK_FLOW_PERSONNELGROUP,
    WORK_FLOW_PERSONNEL_PERSONNELGROUP_ASSOCIATE,
)

bp = Blueprint("control",__name__, url_prefix='/net-web')


def find_asso_cam(cam_col,mission_device_col,cameraNname):
    if not cameraNname:
        cam_list = mission_device_col.distinct('mission_id')
        return cam_list
    query = {"camera_name":{"$regex":cameraNname}}
    res = cam_col.distinct('camera_id',query)
    query2 = {'device_id':{'$in':res}}
    cam_list = mission_device_col.distinct('mission_id',query2)
    return cam_list

def find_asso_alg(constant_col,instance_col,algNname):
    if not algNname:
        alg_list = instance_col.distinct('mission_id')
        return alg_list
    query = {"algorithm_constant_name":{"$regex":algNname}}
    res = constant_col.distinct('algorithm_constant_num',query)
    query2 = {'algorithm_constant_num':{'$in':res}}
    alg_list = instance_col.distinct('mission_id',query2)
    return alg_list

# 布控任务
@bp.route('/control/getControlItemList', methods=['GET','POST'])
@login_required
def getControlItemList():
    responses={}
    my_db = ToMongo("wavedevice")
    mission_coll = workflow_mission_collection(my_db).find()
    mission_model_associate = my_db.get_col(WORK_FLOW_MISSION_MODEL_ASSOCIATE)
    algorithm_coll = my_db.get_col(WORK_FLOW_ALGORITHM_CONSTANT)
    model_coll = my_db.get_col(WORK_FLOW_INSIGHT_MODEL)
    control_coll = my_db.get_col("odin_business_control_manage")
    items=[]
    for controlItem in mission_coll:
        item={}
        item['controlId']=controlItem['mission_id']
        control_item = control_coll.find_one({'control_id':item['controlId']})
        item['controlName']=control_item['control_name']
        item['missionStatus']=controlItem['mission_status']
        item['personCount']=0
        item['deviceCount']=1
        item['missionStartTime']=controlItem['mission_start_time']
        item['missionEndTime']=controlItem['mission_end_time']
        item['storageTime']=control_item['storage_time']
        item['storageNum']=control_item['storage_num']
        item['emergencyAudio']=controlItem['emergency_audio']
        item['emergencyIntervalTime']=controlItem['emergency_interval_time']
        insightModelList=[]
        missionModels = mission_model_associate.find({"mission_id":item['controlId']})
        for missionModel in missionModels :
            insightModel={}
            algorith = model_coll.find_one({'model_id':missionModel['insight_model_id']})
            insightModel['modelName']=algorith['model_name']
            insightModel['modelId']=algorith['model_id']
            insightModel['organizationId']=algorith['organization_id']
            insightModel['isSaveVideo']=algorith['is_save_video']
            insightModel['videoDuration']=algorith['video_duration']
            insightModel['modelDdesc']=algorith['model_desc']

            insightModel['createTime']=algorith['createTime']
            insightModel['createTimeStr']=algorith['createTime'].strftime('%Y-%m-%d %H:%M:%S')

            insightModelList.append(insightModel)
        item['insightModelList']=insightModelList
        items.append(item)
    responses['requestStatus']="SUCCESS"
    responses['requestId']= uuid.uuid4().hex
    responses['timeUsed']=53
    responses['pageSize']=0
    responses['totalCount']=3
    responses['page']=0
    responses['controlInfoVoList']=items
    return  jsonify( responses)


@bp.route('/control/queryControlTaskInfo', methods=['GET','POST'])
@login_required
def queryControlTaskInfo():

    response={}
    controlId=request.json.get('controlId')
    my_db = ToMongo('wavedevice')
    device_associate_coll = my_db.get_col(WORK_FLOW_MISSION_DEVICE_ASSOCIATE)
    control_manage_coll = my_db.get_col("odin_business_control_manage")
    mission_coll = workflow_mission_collection(my_db)
    model_associate_coll = my_db.get_col(WORK_FLOW_INSIGHT_MODEL_ALGORITHM_INSTANCE)
    camera_coll = my_db.get_col("odin_device_camera_edit")
    equipment_col = my_db.get_col('odin_device_equip')
    personnel_coll = my_db.get_col(WORK_FLOW_PERSONNEL)
    personnel_associate_coll = my_db.get_col(WORK_FLOW_MISSION_PERSONNEL_ASSOCIATE)
    personnelgroup_associate_coll = my_db.get_col(WORK_FLOW_MISSION_PERSONNELGROUP_ASSOCIATE)
    group_col =  my_db.get_col(WORK_FLOW_PERSONNELGROUP)
    asso_person_col = my_db.get_col(WORK_FLOW_PERSONNEL_PERSONNELGROUP_ASSOCIATE)

    query = {'mission_id':controlId}

    device_associate = device_associate_coll.find({'mission_id':controlId})
    control_manage = control_manage_coll.find_one({'control_id':controlId})
    model_associate = model_associate_coll.find({'mission_id':controlId},{'_id':0})
    mission_item = mission_coll.find_one({'mission_id':controlId})
    equip_associate = equipment_col.find({'mission_id':controlId})
    asso_personid = personnel_associate_coll.find({'mission_id':controlId})
    asso_persongroup = personnelgroup_associate_coll.distinct('personnel_group_id',query)

    response['controlId'] = controlId
    response['controlName'] = control_manage['control_name']
    response['controlStatus'] = mission_item['mission_status']
    response['createTime'] = control_manage['create_time'].strftime("%Y-%m-%d %H:%M:%S") if control_manage['create_time'] else None
    response['deviceList'] = []
    response['deviceEquipEntityList'] = []

    response['personnelIdList'] = []
    response['personnelList'] = []

    #任务关联的摄像头
    for associate_item in device_associate:
        temp={}
        temp['deviceId'] = associate_item['device_id']
        camera_info = camera_coll.find_one({'camera_id':associate_item['device_id']})
        temp['productKey'] = associate_item['product_key']
        temp['missionId'] = associate_item['mission_id']
        temp['cameraIp'] = camera_info['camera_ip']
        temp['cameraName'] = camera_info['camera_name']
        response['deviceList'].append(temp)

    #任务关联的联动控制器
    for equip_item in equip_associate:        
        temp = database_to_dict(equip_item,equip_database,equip_web)
        response['deviceEquipEntityList'].append(temp)

    #任务关联的人脸ID
    for asso_person_item in asso_personid:
        response['personnelIdList'].append(asso_person_item['personnel_id'])

    #任务关联的人脸组
    if  asso_persongroup:
        response['personnelGroupList'] = []
        for group_id in asso_persongroup:
            query = {'personnel_group_id':group_id}
            group_item = group_col.find_one(query)
            personnum = asso_person_col.find(query).count()
            res = database_to_dict(group_item,personnel_group_database,personnel_group_web)
            res['personNum'] = personnum
            response['personnelGroupList'].append(res)

    response['emergencyAudio'] = mission_item['emergency_audio']
    response['emergencyIntervalTime'] = mission_item['emergency_interval_time']
    response['emergencyLevel'] = mission_item['emergency_level']
    response['emergencyMusicCloseMethod'] = mission_item['emergency_music_close_method']
    
    response['insightModelList'] = []
    response['instanceList'] = []
    for item in model_associate:
        iter = {}
        iter["algorithmConstantNum"] = item["algorithm_constant_num"]
        iter["algorithmServiceNum"] = item["algorithm_service_num"]
        iter["controlId"] = item["mission_id"]
        iter["countLimit"] =item["count_limit"]
        iter["createTime"] =int(item["create_time"].timestamp()) *1000 if item["create_time"] else None
        iter["discernType"] =item["discern_type"]
        #iter["instanceColour"] =item["instance_colour"]
        iter["instanceId"] =item["instance_id"]
        iter["intervalTime"] =item["interval_time"]
        iter["isUse"] =item["is_use"]
        iter["lastTime"] =item["last_time"]
        iter["operateType"] = None
        iter["organizationId"] =item["organization_id"]
        iter["rateNum"] =item["rate_num"]
        iter["timeRangeNum"] =item["time_range_num"]
        response['instanceList'].append(iter)

    response['missionEndTime'] = mission_item['mission_end_time']
    response['missionStartTime'] = mission_item['mission_start_time']

    response['requestId'] = uuid.uuid4().hex
    response['requestStatus'] = 'SUCCESS'
    response['storageNum'] = control_manage['storage_num']
    response['storageTime'] = control_manage['storage_time']
    response['timeUsed'] = 189


    return  jsonify(response)

@bp.route('/control/selectWorkFlowAlgorithmConstantPaging', methods=['GET','POST'])
@login_required
def selectWorkFlowAlgorithmConstantPaging():
    '''
    接口描述：算法常量分页列表
    '''
    pageSize =request.json.get("pageSize")
    page = request.json.get("page")
    my_db = ToMongo("wavedevice")
    algorithm_coll = my_db.get_col(WORK_FLOW_ALGORITHM_CONSTANT).find()
    items=[]
    for algorithm in algorithm_coll:
        item={}
        item['algorithmConstantId']= algorithm['algorithm_constant_id']
        item['algorithmConstantName']= algorithm['algorithm_constant_name']
        item['algorithmConstantNum']= algorithm['algorithm_constant_num']
        item['algorithmConstantType']=algorithm['algorithm_constant_type']
        item['algorithmConstantStatus']=algorithm['algorithm_constant_status']
        item['algorithmModel']= algorithm['algorithm_model']
        item['algorithmVersion']= algorithm['algorithm_version']
        item["algorithmServiceNum"] = algorithm["algorithm_service_num"]
        items.append( item)
    respone={}
    respone['requestStatus']="SUCCESS"
    respone['requestId']= uuid.uuid4().hex
    respone['timeUsed']=63
    respone['totalCount']=len( items)
    respone['algorithmConstantVoList']=items

    return  jsonify( respone )


@bp.route('/vidicon/getAlgorithmList', methods=['GET','POST'])
@login_required
def getAlgorithmList():
    '''
    接口名称：获取算法服务器支持算法模型列表
    '''
    params = request.get_json()
    searchChoose = params.get("searchChoose",None)

    query = {}
    if searchChoose:
        query['algorithm_constant_name'] = {"$regex":searchChoose}

    my_db = ToMongo("wavedevice")
    algorithm_coll = my_db.get_col(WORK_FLOW_ALGORITHM_CONSTANT).find(query)
    items=[]
    for algorithm in algorithm_coll:
        items.append(algorithm['algorithm_constant_num'])
    response={}
    response['requestId']=uuid.uuid4().hex
    response['requestStatus']="SUCCESS"
    response['timeUsed']=40
    response['algorithmList']=items
    return jsonify(response)

@bp.route('/controltask/addControlTask', methods=['GET','POST'])
@login_required
def addControlTask():

    controlId = uuid.uuid1().hex
    params = request.get_json()
    mission_name=params.get('controlName',None)
    algorithm_constant_num=params.get('algorithmConstantNum',None)
    create_time=datetime.now()
    storageTime=int(params.get('storageTime',None))
    storageNum=int(params.get('storageNum',None))
    mission_start_time=params.get('missionStartTime',None)
    mission_end_time=params.get('missionEndTime',None)
    
    my_db = ToMongo('wavedevice')
    generate_log(request,db=my_db)

    error_response  = set_fail_result()
    success_response = set_success_result()

    control_name_list = my_db.get_keyvalues("odin_business_control_manage","control_name")
    if mission_name in control_name_list:
        error_response['errorCode'] = "CONTROL_NAME_EXIST"
        error_response['errorCodeDesc'] = "布控任务名称已存在"        
        return error_response

    item_control = {'control_id':controlId,'control_name':mission_name,'create_time':create_time,
                    'create_user':'admin','organization_id':'001611544223344645607','storage_time':storageTime,
                    'storage_num':storageNum,"device_sn":"HQDZKM6BAAJBC0174"}
    my_db.insert('odin_business_control_manage',item_control)

    item_mission = {"mission_start_time":mission_start_time,"mission_end_time":mission_end_time,"mission_id":controlId,"algorithm_id":algorithm_constant_num,'organization_id':'001611544223344645607'}
    my_db.insert(WORK_FLOW_MISSION,item_mission)

    success_response['controlId'] = controlId
    return  jsonify(success_response)


@bp.route('/controltask/addControlTaskPersonsGroup', methods=['GET','POST'])
@login_required
def addControlTaskPersonsGroup():
    '''
    接口描述：设置布控任务关联人物组
    状态：未完成
    '''
    params = request.get_json()
    accessToken = params.get('accessToken',None)
    controlID = params.get('controlId',None)
    personnelGroupIdList = params.get('personnelGroupIdList',None)
    my_db = ToMongo('wavedevice')
    generate_log(request,db=my_db)
    group_asso_col = my_db.get_col(WORK_FLOW_PERSONNEL_PERSONNELGROUP_ASSOCIATE)

    query = {"mission_id":controlID}
    my_db.delete(WORK_FLOW_MISSION_PERSONNELGROUP_ASSOCIATE,query,is_one=False)
    for groupid in personnelGroupIdList:
        item = {"personnel_group_id":groupid,"mission_id":controlID}
        my_db.insert(WORK_FLOW_MISSION_PERSONNELGROUP_ASSOCIATE,item)

    response = set_success_result()
    return  jsonify( response )

@bp.route('/controltask/addDeviceEquip', methods=['GET','POST'])
@login_required
def addDeviceEquip():
    '''
    接口描述：设置布控任务关联联控设备
    '''
    params = request.get_json()
    accessToken = params.get('accessToken',None)
    equipEntities = params.get('equipEntities',None)
    
    my_db = ToMongo('wavedevice')

    for equipEntity in equipEntities:
        equipType = equipEntity['equipType']
        channelNumber = equipEntity.get('channelNumber',None)
        missionId = equipEntity['missionId']
        equipIp = equipEntity.get('equipIp',None)
        equipPort = equipEntity.get('equipPort',None)
        
        resetDelayTime = equipEntity['resetDelayTime']
        equipids = equipEntity.get('equipId',None)
        equipName = equipEntity.get('equipName',None)
        remark = equipEntity.get('remark',None)
        control_equip_id = uuid.uuid4().hex
        item = {'control_equip_id':control_equip_id,
                'mission_id':missionId,
                'equip_type':equipType,
                'equip_name':equipName,
                'remark':remark,
                'equip_id':equipids,
                'equip_ip':equipIp,
                'equip_port':equipPort,
                'device_control_type':1,  # 网络控制器
                'channel_number':channelNumber,
                'reset_delay_time':resetDelayTime,
                'create_time':None,
                'create_user':None,
                'update_time':None,
                'update_user':None
                }
        my_db.insert('odin_device_equip',item)

    response=set_success_result()
    return  jsonify( response )

@bp.route('/controltask/addControlTaskPersons', methods=['GET','POST'])
@login_required
def addControlTaskPersons():
    '''
    接口描述：设置布控任务关联人物
    '''
    params = request.get_json()
    accessToken = params.get('accessToken')
    controlID = params.get('controlId')
    personnelIdList = params.get('personnelIdList')
    my_db = ToMongo('wavedevice')
    res = my_db.delete(WORK_FLOW_MISSION_PERSONNEL_ASSOCIATE,{"mission_id":controlID},is_one = False)
    for personid in personnelIdList:
        item = {"personnel_id":personid,"mission_id":controlID}
        my_db.insert(WORK_FLOW_MISSION_PERSONNEL_ASSOCIATE,item)

    response = set_success_result()
    return  jsonify( response )

@bp.route('/controltask/addControlTaskCameras', methods=['GET','POST'])
@login_required
def addControlTaskCameras():
    '''
    接口描述：设置布控任务关联摄像头
    '''
    controlID = request.json.get('controlId')
    deviceList = request.json.get('deviceList')
    my_db = ToMongo('wavedevice')
    generate_log(request,db=my_db)
    my_db.delete(WORK_FLOW_MISSION_DEVICE_ASSOCIATE,{"mission_id":controlID},is_one=False)  #删除旧的关联表
    for device in deviceList:
        item = {'mission_id':controlID,'device_id':device['deviceId'],'product_key':device['productKey']}
        my_db.insert(WORK_FLOW_MISSION_DEVICE_ASSOCIATE,item)

    response = set_success_result()
    return  jsonify( response )

@bp.route('/control/setMissionAssociateEmergency', methods=['GET','POST'])
@login_required
def setMissionAssociateEmergency():
    controlID = request.json.get('controlId')
    emergencyAudio=request.json.get('emergencyAudio')
    emergencyIntervalTime=request.json.get('emergencyIntervalTime')
    emergencyLevel=request.json.get('emergencyLevel')
    emergencyMusicCloseMethod=request.json.get('emergencyMusicCloseMethod')

    my_db = ToMongo('wavedevice')
    item = {'mission_type':0,'mission_status':0,
            'create_time':datetime.now(),    
            'emergency_audio':emergencyAudio,'emergency_interval_time':emergencyIntervalTime,
            'emergency_level':emergencyLevel,'emergency_music_close_method':emergencyMusicCloseMethod}
    
    my_db.update(WORK_FLOW_MISSION,{'mission_id':controlID},{'$set':item})
    
    response = set_success_result()
    # 往算法客户端socket发布控信息
    from algorith_server.AlgorithServer_v2 import SenderThread
    sender = SenderThread( current_app.app_context() )
    sender.send_reboot_message()
    return  jsonify(response)


@bp.route('/controltask/deleteControlTask', methods=['GET','POST'])
@login_required
def deleteControlTask():

    params = request.get_json()
    controlID = params.get('controlId',None) 
    check = params.get('check',None)  # 强制删除标志

    my_db = ToMongo('wavedevice')
    generate_log(request,db=my_db)
    my_db.delete(WORK_FLOW_MISSION,{'mission_id':controlID})               #删除布控任务
    my_db.delete(WORK_FLOW_MISSION_DEVICE_ASSOCIATE,{'mission_id':controlID},is_one=False)  #删除布控任务设备关联
    my_db.delete(WORK_FLOW_INSIGHT_MODEL_ALGORITHM_INSTANCE,{'mission_id':controlID},is_one=False)  #删除布控任务模型关联
    my_db.delete('odin_business_control_manage',{'control_id':controlID})     #删除布控任务

    my_db.delete(WORK_FLOW_MISSION_PERSONNEL_ASSOCIATE,{'mission_id':controlID})   #删除布控任务人员关联
    my_db.delete(WORK_FLOW_MISSION_PERSONNELGROUP_ASSOCIATE,{'mission_id':controlID})   #删除布控任务人员组关联

    my_db.delete('odin_device_equip',{'mission_id':controlID})   #删除布控任务人员组关联

    from algorith_server.AlgorithServer_v2 import SenderThread
    sender = SenderThread(context=[])
    sender.send_reboot_message()
 
    response = set_success_result()
    response['failedList']=[]
    return response


@bp.route('/controltask/queryControlTaskList', methods=['GET','POST'])
@login_required
def queryControlTaskList():
    '''
    接口说明：根据任务id查询任务关联的数据
    '''
    params = request.get_json()
    page = params.get('page',None) 
    pageSize = params.get('pageSize',None)
    sortBy = params.get('sortBy',None)
    sortType = params.get('sortType',None)
    algorithmConstantName = params.get('algorithmConstantName',None)   #关联识别模型
    cameraName = params.get('cameraName',None)                         #关联摄像机
    controlName = params.get('controlName',None)                       #布控任务名称

    my_db = ToMongo('wavedevice')
    generate_log(request,db=my_db)
    
    algorithm_col = my_db.get_col(WORK_FLOW_INSIGHT_MODEL_ALGORITHM_INSTANCE)
    device_col = my_db.get_col(WORK_FLOW_MISSION_DEVICE_ASSOCIATE)
    mission_col = workflow_mission_collection(my_db)
    person_col = my_db.get_col(WORK_FLOW_MISSION_PERSONNEL_ASSOCIATE)
    mission_group_col = my_db.get_col(WORK_FLOW_MISSION_PERSONNELGROUP_ASSOCIATE)
    person_group_col = my_db.get_col(WORK_FLOW_PERSONNEL_PERSONNELGROUP_ASSOCIATE)
    cam_col = my_db.get_col('odin_device_camera_edit')
    constant_col = my_db.get_col(WORK_FLOW_ALGORITHM_CONSTANT)
    parm1 = cameraName if cameraName else ''
    parm2 = algorithmConstantName if algorithmConstantName else ''

    query = {}
    if controlName:
        query['control_name'] = {"$regex":controlName}
    if parm1 or parm2:
        list1 = find_asso_cam(cam_col,device_col,parm1)
        list2 = find_asso_alg(constant_col,algorithm_col,parm2)
        asso_mission_list = list(set(list1).intersection(set(list2)))
        query['control_id'] = {"$in":asso_mission_list}
        
    num = (page-1)*pageSize
    control_col = my_db.get_col('odin_business_control_manage').find(query).sort("control_name")
    control_items = control_col.skip(num).limit(pageSize)

    controlInfoVoList = []
    for control_item in control_items:
        item = {}
        item['controlId'] = control_item['control_id']
        item['controlName'] = control_item['control_name']
        item['createTime'] = int(control_item['create_time'].timestamp())*1000 if control_item['create_time'] else None
        item['storageNum'] = control_item['storage_num']
        item['storageTime'] = control_item['storage_time']

        algorithm_associate = algorithm_col.find({'mission_id':item['controlId']}) 
        item['algorithmCount'] = algorithm_associate.count()  #绑定的算法数
        
        device_associate = device_col.find({'mission_id':item['controlId']})
        item['deviceCount'] = device_associate.count()  #绑定的摄像头数
        item['deviceIdList'] = [] 
        item['deviceList'] = []
        for device_item in device_associate:
            ditem={}
            ditem['deviceId'] = device_item['device_id']
            ditem['missionId'] = device_item['mission_id']
            ditem['productKey'] = device_item['product_key']
            item['deviceIdList'].append(ditem['deviceId'])
            item['deviceList'].append(ditem)

        misssion_item = mission_col.find_one({'mission_id':item['controlId']})
        item['emergencyAudio'] = misssion_item['emergency_audio']

        item['instanceList']=[]
        for algorithm_item in algorithm_associate:
            alitem = {}
            alitem['algorithmConstantNum'] = algorithm_item['algorithm_constant_num']
            alitem['controlId'] = item['controlId']
            alitem['createTime'] = int(algorithm_item['create_time'].timestamp()) if control_item['create_time'] else None
            alitem['instanceId'] = algorithm_item['instance_id']
            alitem['isUse'] = algorithm_item['is_use']
            alitem['missionId'] = item['controlId']
            alitem['organizationId'] = algorithm_item['organization_id']
            item['instanceList'].append(alitem)

        item['missionEndTime'] = "[{\"time\":\"00:00:00-23:59:59\"}]"
        item['missionStartTime'] = "[{\"time\":\"00:00:00-23:59:59\"}]"
        item['missionStatus'] = misssion_item['mission_status']

        query = {'mission_id':item['controlId']}
        personid_list = person_col.distinct('personnel_id',query)
        asso_groups = mission_group_col.distinct('personnel_group_id',query)

        if asso_groups:
            query_asso_persons = {'personnel_group_id':{'$in':asso_groups}}
            asso_persons = person_group_col.distinct('personnel_id',query_asso_persons)
            personid_list+=asso_persons

        item['personCount'] = len(set(personid_list))
        item['personnelList'] = []

        controlInfoVoList.append(item)

    response = set_success_result()
    response['controlInfoVoList'] = controlInfoVoList
    response['page']=page
    response['pageSize']=pageSize
    response['totalCount']=control_col.count()
    
    return response


@bp.route('/controltask/modifyControlTask', methods=['GET','POST'])
@login_required
def modifyControlTask():
    '''
    接口说明：修改布控任务
    '''

    params = request.get_json()
    algorithmConstantNum = params.get('algorithmConstantNum',None) 
    controlName = params.get('controlName',None)
    controlTaskId = params.get('controlTaskId',None)
    emergencyAudio = params.get('emergencyAudio',None)
    emergencyIntervalTime = params.get('emergencyIntervalTime',None)
    emergencyLevel = params.get('emergencyLevel',None)
    emergencyMusicCloseMethod = params.get('emergencyMusicCloseMethod',None)
    missionEndTime = params.get('missionEndTime',None)
    missionStartTime = params.get('missionStartTime',None)
    storageNum = params.get('storageNum',None)
    storageTime = params.get('storageTime',None)
    equipEntities = params.get('equipEntities',None)

    my_db = ToMongo('wavedevice')
    mission_col = workflow_mission_collection(my_db)
    generate_log(request,db=my_db)
    mission_update = {"emergency_audio":emergencyAudio,"emergency_interval_time":emergencyIntervalTime,"emergency_level":emergencyLevel,"emergency_music_close_method":emergencyMusicCloseMethod,
                    "mission_start_time":missionStartTime,"mission_end_time":missionEndTime,
                    "algorithm_id":algorithmConstantNum
                    }
    control_update = {"storage_time":int(storageTime),"storage_num":int(storageNum),"control_name":controlName}
    my_db.update(WORK_FLOW_MISSION,
                {'mission_id':controlTaskId},
                {'$set':mission_update})
    my_db.update('odin_business_control_manage',
                {'control_id':controlTaskId},
                {'$set':control_update})

    query = {"mission_id":controlTaskId}
    my_db.delete('odin_device_equip',query,is_one=False)
    if  equipEntities:
        for item in equipEntities:
            equip_item = database_to_dict(item,equip_web,equip_database)
            equip_item['mission_id'] = controlTaskId
            equip_item['equip_type'] = int(equip_item['equip_type'])
            my_db.insert('odin_device_equip',equip_item)
    
    mission_item = mission_col.find_one(query)
    mission_status = mission_item['mission_status'] if mission_item else 0

    if mission_status == 0:
        #任务属于下发状态，则重新下发布控任务
        from algorith_server.AlgorithServer_v2 import SenderThread
        sender = SenderThread( current_app.app_context() )
        sender.send_reboot_message()
    
    response = set_success_result()  
    return response


@bp.route('/controltask/addControlTaskInsightModelAlgorithm', methods=['GET','POST'])
#@login_required
def addControlTaskInsightModelAlgorithm():
    '''
    接口说明：修改布控任务关联的算法模型，包含增加修改删除
    '''

    params = request.get_json()
    controlId = params.get('controlId',None)   
    instanceList = params.get('instanceList',None)

    my_db = ToMongo('wavedevice')
    generate_log(request,db=my_db)
    old_items = my_db.get_col(WORK_FLOW_INSIGHT_MODEL_ALGORITHM_INSTANCE).find({'mission_id':controlId})
    organizationId = find_workflow_mission_by_mission_id(my_db, controlId)['organization_id']

    old_algs = []  
    if old_items.count() != 0:    
        for item in old_items:
            old_algs.append(item['algorithm_service_num'])     #获取旧的算法列表
    
    new_algs = []
    for item in instanceList:
        new_algs.append(item['algorithmServiceNum'])       #新的算法列表
         

    for alg in old_algs:
        if alg not in new_algs:
            my_db.delete(WORK_FLOW_INSIGHT_MODEL_ALGORITHM_INSTANCE,
                        {'mission_id':controlId,'algorithm_service_num':alg})      #如果旧的算法不在了，执行删除


    for ins in instanceList:
        if ins['algorithmServiceNum'] in old_algs:                   #修改旧的算法设置

            item={}
            item['algorithm_constant_num']=ins['algorithmConstantNum']
            item['create_time']=datetime.fromtimestamp(int(ins['createTime']/1000))
            #item['instance_colour']=ins['instanceColour']
            item['instance_id']=ins['instanceId']
            item['is_use']=int(ins['isUse'])
            item['mission_id']=ins['controlId']
            item['organization_id']=ins['organizationId']

            item['instance_path']=None
            item['instance_group']=None
            item['discern_type']=None
            item['last_time']=None
            item['interval_time']=ins['emergencyIntervalTime']
            item['model_id']=None
            item['time_range_num']=None
            item['count_limit']=None            
            item['rate_num'] = None

            item['algorithm_service_num'] = ins['algorithmServiceNum']

            my_db.update(WORK_FLOW_INSIGHT_MODEL_ALGORITHM_INSTANCE,{'instance_id':ins['instanceId']},{'$set':item})

        else:                                             #绑定新的算法
            item={}
            item['algorithm_constant_num']=ins['algorithmConstantNum']
            item['create_time']=  datetime.now()
            #item['instance_colour']=ins['instanceColour']
            item['instance_id']= uuid.uuid4().hex
            item['is_use']=int(ins['isUse'])
            item['mission_id']=controlId
            item['organization_id']=organizationId

            item['instance_path']=None
            item['instance_group']=None
            item['discern_type']=None
            item['last_time']=None
            item['interval_time']=ins['emergencyIntervalTime']
            item['model_id']=None
            item['time_range_num']=None
            item['count_limit']=None          
            item['rate_num'] = None

            item['algorithm_service_num'] = ins['algorithmServiceNum']

            my_db.insert(WORK_FLOW_INSIGHT_MODEL_ALGORITHM_INSTANCE,item)

   
    response = set_success_result()  
    return response


@bp.route('/controltask/modifyControlTaskIsActive', methods=['GET','POST'])
@login_required
def modifyControlTaskIsActive():

    params = request.get_json()
    controlID = params.get('controlId',None) 
    switchOperation = params.get('switchOperation',None)  # 布控开关 0关1开

    my_db = ToMongo('wavedevice')
    generate_log(request,db=my_db)
    item = find_workflow_mission_by_mission_id(my_db, controlID)

    
    if  item:
        my_db.update(WORK_FLOW_MISSION,{'mission_id':controlID},{'$set':{'mission_status':switchOperation}})    #数据库调整为未下发状态

    
    from algorith_server.AlgorithServer_v2 import SenderThread
    sender = SenderThread( current_app.app_context() )
    sender.send_reboot_message()
 
    response=set_success_result()
    return response

@bp.route('/control/emergencyFalseAlarmStatus', methods=['GET','POST'])
@login_required
def emergencyFalseAlarmStatus():
    '''
    接口描述:更新误报标识
    '''
    params = request.get_json()
    emergency_record_id = params.get('emergencyRecordId',None) 
    falseAlarmStatus = params.get('falseAlarmStatus',None) 
    item = {'is_wrong':int(falseAlarmStatus)}

    my_db = ToMongo('wavedevice')
    query = {'emergency_record_id' : emergency_record_id}
    my_db.update('odin_business_emergency_record',query,{'$set':item})

    response=set_success_result()
    return response

@bp.route('/control/emergencyMusicCloseStatus', methods=['GET','POST'])
@login_required
def emergencyMusicCloseStatus():
    '''
    接口描述:关闭音频状态
    状态:未完成
    '''

    params = request.get_json()
    emergency_record_id = params.get('emergencyRecordId',None) 

 
    response=set_success_result()
    return response

@bp.route('/control/getRotationTime', methods=['GET','POST'])
@login_required
def getRotationTime():
    '''
    接口描述:获取轮询时间间隔
    '''

    my_db = ToMongo('wavedevice')
    rotation_item = my_db.get_col('odin_device_rotation_time').find_one()
    
    if rotation_item: 
        response = set_success_result()
        response['rotationTime'] = rotation_item['rotation_time']        
        return response

@bp.route('/control/setRotationTime', methods=['GET','POST'])
@login_required
def setRotationTime():
    '''
    接口描述:设置轮询时间间隔
    '''
    params = request.get_json()
    rotationTime = params.get("rotationTime",None)
    my_db = ToMongo('wavedevice')
    now = datetime.now()
    rotation_item = my_db.get_col("odin_device_rotation_time").find_one()
    if rotation_item:
        id = rotation_item['id']
    
    my_db.update("odin_device_rotation_time",{},{"$set":{"rotation_time":rotationTime}})

 
    response = set_success_result()
    return response

@bp.route('/control/queryControlTaskList', methods=['GET','POST'])
@login_required
def queryControlTaskList2():
    '''
    接口说明：根据任务id查询任务关联的数据
    '''

    params = request.get_json()
    accessToken = params.get('accessToken',None) 
    controlIds = params.get('controlIds',None)
    

    my_db = ToMongo('wavedevice')
    generate_log(request,db=my_db)
    query = {"control_id":{"$in":controlIds}} 
    control_col = my_db.get_col('odin_business_control_manage').find(query)
    algorithm_col = my_db.get_col(WORK_FLOW_INSIGHT_MODEL_ALGORITHM_INSTANCE)
    device_col = my_db.get_col(WORK_FLOW_MISSION_DEVICE_ASSOCIATE)
    mission_col = workflow_mission_collection(my_db)
    person_col = my_db.get_col(WORK_FLOW_MISSION_PERSONNEL_ASSOCIATE)
    cam_col = my_db.get_col('odin_device_camera_edit')
    constant_col = my_db.get_col(WORK_FLOW_ALGORITHM_CONSTANT)

    controlInfoVoList = []
    for control_item in control_col:
        item = {}
        item['controlId'] = control_item['control_id']
        item['controlName'] = control_item['control_name']
        item['createTime'] = int(control_item['create_time'].timestamp())*1000 if control_item['create_time'] else None
        item['storageNum'] = control_item['storage_num']
        item['storageTime'] = control_item['storage_time']

        algorithm_associate = algorithm_col.find({'mission_id':item['controlId']}) 
        item['algorithmCount'] = algorithm_associate.count()  #绑定的算法数
        
        device_associate = device_col.find({'mission_id':item['controlId']})
        item['deviceCount'] = device_associate.count()  #绑定的摄像头数
        item['deviceIdList'] = [] 
        item['deviceList'] = []
        for device_item in device_associate:
            ditem={}
            ditem['deviceId'] = device_item['device_id']
            ditem['missionId'] = device_item['mission_id']
            ditem['productKey'] = device_item['product_key']
            item['deviceIdList'].append(ditem['deviceId'])
            item['deviceList'].append(ditem)

        misssion_item = mission_col.find_one({'mission_id':item['controlId']})
        item['emergencyAudio'] = misssion_item['emergency_audio']
        item['emergencyIntervalTime'] = misssion_item['emergency_interval_time']
        item['emergencyLevel'] = str(misssion_item['emergency_level'])

        item['instanceList']=[]
        for algorithm_item in algorithm_associate:
            alitem = {}
            alitem['algorithmConstantNum'] = algorithm_item['algorithm_constant_num']
            alitem['controlId'] = item['controlId']
            alitem['createTime'] = int(algorithm_item['create_time'].timestamp()) if control_item['create_time'] else None
           # alitem['instanceColour'] = algorithm_item['instance_colour']
            alitem['instanceId'] = algorithm_item['instance_id']
            alitem['isUse'] = algorithm_item['is_use']
            alitem['missionId'] = item['controlId']
            alitem['organizationId'] = algorithm_item['organization_id']
            item['instanceList'].append(alitem)

        item['missionStartTime'] = misssion_item['mission_start_time']
        item['missionEndTime'] = misssion_item['mission_end_time']
        item['missionStatus'] = misssion_item['mission_status']

        item['personCount'] = person_col.find({'mission_id':item['controlId']}).count()
        item['personnelList'] = []

        controlInfoVoList.append(item)

    response = set_success_result()
    response['list'] = controlInfoVoList   
    return response


@bp.route('/control/queryRotationOnOff', methods=['GET','POST'])
@login_required
def queryRotationOnOff():
    '''
    接口描述：查询轮播开关
    '''
    params = request.get_json()
    my_db = ToMongo('wavedevice')
    rotation_col = my_db.get_col("odin_device_rotation_time").find()
    if rotation_col.count() !=0:
        rotation_item = rotation_col[0]
        rotation_onoff = str(rotation_item['rotation_on_off'])
    else:
        rotation_onoff = "1"   #默认开
    response = set_success_result()
    response['rotationOnOff'] = rotation_onoff
    return  jsonify( response )

@bp.route('/control/setRotationOnOff', methods=['GET','POST'])
@login_required
def setRotationOnOff():
    '''
    接口描述：设置轮播开关
    '''
    params = request.get_json()
    rotationOnOff = params.get('rotationOnOff',None)
    my_db = ToMongo('wavedevice')
    modify_time = datetime.now()
    my_db.update("odin_device_rotation_time",{"id":1},{"$set":{"rotation_on_off":rotationOnOff,"modify_time":modify_time}})

    response=set_success_result()
    return  jsonify( response )

@bp.route('/control/exportEmergencyItemsByIds', methods=['GET','POST'])
@login_required
def exportEmergencyItemsByIds():
    '''
    接口描述:导出告警纪录-告警图画框
    '''
    params = request.get_json()
    ids = params.get('ids',None)
    startNum = params.get('startNum',None)
    endNum = params.get('endNum',None)
    derive_type = params.get('type',None)  #导出类型   all part select
    begin_time = params.get('beginTime',None)
    controlName = params.get('controlName',None)
    end_time = params.get('endTime',None)
    falseAlarmStatus = params.get('falseAlarmStatus',None)
    model_path = params.get('modelPath',None)
    modelName = params.get('modelName',None)
    page = params.get('page',None)
    pageSize = params.get('pageSize',None)
    searchChoose = params.get('searchChoose',None)
    sortBy = params.get('sortBy',None)
    sortType = params.get('sortType',None)


    my_db = ToMongo('wavedevice') 

    all_zip = io.BytesIO()
    zf = zipfile.ZipFile(all_zip,'w')


    #创建好导出xls的表头
    book = xlwt.Workbook(encoding='utf-8',style_compression=0)
    now = datetime.now()
    timestr = now.strftime("%Y%m%d%H%M%S")
    xls_name = "导出告警纪录-%s"%timestr
    sheet = book.add_sheet('xls_name',cell_overwrite_ok=True)
    col = ("告警时间","识别模型","布控任务","摄像机名称","图片路径")
    for i in range(5):
        sheet.write(0,i,col[i])


    #获取告警事件的数据，写入告警图片
    emergency_record_col = my_db.get_col('odin_business_emergency_record')
    emergency_record_detail_col = my_db.get_col('odin_business_emergency_record_detail_info')
    datalist = [] 
    if derive_type == "select":
        query = {"emergency_record_id" :{"$in":ids}}
        emergency_items = emergency_record_col.find(query)
    else:
        quary = {}
        if  begin_time and  end_time:
            begin_time = int(str(begin_time)[0:10])
            end_time = int(str(end_time)[0:10])
            begin_time = datetime.fromtimestamp(begin_time)
            begin_time = begin_time.strftime("%Y-%m-%d %H:%M:%S")
            end_time = datetime.fromtimestamp(end_time)
            end_time = end_time.strftime("%Y-%m-%d %H:%M:%S")
            quary['emergency_time'] = {"$gte" :begin_time ,"$lte" :end_time}
        if model_path:
            quary['model_path'] = model_path
        if falseAlarmStatus and falseAlarmStatus != "":
            quary['is_wrong'] = int(falseAlarmStatus)
        if searchChoose and searchChoose != "":
            quary['$or'] = [{'emergency_position':{'$regex':searchChoose}},{'device_name':{'$regex':searchChoose}}]
        if controlName:
            control_item = my_db.get_col("odin_business_control_manage").find_one({'control_name':controlName})
            if control_item:
                quary['mission_id'] = control_item['control_id']
        emergency_items = emergency_record_col.find(quary).sort("emergency_time",-1)
        if derive_type == "part":
            emergency_items = emergency_items[startNum-1:endNum]

    for emergency_item in emergency_items:
        record_id = emergency_item['emergency_record_id']
        emergency_time = emergency_item['emergency_time']
        model_path = emergency_item['model_path']
        control_name = emergency_item['control_name']
        device_name = emergency_item['device_name']
        sub_source_id = emergency_item['sub_source_id']
        emeergency_date = emergency_item['create_time'].strftime("%Y%m%d")  

        detail_item = emergency_record_detail_col.find_one({'emergency_record_id':record_id})
        extra_info = detail_item['emergency_image_extra_info'] 
        alg_num = detail_item['algorithm_constant_num']  

        imgpath = EMERGENCY_IMG_PATH + emeergency_date + '/' + sub_source_id + '.jpg'
        img_zf_path = 'img/' + sub_source_id + '_' + alg_num + '.jpg'
        item = [emergency_time,model_path,control_name,device_name,"查看图片",img_zf_path]
        datalist.append(item)

        imgdata = draw_frame(imgpath,extra_info,alg_num,type=0,model_path=model_path)

        zf.writestr(img_zf_path,imgdata)

    #告警事件写入xls
    num = len(datalist)
    for i in range(num):
        data = datalist[i]
        for j in range(4):
            sheet.write(i+1,j,data[j])
        link = data[5]
        sheet.write(i+1,4,xlwt.Formula('HYPERLINK("%s";"查看图片")'%link))

    xls_file = xls_name + ".xls"
    xls_output = io.BytesIO()
    book.save(xls_output)
    zf.writestr(xls_file,xls_output.getvalue())

    zf.close()
    all_zip.seek(0)
    dl_name = xls_name + '.zip'
    return send_file(all_zip, attachment_filename=dl_name, as_attachment=True)

@bp.route('/control/exportEmergencyItemsByIds2', methods=['GET','POST'])
@login_required
def exportEmergencyItemsByIds_old():
    '''
    接口描述:导出告警纪录-告警图不画框
    '''
    params = request.get_json()
    ids = params.get('ids',None)
    startNum = params.get('startNum',None)
    endNum = params.get('endNum',None)
    derive_type = params.get('type',None)  #导出类型   all part select
    begin_time = params.get('beginTime',None)
    controlName = params.get('controlName',None)
    end_time = params.get('endTime',None)
    falseAlarmStatus = params.get('falseAlarmStatus',None)
    model_path = params.get('modelPath',None)
    modelName = params.get('modelName',None)
    page = params.get('page',None)
    pageSize = params.get('pageSize',None)
    searchChoose = params.get('searchChoose',None)
    sortBy = params.get('sortBy',None)
    sortType = params.get('sortType',None)


    my_db = ToMongo('wavedevice') 

    all_zip = io.BytesIO()
    zf = zipfile.ZipFile(all_zip,'w')


    #创建好导出xls的表头
    book = xlwt.Workbook(encoding='utf-8',style_compression=0)
    now = datetime.now()
    timestr = now.strftime("%Y%m%d%H%M%S")
    xls_name = "导出告警纪录-%s"%timestr
    sheet = book.add_sheet('xls_name',cell_overwrite_ok=True)
    col = ("告警时间","识别模型","布控任务","摄像机名称","图片路径")
    for i in range(5):
        sheet.write(0,i,col[i])


    #获取告警事件的数据，写入告警图片
    emergency_record_col = my_db.get_col('odin_business_emergency_record')
    emergency_record_detail_col = my_db.get_col('odin_business_emergency_record_detail_info')
    datalist = [] 
    if derive_type == "select":
        query = {"emergency_record_id" :{"$in":ids}}
        emergency_items = emergency_record_col.find(query)
    else:
        quary = {}
        if  begin_time and  end_time:
            begin_time = int(str(begin_time)[0:10])
            end_time = int(str(end_time)[0:10])
            begin_time = datetime.fromtimestamp(begin_time)
            begin_time = begin_time.strftime("%Y-%m-%d %H:%M:%S")
            end_time = datetime.fromtimestamp(end_time)
            end_time = end_time.strftime("%Y-%m-%d %H:%M:%S")
            quary['emergency_time'] = {"$gte" :begin_time ,"$lte" :end_time}
        if model_path:
            quary['model_path'] = model_path
        if falseAlarmStatus and falseAlarmStatus != "":
            quary['is_wrong'] = int(falseAlarmStatus)
        if searchChoose and searchChoose != "":
            quary['$or'] = [{'emergency_position':{'$regex':searchChoose}},{'device_name':{'$regex':searchChoose}}]
        if controlName:
            control_item = my_db.get_col("odin_business_control_manage").find_one({'control_name':controlName})
            if control_item:
                quary['mission_id'] = control_item['control_id']
        emergency_items = emergency_record_col.find(quary).sort("emergency_time",-1)
        if derive_type == "part":
            emergency_items = emergency_items[startNum-1:endNum]

    img_subid_list = []
    for emergency_item in emergency_items:
        emergency_time = emergency_item['emergency_time']
        model_path = emergency_item['model_path']
        control_name = emergency_item['control_name']
        device_name = emergency_item['device_name']
        sub_source_id = emergency_item['sub_source_id']
        emeergency_date = emergency_item['create_time'].strftime("%Y%m%d")  

        imgpath = EMERGENCY_IMG_PATH + emeergency_date + '/' + sub_source_id + '.jpg'
        img_zf_path = 'img/' + sub_source_id + '.jpg'
        item = [emergency_time,model_path,control_name,device_name,"查看图片",img_zf_path]
        datalist.append(item)

        if sub_source_id in img_subid_list:
            continue
        else:
            fp_img = open(imgpath,"rb")
            zf.writestr(img_zf_path,fp_img.read())
            img_subid_list.append(sub_source_id)

    #告警事件写入xls
    num = len(datalist)
    for i in range(num):
        data = datalist[i]
        for j in range(4):
            sheet.write(i+1,j,data[j])
        link = data[5]
        sheet.write(i+1,4,xlwt.Formula('HYPERLINK("%s";"查看图片")'%link))

    xls_file = xls_name + ".xls"
    xls_output = io.BytesIO()
    book.save(xls_output)
    zf.writestr(xls_file,xls_output.getvalue())

    zf.close()
    all_zip.seek(0)
    dl_name = xls_name + '.zip'
    return send_file(all_zip, attachment_filename=dl_name, as_attachment=True)
    
@bp.route('/control/checkExportEmergencyItemsByIds', methods=['GET','POST'])
@login_required
def checkExportEmergencyItemsByIds():
    
    params = request.get_json()
    ids = params.get('ids',None)
    startNum = params.get('startNum',None)
    endNum = params.get('endNum',None)
    derive_type = params.get('type',None)  #导出类型   all part select
    begin_time = params.get('beginTime',None)
    controlName = params.get('controlName',None)
    end_time = params.get('endTime',None)
    falseAlarmStatus = params.get('falseAlarmStatus',None)
    model_path = params.get('modelPath',None)
    modelName = params.get('modelName',None)
    page = params.get('page',None)
    pageSize = params.get('pageSize',None)
    searchChoose = params.get('searchChoose',None)
    sortBy = params.get('sortBy',None)
    sortType = params.get('sortType',None)

    error_response = set_fail_result()
    error_response['errorCodeDesc'] = "请选择需要删除的警告记录"

    if derive_type == "select" and ids == []:
        return error_response

    response = set_success_result()
    return  jsonify( response )

@bp.route('/controltask/queryItcServer', methods=['GET','POST'])
@login_required
def queryItcServer():
    '''
    查询itc服务器信息
    '''
    my_db = ToMongo('wavedevice')
    itc_col = my_db.get_col('odin_device_itc_server')
    itc_item = itc_col.find_one()

    lings_col = my_db.get_col('odin_device_lings_server')
    lins_item = lings_col.find_one()

    if itc_item:
        itc_entity = {'soundType':'1',
                      'itcServerId':itc_item['itc_server_id'],   
                      'itcServerPort':itc_item['itc_server_port'],  
                      'itcServerAddress':itc_item['itc_server_address'],  
                      'itcServerPassword':itc_item['itc_server_password'],  
                      'itcServerAccount':itc_item['itc_server_account']}
    else:
        itc_entity = {'soundType':'1',
                      'itcServerId':None,   
                      'itcServerPort':None,  
                      'itcServerAddress':None,  
                      'itcServerPassword':None,  
                      'itcServerAccount':None}

    if lins_item:
        lings_entity = {'soundType':'2',
                        'itcServerId':lins_item['lings_server_id'],   
                        'itcServerPort':lins_item['lings_server_port'],  
                        'itcServerAddress':lins_item['lings_server_address'],  
                        'itcServerPassword':lins_item['lings_server_password'],  
                        'itcServerAccount':lins_item['lings_server_account']}
    else:
        lings_entity = {'soundType':'2',
                        'itcServerId':None,   
                        'itcServerPort':None,  
                        'itcServerAddress':None,  
                        'itcServerPassword':None,  
                        'itcServerAccount':None}    

    response_data = set_success_result()
    response_data['entity'] = []
    response_data['entity'].append(itc_entity)
    response_data['entity'].append(lings_entity)

    return jsonify(response_data)

@bp.route('/controltask/addItcServer', methods=['GET','POST'])
@login_required
def addItcServer():
    '''
    新增或修改itc服务器信息
    '''
    params = request.get_json()
    itcServerAccount = params.get('itcServerAccount',None)
    itcServerAddress = params.get('itcServerAddress',None)
    itcServerId = params.get('itcServerId',None)
    itcServerPassword = params.get('itcServerPassword',None)
    itcServerPort = params.get('itcServerPort',None)
    soundType = params.get('soundType',None)

    my_db = ToMongo('wavedevice')
    
    if not itcServerId:
        itcServerId = uuid.uuid4().hex

    if soundType == '1':
        #itc音响

        item = {}
        item['itc_server_account'] = itcServerAccount
        item['itc_server_address'] = itcServerAddress
        item['itc_server_id'] = itcServerId
        item['itc_server_password'] = itcServerPassword
        item['itc_server_port'] = itcServerPort

        my_db.update('odin_device_itc_server',{},{'$set':item})

    elif soundType == '2':
        #菱声音响

        item = {}
        item['lings_server_account'] = itcServerAccount
        item['lings_server_address'] = itcServerAddress
        item['lings_server_id'] = itcServerId
        item['lings_server_password'] = itcServerPassword
        item['lings_server_port'] = itcServerPort
        item['lings_tts_port'] = 10008  #默认tts端口

        my_db.update('odin_device_lings_server',{},{'$set':item})
        
    response_data = set_success_result()
    return jsonify(response_data)

@bp.route('/controltask/testItcServer', methods=['GET','POST'])
@login_required
def testItcServer():
    '''
    测试itc服务器
    '''
    params = request.get_json()
    itcServerAccount = params.get('itcServerAccount',None)
    itcServerAddress = params.get('itcServerAddress',None)
    itcServerPassword = params.get('itcServerPassword',None)
    itcServerPort = params.get('itcServerPort',None)
    soundType = params.get('soundType',None)
    
    error_response = set_fail_result()
    try:

        if soundType == '1':
            #itc音响
            server_url = 'http://%s:%s'%(itcServerAddress,itcServerPort)
            itc_instance = VoiceBoxUtils(server_url,itcServerAccount,itcServerPassword,volume=70)
            response = itc_instance.login()
            result = response.get('result')
            if result != 200:
                error_response['errorCodeDesc'] = "音响服务器登录失败"
                return error_response
        elif soundType == '2':
            #菱声音响
            #itc音响
            server_url = 'http://%s:%s'%(itcServerAddress,itcServerPort)
            lings_instance = LingsSound(client_url=None,server_url=server_url,sound_no=None,volume=70)
            response = lings_instance.login(account=itcServerAccount,password=itcServerPassword)
            keys = response.keys()
            if "user" not in keys:
                error_response['errorCodeDesc'] = "音响服务器登录失败"
                return error_response
    
    except Exception as e:
        mainlogger.info("*****音响服务器无法访问,Error :%s"%e)
        error_response['errorCodeDesc'] = "音响服务器无法访问"
        return error_response
    
    response_data = set_success_result()
    return jsonify(response_data)

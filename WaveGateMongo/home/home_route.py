import json

from flask import Blueprint, request,jsonify
from Utils.db import ToMongo
import uuid
from datetime import datetime,timedelta
import calendar
from system.system_misc import database_to_dict
from system.sys_config import advise_database,advise_web
from Utils.jwt_verify import *

import Utils.edgebox_repo  # noqa: F401
from edgebox_db.mongo_collections import (
    WORK_FLOW_MISSION,
)

bp = Blueprint("home",__name__, url_prefix='/net-web')
@bp.route('/control/getMisstionCount', methods=['GET','POST'])
@login_required
def getMisstionCount():
    '''
    接口说明：获取任务统计
    '''
    my_db = ToMongo('wavedevice')
    mission_coll = my_db.get_col(WORK_FLOW_MISSION)
    result = mission_coll.aggregate([{'$match':{}},{'$group':{'_id':'$mission_status','count':{'$sum':1}}}
                           ,{'$project':{'status':'$_id',"_id":0,"count": 1}}])
    missionTotal = 0
    missonActiveSize = 0
    for item in result:
        status = item['status']
        num = item['count']
        missionTotal += num
        if status == 0:
            missonActiveSize = num

    response_data = {}
    response_data['missionTotal'] = missionTotal
    response_data['missonActiveSize'] = missonActiveSize
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 56
    return jsonify(response_data)



@bp.route('/advise/getAdviseRecord', methods=['GET','POST'])
@login_required
def getAdviseRecord():
    '''
    接口说明：获取通知数据列表
    '''
    params = request.get_json()
    accessToken = params.get("accessToken",None)#源类型 1业务 2设备
    adviseContent = params.get("adviseContent",None)#消息类容关键词
    adviseType = params.get("adviseType",None) #通知类型
    adviseStatus = params.get("adviseStatus",None)# 未读/已读
    sourceType = params.get("sourceType",None)  

    page = params.get("page",None)
    pageSize = params.get("pageSize",None)
    if page <= 0:
        page=1
    try:
        num = (page-1)*pageSize
    except:
        num = 0
    sortBy = params.get("sortBy",None)
    sortType = params.get("sortType",None)

    query = {}
    if adviseType:
        query['advise_type'] = adviseType
    if adviseStatus != "" and adviseStatus != 2:
        query['advise_status'] = adviseStatus
    # if sourceType:
    #     query['source_type'] = sourceType
    if adviseContent:
        query['advise_content'] = {"$regex":adviseContent}

    my_db = ToMongo('wavedevice')
    advise_info_col = my_db.get_col('odin_advise_info')
    items = advise_info_col.find(query).sort('birth_time',-1)
    advise_items = items.skip(num).limit(pageSize)
    
    emergencyList = []
    for advise_item in advise_items:
        item = database_to_dict(advise_item,advise_database,advise_web)
        item['createTime'] = item['createTime'].strftime('%Y-%m-%d %H:%M:%S.%f') if item['createTime'] else None
        emergencyList.append(item)

    response_data = {}
    response_data['emergencyList'] = emergencyList
    response_data['pageSize'] = pageSize
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['start'] = 1
    response_data['timeUsed'] = 8
    response_data['totalCount'] = items.count()
    return response_data

@bp.route('/advise/getAdviseStatistic', methods=['GET','POST'])
@login_required
def getAdviseStatistic():
    '''
    接口注释：通知消息按照类型分类
    '''
    
    my_db = ToMongo('wavedevice')
    advise_coll = my_db.get_col('odin_advise_info')
    advise_types = advise_coll.distinct('advise_type')


    advise_list = []
    for iter in advise_types:
        item = {}
        num = advise_coll.find({'advise_type':iter}).count()
        item['adviseType'] = iter
        item['size'] = num
        item['organizationId'] = None
        advise_list.append(item)

    response_data = {}
    response_data['adviseInfoQueryCountVoList'] = advise_list
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 18
    return jsonify(response_data)

@bp.route('/advise/batchUpdateAdviseToAlreadyRead', methods=['GET','POST'])
@login_required
def batchUpdateAdviseToAlreadyRead():
    '''
    消息管理-批量消息已读
    '''
    
    params = request.get_json()
    accessToken = params.get("accessToken",None)
    adviseIdList = params.get("adviseIdList",None)

    my_db = ToMongo('wavedevice')
    query = {"advise_id":{"$in":adviseIdList}}
    item = {"advise_status":1}
    my_db.update('odin_advise_info',query,{"$set":item},is_one=False)    

    response_data = {}
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 8
    return response_data

@bp.route('/advise/updateAdviseStatus', methods=['GET','POST'])
@login_required
def updateAdviseStatus():
    
    params = request.get_json()
    accessToken = params.get("accessToken",None)
    adviseId = params.get("adviseId",None)

    my_db = ToMongo('wavedevice')
    query = {"advise_id":adviseId}
    item = {"advise_status":1}
    my_db.update('odin_advise_info',query,{"$set":item})    

    response_data = {}
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 8
    return response_data

@bp.route('/advise/deleteAdviseInfo', methods=['GET','POST'])
@login_required
def deleteAdviseInfo():
    
    params = request.get_json()
    accessToken = params.get("accessToken",None)
    adviseIds = params.get("adviseIds",None)

    my_db = ToMongo('wavedevice')
    query = {"advise_id":{"$in":adviseIds}}
    my_db.delete('odin_advise_info',query,is_one=False)    

    response_data = {}
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 8
    return response_data

@bp.route('/monitor/getEmergencyRecordMapCount', methods=['GET','POST'])
@login_required
def getEmergencyRecordMapCount():
    '''
    接口说明：获取不同维度告警统计
    '''
    my_db = ToMongo('wavedevice')
    time_now = datetime.now()
    emergency_coll = my_db.get_col('odin_business_emergency_record')
    today_zero = time_now.strftime("%Y-%m-%d")+" 00:00:00"
    monday_time = time_now - timedelta(days=time_now.weekday())
    week_firstday = monday_time.strftime("%Y-%m-%d")+" 00:00:00"
    month_firstday = time_now.strftime("%Y-%m") + "-01" + " 00:00:00"

    totalcount = my_db.get_aggregate("odin_business_emergency_record",query={})
    daycount = emergency_coll.find({'emergency_time':{"$gte" :today_zero}}).count()
    weekcount = emergency_coll.find({'emergency_time':{"$gte" :week_firstday}}).count()
    monthcount = emergency_coll.find({'emergency_time':{"$gte" :month_firstday}}).count()
    item = {}
    item['totalCount'] = totalcount
    item['nowDayCount'] = daycount
    item['weekCount'] = weekcount
    item['monthCount'] = monthcount
    
    response_data = {}
    response_data['data'] = item
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 56
    return jsonify(response_data)

@bp.route('/monitor/getEmergencyRecordByLastDayCount', methods=['GET','POST'])
@login_required
def getEmergencyRecordByLastDayCount():
    '''
    接口说明：按天获取最近15天的告警统计(未验证接口)
    '''
    my_db = ToMongo('wavedevice')
    time_now = datetime.now()
    emergency_coll = my_db.get_col('odin_business_emergency_record')
    every_emergency = []

    for i in range(15,0,-1):
        time_before = time_now - timedelta(days=(i))
        date = time_before.strftime("%Y-%m-%d")
        time_0 = date + " 00:00:00"
        time_24 = date + " 24:00:00"
        emergency_record = emergency_coll.find({"emergency_time":{"$gte" :time_0 ,"$lte" :time_24}})

        item ={}
        item['day'] = date
        item['num'] = emergency_record.count()
        every_emergency.append(item)
    
    response_data = {}
    response_data['data'] = every_emergency
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 56    
    return jsonify(response_data)

@bp.route('/monitor/getEmergencyRecordByTypeCount', methods=['GET','POST'])
@login_required
def getEmergencyRecordByTypeCount():
    '''
    接口说明：按告警记录类型统计
    '''
    my_db = ToMongo('wavedevice')
    emergency_col = my_db.get_col('odin_business_emergency_record')
    valuelist = my_db.get_keyvalues('odin_business_emergency_record','model_path')
    data = []
    for  value in valuelist:
        item = {}
        num = emergency_col.find({'model_path':value}).count()
        item["num"] = num
        item["modelPath"] = value
        data.append(item)
    
    response_data = {}
    response_data['data'] = data
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 56    
    return jsonify(response_data)

@bp.route('/monitor/getEmergencyTodayByTypeCount5', methods=['GET','POST'])
@login_required
def getEmergencyTodayByTypeCount5():
    '''
    接口说明：首页今日告警排行(top10)
    '''
    today = datetime.now().strftime("%Y-%m-%d") + " 00:00:00"
    my_db = ToMongo('wavedevice')
    emergency_col = my_db.get_col('odin_business_emergency_record').find({"emergency_time":{"$gte":today}})
    valuelist = []
    for emergency in emergency_col:
        valuelist.append(emergency['model_path'])
    set_value = set(valuelist)
    result = []
    for x in set_value:
        item = {}
        count = valuelist.count(x)
        item['count'] = count
        item['modelPath'] = x
        item['createDay'] =None
        item['groupMatterName'] = None
        result.append(item)

    result_sorted = sorted(result,key=lambda x:x['count'],reverse=True)

    if len(result_sorted) > 10:
        result_sorted = result_sorted[:10]


    response_data = {}
    response_data['data'] = result_sorted
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 56    
    return jsonify(response_data)

@bp.route('/monitor/getEmergencyRecordBy15DayCount', methods=['GET','POST'])
@login_required
def getEmergencyRecordBy15DayCount():
    '''
    接口说明：按天获取最近15天的告警统计（近15日违规行为趋势）
    '''
    my_db = ToMongo('wavedevice')
    time_now = datetime.now()
    emergency_coll = my_db.get_col('odin_business_emergency_record')
    every_emergency = []
    day_list = []
    time_15days_ago = time_now - timedelta(days=15)
    time_15days_ago_str = time_15days_ago.strftime("%Y-%m-%d") + " 00:00:00"
    query = {"emergency_time":{"$gte" :time_15days_ago_str}}
    model_list = emergency_coll.distinct('model_path',query)
    if model_list:
        for i in range(15,0,-1):
            time_before = time_now - timedelta(days=(i))
            date = time_before.strftime("%Y-%m-%d")
            day_list.append(date)
            time_0 = date + " 00:00:00"
            time_24 = date + " 24:00:00"
            query = {"emergency_time":{"$gte" :time_0 ,"$lte" :time_24}}
            res = emergency_coll.aggregate([{'$match':query},
                                            {'$group':{'_id':'$model_path','count':{'$sum':1}}}])      
            res_dict = dict()
            for x in res:
                model = x['_id']
                res_dict[model] = x['count']
            model_keys = res_dict.keys()
            for model in model_list:
                item = {}
                item['day'] = date
                item['modelPath'] = model
                if model in model_keys:
                    item['num'] = res_dict[model]
                else:
                    item['num'] = 0
                every_emergency.append(item)
        every_emergency.append({"time":sorted(day_list),"type":list(model_list)})
    response_data = {}
    response_data['data'] = every_emergency
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 56    
    return jsonify(response_data)

@bp.route('/monitor/getEmergencyRecordBy12MonthCount', methods=['GET','POST'])
@login_required
def getEmergencyRecordBy12MonthCount():
    '''
    接口说明：按月获取最近12月的告警统计（近12月违规行为趋势）
    '''
    my_db = ToMongo('wavedevice')
    now = datetime.now()
    emergency_coll = my_db.get_col('odin_business_emergency_record')
    every_emergency = []

    month_start = datetime(now.year-1,now.month+1,1)
    month_end = datetime(month_start.year,month_start.month,calendar.monthrange(month_start.year,month_start.month)[1])

    for i in range(12):
        start_time = month_start.strftime("%Y-%m-%d %H:%M:%S")
        month_end = month_end + timedelta(days=1)
        end_time = month_end.strftime("%Y-%m-%d %H:%M:%S")
        emergency_record = emergency_coll.find({"emergency_time":{"$gte" :start_time ,"$lte" :end_time}})
        
        item ={}
        item['day'] = "%d年%d月"%(month_start.year,month_start.month)
        item['num'] = emergency_record.count()
        every_emergency.append(item)

        month_start = month_end
        month_end = datetime(month_start.year,month_start.month,calendar.monthrange(month_start.year,month_start.month)[1])
    
    response_data = {}
    response_data['data'] = every_emergency
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 56    
    return jsonify(response_data)


@bp.route('/monitor/getEmergencyTotalByTypeCount15', methods=['GET','POST'])
@login_required
def getEmergencyTotalByTypeCount15():
    '''
    接口说明：按告警类型统计数量（违规行为总排名top15）
    '''
    my_db = ToMongo('wavedevice')
    emergency_col = my_db.get_col('odin_business_emergency_record')
    res = emergency_col.aggregate([{'$match':{}},
                                   {'$group':{'_id':'$model_path','count':{'$sum':1}}}]) 
    resdict = dict()
    for item in res:
        model_path = item['_id']
        num = item['count']
        resdict[model_path] = num

    ans = sorted(resdict.items(),key=lambda x:x[1],reverse=True)
    #mainlogger.debug(str(ans))
    if len(ans)>10:
        ans = ans[:10]
    data = []
    for k in ans:
        item = {}
        item["num"] = k[1]
        item["modelPath"] = k[0]
        data.append(item)
            
    response_data = {}
    response_data['data'] = data
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 56    
    return jsonify(response_data)


@bp.route('/monitor/getEmergencyRecordByPositionCity', methods=['GET','POST'])
@login_required
def getEmergencyRecordByPositionCity():
    '''
    接口说明：获取城市对应的告警统计
    '''
    params = request.get_json()
    positionCity = params.get("positionCity")
    my_db = ToMongo('wavedevice')
    emergency_coll = my_db.get_col('odin_business_emergency_record')
    camera_col =  my_db.get_col('odin_device_camera_edit')
    position_col = my_db.get_col('odin_device_position')

    todayStr = datetime.now().strftime("%Y-%m-%d")

    query = {"emergency_position":{"$regex":positionCity},"emergency_time":{"$regex":todayStr}}
    emergency_items = emergency_coll.find(query)
    
    totalEmergencyRecord = emergency_items.count()

    qurey_position = {"position_city":positionCity}
    cameraIdlist = position_col.distinct("camera_id",qurey_position)
    cameraTotal = len(cameraIdlist)

    query_cam = {"camera_id":{"$in":cameraIdlist},"camera_status":"0"}
    camera_items = camera_col.find(query_cam)
    onlineTimes = camera_items.count()

    totalcount = my_db.get_aggregate("odin_business_emergency_record",query={"emergency_time":{"$regex":todayStr}})
    if totalcount == 0:
        emergencyRecordPercent = 0
    else:
        emergencyRecordPercent = totalEmergencyRecord/totalcount

    query_model = {"emergency_time":{"$regex":todayStr}}
    res = emergency_coll.aggregate([{"$match":query},{"$group":{'_id':"$model_path",'count':{'$sum':1}}}])

    emergencyRecordList = []
    for item in res:
        mainlogger.debug("item:%s"%item)
        newItem = {}
        model_path = item["_id"]
        count = item["count"]
        newItem["modelPath"] = model_path
        newItem["times"] = count
        totalTypeCount = my_db.get_aggregate("odin_business_emergency_record",query={"emergency_time":{"$regex":todayStr},"model_path":model_path})
        newItem["percent"] = count/totalTypeCount * 100
        emergencyRecordList.append(newItem)

    data = {}
    data["emergencyRecordList"] = emergencyRecordList
    data["emergencyRecordPercent"] = emergencyRecordPercent*100
    data["onlineTimes"] = onlineTimes
    data["cameraTotal"] = cameraTotal
    data["totalEmergencyRecord"] = totalEmergencyRecord

    response_data = {}
    response_data['data'] = data
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 56
    return jsonify(response_data)

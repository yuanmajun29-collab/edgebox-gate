import uuid

from flask import Blueprint, flash, redirect, render_template, url_for, request,jsonify,current_app
import json
import os
import time
import base64
from Utils.db import *
from Utils.jwt_verify import *
from emergency.db_router import transfer_img_url
from datetime import datetime
from config import PERSON_IMG_URL,FACE_IDENT_URL
from algorith_server.AgreementBuilder import pack_face_3005
from algorith_server.Agreementunpack import host_ip
from msg_queue import faceidentification_queue
from Utils.facedb import FaceImageDBAPI,FaceFeatureDBAPI,verify_social_num
import Utils.glv as glv


bp = Blueprint("personnel",__name__, url_prefix='/net-web')

@bp.route('/personmanage/getPersonCount', methods=['GET','POST'])
@login_required
def getPersonCount():

    my_db = ToMongo('wavedevice')
    person_col = my_db.get_col('work_flow_personnel')
    response = {}
    response['requestId']=uuid.uuid4().hex
    response['requestStatus']="SUCCESS"
    response['timeUsed']=40
    # response['count'] = person_col.find().count()
    response['count'] = person_col.estimated_document_count()
    return  jsonify( response )

@bp.route('/personmanage/getPersonList', methods=['GET','POST'])
@login_required
def getPersonList():
    '''
    获取人脸库数据
    '''
    params = request.get_json()
    url_referer = request.headers['Referer']
    accessToken = params.get("accessToken",None)
    includeImage = params.get("includeImage",None)
    includePersonGroup = params.get("includePersonGroup",None)
    page = params.get("page",None)
    pageSize = params.get("pageSize",None)
    personnelGroupId = params.get("personnelGroupId",None)
    searchChoose = params.get("searchChoose",None)
    sortBy = params.get("sortBy",None)
    sortType = params.get("sortType",None)

    my_db = ToMongo('wavedevice')
    person_col = my_db.get_col('work_flow_personnel')
    person_img_col = my_db.get_col('work_flow_personnel_image')
    group_col = my_db.get_col('work_flow_personnelgroup')
    asso_group_col = my_db.get_col('work_flow_personnel_personnelgroup_associate')
    asso_mission_col = my_db.get_col('work_flow_mission_personnel_associate')

    query = {}
    if personnelGroupId:
        personid_list = my_db.get_keys_in_limitation("work_flow_personnel_personnelgroup_associate",
                                                    "personnel_id",
                                                    {"personnel_group_id":personnelGroupId})
        query['personnel_id'] = {"$in":personid_list}

    if searchChoose:
        query['$or'] = [{'personnel_name':{'$regex':searchChoose}},{'personnel_social_card':{'$regex':searchChoose}},{'personnel_number':{'$regex':searchChoose}}]

    if not sortBy:
        sortBy = "personnel_name"

    if sortType == "DESC":
        sortnum = -1
    else:
        sortnum = 1

    if page<1:
        page=1
    num = (page-1)*pageSize
    person_col = person_col.find(query).sort(sortBy,sortnum)
    person_items = person_col.skip(num).limit(pageSize)

    personnelList = []
    for person_item in person_items:
        item = {}
        person_id = person_item['personnel_id']
        img_item = person_img_col.find_one({"personnel_id":person_id})

        group_id_list = my_db.get_keys_in_limitation("work_flow_personnel_personnelgroup_associate",
                                                    "personnel_group_id",
                                                    {"personnel_id":person_id})
        if group_id_list:
            group_name_list = my_db.get_keys_in_limitation("work_flow_personnelgroup",
                                                    "personnel_group_name",
                                                    {"personnel_group_id":{"$in":group_id_list}})
        else:
            group_name_list =[]

        if group_name_list:
            groupname = ",".join(group_name_list)
        else:
            groupname = None

        items= asso_mission_col.find({"personnel_id":person_id})

        if items.count() == 0:
            item['flag'] = False
        else:
            item['flag'] = True

        #人脸图片由前端请求表头的Referer拼接
        if not img_item:
            item['imageUrl'] = None
        else:
            imageUrl = img_item['image_url']
            item['imageUrl'] = transfer_img_url(url_referer,imageUrl)

        item['personnelGroupName'] = groupname
        item['personnelId'] = person_id
        item['personnelName'] = person_item['personnel_name']
        item['personnelNumber'] = person_item['personnel_number']
        item['personnelPhoneNum'] = person_item['personnel_phone_number']
        item['personnelSex'] = person_item['personnel_sex']
        item['personnelSocialCard'] = person_item['personnel_social_card']
        personnelList.append(item)
    

    response = {}
    response['page']=page
    response['pageSize']=pageSize
    response['personnelList']=personnelList
    response['requestId']=uuid.uuid4().hex
    response['requestStatus']="SUCCESS"
    response['timeUsed']=40
    response['totalCount'] = person_col.count()
    return  jsonify( response )

@bp.route('/personmanage/getPersonDetail', methods=['GET','POST'])
@login_required
def getPersonDetail():
    '''
    获取人脸库数据
    '''
    params = request.get_json()
    accessToken = params.get("accessToken",None)
    personId = params.get("personId",None)

    my_db = ToMongo('wavedevice')
    person_col = my_db.get_col('work_flow_personnel')
    person_img_col = my_db.get_col('work_flow_personnel_image')
    group_col = my_db.get_col('work_flow_personnelgroup')
    asso_group_col = my_db.get_col('work_flow_personnel_personnelgroup_associate')

    detailEntity = {}
    query = {"personnel_id":personId}
    personnel_item = person_col.find_one(query)

    personnelAssocaiteImageList = []
    personnelGroupList = []
    img_items  = person_img_col.find(query)
    groupid_list = my_db.get_keys_in_limitation("work_flow_personnel_personnelgroup_associate",
                                                "personnel_group_id",
                                                {"personnel_id":personId})
    for groupid in groupid_list:
        item = {}
        grou_item = group_col.find_one({"personnel_group_id":groupid})
        if grou_item:
            item['personnelGroupId'] = groupid
            item['personnelGroupName'] = grou_item['personnel_group_name']
        else:
            item['personnelGroupId'] = ""
            item['personnelGroupName'] = ""
        personnelGroupList.append(item)
    
    for img_item in img_items:
        item = {}
        item['imageId'] = img_item['image_id']
        item['imageOperationStatus'] = img_item['image_operation_statue']
        item['imageType'] = img_item['image_type']
        item['imageUrl'] = img_item['image_url']
        item['faceTokenList'] = None
        personnelAssocaiteImageList.append(item)

    detailEntity['personnelAssocaiteImageList'] = personnelAssocaiteImageList
    detailEntity['personnelBirth'] = personnel_item['personnel_birth']
    detailEntity['personnelDrivingNumber'] = personnel_item['personnel_driving_number']
    detailEntity['personnelDrivingType'] = personnel_item['personnel_driving_type']
    detailEntity['personnelGroupList'] = personnelGroupList
    detailEntity['personnelId'] = personId

    detailEntity['personnelLocalAddress'] = personnel_item['personnel_local_address']
    detailEntity['personnelName'] = personnel_item['personnel_name']
    detailEntity['personnelNation'] =personnel_item['personnel_nation']
    detailEntity['personnelNumber'] =personnel_item['personnel_number']
    detailEntity['personnelPhoneNum'] =personnel_item['personnel_phone_number']
    detailEntity['personnelRemarks'] =personnel_item['personnel_remarks']

    detailEntity['personnelSex'] =personnel_item['personnel_sex']
    detailEntity['personnelSocialCard'] =personnel_item['personnel_social_card']
    detailEntity['wechatOpenId'] = personnel_item['wechat_open_id']
    detailEntity['workingDate'] = personnel_item['working_date']
    

    response = {}
    response['detailEntity']=detailEntity
    response['requestId']=uuid.uuid4().hex
    response['requestStatus']="SUCCESS"
    response['timeUsed']=40
    return  jsonify( response )

@bp.route('/persongroupmanage/getPersonnelGroupList', methods=['GET','POST'])
@login_required
def getPersonnelGroupList():

    params = request.get_json()
    accessToken = params.get("accessToken",None)
    page = params.get("page",None)
    pageSize = params.get("pageSize",None)
    groupType = params.get("groupType",None)
    searchChoose = params.get("searchChoose",None)
    sortBy = params.get("sortBy",None)
    sortType = params.get("sortType",None)

    personnelGroupIdList = params.get("personnelGroupIdList",None)

    query = {}
    if searchChoose:
        query = {"personnel_group_name":{"$regex":searchChoose}}

    if personnelGroupIdList:
        query['personnel_group_id'] = {'$in':personnelGroupIdList}

    if not sortBy:
        sortBy = "create_time"

    if sortType == "DESC":
        sortnum = -1
    else:
        sortnum = 1

    if page <= 0:
        page=1

    my_db = ToMongo('wavedevice')
    num = (page-1)*pageSize
    group_col = my_db.get_col('work_flow_personnelgroup').find(query)
    group_items = group_col.sort(sortBy,sortnum).skip(num).limit(pageSize)
    asso_group_col = my_db.get_col('work_flow_personnel_personnelgroup_associate')

    groupVos =[]
    if group_items.count() != 0:
        for group_item in group_items:
            item = {}
            item['createTime'] = int(group_item['create_time'].timestamp())*1000
            item['flag'] = False
            group_id = item['personnelGroupId'] = group_item['personnel_group_id']
            personNum = asso_group_col.find({"personnel_group_id":group_id}).count()
            item['personnelGroupName'] = group_item['personnel_group_name']
            item['personnelGroupRemarks'] = group_item['personnel_group_remarks']
            item['personNum'] = personNum
            groupVos.append(item)

    response = {}
    response['page']=page
    response['pageSize']=pageSize
    response['groupVos']=groupVos
    response['requestId']=uuid.uuid4().hex
    response['requestStatus']="SUCCESS"
    response['timeUsed']=40
    response['totalCount'] = group_col.count()
    return  jsonify( response )

@bp.route('/personmanage/addPerson', methods=['GET','POST'])
@login_required
def addPerson():

    params = request.get_json()
    accessToken = params.get("accessToken",None)
    edit = params.get("edit",None)
    personnelBirth = params.get("personnelBirth",None)
    personnelDrivingNumber = params.get("personnelDrivingNumber",None)
    personnelDrivingType = params.get("personnelDrivingType",None)
    personnelGroupIds = params.get("personnelGroupIds",None)
    personnelGroupList = params.get("personnelGroupList",None)
    personnelImages = params.get("personnelImages",None)
    personnelName = params.get("personnelName",None)
    personnelNation = params.get("personnelNation",None)
    personnelPhoneNum = params.get("personnelPhoneNum",None)
    personnelSex = params.get("personnelSex",None)
    personnelSocialCard = params.get("personnelSocialCard",None)
    workingDate = params.get("workingDate",None)

    personnelLocalAddress = params.get("personnelLocalAddress",None)
    personnelNumber = params.get("personnelNumber",None)
    personnelRemarks = params.get("personnelRemarks",None)
    
    my_db = ToMongo('wavedevice')
    organization_id = decode_token(accessToken,db=my_db)

    item = {'personnel_driving_type': personnelDrivingType, 
            'personnel_social_card': personnelSocialCard, 
            'personnel_id': uuid.uuid4().hex, 
            'personnel_name': personnelName, 
            'personnel_number': personnelNumber, 
            'organization_id': organization_id, 
            'personnel_birth': personnelBirth, 
            'device_sn': None, 
            'working_date': workingDate, 
            'personnel_sex': personnelSex, 
            'personnel_driving_number': personnelDrivingNumber, 
            'reside_group_size': None, 
            'personnel_local_address': personnelLocalAddress, 
            'personnel_email': None, 
            'personnel_remarks': personnelRemarks, 
            'personnel_age': 0, 
            'create_time': datetime.now(), 
            'personnel_nation': personnelNation, 
            'wechat_open_id': None, 
            'personnel_phone_number': personnelPhoneNum}
    
    my_db.insert("work_flow_personnel",item)

    iter = {"personnel_id":item['personnel_id']}
    for image_item in personnelImages:
        imageid = image_item['imageId']
        my_db.update("work_flow_personnel_image",{"image_id":imageid},{"$set":iter})

    if  personnelGroupIds:
        for groupid in personnelGroupIds:
            item_group = {"personnel_id":item['personnel_id'],"personnel_group_id":groupid}
            my_db.insert("work_flow_personnel_personnelgroup_associate",item_group)
    
    response = {}
    response['requestId']=uuid.uuid4().hex
    response['requestStatus']="SUCCESS"
    response['timeUsed']=40
    response['personnelId'] = item['personnel_id']
    return  jsonify( response )


@bp.route('/personmanage/addPersonBatch', methods=['GET','POST'])
@login_required
def addPersonBatch():
    '''
    导入人脸库成员
    '''

    params = request.get_json()
    accessToken = params.get("accessToken",None)
    personAddList = params.get("personAddList",None)

    my_db = ToMongo('wavedevice')

    error_response = {}
    error_response['errorCode'] = ""
    error_response['errorCodeDesc'] = ""
    error_response['requestId'] = uuid.uuid4().hex
    error_response['requestStatus'] = "FAIL"
    error_response['timeUsed'] = 107

    for personitem in personAddList:
        personnelBirth = personitem['personnelBirth']
        personnelDrivingNumber = personitem['personnelDrivingNumber']
        personnelDrivingType = personitem['personnelDrivingType']
        personnelLocalAddress = personitem['personnelLocalAddress']
        personnelName = personitem['personnelName']
        personnelNation = personitem['personnelNation']
        personnelNumber = personitem['personnelNumber']
        personnelPhoneNum = personitem['personnelPhoneNum']
        personnelRemarks = personitem['personnelRemarks']
        personnelSex = personitem['personnelSex']
        personnelSocialCard = personitem['personnelSocialCard']
        workingDate = personitem['workingDate']

        if not verify_social_num(personnelSocialCard):
            error_response['errorCode'] = "SOCIAL_CARD_ERROR"
            error_response['errorCodeDesc'] = "身份证号码不正确"
            return error_response
        if personnelSex not in ['男','女']:
            error_response['errorCode'] = "SEX_ERROR"
            error_response['errorCodeDesc'] = "性别填写不正确"
            return error_response

        str_phonenum = str(personnelPhoneNum)
        if len(str_phonenum) != 11:
            error_response['errorCode'] = "PHONE_NUM_ERROR"
            error_response['errorCodeDesc'] = "手机号码不正确"
            return error_response

        item = {}
        item['personnel_birth'] = personnelBirth
        item['personnel_driving_number'] = str(personnelDrivingNumber)
        item['personnel_driving_type'] = personnelDrivingType
        item['personnel_local_address'] = personnelLocalAddress
        item['personnel_name'] = personnelName
        item['personnel_nation'] = personnelNation
        item['personnel_number'] = personnelNumber
        item['personnel_phone_number'] = str_phonenum
        item['personnel_remarks'] = personnelRemarks
        item['personnel_sex'] = personnelSex
        item['personnel_social_card'] = personnelSocialCard
        item['working_date'] = workingDate
        item['personnel_id'] = uuid.uuid4().hex

        item['personnel_email'] = None
        item['organization_id'] = decode_token(accessToken,my_db)
        item['create_time'] = datetime.now()
        item['personnel_age'] = 0
        item['reside_group_size'] = None
        item['wechat_open_id'] = None
        item['working_date'] = None
        item['device_sn'] = None

        my_db.insert("work_flow_personnel",item)

    response = {}
    response['requestId']=uuid.uuid4().hex
    response['requestStatus']="SUCCESS"
    response['timeUsed']=40
    return  jsonify( response )

@bp.route('/personmanage/downloadPersonList', methods=['GET','POST'])
@login_required
def downloadPersonList():
    '''
    导出全部人脸库成员
    '''

    params = request.get_json()
    accessToken = params.get("accessToken",None)
    includeImage = params.get("includeImage",None)
    includePersonGroup = params.get("includePersonGroup",None)
    page = params.get("page",None)
    pageSize = params.get("pageSize",None)
    personnelGroupId = params.get("personnelGroupId",None)
    searchChoose = params.get("searchChoose",None)
    sortBy = params.get("sortBy",None)
    sortType = params.get("sortType",None)

    my_db = ToMongo('wavedevice')
    personnel_col = my_db.get_col('work_flow_personnel').find()
    person_image_col =  my_db.get_col('work_flow_personnel_image')


    personnelList = []
    for personnel_item in personnel_col:
        item = {}
        item['flag'] =  False
        item['personnelId'] =  personnel_item['personnel_id']
        item['personnelName'] =  personnel_item['personnel_name']
        item['personnelNumber'] =  personnel_item['personnel_number']
        item['personnelPhoneNum'] =  personnel_item['personnel_phone_number']
        item['personnelSex'] =  personnel_item['personnel_sex']
        item['personnelSocialCard'] =  personnel_item['personnel_social_card']

        group_id_list = my_db.get_keys_in_limitation("work_flow_personnel_personnelgroup_associate",
                                                    "personnel_group_id",
                                                    {"personnel_id":item['personnelId']})
        group_name_list = my_db.get_keys_in_limitation("work_flow_personnelgroup",
                                                "personnel_group_name",
                                                {"personnel_group_id":{"$in":group_id_list}})
        item['personnelGroupName'] = ",".join(group_name_list)
        image_item = person_image_col.find_one({"personnel_id":item['personnelId']})
        if image_item:
            item['imageUrl'] =  image_item['image_url']
        else:
            item['imageUrl'] =  ""
        personnelList.append(item)
            
    response = {}
    response['page']=page
    response['pageSize']=pageSize
    response['personnelList']=personnelList
    response['totalCount']=len(personnelList)
    response['requestId']=uuid.uuid4().hex
    response['requestStatus']="SUCCESS"
    response['timeUsed']=40
    return  jsonify( response )

@bp.route('/personmanage/deletePersonnelData', methods=['GET','POST'])
@login_required
def deletePersonnelData():

    params = request.get_json()
    accessToken = params.get("accessToken",None)
    personnelIdList = params.get("personnelIdList",None)

    my_db = ToMongo('wavedevice')
    
    if personnelIdList:
        for person_id in personnelIdList:
            my_db.delete("work_flow_personnel",
                        {"personnel_id":person_id})
            my_db.delete("work_flow_personnel_personnelgroup_associate",
                        {"personnel_id":person_id})
            my_db.delete("work_flow_personnel_image",
                        {"personnel_id":person_id})
            my_db.delete("work_flow_mission_personnel_associate",   #删除布控任务与人员的关联
                        {"personnel_id":person_id})  

    response = {}
    response['requestId']=uuid.uuid4().hex
    response['requestStatus']="SUCCESS"
    response['timeUsed']=40
    return  jsonify( response )

@bp.route('/personmanage/modifyPerson', methods=['GET','POST'])
@login_required
def modifyPerson():

    params = request.get_json()
    accessToken = params.get("accessToken",None)
    checkedGroupList = params.get("checkedGroupList",None)
    edit = params.get("edit",None)
    personnelAssocaiteImageList = params.get("personnelAssocaiteImageList",None)
    personnelBirth = params.get("personnelBirth",None)
    personnelDrivingNumber = params.get("personnelDrivingNumber",None)
    personnelDrivingType = params.get("personnelDrivingType",None)
    personnelGroupIds = params.get("personnelGroupIds",None)
    personnelGroupList = params.get("personnelGroupList",None)
    personnelId = params.get("personnelId",None)
    personnelImages = params.get("personnelImages",None)
    personnelLocalAddress = params.get("personnelLocalAddress",None)
    personnelName = params.get("personnelName",None)
    personnelNation = params.get("personnelNation",None)
    personnelNumber = params.get("personnelNumber",None)
    personnelPhoneNum = params.get("personnelPhoneNum",None)
    personnelRemarks = params.get("personnelRemarks",None)
    personnelSex = params.get("personnelSex",None)
    personnelSocialCard = params.get("personnelSocialCard",None)
    wechatOpenId = params.get("wechatOpenId",None)
    workingDate = params.get("workingDate",None)

    my_db = ToMongo('wavedevice')
    query = {"personnel_id":personnelId}
    item_personel = {}
    item_personel['working_date'] = workingDate
    item_personel['wechat_open_id'] = wechatOpenId
    item_personel['personnel_social_card'] = personnelSocialCard
    item_personel['personnel_sex'] = personnelSex
    item_personel['personnel_remarks'] = personnelRemarks
    item_personel['personnel_phone_number'] = personnelPhoneNum
    item_personel['personnel_number'] = personnelNumber
    item_personel['personnel_nation'] = personnelNation
    item_personel['personnel_name'] = personnelName
    item_personel['personnel_local_address'] = personnelLocalAddress
    item_personel['personnel_birth'] = personnelBirth
    item_personel['personnel_driving_number'] = personnelDrivingNumber
    item_personel['personnel_driving_type'] = personnelDrivingType
    my_db.update("work_flow_personnel",query,{"$set":item_personel})     #更新人脸库信息


    #更新人脸关联persongroup
    my_db.delete("work_flow_personnel_personnelgroup_associate",query,is_one=False)
    for groupid in personnelGroupIds:
        item = {}
        item['personnel_id'] = personnelId
        item['personnel_group_id'] = groupid
        my_db.insert("work_flow_personnel_personnelgroup_associate",item)

    #更新人脸关联人脸图片
    img_id_list = my_db.get_keyvalues("work_flow_personnel_image","image_id")
    for image_item in personnelImages:
        imageid = image_item['imageId']
        if imageid not in img_id_list:
            continue
        item = {"personnel_id":personnelId}
        my_db.update("work_flow_personnel_image",{"image_id":imageid},{"$set":item})

    response = {}
    response['requestId']=uuid.uuid4().hex
    response['requestStatus']="SUCCESS"
    response['timeUsed']=40
    return  jsonify( response )


@bp.route('/personmanage/delPersonImages', methods=['GET','POST'])
@login_required
def delPersonImages():

    params = request.get_json()
    accessToken = params.get("accessToken",None)
    imageId = params.get("imageId",None)

    my_db = ToMongo('wavedevice')
    query = {"image_id":imageId}
    my_db.delete("work_flow_personnel_image",query)

    response = {}
    response['requestId']=uuid.uuid4().hex
    response['requestStatus']="SUCCESS"
    response['timeUsed']=40
    return  jsonify( response )

@bp.route('/personmanage/getPersonListByIds', methods=['GET','POST'])
@login_required
def getPersonListByIds():

    params = request.get_json()
    accessToken = params.get("accessToken",None)
    personnelIdList = params.get("personnelIdList",None)

    my_db = ToMongo('wavedevice')
    personnel_col = my_db.get_col('work_flow_personnel')
    person_items = personnel_col.find({"personnel_id":{"$in":personnelIdList}})

    personnelEntityList = []
    for person_item in person_items:
        iter = {}
        iter['personnelGroupId'] = None
        iter['personnelGroupName'] = None
        iter['personnelId'] = person_item['personnel_id']
        iter['personnelName'] = person_item['personnel_name']
        iter['personnelNumber'] = person_item['personnel_number']
        iter['personnelPhoneNum'] = person_item['personnel_phone_number']
        iter['personnelSocialCard'] = person_item['personnel_social_card']
        personnelEntityList.append(iter)

    response = {}
    response['personnelEntityList']=personnelEntityList
    response['requestId']=uuid.uuid4().hex
    response['requestStatus']="SUCCESS"
    response['timeUsed']=40
    return  jsonify( response )

@bp.route('/personmanage/validPersonImage', methods=['GET','POST'])
def validPersonImage():

    params = request.form
    imageH = params.get("imageH")
    imageW = params.get("imageW")
    imgtype = params.get("type")
        
    imgfile = request.files['file'].stream.read()
    imgid = uuid.uuid4().hex
    temp_url = PERSON_IMG_URL + imgid + "/" 
    if not os.path.exists(temp_url):
        os.makedirs(temp_url)
        os.chmod(temp_url,0o777)

    img_url = temp_url + imgid + ".jpg"
    img_base64 = base64.b64encode(imgfile)
    face_msg = {}
    face_msg['image_id'] = imgid
    face_msg['image_h'] = imageH
    face_msg['image_w'] = imageW
    face_msg['image_data'] = img_base64.decode('utf-8')
    face_msg['image_type'] = imgtype

    face_msg_str = json.dumps(face_msg)
    total_msg = pack_face_3005(face_msg_str)

    from algorith_server.AlgorithServer_new import SenderThread
    sender = SenderThread( current_app.app_context() )
    sender.send_face_message(facemsg=total_msg)
    
    error_response = {}
    error_response['errorCode'] = "500"
    error_response['errorCodeDesc'] = "图片无法提取人脸特征值，请换另一张图片"
    error_response['exceptionCodeDesc'] = ""
    error_response['requestId'] = uuid.uuid4().hex
    error_response['requestStatus'] = "FAIL"
    error_response['timeUsed'] = 107

    n=0
    while True:
        num = faceidentification_queue.qsize()
        if num == 0:
            if n == 2:
                return error_response
            n+=1
            time.sleep(1)
        else:
            result = faceidentification_queue.get()
            break
    
    msg_result = json.loads(result)
    face_features = msg_result['face_features']
    if not face_features or  face_features == "":
        return error_response

    #把人脸图存到本地
    with open(img_url,"wb") as outfile:
        outfile.write(imgfile)

    #把人脸特征存到本地
    feature_dir = FACE_IDENT_URL + imgid + '/'
    feature_url = feature_dir + imgid + ".json"
    if not os.path.exists(feature_dir):
        os.makedirs(feature_dir)
        os.chmod(feature_dir,0o777)
    with open(feature_url,"a") as outfile:
        outfile.write(face_features)

    my_db = ToMongo('wavedevice')

    port = glv.get_value('nginx_port','8088')
    mainlogger.debug('---nginx_port : %s'%port)
    img_pathhead = 'http://%s:%s/net-web/face_images/'%(host_ip,port)
    feature_pathhead = 'http://%s:%s/net-web/face_features/'%(host_ip,port)
    face_url = img_pathhead   +imgid + ".jpg"
    image_check_url = feature_pathhead + imgid + ".json"
    item = {"image_id":imgid,
            "personnel_id":None,
            "image_operation_statue":0,
            "create_time":datetime.now(),
            "image_type":"0",
            "image_url":face_url,
            "image_checksum":None,
            "image_check_url":image_check_url
            }

    my_db.insert("work_flow_personnel_image",item)

    response = {}
    response['imageId']=imgid
    response['imagePath']= face_url
    response['requestId']=uuid.uuid4().hex
    response['requestStatus']="SUCCESS"
    response['timeUsed']=40
    return  jsonify( response )

@bp.route('/persongroupmanage/getPersonnelByGroupId', methods=['GET','POST'])
@login_required
def getPersonnelByGroupId():

    params = request.get_json()
    accessToken = params.get("accessToken",None)
    page = params.get("page",None)
    includeMission = params.get("includeMission",None)
    includePersonGroup = params.get("includePersonGroup",None)
    pageSize = params.get("pageSize",None)
    personnelGroupId = params.get("personnelGroupId",None)
    
    my_db = ToMongo('wavedevice')
    asso_group_col = my_db.get_col("work_flow_personnel_personnelgroup_associate")
    personnel_col = my_db.get_col("work_flow_personnel")
    personnelList =[]
    if personnelGroupId:
        asso_items = asso_group_col.find({"personnel_group_id":personnelGroupId})
        for asso_item in asso_items:
            personnel_id = asso_item['personnel_id']
            personnel_item = personnel_col.find_one({"personnel_id":personnel_id})
            iter = {}
            iter['personnelGroupId'] = personnelGroupId
            group_id_list = my_db.get_keys_in_limitation("work_flow_personnel_personnelgroup_associate",
                                                    "personnel_group_id",
                                                    {"personnel_id":personnel_id})
            group_name_list = my_db.get_keys_in_limitation("work_flow_personnelgroup",
                                                    "personnel_group_name",
                                                    {"personnel_group_id":{"$in":group_id_list}})
            iter['personnelGroupName'] = ",".join(group_name_list)
            iter['personnelId'] = personnel_item['personnel_id']
            iter['personnelName'] = personnel_item['personnel_name']
            iter['personnelNumber'] = personnel_item['personnel_number']
            iter['personnelPhoneNum'] = personnel_item['personnel_phone_number']
            iter['personnelSocialCard'] = personnel_item['personnel_social_card']
            personnelList.append(iter)
    else:
        personn_in_group = my_db.get_keyvalues("work_flow_personnel_personnelgroup_associate","personnel_id")
        query = {"personnel_id":{"$nin":personn_in_group}}
        asso_items = personnel_col.find(query)
        for asso_item in asso_items:
            iter = {}
            iter['personnelId'] = asso_item['personnel_id']
            iter['personnelName'] = asso_item['personnel_name']
            iter['personnelPhoneNum'] = asso_item['personnel_phone_number']
            iter['personnelSocialCard'] = asso_item['personnel_social_card']
            personnelList.append(iter)

    response = {}
    response['requestId']=uuid.uuid4().hex
    response['requestStatus']="SUCCESS"
    response['timeUsed']=40
    response['personnelList'] = personnelList
    response['total'] = len(personnelList)
    return  jsonify( response )

@bp.route('/persongroupmanage/addPersonnelGroup', methods=['GET','POST'])
@login_required
def addPersonnelGroup():
    '''
    增加人脸组
    '''
    params = request.get_json()
    accessToken = params.get("accessToken",None)
    personnelGroupId = params.get("personnelGroupId",None)
    personnelGroupName = params.get("personnelGroupName",None)
    personnelGroupRemarks = params.get("personnelGroupRemarks",None)
    
    my_db = ToMongo('wavedevice')
    organization_id = decode_token(accessToken,db=my_db)
    item = {}
    item['personnel_group_id'] = uuid.uuid4().hex
    item['personnel_group_name'] = personnelGroupName
    item['personnel_group_remarks'] = personnelGroupRemarks
    item['personnel_group_type'] = 0   #0表示普通分组，1表示黑名单分组
    item['personnel_group_level'] = 0  #人员组在该分组类型中的等级，普通分组只存在等级0，黑名单分组从0-255
    item['organization_id'] = organization_id
    item['create_time'] = datetime.now()
    my_db.insert("work_flow_personnelgroup",item)

    response = {}
    response['requestId']=uuid.uuid4().hex
    response['requestStatus']="SUCCESS"
    response['timeUsed']=40
    response['personnelGroupId'] = item["personnel_group_id"]
    return  jsonify( response )

@bp.route('/persongroupmanage/modifyPersonnelGroup', methods=['GET','POST'])
@login_required
def modifyPersonnelGroup():
    '''
    编辑人脸组
    '''
    params = request.get_json()
    accessToken = params.get("accessToken",None)
    personnelGroupId = params.get("personnelGroupId",None)
    personnelGroupName = params.get("personnelGroupName",None)
    personnelGroupRemarks = params.get("personnelGroupRemarks",None)
    
    my_db = ToMongo('wavedevice')
    item = {}
    item['personnel_group_name'] = personnelGroupName
    item['personnel_group_remarks'] = personnelGroupRemarks

    query= {"personnel_group_id":personnelGroupId}

    my_db.update("work_flow_personnelgroup",query,{"$set":item})

    response = {}
    response['requestId']=uuid.uuid4().hex
    response['requestStatus']="SUCCESS"
    response['timeUsed']=40
    return  jsonify( response )

@bp.route('/persongroupmanage/deletePersonnelGroup', methods=['GET','POST'])
@login_required
def deletePersonnelGroup():
    '''
    删除人脸组
    '''
    params = request.get_json()
    accessToken = params.get("accessToken",None)
    personnelGroupId = params.get("personnelGroupId",None)
    query= {"personnel_group_id":personnelGroupId}
    
    my_db = ToMongo('wavedevice')

    my_db.delete("work_flow_personnelgroup",query)
    my_db.delete("work_flow_personnel_personnelgroup_associate",query,is_one=False)

    response = {}
    response['requestId']=uuid.uuid4().hex
    response['requestStatus']="SUCCESS"
    response['timeUsed']=40
    return  jsonify( response )

@bp.route('/personnel/modifyPersonGroup', methods=['GET','POST'])
@login_required
def modifyPersonGroup():
    '''
    修改人脸组的成员
    '''

    params = request.get_json()
    accessToken = params.get("accessToken",None)
    personnelGroepId = params.get("personnelGroepId",None)
    personnelIds = params.get("personnelIds",None)
    
    my_db = ToMongo('wavedevice')
    my_db.delete("work_flow_personnel_personnelgroup_associate",{"personnel_group_id":personnelGroepId},is_one=False)
    
    for personid in personnelIds:
        item = {'personnel_group_id':personnelGroepId,'personnel_id':personid}
        my_db.insert("work_flow_personnel_personnelgroup_associate",item)

    response = {}
    response['requestId']=uuid.uuid4().hex
    response['requestStatus']="SUCCESS"
    response['timeUsed']=40
    return  jsonify( response )


view_func = FaceImageDBAPI.as_view(('{}_api').format('face_images'))
bp.add_url_rule(('/{}/<string:{}>').format('face_images', 'image_id'), view_func=view_func,methods=['GET', 'PUT', 'DELETE'])


view_func_feature = FaceFeatureDBAPI.as_view(('{}_api').format('face_features'))
bp.add_url_rule(('/{}/<string:{}>').format('face_features', 'image_id'), view_func=view_func_feature,methods=['GET', 'PUT', 'DELETE'])
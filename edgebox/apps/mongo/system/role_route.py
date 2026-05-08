

from datetime import datetime
from flask import Blueprint, render_template, request ,jsonify
import json
from Utils.db import ToMongo
from Utils.utils import generate_log
from Utils.jwt_verify import *
import uuid

bp = Blueprint("role",__name__, url_prefix='/net-web')
@bp.route('/auth/get_role_info', methods=['GET','POST'])
@login_required
def get_role_info():
    '''
    接口描述：查询角色的详细信息；
    '''

    params = request.get_json()
    role_id = params.get("roleId", None)
   
    my_db = ToMongo('wavedevice')
    role_item = my_db.get_col('authority_role').find_one({'role_id':role_id})
    permission_list = my_db.get_col('authority_role_permission_associate').find({'role_id':role_id})

    permission_coll = my_db.get_col('authority_permission')
    permissionInfoList = []
    for permission in permission_list:
        permission_id = permission['permission_id']
        query = {'permission_id':permission_id}
        permission_item = permission_coll.find_one(query)
        item = {}
        item['permissionId'] = permission_id
        item['permissionName'] = permission_item['permission_name']
        item['permissionOriginId'] = permission_item['permission_origin_id']
        permissionInfoList.append(item)


    response_data = {}
    response_data['permissionInfoList'] = permissionInfoList
    response_data['roleId'] = role_id
    response_data['roleDescription'] = role_item['role_description']
    response_data['roleName'] = role_item['role_name']
    response_data['roleType'] = role_item['role_type'] 
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 18 
    return jsonify(response_data)

@bp.route('/auth/get_role_list', methods=['GET','POST'])
@login_required
def get_role_list():
    '''
    接口描述：查询角色列表信息；
    '''
    my_db = ToMongo('wavedevice')

    params = request.get_json()
    page = params.get("page", None)
    pagesize = params.get("pageSize", None)
    role_name = params.get("roleName", None)
    role_type = params.get("roleType", None)

    if page and pagesize:
        num = (page-1)*pagesize

    query = {"organization_id":'001611544223344645607'}
    if role_name:
        query['role_name'] = {"$regex":role_name}
    if role_type:
        query['role_type'] = role_type 

    role_coll = my_db.get_col('authority_role').find(query).sort('role_name',-1)
    totalcount = role_coll.count()
    if page and pagesize:
        role_list = role_coll.skip(num).limit(pagesize)
    else:
        role_list = role_coll
    roleInfoList = []
    for role in role_list:
        item = {}
        item['createTime'] = role['create_time'].timestamp()*1000
        item['roleDescription'] = role['role_description']
        item['roleId'] = role['role_id']
        item['roleName'] = role['role_name']
        item['roleType'] = role['role_type']
        roleInfoList.append(item)

    response_data = {}
    response_data['roleInfoList'] = roleInfoList
    response_data['totalCount'] = totalcount
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 18 
    return jsonify(response_data)

@bp.route('/auth/update_role_info', methods=['GET','POST'])
@login_required
def update_role_info():
    '''
    接口描述：用来编辑角色信息
    '''

    params = request.get_json()
    role_id = params.get("roleId", None)
    role_name = params.get("roleName", None)
    instruction = params.get("instruction", None)
   
    my_db = ToMongo('wavedevice')
    generate_log(request,db=my_db)
    my_db.update('authority_role',
                {'role_id':role_id},
                {'$set':{'role_name':role_name,'role_description':instruction}}
                )   

    response_data = {}
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 18 
    return jsonify(response_data)

@bp.route('/auth/delete_role_info', methods=['GET','POST'])
@login_required
def delete_role_info():
    '''
    接口描述：用户在页面删除组织内的角色信息;
    '''
    
    params = request.get_json()
    role_id_list = params.get("roleIdList", None)

    my_db = ToMongo('wavedevice')
    generate_log(request,db=my_db)
    for role_id in role_id_list:
        my_db.delete('authority_role',{'role_id':role_id})
        my_db.delete('authority_role_permission_associate',{'role_id':role_id},is_one=False)
        my_db.delete('authority_user_role_associate',{'role_id':role_id},is_one=False)


    response_data = {}
    response_data['failedList'] = []
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 18 
    return jsonify(response_data)



@bp.route('/auth/set_role_permission', methods=['GET','POST'])
@login_required
def set_role_permission():
    '''
    接口描述：设置角色关联权限信息;
    '''
    
    params = request.get_json()
    role_id = params.get("roleId", None)
    permission_list = params.get("permissionList", None)

    my_db = ToMongo('wavedevice')
    my_db.delete('authority_role_permission_associate',
                 {'role_id':role_id},
                 is_one = False
                )
    for permission_id in permission_list:
        my_db.insert('authority_role_permission_associate',
                     {'role_id':role_id,'permission_id':permission_id}
                    )

    response_data = {}
    response_data['failedList'] = []
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 18 
    return jsonify(response_data)


@bp.route('/auth/add_role_info', methods=['GET','POST'])
@login_required
def add_role_info():
    '''
    接口描述：用户在页面为自己的组织添加角色信息;
    '''
    
    params = request.get_json()
    role_name = params.get("roleName", None)
    instruction = params.get("instruction", None)

    my_db = ToMongo('wavedevice')
    generate_log(request,db=my_db)
    res = {'role_id':uuid.uuid4().hex,
            'role_name':role_name,
            'role_type':"2",
            'role_description':instruction,
            'organization_id':"001611544223344645607",          
            'create_time':datetime.now()
          }
    my_db.insert('authority_role',
                res)
    

    response_data = {}
    response_data['roleId'] = res['role_id']
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 18 
    return jsonify(response_data)
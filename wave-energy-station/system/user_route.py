import json
import uuid
from flask import Blueprint, jsonify
from utils.db import ToMongo
from utils.Utils import set_success_result, generate_log
from utils.jwt_verify import *
from utils.ver_code_image import *
from utils.redis_connect import redis_database

bp = Blueprint("user", __name__, url_prefix='/net-web')


def valid_login_by_username(my_db):
    '''
    校验*登陆
    '''
    error_response = set_fail_result()
    # 检验*参数合法性
    account = request.get_json().get("accountOrPhone", None)
    password = request.get_json().get("userPassword", None)
    valid_param_legal(account, password, error_response)

    # 避免错误账号多次攻击
    if redis_database.exists(account) and redis_database.get(account) == 0:
        error_response['errorCodeDesc'] = "错误的账号"
        error_response['flag'] = '0'
        raise Exception(BaseException(error_response))
    elif redis_database.exists(account) and redis_database.get(account) == 8:
        error_response['errorCodeDesc'] = "尝试错误次数过多,锁定10分钟"
        error_response['flag'] = '8'
        raise Exception(BaseException(error_response))
    # 检验*登陆合法性
    user_coll = my_db.get_col('authority_user')
    user = user_coll.find_one({'user_status': '1', '$or': [{'user_account': account}, {'user_phone': account}]})
    valid_login_legal(account, password, user)
    # 校验通过*返回正确值
    return user


def valid_param_legal(account, password, error_response):
    '''
    检验*参数合法性
    '''
    error_response['errorCode'] = "ERROR_ACCOUNT_PASSWORD"
    if not account:
        error_response['errorCodeDesc'] = "账号为空"
        error_response['flag'] = "1"
        raise Exception(BaseException(error_response))
    if not password:
        error_response['errorCodeDesc'] = "密码为空"
        error_response['flag'] = "1"
        raise Exception(BaseException(error_response))
    return


def valid_login_legal(account, password, user):
    '''
    检验*登陆合法性
    '''
    error_response = set_fail_result()
    error_response['errorCode'] = "ERROR_ACCOUNT_PASSWORD"
    if not user:
        error_response['errorCodeDesc'] = "错误的账号"
        redis_database.set(account, 0)
        raise Exception(BaseException(error_response))
    if user['user_password'] != password:
        error_response['errorCodeDesc'] = "错误的密码"
        if redis_database.exists(account):
            num = int(redis_database.get(account))
            if 3 <= num < 8:
                # 查询登陆次数：3--生成验证码并返回
                error_response['errorCodeDesc'] = "登陆次数达到3次以上,需要验证码"
                error_response['flag'] = '3'
                num += 1
                redis_database.set(account, num)
                raise Exception(BaseException(error_response))
            elif num > 8:
                # 8次锁定登陆10分钟
                redis_database.set(account, 9, 10 * 60)
                error_response['errorCodeDesc'] = "尝试错误次数过多，锁定10分钟"
                error_response['flag'] = '8'
                raise Exception(BaseException(error_response))
            else:
                num += 1
                redis_database.set(account, num)
                raise Exception(BaseException(error_response))
        else:
            redis_database.set(account, 1)
            raise Exception(BaseException(error_response))
    return


@bp.route('/auth/account_phone_pwd_login', methods=['GET', 'POST'])
def account_phone_pwd_login():
    '''
    接口注释：用户在页面通过输入手机号密码的方式登录
    '''
    my_db = ToMongo('wavedevice')
    try:
        user = valid_login_by_username(my_db)
    except Exception as e:
        return json.loads(str(e).replace("'", "\""))

    organization_coll = my_db.get_col('authority_organization')
    organization_id = user['organization_id']
    organization = organization_coll.find_one({"organization_id": organization_id})

    response_data = set_success_result()
    response_data['organizationId'] = organization_id
    response_data['organizationName'] = organization['organization_name']
    response_data['organizationOwnerId'] = organization['organization_ownerId']

    response_data['userAccount'] = useraccount = user['user_account']
    response_data['userIcon'] = user['user_icon']
    response_data['userId'] = user['user_id']
    response_data['userName'] = user['user_real_name']
    response_data['userPhone'] = user['user_phone']
    response_data['userStatus'] = user['user_status']

    user_role_associate_coll = my_db.get_col('authority_user_role_associate')
    role_permission_associate_coll = my_db.get_col('authority_role_permission_associate')
    permission_coll = my_db.get_col('authority_permission')

    role_item = user_role_associate_coll.find({'user_id': user['user_id']})
    permissionInfoList = []
    for role in role_item:
        role_id = role['role_id']
        permission_list = role_permission_associate_coll.find({'role_id': role_id})
        for permission in permission_list:
            permission_id = permission['permission_id']
            permission_item = permission_coll.find_one({'permission_id': permission_id})
            if not permission_item:
                continue
            item = {}
            item['permissionAlias'] = permission_item['permission_alias']
            item['permissionId'] = permission_id
            item['permissionName'] = permission_item['permission_name']
            item['permissionOriginId'] = permission_item['permission_origin_id']
            permissionInfoList.append(item)

    param = {'organization_id': organization_id}
    model_col = my_db.get_col('authority_work_model')
    model_col.find_one_and_update({'model': '0'}, {"$set": param})

    response_data['permissionInfoList'] = permissionInfoList
    token = create_token(useraccount)
    response_data['accessToken'] = token
    response_data['errorCode'] = None
    response_data['errorCodeDesc'] = None
    response_data['refreshToken'] = str(uuid.uuid4())
    return jsonify(response_data)


@bp.route('/auth/refresh_access_token', methods=['GET', 'POST'])
def refresh_access_token():
    params = request.get_json()
    accessToken = params.get("accessToken", None)
    refreshToken = params.get("accessToken", None)

    response_data = set_fail_result()
    response_data['errorCode'] = "INVALID_REFRESH_TOKEN"
    response_data['errorCodeDesc'] = '登录已过期,请重新登录'
    return jsonify(response_data)


@bp.route('/auth/login_out_user', methods=['GET', 'POST'])
@login_required
def login_out_user():
    '''
    接口注释：用户登出本平台
    '''
    params = request.get_json()
    accessToken = params.get("accessToken", None)

    response_data = set_success_result()
    return jsonify(response_data)


@bp.route('/auth/get_permission_list', methods=['GET', 'POST'])
@login_required
def get_permission_list():
    '''
    接口说明：查询权限列表接口
    状态：未验证
    '''
    my_db = ToMongo('wavedevice')
    permission_coll = my_db.get_col('authority_permission').find({}).sort("permission_id")
    infolist = []
    for info in permission_coll:
        item = {}
        item['permissionId'] = info['permission_id']
        # if item['permissionId'].startswith('base') or item['permissionId'].startswith('device'):
        #     continue
        item['permissionName'] = info['permission_name']
        item['permissionOriginId'] = info['permission_origin_id']
        infolist.append(item)

    response_data = set_success_result()
    response_data['permissionInfoList'] = infolist
    return jsonify(response_data)


@bp.route('/auth/get_user_info', methods=['GET', 'POST'])
@login_required
def get_user_info():
    '''
    接口注释：查询用户的详细信息
    '''
    my_db = ToMongo('wavedevice')
    params = request.get_json()
    user_id = params.get("userId", None)
    user = my_db.get_col('authority_user').find_one({'user_id': user_id})

    response_data = set_success_result()
    response_data['userId'] = user_id
    response_data['userIdCard'] = user['user_idCard']
    response_data['userName'] = user['user_real_name']
    response_data['userPhone'] = user['user_phone']
    response_data['userSex'] = user['user_sex']
    response_data['userStatus'] = user['user_status']
    response_data['userIcon'] = user['user_icon']
    response_data['userAccount'] = user['user_account']

    response_data['organizationId'] = user['organization_id']
    response_data['remark'] = user['remark']
    response_data['createTime'] = int(user['create_time'].timestamp()) * 1000

    organization = my_db.get_col('authority_organization').find_one({'organization_id': user['organization_id']})
    response_data['checkFlag'] = 1
    response_data['openId'] = None
    response_data['departmentInfoList'] = []
    response_data['organizationDomain'] = organization['organization_domain']
    response_data['organizationName'] = organization['organization_name']
    response_data['organizationOwner'] = organization['organization_ownerId']

    role_list = my_db.get_col('authority_user_role_associate').find({'user_id': user_id})
    authority_role_coll = my_db.get_col('authority_role')
    roleInfoList = []
    for role in role_list:
        role_id = role['role_id']
        role_name = authority_role_coll.find_one({'role_id': role_id})['role_name']
        item = {}
        item['roleId'] = role_id
        item['roleName'] = role_name
        roleInfoList.append(item)
    response_data['roleInfoList'] = roleInfoList
    return jsonify(response_data)


@bp.route('/auth/get_department_list', methods=['GET', 'POST'])
@login_required
def get_department_list():
    '''
    接口注释：此接口用来获取部门信息列表信息
    '''
    my_db = ToMongo('wavedevice')
    department_coll = my_db.get_col('authority_department').find()
    departmentInfoList = []
    iter = {}
    for department_info in department_coll:
        iter['departmentId'] = department_info['department_id']
        iter['departmentName'] = department_info['department_name']
        iter['departmentOrder'] = department_info['department_order']
        iter['departmentOriginId'] = department_info['department_origin_id']
        iter['departmentType'] = department_info['department_type']
        departmentInfoList.append(iter)

    response_data = set_success_result()
    response_data['departmentInfoList'] = departmentInfoList
    return jsonify(response_data)


@bp.route('/auth/get_user_list', methods=['GET', 'POST'])
@login_required
def get_user_list():
    '''
    接口注释：用户在页面查询用户列表
    '''
    my_db = ToMongo('wavedevice')
    params = request.get_json()
    department_id = params.get("departmentId", None)
    page = params.get("page", None)
    pagesize = params.get("pageSize", None)
    roleid = params.get("roleId", None)
    sortby = params.get("sortBy", None)
    sort_type = params.get("sortType", None)
    user_name = params.get("userName", None)
    quary = {}
    if user_name:
        quary['user_real_name'] = {"$regex": user_name}
    authority_user_coll = my_db.get_col('authority_user').find(quary).sort('user_account', -1)
    totalcount = authority_user_coll.count()
    num = (page - 1) * pagesize
    authority_user = authority_user_coll.skip(num).limit(pagesize)
    userTableInfos = []
    for user in authority_user:
        iter = {}
        create_time = user['create_time']
        iter['createTime'] = int(create_time.timestamp()) * 1000
        iter['remark'] = user['remark']
        iter['userAccount'] = user['user_account']
        userid = iter['userId'] = user['user_id']
        iter['userName'] = user['user_real_name']
        iter['userSex'] = user['user_sex']
        iter['userStatus'] = user['user_status']
        iter['roleInfoList'] = []

        role_list = my_db.get_col('authority_user_role_associate').find({'user_id': userid})
        role_coll = my_db.get_col('authority_role')
        for role in role_list:
            item = {}
            item['roleId'] = role['role_id']
            item['roleName'] = role_coll.find_one({'role_id': role['role_id']})['role_name']
            iter['roleInfoList'].append(item)
        userTableInfos.append(iter)
    response_data = set_success_result()
    response_data['userTableInfos'] = userTableInfos
    response_data['totalCount'] = totalcount
    response_data['organizationOwner'] = "001611544208158810406"
    return jsonify(response_data)


@bp.route('/auth/del_user', methods=['GET', 'POST'])
@login_required
def del_user():
    '''
    接口注释：管理员删除用户操作
    '''
    my_db = ToMongo('wavedevice')
    generate_log(request, db=my_db)
    params = request.get_json()
    userid_list = params.get("userIdList", None)
    for userid in userid_list:
        my_db.delete('authority_user', {'user_id': userid})
        my_db.delete('authority_user_department_associate', {'user_id': userid})
        my_db.delete('authority_user_role_associate', {'user_id': userid})

    response_data = set_success_result()
    return jsonify(response_data)


@bp.route('/auth/edit_user', methods=['GET', 'POST'])
@login_required
def edit_user():
    '''
    接口注释：超级管理员手动添加人员
    '''
    my_db = ToMongo('wavedevice')
    generate_log(request, db=my_db)
    params = request.get_json()
    departmentId = params.get("departmentId", None)
    phone = params.get("phone", None)
    remark = params.get("remark", None)
    userAccount = params.get("userAccount", None)
    userId = params.get("userId", None)
    userName = params.get("userName", None)
    userPassword = params.get("userPassword", None)

    res = {}
    if remark:
        res['remark'] = remark
    if userPassword:
        res['user_password'] = userPassword
    res['user_phone'] = phone
    res['user_account'] = userAccount
    res['user_real_name'] = userName

    my_db.update('authority_user',
                 {'user_id': userId},
                 {'$set': res}
                 )

    response_data = set_success_result()
    return jsonify(response_data)


@bp.route('/auth/add_user', methods=['GET', 'POST'])
@login_required
def add_user():
    '''
    接口注释：超级管理员手动添加人员
    '''
    my_db = ToMongo('wavedevice')
    generate_log(request, db=my_db)
    params = request.get_json()
    user_name = params.get("userName", None)
    user_password = params.get("userPassword", None)
    user_account = params.get("userAccount", None)
    remark = params.get("remark", None)
    phone = params.get("phone", None)
    department_id = params.get("departmentId", None)

    accountlist = my_db.get_keyvalues("authority_user", "user_account")
    phonelist = my_db.get_keyvalues("authority_user", "user_phone")
    response_data = set_fail_result()

    if user_account in accountlist:
        response_data["errorCode"] = "USER_ACCOUNT_ALREADY_EXIST"
        response_data["errorCodeDesc"] = "账号已存在"
        return jsonify(response_data)

    if phone != "" and phone in phonelist:
        response_data["errorCode"] = "PHONE_ALREADY_EXIT"
        response_data["errorCodeDesc"] = "手机号已存在"
        return jsonify(response_data)

    user_id = uuid.uuid4().hex
    item = {}
    item['user_id'] = user_id
    item['user_account'] = user_account
    item['user_password'] = user_password
    item['open_id'] = None
    item['user_sex'] = None
    item['user_phone'] = phone
    item['user_real_name'] = user_name
    item['user_icon'] = None
    item['user_idCard'] = None
    item['remark'] = remark
    item['organization_id'] = '001611544223344645607'
    item['user_status'] = '1'
    item['create_time'] = datetime.now()
    item['last_modify_time'] = datetime.now()

    my_db.insert('authority_user', item)

    success_response = set_success_result()
    success_response['userId'] = user_id
    return jsonify(success_response)


@bp.route('/auth/set_user_role', methods=['GET', 'POST'])
@login_required
def set_user_role():
    '''
    接口注释：管理员设置用户关联角色
    '''
    my_db = ToMongo('wavedevice')
    params = request.get_json()
    user_id = params.get("userId", None)
    roleid_list = params.get("roleIdList", None)

    my_db.delete('authority_user_role_associate',
                 {'user_id': user_id},
                 False
                 )

    for roleid in roleid_list:
        my_db.insert('authority_user_role_associate',
                     {'user_id': user_id, 'role_id': roleid}
                     )

    response_data = set_success_result()
    return jsonify(response_data)


@bp.route('/auth/open_close_user', methods=['GET', 'POST'])
@login_required
def open_close_user():
    '''
    接口注释：开启关闭用户，实则修改用户的状态
    '''
    my_db = ToMongo('wavedevice')
    params = request.get_json()
    user_id = params.get("userId", None)
    userStatus = params.get("userStatus", None)

    my_db.update('authority_user',
                 {'user_id': user_id},
                 {'$set': {"user_status": str(userStatus)}}
                 )

    response_data = set_success_result()
    return jsonify(response_data)


@bp.route('/auth/manager_update_user_phone', methods=['GET', 'POST'])
@login_required
def manager_update_user_phone():
    '''
    接口注释：管理员在页面修改自己的手机号
    '''
    my_db = ToMongo('wavedevice')
    params = request.get_json()
    user_id = params.get("userId", None)
    newPhone = params.get("newPhone", None)

    phonelist = my_db.get_keyvalues("authority_user", "user_phone")
    response_data = set_fail_result()

    if newPhone in phonelist:
        response_data["errorCode"] = "PHONE_ALREADY_EXIT"
        response_data["errorCodeDesc"] = "手机号已存在"
        return jsonify(response_data)

    my_db.update('authority_user',
                 {'user_id': user_id},
                 {'$set': {"user_phone": newPhone}}
                 )

    success_response = set_success_result()
    return jsonify(success_response)


@bp.route('/auth/manager_update_user_pwd', methods=['GET', 'POST'])
@login_required
def manager_update_user_pwd():
    '''
    接口注释：管理员在详情页面重置密码
    '''
    my_db = ToMongo('wavedevice')
    params = request.get_json()
    user_id = params.get("userId", None)
    newPassword = params.get("newPassword", None)

    my_db.update('authority_user',
                 {'user_id': user_id},
                 {'$set': {"user_password": newPassword}}
                 )

    response_data = set_success_result()
    return jsonify(response_data)


@bp.route('/auth/update_user_pwd', methods=['GET', 'POST'])
@login_required
def update_user_pwd():
    '''
    接口注释：管理员在页面修改密码
    '''
    my_db = ToMongo('wavedevice')
    params = request.get_json()
    accesstoken = params.get('accessToken', None)
    oldPassword = params.get("oldPassword", None)
    newPassword = params.get("newPassword", None)

    current_user = g.user_account
    user_password = my_db.get_col('authority_user').find_one({'user_account': current_user})['user_password']

    if oldPassword != user_password:
        error_response = set_fail_result()
        error_response['errorCode'] = "WRONG_OLDPASSOWED"
        error_response['errorCodeDesc'] = "密码错误"
        return error_response

    my_db.update('authority_user',
                 {'user_account': current_user},
                 {'$set': {"user_password": newPassword}}
                 )

    response_data = set_success_result()
    return jsonify(response_data)


@bp.route('/auth/make_login_code', methods=['GET', 'POST'])
def generate_image_code():
    login_verification_code, login_base64_data = make_ver_code()
    # 返回图片和验证码
    response_data = {'requestId': uuid.uuid4().hex, 'requestStatus': "SUCCESS", 'timeUsed': 10,
                     'code': login_verification_code, 'image': login_base64_data}
    return jsonify(response_data)

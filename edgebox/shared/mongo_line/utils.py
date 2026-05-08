import uuid
from datetime import datetime
import jwt

from edgebox.shared.mongo_line.logcfg import log_map

key = "zkpfw*%$qjrfono@sdko34@%"


def set_fail_result():
    error_response = {}
    error_response['errorCode'] = "0"
    error_response['errorCodeDesc'] = "向平台修改盒子状态不成功，切换工作模式失败"
    error_response['exceptionCodeDesc'] = ""
    error_response['requestId'] = uuid.uuid4().hex
    error_response['requestStatus'] = "FAIL"
    error_response['timeUsed'] = 10
    return error_response


def set_success_result():
    response_data = {}
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 10
    return response_data


def generate_log(request, db):
    request_method = request.method
    totalurl = request.url
    try:
        ip = request.headers['X-Real-Ip']
    except Exception:
        ip = None
    params = request.get_json()
    access_token = params.get('accessToken', None)
    # 取消过期时间验证
    current_user = jwt.decode(access_token, key, options={'verify_exp': False})['user_account']

    logid = uuid.uuid4().hex
    create_time = datetime.now()
    user_item = db.get_col('authority_user').find_one({'user_account': current_user})
    user_id = user_item['user_id']
    user_real_name = user_item['user_real_name']
    department = "未分配部门"
    organization_id = user_item['organization_id']

    url = '/' + totalurl.split('/', 3)[-1]
    if url not in log_map.keys():
        return
    operate_menu = log_map[url]
    method = 0 if request_method == "POST" else 1
    item = {'create_time': create_time,
            'method': method,
            'organization_id': organization_id,
            'operate_menu': operate_menu,
            'url': url,
            'ip': ip,
            'department': department,
            'user_account': current_user,
            'log_id': logid,
            'user_name': user_real_name,
            'user_id': user_id}
    db.insert("user_logs", item)


def get_user_id(request, db):
    params = request.get_json()
    access_token = params.get('accessToken', None)
    user_id = None
    try:
        # 取消过期时间验证
        current_user = jwt.decode(access_token, key, options={'verify_exp': False})['user_account']
        user_item = db.get_col('authority_user').find_one({'user_account': current_user})
        user_id = user_item['user_id']
    except Exception as e:
        print(e)
    return user_id

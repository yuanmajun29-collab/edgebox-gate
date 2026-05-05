import jwt
from datetime import datetime, timedelta
import functools
from flask import g, request ,current_app,jsonify
from jwt import exceptions
from config import JWT_KEY

from utils.Utils import set_fail_result
import utils.logger as logger
import traceback

mainlogger = logger.getLogger('main')

# 构造header
headers = {
    'typ': 'jwt',
    'alg': 'HS256'
}

# 密钥
SALT = 'zkpfw*%$qjrfono@sdko34@%'


def create_token(user_account):
    # 构造payload
    payload = {
        'user_account': user_account,
        'exp': datetime.utcnow() + timedelta(days=7)  # 超时时间
    }
    result = jwt.encode(payload=payload, key=SALT, algorithm="HS256", headers=headers).decode('utf-8')
    return result


def verify_jwt(token, secret=None):
    """
    检验jwt
    :param token: jwt
    :param secret: 密钥
    :return: dict: payload
    """
    if not secret:
        secret = JWT_KEY

    try:
        payload = jwt.decode(token, secret, algorithms=['HS256'])
        return payload
    except exceptions.ExpiredSignatureError:  # 'token已失效'
        return 1
    except jwt.DecodeError:  # 'token认证失败'
        return 2
    except jwt.InvalidTokenError:  # '非法的token'
        return 3


def jwt_authentication():
    token = request.json.get('accessToken')
    g.user_account = None
    try:
        "判断token的校验结果"
        payload = jwt.decode(token, SALT, algorithms=['HS256'])
        "获取载荷中的信息赋值给g对象"
        g.user_account = payload.get('user_account')
    except exceptions.ExpiredSignatureError:  # 'token已失效'
        g.user_account = 1
    except jwt.DecodeError:  # 'token认证失败'
        g.user_account = 2
    except jwt.InvalidTokenError:  # '非法的token'
        g.user_account = 3


def login_required(f):
    '让装饰器装饰的函数属性不会变 -- name属性'
    '第1种方法,使用functools模块的wraps装饰内部函数'
    error_response = set_fail_result()

    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        jwt_authentication()
        try:
            if g.user_account == 1:
                error_response['errorCode'] = "INVALID_ACCESS_TOKEN"
                error_response['errorCodeDesc'] = "token已失效"
                return error_response
            elif g.user_account == 2:
                error_response['errorCode'] = "INVALID_ACCESS_TOKEN"
                error_response['errorCodeDesc'] = "token认证失败"
                return error_response
            elif g.user_account == 3:
                error_response['errorCode'] = "INVALID_ACCESS_TOKEN"
                error_response['errorCodeDesc'] = "非法的token"
                return error_response
            else:
                return f(*args, **kwargs)
        except BaseException as e:
            mainlogger.info('\n'+traceback.format_exc())
            error_response['errorCode'] = "INVALID_ACCESS_TOKEN"
            error_response['errorCodeDesc'] = "??ACCESS_TOKEN"
            return error_response

    return wrapper

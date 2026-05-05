import base64
import flask
import urllib.request
from http import HTTPStatus
from enum import IntEnum

Product = 'SE5'
Max_support_device_num = {
    "SE3": 4,
    "SE5": 16
}


class ErrorResponseType(IntEnum):
    # 成功的返回
    SUCCESS = 20091

    # 400 BAD_REQUEST
    URL_INVAL = 40090
    PARAM_ERROR = 40091
    REPORTED_PEROID_INVAL = 40092

    # 404 NOT_FOUND,比如group name没有的时候
    NOT_FOUND = 40491

    # 415 请求类型错误
    CONTENT_TYPE_ERROR = 41591

    # 500 NOT_IMPLEMENTED
    SERVER_ERROR = 50091

    DEVICE_ADD_ERROR = 40095
    DEVICE_UPDATE_ERROR = 40096
    DEVICE_DELETE_ERROR = 40097
    DEVICE_ADD_MAX_NUM_ERROR = 40098
    DEVICE_ADD_DUPLICATE_ERROR = 40099
    DEVICE_RTMP_ADDRESS_DUPLICATE_ERROR = 40010


def make_response(data=None, error=None, status_code=HTTPStatus.OK):
    ret = {}
    if data is None and error is None:
        raise ('at least one of data or error')
    if data is not None:
        ret['data'] = data
    if error is not None:
        ret['error'] = error
    res = flask.make_response(flask.jsonify(ret), status_code)
    res.headers['Access-Control-Allow-Origin'] = '*'
    res.headers['Access-Control-Allow-Methods'] = '*'
    res.headers['Access-Control-Allow-Headers'] = '*'
    return res


def make_success_response():
    return make_response('ok')


def make_error_response(error_type, message="", chinese_message=""):
    status_code = HTTPStatus(error_type.value // 100)
    if error_type == ErrorResponseType.URL_INVAL:
        message = 'Invalid URL address'
    elif error_type == ErrorResponseType.REPORTED_PEROID_INVAL:
        message = "Invalid reported_peroid"
    elif error_type == ErrorResponseType.DEVICE_ADD_MAX_NUM_ERROR:
        if Product == "SE3":
            message = 'Device must <= {}(photo = 0.5, other = 1.0),Or 10 photo devices'.format(
                Max_support_device_num[Product])
            chinese_message = '设备数量必须小于等于{}路(photo = 0.5, other = 1.0),或是支持10路图片流设备'.format(
                Max_support_device_num[Product])
        else:
            message = 'Device must <= {}(photo = 0.5, other = 1.0)'.format(Max_support_device_num[Product])
            chinese_message = '设备数量必须小于等于{}路(photo = 0.5, other = 1.0)'.format(
                Max_support_device_num[Product])
    elif error_type == ErrorResponseType.DEVICE_ADD_DUPLICATE_ERROR:
        message = 'Device URL duplicate Error,please check'
        chinese_message = '添加的设备Url重复，请检查'
    else:
        message = str(message) if message else ''

    return make_response(
        error={
            'code': error_type.value,
            'status': error_type.name,
            'message': str(message),
            'chinese_message': str(chinese_message)
        },
        status_code=status_code
    )


def make_old_response(data=None, error=None, status_code=HTTPStatus.OK):
    if data is None and error is None:
        raise ('at least one of data or error')
    if data is not None:
        ret = data
    if error is not None:
        ret = error
    return flask.make_response(flask.jsonify(ret), status_code)


def make_response_image_jpeg(image_binary):
    response = flask.make_response(image_binary)
    response.headers.set('Content-Type', 'image/jpeg')
    response.headers.set('Access-Control-Allow-Origin', '*')
    # response.headers.set('Content-Type', 'application/octet-stream')
    return response


def response_no_image(note=''):
    return make_response(
        error={'message': 'empty or broken image' + ((': ' + note) if note else '')},
        status_code=HTTPStatus.BAD_REQUEST
    )


def response_unsupport_content_type(note=''):
    return make_response(
        error={'message': 'unsupported content-type' + ((': ' + note) if note else '')},
        status_code=HTTPStatus.BAD_REQUEST
    )


def response_not_found(note=''):
    return make_response(
        error={'message': 'not found' + ((': ' + note) if note else '')},
        status_code=HTTPStatus.NOT_FOUND
    )


def response_bad_request(note=''):
    return make_response(
        error={'message': 'bad request' + ((': ' + note) if note else '')},
        status_code=HTTPStatus.BAD_REQUEST
    )


# def decode_base64_str(image_base64str):
#     image_base64str = image_base64str.split(',')[-1]
#     image_base64 = base64.b64decode(image_base64str)
#     nparr = np.fromstring(image_base64, np.uint8)
#     image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
#     return image

# def decode_binary(image_binary):

#     if isinstance(image_binary, bytes):
#         nparr = np.fromstring(image_binary, np.uint8)
#     else:
#         nparr = np.fromfile(image_binary, np.uint8)
#     image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
#     return image

def url_to_binary(url):
    with urllib.request.urlopen(url) as response:
        binary = response.read()
    return binary


def base64str_to_binary(image_base64str):
    image_base64str = image_base64str.split(',')[-1]
    binary = base64.b64decode(image_base64str)
    return binary

import uuid
import json



start = '#!'
version='01'
default_head_length='55'
default_head_type='01'
default_body_length='0000000000'
default_body_type_breath='03000'
default_body_type_edge='03001'
default_body_type_query='03002'
default_body_type_bind='03003'
default_body_type_device='03004'
default_body_type_face='03005'
default_body_type_sync='03006'   #同步数据下发给算法
default_device_change='03007'   #同步摄像头下发给算法
default_body_id='00000000000000000000000000000000'


def alg_reboot():
    body_length='%010d'%2
    body = '[]'
    result = start + version +default_head_length + default_head_type + body_length + default_body_type_sync + default_body_id + body
    return result

def pack_init_agreement(json_body):
    default_body_length = '%010d'%len(json_body)
    response = start + version + default_head_length + default_head_type + default_body_length + default_body_type_bind + default_body_id
    response += json_body
    return response

def pack_3004_agreement(json_body):
    default_body_length = '%010d'%len(json_body)
    response = start + version + default_head_length + default_head_type + default_body_length + default_body_type_device + default_body_id
    response += json_body
    return response

def pack_face_3005(json_body):
    default_body_length = '%010d'%len(json_body)
    response = start + version + default_head_length + default_head_type + default_body_length + default_body_type_face + default_body_id
    response += json_body
    return response

def pack_3007_agreement():
    body_length='%010d'%2
    body = '[]'
    result = start + version +default_head_length + default_head_type + body_length + default_device_change + default_body_id + body
    return result
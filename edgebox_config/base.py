"""
Default configuration shared by WaveGateMongo, web-ai-spirit, and wave-energy-station.

Products should ``from edgebox_config.base import *`` then set overrides (paths,
``BASE_INFO['web_version']``, ``NetAgreementType``, optional blueprint flags, etc.).
"""
import os

# Mongodb 基础配置
MONGODB_SETTINGS = {'db': 'flask', 'host': 'localhost', 'port': 27017, 'connect': True}

SECRET_KEY = "sdfsadfskrwerfj1233453345"

JWT_KEY = "zkpfw*%$qjrfono@sdko34@%"

SMS_CONFIG = {
    "sms_access_key": os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_ID", ""),
    "sms_access_key_secret": os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_SECRET", ""),
    "sms_sign_name": "威富视界",
    "alarm_templete_code": "SMS_254820804",
    "disk_templete_code": "SMS_264070015",
    "dynamic_templete_code": "SMS_264070015",
}

# 能耗/控制侧算法模型展示名（其它产品线未使用时可忽略）
MODEL_DICT = {
    1: '穿戴(A1)',
    2: '手持(B1)',
    3: '危险行为(C1)',
    4: '越界行为(C2)',
    5: '越界行为(C2)',
    6: '消防(D1)',
    7: '设备(E1)',
    8: '人脸(F1)',
    9: '摄像机内置算法(G1)',
}

BASE_INFO = {
    'web_version': 'v1.0.0.0',
    'equipment_serial_number': 'E25456245',
    'last_modify_time': None,
    'installation_position': '深圳威富公司',
    'equipment_name': '算力盒子',
    'organization_id': '001611544223344645607',
    'video_camera_num': 8,
    'algorithm_server_version': 'v3.0',
    'hardware_version': 'v2.0.01',
    'create_time': None,
    'equipment_model': 'WF-EC06',
}

BASE_PATH = "/data/events/"

EMERGENCY_IMG_PATH = BASE_PATH + "emergencyimg/"
PERSON_IMG_URL = BASE_PATH + "faceimg/"
FACE_IDENT_URL = BASE_PATH + "faceidentification/"
SYSTEMLOGO_URL = BASE_PATH + "systemlogo/"
SYSTEM_CFG_URL = BASE_PATH + "systemcfg/"

UNDERLAY_URL = "/data/ebox/alg/model/OcuuPass/"

PLATFORM_MINIO_URL = 'http://internal.minio.wavewisdom-bj.com:9090'

NetAgreementType = "http"

DISK_PATH = "/dev/mmcblk0p7"

SHELL_DIR = "/bm_bin/"

CURVE_CONFIG = {"use": 0, "sync": 0}

MESSAGE_RADAR_VEHICLES = "message_radar_vehicles"
MESSAGE_CAMERA_VEHICLES = "message_camera_vehicles"
MESSAGE_CAMERA_PEDESTRIAN = "message_camera_pedestrian"

CROSSING_CONFIG = {"use": 0, "sync": 0}
PEDESTRIAN_ALG_NUM = '1'
VEHICLE_ALG_NUM = '165'

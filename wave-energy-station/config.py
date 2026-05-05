import os

MONGODB_SETTINGS = {
    'db': 'flask',
    'host': 'localhost',
    'port': 27017,
    'connect': True,
}
SECRET_KEY = "sdfsadfskrwerfj1233453345"

JWT_KEY = "zkpfw*%$qjrfono@sdko34@%"

MODEL_DICT = {
    1: '穿戴(A1)',
    2: '手持(B1)',
    3: '危险行为(C1)',
    4: '越界行为(C2)',
    5: '越界行为(C2)',
    6: '消防(D1)',
    7: '设备(E1)',
    8: '人脸(F1)',
    9: '摄像机内置算法(G1)'
}

SMS_CONFIG = {
    "sms_access_key": os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_ID", ""),
    "sms_access_key_secret": os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_SECRET", ""),
    "sms_sign_name": "威富视界",
    "alarm_templete_code": "SMS_254820804",
    "disk_templete_code": "SMS_264070015",
    "dynamic_templete_code": "SMS_264070015"
}

BASE_INFO = {'equipment_serial_number': 'E25456245',
             'web_version': 'v1.0.0.7',
             'last_modify_time': None,
             'installation_position': '深圳威富公司',
             'equipment_name': '算力盒子',
             'organization_id': '001611544223344645607',
             'video_camera_num': 8,
             'algorithm_server_version': 'v3.0',
             'hardware_version': 'v2.0.01',
             'create_time': None,
             'equipment_model': 'WF-EC06'}

EMERGENCY_IMG_PATH = "/data/events/emergencyimg/"
PERSON_IMG_URL = "/data/events/faceimg/"  # 人脸库图片存储路径
FACE_IDENT_URL = "/data/events/faceidentification/"  # 人脸库图片提取的人脸特征存储路径
SYSTEMLOGO_URL = "/data/events/systemlogo/"  # 系统logo路径
SYSTEM_CFG_URL = "/data/events/systemcfg/"

PLATFORM_MINIO_URL = 'http://internal.minio.wavewisdom-bj.com:9090'  # 云平台minio地址

NetAgreementType = "http"  # 网络通信协议  http or https

DISK_PATH = "/dev/mmcblk0p7"

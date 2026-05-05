import os

#Mongodb基础配置
MONGODB_SETTINGS = {'db': 'flask','host': 'localhost','port': 27017,'connect': True}

SECRET_KEY = "sdfsadfskrwerfj1233453345"

#jwt认证秘钥
JWT_KEY = "zkpfw*%$qjrfono@sdko34@%" 

#短信网管默认配置
SMS_CONFIG = {
              "sms_access_key": os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_ID", ""),
              "sms_access_key_secret": os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_SECRET", ""),
              "sms_sign_name":"威富视界",
              "alarm_templete_code":"SMS_254820804",
              "disk_templete_code":"SMS_264070015"}

BASE_INFO = {   'web_version': 'v2.3.5.5',   #软件后台版本
                'equipment_serial_number': 'E25456245',              
                'last_modify_time': None, 
                'installation_position': '深圳威富公司', 
                'equipment_name': '算力盒子', 
                'organization_id': '001611544223344645607', 
                'video_camera_num': 8, 
                'algorithm_server_version': 'v3.0', 
                'hardware_version': 'v2.0.01', 
                'create_time': None, 
                'equipment_model': 'WF-EC06'}

#图片存储根路径
BASE_PATH = "/data/events/"

#告警图片存储路径
EMERGENCY_IMG_PATH = BASE_PATH + "emergencyimg/"  

#人脸库图片存储路径
PERSON_IMG_URL = BASE_PATH + "faceimg/"   

#人脸库图片提取的人脸特征存储路径
FACE_IDENT_URL = BASE_PATH + "faceidentification/"   

#系统logo路径
SYSTEMLOGO_URL = BASE_PATH + "systemlogo/"   

#导出配置路径
SYSTEM_CFG_URL = BASE_PATH + "systemcfg/"    

#摄像机底图路径
UNDERLAY_URL = "/data/ebox/alg/model/OcuuPass/"    

#云平台默认minio地址
PLATFORM_MINIO_URL = 'http://internal.minio.wavewisdom-bj.com:9090' 

#网络通信协议  http or https
NetAgreementType = "http"

#系统文件的磁盘分区
DISK_PATH = "/dev/mmcblk0p7"

#系统脚本路径
SHELL_DIR = "/bm_bin/"  

# 弯道配置
CURVE_CONFIG = {"use" :0,"sync":0}

# 消息类型分类
MESSAGE_RADAR_VEHICLES = "message_radar_vehicles"
MESSAGE_CAMERA_VEHICLES = "message_camera_vehicles"
MESSAGE_CAMERA_PEDESTRIAN = "message_camera_pedestrian"

# 交通灯配置
CROSSING_CONFIG = {"use" :0,"sync":0}
PEDESTRIAN_ALG_NUM = '1' #摄像机遮挡
VEHICLE_ALG_NUM = '165'


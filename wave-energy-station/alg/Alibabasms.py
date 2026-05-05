from config import SMS_CONFIG

# 以下是发送阿里云短信的库
from alibabacloud_dysmsapi20170525.client import Client as Dysmsapi20170525Client
from alibabacloud_dysmsapi20170525 import models as dysmsapi_20170525_models
from alibabacloud_tea_util import models as util_models
from alibabacloud_tea_util.client import Client as UtilClient
from Tea.model import TeaModel
from alibabacloud_credentials.client import Client as CredentialClient
from typing import Dict, Any, BinaryIO

import uuid
import json
from utils.CheckdeviceStatus import CheckDeviceStatus
from utils.db import ToMongo
from datetime import datetime
from threading import Thread

delivery_sample = {"alarm_datetime": "", "alarm_content": ""}


class GlobalParameters(TeaModel):
    def __init__(
            self,
            headers: Dict[str, str] = None,
            queries: Dict[str, str] = None,
    ):
        self.headers = headers
        self.queries = queries

    def validate(self):
        pass

    def to_map(self):
        _map = super().to_map()
        if _map is not None:
            return _map

        result = dict()
        if self.headers is not None:
            result['headers'] = self.headers
        if self.queries is not None:
            result['queries'] = self.queries
        return result

    def from_map(self, m: dict = None):
        m = m or dict()
        if m.get('headers') is not None:
            self.headers = m.get('headers')
        if m.get('queries') is not None:
            self.queries = m.get('queries')
        return self


class Config(TeaModel):
    """
    Model for initing client
    """

    def __init__(
            self,
            access_key_id: str = None,
            access_key_secret: str = None,
            security_token: str = None,
            protocol: str = None,
            method: str = None,
            region_id: str = None,
            read_timeout: int = None,
            connect_timeout: int = None,
            http_proxy: str = None,
            https_proxy: str = None,
            credential: CredentialClient = None,
            endpoint: str = None,
            no_proxy: str = None,
            max_idle_conns: int = None,
            network: str = None,
            user_agent: str = None,
            suffix: str = None,
            socks_5proxy: str = None,
            socks_5net_work: str = None,
            endpoint_type: str = None,
            open_platform_endpoint: str = None,
            type: str = None,
            signature_version: str = None,
            signature_algorithm: str = None,
            global_parameters: GlobalParameters = None,
            key: str = None,
            cert: str = None,
            ca: str = None,
    ):
        # accesskey id
        self.access_key_id = access_key_id
        # accesskey secret
        self.access_key_secret = access_key_secret
        # security token
        self.security_token = security_token
        # http protocol
        self.protocol = protocol
        # http method
        self.method = method
        self.region_id = region_id
        # read timeout
        self.read_timeout = read_timeout
        # connect timeout
        self.connect_timeout = connect_timeout
        # http proxy
        self.http_proxy = http_proxy
        # https proxy
        self.https_proxy = https_proxy
        # credential
        self.credential = credential
        # endpoint
        self.endpoint = endpoint
        # proxy white list
        self.no_proxy = no_proxy
        # max idle conns
        self.max_idle_conns = max_idle_conns
        # network for endpoint
        self.network = network
        # user agent
        self.user_agent = user_agent
        # suffix for endpoint
        self.suffix = suffix
        # socks5 proxy
        self.socks_5proxy = socks_5proxy
        # socks5 network
        self.socks_5net_work = socks_5net_work
        # endpoint type
        self.endpoint_type = endpoint_type
        # OpenPlatform endpoint
        self.open_platform_endpoint = open_platform_endpoint
        # credential type
        self.type = type
        # Signature Version
        self.signature_version = signature_version
        # Signature Algorithm
        self.signature_algorithm = signature_algorithm
        # Global Parameters
        self.global_parameters = global_parameters
        # privite key for client certificate
        self.key = key
        # client certificate
        self.cert = cert
        # server certificate
        self.ca = ca

    def validate(self):
        if self.global_parameters:
            self.global_parameters.validate()

    def to_map(self):
        _map = super().to_map()
        if _map is not None:
            return _map

        result = dict()
        if self.access_key_id is not None:
            result['accessKeyId'] = self.access_key_id
        if self.access_key_secret is not None:
            result['accessKeySecret'] = self.access_key_secret
        if self.security_token is not None:
            result['securityToken'] = self.security_token
        if self.protocol is not None:
            result['protocol'] = self.protocol
        if self.method is not None:
            result['method'] = self.method
        if self.region_id is not None:
            result['regionId'] = self.region_id
        if self.read_timeout is not None:
            result['readTimeout'] = self.read_timeout
        if self.connect_timeout is not None:
            result['connectTimeout'] = self.connect_timeout
        if self.http_proxy is not None:
            result['httpProxy'] = self.http_proxy
        if self.https_proxy is not None:
            result['httpsProxy'] = self.https_proxy
        if self.credential is not None:
            result['credential'] = self.credential
        if self.endpoint is not None:
            result['endpoint'] = self.endpoint
        if self.no_proxy is not None:
            result['noProxy'] = self.no_proxy
        if self.max_idle_conns is not None:
            result['maxIdleConns'] = self.max_idle_conns
        if self.network is not None:
            result['network'] = self.network
        if self.user_agent is not None:
            result['userAgent'] = self.user_agent
        if self.suffix is not None:
            result['suffix'] = self.suffix
        if self.socks_5proxy is not None:
            result['socks5Proxy'] = self.socks_5proxy
        if self.socks_5net_work is not None:
            result['socks5NetWork'] = self.socks_5net_work
        if self.endpoint_type is not None:
            result['endpointType'] = self.endpoint_type
        if self.open_platform_endpoint is not None:
            result['openPlatformEndpoint'] = self.open_platform_endpoint
        if self.type is not None:
            result['type'] = self.type
        if self.signature_version is not None:
            result['signatureVersion'] = self.signature_version
        if self.signature_algorithm is not None:
            result['signatureAlgorithm'] = self.signature_algorithm
        if self.global_parameters is not None:
            result['globalParameters'] = self.global_parameters.to_map()
        if self.key is not None:
            result['key'] = self.key
        if self.cert is not None:
            result['cert'] = self.cert
        if self.ca is not None:
            result['ca'] = self.ca
        return result

    def from_map(self, m: dict = None):
        m = m or dict()
        if m.get('accessKeyId') is not None:
            self.access_key_id = m.get('accessKeyId')
        if m.get('accessKeySecret') is not None:
            self.access_key_secret = m.get('accessKeySecret')
        if m.get('securityToken') is not None:
            self.security_token = m.get('securityToken')
        if m.get('protocol') is not None:
            self.protocol = m.get('protocol')
        if m.get('method') is not None:
            self.method = m.get('method')
        if m.get('regionId') is not None:
            self.region_id = m.get('regionId')
        if m.get('readTimeout') is not None:
            self.read_timeout = m.get('readTimeout')
        if m.get('connectTimeout') is not None:
            self.connect_timeout = m.get('connectTimeout')
        if m.get('httpProxy') is not None:
            self.http_proxy = m.get('httpProxy')
        if m.get('httpsProxy') is not None:
            self.https_proxy = m.get('httpsProxy')
        if m.get('credential') is not None:
            self.credential = m.get('credential')
        if m.get('endpoint') is not None:
            self.endpoint = m.get('endpoint')
        if m.get('noProxy') is not None:
            self.no_proxy = m.get('noProxy')
        if m.get('maxIdleConns') is not None:
            self.max_idle_conns = m.get('maxIdleConns')
        if m.get('network') is not None:
            self.network = m.get('network')
        if m.get('userAgent') is not None:
            self.user_agent = m.get('userAgent')
        if m.get('suffix') is not None:
            self.suffix = m.get('suffix')
        if m.get('socks5Proxy') is not None:
            self.socks_5proxy = m.get('socks5Proxy')
        if m.get('socks5NetWork') is not None:
            self.socks_5net_work = m.get('socks5NetWork')
        if m.get('endpointType') is not None:
            self.endpoint_type = m.get('endpointType')
        if m.get('openPlatformEndpoint') is not None:
            self.open_platform_endpoint = m.get('openPlatformEndpoint')
        if m.get('type') is not None:
            self.type = m.get('type')
        if m.get('signatureVersion') is not None:
            self.signature_version = m.get('signatureVersion')
        if m.get('signatureAlgorithm') is not None:
            self.signature_algorithm = m.get('signatureAlgorithm')
        if m.get('globalParameters') is not None:
            temp_model = GlobalParameters()
            self.global_parameters = temp_model.from_map(m['globalParameters'])
        if m.get('key') is not None:
            self.key = m.get('key')
        if m.get('cert') is not None:
            self.cert = m.get('cert')
        if m.get('ca') is not None:
            self.ca = m.get('ca')
        return self


class SendSmsResqueset():
    def __init__(self):
        self.my_db = ToMongo('wavedevice')
        config_col = self.my_db.get_col("odin_advise_sms_config").find()
        if config_col.count() != 0:
            config_param = config_col[0]
            self.access_key = config_param['sms_access_key']
            self.sms_access_key_secret = config_param['sms_access_key_secret']
            self.sms_sign_name = config_param['sms_sign_name']
            self.alarm_templete_code = config_param['alarm_templete_code']
            self.disk_templete_code = config_param['disk_templete_code']
        else:
            self.access_key = SMS_CONFIG['sms_access_key']
            self.sms_access_key_secret = SMS_CONFIG['sms_access_key_secret']
            self.sms_sign_name = SMS_CONFIG['sms_sign_name']
            self.alarm_templete_code = SMS_CONFIG['alarm_templete_code']
            self.disk_templete_code = SMS_CONFIG['disk_templete_code']

        self.dynamic_templete_code = SMS_CONFIG['dynamic_templete_code']
        config = Config(
            access_key_id=self.access_key,
            access_key_secret=self.sms_access_key_secret,
            endpoint='dysmsapi.aliyuncs.com')
        self.clientsms = Dysmsapi20170525Client(config)
        self.delivery_task = []

    def get_sms_config(self):
        config_col = self.my_db.get_col("odin_advise_sms_config").find()
        if config_col.count() != 0:
            config_param = config_col[0]
            self.access_key = config_param['sms_access_key']
            self.sms_access_key_secret = config_param['sms_access_key_secret']
            self.sms_sign_name = config_param['sms_sign_name']
            self.alarm_templete_code = config_param['alarm_templete_code']
            self.disk_templete_code = config_param['disk_templete_code']
            config = Config(
                access_key_id=self.access_key,
                access_key_secret=self.sms_access_key_secret,
                endpoint='dysmsapi.aliyuncs.com')
            self.clientsms = Dysmsapi20170525Client(config)

    def trigger_condition_switch(self, trigger_condition):
        '''
        触发条件判断
        '''
        trigger_list = trigger_condition.split(';')[:-1]
        result = {}
        for item in trigger_list:
            tmp = item.split('=')
            if tmp[1] != '':
                result[tmp[0]] = tmp[1]
        return result

    def delivery_content_switch(self, delivery_content, msg):
        '''
        投递任务格式转换
        '''
        content_list = delivery_content.split(',')
        delivery_res = delivery_sample.copy()
        if '1' in content_list:
            delivery_res['alarm_datetime'] = msg['time']
        if '6' in content_list:
            delivery_res['alarm_content'] = msg['modelName']
        if '4' in content_list:
            msg_str4 = "，布控任务：" + msg['controlName']
            delivery_res['alarm_content'] += msg_str4
        if '3' in content_list:
            msg_str3 = "，位置：" + msg['adress']
            delivery_res['alarm_content'] += msg_str3
        if '2' in content_list:
            msg_str2 = "，摄像机名称：" + msg['deviceName']
            delivery_res['alarm_content'] += msg_str2

        return delivery_res

    def get_sms_delivery(self):
        '''
        从数据库从新拉取短信投递任务
        '''
        delivery_col = self.my_db.get_col("odin_advise_sms_delivery").find()
        res = []
        for delivery_item in delivery_col:
            item = {}
            delivery_content = delivery_item['delivery_content']
            delivery_phones = delivery_item['delivery_phones'].split(',')
            trigger_condition = delivery_item['trigger_condition']
            trigger_condition_dict = self.trigger_condition_switch(trigger_condition)
            item['delivery_content'] = delivery_content
            item['trigger_condition'] = trigger_condition_dict
            item['delivery_phones'] = delivery_phones
            item['delivery_id'] = delivery_item['sms_delivery_id']
            res.append(item)
        self.delivery_task = res

    def insert_delivery_data(self, msg, param, delivery_content):
        item = {}
        now = datetime.now()
        item['control_name'] = msg['controlName']
        item['device_name'] = msg['deviceName']
        item['model_path'] = msg['modelPath']

        item['delivery_record_id'] = uuid.uuid4().hex
        item['delivery_time'] = now.strftime("%Y-%m-%d %H:%M:%S")
        item['emergency_time'] = msg['time']

        item['delivery_status'] = param['delivery_status']
        item['delivery_id'] = param['delivery_id']
        item['create_time'] = now
        item['update_time'] = now
        item['emergency_record_id'] = param['emergency_record_id']
        item['model_name'] = msg['modelPath']
        item['emergency_position'] = msg['adress']
        item['advise_content'] = delivery_content
        item['delivery_phones'] = param['delivery_phones']
        item['organization_id'] = param['organization_id']

        self.my_db.insert("odin_advise_sms_delivery_record", item)

    def send_sms_thread(self, msg, param_dict):
        if self.delivery_task:
            for delivery in self.delivery_task:
                delivery_thread = Thread(target=self.send_sms_delivery, args=[delivery, msg, param_dict])
                delivery_thread.start()

    def send_sms_delivery(self, delivery, msg, param_dict):
        '''
        触发条件判断，然后发送短信。
        '''

        trigger_condition = delivery['trigger_condition']
        if "controlName" in trigger_condition.keys():
            if msg['controlName'] not in trigger_condition['controlName']:
                return
        if "deviceName" in trigger_condition.keys():
            if msg['deviceName'] not in trigger_condition['deviceName']:
                return
        if "modelPath" in trigger_condition.keys():
            if msg['modelPath'] not in trigger_condition['modelPath']:
                return
        for phone_number in delivery['delivery_phones']:
            delivery_content = self.delivery_content_switch(delivery['delivery_content'], msg)
            send_sms_request = dysmsapi_20170525_models.SendSmsRequest(out_id=uuid.uuid1(),
                                                                       phone_numbers=phone_number,
                                                                       template_code=self.alarm_templete_code,
                                                                       sign_name=self.sms_sign_name,
                                                                       template_param=json.dumps(delivery_content))
            try:
                response = self.clientsms.send_sms_with_options(send_sms_request, util_models.RuntimeOptions())
                statusCode = response.code
            except Exception as e:
                print('Error : 告警短信发送失败,请检查网络！ ', e)
                statusCode = None
            delivery_status = '1' if statusCode == 'OK' else '2'
            delivery_id = delivery['delivery_id']
            param = {'delivery_status': delivery_status,
                     'delivery_id': delivery_id,
                     'emergency_record_id': param_dict['emergency_record_id'],
                     'delivery_phones': phone_number,
                     'organization_id': param_dict['organization_id']}
            self.insert_delivery_data(msg, param, delivery_content)

    def resend_sms_delivery(self, item):
        advise_content = item['advise_content']
        delivery_phones = item['delivery_phones']
        delivery_id = item['delivery_id']
        if not delivery_phones:
            return
        send_sms_request = dysmsapi_20170525_models.SendSmsRequest(out_id=uuid.uuid1(),
                                                                   phone_numbers=delivery_phones,
                                                                   template_code=self.alarm_templete_code,
                                                                   sign_name=self.sms_sign_name,
                                                                   template_param=json.dumps(advise_content))
        try:
            response = self.clientsms.send_sms_with_options(send_sms_request, util_models.RuntimeOptions())
            statusCode = response.code
        except Exception as e:
            print('Error : 告警短信发送失败,请检查网络！ ', e)
            statusCode = None
        delivery_status = '1' if statusCode == 'OK' else '2'
        return delivery_status

    def send_sms_disk(self, msg, phone_list):
        '''
        发送磁盘空间告警
        '''
        for phone_number in phone_list:
            send_sms_request = dysmsapi_20170525_models.SendSmsRequest(out_id=uuid.uuid1(),
                                                                       phone_numbers=phone_number,
                                                                       template_code=self.disk_templete_code,
                                                                       sign_name=self.sms_sign_name,
                                                                       template_param=json.dumps(msg))
            try:
                response = self.clientsms.send_sms_with_options(send_sms_request, util_models.RuntimeOptions())
                print(response.code, '发送磁盘告警成功！')
            except Exception as e:
                print('Error : 磁盘空间短信告警发送失败,请检查网络！ ', e)

    def send_sms_dynamic(self,msg,phone_list):
        '''
        发送485设备告警
        '''
        for phone_number in phone_list:
            send_sms_request = dysmsapi_20170525_models.SendSmsRequest(out_id=uuid.uuid1(),
                                                                       phone_numbers=phone_number,
                                                                       template_code=self.dynamic_templete_code,
                                                                       sign_name=self.sms_sign_name,
                                                                       template_param=json.dumps(msg))
            try:
                response = self.clientsms.send_sms_with_options(send_sms_request, util_models.RuntimeOptions())
                print(response.code, '485设备告警成功!')
            except Exception as e:
                print('Error : 485设备告警发送失败,请检查网络！ ', e)


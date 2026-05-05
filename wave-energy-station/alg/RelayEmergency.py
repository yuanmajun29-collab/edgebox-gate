import requests
import json
from utils.db import ToMongo
import utils.logger as logger
from threading import Thread
from datetime import datetime
import uuid
from .redis_connect import redis_database

mainlogger = logger.getLogger('main')


class Sendwebrequest():
    def __init__(self):
        self.my_db = ToMongo('wavedevice')
        self.delivery_task = []
        self.re_pool = redis_database

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

    def delivery_content_switch(self, relay_content, msg):
        '''
        投递任务格式转换
        '''
        content_list = relay_content.split(',')
        relay_res = dict()
        relay_res['emergencyId'] = msg['emergencyId']
        if '1' in content_list:
            relay_res['time'] = msg['time']
        if '2' in content_list:
            relay_res['deviceName'] = msg['deviceName']
            relay_res['deviceId'] = msg['deviceId']
        if '3' in content_list:
            relay_res['emergencyAddress'] = msg['adress']
            relay_res['positionId'] = msg['positionId']
        if '4' in content_list:
            relay_res['controlName'] = msg['controlName']
            relay_res['controlId'] = msg['controlId']
        if '5' in content_list:
            relay_res['modelName'] = msg['modelPath']
        if '6' in content_list:
            relay_res['modelPath'] = msg['modelPath']
            relay_res['modelId'] = msg['modelId']
        relay_copy = relay_res.copy()
        if '7' in content_list:
            relay_res['emergencyImageUrls'] = msg['emergencyImageUrls']
            relay_res['emergencyImage'] = msg['emergencyImage']
            relay_copy['emergencyImageUrls'] = msg['emergencyImageUrls']
            relay_copy['emergencyImage'] = ""
        return relay_res, relay_copy

    def get_webhook_delivery(self):
        '''
        从数据库从新拉取告警转发任务
        '''
        relay_col = self.my_db.get_col("odin_advise_webhook_delivery").find({}, {'_id': 0})
        res = []
        for relay_item in relay_col:
            item = {}
            trigger_condition = relay_item['trigger_condition']
            trigger_condition_dict = self.trigger_condition_switch(trigger_condition)
            relay_item['trigger_condition'] = trigger_condition_dict
            res.append(relay_item)
        self.delivery_task = res

    def insert_delivery_record(self, msg, param, delivery_content):
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
        item['emergency_image_urls'] = msg['emergencyImageUrls']
        item['organization_id'] = param['organization_id']
        self.my_db.insert("odin_advise_webhook_delivery_record", item)

    def send_webhook_thread(self, msg, param_dict):
        if self.delivery_task:
            for delivery in self.delivery_task:
                delivery_thread = Thread(target=self.send_web_delivery, args=[delivery, msg, param_dict])
                delivery_thread.start()

    def send_web_delivery(self, delivery, msg, param):
        '''
        触发条件判断，然后转发告警。
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
        relay_content, relay_copy = self.delivery_content_switch(delivery['delivery_content'], msg)
        mainlogger.info('--告警转发内容 :   %s' % relay_copy)
        weburl = delivery['webhook_delivery_address']
        # headers = json.loads(delivery['request_headers'])
        headers = {'Content-Type': 'application/json'}
        request_type = delivery['request_type']

        try:

            if request_type == "POST":
                response = requests.post(url=weburl, data=json.dumps(relay_content), headers=headers, verify=False)
            elif request_type == "GET":
                response = requests.get(url=weburl, data=json.dumps(relay_content), headers=headers, verify=False)

            if response.status_code == requests.codes.ok:
                relay_status = '1'
                mainlogger.info("==告警转发成功==")
            else:
                relay_status = '2'
                mainlogger.info("==告警转发失败,result code:{}==".format(response.status_code))

        except Exception as e:
            relay_status = '2'
            mainlogger.info("==告警转发出现错误,请检查网络或转发地址是否正确！error:%s" % e)

        delivery_id = delivery['webhook_delivery_id']
        param = {'delivery_status': relay_status,
                 'delivery_id': delivery_id,
                 'emergency_record_id': param['emergency_record_id'],
                 'organization_id': param['organization_id']}
        self.insert_delivery_record(msg, param, relay_copy)

import time
from threading import Thread,Timer
import paho.mqtt.client as mqtt

import Utils.logger as logger
import Utils.glv as glv
from Utils.db import ToMongo

mainlogger = logger.getLogger('main')

def on_connect(client, obj, flags, rc):
    print("connected rc: " + str(rc))


def on_publish(client, obj, mid):
    print("mid: " + str(mid))


def on_disconnect(client, userdata, rc):
    print("disconnect")

            
class MqttInstance:

    def __init__(self):
        self.client = None
        self.mqtt_init()
        self.init_pop_state()

    def mqtt_init(self):
        _client_id = time.strftime('%Y%m%d%H%M%S', time.localtime(time.time()))

        try:
            self.client = mqtt.Client(_client_id, transport='tcp')        
            self.client.username_pw_set("", "")
            self.client.connect('127.0.0.1', 1883, 60)  # 此处端口默认为1883，通信端口期keepalive默认60
            self.client.loop_start()
        except Exception as e:
            mainlogger.info('Error : %s'%e)
            return

    def init_pop_state(self):
        '''
        初始化弹窗状态 0弹 1不弹
        '''
        my_db = ToMongo('wavedevice')
        setting_col = my_db.get_col('system_setting')
        query = {'file_type':0}
        item = setting_col.find_one(query)

        try:
            pop_state = item['emergency_pop_state'] 
        except:
            pop_state = 0
        glv.set_value('pop_state',pop_state)
        return
        



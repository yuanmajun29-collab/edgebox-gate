
import requests
import json
import uuid
import time
from datetime import datetime
import logger as logger
from Utils.db import ToMongo
from Utils.CheckdeviceStatus import CheckDeviceStatus
from threading import Timer,Thread


mainlogger = logger.getLogger('main')

class VoiceBoxUtils:

    token = ""
    def __init__(self,url,account,password,volume):

        self.url = url
        self.account = account
        self.password = password
        self.volume = volume
    
    def login(self):

        url_total = self.url + "/api/v29+/auth?name=" + self.account + "&password=" + self.password + "&force=1"
        result = requests.get(url_total,timeout=2)
        jsonobject = result.json()
        token = jsonobject.get("token")
        self.token = token
        mainlogger.info("token :%s"%token)
        return jsonobject

    def refresh(self):
        param = {'Authorization':self.token}
        header = {"Content-Type": "application/json"}
        result = requests.get(self.url+"/api/v29+/auth/refresh?",json.dumps(param),headers=header)
        mainlogger.info('refresh:%s'%result)
        return result

    def getterminalinfo(self):
        '''
        获取服务音频终端列表
        '''
        item = {}
        item['token'] = self.token
        item['data'] = ""
        item['company'] = "BL"
        item['return_message'] = ""
        item['result'] = "0"
        item['actioncode'] = "c2ls_get_server_terminals_status"
        item['sign'] = ""
        header = {"Content-Type": "application/json"}
        result = requests.put(self.url + "/api/v29+/ws/forwarder", json.dumps(item),headers=header,verify=False)
        mainlogger.info('getterminalinfo: %s'%result)
        return result

    def playTTS(self,endPointsList,content):
        '''
        播放tts语音
        '''
        taskid = uuid.uuid4().hex
        params = {}
        data = {}
        data['EndPointsAdditionalProp'] = ""
        data['EndPointsList'] = endPointsList
        data['TTSEngineName'] = "Microsoft Huihui Desktop - Chinese (Simplified)"
        data['TTSSpeed'] = 5
        data['RepeatTime'] = 1
        data['TaskID'] = "{%s}"%taskid
        data['TaskName'] = "文本_" + datetime.now().strftime("%Y%m%d%H%M%S")
        data['TaskPriority'] = 70
        data['TextContent'] = content
        data['Volume'] = self.volume

        params['token'] = self.token
        params['data'] = data
        params['company'] = "BL"
        params['return_message'] = ""
        params['result'] = 200
        params['actioncode'] = "c2ls_server_tts_mp3_play"
        params['sign'] = ""
        header = {"Content-Type": "application/json"}
        result = requests.put(self.url + "/api/v29+/ws/forwarder", json.dumps(params),headers=header,verify=False)
        mainlogger.info('playTTS: %s'%result)
        return result


    def getTTS(self):
        '''
        获取tts引擎
        '''
        params = {}
        params['token'] = self.token
        params['data'] = ""
        params['company'] = "BL"
        params['return_message'] = ""
        params['result'] = "0"
        params['actioncode'] = "c2ls_get_tts_engine_info"
        params['sign'] = ""
        header = {"Content-Type": "application/json"}
        result = requests.put(self.url + "/api/v29+/ws/forwarder", json.dumps(params),headers=header,verify=False)
        mainlogger.info('getTTS: %s'%result)
        return result

    def getMusicList(self):
        '''
        获取音乐列表
        '''
        params = {}
        params['token'] = self.token
        params['data'] = ""
        params['company'] = "BL"
        params['return_message'] = ""
        params['result'] = "200"
        params['actioncode'] = "c2ls_get_server_music_list"
        params['sign'] = ""
        header = {"Content-Type": "application/json"}
        result = requests.put(self.url + "/api/v29+/ws/forwarder", json.dumps(params),headers=header,verify=False)
        mainlogger.info('getMusicList: %s'%result)
        return result

    def playMusic(self,endPointIDsList,musicIDsList):
        '''
        播放音乐
        '''
        params = {}
        data = {}
        data['EndPointsAdditionalProp'] = ""
        data['EndPointIDs'] = endPointIDsList
        data['MusicIDs'] = musicIDsList
        data['MusicGroupIDs'] = []
        data['EndPointGroupIDs'] = []
        data['TaskID'] = uuid.uuid4().hex
        data['TaskName'] = "播放_" + + datetime.now().strftime("%Y%m%d%H%M%S")
        data['PlayMode'] = "normal_mode"
        data['Priority'] = "70"
        data['Volume'] = self.volume

        params['token'] = self.token
        params['data'] = data
        params['company'] = "BL"
        params['return_message'] = ""
        params['result'] = "0"
        params['actioncode'] = "c2ls_mobile_terminal_damand_music"
        params['sign'] = ""
        header = {"Content-Type": "application/json"}
        result = requests.put(self.url + "/api/v29+/ws/forwarder", json.dumps(params),headers=header)
        mainlogger.info('playMusic: %s'%result)
        return result

class LingsSound:


    def __init__(self,client_url,server_url,sound_no,volume):

        self.client_url = client_url
        self.server_url = server_url
        self.sound_no = sound_no
        self.volume = volume

    def login(self,account,password):
        '''
        菱声音响登录接口
        '''
        login_url = "%s/api/users/login"%(self.server_url)
        params = dict()
        data = dict()
        data['email'] = "ls20@%s"%account
        data['password'] = password
        params['user'] = data
        header = {"Content-Type": "application/json"}
        result = requests.post(login_url,headers=header,data=json.dumps(params),timeout=2).json()       
        return result

    def getTerminalinfo(self,token):
        '''
        菱声获取设备终端接口
        '''
        url = "%s/api/devices?page=1&pageSize=10000"%(self.server_url)
        header = {"Content-Type": "application/json",'Authorization':"Bearer " + token}
        result = requests.get(url,headers=header,timeout=2).json()
        return result

    def playTTS(self,content):
        mp3_url = "%s/tts_xf.single?text=%s&voice_name=xiaoyan&speed=50&volume=100"%(self.server_url,content)
        data = dict()
        data['sn'] = self.sound_no
        data['type'] = 'req'
        data['name'] = 'songs_queue_append'
        params = dict()
        params['tid'] = uuid.uuid4().hex
        params['vol'] = self.volume
        params['urls'] = [{'name':'告警语音.mp3','uri':mp3_url}]
        data['params'] = params
        header = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; Trident/7.0; rv:11.0) like Gecko',"Content-Type": "application/json"}
        try:
            result = requests.post(self.client_url,json.dumps(data),headers=header,verify=False)
            mainlogger.info('LinsSound playtts : %s'%result.json())
        except requests.exceptions.Timeout or requests.exceptions.ConnectionError:
            time.sleep(1)
            result = requests.post(self.client_url,json.dumps(data),headers=header,verify=False)
        return result
    
    def getDeviceBySN(self,sound_no):
        params = {
                    "type": "req",
                    "app": "ls20",
                    "sn": sound_no
                }
        header = {"Content-Type": "application/json"}
        url = "%s/api/devices/getDeviceBySN"%(self.server_url)
        result = requests.post(url,json.dumps(params),headers=header,verify=False)
        return result.json()

class CheckSoundStatus:

    def __init__(self):

        self.my_db = ToMongo('wavedevice')
        self.interval = 20
        single_thread = Thread(target=self.check_sound(),args=[])
        single_thread.start()
        
    def check_sound(self):
        #定时器  定时check音响设备的状态
        self.check_status()
        check_thread = Timer(self.interval,self.check_sound)
        check_thread.start()

    def check_status(self):

        sound_info = self.my_db.get_col('odin_device_sound').find({},{'_id':0})
        if sound_info.count() == 0:
            return
        for sound_item in sound_info:
            ip = sound_item['sound_ip']
            status = sound_item['sound_status']
            result = CheckDeviceStatus(ip)
            if status == '0' and not result:
                item = {'sound_status':'1'}
                self.my_db.update('odin_device_sound',query={'sound_ip':ip},new={'$set':item})
            if status == '1' and result:
                item = {'sound_status':'0'}
                self.my_db.update('odin_device_sound',query={'sound_ip':ip},new={'$set':item})
        return


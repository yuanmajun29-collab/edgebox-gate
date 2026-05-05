
import socket
import threading
import time
from datetime import datetime
from Utils.utils import *
from .control_constuct import  ControlSqlHelperv2

import sys
import os
import paho.mqtt.client as mqtt
import redis
from Utils.db import ToMongo
from .Agreementunpack import *
from algorith_server.AgreementBuilder import alg_reboot,pack_3007_agreement
from .redis_connect import redis_database
from .mqtt_service import MqttInstance

import Utils.logger as logger

mainlogger = logger.getLogger('main')

class AlgorithServer():
    __instance =None
    __flag =False
    def __new__(cls, *args, **kwargs):
        # super().__new__(cls)
        if cls.__instance is None:
            cls.__instance=super().__new__(cls)
        return  cls.__instance

    def __init__(self, context):
        if not  AlgorithServer.__flag:
            AlgorithServer.__flag=True
            self.context = context
            self.socket =socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR,1)

            self.ip = "0.0.0.0" 
            self.socket.bind((self.ip, 6666))
            mainlogger.info("绑定 IP %s , 端口 %s"%(self.ip,6666))
            self.socket.listen(10)
            self.conn_list=[]

            self.mqtt_instance = MqttInstance()
            self.client = self.mqtt_instance.client

            self.my_db = ToMongo('wavedevice')

            self.Sms_sender = SendSmsResqueset() 
            self.Sms_sender.get_sms_delivery()   #启动时从数据库拉取短信投递任务

            self.web_sender = Sendwebrequest()
            self.web_sender.get_webhook_delivery()   #启动时从数据库拉取告警转发任务

            self.re_pool = redis_database


    def accept_conn(self):
        while True:
            conn,add=self.socket.accept()
            mainlogger.info("接收到连接请求 %s"%str(conn.getpeername()))
            self.conn_list = []
            self.conn_list.append( conn )


    def recv_message(self):
        mainlogger.info("receive message")
        while True:
            if len( self.conn_list) >0 :
                for conn in self.conn_list:
                    msg_cache = ""
                    while True:
                        try:
                            data = conn.recv(65536)
                            if not data:
                                break
                        except Exception as e:
                            mainlogger.info('接受告警数据出错:%s'%e)
                            break
                        msg = data.decode()
                        msg_head = msg[0:2]
                        if msg_head == '#!' and  msg_cache:
                            msg_cache = ""
                            msg_cache += msg
                        else:
                            msg_cache = msg_cache + msg

                        msg_cache = judge_cache(msg_cache,mongo=self.my_db,mqtt_client=self.client,sms=self.Sms_sender,webhook =self.web_sender,re_pool = self.re_pool)            


    def send_message(self, message):
        mainlogger.info("send message")
        if len(self.conn_list)==0:
            mainlogger.info("没有客户端连接 %s"%(self.conn_list))
            return
        for conn in self.conn_list:
            try:
                conn_name = conn.getpeername()
                mainlogger.info('--连接有效，发送信息--')
            except:
                mainlogger.info('--连接失效，移除连接--')
                self.conn_list.remove(conn)
                continue
            mainlogger.info("发送信息 %s 消息内容: %s"%(conn.getpeername(), message) )
            conn.send( message.encode())

    def start(self):
        thread1 = AcceptThread(  self.context)
        thread2 = RecvThread(  self.context)
        # 开启新线程
        thread1.start()
        thread2.start()

        mainlogger.info("开启发送接收线程")
  
class AcceptThread(threading.Thread):
    def __init__(self,  context):
        threading.Thread.__init__(self)

        self.context =context
        self.server = AlgorithServer(self.context)

    def run(self):
        self.server.accept_conn()


class RecvThread (threading.Thread):
    def __init__(self,  context):
        threading.Thread.__init__(self)

        self.context=context
        self.server= AlgorithServer(self.context)

    def run(self):
        self.server.recv_message()


class SenderThread(threading.Thread ):
    def __init__(self,context):
        threading.Thread.__init__(self)
        self.context =context
        self.server = AlgorithServer(context)
        self.my_db = ToMongo('wavedevice')


    def start_controls_message(self,mode):
        mainlogger.info("--工作模式：%s"%mode)
        self.target = self.send_controls_message(mode)
        self.start()


    def send_controls_message(self,mode):
        helper = ControlSqlHelperv2(self.context,db_mongo=self.my_db)
        if mode == "1":
            control_message = helper.build_controls_message()
        else:
            control_message = helper.build_controls_message_singlemode()
        camera_message = helper.build_cameras_message()
        mainlogger.info("发送布控信息--")
        self.server.send_message(control_message)
        mainlogger.info("发送布控信息完成--")

        mainlogger.info("发送摄像头信息--")
        self.server.send_message(camera_message)
        mainlogger.info("摄像头信息发送完毕--")

    def send_reboot_message(self):
        mainlogger.info("发送算法重启信息--")
        reboot_message = alg_reboot()
        self.server.send_message(reboot_message)
        mainlogger.info("算法重启信息发送完毕--")
        self.server.conn_list=[]
        mainlogger.info("清空socket连接--")

    def send_face_message(self,facemsg:str):
        mainlogger.info("发送人脸信息--")
        self.server.send_message(facemsg)
        mainlogger.info("人脸信息发送完毕--")

    def send_3007_message(self):
        camera_change_message = pack_3007_agreement()
        self.server.send_message(camera_change_message)
        self.server.conn_list=[]

class RecvHikHotThread (threading.Thread):
    def __init__(self,  context,req):
        threading.Thread.__init__(self)

        self.context=context
        self.req=req
        self.server= AlgorithServer(self.context)

    def run(self):
        self.server.recv_hot_message(self.req)
    


import os
import time
from Utils.db import ToMongo
from threading import Thread
from Utils.advise_func import insert_camera_advise

def CheckDeviceStatus(ip):
    ret = True
    ping_cmd = 'ping -c 2 {} >> /dev/null'.format(ip)
    result = os.system(ping_cmd)
    if result:
        ret = False
    return ret

class CheckInService():
    def __init__(self):
        self.reported_peroid = 60
        self.device_status_list = {}
        self.my_db = ToMongo("wavedevice")
   
    def run_device_monitor(self):
        self.my_db = ToMongo("wavedevice")
        while True:
            status_list = {}
            camera_coll = self.my_db.get_col("odin_device_camera_edit").find()
            if camera_coll.count() == 0:
                time.sleep(5)
                continue
            ip_keys = self.device_status_list.keys()
            for data in camera_coll:                
                ip = data["camera_ip"]
                organization_id = data["organization_id"]
                camera_name = data["camera_name"]
                name = camera_name + "(%s)"%ip
                if not ip and data["set_type"]=="1":
                    ip = data["main_url"].split("@")[1].split(":")[0]
                result = CheckDeviceStatus(ip)
                status = "0" if result else "1"
                query = {"camera_ip":ip}
                if ip not in ip_keys:
                    self.my_db.update("odin_device_camera_edit",query,{'$set':{'camera_status':status}})
                else:
                    status_before = self.device_status_list[ip]
                    if status_before != status:
                        flag = 1 if result else 0
                        insert_camera_advise(self.my_db,name,flag,organization_id)
                        self.my_db.update("odin_device_camera_edit",query,{'$set':{'camera_status':status}})
                status_list[ip] = status
            self.device_status_list = status_list.copy()
            time.sleep(5)

    def check_device(self,ip):
        result = CheckDeviceStatus(ip)
        status = "0" if result else "1"
        self.device_status_list[ip] = status
        if status == "0":
            query = {"camera_ip":ip}
            self.my_db.update("odin_device_camera_edit",query,{'$set':{'camera_status':status}})
import os
import time
from datetime import datetime
from Utils.db import ToMongo
from threading import Thread
from Utils.advise_func import insert_camera_advise


def CheckDeviceStatus(ip):
    '''
    设备ping得通则返回True，不通返回False
    '''
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
        self.devce_ping_thread = Thread(target=self.run_device_monitor, args=[])
        self.devce_ping_thread.start()

    def run_device_monitor(self):
        self.my_db = ToMongo("wavedevice")
        while True:
            status_list = {}
            camera_coll = self.my_db.get_col("odin_device_camera_edit")
            query = {"stream_url": {"$eq": None}}
            camera_items = camera_coll.find(query)
            if camera_items.count() == 0:
                time.sleep(5)
                continue
            ip_keys = self.device_status_list.keys()
            for data in camera_items:
                ip = data["camera_ip"]
                if not ip and data["set_type"] == "1":
                    ip = data["main_url"].split("@")[1].split(":")[0]
                if not ip:
                    continue
                organization_id = data["organization_id"]
                camera_name = data["camera_name"]
                name = camera_name + "(%s)" % ip
                result = CheckDeviceStatus(ip)
                status = "0" if result else "1"
                query = {"camera_ip": ip}
                if ip not in ip_keys:
                    self.my_db.update("odin_device_camera_edit", query, {'$set': {'camera_status': status}})
                else:
                    status_before = self.device_status_list[ip]
                    if status_before != status:
                        flag = 1 if result else 0
                        newItem = {}
                        if not flag:
                            newItem['offline_time'] = datetime.now()
                        #    self.my_db.update("odin_device_camera_edit", query, {'$set': {'offline_line': datetime.now()}})
                        insert_camera_advise(self.my_db, name, flag, organization_id)
                        newItem['camera_status'] = status
                        self.my_db.update("odin_device_camera_edit", query, {'$set': newItem})
                status_list[ip] = status
            self.device_status_list = status_list.copy()
            time.sleep(5)

    def check_device(self, ip):
        result = CheckDeviceStatus(ip)
        status = "0" if result else "1"
        self.device_status_list[ip] = status
        query = {"camera_ip": ip}
        if status == "0":          
            self.my_db.update("odin_device_camera_edit", query, {'$set': {'camera_status': status}})
        else:
            self.my_db.update("odin_device_camera_edit", query, {'$set': {'offline_time': datetime.now()}})

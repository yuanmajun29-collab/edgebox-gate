import os
import time
from Utils.db import ToMongo
from threading import Thread
from Utils.advise_func import insert_camera_advise
import Utils.logger as logger

mainlogger = logger.getLogger("main")


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
        self.camera_col = self.my_db.get_col("odin_device_camera_edit")
        self.cameraStatusMap = {}

        self.devce_ping_thread = Thread(target=self.run_device_monitor, args=[])
        self.devce_ping_thread.start()

    def get_status(self):
        query = {"stream_url": {"$eq": None}}
        camera_items = self.camera_col.find(query)
        camera_list = list(camera_items)
        statusMap = {}
        for item in camera_list:
            ip = item.get('camera_ip')
            status = item.get('camera_status')
            statusMap[ip] = status
        self.cameraStatusMap = statusMap
        return camera_list

    def run_device_monitor(self):

        while True:
            camera_list = self.get_status()
            status_list = {}
            query = {"stream_url": {"$eq": None}}
            camera_items = self.camera_col.find(query)
            if camera_items.count() == 0:
                time.sleep(10)
                continue
            ip_keys = self.device_status_list.keys()
            for data in camera_list:
                try:
                    ip = data["camera_ip"]
                    if not ip and data["set_type"] == "1":
                        ip = data["main_url"].split("@")[1].split(":")[0]
                    if not ip:
                        continue
                    organization_id = data.get("organization_id")
                    camera_name = data.get("camera_name")
                    if not camera_name:
                        continue
                    name = camera_name + "(%s)" % ip
                    result = CheckDeviceStatus(ip)
                    status = "0" if result else "1"
                    query = {"camera_ip": ip}

                    status_before = self.cameraStatusMap.get(ip)
                    if status != status_before:
                        flag = 1 if result else 0
                        insert_camera_advise(self.my_db, name, flag, organization_id)
                        self.my_db.update("odin_device_camera_edit", query, {'$set': {'camera_status': status}})
                    status_list[ip] = status
                except Exception as e:
                    mainlogger.exception(e)
            self.device_status_list = status_list.copy()
            time.sleep(10)

    def check_device(self, ip):
        result = CheckDeviceStatus(ip)
        status = "0" if result else "1"
        self.device_status_list[ip] = status
        if status == "0":
            query = {"camera_ip": ip}
            self.my_db.update("odin_device_camera_edit", query, {'$set': {'camera_status': status}})
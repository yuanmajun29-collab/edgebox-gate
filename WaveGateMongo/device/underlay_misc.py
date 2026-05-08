import os
from flask.views import MethodView
from flask import request,send_file
from Utils.device_misc import response_no_image
from config import UNDERLAY_URL
import  Utils.logger as logger

import Utils.edgebox_repo  # noqa: F401
from edgebox_db.workflow_mission_queries import workflow_mission_collection
from edgebox_db.mongo_collections import (
    WORK_FLOW_INSIGHT_MODEL_ALGORITHM_INSTANCE,
    WORK_FLOW_MISSION_DEVICE_ASSOCIATE,
)

#mainlogger = logger.getLogger("main")

def isControlRelated(my_db,camera_id,alg_num) -> bool:
    '''
    新增、删除、编辑底图时，查询是否需要下发给算法；
    '''
    asso_device_col = my_db.get_col(WORK_FLOW_MISSION_DEVICE_ASSOCIATE)
    instance_col = my_db.get_col(WORK_FLOW_INSIGHT_MODEL_ALGORITHM_INSTANCE)
    mission_col = workflow_mission_collection(my_db)

    missionIDList= asso_device_col.distinct("mission_id",{'device_id':camera_id})

    if not missionIDList:
        #设备没有布控任务
        return False
    
    query = {'mission_id':{'$in':missionIDList},
             'algorithm_constant_num':alg_num}
    
    missionIDList2 = instance_col.distinct("mission_id",query)

    if not missionIDList2:
        #设备有布控任务,但是没有配置该算法
        return False
    
    query_status = {'mission_id':{'$in':missionIDList2},
                    'mission_status':0}
    
    result = mission_col.find_one(query_status)
    if not result:
        #设备有布控任务且配置该算法，但是出于关闭状态
        return False

    return True


def restartAlg(my_db,camera_id,alg_num):
    #如果有关联任务，就重启算法
    result = isControlRelated(my_db,camera_id,alg_num) 
#    mainlogger.debug("摄像机任务关联结果%s;camera_id:%s,alg_num:%s"%(result,camera_id,alg_num))
    if result:
        from algorith_server.AlgorithServer_new import SenderThread
        sender = SenderThread(context=None)
        #发送算法重启信息
        sender.send_3007_message()
    
    return

class UnderlayImageDBAPI(MethodView):
    
    def getImage(self, image_id, camera_id):
        origin_image_binary = b''
        origin_image_folder = UNDERLAY_URL

        if image_id is not None:
            per_image_name = image_id + ".jpg" 
            second_dir = str(camera_id)            
            second_dir_path = os.path.join(origin_image_folder, second_dir)        
            origin_image_path = os.path.join(second_dir_path, per_image_name)
            if not os.path.exists(origin_image_path):
                origin_image_path = None
            return origin_image_path

    def get(self, image_id=None):

        cameraId = int(request.args.get('id', None))
        image_path = self.getImage(image_id, cameraId)
        if not image_path:
            return response_no_image()
        fl_name = image_id + '.jpg'
        return send_file(image_path,as_attachment=True,attachment_filename=fl_name,cache_timeout=0)

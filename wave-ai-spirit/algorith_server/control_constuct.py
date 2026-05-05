import json

from algorith_server.AgreementBuilder import pack_init_agreement,pack_3004_agreement
from Utils.db import ToMongo
from algorith_server.Algorithmutil import constant_to_str
from personnel.personnel_route import FaceFeatureDBAPI


def switch_roi(roi_item):
    '''
    数据库查到的转换成需要返回的格式；
    '''
    if not roi_item:
        return
    try:
        roi_infos = json.loads(roi_item['roi_area_info'])
        ans = []
        roi_id = roi_item.get("roi_id")
        roi_name = roi_item.get("roi_name")
        i = 0
        for roi_info_item in roi_infos:
            result = {}
            result["roi_id"] = roi_id
            result["roi_name"] = roi_name
            result["roi_type"] = "0"
            result['source_width'] = roi_info_item['sourceWidth']
            result['source_height'] = roi_info_item['sourceHeight']
            result['top_y'] = roi_info_item['top']
            result['left_x'] = roi_info_item['left']
            result['points'] = []
            origin_points = roi_info_item['points']
            start_point = origin_points[0]
            for point in origin_points:
                result['points'].append(point['x'])
                result['points'].append(point['y'])
            result['points'].append(start_point['x'])
            result['points'].append(start_point['y'])
            ans.append(result)
            i+=1
    except Exception as e:
        return
    return ans

def mission_devices(items):
    #形成item与索引配对的字典
    result = {}
    if items:
        for i,element in enumerate(items):
            device_id = element['device_id']
            result[device_id] = i 
    return  result


class ControlSqlHelperv2():
    def __init__(self, context,db_mongo:ToMongo):
        self.context = context
        self.my_db = db_mongo
 
    def build_controls_message(self):

        controlMissons  = self.my_db.get_col('work_flow_mission').find({'mission_status':0})
        DeviceAssociate = self.my_db.get_col('work_flow_mission_device_associate')
        camera_coll = self.my_db.get_col('odin_device_camera_edit')
        algorithm_coll = self.my_db.get_col('work_flow_insight_model_algorithm_instance')
        roi_col = self.my_db.get_col('odin_device_roi_area_record')
        constant_col = self.my_db.get_col('work_flow_algorithm_constant')
        items = []
        if controlMissons:
            for controlItem in controlMissons:  
                mission_id = controlItem['mission_id']
                missionDevices = DeviceAssociate.find({'mission_id':mission_id})
                for missionDevice in missionDevices:
                    item = {}
                    device_id = missionDevice['device_id']
                    cameraItems=camera_coll.find_one({'camera_id':device_id})
                    item['url']=cameraItems['main_url']
                    item['device_id']=device_id
                    match_models = algorithm_coll.find({'mission_id':mission_id})

                
                    constant_list = []
                    algorithm_list = []
                    for match_model in match_models:
                        try:
                            iter = {}
                            service_num = match_model['algorithm_service_num']
                            constant_num = match_model['algorithm_constant_num']
                            constant_item = constant_col.find_one({'algorithm_service_num':service_num})
                            constant_list.append(constant_num)
                            roi_item = roi_col.find_one({"algorithm_constant_id":{"$regex":service_num},
                                                          "camera_id":device_id})
                            iter["algorithm"] = constant_to_str(constant_num)
                            if not iter["algorithm"]:
                                continue
                        except:
                            continue
                        #只有睡岗和离岗有rate_num
                        if constant_num in ['113','114']:
                            try:
                                iter["rate_num"] = constant_item['rate_num']  
                            except:
                                iter["rate_num"] = None
                        else:
                            iter["rate_num"] = None
                        iter["duration_num"] = None

                        #设备绑定的ROI
                        iter['roi_list'] = []
                        if roi_item:
                            roi_alg_list = roi_item['algorithm_constant_id'].split(',')
                            if service_num in roi_alg_list:
                                iter['roi_list'] = switch_roi(roi_item)

                        #算法绑定的人脸
                        iter["person_list"] = []
                        face_list = match_model.get("face_list")
                        if face_list and face_list != "[]":
                    #        face_list = json.loads(face_list)
                            for faceInfo in face_list:
                                item_person = {}
                                item_person['type'] = "0"
                                item_person['person_id'] = faceInfo.get("faceId")
                                faceFeature = faceInfo.get("faceFeature")
                                if not faceFeature:
                                    continue
                                item_person['face_features'] = faceFeature
                                iter["person_list"].append(item_person)

                        algorithm_list.append(iter)


                    algorithm_str = constant_to_str(constant_list)
                    if not algorithm_str:
                        continue
                    item['algorithm']=algorithm_str
                    item['algorithm_list']=algorithm_list
                    items.append(item)


        missons_message = json.dumps(items)
        message = pack_init_agreement( missons_message)

        return message
    
    def build_cameras_message(self):
        camera_list = self.my_db.get_col('odin_device_camera_edit').find()
        items=[]
        if camera_list:
            for camera_item in camera_list:
                item = {}
                item['url'] = camera_item['main_url']
                item['device_id'] = camera_item['camera_id']
                item['algorithm'] = None
                item['algorithm_list'] = []
                items.append(item)   
        camera_message = json.dumps(items)
        message = pack_3004_agreement(camera_message)

        return message
    
    def build_controls_message_singlemode(self):
        Facefature = FaceFeatureDBAPI()
        controlMissons  = self.my_db.get_col('work_flow_mission').find({'mission_status':0})
        DeviceAssociate = self.my_db.get_col('work_flow_mission_device_associate')
        camera_coll = self.my_db.get_col('odin_device_camera_edit')
        algorithm_coll = self.my_db.get_col('work_flow_insight_model_algorithm_instance')
        roi_col = self.my_db.get_col('odin_device_roi_area_record')
        asso_person_col = self.my_db.get_col('work_flow_mission_personnel_associate')
        asso_persongroup_col = self.my_db.get_col('work_flow_mission_personnelgroup_associate')
        group_col = self.my_db.get_col('work_flow_personnel_personnelgroup_associate')
        asso_img_col = self.my_db.get_col('work_flow_personnel_image')
        constant_col = self.my_db.get_col('work_flow_algorithm_constant')
        items = []
        device_asso_alg = {}
        if controlMissons:
            for controlItem in controlMissons:  
                mission_id = controlItem['mission_id']
                missionDevices = DeviceAssociate.find({'mission_id':mission_id})
                for missionDevice in missionDevices:
                    devices = mission_devices(items)
                    item = {}
                    device_id = missionDevice['device_id']
                    cameraItems=camera_coll.find_one({'camera_id':device_id})
                    item['url'] = cameraItems['main_url']
                    item['device_id']=device_id
                    match_models = algorithm_coll.find({'mission_id':mission_id})

                    if device_id in devices.keys():                        
                        index = devices[device_id]
                        flag = True
                    else:
                        flag = False
                
                    constant_list = []
                    algorithm_list = []
                    for match_model in match_models:
                        try:
                            iter = {}
                            service_num = match_model['algorithm_service_num']
                            constant_num = match_model['algorithm_constant_num']
                            time_list = match_model['last_time']
                            constant_item = constant_col.find_one({'algorithm_service_num':service_num})
                            constant_list.append(constant_num)
                            roi_items = roi_col.find({"algorithm_constant_id":{"$regex":service_num},
                                                    "camera_id":device_id})
                            iter["algorithm"] = constant_to_str(constant_num)
                            item["time_list"] = time_list if time_list else None
                            if not iter["algorithm"]:
                                continue
                        except:
                            continue
                        #只有睡岗和离岗有rate_num
                        if constant_num in ['113','114']:
                            try:
                                iter["rate_num"] = constant_item['rate_num']  
                            except:
                                iter["rate_num"] = None
                        else:
                            iter["rate_num"] = None
                        iter["duration_num"] = None
                        iter["roi_list"] = []
                        for roi_item in roi_items:
                            roi_alg_list = roi_item['algorithm_constant_id'].split(',')
                            if service_num in roi_alg_list:
                                iter['roi_list'].append(switch_roi(roi_item))
                        iter["person_list"] = []
                        #目标布控才下发人脸
                        if constant_num == "100":
                            query= {"mission_id":mission_id}
                            peronid_list = asso_person_col.distinct('personnel_id',query)
                            groupid_list = asso_persongroup_col.distinct('personnel_group_id',query)
                            if groupid_list:
                                peronid_list1 = group_col.distinct('personnel_id',{'personnel_group_id':{'$in':groupid_list}})
                                peronid_list += peronid_list1
                                peronid_list = set(peronid_list)

                            for person_id in peronid_list:

                                item_person = {}
                                item_person['type'] = "0"
                                item_person['person_id'] = person_id
                                item_person['face_features'] = []
                                asso_img_items = asso_img_col.find({"personnel_id":person_id})
                                for asso_img in asso_img_items:
                                    imgid = asso_img['image_id']
                                    imgfeature = Facefature.get(image_id=imgid)
                                    if imgfeature:
                                        item_person['face_features'].append(imgfeature)
                                iter["person_list"].append(item_person)


                        alg_list = device_asso_alg.get(device_id)
                        if not alg_list:
                            device_asso_alg[device_id] = []
                            device_asso_alg[device_id].append(service_num)
                            algorithm_list.append(iter)
                        elif service_num not in alg_list:
                            device_asso_alg[device_id].append(service_num)
                            if flag:
                                items[index]['algorithm_list'].append(iter)
                            else:
                                algorithm_list.append(iter)

                    if not flag:
                        algorithm_str = constant_to_str(constant_list)
                        if not algorithm_str:
                            continue
                        item['algorithm']=algorithm_str
                        item['algorithm_list']=algorithm_list
                        items.append(item)
                    else:
                        alg_param = items[index]['algorithm']
                        algorithm_str = constant_to_str(constant_list,alg_init=alg_param)
                        if not algorithm_str:
                            continue
                        items[index]['algorithm'] = algorithm_str

        missons_message = json.dumps(items)
        message = pack_init_agreement( missons_message)

        return message
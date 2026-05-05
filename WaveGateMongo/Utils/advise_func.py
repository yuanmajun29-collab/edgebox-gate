
from Utils.db import ToMongo
import uuid
import json
from datetime import datetime

def insert_camera_advise(my_db,camera_name,flag,organization_id):
    '''
    插入摄像头消息数据
    flag : int--(0,1)  表示是摄像头离线消息还是上线消息
    '''
    format_pattern = '%Y-%m-%d %H:%M:%S'
    now = datetime.now()
    res = {}
    res['advise_id'] = uuid.uuid4().hex
    res['source_type'] = 1
    res['advise_type'] = 1
    res['advise_status'] = 0
    res['birth_time'] = now.strftime(format_pattern)
    res['create_time'] = now
    res['read_person'] =None
    res['advise_persons'] = None
    res['audio_type'] = None
    res['parameter'] = None
    res['organization_id'] = organization_id
    content1 = "<div class='notice-container'><a class='notice-reson' href='#'>"+camera_name+"</a><p class='notice-desc'><b>状态描述：</b>摄像机重新上线。 </p><s class='bottom-line'></s><p class='notice-date'>"+res['birth_time']+"</p></div>"
    content2 = "<div class='notice-container'><a class='notice-reson' href='#'>"+camera_name+"</a><p class='notice-desc'><b>状态描述：</b>系统无法检测到摄像机。 </p ><p class='notice-plan'><s class='notice-dashed-line'></s><b>解决方案：</b> 请检查网络是否正常连接，代理模块、摄像机是否处于正常运行状态。 </p ><s class='bottom-line'></s><p class='notice-date'>"+res['birth_time']+"</p ></div>"
    if flag == 0:
        res['advise_content'] = content2
    else:
        res['advise_content'] = content1
    my_db.insert("odin_advise_info",res)

def insert_emergency_advise(db,msg,param,organization_id):
    '''
    消息管理表插入告警信息
    '''
    format_pattern = '%Y-%m-%d %H:%M:%S'
    now = datetime.now()
    res = {}
    res['advise_id'] = uuid.uuid4().hex
    res['source_type'] = 0
    res['advise_type'] = 3
    res['advise_status'] = 0
    res['birth_time'] = now.strftime(format_pattern)
    res['create_time'] = now
    res['read_person'] =None
    res['advise_persons'] = None
    res['audio_type'] = None
    res['parameter'] = json.dumps(param)
    res['organization_id'] = organization_id 
    res['advise_content'] = json.dumps(msg,ensure_ascii=False)
    db.insert("odin_advise_info",res)
    
    
    
    
    


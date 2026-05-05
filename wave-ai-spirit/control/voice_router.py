import uuid
from flask import Blueprint,jsonify
from Utils.jwt_verify import *
from Utils.db import ToMongo
from Utils.utils import set_fail_result,set_success_result
from Utils.voicedevice_utils import VoiceBoxUtils,LingsSound,CheckSoundStatus
from system.sys_config import sound_database,sound_web
from system.system_misc import database_to_dict


bp = Blueprint("sound",__name__, url_prefix='/net-web')

checkSoundInstance = CheckSoundStatus() #定时任务check音响状态

@bp.route('/devicesound/queryDeviceSoundList', methods=['GET','POST'])
@login_required
def queryDeviceSoundList():
    '''
    音箱列表-查询音箱列表
    '''
    params = request.get_json()
    page =     params.get('page',None)
    pageSize = params.get('pageSize',None)
    soundIp =  params.get('soundIp',None)
    soundNo =  params.get('soundNo',None)
    soundType = params.get('soundType',None)

    my_db = ToMongo('wavedevice')
    sound_col = my_db.get_col('odin_device_sound')

    query = dict()
    if soundIp:
        query['sound_ip'] = {'$regex':soundIp}
    if soundNo:
        query['sound_no'] = {'$regex':soundNo}
    items = sound_col.find(query).sort('sound_name')

    if page and pageSize:
        num = (page-1)*pageSize
        res = items.skip(num).limit(pageSize)
    else:
        page = 0
        pageSize = 0
        res = items

    if soundType:
        query['sound_type'] = soundType

    soundEntities = list()
    for item in res:
        a = database_to_dict(item,sound_database,sound_web)
        soundEntities.append(a)
    
    response_data = set_success_result()
    response_data['page'] = page
    response_data['pageSize'] = pageSize
    response_data['soundEntities'] = soundEntities
    response_data['totalCount'] = len(soundEntities)
    return jsonify(response_data)


@bp.route('/devicesound/deleteDeviceSound', methods=['GET','POST'])
@login_required
def deleteDeviceSound():
    '''
    音箱列表-删除音箱
    '''
    params = request.get_json()
    soundIds =  params.get('soundIds',None)

    my_db = ToMongo('wavedevice')
    
    if soundIds:
        query = {'sound_id':{'$in':soundIds}}
        my_db.delete('odin_device_sound',query,is_one=False)
   
    response_data = set_success_result()
    return jsonify(response_data)

@bp.route('/devicesound/checkAudioMacIsExists', methods=['GET','POST'])
@login_required
def checkAudioMacIsExists():
    '''
    音箱列表-手动添加-检查音箱序号
    '''
    params = request.get_json()
    mac =  params.get('mac',None)

    my_db = ToMongo('wavedevice')
    flagResult = False
  
    response_data = set_success_result()
    response_data['flagResult'] = flagResult
    return jsonify(response_data)
      
@bp.route('/devicesound/synDeviceSoundData', methods=['GET','POST'])
@login_required
def synDeviceSoundData():
    '''
    音箱列表-同步音箱
    '''
    my_db = ToMongo('wavedevice')
    itc_server_col = my_db.get_col('odin_device_itc_server')    
    itc_item = itc_server_col.find_one()

    lings_server_col = my_db.get_col('odin_device_lings_server')
    lings_item= lings_server_col.find_one()
    
    response_data = set_success_result()
    synDeviceSoundEntities = []
    if not itc_item and not lings_item:
        response_data['synDeviceSoundEntities'] = synDeviceSoundEntities
        return jsonify(response_data)
    
    if itc_item:
        try:
            ip = itc_item.get('itc_server_address',None)
            port = itc_item.get('itc_server_port',None)
            account = itc_item.get('itc_server_account',None)
            password = itc_item.get('itc_server_password',None)

            if ip and port:
                
                server_url = 'http://%s:%s'%(ip,port)
                VoiceInstance = VoiceBoxUtils(server_url,account,password,volume=70)
                VoiceInstance.login()
                terminal_info = VoiceInstance.getterminalinfo().json()
                result = terminal_info['result']
                if result == 200:
                    EndPointsArray = terminal_info['data']['EndPointsArray']
                    for item in EndPointsArray:
                        sound_ip = item['EndpointIP']
                        sound_mac = item['EndpointMac']
                        soundStatus = "0"
                        soundName = "itc_" + sound_ip.split('.')[-1]
                        res = {"soundIp":sound_ip,
                            "soundNo":sound_mac,
                            "soundStatus":soundStatus,
                            "soundName":soundName,
                            "soundType":"1"}
                        synDeviceSoundEntities.append(res)
        except Exception as e:
            mainlogger.info('--itc同步Error:%s'%e)

    if lings_item:
        try:
            ip = lings_item.get('lings_server_address',None)
            port = lings_item.get('lings_server_port',None)
            account = lings_item.get('lings_server_account',None)
            password = lings_item.get('lings_server_password',None)

            if ip and port:

                server_url = 'http://%s:%s'%(ip,port)
                LingsInstance = LingsSound(client_url=None,server_url=server_url,sound_no=None,volume=70)
                response = LingsInstance.login(account=account,password=password)
                token = response['user']['token']
                devices_info = LingsInstance.getTerminalinfo(token=token)
                if 'rows' in devices_info.keys():
                    rows = devices_info['rows']
                    for item in rows:
                        type = item['type']
                        if type == '0001':
                            #类型为采集器
                            continue
                        sound_ip = item['extra']['ip']
                        sound_mac = item['sn']
                        soundStatus = "0"
                        soundName = item['name']
                        res = {"soundIp":sound_ip,
                            "soundNo":sound_mac,
                            "soundStatus":soundStatus,
                            "soundName":soundName,
                            "soundType":"2"}
                        synDeviceSoundEntities.append(res)
        except Exception as e:
            mainlogger.info('--菱声同步Error:%s'%e)

    response_data['synDeviceSoundEntities'] = synDeviceSoundEntities
    return response_data

@bp.route('/devicesound/addDeviceSoundData', methods=['GET','POST'])
@login_required
def addDeviceSoundData():
    '''
    音箱列表-同步音箱-添加音响
    '''
    params = request.get_json()
    item = params.get("0",None)
    my_db = ToMongo('wavedevice')
    soundIp = item['soundIp']
    soundNo = item['soundNo']
    soundName = item['soundName']
    soundStatus = item['soundStatus']
    soundType = item['soundType']

    sound_col = my_db.get_col('odin_device_sound')
    sound_ip_list = sound_col.distinct('sound_ip')
    error_response = set_fail_result()
    if soundIp in sound_ip_list:
        error_response['errorCodeDesc'] = '音响设备已存在'
        return error_response

    soundId = uuid.uuid4().hex
    res = {"soundId":soundId,
           "soundIp":soundIp,
           "soundName":soundName,
           "soundNo":soundNo,
           "soundStatus":soundStatus,
           "soundType":soundType}
    if soundType == "2":
        #菱声的音响端口为8888
        res['soundPort'] = "8888"
    sound_item = database_to_dict(res,sound_web,sound_database)
    my_db.insert("odin_device_sound",sound_item)
    response_data = set_success_result()
    return response_data

    
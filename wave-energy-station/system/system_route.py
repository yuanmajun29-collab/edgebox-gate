from datetime import datetime
from flask import Blueprint,request, jsonify, current_app,send_file
import uuid
from threading import Thread
from Utils.db import ToMongo
from Utils.jwt_verify import *
from Utils.Utils import set_success_result,set_fail_result
from .system_misc import *
from .system_sync import *
from .sync_model import SyncTimer,init_box_model,init_param,check_service_addr
from config import SYSTEMLOGO_URL
import Utils.edgebox_repo  # noqa: F401
from edgebox_db.mongo_collections import WORK_FLOW_ALGORITHM_CONSTANT
from Utils.device_misc import make_response_image_jpeg
import Utils.glv as glv
from emergency.db_router import transfer_img_url
import traceback
from msg_queue import *

host_ip = get_ip()
init_workmodel = init_box_model() #掉电重启为联网模式
#init_box_info = init_base_info()
srs_instance = SyncDeviceP2p()

bp = Blueprint("system",__name__, url_prefix='/net-web')
@bp.route('/auth/querySystemSetting', methods=['GET','POST'])
@login_required
def querySystemSetting():
    '''
    接口注释：查看系统设置
    '''
    url_referer = request.headers['Referer']
    my_db = ToMongo('wavedevice')
    system_items = my_db.get_col('system_setting').find({})
    systemSettingEntities = []
    for item in system_items:
        iter={}
        iter['emergencyPopState'] = item['emergency_pop_state']
        iter['organizationId'] = item['organization_id']
        if  item['system_logo_url']:
            iter['systemLogoUrl'] = transfer_img_url(url_referer,item['system_logo_url'])
        else:
            iter['systemLogoUrl'] = None
        iter['systemName'] = item['system_name']
        iter['fileType'] = item['file_type']
        iter['homeOverviewStyle'] = item['home_overview_style']
        iter['centerType'] = item.get('center_type')
        iter['systemNameScreen'] = item.get('system_name_screen')
        systemSettingEntities.append(iter)

    response_data = {}
    response_data['systemSettingEntities'] = systemSettingEntities
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 556
    return jsonify(response_data)

@bp.route('/auth/uploadSystemLogo', methods=['GET','POST'])
def uploadSystemLogo():
    '''
    接口注释：上传系统图标
    '''
    params = request.form
    accessToken = params.get("accessToken",None)
    fileType = params.get("fileType",None)
    imgfile = request.files['file'].stream.read()
    logodir = SYSTEMLOGO_URL
    if not os.path.exists(logodir):
        os.mkdir(logodir)

    logo_id = uuid.uuid4().hex 
    imgpath = logodir + logo_id + '.jpg'

    with open(imgpath,"wb") as outfile:
        outfile.write(imgfile)

    port = glv.get_value('nginx_port','8088')
    pathhead = 'http://%s:%s/net-web/system/systemIocn/'%(host_ip,port)
    logo_url = pathhead + logo_id + '.jpg'

    my_db = ToMongo('wavedevice')
    setting_col = my_db.get_col('system_setting')
    item = {'system_logo_url':logo_url}
    fileType = int(fileType) if fileType else None
    query = {'file_type':fileType}
    origin_item = setting_col.find_one(query)
    my_db.update('system_setting',query,{"$set":item})

    if origin_item:
        try:
            url = origin_item['system_logo_url']
            if url:
                imgname = url.split('/')[-1]
                filepath = logodir + imgname
                os.remove(filepath)
        except Exception as e:
            mainlogger.info(''+traceback.format_exc())

    response_data = {}
    response_data['logoUrl'] = logo_url
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 18
    return jsonify(response_data)

@bp.route('/auth/deleteSystemLogo', methods=['GET','POST'])
@login_required
def deleteSystemLogo():
    '''
    接口注释：删除系统图标
    '''
    params = request.get_json()
    fileType = params.get('fileType',None)
    my_db = ToMongo('wavedevice')
    item = {'system_logo_url':None}
    query = {'file_type':fileType}
    setting_item = my_db.get_col("system_setting").find_one(query)
    if setting_item:
        logo_url = setting_item['system_logo_url']
        my_db.update('system_setting',query,{"$set":item})
        if logo_url:
            imgname = logo_url.split('/')[-1]
            imgpath = SYSTEMLOGO_URL + imgname
            if os.path.exists(imgpath):
                os.remove(imgpath)

    response_data = {}
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 18
    return jsonify(response_data)

@bp.route('/system/systemIocn/<string:id>', methods=['GET','POST','PUT'])
def findSystemLogo(id):
    image_id = id.split(".")[0]
    origin_image_binary = b''
    origin_image_folder = SYSTEMLOGO_URL

    if image_id is not None:
        file_name = image_id + ".jpg"                
        origin_image_path = os.path.join(origin_image_folder, file_name)
        try:
            with open(origin_image_path, 'rb') as fp:                
                origin_image_binary = fp.read()
        except:
            print('Error:logo路径不存在')
            origin_image_binary = None   
    return make_response_image_jpeg(origin_image_binary)

@bp.route('/mailServiceSetting/getMailServiceSetting', methods=['GET','POST'])
@login_required
def getMailServiceSetting():   
    '''
    接口注释：获取当前用户的邮箱信息
    '''
    
    params = request.get_json()
    user_id = params.get("userId", None)

    my_db = ToMongo('wavedevice')
    # organization_id = my_db.get_col('authority_user').find_one({'user_id':user_id})['organization_id']
    # query = {"organization_id":organization_id}
    mail_coll = my_db.get_col('authority_mail_service_setting').find_one()
    
    response_data = {}
    response_data['mailSmtpAddress'] = mail_coll.get('mail_smtp_address')
    response_data['mailServerPort'] = mail_coll.get('mail_server_port')
    response_data['mailSmtpType'] = mail_coll.get('mail_smtp_type')
    response_data['mailAccount'] = mail_coll.get('mail_account')
    response_data['mailPassword'] = mail_coll.get('mail_password')
    response_data['mailSendName'] = mail_coll.get('mail_send_name')
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 556
    return jsonify(response_data)

@bp.route('/timeSetting/getInfo', methods=['GET','POST'])
@login_required
def getInfo():   
    '''
    接口注释：获取当前用户的ntp配置信息
    '''
    params = request.get_json()
    accesstoken = params.get('accessToken',None)
    current_user = g.user_account
    my_db = ToMongo('wavedevice')
    organization_id = my_db.get_col('authority_user').find_one({'user_account':current_user})['organization_id']

    time_coll = my_db.get_col('authority_time_setting').find_one({'organization_id':organization_id})
    

    response_data = {}
    response_data['timeZone'] = time_coll['time_zone']
    response_data['timeMode'] = time_coll['time_mode']
    response_data['ntpAddress'] = time_coll['ntp_address']
    response_data['ntpPort'] = time_coll['ntp_port']
    response_data['ntpIntervalTime'] = time_coll['ntp_interval_time']
    response_data['equipmentTime'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    response_data['setTime'] = None

    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 556
    return jsonify(response_data)

@bp.route('/timeSetting/saveOrUpdate', methods=['GET','POST'])
@login_required
def saveOrUpdate2():   
    '''
    接口注释：获取当前用户的ntp配置信息
    '''
    params = request.get_json()
    accesstoken = params.get('accessToken',None)
    current_user = g.user_account
    my_db = ToMongo('wavedevice')
    organization_id = my_db.get_col('authority_user').find_one({'user_account':current_user})['organization_id']

    # ntp_address = params.get("ntpAddress", None)
    # ntp_interval_time = int(params.get("ntpIntervalTime", None))
    # ntp_port = params.get("ntpPort", None)
    # time_mode = params.get("timeMode", None)
    ntp_address = '1.1.1.2'
    ntp_interval_time = '5'
    time_mode = '1'
    time_zone = params.get("timeZone", None)
 

    last_modify_time = datetime.now()
    res ={'ntp_address':ntp_address,'ntp_interval_time':ntp_interval_time,'ntp_port':'80',
            'time_mode': time_mode,'time_zone':time_zone,'last_modify_time':last_modify_time
         }

    my_db.update('authority_time_setting',
                    {'organization_id':organization_id},
                    {'$set':res}
                )


    response_data = {}
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 556
    return jsonify(response_data)

@bp.route('/timeSetting/validOffOrOn', methods=['GET','POST'])
@login_required
def validOffOrOn():   
    '''
    接口注释：联网状态则可以手动设置时间，离线状态则不能
    状态:未完成
    '''
 
    response_data = {}
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 5
    response_data['validFlag'] = False
    return jsonify(response_data)

@bp.route('/timeSetting/setServiceTime', methods=['GET','POST'])
@login_required
def setServiceTime():   
    '''
    接口注释：手动设置时间
    '''
    params = request.get_json()
    setTime = params.get("setTime", None)
    timenset = setTime.split(' ')[1]
    datetemp = setTime.split(' ')[0].split('-')
    dateset = datetemp[0]+datetemp[1]+datetemp[2]

    time_param = timenset+' '+dateset
    cmd = "date -s '%s'"%time_param
    execShell(cmd)  
    
    response_data = {}
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 5
    return jsonify(response_data)

@bp.route('/baseInfo/getBaseInfoByUserId', methods=['GET','POST'])
@login_required
def getBaseInfoByUserId():   
    '''
    接口注释：获取当前用户的设置基本信息
    '''
    params = request.get_json()
    page = params.get("page", None)
    pageSize = params.get("pageSize", None)
    
    my_db = ToMongo('wavedevice')
    baseinfo_coll = my_db.get_col('authority_base_info').find()
    baseinfo = list(baseinfo_coll)[0]
    response_data = {}
    response_data['equipmentName'] = baseinfo['equipment_name']
    response_data['installationPosition'] = baseinfo['installation_position']
    response_data['equipmentModel'] = baseinfo['equipment_model']
    response_data['equipmentSerialNumber'] = baseinfo['equipment_serial_number']
    response_data['hardwareVersion'] = baseinfo['hardware_version']
    response_data['videoCameraNum'] = baseinfo['video_camera_num']
    response_data['webVersion'] = baseinfo['web_version']
    response_data['algorithmServerVersion'] = baseinfo['algorithm_server_version']

    if page and pageSize:
        num = (page-1) * pageSize
        model_list = my_db.get_col(WORK_FLOW_ALGORITHM_CONSTANT).find().sort("serial_number").skip(num).limit(pageSize)
        response_data['page'] = page
        response_data['total'] = model_list.count()
        response_data['pageSize'] = pageSize
    else:
        model_list = my_db.get_col(WORK_FLOW_ALGORITHM_CONSTANT).find().sort("serial_number")
        response_data['page'] = 0
        response_data['total'] = model_list.count()
        response_data['pageSize'] = 0
    
    response_data['list'] = []
    for model in model_list:  
        iter={}     
        iter['serialNumber'] = model['algorithm_constant_num']
        iter['id'] = model['algorithm_constant_id']
        iter['modelName'] = model['algorithm_constant_name']
        iter['algorithmVersion'] = model['algorithm_version']
        response_data['list'].append(iter)

    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 56
    return jsonify(response_data)


@bp.route('/baseInfo/saveOrUpdate', methods=['GET','POST'])
@login_required
def saveOrUpdate():   
    '''
    接口注释：设置基础信息保存修改
    '''
    my_db = ToMongo('wavedevice')
    params = request.get_json()
    equipment_name = params.get("equipmentName", None)
    installation_position = params.get("installationPosition", None)
    equipment_model = params.get("equipmentModel", None)
    equipment_serial_number = params.get("equipmentSerialNumber", None)
    hardware_version = params.get("hardwareVersion", None)
    video_camera_num = params.get("videoCameraNum", None)
    web_version = params.get("webVersion", None)
    algorithm_server_version = params.get("algorithmServerVersion", None)
    user_id = params.get("userId", None)

    res ={'equipment_name':equipment_name,'installation_position':installation_position,'equipment_model':equipment_model,
            'equipment_serial_number': equipment_serial_number,'hardware_version':hardware_version,'video_camera_num':video_camera_num,
            'web_version':web_version,'algorithm_server_version':algorithm_server_version}

    my_db.update('authority_base_info',
                    {},
                    {'$set':res}
                )


    response_data = {}
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 556
    return jsonify(response_data)

@bp.route('/networkConfiguration/getNetworkConfiguration', methods=['GET','POST'])
@login_required
def getNetworkConfiguration():   
    '''
    接口注释：获取当前用户的网络配置信息
    '''
    my_db = ToMongo('wavedevice')
    network_coll = my_db.get_col('authority_network_configuration').find()
    networkinfo = list(network_coll)[0]
    response_data = {}
    response_data['ipv4Address'] = networkinfo['IPv4_address']
    response_data['ipv4Mask'] = networkinfo['IPv4_mask']
    response_data['ipv4Gateway'] = networkinfo['IPv4_gateway']
    response_data['ipv6Address'] = networkinfo['IPv6_address']
    response_data['ipv6Mask'] = networkinfo['IPv6_mask']
    response_data['ipv6Gateway'] = networkinfo['IPv6_gateway']
    response_data['macAddress'] = networkinfo['mac_address']
    response_data['dnsServer'] = networkinfo['dns_server']
    response_data['spareDnsServer'] = networkinfo['spare_dns_server']

    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 556
    return jsonify(response_data)


@bp.route('/mailServiceSetting/saveOrUpdate', methods=['GET','POST'])
@login_required
def saveOrUpdate3():   
    '''
    接口注释：获取当前用户的ntp配置信息
    '''
    my_db = ToMongo('wavedevice')
    params = request.get_json()
    mail_account = params.get("mailAccount", None)
    mail_password = params.get("mailPassword", None)
    mail_send_name = params.get("mailSendName", None)
    mail_server_port = params.get("mailServerPort", None)
    mail_smtp_address = params.get("mailSmtpAddress", None)
    mail_smtp_type = params.get("mailSmtpType", None)
    user_id = params.get("userId", None)

    organization_id = my_db.get_col('authority_user').find_one({'user_id':user_id})['organization_id']

    last_modify_time = datetime.now()
    res ={'mail_account':mail_account,'mail_password':mail_password,'mail_send_name':mail_send_name,
            'mail_server_port': mail_server_port,'mail_smtp_address':mail_smtp_address,'mail_smtp_type':mail_smtp_type,'last_modify_time':last_modify_time
         }

    my_db.update('authority_mail_service_setting',
                    {'organization_id':organization_id},
                    {'$set':res}
                )


    response_data = {}
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 556
    return jsonify(response_data)

@bp.route('/mailServiceSetting/testMailSend', methods=['GET','POST'])
@login_required
def testMailSend():   
    '''
    接口注释:测试邮箱发信
    '''
    params = request.get_json()
    accessToken = params.get("accessToken", None)
    mail_account = params.get("mailAccount", None)
    mail_password = params.get("mailPassword", None)
    mail_send_name = params.get("mailSendName", None)
    mail_server_port = params.get("mailServerPort", None)
    mail_smtp_address = params.get("mailSmtpAddress", None)
    mail_smtp_type = params.get("mailSmtpType", None)
    toMail = params.get("toMail", None)
    user_id = params.get("userId", None)

    response_data = {}
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 556

    content = '"Hi,感知平台\n邮箱测试成功!"'
    subject = '"感知平台邮箱测试"'
    cmd_mail =  'echo ' + content + '|/data/ebox/mail/mailx -s ' + subject + ' -S smtp=' + mail_smtp_address + ' -S from=' + mail_send_name + ' -S smtp-auth-user=' + mail_account + ' -S smtp-auth-password=' + mail_password +' -S smtp-auth="login" '+ toMail

    err,result = execShell(cmd_mail)
    if result:
        response_data['requestStatus'] = "FAIL"
        response_data['errorCode'] =    "FAIL"
        response_data['errorCodeDesc'] = "测试发邮件失败"
        response_data['exceptionCodeDesc'] = ""
        return jsonify(response_data)

    return jsonify(response_data)

@bp.route('/auth/updateSystemSetting', methods=['GET','POST'])
@login_required
def updateSystemSetting():   
    '''
    接口注释：修改系统名称或告警弹窗状态
    '''
    my_db = ToMongo('wavedevice')
    params = request.get_json()
    emergency_pop_state = params.get("emergencyPopState", None)
    system_name = params.get("systemName", None)
    file_type = params.get("fileType", None)
    homeOverviewStyle = params.get("homeOverviewStyle", None)
    centerType = params.get("centerType", None) #大屏内容风格 1、统计数据  2、实时视频
    systemNameScreen = params.get("systemNameScreen", None)  #大屏标题


    centerType = str(centerType) if centerType else None
    query = {'file_type':file_type}
    res = {
           'emergency_pop_state':emergency_pop_state,
           'system_name':system_name,
           'home_overview_style':homeOverviewStyle,
           'center_type':centerType,
           'system_name_screen':systemNameScreen
           }

    my_db.update('system_setting',
                    query,
                    {'$set':res}
                )

    emergencyPop_queue.put(emergency_pop_state)     #弹窗状态存入消息队列 0弹窗  1不弹窗
    response_data = {}
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 556
    return jsonify(response_data)

@bp.route('/networkConfiguration/saveOrUpdate', methods=['GET','POST'])
@login_required
def saveOrUpdate4():   
    '''
    接口注释：保存更新当前用户的网络配置信息
    '''
    my_db = ToMongo('wavedevice')
    params = request.get_json()
    dns_server = params.get("dnsServer", None)
    IPv4_address = params.get("ipv4Address", None)
    IPv4_gateway = params.get("ipv4Gateway", None)
    IPv4_mask = params.get("ipv4Mask", None)
    IPv6_address = params.get("ipv6Address", None)
    IPv6_gateway = params.get("ipv6Gateway", None)
    IPv6_mask = params.get("ipv6Mask", None)
    mac_address = params.get("macAddress", None)
    spare_dns_server = params.get("spareDnsServer", None)

    cmd_str = '/bm_bin/bm_set_ip eth0 %s %s %s %s' % (IPv4_address , IPv4_mask , IPv4_gateway , dns_server)
    set_ip_thread = Thread(target = execShell , args = (cmd_str,))
    set_ip_thread.start()
    last_modify_time = datetime.now()
    res ={'dns_server':dns_server,'IPv4_address':IPv4_address,'IPv4_gateway':IPv4_gateway,
            'IPv4_mask': IPv4_mask,'IPv6_address':IPv6_address,'IPv6_gateway':IPv6_gateway,
            'IPv6_mask':IPv6_mask,'mac_address':mac_address,'spare_dns_server':spare_dns_server,'last_modify_time':last_modify_time
         }

    my_db.update('authority_network_configuration',
                    {},
                    {'$set':res}
                )


    response_data = {}
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 556
    return jsonify(response_data)


@bp.route('/setting/getCunrrentIp', methods=['GET','POST'])
@login_required
def getCunrrentIp():   
    '''
    接口注释：获取当前ip
    '''
    #从eth0文件获取ip信息
    try:
        eth0_res = get_eth0_ipv4()
        macV4,macV6 = get_mac() #获取MAc地址

        if not eth0_res:
            err0,result0 = execShell("/sbin/ifconfig eth0")    
            result0 = result0.split()
            if 'inet' in result0 and 'netmask' in result0:
                ipv4_addr = result0[5]
                ipv4_mask = result0[7]
                ipv4_broadcast = result0[9]
                ipv4_dns = '8.8.8.8'
            else:
                ipv4_addr = None
                ipv4_mask = None
                ipv4_broadcast = None
                ipv4_dns = None
        else:
            ipv4_addr = eth0_res[0]
            ipv4_mask = eth0_res[1]
            ipv4_broadcast = eth0_res[2]
            ipv4_dns = eth0_res[3]

        eth1_res = get_eth1_ipv6() 

        data = []
        item0,item1={},{}
        item0['dnsService'] = ipv4_dns
        item0['ipv4Broadcast'] = ipv4_broadcast
        item0['ipv4Inet'] = ipv4_addr
        item0['ipv4netmask'] = ipv4_mask
        item0['macAddress'] = macV4
        item0['type'] = "1"
        item0['typeName'] = "WAN口"
        data.append(item0)

        if eth1_res:
            item1['ipv4Broadcast'] = eth1_res[0] 
            item1['ipv4Inet'] = eth1_res[1]
            item1['ipv4netmask'] = eth1_res[2]
        else:
            item1['ipv4Broadcast'] = None
            item1['ipv4Inet'] = None
            item1['ipv4netmask'] = None
        item1['dnsService'] = '8.8.8.8'       
        item1['macAddress'] = macV6
        item1['type'] = "2"
        item1['typeName'] = "LAN口"
        data.append(item1)
    except Exception as e:
        mainlogger.info("--getCunrrentIp error :%s"%e)
        data = []

    response_data = {}
    response_data['data'] = data
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 556
    return jsonify(response_data)

@bp.route('/setting/modifyCunrrentIp', methods=['GET','POST'])
@login_required
def modifyCunrrentIp():   
    '''
    接口注释：修改盒子的ip、网关等
    '''
    cmd_reboot = "/sbin/reboot"
    bash_set_ip = "/bm_bin/bm_set_ip"

    params = request.get_json()
    ipv4Inet = params.get("ipv4Inet", None)
    ipv4netmask = params.get("ipv4netmask", None)
    ipv4Broadcast = params.get("ipv4Broadcast", None)
    dnsService = params.get("dnsService", None)
    spareDnsServer = params.get("spareDnsServer", None)

    if not dnsService:
        dns = spareDnsServer if spareDnsServer else "114.114.114.114"
    else:
        dns = dnsService

    cmd_set_ip = bash_set_ip + " eth0 " + ipv4Inet + " " + ipv4netmask + " " + ipv4Broadcast + " " + dns
    err0,result0 = execShell(cmd_set_ip)
    err1,result1 = execShell(cmd_reboot)

    response_data = {}
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 56
    return jsonify(response_data)

@bp.route('/setting/getSmsAccessInfo', methods=['GET','POST'])
@login_required
def getSmsAccessInfo():   
    '''
    接口注释：获取短信sms配置信息
    '''
    my_db = ToMongo('wavedevice')
    sms_col = my_db.get_col('odin_advise_sms_config').find()

    item = {}
    if sms_col.count() != 0:
        res = sms_col[0]
        item['alarmTempleteCode'] = res['alarm_templete_code']
        item['configId'] = res['config_id']
        item['diskTempleteCode'] = res['disk_templete_code']
        item['smsAccessKey'] = res['sms_access_key']
        item['smsAccessKeySecret'] = res['sms_access_key_secret']
        item['smsSignName'] = res['sms_sign_name']

    response_data = {}
    response_data['data'] = item
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 56
    return jsonify(response_data)

@bp.route('/setting/modifySmsAccessInfo', methods=['GET','POST'])
@login_required
def modifySmsAccessInfo():   
    '''
    接口注释：修改短信sms配置信息
    '''
    params = request.get_json()
    accessToken = params.get("accessToken", None)
    alarmTempleteCode = params.get("alarmTempleteCode", None)
    configId = params.get("configId", None)
    diskTempleteCode = params.get("diskTempleteCode", None)
    smsAccessKey = params.get("smsAccessKey", None)
    smsAccessKeySecret = params.get("smsAccessKeySecret", None)
    smsSignName = params.get("smsSignName", None)

    my_db = ToMongo('wavedevice')
    sms_col = my_db.get_col('odin_advise_sms_config').find()

    item = {}    
    item['alarm_templete_code'] = alarmTempleteCode
    item['config_id'] = configId
    item['disk_templete_code'] = diskTempleteCode
    item['sms_access_key'] = smsAccessKey
    item['sms_access_key_secret'] = smsAccessKeySecret
    item['sms_sign_name'] = smsSignName

    my_db.update("odin_advise_sms_config",{"config_id":configId},{"$set":item})

    smsconfig_state = 1
    smsconfig_queue.put(smsconfig_state)     #短信投递重新拉取配置存入消息队列 0不变  1重新拉取

    response_data = {}
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 56
    return jsonify(response_data)

@bp.route('/workModel/getWorkModelInfo', methods=['GET','POST'])
@login_required
def getWorkModelInfo():   
    '''
    接口注释：获取工作模式信息
    '''
    my_db = ToMongo('wavedevice')
    work_model = my_db.get_col('authority_work_model').find()[0]
    
    info = {}
    info['model'] = work_model['model']
    info['organizationId'] = work_model['organization_id']
    info['serviceOrganizationId'] = work_model['service_organization_id']
    info['serviceAddress'] = work_model['service_address']
    info['servicePort'] = work_model['service_port']
    info['serviceAccount'] = work_model['service_account']
    info['createTime'] = int(work_model['create_time'].timestamp())
    info['lastModifyTime'] = int(work_model['last_modify_time'].timestamp())

    response_data = {}
    response_data['wrokModelEntityInfo'] = info
    response_data['requestId'] = uuid.uuid4().hex
    response_data['requestStatus'] = "SUCCESS"
    response_data['timeUsed'] = 56
    return jsonify(response_data)

@bp.route('/setting/downloadFile', methods=['GET','POST'])
def downloadFile():   
    '''
    接口注释：帮助文档
    '''
    filepath = "/data/ebox/wavegate/operationManual.doc"
    if os.path.exists(filepath):
        return send_file(filepath,as_attachment=True,cache_timeout=0)
    else:
        return None

@bp.route('/setting/addApikey', methods=['GET','POST'])
@login_required
def addApikey():   
    '''
    接口注释：第三方接口的api密钥
    '''
    params = request.get_json()
    apiKey = params.get('apiKey')
    my_db = ToMongo('wavedevice')
    item = {'public_dict_param1':apiKey}
    query = {'public_dict_type':2}
    my_db.update('public_dict_baseinfo',query,item)
    response = set_success_result()
    return jsonify(response)

@bp.route('/setting/queryApiKey', methods=['GET','POST'])
@login_required
def queryApiKey():   
    '''
    接口注释：查询第三方接口的api密钥
    '''
    my_db = ToMongo('wavedevice')
    api_col = my_db.get_col('public_dict_baseinfo')
    query = {'public_dict_type':2}
    item = api_col.find_one(query)
    apiKey = item.get('public_dict_param1')

    response = set_success_result()
    response['apiKey'] = apiKey
    return jsonify(response)

@bp.route('/workModel/testWorkModel', methods=['GET','POST'])
@login_required
def testWorkModel():   
    '''
    接口注释：联网模式连接测试
    '''
    params = request.get_json()
    serviceAccount = params.get("serviceAccount", None)
    serviceAddress = params.get("serviceAddress", None)
    password = params.get("servicePwd", None)
    serviceAddress = check_service_addr(serviceAddress)

    paramDict = {'servicePwd':password,'serviceAccount':serviceAccount,'serviceAddress':serviceAddress}
    response_data,organization_id,bind_organization_id = request_login_url(params=paramDict) 
    return jsonify(response_data)


@bp.route('/workModel/setWorkModel', methods=['GET','POST'])
@login_required
def setWorkModel():   
    '''
    接口注释：保存ssas平台数据中心地址+账户
    '''
    params = request.get_json()
    accessToken = params.get("accessToken", None)
    serviceAccount = params.get("serviceAccount", None)
    serviceAddress = params.get("serviceAddress", None)
    password = params.get("servicePwd", None)
    model = params.get("model", None)

    serviceAddress = check_service_addr(serviceAddress)

    error_response = set_fail_result()
    success_response = set_success_result()

    my_db = ToMongo('wavedevice')

    if model == '0':
        #更新模式为单机模式
        item = {"model":model}
        my_db.update("authority_work_model",{},{"$set":item})
        glv.set_value('model','0')
        return jsonify(success_response)

    paramDict = {'servicePwd':password,'serviceAccount':serviceAccount,'serviceAddress':serviceAddress}
    response_data,organization_id,bind_organization_id = request_login_url(params=paramDict)
    requestStatus = response_data.get("requestStatus",None)
    if requestStatus == "FAIL":
        #登录失败
        return jsonify(response_data)

    register_item,content,origin_mode = query_edge_service(my_db)
    register_item['organizationId'] = organization_id
    register_item['bindOrganizationId'] = bind_organization_id
    
    response = register_device(remote_url=serviceAddress,content=register_item)

    if response['requestStatus'] == "SUCCESS":           
        #更改盒子模式为联网模式
        item = {"last_modify_time": datetime.now(),
                "service_address": serviceAddress,
                "model": '1',
                "service_account": serviceAccount,
                "organization_id":organization_id,
                "service_organization_id":bind_organization_id}
        my_db.update("authority_work_model",{},{"$set":item})

        param = item.copy()
        param['bind_organization_id'] = bind_organization_id
        #初始化全局变量
        init_param(param)

        #开启轮询心跳接口的进程
        sync_data = SyncTimer()
        sync_data.init_base_info()
        sync_data.post_all_data()
        if origin_mode == '0':
            #一直发送心跳
            sync_data.heartbeat_thread()
        
    else:
        error_response['errorCodeDesc'] = "向云平台发起注册请求失败"
        mainlogger.info("向云平台发起注册请求失败!")        
        return jsonify(error_response)

    return jsonify(success_response)


camerakeys_database = ['organization_id', 'camera_status', 'code_stream', 'product_key', 'camera_id', 'encoding_format', 'camera_password', 'camera_remarks', 'extend_info', 'update_time', 'set_type', 'camera_mac', 'create_time', 'camera_ip_label', 'videotape', 'camera_name', 'rtsp_port', 'camera_type', 'camera_account', 'service_id', 'report_frequency', 'camera_num', 'main_url', 'camera_ip', 'camera_source','live_url']
camerakeys_web = ['organizationId', 'cameraStatus', 'codeStream', 'productKey', 'cameraId', 'encodingFormat', 'cameraPassword', 'cameraRemarks', 'extendInfo', 'updateTime', 'setType', 'cameraMac', 'createTime', 'cameraIpLabel', 'videotape', 'cameraName', 'rtspPort', 'cameraType', 'cameraAccount', 'serviceId', 'reportFrequency', 'cameraNum', 'mainUrl', 'cameraIp', 'cameraSource','liveUrl']
camerakeys_server = ['organizationId', 'cameraStatus', 'codeStream', 'productKey', 'cameraId', 'encodingFormat', 'cameraPassword', 'cameraRemarks', 'extendInfo', 'cameraUpdateTime', 'setType', 'cameraMac', 'cameraCreateTime', 'cameraIpLabel', 'videotape', 'cameraName', 'rtspPort', 'cameraType', 'cameraAccount', 'serviceId', 'reportFrequency', 'cameraNum', 'mainUrl', 'cameraIp', 'cameraSource','liveUrl']

positionkeys_database = ['create_time', 'position_area', 'position_desc', 'position_num', 'lon_and_lat', 'update_time', 'position_id', 'position_province', 'position_county', 'position_city', 'organization_id','camera_id']
positionkeys_web = ['createTime', 'positionArea', 'positionDesc', 'positionNum', 'lonAndLat', 'updateTime', 'positionId', 'positionProvince', 'positionCounty', 'positionCity', 'organizationId','cameraId']


instance_database = ['time_range_num', 'model_id', 'discern_type', 'mission_id', 'organization_id', 'is_use', 'instance_group', 'rate_num', 'last_time', 'algorithm_constant_num', 'count_limit', 'instance_id', 'interval_time', 'instance_path', 'create_time','algorithm_service_num','face_list']
instance_web =      ['timeRangeNum', 'modelId', 'discernType', 'missionId', 'organizationId', 'isUse', 'instanceGroup', 'rateNum', 'lastTime', 'algorithmConstantNum', 'countLimit', 'instanceId', 'intervalTime', 'instancePath', 'createTime','algorithmServiceNum','faceList']

business_control_database = ['organization_id', 'control_name', 'storage_time', 'storage_num', 'device_sn', 'control_id', 'create_user', 'create_time']
business_control_web = ['organizationId', 'controlName', 'storageTime', 'storageNum', 'deviceSn', 'controlId', 'createUser', 'createTime']

mission_database = ['mission_id', 'mission_start_time', 'emergency_music_close_method', 'organization_id', 'mission_status', 'mission_end_time', 'mission_type', 'emergency_interval_time', 'create_time', 'emergency_audio', 'emergency_level', 'algorithm_id']
mission_web = ['missionId', 'missionStartTime', 'emergencyMusicCloseMethod', 'organizationId', 'missionStatus', 'missionEndTime', 'missionType', 'emergencyIntervalTime', 'createTime', 'emergencyAudio', 'emergencyLevel', 'algorithmId']

personnel_database = ['organization_id', 'personnel_sex', 'personnel_phone_number', 'device_sn', 'personnel_driving_number', 'personnel_local_address', 'personnel_email', 'personnel_id', 'personnel_social_card', 'reside_group_size', 'personnel_age', 'personnel_driving_type', 'working_date', 'wechat_open_id', 'personnel_number', 'personnel_name', 'personnel_birth', 'create_time', 'personnel_nation', 'personnel_remarks']
personnel_web = ['organizationId', 'personnelSex', 'personnelPhoneNumber', 'deviceSn', 'personnelDrivingNumber', 'personnelLocalAddress', 'personnelEmail', 'personnelId', 'personnelSocialCard', 'resideGroupSize', 'personnelAge', 'personnelDrivingType', 'workingDate', 'wechatOpenId', 'personnelNumber', 'personnelName', 'personnelBirth', 'createTime', 'personnelNation', 'personnelRemarks']

personnel_image_database = ['image_operation_statue', 'image_type', 'image_checksum', 'image_url', 'image_check_url', 'image_id', 'personnel_id', 'create_time']
personnel_image_web = ['imageOperationStatue', 'imageType', 'imageChecksum', 'imageUrl', 'imageCheckUrl', 'imageId', 'personnelId', 'createTime']

personnel_group_database = ['personnel_group_type', 'personnel_group_name', 'personnel_group_id', 'organization_id', 'personnel_group_remarks', 'create_time', 'personnel_group_level']
personnel_group_web = ['personnelGroupType', 'personnelGroupName', 'personnelGroupId', 'organizationId', 'personnelGroupRemarks', 'createTime', 'personnelGroupLevel']

version_server = ['modifyTime','organizationId','versionNumber','name']
version_database = ['modify_time','organization_id','version_number','name']

emergency_database = ['storage_num', 'storage_time', 'device_id', 'emergency_audio', 'sub_source_id', 'trid', 'emergency_exec_name', 'emergency_time', 'emergency_music_close_method', 'mission_id', 'emergency_lon_and_lat', 'tid', 'media_info', 'emergency_level', 'model_path', 'device_name', 'emergency_music_close_status', 'alarm_status', 'organization_id', 'emergency_device_id', 'emergency_exec_desc', 'position_id', 'emergency_exec_flag', 'create_time', 'device_num', 'control_name', 'emergency_media_info', 'is_wrong', 'emergency_exec_result', 'emergency_position', 'model_name', 'emergency_record_id']
emergency_server = ['storageNum', 'storageTime', 'deviceId', 'emergencyAudio', 'subSourceId', 'trid', 'emergencyExecName', 'emergencyTime', 'emergencyMusicCloseMethod', 'missionId', 'emergencyLonAndLat', 'tid', 'mediaInfo', 'emergencyLevel', 'modelPath', 'deviceName', 'emergencyMusicCloseStatus', 'alarmStatus', 'organizationId', 'emergencyDeviceId', 'emergencyExecDesc', 'positionId', 'emergencyExecFlag', 'createTime', 'deviceNum', 'controlName', 'emergencyMediaInfo', 'falseAlarmStatus', 'emergencyExecResult', 'emergencyPosition', 'modelName', 'emergencyRecordId']

emergency_detail_database = ['algorithm_constant_num', 'group_num', 'base_personnel_nation', 'emergency_record_id', 'group_matter_name', 'emergency_alarm_extra_info', 'step_time', 'emergency_image_extra_info', 'emergency_image', 'emergency_record_detail_info_id', 'base_personnel_birth', 'is_wrong', 'discern_time', 'base_personnel_image', 'num', 'base_personnel_sex', 'base_personnel_id', 'base_personnel_name', 'video_preview_image', 'step_num']
emergency_detail_server = ['algorithmConstantNum', 'groupNum', 'basePersonnelNation', 'emergencyRecordId', 'groupMatterName', 'emergencyAlarmExtraInfo', 'stepTime', 'emergencyImageExtraInfo', 'emergencyImage', 'emergencyRecordDetailInfoId', 'basePersonnelBirth', 'falseAlarmStatus', 'discernTime', 'basePersonnelImage', 'num', 'basePersonnelSex', 'basePersonnelId', 'basePersonnelName', 'videoPreviewImage', 'stepNum']


advise_database = ['source_type', 'audio_type', 'advise_id', 'advise_content', 'create_time', 'advise_status', 'read_persons', 'birth_time', 'organization_id', 'parameter', 'advise_type']
advise_web = ['sourceType', 'audioType', 'adviseId', 'adviseContent', 'createTime', 'adviseStatus', 'readPersons', 'birthTime', 'organizationId', 'parameter', 'adviseType']

roi_database = ['roi_name', 'create_time', 'camera_id', 'roi_area_record_id', 'algorithm_constant_id', 'roi_id', 'roi_area_info', 'organization_id']
roi_server = ['roiName', 'createTime', 'cameraId', 'roiAreaRecordId', 'algorithmConstantId', 'roiId', 'roiAreaInfo', 'organizationId']

smsdelivery_database = ['device_name', 'delivery_phones', 'delivery_content', 'organization_id', 'control_name', 'update_time', 'model_path', 'trigger_condition', 'sms_delivery_name', 'create_time', 'sms_delivery_id']
smsdelivery_web = ['deviceName', 'deliveryPhones', 'deliveryContent', 'organizationId', 'controlName', 'updateTime', 'modelPath', 'triggerCondition', 'smsDeliveryName', 'createTime', 'smsDeliveryId']

webhook_database = ['frequency_count', 'frequency_type', 'create_time', 'update_time', 'delivery_content', 'request_headers', 'timeout', 'organization_id', 'request_type', 'webhook_delivery_id', 'webhook_delivery_address', 'webhook_delivery_name', 'frequency_date_format', 'job_id', 'trigger_condition']
webhook_web =      ['frequencyCount', 'frequencyType', 'createTime', 'updateTime', 'deliveryContent', 'requestHeaders', 'timeout', 'organizationId', 'requestType', 'webhookDeliveryId', 'webhookDeliveryAddress', 'webhookDeliveryName', 'frequencyDateFormat', 'jobId', 'triggerCondition']

equip_database = ['reset_delay_time', 'channel_number', 'equip_ip', 'equip_port', 'create_user', 'update_time', 'control_equip_id', 'mission_id', 'create_time', 'update_user', 'device_control_type', 'equip_type','equip_name','remark','equip_id']
equip_web =      ['resetDelayTime',   'channelNumber',  'equipIp',  'equipPort',  'createUser',  'updateTime',  'controlEquipId',   'missionId',  'createTime',  'updateUser',  'deviceControlType',   'equipType', 'equipName',   'remark','equipId']

constant_database = ['algorithm_version', 'algorithm_color', 'algorithm_constant_id', 'algorithm_constant_type', 'algorithm_constant_name', 'algorithm_level', 'algorithm_model', 'algorithm_interval', 'algorithm_constant_num', 'algorithm_constant_status','rate_num','algorithm_sound_type','algorithm_sound_file','algorithm_service_num']
constant_web =      ['algorithmVersion',  'algorithmColor',  'algorithmConstantId',   'algorithmConstantType',   'algorithmConstantName',   'algorithmLevel',  'algorithmModel',  'emergencyIntervalTime',  'algorithmConstantNum',   'algorithmConstantStatus',  'rateNum','algorithmSoundType','algorithmSoundFile','algorithmServiceNum']

#音箱设备
sound_database = ['sound_password', 'sound_id', 'talk_number', 'sound_no', 'sound_type', 'sound_name', 'sound_ip', 'organization_id', 'end_point_id', 'create_time', 'sound_status', 'area_id', 'sound_port', 'sound_account']
sound_web =      ['soundPassword',  'soundId',  'talkNumber',  'soundNo',  'soundType',  'soundName',  'soundIp', ' organizationId',  'endPointId', 'createTime', 'soundStatus', 'areaId', 'soundPort', 'soundAccount']

#itc server
itc_database = ['itc_server_id', 'itc_server_port', 'itc_server_address', 'itc_server_password', 'itc_server_account']
itc_web      = ['itcServerId',   'itcServerPort',   'itcServerAddress',   'itcServerPassword',   'itcServerAccount']

#control_manage
control_database = ['storage_time', 'control_id', 'create_user', 'device_sn', 'storage_num', 'organization_id', 'create_time', 'control_name']
control_web      = ['storageTime', 'controlId', 'createUser', 'deviceSn', 'storageNum', 'organizationId', 'createTime', 'controlName']
/*
 Navicat Premium Data Transfer

 Source Server         : 192.168.5.198_27017
 Source Server Type    : MongoDB
 Source Server Version : 30418 (3.4.18)
 Source Host           : 192.168.5.198:27017
 Source Schema         : wavedevice

 Target Server Type    : MongoDB
 Target Server Version : 30418 (3.4.18)
 File Encoding         : 65001

 Date: 12/12/2024 11:21:47
*/


// ----------------------------
// Collection structure for alert_log
// ----------------------------
db.getCollection("alert_log").drop();
db.createCollection("alert_log",{
    capped: true,
    size: 100096
});

// ----------------------------
// Collection structure for authority_base_info
// ----------------------------
db.getCollection("authority_base_info").drop();
db.createCollection("authority_base_info");

// ----------------------------
// Collection structure for authority_department
// ----------------------------
db.getCollection("authority_department").drop();
db.createCollection("authority_department");

// ----------------------------
// Collection structure for authority_identify_model
// ----------------------------
db.getCollection("authority_identify_model").drop();
db.createCollection("authority_identify_model");

// ----------------------------
// Collection structure for authority_mail_service_setting
// ----------------------------
db.getCollection("authority_mail_service_setting").drop();
db.createCollection("authority_mail_service_setting");

// ----------------------------
// Collection structure for authority_network_configuration
// ----------------------------
db.getCollection("authority_network_configuration").drop();
db.createCollection("authority_network_configuration");

// ----------------------------
// Collection structure for authority_organization
// ----------------------------
db.getCollection("authority_organization").drop();
db.createCollection("authority_organization");

// ----------------------------
// Collection structure for authority_permission
// ----------------------------
db.getCollection("authority_permission").drop();
db.createCollection("authority_permission");

// ----------------------------
// Collection structure for authority_role
// ----------------------------
db.getCollection("authority_role").drop();
db.createCollection("authority_role");

// ----------------------------
// Collection structure for authority_role_permission_associate
// ----------------------------
db.getCollection("authority_role_permission_associate").drop();
db.createCollection("authority_role_permission_associate");

// ----------------------------
// Collection structure for authority_sys_maintain
// ----------------------------
db.getCollection("authority_sys_maintain").drop();
db.createCollection("authority_sys_maintain");

// ----------------------------
// Collection structure for authority_time_setting
// ----------------------------
db.getCollection("authority_time_setting").drop();
db.createCollection("authority_time_setting");

// ----------------------------
// Collection structure for authority_user
// ----------------------------
db.getCollection("authority_user").drop();
db.createCollection("authority_user");

// ----------------------------
// Collection structure for authority_user_department_associate
// ----------------------------
db.getCollection("authority_user_department_associate").drop();
db.createCollection("authority_user_department_associate");

// ----------------------------
// Collection structure for authority_user_role_associate
// ----------------------------
db.getCollection("authority_user_role_associate").drop();
db.createCollection("authority_user_role_associate");

// ----------------------------
// Collection structure for authority_work_model
// ----------------------------
db.getCollection("authority_work_model").drop();
db.createCollection("authority_work_model");

// ----------------------------
// Collection structure for centimani_storage_live_choose_record
// ----------------------------
db.getCollection("centimani_storage_live_choose_record").drop();
db.createCollection("centimani_storage_live_choose_record");
db.getCollection("centimani_storage_live_choose_record").createIndex({
    device_id: ""
}, {
    name: "device_id_"
});
db.getCollection("centimani_storage_live_choose_record").createIndex({
    user_id: NumberInt("1")
}, {
    name: "user_id_1"
});

// ----------------------------
// Collection structure for control_device_algorithm_associate
// ----------------------------
db.getCollection("control_device_algorithm_associate").drop();
db.createCollection("control_device_algorithm_associate");

// ----------------------------
// Collection structure for control_manage_mission
// ----------------------------
db.getCollection("control_manage_mission").drop();
db.createCollection("control_manage_mission");

// ----------------------------
// Collection structure for crowd_entrance_camera_associate
// ----------------------------
db.getCollection("crowd_entrance_camera_associate").drop();
db.createCollection("crowd_entrance_camera_associate");

// ----------------------------
// Collection structure for crowd_entrance_exit_detail
// ----------------------------
db.getCollection("crowd_entrance_exit_detail").drop();
db.createCollection("crowd_entrance_exit_detail");

// ----------------------------
// Collection structure for crowd_entrance_exit_info
// ----------------------------
db.getCollection("crowd_entrance_exit_info").drop();
db.createCollection("crowd_entrance_exit_info");

// ----------------------------
// Collection structure for crowd_project_info
// ----------------------------
db.getCollection("crowd_project_info").drop();
db.createCollection("crowd_project_info");

// ----------------------------
// Collection structure for new_radar_log
// ----------------------------
db.getCollection("new_radar_log").drop();
db.createCollection("new_radar_log");

// ----------------------------
// Collection structure for odin_advise_info
// ----------------------------
db.getCollection("odin_advise_info").drop();
db.createCollection("odin_advise_info");

// ----------------------------
// Collection structure for odin_advise_sms_config
// ----------------------------
db.getCollection("odin_advise_sms_config").drop();
db.createCollection("odin_advise_sms_config");

// ----------------------------
// Collection structure for odin_advise_sms_delivery
// ----------------------------
db.getCollection("odin_advise_sms_delivery").drpo();
db.createCollection("odin_advise_sms_delivery");

// ----------------------------
// Collection structure for odin_advise_sms_delivery_record
// ----------------------------
db.getCollection("odin_advise_sms_delivery_record").drop();
db.createCollection("odin_advise_sms_delivery_record");

// ----------------------------
// Collection structure for odin_advise_webhook_delivery
// ----------------------------
db.getCollection("odin_advise_webhook_delivery").drop();
db.createCollection("odin_advise_webhook_delivery");

// ----------------------------
// Collection structure for odin_advise_webhook_delivery_record
// ----------------------------
db.getCollection("odin_advise_webhook_delivery_record").drop();
db.createCollection("odin_advise_webhook_delivery_record");

// ----------------------------
// Collection structure for odin_business_control_manage
// ----------------------------
db.getCollection("odin_business_control_manage").drop();
db.createCollection("odin_business_control_manage");

// ----------------------------
// Collection structure for odin_business_dynamic_emergency_record
// ----------------------------
db.getCollection("odin_business_dynamic_emergency_record").drop();
db.createCollection("odin_business_dynamic_emergency_record");

// ----------------------------
// Collection structure for odin_business_dynamic_threshold
// ----------------------------
db.getCollection("odin_business_dynamic_threshold").drop();
db.createCollection("odin_business_dynamic_threshold");

// ----------------------------
// Collection structure for odin_business_emergency_record
// ----------------------------
db.getCollection("odin_business_emergency_record").drop();
db.createCollection("odin_business_emergency_record");
db.getCollection("odin_business_emergency_record").createIndex({
    emergency_time: NumberInt("1")
}, {
    name: "emergency_time_1"
});
db.getCollection("odin_business_emergency_record").createIndex({
    model_path: NumberInt("1")
}, {
    name: "model_path_1"
});

// ----------------------------
// Collection structure for odin_business_emergency_record_detail_info
// ----------------------------
db.getCollection("odin_business_emergency_record_detail_info").drop();
db.createCollection("odin_business_emergency_record_detail_info");
db.getCollection("odin_business_emergency_record_detail_info").createIndex({
    emergency_record_id: NumberInt("1")
}, {
    name: "emergency_record_id_1"
});

// ----------------------------
// Collection structure for odin_device_area
// ----------------------------
db.getCollection("odin_device_area").drop();
db.createCollection("odin_device_area");

// ----------------------------
// Collection structure for odin_device_camera_edit
// ----------------------------
db.getCollection("odin_device_camera_edit").drop();
db.createCollection("odin_device_camera_edit");

// ----------------------------
// Collection structure for odin_device_device_position_associate
// ----------------------------
db.getCollection("odin_device_device_position_associate").drop();
db.createCollection("odin_device_device_position_associate");

// ----------------------------
// Collection structure for odin_device_equip
// ----------------------------
db.getCollection("odin_device_equip").drop();
db.createCollection("odin_device_equip");
db.getCollection("odin_device_equip").createIndex({
    mission_id: NumberInt("1")
}, {
    name: "mission_id_1"
});

// ----------------------------
// Collection structure for odin_device_itc_server
// ----------------------------
db.getCollection("odin_device_itc_server").drop();
db.createCollection("odin_device_itc_server");

// ----------------------------
// Collection structure for odin_device_lings_server
// ----------------------------
db.getCollection("odin_device_lings_server").drop();
db.createCollection("odin_device_lings_server");

// ----------------------------
// Collection structure for odin_device_position
// ----------------------------
db.getCollection("odin_device_position").drop();
db.createCollection("odin_device_position");

// ----------------------------
// Collection structure for odin_device_roi_area_record
// ----------------------------
db.getCollection("odin_device_roi_area_record").drop();
db.createCollection("odin_device_roi_area_record");

// ----------------------------
// Collection structure for odin_device_rotation_time
// ----------------------------
db.getCollection("odin_device_rotation_time").drop();
db.createCollection("odin_device_rotation_time");

// ----------------------------
// Collection structure for odin_device_sound
// ----------------------------
db.getCollection("odin_device_sound").drop();
db.createCollection("odin_device_sound");

// ----------------------------
// Collection structure for odin_device_underlay
// ----------------------------
db.getCollection("odin_device_underlay").drop();
db.createCollection("odin_device_underlay");

// ----------------------------
// Collection structure for odin_dynamic_device
// ----------------------------
db.getCollection("odin_dynamic_device").drop();
db.createCollection("odin_dynamic_device");

// ----------------------------
// Collection structure for odin_dynamic_device_model
// ----------------------------
db.getCollection("odin_dynamic_device_model").drop();
db.createCollection("odin_dynamic_device_model");

// ----------------------------
// Collection structure for odin_point
// ----------------------------
db.getCollection("odin_point").drop();
db.createCollection("odin_point");

// ----------------------------
// Collection structure for public_dict_baseinfo
// ----------------------------
db.getCollection("public_dict_baseinfo").drop();
db.createCollection("public_dict_baseinfo");

// ----------------------------
// Collection structure for radar_data_record
// ----------------------------
db.getCollection("radar_data_record").drop();
db.createCollection("radar_data_record");

// ----------------------------
// Collection structure for small_stall_mission
// ----------------------------
db.getCollection("small_stall_mission").drop();
db.createCollection("small_stall_mission");

// ----------------------------
// Collection structure for system_data_version
// ----------------------------
db.getCollection("system_data_version").drop();
db.createCollection("system_data_version");

// ----------------------------
// Collection structure for system_logo_url
// ----------------------------
db.getCollection("system_logo_url").drop();
db.createCollection("system_logo_url");

// ----------------------------
// Collection structure for system_setting
// ----------------------------
db.getCollection("system_setting").drop();
db.createCollection("system_setting");

// ----------------------------
// Collection structure for test
// ----------------------------
db.getCollection("test").drop();
db.createCollection("test");

// ----------------------------
// Collection structure for traffic_light_config
// ----------------------------
db.getCollection("traffic_light_config").drop();
db.createCollection("traffic_light_config");

// ----------------------------
// Collection structure for traffic_light_project
// ----------------------------
db.getCollection("traffic_light_project").drop();
db.createCollection("traffic_light_project");

// ----------------------------
// Collection structure for traffic_light_ruler
// ----------------------------
db.getCollection("traffic_light_ruler").drop();
db.createCollection("traffic_light_ruler");

// ----------------------------
// Collection structure for user_logs
// ----------------------------
db.getCollection("user_logs").drop();
db.createCollection("user_logs");

// ----------------------------
// Collection structure for user_logs_set
// ----------------------------
db.getCollection("user_logs_set").drop();
db.createCollection("user_logs_set");

// ----------------------------
// Collection structure for work_flow_algorithm_constant
// ----------------------------
db.getCollection("work_flow_algorithm_constant").drop();
db.createCollection("work_flow_algorithm_constant");

// ----------------------------
// Collection structure for work_flow_insight_model_algorithm_instance
// ----------------------------
db.getCollection("work_flow_insight_model_algorithm_instance").drop();
db.createCollection("work_flow_insight_model_algorithm_instance");

// ----------------------------
// Collection structure for work_flow_mission
// ----------------------------
db.getCollection("work_flow_mission").drop();
db.createCollection("work_flow_mission");

// ----------------------------
// Collection structure for work_flow_mission_device_associate
// ----------------------------
db.getCollection("work_flow_mission_device_associate").drop();
db.createCollection("work_flow_mission_device_associate");

// ----------------------------
// Collection structure for work_flow_mission_hidden
// ----------------------------
db.getCollection("work_flow_mission_hidden").drop();
db.createCollection("work_flow_mission_hidden");

// ----------------------------
// Collection structure for work_flow_mission_model_associate
// ----------------------------
db.getCollection("work_flow_mission_model_associate").drop();
db.createCollection("work_flow_mission_model_associate");

// ----------------------------
// Collection structure for work_flow_mission_personnel_associate
// ----------------------------
db.getCollection("work_flow_mission_personnel_associate").drop();
db.createCollection("work_flow_mission_personnel_associate");

// ----------------------------
// Collection structure for work_flow_mission_personnelgroup_associate
// ----------------------------
db.getCollection("work_flow_mission_personnelgroup_associate").drop();
db.createCollection("work_flow_mission_personnelgroup_associate");

// ----------------------------
// Collection structure for work_flow_personnel
// ----------------------------
db.getCollection("work_flow_personnel").drop();
db.createCollection("work_flow_personnel");

// ----------------------------
// Collection structure for work_flow_personnel_image
// ----------------------------
db.getCollection("work_flow_personnel_image").drop();
db.createCollection("work_flow_personnel_image");

// ----------------------------
// Collection structure for work_flow_personnel_personnelgroup_associate
// ----------------------------
db.getCollection("work_flow_personnel_personnelgroup_associate").drop();
db.createCollection("work_flow_personnel_personnelgroup_associate");

// ----------------------------
// Collection structure for work_flow_personnelgroup
// ----------------------------
db.getCollection("work_flow_personnelgroup").drop();
db.createCollection("work_flow_personnelgroup");

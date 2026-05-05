from queue import Queue

#人脸特征消息队列
faceidentification_queue = Queue(maxsize=1000)

#告警弹窗消息队列
emergencyPop_queue = Queue(maxsize=1000)

#短信投递配置消息队列
smsconfig_queue =    Queue(maxsize=1000)

#短信投递任务消息队列
smsdelivery_queue = Queue(maxsize=1000)

#告警转发任务消息队列
webdelivery_queue = Queue(maxsize=1000)

# 雷达消息处理队列
radar_message_receive_queue = Queue(maxsize=1000)

# ALG/雷达检测到人/车辆消息转发队列
vehicle_pedestrian_events_queue = Queue(maxsize=1000)
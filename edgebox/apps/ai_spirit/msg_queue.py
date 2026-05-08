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

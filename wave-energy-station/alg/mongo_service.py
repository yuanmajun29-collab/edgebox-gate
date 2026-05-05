import subprocess
from threading import Timer
import utils.logger as logger

mainlogger = logger.getLogger('main')


def check_port():
    cmd = 'lsof -i:27017'
    obj = subprocess.Popen((cmd), shell=True, stdout=subprocess.PIPE)
    restful = obj.stdout.read()
    return restful


def check_mongo():
    res = check_port()
    if not res:
        mainlogger.info('定时任务:Mongodb未启动')
        check_timer = Timer(3, check_mongo)
        check_timer.start()
        check_timer.join()
    else:
        return True


check_mongo_status = check_mongo()

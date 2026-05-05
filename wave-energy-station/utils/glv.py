def init():
    # print("GLV init")
    global _global_dict
    _global_dict = {}


def set_value(key, value):
    '''
    定义一个全局变量
    :param key:
    :param value:
    :return:
    '''
    # print("set value %s %s" %(key,value))
    _global_dict[key] = value


def get_value(key, default_value=None):
    '''
    取得一个全局变量，如果不存在则返回default_value
    :param key:
    :param value:
    :return:
    '''
    # print("get value %s %s" % (key, default_value))
    try:
        return _global_dict[key]
    except KeyError:
        return default_value

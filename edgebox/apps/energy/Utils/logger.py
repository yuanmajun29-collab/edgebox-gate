from __future__ import annotations

import logging
import threading
import yaml
import logging.config
import os

import Utils.glv as glv

glv.init()

initLock = threading.Lock()
rootLoggerInitialized = False


_DEPLOY_ROOT = "/data/ebox/wavegate/wave-energy-station"
_LOGGING_YAML_CANDIDATES = (
    os.path.join(_DEPLOY_ROOT, "Utils", "logging.yaml"),
    os.path.join(_DEPLOY_ROOT, "utils", "logging.yaml"),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "logging.yaml"),
)


def resolve_logging_config_path() -> str | None:
    """部署目录优先 ``Utils``，其次旧版 ``utils``，最后是仓库内 ``Utils/logging.yaml``。"""
    for p in _LOGGING_YAML_CANDIDATES:
        if os.path.isfile(p):
            return p
    return None


log_format = "%(asctime)s %(process)d-%(thread)d %(name)s [%(levelname)s] %(message)s"
level = logging.DEBUG
console_log = True

def setup_logging(default_path: str | None = None, default_level=logging.INFO):
    path = default_path if default_path is not None else resolve_logging_config_path()
    if path and os.path.isfile(path):
        with open(path, 'rt') as f:
            config = yaml.safe_load(f.read())
        logging.config.dictConfig(config)
    else:
        logging.basicConfig(level = default_level)


def init_handler(handler):
    handler.setFormatter(Formatter(log_format))


def init_logger(logger):
    setup_logging(None)


def initialize():
    global rootLoggerInitialized
    with initLock:
        if not rootLoggerInitialized:
            path = resolve_logging_config_path()
            if path is not None:
                os.path.getmtime(path)
            init_logger(logging.getLogger())
            rootLoggerInitialized = True


def getLogger(name=None):
    initialize()
    my_logger = logging.getLogger(name)
    return my_logger

class Formatter(logging.Formatter):
    DATETIME_HOOK = None

    def formatTime(self, record, datefmt=None):
        newDateTime = None

        if Formatter.DATETIME_HOOK is not None:
            newDateTime = Formatter.DATETIME_HOOK()

        if newDateTime is None:
            ret = logging.Formatter.formatTime(self, record, datefmt)
        else:
            ret = str(newDateTime)
        return ret

class RotatingFileHandlerByPID(logging.handlers.RotatingFileHandler):
    def __init__(self, filename, mode='a', maxBytes=0, backupCount=0, encoding=None, delay=False):
        '''

        '''
        pid = os.getpid()
        name = glv.get_value("LOG_FILE", "/data/ebox/wavegate/log-energy/system.log")
        #print("RotatingFileHandlerByPID: pid: %s,  name: %s" % (pid, name))
        super().__init__(name, mode, maxBytes, backupCount, encoding, delay)

def main():
    log = getLogger()
    log.info("this is info test")
    log.debug("this is just debug test")
    log.error("this is error test")

if __name__ == '__main__':
    main()

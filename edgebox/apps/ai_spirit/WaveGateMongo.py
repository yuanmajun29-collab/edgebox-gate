from flask import Flask

import Utils.edgebox_repo  # noqa: F401 — monorepo 根路径，供 edgebox.db / edgebox.config
from algorith_server.mongo_service import check_mongo
import config
from algorith_server.AlgorithServer_v2 import AlgorithServer
from home import home_bp
from device import device_bp,device_roibp
from device import  position_bp
from personnel import  personnel_bp
from control import control_bp,constant_bp,voice_bp
from system import log_bp,user_bp,system_bp,role_bp
from emergency import emergency_bp ,advise_bp
from thirdpaty import third_bp


class WaveGateMongoApp():
    def __init__(self):
        self.app = Flask(__name__)
        # 读取配置
        self.app.config.from_object(config)

        self.app.register_blueprint(home_bp)
        self.app.register_blueprint(system_bp)
        self.app.register_blueprint(user_bp)
        self.app.register_blueprint(role_bp)
        self.app.register_blueprint(log_bp)
        self.app.register_blueprint(emergency_bp)
        self.app.register_blueprint(advise_bp)
        self.app.register_blueprint(device_bp)
        self.app.register_blueprint(device_roibp)
        self.app.register_blueprint(position_bp)
        self.app.register_blueprint(personnel_bp)
        self.app.register_blueprint(control_bp)
        self.app.register_blueprint(constant_bp)
        self.app.register_blueprint(voice_bp)
        self.app.register_blueprint(third_bp)
              
        self.context = self.app.app_context()
        self.algorithServer = AlgorithServer(self.context)
        

    def run(self):
        self.algorithServer.start()        
        self.app.run('0.0.0.0',5000)
from flask import Flask

import Utils.edgebox_repo  # noqa: F401 — monorepo 根路径，供 edgebox_db / edgebox_config
import config
from home import home_bp
from device import device_bp, device_roibp, dynamic_bp
from device import position_bp
from personnel import personnel_bp, flow_bp
from control import control_bp, constant_bp, voice_bp
from system import log_bp, user_bp, system_bp, role_bp
from emergency import emergency_bp, advise_bp
from thirdpaty import third_bp

from device.konad_service import KNDserver
from device.temp_service import TempServer

from system.curve_misc import SerialNetServer
from config import CURVE_CONFIG, CROSSING_CONFIG
from system.crossroads_controller import run_crossroads_control
from algorith_server.AlgorithServer_new import AlgorithServerNew


class WaveGateMongoApp():
    def __init__(self):
        self.app = Flask(__name__)
        # 读取配置
        self.app.config.from_object(config)

        # 注册路由
        self.app.register_blueprint(home_bp)
        self.app.register_blueprint(system_bp)
        self.app.register_blueprint(user_bp)
        self.app.register_blueprint(role_bp)
        self.app.register_blueprint(log_bp)
        self.app.register_blueprint(emergency_bp)
        self.app.register_blueprint(advise_bp)
        self.app.register_blueprint(device_bp)
        self.app.register_blueprint(flow_bp)
        self.app.register_blueprint(device_roibp)
        self.app.register_blueprint(dynamic_bp)
        self.app.register_blueprint(position_bp)
        self.app.register_blueprint(personnel_bp)
        self.app.register_blueprint(control_bp)
        self.app.register_blueprint(constant_bp)
        self.app.register_blueprint(voice_bp)
        self.app.register_blueprint(third_bp)

        # 启动算法服务
        self.context = self.app.app_context()
        self.algorithServer = AlgorithServerNew(self.context)
        self.KNDservice = KNDserver(context=None)
        self.Tempservice = TempServer(context=None)

        if CURVE_CONFIG['use'] == 1:
            self.Serialservice = SerialNetServer(context=None)
        if CROSSING_CONFIG['use'] == 1:
            run_crossroads_control()

    def run(self):
        self.algorithServer.start()
        self.KNDservice.start()
        self.Tempservice.start()
        self.app.run('0.0.0.0', 5000)

import Utils.edgebox_repo  # noqa: F401 — monorepo 根路径，供 edgebox.db / edgebox.config

from edgebox.shared.flask_bootstrap import create_configured_app
from emergency import homepage_bp
from device import area_bp, position_bp, device_bp, device_roibp, dynamic_bp
from control import control_bp, algorithm_bp, control_emergency_bp
from emergency import emergency_bp, advise_bp
from system import log_bp, user_bp, system_bp, role_bp
from home import home_bp
from algorith_server.AlgorithServer_v2 import AlgorithServer

from device.Serialnetservice import SerialNetServer


class WaveEnergyStationApp():
    def __init__(self):
        self.app = create_configured_app()

        self.app.register_blueprint(user_bp)
        self.app.register_blueprint(area_bp)
        self.app.register_blueprint(position_bp)
        self.app.register_blueprint(homepage_bp)
        self.app.register_blueprint(control_bp)
        self.app.register_blueprint(algorithm_bp)

        self.app.register_blueprint(home_bp)

        self.app.register_blueprint(device_bp)
        self.app.register_blueprint(device_roibp)
        self.app.register_blueprint(dynamic_bp)

        self.app.register_blueprint(emergency_bp)
        self.app.register_blueprint(advise_bp)

        self.app.register_blueprint(system_bp)
        self.app.register_blueprint(role_bp)
        self.app.register_blueprint(log_bp)
        self.app.register_blueprint(control_emergency_bp)

        self.context = self.app.app_context()
        self.algorithServer = AlgorithServer(self.context)

        self.Serialservice = SerialNetServer(context=None)

    def run(self):
        self.algorithServer.start()
        self.app.run('0.0.0.0', 5000)

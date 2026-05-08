import Utils.edgebox_repo  # noqa: F401 — monorepo 根路径，供 edgebox.db / edgebox.config

from edgebox.shared.flask_bootstrap import create_configured_app
from edgebox.shared.energy_line import register_energy_blueprints
from algorith_server.AlgorithServer_v2 import AlgorithServer

from device.Serialnetservice import SerialNetServer


class WaveEnergyStationApp():
    def __init__(self):
        self.app = create_configured_app()
        register_energy_blueprints(self.app)

        self.context = self.app.app_context()
        self.algorithServer = AlgorithServer(self.context)

        self.Serialservice = SerialNetServer(context=None)

    def run(self):
        self.algorithServer.start()
        self.app.run('0.0.0.0', 5000)

import Utils.edgebox_repo  # noqa: F401 — monorepo 根路径，供 edgebox.db / edgebox.config

from algorith_server.AlgorithServer_v2 import AlgorithServer
from edgebox.shared.mongo_line.wave_gate_common import (
    create_configured_app,
    register_wave_gate_blueprints,
)


class WaveGateMongoApp():
    def __init__(self):
        self.app = create_configured_app()
        register_wave_gate_blueprints(self.app, full_mongo=False)

        self.context = self.app.app_context()
        self.algorithServer = AlgorithServer(self.context)

    def run(self):
        self.algorithServer.start()
        self.app.run('0.0.0.0', 5000)

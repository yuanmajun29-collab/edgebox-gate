import Utils.edgebox_repo  # noqa: F401 — monorepo 根路径，供 edgebox.db / edgebox.config

from edgebox.shared.mongo_line.wave_gate_common import (
    create_configured_app,
    register_wave_gate_blueprints,
)
from device.konad_service import KNDserver
from device.temp_service import TempServer

from system.curve_misc import SerialNetServer
from config import CURVE_CONFIG, CROSSING_CONFIG
from system.crossroads_controller import run_crossroads_control
from algorith_server.AlgorithServer_new import AlgorithServerNew


class WaveGateMongoApp():
    def __init__(self):
        self.app = create_configured_app()
        register_wave_gate_blueprints(self.app, full_mongo=True)

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

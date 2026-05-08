"""
Energy Station 共用：Blueprint 注册（顺序与原先 ``WaveEnergyStation.py`` 一致）。

需在已将 ``apps/energy`` 置于 ``sys.path`` 首位后再调用。
"""
from __future__ import annotations

__all__ = ["register_energy_blueprints"]


def register_energy_blueprints(app) -> None:
    from emergency import homepage_bp
    from device import area_bp, position_bp
    from control import control_emergency_bp
    from system import user_bp, system_bp
    from home import home_bp

    from edgebox.shared.wave_blueprint_segments import (
        register_control_algorithm_pair,
        register_device_bp_roibp_pair,
        register_dynamic_bp,
        register_emergency_advise_pair,
        register_role_log_pair,
    )

    app.register_blueprint(user_bp)
    app.register_blueprint(area_bp)
    app.register_blueprint(position_bp)
    app.register_blueprint(homepage_bp)
    register_control_algorithm_pair(app)

    app.register_blueprint(home_bp)

    register_device_bp_roibp_pair(app)
    register_dynamic_bp(app)

    register_emergency_advise_pair(app)

    app.register_blueprint(system_bp)
    register_role_log_pair(app)
    app.register_blueprint(control_emergency_bp)

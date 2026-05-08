"""
Energy Station 共用：Blueprint 注册（顺序与原先 ``WaveEnergyStation.py`` 一致）。

需在已将 ``apps/energy`` 置于 ``sys.path`` 首位后再调用。
"""
from __future__ import annotations

__all__ = ["register_energy_blueprints"]


def register_energy_blueprints(app) -> None:
    from emergency import homepage_bp
    from device import area_bp, position_bp, device_bp, device_roibp, dynamic_bp
    from control import control_bp, algorithm_bp, control_emergency_bp
    from emergency import emergency_bp, advise_bp
    from system import log_bp, user_bp, system_bp, role_bp
    from home import home_bp

    app.register_blueprint(user_bp)
    app.register_blueprint(area_bp)
    app.register_blueprint(position_bp)
    app.register_blueprint(homepage_bp)
    app.register_blueprint(control_bp)
    app.register_blueprint(algorithm_bp)

    app.register_blueprint(home_bp)

    app.register_blueprint(device_bp)
    app.register_blueprint(device_roibp)
    app.register_blueprint(dynamic_bp)

    app.register_blueprint(emergency_bp)
    app.register_blueprint(advise_bp)

    app.register_blueprint(system_bp)
    app.register_blueprint(role_bp)
    app.register_blueprint(log_bp)
    app.register_blueprint(control_emergency_bp)

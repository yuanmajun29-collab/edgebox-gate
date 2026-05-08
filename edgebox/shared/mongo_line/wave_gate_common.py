"""
Mongo / ai_spirit 共用：Blueprint 注册（顺序与原先 ``WaveGateMongo.py`` 一致）。

Flask 实例请使用 ``edgebox.shared.flask_bootstrap.create_configured_app``；本模块再导出该函数以兼容现有 import。

需在已将具体产品目录置于 ``sys.path`` 首位后再调用。
"""
from __future__ import annotations

from edgebox.shared.flask_bootstrap import create_configured_app

__all__ = ["create_configured_app", "register_wave_gate_blueprints"]


def register_wave_gate_blueprints(app, *, full_mongo: bool = False) -> None:
    """
    :param full_mongo: 为 True 时注册 ``flow_bp``、``dynamic_bp``（仅 ``apps/mongo``）。
    """
    from home import home_bp
    from device import device_bp, device_roibp, position_bp
    from personnel import personnel_bp
    from control import control_bp, constant_bp, voice_bp
    from system import log_bp, user_bp, system_bp, role_bp
    from emergency import emergency_bp, advise_bp
    from thirdpaty import third_bp

    app.register_blueprint(home_bp)
    app.register_blueprint(system_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(role_bp)
    app.register_blueprint(log_bp)
    app.register_blueprint(emergency_bp)
    app.register_blueprint(advise_bp)
    app.register_blueprint(device_bp)
    if full_mongo:
        from device import dynamic_bp
        from personnel import flow_bp

        app.register_blueprint(flow_bp)
    app.register_blueprint(device_roibp)
    if full_mongo:
        app.register_blueprint(dynamic_bp)
    app.register_blueprint(position_bp)
    app.register_blueprint(personnel_bp)
    app.register_blueprint(control_bp)
    app.register_blueprint(constant_bp)
    app.register_blueprint(voice_bp)
    app.register_blueprint(third_bp)

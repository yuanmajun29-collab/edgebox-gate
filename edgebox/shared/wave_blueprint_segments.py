"""
多条产品线共用的 Blueprint 注册小段（只做连续、顺序固定的若干 register）。

调用方负责在各自函数里按历史行为插入这些段的位置；不要在段内改变先后顺序。
"""
from __future__ import annotations

__all__ = [
    "register_emergency_advise_pair",
    "register_device_bp_roibp_pair",
    "register_dynamic_bp",
    "register_device_roibp_dynamic_pair",
]


def register_emergency_advise_pair(app) -> None:
    from emergency import emergency_bp, advise_bp

    app.register_blueprint(emergency_bp)
    app.register_blueprint(advise_bp)


def register_device_bp_roibp_pair(app) -> None:
    from device import device_bp, device_roibp

    app.register_blueprint(device_bp)
    app.register_blueprint(device_roibp)


def register_dynamic_bp(app) -> None:
    from device import dynamic_bp

    app.register_blueprint(dynamic_bp)


def register_device_roibp_dynamic_pair(app) -> None:
    """紧挨着的 ``device_roibp`` → ``dynamic_bp``（例如 mongo ``full_mongo`` 里接在 ``flow_bp`` 之后）。"""
    from device import device_roibp, dynamic_bp

    app.register_blueprint(device_roibp)
    app.register_blueprint(dynamic_bp)

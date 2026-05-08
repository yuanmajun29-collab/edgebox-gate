"""
edgebox_products — 统一入口，将三个产品线作为同一仓库内的可选模块运行。

- ``mongo`` → ``WaveGateMongo/``（全功能 Mongo 门）
- ``ai_spirit`` → ``wave-ai-spirit/``（精简 Mongo 门，模块名与网关同名 ``WaveGateMongo``）
- ``energy`` → ``wave-energy-station/``（能耗站）

运行时会把对应产品目录置于 ``sys.path`` 首位，以保留各目录内 ``import config`` /
``from device import ...`` 的既有语义。共享能力见 ``edgebox_config``、``edgebox_db``。

用法示例::

    EDGEBOX_PROFILE=energy python -m edgebox_products
    python -m edgebox_products mongo
    python -c \"from edgebox_products import create_product_app; create_product_app('energy').run()\"
"""

from .launcher import (
    PROFILES,
    create_product_app,
    default_profile,
    get_flask_app,
    install_product_paths,
    resolve_profile,
)

__all__ = [
    "PROFILES",
    "create_product_app",
    "default_profile",
    "get_flask_app",
    "install_product_paths",
    "resolve_profile",
]

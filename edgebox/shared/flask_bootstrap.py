"""
各产品线共用的最小 Flask 构造：`Flask(__name__)` + ``app.config.from_object(config)``。

``config`` 解析为当前 ``sys.path`` 上、产品目录内的同名模块（与原先各 ``*App`` 一致）。
"""
from __future__ import annotations

from flask import Flask


def create_configured_app() -> Flask:
    import config

    app = Flask(__name__)
    app.config.from_object(config)
    return app

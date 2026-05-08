"""
从仓库根启动指定产品模块（Flask 应用包装类与原有各目录 ``app.py`` 一致）。
"""
from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from typing import Any, Dict, Tuple, Union

REPO_ROOT = Path(__file__).resolve().parents[1]
_repo_s = str(REPO_ROOT)
if _repo_s not in sys.path:
    sys.path.insert(0, _repo_s)

# profile 键 → 产品根目录（相对 REPO_ROOT，统一在 products/ 下）
PRODUCT_ROOT: Dict[str, str] = {
    "mongo": "products/mongo",
    "ai_spirit": "products/ai_spirit",
    "energy": "products/energy",
}

# profile → (Python 模块名, 应用类名)
APP_SPEC: Dict[str, Tuple[str, str]] = {
    "mongo": ("WaveGateMongo", "WaveGateMongoApp"),
    "ai_spirit": ("WaveGateMongo", "WaveGateMongoApp"),
    "energy": ("WaveEnergyStation", "WaveEnergyStationApp"),
}

PROFILES = tuple(PRODUCT_ROOT.keys())

_ALIASES = {
    "wavegatemongo": "mongo",
    "wave-gate-mongo": "mongo",
    "mongogate": "mongo",
    "ai-spirit": "ai_spirit",
    "spirits": "ai_spirit",
    "wave_energy": "energy",
    "wave-energy-station": "energy",
    "energy-station": "energy",
}


def resolve_profile(name: Union[str, None]) -> str:
    if not name:
        name = os.environ.get("EDGEBOX_PROFILE", "mongo")
    key = str(name).strip().lower().replace(" ", "_")
    key = _ALIASES.get(key, key)
    if key not in PRODUCT_ROOT:
        raise ValueError(
            f"未知产品线 profile={name!r}，可选: {', '.join(PRODUCT_ROOT)} "
            f"或设置环境变量 EDGEBOX_PROFILE"
        )
    return key


def default_profile() -> str:
    """未显式传 profile 时的解析结果（环境变量 ``EDGEBOX_PROFILE``，缺省为 ``mongo``）。"""
    return resolve_profile(None)


def install_product_paths(profile: str) -> Path:
    """将产品目录插入 ``sys.path[0]``，保证 ``import config`` 等解析到该产品。"""
    p = resolve_profile(profile)
    root_name = PRODUCT_ROOT[p]
    product_dir = (REPO_ROOT / root_name).resolve()
    if not product_dir.is_dir():
        raise FileNotFoundError(f"产品目录不存在: {product_dir}")
    s = str(product_dir)
    try:
        sys.path.remove(s)
    except ValueError:
        pass
    sys.path.insert(0, s)
    return product_dir


def create_product_app(profile: Union[str, None] = None) -> Any:
    """
    实例化各产品自带的 App 类（与各自 ``app.py`` 中行为一致，含 ``.app`` / ``.run()``）。
    """
    p = resolve_profile(profile)
    install_product_paths(p)
    mod_name, cls_name = APP_SPEC[p]
    mod = importlib.import_module(mod_name)
    cls = getattr(mod, cls_name)
    return cls()


def get_flask_app(profile: Union[str, None] = None):
    """供 WSGI / 测试使用：返回 ``Flask`` 实例。"""
    bundle = create_product_app(profile)
    return bundle.app


def main(argv=None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="edgebox-gate 统一启动：选择 products/mongo | products/ai_spirit | products/energy",
    )
    parser.add_argument(
        "profile",
        nargs="?",
        default=os.environ.get("EDGEBOX_PROFILE", "mongo"),
        help="产品线: mongo | ai_spirit | energy（也可用环境变量 EDGEBOX_PROFILE）",
    )
    args = parser.parse_args(argv)
    app_bundle = create_product_app(args.profile)
    app_bundle.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""仓库根目录加入 ``sys.path`` 的唯一实现，供各 app 的 ``Utils.edgebox_repo`` 通过 importlib 加载。"""
from __future__ import annotations

import sys
from pathlib import Path

__all__ = ["activate"]


def activate(utils_package_dir: Path) -> Path:
    """将包含 ``edgebox/config`` 的仓库根插入 ``sys.path``（若尚未插入）。"""
    for anc in [utils_package_dir, *utils_package_dir.parents]:
        if (anc / "edgebox" / "config").is_dir():
            s = str(anc)
            if s not in sys.path:
                sys.path.insert(0, s)
            return anc
    raise RuntimeError("edgebox-gate root not found (missing edgebox/config/)")

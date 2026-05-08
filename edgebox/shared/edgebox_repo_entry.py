"""Put monorepo root on sys.path so ``edgebox.db`` / ``edgebox.config`` resolve."""
from __future__ import annotations

import importlib.util
from pathlib import Path


def _activate() -> None:
    utils_dir = Path(__file__).resolve().parent
    for anc in [utils_dir, *utils_dir.parents]:
        rp = anc / "edgebox" / "shared" / "repo_path.py"
        if rp.is_file():
            spec = importlib.util.spec_from_file_location(
                "edgebox.shared.repo_path",
                rp,
            )
            mod = importlib.util.module_from_spec(spec)
            assert spec.loader is not None
            spec.loader.exec_module(mod)
            mod.activate(utils_dir)
            return
    raise RuntimeError(
        "edgebox-gate root not found (missing edgebox/shared/repo_path.py)",
    )


_activate()

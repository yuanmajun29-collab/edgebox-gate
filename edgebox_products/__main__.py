"""python -m edgebox_products [mongo|ai_spirit|energy]（请在仓库根目录执行）。"""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from .launcher import main

if __name__ == "__main__":
    raise SystemExit(main())

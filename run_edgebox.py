"""
自仓库根运行：python run_edgebox.py [mongo|ai_spirit|energy]
等价于在仓库根执行：python -m edgebox_products
"""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from edgebox_products.launcher import main

if __name__ == "__main__":
    raise SystemExit(main())

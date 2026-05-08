import runpy
from pathlib import Path

_target = Path(__file__).resolve().parents[3] / "shared" / "mongo_line" / "scripts" / "insert_newalg.py"
runpy.run_path(str(_target), run_name="__main__")

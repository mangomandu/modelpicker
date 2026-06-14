import sys
from pathlib import Path

# Belt-and-suspenders: ensure src/ is importable even without the pyproject pythonpath.
SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


@pytest.fixture(scope="session", autouse=True)
def build_cpp_library() -> None:
    library = ROOT / "cpp" / "doonroute_cpp.dll"
    source = ROOT / "cpp" / "dijkstra.cpp"
    if not library.exists() or source.stat().st_mtime > library.stat().st_mtime:
        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "build_cpp.py")],
            check=True,
        )

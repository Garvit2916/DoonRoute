import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "scripts", ROOT / "tests"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


@pytest.fixture(scope="session", autouse=True)
def build_cython_extension() -> None:
    source = ROOT / "src" / "cython_dijkstra.pyx"
    extension = next(
        (
            candidate
            for pattern in ("cython_dijkstra*.pyd", "cython_dijkstra*.so")
            for candidate in (ROOT / "src").glob(pattern)
        ),
        None,
    )
    if extension is None or source.stat().st_mtime > extension.stat().st_mtime:
        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "build_cython.py")],
            check=True,
        )

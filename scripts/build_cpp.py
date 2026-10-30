from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "cpp" / "dijkstra.cpp"
OUTPUT = ROOT / "cpp" / "doonroute_cpp.dll"


def build() -> Path:
    compiler = shutil.which("g++")
    if compiler is None:
        raise RuntimeError("g++ was not found on PATH.")
    command = [
        compiler,
        "-O3",
        "-std=c++17",
        "-shared",
        "-static",
        "-Wall",
        "-Wextra",
        "-o",
        str(OUTPUT),
        str(SOURCE),
    ]
    print(" ".join(command))
    subprocess.run(command, check=True)
    print(f"Built {OUTPUT}")
    return OUTPUT


if __name__ == "__main__":
    build()

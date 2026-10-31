"""
Build the independent Cython Dijkstra extension.

Usage (from project root with the environment active):
    python setup.py build_ext --inplace

This compiles src/cython_dijkstra.pyx into a native C extension
(cython_dijkstra.cp311-win_amd64.pyd on Windows). No C++ source files
or C++ language features are used.

Requirements:
    - Python 3.11+ (64-bit)
    - Cython 3.x
    - Microsoft Build Tools 2022 with the MSVC C compiler

Windows setup:
    Install the "Desktop development with C++" workload from
    https://visualstudio.microsoft.com/visual-cpp-build-tools/
"""

from Cython.Build import cythonize
from setuptools import Extension, setup

setup(
    name="cython_dijkstra",
    ext_modules=cythonize(
        [
            Extension(
                "cython_dijkstra",
                sources=["src/cython_dijkstra.pyx"],
                # Pure C extension — no C++ sources, no C++ flags.
            ),
        ],
        language_level=3,
        compiler_directives={
            "language_level": "3",
            "boundscheck": False,
            "wraparound": False,
            "cdivision": True,
        },
    ),
)

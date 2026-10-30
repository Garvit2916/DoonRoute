from Cython.Build import cythonize
from setuptools import Extension, setup

setup(
    name="cython_dijkstra",
    ext_modules=cythonize(
        [
            Extension(
                "cython_dijkstra",
                sources=["src/cython_dijkstra.pyx", "cpp/dijkstra.cpp"],
                include_dirs=["cpp"],
                language="c++",
                extra_compile_args=["/std:c++17"],
            ),
        ],
        language_level=3,
        compiler_directives={"language_level": "3"},
    ),
)

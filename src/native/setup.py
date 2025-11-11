import os
from setuptools import Extension, setup

extra_args = ["/O2"] if os.name == "nt" else ["-O3"]

module = Extension(
    "c_nearest",
    sources=["c_nearest.c"],
    extra_compile_args=extra_args
)

setup(
    name="c_nearest",
    version="0.1.0",
    description="Native helpers for ParkWise nearest-violation queries",
    ext_modules=[module]
)

#!/usr/bin/env python3
"""Setup script for AegisDB."""

import os
import sys
from pathlib import Path
from setuptools import setup, find_packages

# Read requirements
with open("requirements.txt") as f:
    requirements = [line.strip() for line in f if line.strip() and not line.startswith("#")]

# Read README
with open("README.md", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="aegisdb",
    version="0.1.0",
    description="AegisDB: Autonomous AI SRE Copilot for CockroachDB & AWS",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Arthur-101",
    author_email="dev@aegisdb.io",
    url="https://github.com/Arthur-101/CockroachDB",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    include_package_data=True,
    install_requires=requirements,
    python_requires=">=3.8",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: POSIX :: Linux",
        "Operating System :: MacOS",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
    entry_points={
        "console_scripts": [
            "agenticai=src.cli.main:cli",
        ],
    },
)
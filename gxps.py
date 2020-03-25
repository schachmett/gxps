#!/usr/bin/env python3
"""GXPS launcher."""

from pathlib import Path
import os
import sys

from gxps.main import main

def set_gxps_env():
    """Find the location of gxps's working directory and insert it to sys.path
    """
    # pylint: disable=no-member
    basedir = Path(__file__).resolve().parents[0]
    if not (basedir / "gxps.py").is_file():
        basedir = Path().cwd()
        if not (basedir / "gxps.py").is_file():
            print("WARNING : gxps source path not found")
    sys.path.insert(0, str(basedir))
    os.environ["GXPS_DIR"] = str(basedir)


if __name__ == "__main__":
    set_gxps_env()
    main()

"""Provides platform-independent access to directories and configuration."""
# pylint has a bug with pathlib: https://github.com/PyCQA/pylint/issues/1660
# pylint: disable=no-member

import os
from pathlib import Path
import sys
from gi.repository import GLib


GXPS_DIR = Path(os.path.realpath(__file__)).parents[1]
# The following hack works only if the gxps.py setting the env var is
# one directory above the gxps package
if os.getenv("GXPS_DIR") and sys.platform == "win32":
    GXPS_DIR = Path(os.getenv("GXPS_DIR"))
    print("INFO    : Source dir taken from environment variable.")
HOME_DIR = os.path.expanduser("~")

# detect if running without being installed
LOCAL_HACK = (GXPS_DIR / "data").is_dir() and sys.platform != "win32"
# detect if running from a virtualenv
VENV = hasattr(sys, "real_prefix")

DATA_DIR = Path(GLib.get_user_data_dir()) / "gxps"
if LOCAL_HACK or sys.platform == "win32":
    DATA_DIR = GXPS_DIR / "data"
if VENV:
    DATA_DIR = Path(sys.prefix) / "share/gxps"
DATA_DIRS = [DATA_DIR]
if os.getenv("XDG_DATA_DIRS"):
    XDG_DATA_DIRS = os.getenv("XDG_DATA_DIRS").split(os.pathsep)
    DATA_DIRS.extend([Path(d) / "gxps" for d in XDG_DATA_DIRS])

CONF_DIR = Path(GLib.get_user_config_dir()) / "gxps"
CONF_DIRS = [CONF_DIR]
if os.getenv("XDG_CONFIG_DIRS"):
    XDG_CONFIG_DIRS = os.getenv("XDG_CONFIG_DIRS").split(os.pathsep)
    CONF_DIRS.extend([Path(d) / "gxps" for d in XDG_CONFIG_DIRS])
if LOCAL_HACK or sys.platform == "win32":
    CONF_DIRS.append(GXPS_DIR / "data/config")

CACHE_DIR = Path(GLib.get_user_cache_dir()) / "gxps"

LOG_DIR = CACHE_DIR / "logs"
if sys.platform == "win32":
    LOG_DIR = CONF_DIR / "logs"
LOG_FILE = LOG_DIR / "gxps.log"


def _make_missing_dirs():
    if not DATA_DIR.is_dir():
        os.makedirs(str(DATA_DIR))
    if not CONF_DIR.is_dir():
        os.makedirs(str(CONF_DIR))
    if not CACHE_DIR.is_dir():
        os.makedirs(str(CACHE_DIR))
    if not LOG_DIR.is_dir():
        os.makedirs(str(LOG_DIR))

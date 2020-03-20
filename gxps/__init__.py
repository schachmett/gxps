"""Loads the configuration ini and sets app name and version."""
# pylint: disable=invalid-name
# pylint: disable=wrong-import-order
# pylint: disable=logging-format-interpolation

__appname__ = "GXPS"
__authors__ = ["Simon Fischer <sf@simon-fischer.info>"]
__website__ = "https://github.com/schachmett/gxps"

from pbr.version import VersionInfo
__version__ = VersionInfo("gxps").version_string()


import os
from pathlib import Path
import configparser
import datetime
import sys
import logging
import logging.config
import traceback

from gi.repository import GLib


ASSETDIR = Path(os.path.realpath(__file__)).parents[0] / "assets/"
assert Path(ASSETDIR).is_dir()

CONFDIR = Path(GLib.get_user_config_dir()) / "gxps"
if not Path(CONFDIR).is_dir():
    os.makedirs(str(CONFDIR))

CFG_DEFAULTS = ASSETDIR / "config.ini"
CFG_PATH = CONFDIR / "config.ini"
COLOR_DEFAULTS = ASSETDIR / "colors.ini"
COLOR_CFG_PATH = CONFDIR / "colors.ini"
LOG_PATH = CONFDIR / "gxps.log"

CONFIG = configparser.ConfigParser()
CONFIG.read([str(CFG_DEFAULTS), str(CFG_PATH)])
def write_config():
    """Helper function for writing to correct path every time."""
    with open(str(CFG_PATH), "w") as cfg:
        CONFIG.write(cfg)
CONFIG.save = write_config

COLORS = configparser.ConfigParser()
COLORS.read([str(COLOR_DEFAULTS), str(COLOR_CFG_PATH)])
def write_colors():
    """Helper function for writing to correct path every time."""
    with open(str(COLOR_CFG_PATH), "w") as col:
        COLORS.write(col)
COLORS.save = write_colors

def activate_logging():
    """Configures the logging."""
    logging.config.dictConfig(logger_conf())
    logging.getLogger(__name__)
    logging.getLogger("matplotlib").setLevel(logging.WARNING)
    ex_logger = logging.getLogger("ExceptionLogger")
    def exception_handler(type_, value, tb):
        """Logs any exception."""
        tbstring = traceback.format_tb(tb)
        tbstring = [line.replace("\n", "") for line in tbstring]
        tbstring = (" " * 10).join(tbstring)
        ex_logger.error("Uncaught {}: {}, traceback: '{}'"
                        "".format(type_.__name__, value, tbstring))
        sys.__excepthook__(type_, value, tb)
    sys.excepthook = exception_handler
    file_handler = logging.getLogger("").handlers[1]
    file_handler.doRollover()


def logger_conf():
    """Logger configuration dictionary."""
    confdict = {
        "version": 1,
        "disable_existing_loggers": True,
        "formatters": {
            "verbose": {
                "format": "{levelname:8s} {asctime} "
                          "{lineno:5d}:{name:20s}{message}",
                "style": "{",
            },
            "brief": {
                "format": "{levelname:8s}: {message}",
                "style": "{",
            }
        },
        "handlers": {
            "console": {
                "class":"logging.StreamHandler",
                "level":"WARNING",
                "formatter": "brief",
                "stream": sys.stderr,
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "DEBUG",
                "filename": LOG_PATH,
                "formatter": "verbose",
                "maxBytes": 2000000,        # = 2MB
                "backupCount": 5,
            },
        },
        "loggers": {
            "ExceptionLogger": {
                "handlers": ["file"],
                "level": "ERROR",
                "propagate": False,
            },
        },
        "root": {
            "handlers": ["console", "file"],
            "level":"DEBUG",
        },
    }
    return confdict


activate_logging()

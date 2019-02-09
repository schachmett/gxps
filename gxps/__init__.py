"""Loads the configuration ini and sets app name and version."""
# pylint: disable=invalid-name
# pylint: disable=logging-format-interpolation

import os
from pathlib import Path
import configparser
import datetime
import sys
import logging
import logging.config
import traceback
from collections import OrderedDict

from gi.repository import GLib


__appname__ = "GXPS"
__version__ = "alpha"
__authors__ = ["Simon Fischer <sfischer@ifp.uni-bremen.de>"]
__website__ = "https://github.com/schachmett/gxps"

BASEDIR = Path(os.path.realpath(__file__)).parents[1]
assert Path(BASEDIR).is_dir()
RSF_DB_PATH = BASEDIR / "gxps/assets/rsf.db"

CONFDIR = Path(GLib.get_user_config_dir()) / "gxps"
if not Path(CONFDIR).is_dir():
    os.makedirs(str(CONFDIR))
CFG_PATH = CONFDIR / "config.ini"
COLOR_CFG_PATH = CONFDIR / "colors.ini"
LOG_PATH = CONFDIR / "gxps.log"

__config__ = configparser.ConfigParser()
__colors__ = configparser.ConfigParser()


def on_import():
    """Gets called when gxps is imported."""
    make_logger(LOG_PATH)
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
    load_config(__config__, CFG_PATH)
    load_colors(__colors__, COLOR_CFG_PATH)


def load_config(config, path):
    """Loads the config from file or creates a new one if that file is
    missing."""
    if not path.is_file():
        config.add_section("window")
        config.set("window", "xsize", "1200")
        config.set("window", "ysize", "700")
        config.set("window", "xpos", "200")
        config.set("window", "ypos", "200")
        config.add_section("io")
        config.set("io", "xydir", str(CONFDIR / "xy_temp/"))
        config.set("io", "project_file", "None")
        config.set("io", "project_dir", os.environ["HOME"])
        config.set("io", "data_dir", os.environ["HOME"])
        config.set("io", "export_dir", os.environ["HOME"])
        with open(str(path), "w") as cfg_file:
            config.write(cfg_file)
    else:
        config.read(str(path))


def load_colors(colorconfig, path):
    """Loads the color config from file or creates a new one if that file is
    missing."""
    if not path.is_file():
        colorconfig.add_section("treeview")
        colorconfig.set("treeview", "tv-highlight-bg", "#F08763")
        colorconfig.add_section("plotting")
        colorconfig.set("plotting", "axisticks", "#AAAAAA")
        colorconfig.set("plotting", "spectra",
                        "#C3D2A1, #B5C689, #909F6E, #6C7752, #484F37")
        colorconfig.set("plotting", "region-vlines", "#A93F00")
        colorconfig.set("plotting", "region-vlines-active", "#F58B4C")
        colorconfig.set("plotting", "region-background", "#A93F00")
        colorconfig.set("plotting", "region-background-active", "#F58B4C")
        colorconfig.set("plotting", "peak", "#66668C")
        colorconfig.set("plotting", "peak-active", "#b2b2d8")
        colorconfig.set("plotting", "peak-sum", "#CCCCF2")
        colorconfig.set("plotting", "peak-sum-active", "#E5E5FF")
        colorconfig.set("plotting", "peak-wedge-edge", "#FA8072")
        colorconfig.set("plotting", "peak-wedge-face", "#FA8072")
        colorconfig.set("plotting", "rsf-annotation", "#AAAAAA")
        colorconfig.set("plotting", "rsf-vlines",
                        "#468CDE, #52D273, #E94F64, #E57254, #E8C454")
        with open(str(path), "w") as c_cfg_file:
            colorconfig.write(c_cfg_file)
    else:
        colorconfig.read(str(path))


def make_logger(path):
    """Configures the root logger for this application."""
    logger_conf = {
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
                "filename": str(path),
                "formatter": "verbose",
                "maxBytes": 2000000,
                "backupCount": 3,
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
    logging.config.dictConfig(logger_conf)
    logging.getLogger(__name__)
    logging.getLogger("matplotlib").setLevel(logging.WARNING)


def introspect(gobject):
    """Print all Property values of a GObject.GObject."""
    for param in gobject.list_properties():
        try:
            print("{}: {}".format(
                param.name, gobject.get_property(param.name)))
        except TypeError:
            print("{} not readable".format(param.name))


on_import()

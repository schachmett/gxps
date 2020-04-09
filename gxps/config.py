"""Provides access to configparser instances and logging parameters."""
# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation

import sys
import configparser
import logging
import logging.config
import traceback

from bidict import OrderedBidict

from gxps.xdg import (
    DATA_DIR, CONF_DIR, CONF_DIRS, LOG_FILE,
    _make_missing_dirs
    )


CONFIG = configparser.ConfigParser()
def load_cfg():
    default = str(DATA_DIR / "config/config.ini")
    conf_locations = [str(DIR / "config.ini") for DIR in CONF_DIRS[::-1]]
    if CONF_DIR not in CONF_DIRS:
        conf_locations.append(str(CONF_DIR / "config.ini"))
    CONFIG.read([default, *conf_locations])
def save_cfg():
    with open(str(CONF_DIR / "config.ini"), "w") as cfg_file:
        CONFIG.write(cfg_file)
CONFIG.load = load_cfg
CONFIG.save = save_cfg

COLORS = configparser.ConfigParser()
def load_colors():
    default = str(DATA_DIR / "config/colors.ini")
    conf_locations = [str(DIR / "colors.ini") for DIR in CONF_DIRS[::-1]]
    if CONF_DIR not in CONF_DIRS:
        conf_locations.append(str(CONF_DIR / "colors.ini"))
    COLORS.read([default, *conf_locations])
def save_colors():
    with open(str(CONF_DIR / "colors.ini"), "w") as color_file:
        COLORS.write(color_file)
COLORS.load = load_colors
COLORS.save = save_colors

LOG_CFG = {}

TITLES = {
    "spectrum_view": OrderedBidict({
        "name": "Name",
        "notes": "Notes"
    }),
    "peak_view": OrderedBidict({
        "label": "Label",
        "name": "     ",
        "shape": "Shape",
        "position": "Position",
        "area": "Area*",
        "fwhm": "FWHM*",
        "alpha": "Par1",
        "beta": "Par2",
        "gamma": "Par3"
    }),
    "static_specinfo": OrderedBidict({
        "filename": "Filename"
    }),
    "editing_dialog": OrderedBidict({
        "name": "Name",
        "notes": "Notes",
        "pass_energy": "Pass Energy",
        "integration_time": "Time per Data Point",
        "sweeps": "Sweeps"
    }),
    "norm_types": OrderedBidict({
        "none": "none",
        "manual": "Manual",
        "high_energy": "High energy background",
        "low_energy": "Low energy background",
        "highest": "Highest peak"
    }),
    "norm_type_ids": OrderedBidict({
        "none": "0",
        "highest": "1",
        "high_energy": "2",
        "low_energy": "3",
        "manual": "4"
    }),
    "background_types": OrderedBidict({
        "none": "none",
        "shirley": "Shirley",
        "linear": "Linear"
    }),
    "background_type_ids": OrderedBidict({
        "none": "0",
        "shirley": "1",
        "linear": "2"
    }),
    "photon_source_ids": OrderedBidict({
        "Al": "0",
        "Mg": "1"
    }),
    "peak_shapes": OrderedBidict({
        "PseudoVoigt": "PseudoVoigt",
        "Voigt": "Voigt",
        "DoniachSunjic": "DoniachSunjic"
    }),
    "peak_shape_ids": OrderedBidict({
        "PseudoVoigt": "0",
        "Voigt": "1",
        "DoniachSunjic": "2"
    })
}

def load_configs():
    _make_missing_dirs()
    CONFIG.load()
    COLORS.load()

def activate_logging():
    _make_missing_dirs()
    LOG_CFG.update(_logger_conf())
    logging.config.dictConfig(LOG_CFG)
    logging.getLogger(__name__)
    logging.getLogger("matplotlib").setLevel(logging.WARNING)
    ex_logger = logging.getLogger("ExceptionLogger")
    def exception_handler(type_, value, tback):
        tbstring = traceback.format_tb(tback)
        tbstring = [line.replace("\n", "") for line in tbstring]
        tbstring = (" " * 10).join(tbstring)
        ex_logger.error(
            "Uncaught {}: {}, traceback: '{}'"
            "".format(type_.__name__, value, tbstring)
        )
        sys.__excepthook__(type_, value, tback)
    sys.excepthook = exception_handler
    file_handler = logging.getLogger("").handlers[1]
    file_handler.doRollover()


def _logger_conf():
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
                "filename": LOG_FILE,
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

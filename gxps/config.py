"""Provides access to configparser instances and logging parameters."""
# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation

import sys
import configparser
import logging
import logging.config
import traceback

from gxps.xdg import DATA_DIR, CONF_DIR, LOG_FILE, _make_missing_dirs


CONFIG = configparser.ConfigParser()
def load_cfg():
    # TODO look also in CONF_DIRS and copy to "canonical" location
    default = str(DATA_DIR / "config/config.ini")
    user = str(CONF_DIR / "config.ini")
    CONFIG.read([default, user])
def save_cfg():
    with open(str(CONF_DIR / "config.ini"), "w") as cfg_file:
        CONFIG.write(cfg_file)
CONFIG.load = load_cfg
CONFIG.save = save_cfg

COLORS = configparser.ConfigParser()
def load_colors():
    default = str(DATA_DIR / "config/colors.ini")
    user = str(CONF_DIR / "colors.ini")
    COLORS.read([default, user])
def save_colors():
    with open(str(CONF_DIR / "colors.ini"), "w") as color_file:
        COLORS.write(color_file)
COLORS.load = load_colors
COLORS.save = save_colors

LOG_CFG = {}
# TODO use config file https://docs.python.org/2/library/logging.config.html
# def load_log_cfg():
#     LOG_CFG.update(_logger_conf())
# LOG_CFG.load = load_log_cfg
# LOG_CFG.save = lambda *_args: None

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

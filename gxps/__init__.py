"""Loads the configuration ini and sets app name and version."""
# pylint: disable=invalid-name
# pylint: disable=wrong-import-order
# pylint: disable=logging-format-interpolation

__appname__ = "GXPS"
__authors__ = ["Simon Fischer <sf@simon-fischer.info>"]
__website__ = "https://github.com/schachmett/gxps"

try:
    from pbr.version import VersionInfo
    __version__ = VersionInfo("gxps").version_string()
except ImportError:
    __version__ = "devel"

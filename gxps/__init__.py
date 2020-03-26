"""Loads the configuration ini and sets app name and version."""
# pylint: disable=invalid-name
# pylint: disable=wrong-import-order
# pylint: disable=logging-format-interpolation

__appname__ = "GXPS"
__authors__ = ["Simon Fischer <sf@simon-fischer.info>"]
__website__ = "https://github.com/schachmett/gxps"

# maybe use release_string() instead?
try:
    import sys
    if sys.platform == "win32":
        __version__ = "windows-version"
    else:
        from pbr.version import VersionInfo
        __version__ = VersionInfo("gxps").version_string()
except ImportError:
    __version__ = "devel"

"""Loads the configuration ini and sets app name and version."""
# pylint: disable=invalid-name
# pylint: disable=wrong-import-order
# pylint: disable=logging-format-interpolation

__appname__ = "GXPS"
__authors__ = ["Simon Fischer <sf@simon-fischer.info>"]
__website__ = "https://github.com/schachmett/gxps"

# maybe use release_string() instead?
__version__ = "unknown"
__release__ = "unknown"
try:
    import sys
    if sys.platform == "win32":
        __version__ = "windows-version"
        __release__ = "windows-version"
    else:
        from pbr.version import VersionInfo
        __version__ = VersionInfo("gxps").version_string()
        __release__ = VersionInfo("gxps").release_string()
except ImportError:
    __version__ = "devel"
    __release__ = "devel"

"""Loads the configuration ini and sets app name and version."""
# pylint: disable=invalid-name
# pylint: disable=wrong-import-order
# pylint: disable=logging-format-interpolation

__appname__ = "GXPS"
__authors__ = ["Simon Fischer <sf@simon-fischer.info>"]
__website__ = "https://github.com/schachmett/gxps"

# maybe use release_string() instead?
__version__ = "unknown version"
__release__ = "unknown release"
try:
    import sys
    if sys.platform == "win32":
        from gxps.xdg import DATA_DIR
        with open(DATA_DIR / "version.txt") as vfile:
            __version__ = vfile.readline().strip()
        with open(DATA_DIR / "release.txt") as rfile:
            __release__ = rfile.readline().strip()
    else:
        from pbr.version import VersionInfo
        __version__ = VersionInfo("gxps").version_string()
        __release__ = VersionInfo("gxps").release_string()
except ImportError:
    __version__ = "devel"
    __release__ = "devel"
except FileNotFoundError:
    __version__ = "missingversion"
    __release__ = "missingrelease"

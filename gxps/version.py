"""Version information and static info."""

__appname__ = "GXPS"
__authors__ = ["Simon Fischer <sf@simon-fischer.info>"]
__website__ = "https://github.com/schachmett/gxps"

try:
    from pbr.version import VersionInfo
    __version__ = VersionInfo("gxps").version_string()
except ImportError:
    __version__ = "devel"

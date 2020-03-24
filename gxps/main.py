"""Starts the program."""

import signal
import sys

try:
    from gi.repository import GLib
except ImportError:
    print("-" * 79)
    print("please do sudo apt install python-gi")
    print("-" * 79)
    raise

from gxps.gui import GXPS


def main():
    """Runs GXPS app from gxps.gxps module."""
    app = GXPS()
    if hasattr(GLib, "unix_signal_add"):
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, app.on_quit)
    exit_status = app.run(sys.argv)
    sys.exit(exit_status)


# if __name__ == "__main__":
#     main()

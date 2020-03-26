"""Starts the program."""


def main():
    """Runs GXPS app from gxps.gxps module."""
    # Test for some cli options immediately
    import sys
    if "--version" in sys.argv:
        __version__ = "unknown"
        try:
            if sys.platform == "win32":
                __version__ = "windows-version"
            else:
                from pbr.version import VersionInfo
                __version__ = VersionInfo("gxps").release_string()
        except ImportError:
            __version__ = "devel"
        print(__version__)
        sys.exit(0)


    # Set process name
    if sys.platform == 'linux':
        # pylint: disable=broad-except
        try:
            import ctypes
            libc = ctypes.CDLL('libc.so.6')
            libc.prctl(15, b'gxps', 0, 0, 0)  # 15 = PR_SET_NAME
        except Exception:
            pass
    try:
        from setproctitle import setproctitle
        setproctitle('gxps')
    except ImportError:
        pass

    # Set up config and logging
    from gxps.config import (
        activate_logging,
        load_configs
    )
    load_configs()
    activate_logging()

    # Test dependencies
    try:
        from gi.repository import GLib
    except ImportError:
        print("-" * 79)
        print("please do sudo apt install python-gi")
        print("-" * 79)
        raise

    # Build app object
    from gxps.gui import GXPS
    app = GXPS()

    # Run
    import signal
    if hasattr(GLib, "unix_signal_add"):
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, app.on_quit)
    exit_status = app.run(sys.argv)
    sys.exit(exit_status)


if __name__ == "__main__":
    main()

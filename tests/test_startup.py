"""Tests the modules __main__ and __init__ to verify correct application
startup."""
# pylint: disable=invalid-name
# pylint: disable=missing-docstring

import pytest

from gxps import __appname__, __version__
from gxps.__main__ import main

def test_main():
    with pytest.raises(SystemExit):
        main()

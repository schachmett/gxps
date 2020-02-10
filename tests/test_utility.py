"""Tests utility classes."""
# pylint: disable=invalid-name
# pylint: disable=missing-docstring

from gxps.utility import Borg#, Observable


def test_borg():
    b = Borg()
    b.testvar = "moin"
    b2 = Borg()
    assert b2.testvar == "moin"

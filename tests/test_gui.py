"""Tests the gui module."""
# pylint: disable=missing-docstring

# import pytest

from gxps import gui


def test_gui_state():
    state = gui.GUIState()
    state.active_peak = "p1"
    state2 = gui.GUIState()
    assert state2.active_peak == "p1"
    gui.GUIState.cleanup()

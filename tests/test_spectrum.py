"""Tests the Spectrum class."""
# pylint: disable=invalid-name
# pylint: disable=missing-docstring
# pylint: disable=redefined-outer-name

import pytest

from gxps.spectrum import Spectrum


# keep in mind: @pytest.mark.parametrize
# travis CI

@pytest.fixture
def simple_spectrum():
    """
    Very simple Spectrum, only required constructor arguments.
    """
    s = Spectrum(energy=[1, 2, 3], intensity=[0, 2, 5])
    return s

def test_spectrum_constructor():
    with pytest.raises(ValueError):
        Spectrum(hi="moin")

def test_spectrum(simple_spectrum):
    assert not hasattr(simple_spectrum, "greeting")

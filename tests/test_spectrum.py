"""Tests the Spectrum class."""
# pylint: disable=invalid-name
# pylint: disable=missing-docstring
# pylint: disable=redefined-outer-name

import pytest

from gxps.spectrum import Spectrum
from gxps import io


########## Fixtures

parsed_sdicts = [
    io.parse_spectrum_file("tests/fixtures/TiO2-110-f.txt"),
    io.parse_spectrum_file("tests/fixtures/Al-NE-FeCr-S02p6-Fe2p-3.xy"),
    io.parse_spectrum_file("tests/fixtures/contains_layer_zeros.txt"),
    io.parse_spectrum_file("tests/fixtures/21-04_015-XAS_100.xy"),
]

parsed_spectra = [Spectrum(**sdictlist[-1]) for sdictlist in parsed_sdicts]

@pytest.fixture
def tio2f():
    """TiO2-110-f dataset containing 22 individual spectra."""
    specdicts = io.parse_spectrum_file("tests/fixtures/TiO2-110-f.txt")
    return Spectrum(**specdicts[3])

@pytest.fixture
def simple_spectrum():
    return Spectrum(energy=[1, 2, 3], intensity=[4, 5, 6])


########## Test functions

def test_spectrum_constructor():
    with pytest.raises(ValueError):
        Spectrum()
    with pytest.raises(ValueError):
        Spectrum(energy=[1, 2, 3], intensity=[1, 2])
    with pytest.raises(ValueError):
        Spectrum(energy=[1, 2, 3], intensity=[1, 2, 3, 4])
    with pytest.raises(ValueError):
        Spectrum(energy=[[1, 2], [3, 4]], intensity=[[3, 3], [2, 2]])

@pytest.mark.parametrize("spectrum", parsed_spectra)
def test_spectrum_observability(spectrum):
    x = []
    def cb():
        x.append(True)
    spectrum.connect("changed-data", cb)
    spectrum.background_type = "linear"
    assert x

def test_spectrum_background_type(simple_spectrum):
    with pytest.raises(ValueError):
        simple_spectrum.background_type = "foo"
    with pytest.raises(AttributeError):
        simple_spectrum.energy = [10, 11, 12]
    with pytest.raises(AttributeError):
        simple_spectrum.intensity = [10, 11, 12]

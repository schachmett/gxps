"""Tests the Spectrum class."""
# pylint: disable=invalid-name
# pylint: disable=missing-docstring
# pylint: disable=redefined-outer-name
# pylint: disable=protected-access

import pytest
import numpy as np
import matplotlib.pyplot as plt

from gxps.spectrum import Spectrum
from gxps import io


########## Fixtures

parsed_sdicts = [
    io.parse_spectrum_file("tests/fixtures/TiO2-110-f.txt"),
    io.parse_spectrum_file("tests/fixtures/Al-NE-FeCr-S02p6-Fe2p-3.xy"),
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
    return Spectrum(
        energy=[1, 2, 3],
        intensity=[4, 5, 6],
        filename="fixture_nofile",
        name="fixture"
    )

parsed_spectra.append(Spectrum(
    energy=[1, 2, 3],
    intensity=[4, 5, 6],
    filename="fixture_nofile",
    name="fixture"
))


########## Test functions

def test_spectrum_constructor():
    with pytest.raises(ValueError):
        Spectrum()
    with pytest.raises(ValueError):
        Spectrum(
            energy=[1, 2, 3], intensity=[1, 2], name="n", filename="f"
        )
    with pytest.raises(ValueError):
        Spectrum(
            energy=[1, 2, 3], intensity=[1, 2, 3, 4], name="n", filename="f"
        )
    with pytest.raises(ValueError):
        Spectrum(
            energy=[[1, 2], [3, 4]],
            intensity=[[3, 3], [2, 2]],
            name="n",
            filename="f"
        )

@pytest.mark.parametrize("spectrum", parsed_spectra)
def test_spectrum_plot(spectrum):
    plt.clf()
    plt.plot(spectrum.energy, spectrum.intensity)
    suffix = (spectrum.meta.filename.split("/")[-1]).split(".")[0]
    plt.savefig("tests/plot_verification/s_{}.png".format(suffix))

def test_spectrum_observability(tio2f):
    x_data, x_meta = [], []
    def cb_data(*_args):
        x_data.append(True)
    tio2f.connect("changed-data", cb_data)
    tio2f.background_type = "linear"
    assert x_data
    x_data.clear()
    tio2f.energy_calibration = 1.5
    assert x_data
    def cb_meta(*_args):
        x_meta.append(True)
    tio2f.connect("changed-metadata", cb_meta)
    tio2f.meta.filename = "test"
    assert x_meta

def test_spectrum_background_setters(simple_spectrum):
    with pytest.raises(ValueError):
        simple_spectrum.background_type = "foo"
    with pytest.raises(AttributeError):
        simple_spectrum.energy = [10, 11, 12]
    with pytest.raises(AttributeError):
        simple_spectrum.intensity = [10, 11, 12]
    with pytest.raises(ValueError):
        simple_spectrum.background_bounds = [1.1, 1.4, 1.9]
    with pytest.raises(ValueError):
        simple_spectrum.background_bounds = [1.1, 1.3, 1.5, 3.8]
    simple_spectrum.background_type = "linear"
    simple_spectrum.background_bounds = [1.1, 1.3, 1.8, 2.1]
    for bg_type in simple_spectrum._bg_types:
        if bg_type == "tougaard":
            with pytest.raises(NotImplementedError):
                simple_spectrum.background_type = bg_type
        else:
            simple_spectrum.background_type = bg_type

def test_spectrum_energy_calibration(tio2f):
    with pytest.raises(TypeError):
        tio2f.energy_calibration = "one"
    with pytest.raises(ValueError):
        tio2f.energy_calibration = -np.inf
    assert tio2f.energy_calibration == 0.0
    tio2f.background_bounds = [390, 411]
    tio2f.background_type = "shirley"
    e = tio2f.energy.copy()
    i = tio2f.intensity.copy()
    b = tio2f.background.copy()
    bb = tio2f.background_bounds.copy()
    tio2f.energy_calibration = 4.3
    assert np.allclose(tio2f.energy, e + 4.3)
    assert np.allclose(tio2f.intensity, i)
    assert np.allclose(tio2f.background, b)
    assert np.allclose(tio2f.background_bounds, bb + 4.3)

def test_spectrum_normalization(tio2f):
    with pytest.raises(TypeError):
        tio2f.normalization_divisor = [1, 4]
    with pytest.raises(ValueError):
        tio2f.normalization_divisor = 0.0
    with pytest.raises(ValueError):
        tio2f.normalization_type = 5.3
    with pytest.raises(ValueError):
        tio2f.normalization_type = "foo"
    assert tio2f.normalization_type == "none"
    assert tio2f.normalization_divisor == 1.0
    tio2f.background_bounds = [390, 410]
    tio2f.background_type = "shirley"
    e = tio2f.energy.copy()
    i = tio2f.intensity.copy()
    b = tio2f.background.copy()
    tio2f.normalization_divisor = 3.4
    assert tio2f.normalization_type == "manual"
    assert np.allclose(tio2f.energy, e)
    assert np.allclose(tio2f.intensity * 3.4, i)
    assert np.allclose(tio2f.background * 3.4, b)
    tio2f.normalization_divisor = 1.9
    assert np.allclose(tio2f.intensity * 1.9, i)
    assert np.allclose(tio2f.background * 1.9, b)
    tio2f.normalization_type = "none"
    assert tio2f.normalization_divisor == 1.0
    assert np.allclose(tio2f.intensity, i)

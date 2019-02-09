"""Tests the spectrum module."""
# pylint: disable=invalid-name
# pylint: disable=missing-docstring
# pylint: disable=redefined-outer-name
# pylint: disable=protected-access

import pytest
import numpy as np
import matplotlib.pyplot as plt

from gxps.spectrum import Spectrum, SpectrumContainer
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
    return Spectrum(**specdicts[7])

@pytest.fixture
def simple_spectrum():
    return Spectrum(
        energy=[1, 2, 3],
        intensity=[4, 5, 6],
        filename="fixture_nofile",
        name="fixture",
        key="T 2"
    )

parsed_spectra.append(Spectrum(
    energy=[1, 2, 3],
    intensity=[4, 5, 6],
    filename="fixture_nofile",
    name="fixture",
    key="T 1"
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
    plt.plot(spectrum.energy, spectrum.intensity)
    suffix = (spectrum.meta.filename.split("/")[-1]).split(".")[0]
    plt.savefig("tests/plot_verification/s_{}.png".format(suffix))
    plt.clf()

def test_spectrum_container():
    class ObservingException(Exception):
        pass
    def cb_exception(*_args):
        raise ObservingException

    specdicts = io.parse_spectrum_file("tests/fixtures/TiO2-110-f.txt")
    spectra = SpectrumContainer()
    for specdict in specdicts:
        spectra.add_spectrum(**specdict)
    assert len(specdicts) == len(spectra)
    spectra.connect("changed-spectrum", cb_exception)
    spectra.connect("changed-peak", cb_exception)
    with pytest.raises(ObservingException):
        spectra.spectra[0].normalization_divisor = 3.1
    with pytest.raises(ObservingException):
        spectrum = spectra.spectra[1]
        peak = spectrum.model.add_peak("p1", area=50, fwhm=0.3, position=3)
        peak.set_constraint("fwhm", max=4.2)
    spectra2 = SpectrumContainer()
    assert len(spectra2) == len(specdicts)
    SpectrumContainer.cleanup()

def test_spectrum_observability(tio2f):
    class ObservingException(Exception):
        pass
    def cb_exception(*_args):
        raise ObservingException

    tio2f.connect("changed-spectrum", cb_exception)
    with pytest.raises(ObservingException):
        tio2f.normalization_divisor = 2.3
    tio2f.connect("changed-metadata", cb_exception)
    with pytest.raises(ObservingException):
        tio2f.meta.filename = "test"
    tio2f.model.add_peak("p2", area=200, fwhm=3, position=500)
    tio2f.connect("changed-fit", cb_exception)
    with pytest.raises(ObservingException):
        tio2f.model.add_peak("p1", area=300, fwhm=2, position=340)
    tio2f.connect("changed-peak", cb_exception)
    with pytest.raises(ObservingException):
        tio2f.model["p2"].set_constraint("fwhm", min=4)

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
    tio2f.background_bounds = [510, 535]
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
    tio2f.background_bounds = [510, 535]
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

def test_peak_addition(tio2f):
    with pytest.raises(ValueError):
        tio2f.model.add_peak(name="p1", fwhm=2.0, area=600)
    with pytest.raises(TypeError):
        tio2f.model.add_peak(name="p1", fwhm=3.1, area=400, position="3br0")
    assert not tio2f.model
    tio2f.model.add_peak(name="p2", fwhm=2.4, area=300, position=515.3)
    with pytest.raises(ValueError):
        tio2f.model.add_peak(name="p2", fwhm=1.0, area=400, position=530)
    assert len(tio2f.model) == 1
    assert tio2f.model["p2"] in tio2f.model.peaks
    tio2f.model.remove_peak(name="p2")
    assert not tio2f.model

def test_peak_manipulation(tio2f):
    tio2f.model.add_peak(name="p1", fwhm=4.3, area=3500, position=530)
    tio2f.model.add_peak(name="p2", fwhm=4.3, area=3500, position=330)
    tio2f.model.add_peak(name="p2axl", fwhm=1.3, area=3500, position=515)
    p1 = tio2f.model["p1"]
    p2 = tio2f.model["p2"]
    assert p1.fwhm == 4.3
    p1.area = 4300
    assert p1.area == 4300
    p1.alpha = 0.6
    assert p1.alpha == 0.6
    plt.plot(tio2f.energy, tio2f.intensity)
    plt.plot(tio2f.energy, p1.get_intensity(tio2f.energy))
    plt.plot(tio2f.energy, tio2f.model["p2"].get_intensity(tio2f.energy))
    plt.plot(tio2f.energy, tio2f.model["p2axl"].get_intensity(tio2f.energy))
    plt.savefig("tests/plot_verification/p_1.png")
    plt.clf()
    with pytest.raises(ValueError):
        p1.set_constraint("fwhm", expr="bla")
    with pytest.raises(ValueError):
        p1.set_constraint("fwhm", expr="p1 =")
    p1.set_constraint("fwhm", max=3.0)
    assert tio2f.model.params["p1_fwhm"].max == 3.0
    assert p1.fwhm == 3.0
    p2.set_constraint("fwhm", min=0.1)
    assert p2.get_constraint("fwhm", "min") == 0.1
    tio2f.model["p2"].fwhm = 4.5
    p1.set_constraint("fwhm", expr="p2 * 3")
    assert p1.fwhm == 13.5
    p1.set_constraint("fwhm", expr="")
    assert p1.get_constraint("fwhm", "vary") is True
    p1.set_constraint("fwhm", expr="p2axl*2")
    assert p1.get_constraint("fwhm", "expr") == "p2axl*2"
    assert p1.get_constraint("fwhm", "vary") is False
    with pytest.raises(ValueError):
        p1.set_constraint("fwhm", expr="p1 * 4")

def test_peak_destruction(tio2f):
    tio2f.model.add_peak(name="p1", fwhm=4.3, area=3500, position=530)
    tio2f.model.add_peak(name="p2", fwhm=4.3, area=3500, position=330)
    tio2f.model.add_peak(name="p2axl", fwhm=1.3, area=3500, position=515)
    assert "p1_fwhm" in tio2f.model.params
    tio2f.model.remove_peak("p1")
    assert "p1_fwhm" not in tio2f.model.params

def test_fitting(tio2f):
    p1 = tio2f.model.add_peak(name="p1", fwhm=2.5, area=5000, position=530)
    p2 = tio2f.model.add_peak(name="p2", fwhm=3, area=3500, position=515)
    p3 = tio2f.model.add_peak(name="p3", fwhm=3, area=1000, position=522)
    tio2f.background_bounds = (509, 535)
    tio2f.background_type = "shirley"
    def plot():
        toplot = (
            tio2f.intensity,
            tio2f.background,
            p1.get_intensity(tio2f.energy) + tio2f.background,
            p2.get_intensity(tio2f.energy) + tio2f.background,
            p3.get_intensity(tio2f.energy) + tio2f.background,
            tio2f.model.get_intensity(tio2f.energy) + tio2f.background
        )
        for i in toplot:
            plt.plot(tio2f.energy, i)
    plot()
    plt.savefig("tests/plot_verification/p_prefit.png")
    plt.clf()
    tio2f.model.fit(tio2f.energy, tio2f.intensity - tio2f.background)
    plot()
    plt.savefig("tests/plot_verification/p_postfit.png")
    plt.clf()
    p1.alpha = 1.5
    tio2f.model.fit(tio2f.energy, tio2f.intensity - tio2f.background)
    assert p1.alpha == 1.0

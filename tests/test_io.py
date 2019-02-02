"""Tests the IO functions."""
# pylint: disable=invalid-name
# pylint: disable=missing-docstring
# pylint: disable=redefined-outer-name

import pytest

from gxps import io

@pytest.mark.parametrize("fname", [
    "tests/fixtures/TiO2-110-f.txt",
    "tests/fixtures/Al-NE-FeCr-S02p6-Fe2p-3.xy",
    "tests/fixtures/contains_layer_zeros.txt",
    "tests/fixtures/21-04_015-XAS_100.xy"
])
def test_parse_spectrum_file(fname):
    specdicts = io.parse_spectrum_file(fname)
    assert specdicts
    for specdict in specdicts:
        assert specdict.keys() == specdicts[0].keys()
        assert "intensity" in specdict
        assert "energy" in specdict

def test_parse_invalid_spectrum_file():
    with pytest.raises(FileNotFoundError):
        io.parse_spectrum_file("tests/fixtures/nonexistent.txt")
    with pytest.raises(ValueError):
        io.parse_spectrum_file("tests/fixtures/faulty.xy")
    with pytest.raises(ValueError):
        io.parse_spectrum_file("tests/fixtures/ag-fitted.xpl")

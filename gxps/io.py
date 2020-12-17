"""Manages database file and has import filters."""
# pylint: disable=logging-format-interpolation
# pylint: disable=global-statement

import re
import logging
import pickle
import sqlite3

import numpy as np

from gxps import __version__
from gxps.xdg import DATA_DIR


LOG = logging.getLogger(__name__)


def load_project(fname):
    """Loads project file."""
    with open(fname, "rb") as pfile:
        state = pickle.load(pfile)
    state = convert_older_version(state)
    return state

def convert_older_version(state):
    """If the project file has an older version, this should convert it.
    """
    if state[2] != __version__:
        LOG.warning(f"Project file has different version: '{state[2]}'")
    state.remove(state[2])
    return state

def save_project(fname, spectrum_container, gui_state):
    """Saves a StatefulSpectrumContainer as a file."""
    active_spectrum_idxs = []
    for spectrum in gui_state.active_spectra:
        s_idx = spectrum_container.spectra.index(spectrum)
        active_spectrum_idxs.append(s_idx)
    container = spectrum_container.deepcopy()
    spectra = container.spectra
    state = [
        spectra,
        active_spectrum_idxs,
        __version__
    ]
    with open(fname, "wb") as pfile:
        pickle.dump(state, pfile, pickle.HIGHEST_PROTOCOL)


def parse_spectrum_file(fname):
    """Checks file extension and calls appropriate parsing method."""
    specdicts = []
    with open(fname, "r") as sfile:
        firstline = sfile.readline()
    if fname.split(".")[-1] == "txt":
        if "Region" in firstline:
            for specdict in parse_eistxt(fname):
                specdicts.append(specdict)
        if "[Info]" in firstline:
            specdicts.append(parse_arpestxt(fname))
        elif re.fullmatch(r"\d+\.?\d*,\d+\.?\d*\n", firstline):
            specdicts.append(parse_simple_xy(fname, delimiter=","))
        elif re.fullmatch(r"\d+\.?\d*\s\d+\.?\d*\n", firstline):
            specdicts.append(parse_simple_xy(fname))
    elif fname.split(".")[-1] == "xy":
        if re.fullmatch(r"\d+\.?\d*,\d+\.?\d*\n", firstline):
            delimiter = ","
        else:
            delimiter = None
        specdicts.append(parse_simple_xy(fname, delimiter=delimiter))
    if not specdicts:
        raise ValueError("Could not parse file '{}'".format(fname))
    return specdicts

def parse_simple_xy(fname, delimiter=None):
    """
    Parses the most simple x, y file with no header.
    """
    energy, intensity = np.genfromtxt(
        fname,
        delimiter=delimiter,
        unpack=True
    )
    specdict = {
        "filename": fname,
        "energy": energy,
        "intensity": intensity,
        "energy_scale": "binding",
        "name": "S XY",
        "notes": "file {}".format(fname.split("/")[-1])
    }
    return specdict

def parse_eistxt(fname):
    """Splits Omicron EIS txt file."""
    splitregex = re.compile(r"^Region.*")
    skip_once_regex = re.compile(r"Layer.*")
    skip_regex = re.compile(r"^[0-9]+\s*False.*")
    split_eislines = []
    with open(fname, "br") as eisfile:
        for line in eisfile:
            line = line.decode("utf-8", "backslashreplace")
            if re.match(splitregex, line):
                split_eislines.append([])
                do_skip = False
            elif re.match(skip_regex, line):
                do_skip = True
            elif re.match(skip_once_regex, line):
                continue
            if not do_skip:
                split_eislines[-1].append(line)

    for data in split_eislines:
        energy, intensity = np.genfromtxt(
            data,
            skip_header=4,
            unpack=True
        )
        header = [line.split("\t") for line in data[:4]]
        specdict = {
            "filename": fname,
            "energy": energy,
            "intensity": intensity,
            "energy_scale": "binding",
            "eis_region": int(header[1][0]),
            "name": "S {}".format(header[1][0]),
            "sweeps": int(header[1][6]),
            "dwelltime": float(header[1][7]),
            "pass_energy": float(header[1][9]),
            "notes": header[1][12],
        }
        yield specdict


def parse_arpestxt(fname):
    """Reads a txt file obtained from Elettra's VUV beamline."""
    properties = {}
    energy = []
    intensity = []
    is_data = False
    databegin_regex = re.compile(r"^\[Data [0-9]+\]")
    datarow_regex = re.compile(
        r"^\s[0-9]+\.?[0-9]*(E\+)?[0-9]*\s*[0-9]+\.?[0-9]*(E\+)?[0-9]*\s*$"
    )
    with open(fname, "r") as afile:
        for line in afile:
            if "=" in line:
                key, value = line.split("=")[:2]
                properties[key.strip()] = value.strip()
            if re.match(databegin_regex, line):
                is_data = True
                continue
            if not is_data:
                continue
            if not re.match(datarow_regex, line):
                is_data = False
                continue
            estring, istring = line.strip().split()
            energy.append(float(estring))
            intensity.append(float(istring))
    specdict = {
        "filename": fname,
        "energy": energy,
        "intensity": intensity,
        "energy_scale": properties["Energy Scale"].lower(),
        "name": properties["Spectrum Name"],
        "sweeps": int(properties["Number of Sweeps"]),
        "dwelltime": 0.001 * float(properties["Step Time"]),
        "pass_energy": float(properties["Pass Energy"]),
        "notes": properties["Comments"],
        "time": f"{properties['Date']}, {properties['Time']}",
    }
    return specdict


def get_element_rsfs(element, source):
    """Return dictionary containing rsfs for a specific element / source.
    """
    source_photons = {
        "Al": 1486.3,
        "Mg": 1253.4
    }
    photon_energy = source_photons.get(source, None)
    if photon_energy is None:
        photon_energy = float(source)
    dbfname = str(DATA_DIR / "assets/rsf.db")
    with sqlite3.connect(dbfname) as database:
        cursor = database.cursor()
        sql = """
            SELECT IsAuger, Orbital, BE, RSF
            FROM Peak
            WHERE Element=? AND (Source=? OR Source="Any")
        """
        cursor.execute(sql, (element.title(), source))
        rsf_data = cursor.fetchall()
        rsf_dicts = []
        for isauger, orbital, energy, rsf in rsf_data:
            if isauger == 1.0:
                binding_energy = photon_energy - energy
                orbital = orbital.upper()
            else:
                binding_energy = energy
            rsf_dicts.append({
                "Element": element.title(),
                "Orbital": orbital,
                "BE": binding_energy,
                "RSF": rsf
            })
    return rsf_dicts


def export_txt(fname, spectrum):
    """Export given spectra and everything that belongs to it as txt."""
    column_stack = [
        spectrum.energy,
        spectrum.intensity,
    ]
    name = re.sub(r"\s+", "_", spectrum.name)
    header = "{:_<15}_Energy\t{:_<14}_intensity\t".format(name, name)
    if spectrum.background.any():
        column_stack.append(spectrum.background)
        header += "{:_<13}_background\t".format(name)
    if spectrum.fit.any():
        column_stack.append(spectrum.fit)
        header += "{:_<20}_fit\t".format(name)
    for peak in spectrum.peaks:
        column_stack.append(peak.intensity)
        peak_name = re.sub(r"\s+", "_", peak.name)
        header += "{:_<12}_{:_<3}_peakint\t".format(name, peak_name)
    data = np.column_stack(column_stack)
    np.savetxt(fname, data, delimiter="\t", header=header)


def export_params(fname, spectrum):
    """Export given spectra and everything that belongs to it as txt."""
    params = ("area", "fwhm", "position", "alpha", "beta", "gamma")
    header = "\t".join(params)
    data = []
    for peak in spectrum.peaks:
        row = []
        row.append(peak.label)
        row.append(peak.shape)
        for par in params:
            value = peak.get_constraints(par)["value"]
            row.append(value)
        data.append(row)
    np.savetxt(fname, data, delimiter="\t", header=header, fmt="%s")

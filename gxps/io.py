"""Manages database file and has import filters."""
# pylint: disable=logging-format-interpolation
# pylint: disable=global-statement

import re
import logging
import pickle
import sqlite3
import copy

import numpy as np

from gxps import ASSETDIR, __version__


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
        raise NotImplementedError
    state.remove(state[2])
    return state

def save_project(fname, spectrum_container, gui_state):
    """Saves a StatefulSpectrumContainer as a file."""
    spectra = copy.copy(spectrum_container.spectra)
    active_spectrum_idxs = []
    for spectrum in gui_state.active_spectra:
        s_idx = spectrum_container.spectra.index(spectrum)
        active_spectrum_idxs.append(s_idx)
    for spectrum in spectra:
        spectrum.unregister_all_queues()
        for peak in spectrum.peaks:
            peak.unregister_all_queues()
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
        elif re.fullmatch(r"\d+\.\d+,\d+\n", firstline):
            specdicts.append(parse_simple_xy(fname, delimiter=","))
    elif fname.split(".")[-1] == "xy":
        if re.fullmatch(r"\d+\.\d+,\d+\n", firstline):
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
            "eis_region": int(header[1][0]),
            "name": "S {}".format(header[1][0]),
            "sweeps": int(header[1][6]),
            "dwelltime": float(header[1][7]),
            "pass_energy": float(header[1][9]),
            "notes": header[1][12],
        }
        yield specdict


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
    dbfname = str(ASSETDIR / "rsf.db")
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



# def export_txt(dh, spectrumID, fname):
#     """Export given spectra and everything that belongs to it as txt."""
#     # pylint: disable=too-many-locals
#     energy = dh.get(spectrumID, "energy")
#     cps = dh.get(spectrumID, "cps")
#     background = copy.deepcopy(cps)
#     allfit = np.array([0.0] * len(energy))
#     peaknames = []
#     peaks = []
#     for regionID in dh.children(spectrumID):
#         emin = np.searchsorted(energy, dh.get(regionID, "emin"))
#         emax = np.searchsorted(energy, dh.get(regionID, "emax"))
#         single_bg = dh.get(regionID, "background")
#         background[emin:emax] -= cps[emin:emax] - single_bg
#         allfit[emin:emax] += dh.get(regionID, "fit_cps")
#         for peakID in dh.children(regionID):
#             peakname = dh.get(peakID, "name")
#             peaknames.append("Peak {:19}"
#                 "".format(peakname.replace("Peak", "")))
#             peaks.append(dh.get(peakID, "fit_cps_fullrange"))
#     data = np.column_stack(
#         (energy, cps, background, allfit, *[peak for peak in peaks])
#     )
#     header = """
#         {:22}\t{:24}\t{:24}\t{:24}\t{}
#     """.format(
#         "Energy",
#         "CPS",
#         "Background",
#         "Fit",
#         "{}".format("\t".join(peaknames))
#     ).strip()
#     np.savetxt(fname, data, delimiter="\t", header=header)

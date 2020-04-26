"""
Has a state class storing all information on GUI state, and has
GTK classes representing data from a SpectrumContainer and the GUI state.
"""
# pylint: disable=wrong-import-position
# pylint: disable=logging-format-interpolation

import logging
import string

from gxps.config import CONFIG, TITLES
from gxps.utility import Observable


LOG = logging.getLogger(__name__)


class State(Observable):
    """Holds information on the GUI state.
    """
    # pylint: disable=too-many-instance-attributes
    _signals = (
        "changed-plotting-options",
        "changed-project",
        "changed-tv",
        "changed-rsf",
        "changed-active",
        "changed-editing-spectra"
    )
    peak_name_list = [
        *list(string.ascii_uppercase),
        *[i+b for i in string.ascii_uppercase for b in string.ascii_uppercase]
    ]
    titles = TITLES

    def __init__(self, app, spectra):
        self._app = app
        self._spectra = spectra
        # Most of the states are properties: the direct values are non-public
        # Active data objects: Where all operations and visualization apply
        self._active_spectra = []
        self._editing_spectra = []
        self._active_peaks = []
        # Project file-related
        self._current_project = ""
        self._project_isaltered = False
        # Spectrum Treeview-related
        self._spectra_tv_columns = [
            self.titles["spectrum_view"].inverse[title.strip()]
            for title in CONFIG["View"]["spectrum-table"].split(",")
        ]
        self._spectra_tv_filter = ["notes", None]
        # Peak Trewwvie-related
        self._peak_tv_columns = ["name"]
        self._peak_tv_columns.extend([
            self.titles["peak_view"].inverse[title.strip()]
            for title in CONFIG["View"]["peak-table"].split(",")
        ])
        # Plotting-related
        self._rsf_elements = [""]
        self._photon_source = "Al"
        # Option dicts
        self._plotting_options = {
            "show-spectra": True,
            "show-background-definition": True,
            "show-background": True,
            "subtract-background": False,
            "show-peaks": True,
            "show-rsfs": True
        }
        # Keep the active spectra up to date
        self._app.bus.subscribe(
            self.update_active, "changed-spectra", priority=9)
        self._app.bus.subscribe(
            self.update_active, "changed-fit", priority=0)
        signals = (
            "changed-spectra",
            "changed-spectrum",
            "changed-spectrum-meta",
            "changed-fit",
            "changed-peak",
            "changed-peak-meta"
        )
        for signal in signals:
            self._app.bus.subscribe(self.alter_project, signal, priority=10)

        super().__init__()

    @property
    def active_spectra(self):
        """Currently active spectra.
        """
        return self._active_spectra.copy()

    @active_spectra.setter
    def active_spectra(self, spectra):
        """Activates given spectra.
        """
        if spectra == self._active_spectra:
            return
        for spectrum in spectra.copy():
            if spectrum not in self._spectra.spectra:
                raise ValueError("Invalid spectrum activated.")
        self._active_spectra.clear()
        self._active_spectra.extend(spectra)
        self.emit("changed-active", attr="spectra")
        # update active peaks:
        peaks = self._active_peaks.copy()
        for peak in self._active_peaks:
            for spectrum in self._active_spectra:
                if peak in spectrum.peaks:
                    break
            else:
                peaks.remove(peak)
        self.active_peaks = peaks

    @property
    def selected_spectra(self):
        """Returns spectra currently selected in the spectrum_view."""
        selection = self._app.builder.get_object("spectrum_selection")
        model, pathlist = selection.get_selected_rows()
        iters = [model.get_iter(path) for path in pathlist]
        spectra = [model.get(iter_, 0)[0] for iter_ in iters]
        return spectra

    @property
    def editing_spectra(self):
        """Returns list of spectra which are currently in editing."""
        return self._editing_spectra.copy()

    @editing_spectra.setter
    def editing_spectra(self, spectra):
        """Set new spectra to edit. Emits 'changed-editing-spectra'."""
        if spectra == self._editing_spectra:
            return
        for spectrum in spectra.copy():
            if spectrum not in self._spectra.spectra:
                raise ValueError("Invalid spectrum activated.")
        self._editing_spectra.clear()
        self._editing_spectra.extend(spectra)
        self.emit("changed-editing-spectra")

    @property
    def visible_peaks(self):
        """Currently visible peaks: the ones that belong to active spectra.
        """
        v_peaks = []
        for spectrum in self.active_spectra:
            v_peaks.extend(spectrum.peaks)
        return v_peaks

    @property
    def active_peaks(self):
        """Currently active peaks.
        """
        # for peak in self._active_peaks:
        #     for spectrum in self.active_spectra:
        #         if peak in spectrum.peaks:
        #             break
        #     else:
        #         self._active_peaks.remove(peak)
        return self._active_peaks.copy()

    @active_peaks.setter
    def active_peaks(self, peaks):
        """Activates given peaks.
        """
        if peaks == self._active_peaks:
            return
        for peak in peaks.copy():
            for spectrum in self.active_spectra:
                if peak in spectrum.peaks:
                    break
            else:
                raise ValueError("Invalid peak activated.")
        self._active_peaks.clear()
        self._active_peaks.extend(peaks)
        self.emit("changed-active", attr="peaks")

    @property
    def peak_names(self):
        """Already taken peak names."""
        peak_names = []
        for spectrum in self._spectra.spectra:
            for peak in spectrum.peaks:
                peak_names.append(peak.name)
        return peak_names

    @property
    def next_peak_name(self):
        """Returns the next peak name that is free."""
        peak_names = self.peak_names
        for name in self.peak_name_list:
            if name not in peak_names:
                return name
        return "N/A"

    @property
    def selected_peaks(self):
        """Currently selected peaks. Will be set to active peaks
        immediately by the ViewController.
        """
        selection = self._app.builder.get_object("peak_selection")
        model, pathlist = selection.get_selected_rows()
        iters = [model.get_iter(path) for path in pathlist]
        peaks = [model.get(iter_, 0)[0] for iter_ in iters]
        return peaks

    def update_active(self, *_args):
        """Clean out active spectra/peaks that do not exist anymore."""
        spectra = self._active_spectra.copy()
        for spectrum in self._active_spectra:
            if spectrum not in self._spectra.spectra:
                spectra.remove(spectrum)
        self.active_spectra = spectra
        peaks = self._active_peaks.copy()
        for peak in self._active_peaks:
            for spectrum in self._active_spectra:
                if peak in spectrum.peaks:
                    break
            else:
                peaks.remove(peak)
        self.active_peaks = peaks

    @property
    def current_project(self):
        """Filename of the currently opened project."""
        if self._current_project == "Untitled":
            return ""
        return self._current_project

    @current_project.setter
    def current_project(self, value):
        """Set the current project file name, also in the config."""
        self._project_isaltered = False
        if value == "Untitled" or not value:
            self._current_project = "Untitled"
            CONFIG["IO"]["current-project"] = ""
            self.emit("changed-project", attr="filename")
        elif value != self._current_project:
            self._current_project = value
            CONFIG["IO"]["current-project"] = value
            self.emit("changed-project", attr="filename")

    @property
    def project_isaltered(self):
        """Boolean if the project was altered since last save.
        """
        return self._project_isaltered

    @project_isaltered.setter
    def project_isaltered(self, isaltered):
        """Project was altered or saved."""
        if isaltered != self._project_isaltered:
            self._project_isaltered = isaltered
            self.emit("changed-project", attr="isaltered")

    def alter_project(self, _event):
        """Helper for setting project_isaltered."""
        self.project_isaltered = True

    @property
    def spectra_tv_columns(self):
        """Treeview columns for spectra view.
        """
        return self._spectra_tv_columns.copy()

    @property
    def spectra_tv_filter(self):
        """Treeview filter for spectra view.
        """
        return self._spectra_tv_filter.copy()

    @spectra_tv_filter.setter
    def spectra_tv_filter(self, value):
        """Set Spectrum Treeview Filter.
        """
        try:
            meta_attr_title, search_term = value
            meta_attr = self.titles["spectrum_view"].inverse[meta_attr_title]
            self._spectra_tv_filter[0] = meta_attr
            self._spectra_tv_filter[1] = search_term
            self.emit("changed-tv", attr="filter")
        except TypeError:
            LOG.error("Spectrum treeview filter '{}' invalid".format(value))

    @property
    def peak_tv_columns(self):
        """Treeview columns for peaks view.
        """
        return self._peak_tv_columns.copy()

    @property
    def rsf_elements(self):
        """Elements for which RSF values are plotted."""
        return self._rsf_elements.copy()

    @rsf_elements.setter
    def rsf_elements(self, elements):
        """Set Elements for which RSF values should be plotted."""
        self._rsf_elements.clear()
        self._rsf_elements.extend(elements)
        self.emit("changed-rsf", attr="elements")

    @property
    def photon_source(self):
        """Currently selected photon source."""
        return self._photon_source

    @property
    def photon_source_id(self):
        """ID of the active photon source."""
        return self.titles["photon_source_ids"][self._photon_source]

    @photon_source.setter
    def photon_source(self, source):
        """Set photon source."""
        self._photon_source = source
        self.emit("changed-rsf", attr="source")

    @property
    def plotting_options(self):
        """Option dictionary for how to plot the spectra and peaks."""
        return self._plotting_options.copy()

    def set_plotting_option(self, **options):
        """Sets plotting options via keyword arguments."""
        self._plotting_options.update(options)
        self.emit("changed-plotting-options")

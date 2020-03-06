"""Class holding all the actions that can be invoked by the user.
"""
# pylint: disable=wrong-import-position
# pylint: disable=logging-format-interpolation
# pylint: disable=too-few-public-methods

import logging
import os
import sys
import re

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk

from gxps import (
    CONFIG, COLORS, LOG_PATH, COLOR_CFG_PATH,
    __version__, __authors__, __website__, __appname__
    )
import gxps.io


LOG = logging.getLogger(__name__)


class Operator:
    """Meta class for objects that contain the main functions of the
    application as methods.
    """
    def __init__(self, get_widget, state, data):
        self.get_widget = get_widget
        self.state = state
        self.data = data


class Help(Operator):
    """Cares about extra windows etc."""
    @staticmethod
    def on_view_logfile(_action, *_args):
        """Views logfile in external text editor."""
        if sys.platform.startswith("linux"):
            os.system("xdg-open {}".format(str(LOG_PATH)))
        else:
            LOG.warning("logfile viewing only implemented for linux")

    @staticmethod
    def on_edit_colors(_action, *_args):
        """Views colors.ini file in external text editor."""
        if sys.platform.startswith("linux"):
            os.system("xdg-open {}".format(str(COLOR_CFG_PATH)))
        else:
            LOG.warning("color file editing only implemented for linux")

    def on_about(self, _widget, *_ignore):
        """Show 'About' dialog."""
        dialog = self.get_widget("about_dialog")
        dialog.run()
        dialog.hide()


class File(Operator):
    """Manages project files."""
    def startup(self, fname, *_args):
        """Opens a file or makes a new project if that file does not exist."""
        if fname:
            try:
                self.open(fname)
            except FileNotFoundError:
                LOG.warning("File '{}' not found".format(fname))
                self.new()
        else:
            self.new()

    def new(self):
        """Make new project."""
        self.data.clear()
        self.state.current_project = ""
        LOG.info("New project")

    def on_new(self, *_args):
        """User callback for making a new project."""
        if self.state.project_isaltered:
            self.ask_for_save()
        if self.state.project_isaltered:
            return
        self.new()

    def open(self, fname, merge=False):
        """Load project file."""
        spectra, active_idxs = gxps.io.load_project(fname)
        if not merge:
            self.data.clear()
        for spectrum in spectra:
            self.data.add_spectrum(spectrum)
        if not merge:
            self.state.active_spectra = [spectra[idx] for idx in active_idxs]
            self.state.current_project = fname
        LOG.info("Opened project file {}".format(fname))

    def on_open(self, *_args):
        """Let the user choose a project file to open and open it through
        self.open_project."""
        if self.state.project_isaltered:
            self.ask_for_save()
        if self.state.project_isaltered:
            return
        dialog = self.get_widget("open_project_dialog")
        project_dir = os.path.expandvars(CONFIG["IO"]["project-dir"])
        dialog.set_current_folder(project_dir)
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            fname = dialog.get_filename()
            CONFIG["IO"]["project-dir"] = dialog.get_current_folder()
            self.open(fname)
        dialog.hide()

    def on_merge(self, *_args):
        """Merges a project file into the current project."""
        dialog = self.get_widget("merge_project_dialog")
        project_dir = os.path.expandvars(CONFIG["IO"]["project-dir"])
        dialog.set_current_folder(project_dir)
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            fname = dialog.get_filename()
            CONFIG["IO"]["project-dir"] = dialog.get_current_folder()
            self.open(fname, merge=True)
        dialog.hide()

    def on_import(self, *_args):
        """Imports spectra from a data file."""
        dialog = self.get_widget("import_dialog")
        data_dir = os.path.expandvars(CONFIG["IO"]["data-dir"])
        dialog.set_current_folder(data_dir)
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            CONFIG["IO"]["data-dir"] = dialog.get_current_folder()
            specdicts = []
            for fname in dialog.get_filenames():
                specdicts.extend(gxps.io.parse_spectrum_file(fname))
            for specdict in specdicts:
                self.data.add_spectrum(**specdict)
        dialog.hide()

    def ask_for_save(self):
        """Opens a AskForSaveDialog and then either saves the file or,
        if the user does not want to save, sets the project_isaltered
        to False. If the dialog is canceled, nothing happens and
        project_isaltered stays True."""
        dialog = self.get_widget("save_confirmation_dialog")
        response = dialog.run()
        if response == Gtk.ResponseType.YES:
            dialog.hide()
            self.on_save()
        elif response == Gtk.ResponseType.NO:
            dialog.hide()
            self.state.project_isaltered = False
        else:
            dialog.hide()

    def save(self, fname):
        """Saves project file."""
        gxps.io.save_project(fname, self.data, self.state)
        self.state.current_project = fname

    def on_save(self, *_args):
        """Saves the current project."""
        project = self.state.current_project
        if not project or project == "Untitled":
            self.on_save_as()
        else:
            self.save(self.state.current_project)

    def on_save_as(self, *_args):
        """Saves the current project as a new file."""
        dialog = self.get_widget("save_project_dialog")
        project_dir = os.path.expandvars(CONFIG["IO"]["project-dir"])
        dialog.set_current_folder(project_dir)
        dialog.set_current_name("untitled.gxps")
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            fname = dialog.get_filename()
            CONFIG["IO"]["project-dir"] = dialog.get_current_folder()
            self.save(fname)
        dialog.hide()


class Edit(Operator):
    """Contains methods for user initiated data manipulation."""
    def on_remove_selected_spectra(self, *_args):
        """Removes selected spectra."""
        spectra = self.state.selected_spectra
        for spectrum in spectra:
            self.data.remove_spectrum(spectrum)

    def on_edit_spectra(self, *_args):
        """Opens an 'Edit' dialog for selected spectra."""
        spectra = self.state.selected_spectra
        if not spectra:
            return
        self.state.editing_spectra = spectra
        dialog = self.get_widget("edit_spectrum_dialog")
        response = dialog.run()
        if response == Gtk.ResponseType.APPLY:
            values = dialog.get_values()
            for spectrum in spectra:
                for attr, value in values.items():
                    spectrum.set_meta(attr, value)
        dialog.hide()
        self.state.editing_spectra = []

    def on_calibrate(self, *_args):
        """Changes the calibration for selected spectra."""
        adjustment = self.get_widget("calibration_spinbutton_adjustment")
        calibration = float(adjustment.get_value())
        for spectrum in self.state.active_spectra:
            spectrum.energy_calibration = calibration

    def on_normalize(self, *_args):
        """Changes the normalization for selected spectra."""
        combo = self.get_widget("normalization_combo")
        normid = combo.get_active_id()
        if normid is None:
            return
        norm_type = self.state.titles["norm_type_ids"].inverse[normid]
        for spectrum in self.state.active_spectra:
            spectrum.normalization_type = norm_type

    def on_normalize_manual(self, *_args):
        """Changes the normalization divisor directly."""
        entry = self.get_widget("normalization_entry")
        for spectrum in self.state.active_spectra:
            if spectrum.normalization_type != "manual":
                raise ValueError("Normalization is not set to manual")
            spectrum.normalization_divisor = 1 / float(entry.get_text())


class Fit(Operator):
    """Methods for drawing peaks, fitting and peak and background
    manipulation."""
    def on_add_region(self, *_args):
        """Add two region boundaries to each of the active spectra."""
        def add_region(emin, emax):
            """Add region"""
            for spectrum in self.state.active_spectra:
                spectrum.background_type = "shirley"
                spectrum.add_background_bounds(emin, emax)
        spanprops = {"edgecolor": COLORS["Plotting"]["region-vlines"], "lw": 2}
        navbar = self.get_widget("plot_toolbar")
        navbar.get_span(add_region, **spanprops)

    @staticmethod
    def on_change_region(event):
        """Set a new region boundary."""
        if "release" not in event.properties["attr"]:
            return
        old_value = event.properties["old_value"][0]
        new_value = event.properties["value"][0]
        spectrum = event.properties["data"][0]
        bg_bounds = spectrum.background_bounds.copy()
        for lower, upper in zip(bg_bounds[0::2], bg_bounds[1::2]):
            if old_value == lower:
                spectrum.remove_background_bounds(lower, upper)
                spectrum.add_background_bounds(new_value, upper)
            if old_value == upper:
                spectrum.remove_background_bounds(lower, upper)
                spectrum.add_background_bounds(lower, new_value)

    def on_remove_region(self, *_args):
        """Remove selected region."""
        def remove_region(_x_0, _y_0, x_1, _y_1):
            """Remove region"""
            esel = x_1
            for spectrum in self.state.active_spectra:
                bg_bounds = spectrum.background_bounds.copy()
                for lower, upper in zip(bg_bounds[0::2], bg_bounds[1::2]):
                    if esel >= lower and esel <= upper:
                        spectrum.remove_background_bounds(lower, upper)
        navbar = self.get_widget("plot_toolbar")
        navbar.get_point(remove_region)

    def on_add_peak(self, *_args):
        """Add peak to active regions."""
        def add_peak(position, height, angle):
            """Create new peak from drawn parameters."""
            for spectrum in self.state.active_spectra:
                height -= spectrum.background_of_E(position)
                name = self.state.next_peak_name
                shape = "PseudoVoigt"
                spectrum.add_peak(name, position=position, angle=angle,
                                  height=height, shape=shape)
        wedgeprops = {}
        navbar = self.get_widget("plot_toolbar")
        navbar.get_wedge(add_peak, **wedgeprops)

    def on_remove_active_peak(self, *_args):
        """Remove active peak."""
        for peak in self.state.active_peaks:
            self.state.peak_names.remove(peak.name)
            peak.spectrum.remove_peak(peak)

    def on_clear_peaks(self, *_args):
        """Remove all peaks from active spectra."""
        # with EventQueue("combine-all"):
        for spectrum in self.state.selected_spectra:
            for peak in spectrum.peaks:
                self.state.peak_names.remove(peak.name)
                spectrum.remove_peak(peak.name)

    def on_peak_entry_activate(self, *_args):
        """Change the active peak's parameters."""
        active_peaks = self.state.active_peaks
        if len(active_peaks) != 1:
            return
        peak = active_peaks[0]
        entries = {
            "peak_position_entry": "position",
            "peak_area_entry": "area",
            "peak_fwhm_entry": "fwhm",
            "peak_alpha_entry": "alpha"
        }
        for widget_name, attr in entries.items():
            entry = self.get_widget(widget_name)
            constraints = self.parse_peak_entry(entry.get_text())
            peak.set_constraint(attr, **constraints)
        model_combo = self.get_widget("peak_model_combo")
        peak.shape = peak.shapes[model_combo.get_active()]

    def on_peak_name_entry_changed(self, *_args):
        """Change the active peak's name."""
        active_peaks = self.state.active_peaks
        if len(active_peaks) != 1:
            return
        peak = active_peaks[0]
        name_entry = self.get_widget("peak_name_entry")
        name = name_entry.get_text()
        peak.label = name

    def on_fit(self, *_args):
        """Do the fucking fitting."""
        active_spectra = self.state.active_spectra
        for spectrum in active_spectra:
            spectrum.do_fit()

    @staticmethod
    def parse_peak_entry(param_string):
        """Parse what is entered into a peak entry field."""
        kwargs = {}
        if "<" in param_string or ">" in param_string:
            try:
                kwargs["min"] = float(param_string.split(">")[1].split()[0])
            except IndexError:
                kwargs["min"] = None
            try:
                kwargs["max"] = float(param_string.split("<")[1].split()[0])
            except IndexError:
                kwargs["max"] = None
        else:
            try:
                kwargs["value"] = float(param_string.strip())
            except ValueError:
                kwargs["expr"] = param_string.strip()
        return kwargs


class ViewController(Operator):
    """Contains methods for user initiated view manipulation."""
    def on_show_selected_spectra(self, *_args):
        """Callback for showing all selected spectra."""
        spectra = self.state.selected_spectra
        self.state.active_spectra = spectra

    def on_spectrum_view_row_activated(self, treeview, path, _col):
        """Callback for row activation by Enter key or double click."""
        model = treeview.get_model()
        iter_ = model.get_iter(path)
        spectrum = model.get(iter_, 0)[0]
        self.state.active_spectra = [spectrum]

    def on_spectrum_view_clicked(self, treeview, event):
        """Callback for button-press-event, popups the menu on right click.
        Return value determines if the selection on self persists,
        True if not."""
        if not (event.type == Gdk.EventType.BUTTON_PRESS
                and event.button == Gdk.BUTTON_SECONDARY):
            return False
        _, pathlist = treeview.get_selection().get_selected_rows()
        tvmenu = self.get_widget("spectrum_view_context_menu")
        tvmenu.popup(None, None, None, None, event.button, event.time)
        pathinfo = treeview.get_path_at_pos(int(event.x), int(event.y))
        if pathinfo is None:
            return False
        return pathinfo[0] in pathlist

    def on_spectrum_view_filter_changed(self, *_args):
        """Applies search term from entry.get_text() to the TreeView in column
        combo.get_active_text()."""
        combo = self.get_widget("spectrum_view_search_combo")
        entry = self.get_widget("spectrum_view_search_entry")
        self.state.spectra_tv_filter = (
            combo.get_active_text(),
            entry.get_text()
        )

    def on_peak_view_row_activated(self, treeview, path, _col):
        """Callback for row activation by Enter key or single click."""
        model = treeview.get_model()
        iter_ = model.get_iter(path)
        peak = model.get(iter_, 0)[0]
        self.state.active_peaks = [peak]

    def on_show_rsfs(self, *_args):
        """Opens an RSF dialog."""
        dialog = self.get_widget("rsf_dialog")
        source_combo = self.get_widget("rsf_combo")
        element_entry = self.get_widget("rsf_entry")
        source_combo.set_active_id(self.state.photon_source_id)
        element_entry.set_text(" ".join(self.state.rsf_elements))
        response = dialog.run()
        if response == Gtk.ResponseType.APPLY:
            elements = re.findall(r"[\w]+", element_entry.get_text())
            self.state.rsf_elements = [element.title() for element in elements]
            self.state.photon_source = source_combo.get_active_text()
        elif response == Gtk.ResponseType.REJECT:
            self.state.rsf_elements = []
        dialog.hide()

    def on_center_plot(self, *_args):
        """Centers the plot via the navbar command."""
        navbar = self.get_widget("plot_toolbar")
        navbar.center()

    def on_pan_plot(self, *_args):
        """Activates plot panning."""
        navbar = self.get_widget("plot_toolbar")
        navbar.pan()

    def on_zoom_plot(self, *_args):
        """Activates plot panning."""
        navbar = self.get_widget("plot_toolbar")
        navbar.zoom()

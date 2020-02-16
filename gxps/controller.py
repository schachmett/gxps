"""Class holding all the actions that can be invoked by the user.
"""
# pylint: disable=wrong-import-position
# pylint: disable=logging-format-interpolation
# pylint: disable=too-few-public-methods

import logging
import os.path
import re

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk

from gxps import CONFIG, COLORS
from gxps.utility import EventQueue
import gxps.io

LOG = logging.getLogger(__name__)


class Controller():
    """Gets all user input and triggers the appropriate functions."""
    def __init__(self, app, gui, spectra):
        self._app = app
        self._gui = gui
        self._spectra = spectra

        self.project = ProjectController(app, gui, spectra)
        self.data = DataController(app, gui, spectra)
        self.view = ViewController(app, gui, spectra)
        self.fit = FitController(app, gui, spectra)

    # @staticmethod
    # def on_view_logfile(_action, *_args):
    #     """Views logfile in external text editor."""
    #     if sys.platform.startswith("linux"):
    #         os.system("xdg-open {}".format(str(LOG_PATH)))
    #     else:
    #         logger.warning("logfile viewing only implemented for linux")
    #
    # @staticmethod
    # def on_edit_colors(_action, *_args):
    #     """Views colors.ini file in external text editor."""
    #     if sys.platform.startswith("linux"):
    #         os.system("xdg-open {}".format(str(COLOR_CFG_PATH)))
    #     else:
    #         logger.warning("color file editing only implemented for linux")
    #
    # def on_about(self, _widget, *_ignore):
    #     """Show 'About' dialog."""
    #     dialog = self.builder.get_object("about_dialog")
    #     dialog.set_program_name(__appname__)
    #     dialog.set_authors(__authors__)
    #     dialog.set_version(__version__)
    #     dialog.set_license_type(Gtk.License.GPL_3_0)
    #     commentstring = """If you encounter any bugs, mail me or open an
    #                     issue on my github. Please include a logfile, it is
    #                     located at '{}'.
    #                     """.format(str(LOG_PATH))
    #     commentstring = " ".join(commentstring.split())
    #     dialog.set_website(__website__)
    #     dialog.set_comments(commentstring)
    #     dialog.run()
    #     dialog.hide()


class ProjectController():
    """Manages project files."""
    def __init__(self, app, gui, spectra):
        self._app = app
        self._gui = gui
        self._spectra = spectra
        for signal in self._spectra.signals:
            self._spectra.connect(signal, self.changed)

    def changed(self, *_args):
        """Marks project as altered."""
        self._gui.project_isaltered = True

    def ask_for_save(self):
        """Opens a AskForSaveDialog and then either saves the file or,
        if the user does not want to save, sets the project_isaltered
        to False. If the dialog is canceled, nothing happens and
        project_isaltered stays True.
        """
        dialog = self._app.builder.get_object("save_confirmation_dialog")
        response = dialog.run()
        if response == Gtk.ResponseType.YES:
            dialog.hide()
            self.on_save()
        if response == Gtk.ResponseType.NO:
            dialog.hide()
            self._gui.project_isaltered = False
        dialog.hide()

    def new(self):
        """Make new project."""
        self._spectra.clear_spectra()
        self._gui.current_project = ""

    def open(self, fname, merge=False):
        """Load project file."""
        spectra, active_s_keys, active_p_keys = gxps.io.load_project(fname)
        if not merge:
            self._spectra.clear_spectra()
        for spectrum in spectra:
            self._spectra.add_spectrum(spectrum)
        if not merge:
            self._gui.active_spectra = [
                spectrum
                for spectrum in spectra
                if spectrum.key in active_s_keys
            ]
            self._gui.active_peak = [
                peak
                for spectrum in self._gui.active_spectra
                for peak in spectrum.model.peaks
                if peak.key in active_p_keys
            ]
            self._gui.current_project = fname
        LOG.info("Opened project file {}".format(fname))

    def save(self, fname):
        """Saves project file."""
        gxps.io.save_project(fname, self._spectra, self._gui)
        self._gui.current_project = fname

    def on_new(self, *_args):
        """User callback for making a new project."""
        if self._gui.project_isaltered:
            self.ask_for_save()
        if self._gui.project_isaltered:
            return
        self.new()

    def on_open(self, *_args):
        """Let the user choose a project file to open and open it through
        self.open_project."""
        if self._gui.project_isaltered:
            self.ask_for_save()
        if self._gui.project_isaltered:
            return
        dialog = Gtk.FileChooserDialog(
            "Open project...",
            self._app.builder.get_object("main_window"),
            Gtk.FileChooserAction.OPEN,
            ("_Cancel", Gtk.ResponseType.CANCEL, "_Open", Gtk.ResponseType.OK),
        )
        project_dir = os.path.expandvars(CONFIG["IO"]["project-dir"])
        dialog.set_current_folder(project_dir)
        dialog.add_filter(Filter(".gxps", ["*.gxps"]))
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            fname = dialog.get_filename()
            CONFIG["IO"]["project-dir"] = dialog.get_current_folder()
            self.open(fname)
        dialog.destroy()

    def on_merge(self, *_args):
        """Merges a project file into the current project."""
        dialog = Gtk.FileChooserDialog(
            "Merge project...",
            self._app.builder.get_object("main_window"),
            Gtk.FileChooserAction.OPEN,
            ("_Cancel", Gtk.ResponseType.CANCEL, "_Open", Gtk.ResponseType.OK),
        )
        project_dir = os.path.expandvars(CONFIG["IO"]["project-dir"])
        dialog.set_current_folder(project_dir)
        dialog.add_filter(Filter(".gxps", ["*.gxps"]))
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            fname = dialog.get_filename()
            CONFIG["IO"]["project-dir"] = dialog.get_current_folder()
            self.open(fname, merge=True)
        dialog.destroy()

    def on_save(self, *_args):
        """Saves the current project."""
        if self._gui.current_project:
            self.save(self._gui.current_project)
        else:
            self.on_save_as()

    def on_save_as(self, *_args):
        """Saves the current project as a new file."""
        dialog = Gtk.FileChooserDialog(
            "Save project...",
            self._app.builder.get_object("main_window"),
            Gtk.FileChooserAction.SAVE,
            ("_Cancel", Gtk.ResponseType.CANCEL, "_Save", Gtk.ResponseType.OK)
        )
        project_dir = os.path.expandvars(CONFIG["IO"]["project-dir"])
        dialog.set_current_folder(project_dir)
        dialog.set_do_overwrite_confirmation(True)
        dialog.add_filter(Filter(".gxps", ["*.gxps"]))
        dialog.set_current_name("untitled.gxps")
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            fname = dialog.get_filename()
            CONFIG["IO"]["project-dir"] = dialog.get_current_folder()
            self.save(fname)
        dialog.destroy()


class DataController():
    """Contains methods for user initiated data manipulation.
    """
    def __init__(self, app, gui, spectra):
        self._app = app
        self._gui = gui
        self._spectra = spectra

    def on_import(self, *_args):
        """Imports spectra from a data file."""
        dialog = Gtk.FileChooserDialog(
            "Import data...",
            self._app.builder.get_object("main_window"),
            Gtk.FileChooserAction.OPEN,
            ("_Cancel", Gtk.ResponseType.CANCEL, "_Open", Gtk.ResponseType.OK),
        )
        data_dir = os.path.expandvars(CONFIG["IO"]["data-dir"])
        dialog.set_current_folder(data_dir)
        dialog.set_select_multiple(True)
        dialog.add_filter(Filter("all files", ["*.xym", "*txt", "*.xy"]))
        dialog.add_filter(Filter(".xym", ["*.xym"]))
        dialog.add_filter(Filter(".xy", ["*.xy"]))
        dialog.add_filter(Filter(".txt", ["*.txt"]))
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            CONFIG["IO"]["data-dir"] = dialog.get_current_folder()
            specdicts = []
            for fname in dialog.get_filenames():
                specdicts.extend(gxps.io.parse_spectrum_file(fname))
            for specdict in specdicts:
                self._spectra.add_spectrum(**specdict)
        dialog.destroy()

    def on_remove_selected_spectra(self, *_args):
        """Removes selected spectra."""
        spectra = self._gui.selected_spectra
        for spectrum in spectra:
            self._spectra.remove_spectrum(spectrum)

    def on_edit_spectra(self, *_args):
        """Opens an 'Edit' dialog for selected spectra."""
        spectra = self._gui.selected_spectra
        if not spectra:
            return
        self._gui.editing_spectra = spectra
        dialog = self._app.builder.get_object("edit_spectrum_dialog")
        response = dialog.run()
        if response == Gtk.ResponseType.APPLY:
            values = dialog.get_values()
            for spectrum in spectra:
                for attr, value in values.items():
                    spectrum.meta.set(attr, value)
        dialog.hide()
        self._gui.editing_spectra = []

    def on_calibrate(self, *_args):
        """Changes the calibration for selected spectra."""
        adjustment = self._app.builder.get_object(
            "calibration_spinbutton_adjustment")
        calibration = float(adjustment.get_value())
        for spectrum in self._gui.active_spectra:
            spectrum.energy_calibration = calibration

    def on_normalize(self, *_args):
        """Changes the normalization for selected spectra."""
        combo = self._app.builder.get_object("normalization_combo")
        normid = combo.get_active_id()
        if normid is None:
            return
        norm_type = self._gui.titles["norm_type_ids"].inverse[normid]
        for spectrum in self._gui.active_spectra:
            spectrum.normalization_type = norm_type

    def on_normalize_manual(self, *_args):
        """Changes the normalization divisor directly."""
        entry = self._app.builder.get_object("normalization_entry")
        for spectrum in self._gui.active_spectra:
            if spectrum.normalization_type != "manual":
                raise ValueError("Normalization is not set to manual")
            spectrum.normalization_divisor = 1 / float(entry.get_text())


class FitController():
    """Methods for drawing peaks, fitting and peak and background
    manipulation.
    """
    def __init__(self, app, gui, spectra):
        self._app = app
        self._gui = gui
        self._spectra = spectra

    def on_add_region(self, *_args):
        """Add two region boundaries to each of the active spectra."""
        def add_region(emin, emax):
            """Add region"""
            with EventQueue("combine-all"):
                for spectrum in self._gui.active_spectra:
                    spectrum.background_type = "shirley"
                    spectrum.add_background_bounds(emin, emax)
        spanprops = {"edgecolor": COLORS["Plotting"]["region-vlines"], "lw": 2}
        navbar = self._app.builder.get_object("plot_toolbar")
        navbar.get_span(add_region, **spanprops)

    def on_remove_region(self, *_args):
        """Remove selected region."""
        def remove_region(_x_0, _y_0, x_1, _y_1):
            """Remove region"""
            esel = x_1
            with EventQueue("combine-all"):
                for spectrum in self._gui.active_spectra:
                    bg_bounds = spectrum.background_bounds.copy()
                    for lower, upper in zip(bg_bounds[0::2], bg_bounds[1::2]):
                        if esel >= lower and esel <= upper:
                            spectrum.remove_background_bounds(lower, upper)
        navbar = self._app.builder.get_object("plot_toolbar")
        navbar.get_point(remove_region)

    def on_add_peak(self, *_args):
        """Add peak to active regions."""
        def add_peak(position, height, angle):
            """Create new peak from drawn parameters."""
            for spectrum in self._gui.active_spectra:
                height -= spectrum.background_of_E(position)
                for pname in self._gui.peak_name_list:
                    if pname not in self._gui.peak_names:
                        name = pname
                        break
                self._gui.peak_names.append(name)
                with EventQueue("combine-all"):
                    spectrum.model.add_peak(
                        name,
                        position=position,
                        angle=angle,
                        height=height,
                        shape="PseudoVoigt"
                    )
        wedgeprops = {}
        navbar = self._app.builder.get_object("plot_toolbar")
        navbar.get_wedge(add_peak, **wedgeprops)

    def on_remove_peak(self, *_args):
        """Remove active peak."""
        with EventQueue("combine-all"):
            for peak in self._gui.active_peaks:
                peak.s_model.remove_peak(peak.name)
                self._gui.peak_names.remove(peak.name)

    def on_clear_peaks(self, *_args):
        """Remove all peaks from active spectra."""
        with EventQueue("combine-all"):
            for spectrum in self._gui.selected_spectra:
                for peak in spectrum.model.peaks:
                    peak.s_model.remove_peak(peak.name)
                    self._gui.peak_names.remove(peak.name)

    def on_peak_entry_activate(self, *_args):
        """Change the active peak's parameters."""
        active_peaks = self._gui.active_peaks
        if len(active_peaks) != 1:
            return
        peak = active_peaks[0]

        position_entry = self._app.builder.get_object("peak_position_entry")
        area_entry = self._app.builder.get_object("peak_area_entry")
        fwhm_entry = self._app.builder.get_object("peak_fwhm_entry")
        model_combo = self._app.builder.get_object("peak_model_combo")
        alpha_entry = self._app.builder.get_object("peak_alpha_entry")

        peak.shape = peak.shapes[model_combo.get_active()]
        position_kwargs = self.parse_peak_entry(position_entry.get_text())
        area_kwargs = self.parse_peak_entry(area_entry.get_text())
        fwhm_kwargs = self.parse_peak_entry(fwhm_entry.get_text())
        alpha_kwargs = self.parse_peak_entry(alpha_entry.get_text())

        with EventQueue("combine-all"):
            peak.set_constraint("position", **position_kwargs)
            peak.set_constraint("area", **area_kwargs)
            peak.set_constraint("fwhm", **fwhm_kwargs)
            peak.set_constraint("alpha", **alpha_kwargs)

    @staticmethod
    def parse_peak_entry(param_string):
        """Parse what is entered into a peak entry field."""
        # return float(param_string)
        kwargs = {}
        # if not param_string:
        #     self.dh.constrain_peak(peakID, param)
        if "<" in param_string or ">" in param_string:
            try:
                kwargs["min"] = float(param_string.split(">")[1].split()[0])
            except IndexError:
                kwargs["min"] = None
            try:
                kwargs["max"] = float(param_string.split("<")[1].split()[0])
            except IndexError:
                kwargs["max"] = None
            # self.dh.constrain_peak(peakID, param, min_=min_, max_=max_)
        else:
            try:
                kwargs["value"] = float(param_string.strip())
            except ValueError:
                kwargs["expr"] = param_string.strip()
                # self.dh.constrain_peak(peakID, param, expr=expr)
            # else:
            #     self.dh.constrain_peak(
            #         peakID, param, vary=False, value=value
            #     )
        return kwargs

    def on_peak_name_entry_changed(self, *_args):
        """Change the active peak's name."""
        active_peaks = self._gui.active_peaks
        if len(active_peaks) != 1:
            return
        peak = active_peaks[0]

        name_entry = self._app.builder.get_object("peak_name_entry")
        name = name_entry.get_text()
        peak.label = name


class ViewController():
    """Contains methods for user initiated view manipulation."""
    def __init__(self, app, gui, spectra):
        self._app = app
        self._gui = gui
        self._spectra = spectra

    def on_show_selected_spectra(self, *_args):
        """Callback for showing all selected spectra."""
        spectra = self._gui.selected_spectra
        self._gui.active_spectra = spectra

    def on_spectrum_view_row_activated(self, treeview, path, _col):
        """Callback for row activation by Enter key or double click."""
        model = treeview.get_model()
        iter_ = model.get_iter(path)
        spectrum = model.get(iter_, 0)[0]
        self._gui.active_spectra = [spectrum]

    def on_spectrum_view_clicked(self, treeview, event):
        """Callback for button-press-event, popups the menu on right click.
        Return value determines if the selection on self persists,
        True if not."""
        if not (event.type == Gdk.EventType.BUTTON_PRESS
                and event.button == Gdk.BUTTON_SECONDARY):
            return False
        _, pathlist = treeview.get_selection().get_selected_rows()
        tvmenu = self._app.builder.get_object("spectrum_view_context_menu")
        tvmenu.popup(None, None, None, None, event.button, event.time)
        pathinfo = treeview.get_path_at_pos(int(event.x), int(event.y))
        if pathinfo is None:
            return False
        return pathinfo[0] in pathlist

    def on_spectrum_view_filter_changed(self, *_args):
        """Applies search term from entry.get_text() to the TreeView in column
        combo.get_active_text()."""
        # damn user_data from glade does not allow to pass both widgets here
        # as arguments, so they must be fetched from the builder
        combo = self._app.builder.get_object("spectrum_view_search_combo")
        entry = self._app.builder.get_object("spectrum_view_search_entry")
        self._gui.spectra_tv_filter = (
            combo.get_active_text(),
            entry.get_text()
        )

    def on_peak_view_row_activated(self, treeview, path, _col):
        """Callback for row activation by Enter key or single click."""
        model = treeview.get_model()
        iter_ = model.get_iter(path)
        peak = model.get(iter_, 0)[0]
        self._gui.active_peaks = [peak]

    def on_show_rsfs(self, *_args):
        """Opens an RSF dialog."""
        dialog = self._app.builder.get_object("rsf_dialog")
        source_combo = self._app.builder.get_object("rsf_combo")
        element_entry = self._app.builder.get_object("rsf_entry")
        source_combo.set_active_id(self._gui.photon_source_id)
        element_entry.set_text(" ".join(self._gui.rsf_elements))
        response = dialog.run()
        if response == Gtk.ResponseType.APPLY:
            elements = re.findall(r"[\w]+", element_entry.get_text())
            self._gui.rsf_elements = [element.title() for element in elements]
            self._gui.photon_source = source_combo.get_active_text()
        elif response == Gtk.ResponseType.REJECT:
            self._gui.rsf_elements = []
        dialog.hide()

    def on_center_plot(self, *_args):
        """Centers the plot via the navbar command.
        """
        navbar = self._app.builder.get_object("plot_toolbar")
        navbar.center()

    def on_pan_plot(self, *_args):
        """Activates plot panning."""
        navbar = self._app.builder.get_object("plot_toolbar")
        navbar.pan()

    def on_zoom_plot(self, *_args):
        """Activates plot panning."""
        navbar = self._app.builder.get_object("plot_toolbar")
        navbar.zoom()


class Filter(Gtk.FileFilter):
    """Very simple FileFilter for FileChooserDialogs."""
    def __init__(self, name, patterns):
        super().__init__()
        for pattern in patterns:
            self.add_pattern(pattern)
        self.set_name(name)

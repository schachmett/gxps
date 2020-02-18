"""Gtk.Application class."""
# pylint: disable=wrong-import-position
# pylint: disable=logging-format-interpolation

import logging

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gio, GLib

from gxps import __appname__, __version__, ASSETDIR, CONFIG, COLORS
from gxps.utility import EventBus
from gxps.spectrum import SpectrumContainer
from gxps.state import GUIState
from gxps.controller import Controller
from gxps.view import ViewManager

import gxps.widgets         # pylint: disable=unused-import


LOG = logging.getLogger(__name__)


class GXPS(Gtk.Application):
    """Application class organising user interaction."""
    # pylint: disable=arguments-differ
    def __init__(self):
        app_id = "com.github.schachmett.{}".format(__appname__.lower())
        super().__init__(
            application_id=app_id,
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE
        )
        GLib.set_application_name(__appname__)
        self.set_resource_base_path(str(ASSETDIR))

        self.builder = Gtk.Builder.new()
        self.builder.add_from_file(str(ASSETDIR / "gtk/gxps.glade"))
        self.builder.add_from_file(str(ASSETDIR / "gtk/menus.ui"))

        self.bus = None
        self.win = None
        self.spectra = None
        self.gui = None
        self.controller = None
        self.view_manager = None

        self.add_main_option_entries([
            make_option("--verbosity", "-v", arg=GLib.OptionArg.INT,
                        description="Value from 1 (only errors) to 4 (debug)"),
            make_option("--version", description="show program version"),
            make_option("--clean", description="don't load previous file")
        ])

    def do_activate(self):
        """Instantiate MainWindow."""
        LOG.debug("Activating application...")
        # load the last used project file
        fname = CONFIG["IO"]["current-project"]
        # with EventQueue("combine-all"):
        if fname:
            try:
                self.controller.project.open(fname)
            except FileNotFoundError:
                LOG.warning("File '{}' not found".format(fname))
                self.controller.project.new()
            else:
                LOG.info("loaded file {}".format(fname))
        else:
            self.controller.project.new()

    def do_startup(self):
        """Adds actions."""
        LOG.info("Starting application...")
        Gtk.Application.do_startup(self)
        self.set_menubar(self.builder.get_object("menubar"))
        self.win = self.builder.get_object("main_window")
        self.win.startup(app=self)

        # initialize all the state objects and workers
        self.bus = EventBus(default_policy="fire")
        self.spectra = SpectrumContainer()
        self.spectra.register_queue(self.bus)
        self.gui = GUIState(self, self.spectra)
        self.gui.register_queue(self.bus)
        self.controller = Controller(self, self.gui, self.spectra)
        self.view_manager = ViewManager(self, self.gui, self.spectra)

        handlers = {
            "on_main_window_delete_event": self.on_quit,
            "on_calibration_spinbutton_value_changed":
                self.controller.data.on_calibrate,
            "on_normalization_combo_changed":
                self.controller.data.on_normalize,
            "on_normalization_entry_activate":
                self.controller.data.on_normalize_manual,
            "on_region_background_type_combo_changed": lambda *x: None,
            "on_peak_entry_activate":
                self.controller.fit.on_peak_entry_activate,
            "on_peak_name_entry_changed":
                self.controller.fit.on_peak_name_entry_changed,
            "on_spectrum_view_search_entry_changed":
                self.controller.view.on_spectrum_view_filter_changed,
            "on_spectrum_view_search_combo_changed":
                self.controller.view.on_spectrum_view_filter_changed,
            "on_spectrum_view_button_press_event":
                self.controller.view.on_spectrum_view_clicked,
            "on_spectrum_view_row_activated":
                self.controller.view.on_spectrum_view_row_activated,
            "on_peak_view_row_activated":
                self.controller.view.on_peak_view_row_activated,
            "on_spectrum_chooser_combo_changed": lambda *x: None
        }
        self.builder.connect_signals(handlers)

        actions = {
            "project-new": self.controller.project.on_new,
            "save-project": self.controller.project.on_save,
            "save-project-as": self.controller.project.on_save_as,
            "open-project": self.controller.project.on_open,
            "merge-project": self.controller.project.on_merge,
            "import-spectra": self.controller.data.on_import,
            "remove-spectra": self.controller.data.on_remove_selected_spectra,
            "edit-spectra": self.controller.data.on_edit_spectra,
            "remove-region": self.controller.fit.on_remove_region,
            "clear-regions": lambda *x: None,
            "add-region": self.controller.fit.on_add_region,
            "add-peak": self.controller.fit.on_add_peak,
            "add-guessed-peak": lambda *x: None,
            "remove-peak": self.controller.fit.on_remove_peak,
            "clear-peaks": self.controller.fit.on_clear_peaks,
            "avg-selected-spectra": lambda *x: None,
            "fit": lambda *x: None,
            "export-txt": lambda *x: None,
            "export-image": lambda *x: None,
            "quit": self.on_quit
        }
        for name, callback in actions.items():
            simple = Gio.SimpleAction.new(name, None)
            simple.connect("activate", callback)
            self.add_action(simple)
        win_actions = {
            "about": lambda *x: None,
            "center-plot": self.controller.view.on_center_plot,
            "pan-plot": self.controller.view.on_pan_plot,
            "zoom-plot": self.controller.view.on_zoom_plot,
            "show-selected-spectra":
                self.controller.view.on_show_selected_spectra,
            "show-atomlib": self.controller.view.on_show_rsfs,
            "view-logfile": lambda *x: None,
            "edit-colors": lambda *x: None
        }
        for name, callback in win_actions.items():
            simple = Gio.SimpleAction.new(name, None)
            simple.connect("activate", callback)
            self.win.add_action(simple)

    def do_command_line(self, command_line):
        """Handles command line arguments"""
        Gtk.Application.do_command_line(self, command_line)
        options = command_line.get_options_dict()
        if options.contains("verbosity"):
            verb = options.lookup_value("verbosity", GLib.VariantType("i"))
            levels = (
                None,
                logging.ERROR,
                logging.WARNING,
                logging.INFO,
                logging.DEBUG
                )
            logging.getLogger().handlers[0].setLevel(levels[verb.unpack()])
        if options.contains("version"):
            print("{} version: {}".format(__appname__, __version__))
            self.quit()
        if options.contains("clean"):
            CONFIG["IO"]["current-project"] = ""
        self.activate()
        return 0

    def on_quit(self, *_args):
        """Clean up, write configs, ask if user wants to save, and die."""
        if self.gui.project_isaltered:
            self.controller.project.ask_for_save()
        if self.gui.project_isaltered:
            return True
        xsize, ysize = self.win.get_size()
        xpos, ypos = self.win.get_position()
        CONFIG["Window"]["xsize"] = str(xsize)
        CONFIG["Window"]["ysize"] = str(ysize)
        CONFIG["Window"]["xpos"] = str(xpos)
        CONFIG["Window"]["ypos"] = str(ypos)
        CONFIG.save()
        COLORS.save()
        LOG.info("quitting...")
        self.quit()
        return False


def make_option(long_name, short_name=None, arg=GLib.OptionArg.NONE, **kwargs):
    """Make GLib option for the command line. Uses kwargs description, flags,
    arg_data and arg_description."""
    # surely something like this should exist inside PyGObject itself?!
    option = GLib.OptionEntry()
    option.long_name = long_name.lstrip('-')
    option.short_name = 0 if not short_name else ord(short_name.lstrip('-'))
    option.arg = arg
    option.flags = kwargs.get("flags", 0)
    option.arg_data = kwargs.get("arg_data", None)
    option.description = kwargs.get("description", None)
    option.arg_description = kwargs.get("arg_description", None)
    return option

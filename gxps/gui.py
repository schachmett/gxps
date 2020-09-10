"""Gtk.Application class."""
# pylint: disable=wrong-import-position
# pylint: disable=logging-format-interpolation

import logging

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gio, GLib

from gxps import __appname__, __version__
from gxps.xdg import DATA_DIR
from gxps.config import CONFIG, COLORS
from gxps.utility import EventBus
from gxps.spectrum import SpectrumContainer
from gxps.state import State
from gxps.control import CommandSender
from gxps.view import ViewManager

import gxps.widgets         # pylint: disable=unused-import


LOG = logging.getLogger(__name__)


class GXPS(Gtk.Application):
    """Application class organising user interaction."""
    # pylint: disable=arguments-differ
    # pylint: disable=too-many-instance-attributes
    def __init__(self):
        app_id = "com.github.schachmett.{}".format(__appname__.lower())
        super().__init__(
            application_id=app_id,
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE
        )
        GLib.set_application_name(__appname__)
        self.set_resource_base_path(str(DATA_DIR / "assets"))

        self.builder = Gtk.Builder.new()
        self.builder.add_from_file(str(DATA_DIR / "ui/gxps.glade"))
        self.builder.add_from_file(str(DATA_DIR / "ui/menus.ui"))
        self.get_widget = self.builder.get_object

        self.win = None
        self.bus = None
        self.commandsender = None
        self.data = None
        self.state = None
        self._view = None

        self.add_main_option_entries([
            make_option("--verbosity", "-v", arg=GLib.OptionArg.INT,
                        description="Value from 1 (only errors) to 4 (debug)"),
            make_option("--version", description="show program version"),
            make_option("--clean", description="don't load previous file")
        ])

    def do_activate(self):
        """Instantiate MainWindow."""
        LOG.info("GXPS has version '{}'".format(__version__))
        # load the last used project file
        fname = CONFIG["IO"]["current-project"]
        self.commandsender(fname, "startup")

    def do_startup(self):
        """Adds actions."""
        LOG.info("Starting application...")
        Gtk.Application.do_startup(self)
        self.set_menubar(self.builder.get_object("menubar"))
        self.win = self.get_widget("main_window")
        self.win.startup(app=self)

        # initialize all the state objects and workers
        complement_builder(self.builder)
        self.bus = EventBus(default_policy="fire")
        self.data = SpectrumContainer()
        self.data.register_queue(self.bus)
        self.state = State(self, self.data)
        self.state.register_queue(self.bus)
        self._view = ViewManager(self, self.state, self.data)
        self.commandsender = CommandSender(
            self.bus,
            self.data,
            self.state,
            self.get_widget
        )

        callbacks = [
            "on_spectrum_view_search_entry_changed",
            "on_spectrum_view_search_combo_changed",
            "on_spectrum_view_button_press_event",
            "on_spectrum_view_row_activated",
            "on_calibration_spinbutton_value_changed",
            "on_normalization_combo_changed",
            "on_normalization_entry_activate",
            "on_region_background_type_combo_changed",
            "on_peak_entry_activate",
            "on_peak_name_entry_changed",
            "on_peak_view_row_activated",
            "on_peak_model_combo_changed",
            "on_img_export_change"
        ]
        actions = [
            "project-new", "save-project", "save-project-as", "open-project",
            "merge-project", "import-spectra", "export-txt", "export-params",
            "export-image",

            "edit-spectra", "remove-spectra", "avg-selected-spectra",

            "add-region", "remove-region", "clear-regions", "add-peak",
            "add-guessed-peak", "remove-peak", "clear-peaks", "fit",

            "show-selected-spectra", "show-atomlib", "center-plot", "pan-plot",
            "zoom-plot",

            "view-logfile", "edit-colors", "about"
        ]
        handlers = dict((key, (self.commandsender, key)) for key in callbacks)
        handlers["on_main_window_delete_event"] = self.on_quit
        self.builder.connect_signals(handlers)
        for name in actions:
            simple = Gio.SimpleAction.new(name, None)
            simple.connect("activate", self.commandsender, name)
            self.add_action(simple)
        simple = Gio.SimpleAction.new("quit", None)
        simple.connect("activate", self.on_quit)
        self.add_action(simple)

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
            return 0
        if options.contains("clean"):
            CONFIG["IO"]["current-project"] = ""
        self.do_activate()
        return 0

    def on_quit(self, *_args):
        """Clean up, write configs, ask if user wants to save, and die."""
        if self.state.project_isaltered:
            self.commandsender("ask-for-save")
        if self.state.project_isaltered:
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


def complement_builder(builder):
    """Do trivial GTK stuff that the builder can not do."""
    # Save confirmation dialog
    save_conf_dialog = builder.get_object("save_confirmation_dialog")
    save_conf_dialog.set_accels()
    # Plot navigation toolbar
    navbar = builder.get_object("plot_toolbar")
    navbar.startup(builder)
    # RSF dialog
    rsf_dialog = builder.get_object("rsf_dialog")
    rsf_entry = builder.get_object("rsf_entry")
    def apply_rsf(*_args):
        """Let the dialog send APPLY response."""
        rsf_dialog.emit("response", Gtk.ResponseType.APPLY)
    rsf_entry.connect("activate", apply_rsf)

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

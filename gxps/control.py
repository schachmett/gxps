"""Classes for issuing commands and managing undo/redo history."""
# pylint: disable=logging-format-interpolation

import logging

from gxps.controller import File, Edit, Fit, ViewC, Help


LOG = logging.getLogger(__name__)


class CommandSender:
    """Gets all user input and triggers the appropriate functions."""
    # pylint: disable=too-many-instance-attributes
    def __init__(self, bus, data, state, get_widget):
        self.bus = bus
        self.data = data
        self.state = state
        self.get_widget = get_widget
        self.history = History()

        self._file = File(get_widget, self.state, self.data, self.bus)
        self._edit = Edit(get_widget, self.state, self.data, self.bus)
        self._fit = Fit(get_widget, self.state, self.data, self.bus)
        self._view = ViewC(get_widget, self.state, self.data, self.bus)
        self._help = Help(get_widget, self.state, self.data, self.bus)

        self.callbacks = {
            # File actions
            "startup": self._file.startup,
            "ask-for-save": self._file.ask_for_save,
            "project-new": self._file.on_new,
            "save-project": self._file.on_save,
            "save-project-as": self._file.on_save_as,
            "open-project": self._file.on_open,
            "merge-project": self._file.on_merge,
            "import-spectra": self._file.on_import,
            "export-txt": lambda *x: None,
            "export-image": lambda *x: None,

            # Edit actions
            "edit-spectra": self._edit.on_edit_spectra,
            "remove-spectra": self._edit.on_remove_selected_spectra,
            "avg-selected-spectra": lambda *x: None,
            # Edit handlers
            "on_calibration_spinbutton_value_changed": self._edit.on_calibrate,
            "on_normalization_combo_changed": self._edit.on_normalize,
            "on_normalization_entry_activate": self._edit.on_normalize_manual,
            "on_region_background_type_combo_changed": lambda *x: None,

            # Fit actions
            "add-region": self._fit.on_add_region,
            "remove-region": self._fit.on_remove_region,
            "clear-regions": lambda *x: None,
            "add-peak": self._fit.on_add_peak,
            "add-guessed-peak": lambda *x: None,
            "remove-peak": self._fit.on_remove_active_peak,
            "clear-peaks": self._fit.on_clear_peaks,
            "fit": self._fit.on_fit,
            # Fit handlers
            "on_peak_entry_activate": self._fit.on_peak_entry_activate,
            "on_peak_name_entry_changed": self._fit.on_peak_name_entry_changed,

            # View actions
            "show-selected-spectra": self._view.on_show_selected_spectra,
            "show-atomlib": self._view.on_show_rsfs,
            "center-plot": self._view.on_center_plot,
            "pan-plot": self._view.on_pan_plot,
            "zoom-plot": self._view.on_zoom_plot,
            # View handlers
            "on_spectrum_view_search_entry_changed":
                self._view.on_spectrum_view_filter_changed,
            "on_spectrum_view_search_combo_changed":
                self._view.on_spectrum_view_filter_changed,
            "on_spectrum_view_button_press_event":
                self._view.on_spectrum_view_clicked,
            "on_spectrum_view_row_activated":
                self._view.on_spectrum_view_row_activated,
            "on_peak_view_row_activated":
                self._view.on_peak_view_row_activated,

            # Help actions
            "view-logfile": self._help.on_view_logfile,
            "edit-colors": self._help.on_edit_colors,
            "about": self._help.on_about,
        }

        self.bus.subscribe(self._fit.on_change_region, "changed-vline", 5)

    def __call__(self, *args):
        key = args[-1]
        if key not in self.callbacks:
            LOG.warning("Action/Handler {} does not exist".format(key))
            return False
        do_func = self.callbacks[key]
        command = Command(do_func)
        return self.history.do_command(command, *args[:-1])

    def callback(self, *_args):
        """Manages observer-style subscriptions."""

    def execute(self, command):
        """Execute a command object."""
        self.history.do_command(command)
        self.bus.fire()


class History:
    """Stores commands, organizes undo/redo."""
    def __init__(self):
        self._commands_done = []
        self._commands_redoable = []

    def do_command(self, command, *args, **kwargs):
        """Executes a command."""
        if command.undoable:
            self._commands_redoable.clear()
        return_value = command(*args, **kwargs)
        if command.undoable:
            self._commands_done.append(command)
        return return_value

    def undo(self):
        """Undoes last command."""
        command = self._commands_done.pop()
        command.undo()
        self._commands_redoable.append(command)

    def redo(self):
        """Redoes last command."""
        command = self._commands_redoable.pop()
        command.redo()
        self._commands_done.append(command)


class Command:
    """Executes user action: Affects the self.data and self.state objects,
    uses self.get_widget.
    """
    def __init__(self, func=None, undo_func=None, redo_func=None, data=None):
        self.func = func
        if self.func is None:
            raise ValueError("Command missing executor function")
        self.undo_func = undo_func
        self.redo_func = redo_func
        self.data = data
        self.state = []
        self.data = []
        self.obj = None

    @property
    def undoable(self):
        """Make testing for undoability available."""
        return self.undo_func is not None

    @property
    def redoable(self):
        """Make testing for redoability available."""
        return self.redo_func is not None

    def __call__(self, *args, **kwargs):
        self.state = self.func(*args, **kwargs)
        return self.state

    def undo(self):
        """Call the undo function."""
        if self.undo_func is None:
            raise AttributeError("Command {} has no undoer".format(self))
        self.undo_func(*self.state)

    def redo(self, *args, **kwargs):
        """Call the redo function. If it is None, call the normal executor."""
        if self.undo_func is None:
            self(*args, **kwargs)
        self.redo_func(*self.state)

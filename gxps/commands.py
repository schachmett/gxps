"""Implementations of Command class.
Command has method self.get_widget for retrieving Gtk widgets and attributes
self.state (representing GUI state) as well as self.data (representing
spectra).
"""
# pylint: disable=wrong-import-position
# pylint: disable=logging-format-interpolation

import logging
# import os
# import weakref
import functools

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk #, Gio, GLib

# from gxps import CONFIG
# import gxps.io
# from gxps.widgets import GXPSImportDialog


LOG = logging.getLogger(__name__)


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


# def cmd(func):
#     def wrapper(*args, **kwargs):
#         obj = func.__self__
#         a = func(*args, **kwargs)
#         return a
#     return wrapper



class TC:
    def __init__(self):
        self.last = 0
        self.now = 0

    @Command
    def makegreat(self, value):
        self.last = self.now
        self.now = value
        # return x

    @makegreat.undoer
    def makegreat(self):
        self.now = self.last

    def prln(self):
        print("last: {}".format(self.last))
        print("now: {}".format(self.now))

# x = tclass()
# a = x.makegreat
# a(5)
# a.print()
# a.undo()
# x.print()
# a(8)
# x.print()
# a(10)
# x.print()
# a.undo()
# x.print()


    # def setup(self, *args):
    #     """Provide additional data for execution that is needed."""
    #     self.setup_data = args
    #
    # def execute(self):
    #     """Command execution method to be called from outside."""
    #     self.do_execute()
    #     self.done = True
    #
    # def do_execute(self):
    #     """Does the action. Implemented by child classes."""
    #     raise NotImplementedError
    #
    # def undo(self):
    #     """Reverts data / state objects into the state before self.execute().
    #     """
    #     raise NotImplementedError
    #
    # def redo(self):
    #     """If execute requires a lot of cpu time, this is the faster
    #     way compared to a second self.execute().
    #     """
    #     self.execute()


# class ImportCommand(Command):
#     """Imports data."""
#     # pylint: disable=not-a-mapping
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         self._added_spectra = weakref.WeakSet([])
#         self._fnames = []
#
#     def do_execute(self):
#         data_dir = os.path.expandvars(CONFIG["IO"]["data-dir"])
#         dialog = ImportDialog(self.get_widget("main_window"), data_dir)
#         response = dialog.run()
#         if response == Gtk.ResponseType.OK:
#             CONFIG["IO"]["data-dir"] = dialog.get_current_folder()
#             specdicts = []
#             for fname in dialog.get_filenames():
#                 specdicts.extend(gxps.io.parse_spectrum_file(fname))
#                 self._fnames.append(fname)
#             for specdict in specdicts:
#                 spectrum = self.data.add_spectrum(**specdict)
#                 self._added_spectra.add(spectrum)
#         dialog.destroy()
#
#     def undo(self):
#         for spectrum in self._added_spectra:
#             self.data.remove(spectrum)
#
#     def redo(self):
#         self._added_spectra.clear()
#         specdicts = []
#         for fname in self._fnames:
#             specdicts.extend(gxps.io.parse_spectrum_file(fname))
#         for specdict in specdicts:
#             spectrum = self.data.add_spectrum(**specdict)
#             self._added_spectra.add(spectrum)

"""Classes for issuing commands and managing undo/redo history."""

import logging


LOG = logging.getLogger(__name__)


class CommandSender:
    """Gets all user input and triggers the appropriate functions."""
    def __init__(self, bus, data, state, get_widget):
        self.bus = bus
        self.data = data
        self.state = state
        self.get_widget = get_widget
        self.history = History()

    def __call__(self, _object, _irr, command_name):
        pass

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

    def do_command(self, command):
        """Executes a command."""
        if command.undoable:
            self._commands_redoable.clear()
        command()
        if command.undoable:
            self._commands_done.append(command)

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

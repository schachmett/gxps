"""Provides utility classes for Observer pattern and Singleton pattern."""
# pylint: disable=logging-format-interpolation

import logging


LOGGER = logging.getLogger(__name__)


class Borg(object):
    """Alternative to Singleton pattern: all instances have the same state."""
    # pylint: disable=too-few-public-methods
    __shared_state = {}

    def __init__(self, *args, **kwargs):
        # pylint: disable=access-member-before-definition
        super().__init__(*args, **kwargs)
        print(self.__shared_state)
        print(self.__dict__)
        if not self.__shared_state:
            self.__shared_state.update(self.__dict__)
        self.__dict__ = self.__shared_state

    @classmethod
    def cleanup(cls):
        """Cleans up the object. Mainly for testing."""
        cls.__shared_state.clear()


class Observable:
    """
    Provides methods for observing these objects via callbacks.
    """
    _signals = (
        "changed",
        "changed-spectra",
        "changed-spectrum",
        "changed-metadata",
        "changed-fit",
        "changed-peak"
    )

    def __init__(self, *args, **kwargs):
        self._observers = dict((signal, []) for signal in self._signals)
        self._propagators = {}
        super().__init__(*args, **kwargs)

    def connect(self, signal, cb_func):
        """
        Registers cb_func as a callback for the specified signal. signal
        has to be in self._signals
        """
        if signal not in self._observers:
            raise ValueError("Unknown signal '{}'".format(signal))
        self._observers[signal].append(cb_func)

    def disconnect(self, signal, cb_func):
        """
        Deregisters cb_func as a callback for the specified signal.
        """
        self._observers[signal].remove(cb_func)

    def _start_propagating(self, other, signal):
        """Emit the same signal as other."""
        def re_emit(*args):
            """Re-emit the signal from self."""
            self._emit(signal, *args, source=other)
        self._propagators[(id(other), signal)] = re_emit
        other.connect(signal, re_emit)

    def _stop_propagating(self, other, signal):
        """Stop re-emitting the signal from other."""
        re_emit = self._propagators.pop((id(other), signal))
        other.disconnect(re_emit)

    def _emit(self, signal, *args, source=None):
        """Calls callbacks for signal signal."""
        if source is None:
            source = self
            LOGGER.debug("'{}' emitting signal '{}'...".format(source, signal))
        for cb_func in self._observers[signal]:
            cb_func(source, *args)

"""Spectrum class represents spectrum data."""

import numpy as np


class Observable:
    """
    Provides methods for observing these objects via callbacks.
    """
    _signals = (
        "changed",
    )
    def __init__(self, *args, **kwargs):
        self._observers = dict((signal, []) for signal in self._signals)
        super().__init__(*args, **kwargs)

    def connect(self, signal, cb_func):
        """
        Registers cb_func as a callback for the specified signal. signal
        has to be in self._signals
        """
        self._observers[signal].append(cb_func)

    def disconnect(self, signal, cb_func):
        """
        Deregisters cb_func as a callback for the specified signal.
        """
        self._observers[signal].remove(cb_func)

    def _emit(self, signal):
        """Calls callbacks for signal signal."""
        for cb_func in self._observers[signal]:
            cb_func()


class SpectrumList(Observable):
    """
    Manages a list of several spectra.
    """
    def add(self, spectrum):
        """Adds a spectrum."""

    def remove(self, spectrum):
        """Removes a spectrum."""

class Spectrum(Observable):
    """
    Holds data from one single spectrum.
    """
    _required = ("energy", "intensity")
    _bg_types = ("none", "linear", "shirley", "tougaard")
    _signals = (
        *Observable._signals,
        "changed-data",
        "changed-metadata"
    )

    def __init__(self, **kwargs):
        for attr in self._required:
            if attr not in kwargs:
                raise ValueError("Attribute '{}' missing".format(attr))
        energy = np.array(kwargs.pop("energy"))
        intensity = np.array(kwargs.pop("intensity"))
        if len(energy) != len(intensity) or energy.ndim != 1:
            raise ValueError("energy and intensity array sizes differ")
        idxes = energy.argsort()
        self._energy = energy[idxes]
        self._intensity = intensity[idxes]
        self._background = np.zeros((len(self._energy), ))
        self._background_type = "none"
        super().__init__()

    @property
    def energy(self):
        """Returns energy numpy array."""
        return self._energy

    @property
    def intensity(self):
        """Returns intensity numpy array."""
        return self._intensity

    @property
    def background(self):
        """Returns background numpy array."""
        return self._background

    @property
    def background_type(self):
        """Returns background type string."""
        return self._background_type

    @background_type.setter
    def background_type(self, value):
        """Sets background type."""
        if value not in self._bg_types:
            raise ValueError("Background type {} not valid".format(value))
        self._background_type = value
        # self._background =
        self._emit("changed-data")
        self._emit("changed")

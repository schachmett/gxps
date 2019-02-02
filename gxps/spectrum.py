"""Spectrum class represents spectrum data."""

import numpy as np

from gxps.processing import (
    calculate_background, is_equidistant, make_equidistant, make_increasing
)


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
        energy, intensity = make_increasing(energy, intensity)
        energy, intensity = make_equidistant(energy, intensity)
        self._energy = energy
        self._intensity = intensity

        self._background = np.zeros(self._energy.shape)
        self._background_type = "none"
        self._background_bounds = np.array([])

        self.filename = kwargs.pop("filename")

        super().__init__()

    @property
    def energy(self):
        """Energy numpy array."""
        return self._energy

    @property
    def intensity(self):
        """Intensity numpy array."""
        return self._intensity

    @property
    def background(self):
        """Background numpy array."""
        return self._background

    @property
    def background_type(self):
        """Background type string."""
        return self._background_type

    @background_type.setter
    def background_type(self, value):
        """Only values from self._bg_types are valid."""
        if value not in self._bg_types:
            raise ValueError("Background type {} not valid".format(value))
        self._background_type = value
        self._background = calculate_background(
            self._background_type,
            self._background_bounds,
            self.energy,
            self.intensity
        )
        self._emit("changed-data")
        self._emit("changed")

    @property
    def background_bounds(self):
        """
        Even-length numpy array with boundary values of slices where
        background will be subtracted via method defined in
        self.background_type.
        """
        return self._background_bounds

    @background_bounds.setter
    def background_bounds(self, value):
        """Only even-length numeral sequence-types are valid."""
        if len(value) % 2 != 0:
            raise ValueError("Background bounds must be pairwise.")
        for bound in value:
            if bound > self.energy.max() or bound < self.energy.min():
                raise ValueError("Background bound out of energy range.")
        self._background_bounds = np.array(value)
        self._background = calculate_background(
            self._background_type,
            self._background_bounds,
            self.energy,
            self.intensity
        )
        self._emit("changed-data")
        self._emit("changed")

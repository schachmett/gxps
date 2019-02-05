"""Spectrum class represents spectrum data."""
# pylint: disable=too-many-instance-attributes

import numpy as np

from gxps.processing import (
    calculate_background, make_equidistant, make_increasing,
    calculate_normalization_divisor
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
        self._propagators = {}
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

    def _start_propagating(self, other, signal):
        """Emit the same signal as other."""
        def re_emit(*args):
            """Re-emit the signal from self."""
            self._emit(signal, *args)
        self._propagators[(id(other), signal)] = re_emit
        other.connect(signal, re_emit)

    def _stop_propagating(self, other, signal):
        """Stop re-emitting the signal from other."""
        re_emit = self._propagators.pop((id(other), signal))
        other.disconnect(re_emit)

    def _emit(self, signal, *args):
        """Calls callbacks for signal signal."""
        for cb_func in self._observers[signal]:
            cb_func(*args)


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
    _norm_types = ("none", "manual", "highest", "high_energy", "low_energy")
    _signals = (
        *Observable._signals,
        "changed-data",
        "changed-metadata"
    )

    def __init__(self, **kwargs):
        super().__init__()
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

        self._energy_calibration = 0
        self._normalization_type = "none"
        self._normalization_divisor = 1.0

        self.meta = SpectrumMeta(**kwargs)
        self._start_propagating(self.meta, "changed-metadata")
        self.model = SpectrumModel()

    @property
    def energy(self):
        """Energy numpy array."""
        return self._energy + self._energy_calibration

    @property
    def kinetic_energy(self):
        """Kinetic energy numpy array."""

    @property
    def photon_energy(self):
        """Photon energy numpy array."""

    @property
    def intensity(self):
        """Intensity numpy array."""
        return self._intensity / self._normalization_divisor

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
            self.background_type,
            self.background_bounds,
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
        return self._background_bounds + self._energy_calibration

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
            self.background_type,
            self.background_bounds,
            self.energy,
            self.intensity
        )
        self._emit("changed-data")
        self._emit("changed")

    @property
    def energy_calibration(self):
        """Number by which the energy axis is shifted from raw to displayed."""
        return self._energy_calibration

    @energy_calibration.setter
    def energy_calibration(self, value):
        """Only numbers are valid."""
        if abs(value) == np.inf:
            raise ValueError("Invalid energy calibration value 'np.inf'.")
        self._energy_calibration = value
        self._emit("changed-data")
        self._emit("changed")

    @property
    def normalization_type(self):
        """Normalization type string."""
        return self._normalization_type

    @normalization_type.setter
    def normalization_type(self, value):
        """Normalization type has to be in self._norm_types."""
        if value not in self._norm_types:
            raise ValueError("Invalid normalization type '{}'".format(value))
        self._normalization_type = value
        old_divisor = self._normalization_divisor
        if self._normalization_type != "manual":
            self._normalization_divisor = calculate_normalization_divisor(
                self.normalization_type,
                self.normalization_divisor,
                self.energy,
                self.intensity
            )
            self._background *= old_divisor / self._normalization_divisor
        self._emit("changed-data")
        self._emit("changed")

    @property
    def normalization_divisor(self):
        """Return divisor for intensity normalization."""
        return self._normalization_divisor

    @normalization_divisor.setter
    def normalization_divisor(self, value):
        """Only numbers are valid. Sets normalization_type to manual."""
        if not abs(value) > 0:
            raise ValueError("Invalid normalization divisor '0.0'")
        self._normalization_type = "manual"
        old_divisor = self._normalization_divisor
        self._normalization_divisor = value
        self._background *= old_divisor / self._normalization_divisor


class SpectrumMeta(Observable):
    """Holds meta data of a spectrum."""
    _required = ("filename", "name")
    _defaults = {
        "notes": "",
        "spectrum_type": "unknown"
    }
    _signals = (
        *Observable._signals,
        "changed-metadata"
    )

    def __init__(self, **kwargs):
        super().__init__()
        self.kwargs = kwargs
        print(self.__dict__)
        for attr in self._required:
            if attr not in kwargs:
                raise ValueError("Attribute '{}' missing".format(attr))

        for key, value in kwargs.items():
            setattr(self, key, value)

    def __setattr__(self, attr, value):
        if attr not in "_observers":
            self._emit("changed-metadata", attr)
            self._emit("changed")
        super().__setattr__(attr, value)


class SpectrumModel(Observable):
    """
    Holds information on the Fit and provides methods for fitting.
    """
    def add(self, peak_params):
        """Add a peak with given parameters."""

    def remove(self, peak_name):
        """Add a peak specified by its name."""


class Peak(Observable):
    """
    Provides read access to peak parameters and provides methods to
    constrain them.
    """

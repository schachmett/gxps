"""Spectrum class represents spectrum data."""
# pylint: disable=too-many-instance-attributes
# pylint: disable=logging-format-interpolation

import logging
import re

import numpy as np
from lmfit import Parameters
from lmfit.models import PseudoVoigtModel

from gxps.utility import Observable, Borg
from gxps.processing import (
    calculate_background, make_equidistant, make_increasing,
    calculate_normalization_divisor
)


LOGGER = logging.getLogger(__name__)


class SpectrumContainer(Observable, Borg):
    """
    Manages a list of several spectra.
    """
    __shared_state = {}

    def __init__(self, *args, **kwargs):
        self._spectra = {}
        super().__init__(*args, **kwargs)
        LOGGER.debug("{} created".format(self))

    @property
    def spectra(self):
        """Returns spectrum objects."""
        return list(self._spectra.values())

    @property
    def spectrum_keys(self):
        """Returns list of spectrum keys."""
        return list(self._spectra.keys())

    def add_spectrum(self, **specdict):
        """Adds a spectrum."""
        if specdict["key"] in self._spectra:
            raise ValueError("Spectrum key already exists")
        spectrum = Spectrum(**specdict)
        self._spectra[spectrum.key] = spectrum
        self._start_propagating(spectrum, "changed-spectrum")
        self._start_propagating(spectrum, "changed-metadata")
        self._start_propagating(spectrum, "changed-fit")
        self._start_propagating(spectrum, "changed-peak")
        LOGGER.debug("Added spectrum {} to {}".format(spectrum, self))
        self._emit("changed-spectra")
        return spectrum

    def remove_spectrum(self, spectrum_key):
        """Removes a spectrum."""
        self._spectra.pop(spectrum_key)
        LOGGER.debug("Removed spectrum {} from {}".format(spectrum_key, self))
        self._emit("changed-spectra")

    def clear_spectra(self):
        """Clear all spectra from self."""
        self._spectra.clear()
        LOGGER.debug("Cleared container {}".format(self))
        self._emit("changed-spectra")

    def __iter__(self):
        for spectrum_key in self._spectra:
            yield spectrum_key

    def __len__(self):
        return len(self._spectra)

    def __getitem__(self, key):
        return self._spectra[key]


class Spectrum(Observable):
    """
    Holds data from one single spectrum.
    """

    _required = ("energy", "intensity", "key")
    _bg_types = ("none", "linear", "shirley", "tougaard")
    _norm_types = ("none", "manual", "highest", "high_energy", "low_energy")

    def __init__(self, **kwargs):
        super().__init__()
        if not all(a in kwargs for a in self._required):
            raise ValueError("Required attribute(s) missing")
        self._key = kwargs.pop("key")

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
        self._start_propagating(self.model, "changed-fit")
        self._start_propagating(self.model, "changed-peak")
        LOGGER.debug(
            "Spectrum '{}' created ({}, {}, {})"
            "".format(self.key, self, self.meta, self.model)
        )

    @property
    def key(self):
        """Wrapping self.meta.key."""
        return self._key

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
        LOGGER.debug("'{}' changed bg type to '{}'".format(self, value))
        self._emit("changed-spectrum")

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
        LOGGER.debug("'{}' changed bg bounds to '{}'".format(self, value))
        self._emit("changed-spectrum")

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
        LOGGER.debug("'{}' changed energy cal to '{}'".format(self, value))
        self._emit("changed-spectrum")

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
            LOGGER.debug("'{}' changed norm type to '{}'".format(self, value))
        self._emit("changed-spectrum")

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
        LOGGER.debug("'{}' changed norm divisor to '{}'".format(self, value))
        self._emit("changed-spectrum")


class SpectrumMeta(Observable):
    """Holds meta data of a spectrum."""
    _required = ("filename", "name")
    __initialized = False

    def __init__(self, **kwargs):
        self.__initialized = False

        super().__init__()
        if not all(a in kwargs for a in self._required):
            raise ValueError("Required attribute(s) missing")

        self.name = kwargs.pop("name")
        self.filename = kwargs.pop("filename")
        for key, value in kwargs.items():
            setattr(self, key, value)

        self.__initialized = True

    def __setattr__(self, attr, value):
        super().__setattr__(attr, value)
        if self.__initialized and attr != "_SpectrumMeta__initialized":
            LOGGER.debug("'{}' changed '{}' to '{}'".format(self, attr, value))
            self._emit("changed-metadata")


class SpectrumModel(Observable):
    """
    Holds information on the Fit and provides methods for fitting.
    """

    def __init__(self):
        super().__init__()
        self.params = Parameters()
        self._single_models = {}
        self._peaks = {}

    @property
    def peaks(self):
        """Returns peaks dictionary."""
        return list(self._peaks.values())

    @property
    def peak_names(self):
        """Returns list of peak names."""
        return list(self._peaks.keys())

    def get_intensity(self, energy):
        """Returns model intensity at given energy."""
        old_settings = np.seterr(under="ignore")
        intensity = self.total_model.eval(params=self.params, x=energy)
        np.seterr(**old_settings)
        return intensity

    @property
    def total_model(self):
        """Returns the sum of all models."""
        if not self.peaks:
            return None
        model_list = [peak.model for peak in self._peaks.values()]
        model_sum = model_list[0]
        for i in range(1, len(model_list)):
            model_sum += model_list[i]
        return model_sum

    def fit(self, energy, intensity):
        """Returns the fitted cps values."""
        if not self._peaks:
            return
        old_settings = np.seterr(under="ignore")    # ignore underflow error
        result = self.total_model.fit(intensity, self.params, x=energy)
        np.seterr(**old_settings)
        self.params.update(result.params)
        LOGGER.debug("'{}' fitted".format(self))
        self._emit("changed-fit")

    def add_peak(self, name, **kwargs):
        """
        Add a peak with given parameters. Valid parameters: area,
        fwhm, position and model specific parameters:
        PseudoVoigt: fraction, gausswidth
        """
        if name in self._peaks:
            raise ValueError("Peak already exists")
        peak = Peak(name, self, **kwargs)
        self._peaks[name] = peak
        self._emit("changed-fit")
        self._start_propagating(peak, "changed-peak")
        return peak

    def add_guessed(self, name):
        """Add a peak while guessing parameters."""
        raise NotImplementedError

    def remove_peak(self, name):
        """Remove a peak specified by its name."""
        peak = self._peaks[name]
        pars_to_del = [
            par for par in self.params
            if re.match(r"{}_[a-z]+".format(peak.name), par)
        ]
        self._peaks.pop(name)
        for par in pars_to_del:
            self.params.pop(par)
        self._emit("changed-fit")

    def __len__(self):
        return len(self._peaks)

    def __getitem__(self, key):
        return self._peaks[key]

    def __iter__(self):
        for peak_name in self._peaks:
            yield peak_name


class Peak(Observable):
    """
    Provides read access to peak parameters and provides methods to
    constrain them.
    """

    def __init__(self, name, smodel, area=None, fwhm=None, position=None,
                 alpha=0.2, shape="PseudoVoigt", **kwargs):
        # pylint: disable=too-many-arguments
        super().__init__()
        self.name = name
        self._smodel = smodel
        self._shape = shape
        if None in (area, fwhm, position):
            raise ValueError("Required attribute(s) missing")

        if self._shape == "PseudoVoigt":
            self._model = PseudoVoigtModel(prefix="{}_".format(name))
            self._model.set_param_hint("fraction", vary=False, value=alpha)
        else:
            raise NotImplementedError("Only PseudoVoigt shape supported")

        self.param_aliases = {
            "area": "amplitude",
            "fwhm": "fwhm",
            "center": "center",
            "fraction": "fraction"
        }
        if self._shape == "PseudoVoigt":
            self.param_aliases["alpha"] = "fraction"

        self._smodel.params += self._model.make_params()
        self._smodel.params["{}_fwhm".format(name)].set(
            value=abs(fwhm), vary=True, min=0
        )
        self._smodel.params["{}_sigma".format(name)].set(
            expr="{}_fwhm/2".format(name)
        )
        self._smodel.params["{}_amplitude".format(name)].set(
            value=abs(area), min=0
        )
        self._smodel.params["{}_center".format(name)].set(
            value=abs(position), min=0
        )
        LOGGER.debug("Peak '{}' created ({})".format(self.name, self))

    def get_intensity(self, energy):
        """Returns model intensity at given energy."""
        old_settings = np.seterr(under="ignore")
        intensity = self._model.eval(params=self._smodel.params, x=energy)
        np.seterr(**old_settings)
        return intensity

    def set_constraint(self, param, value=None, vary=None, min=None,
                       max=None, expr=None):
        """Sets a constraint for param."""
        # pylint: disable=too-many-arguments
        # pylint: disable=redefined-builtin
        paramname = "{}_{}".format(self.name, self.param_aliases[param])
        param_ = self._smodel.params[paramname]
        for arg in (value, vary, min, max):
            try:
                if arg and abs(arg) > -1:         # fail if x is not number
                    pass
            except TypeError:
                LOGGER.warning("Invalid constraint value '{}'".format(arg))
                raise TypeError("Invalid constraint value '{}'".format(arg))

        if expr:
            def name_repl(matchobj):
                """Replaces 'peakname' by 'peakname_param'"""
                name = matchobj.group(0)
                if name == self.name:
                    raise ValueError("Own name inside expression")
                if name in self._smodel.peak_names:
                    return "{}_{}".format(name, self.param_aliases[param])
                return name
            expr = re.sub(r"\b[A-Za-z][A-Za-z0-9]*", name_repl, expr)

            old_dict = {
                "value": param_.value,
                "min": param_.min,
                "max": param_.max,
                "vary": param_.vary
            }
            try:
                param_.set(expr=expr, min=-np.inf, max=np.inf)
                self._smodel.params.valuesdict()
            except (SyntaxError, NameError, TypeError):
                param_.set(expr="", **old_dict)
                self._emit("changed-peak")
                LOGGER.info("Invalid expression '{}'".format(expr))
                raise ValueError("Invalid expression '{}'".format(expr))
        elif expr == "":
            param_.set(expr="", vary=True)
        param_.set(min=min, max=max, vary=vary, value=value)
        LOGGER.debug(
            "{} set '{}' constraints min {}, max {}, vary {}, value {},"
            "expr {}".format(self, param, min, max, vary, value, expr)
        )
        self._emit("changed-peak")

    def get_constraint(self, param, constraint):
        """Returns a string containing min/max or expr."""
        paramname = "{}_{}".format(self.name, self.param_aliases[param])
        if constraint == "min":
            return self._smodel.params[paramname].min
        if constraint == "max":
            return self._smodel.params[paramname].max
        if constraint == "vary":
            return self._smodel.params[paramname].vary
        if constraint == "expr":
            def param_repl(matchobj):
                """Replaces 'peakname_param' by 'peakname'"""
                param_name = matchobj.group(0)
                name = param_name.split("_")[0]
                if name == self.name:
                    raise ValueError("Own name inside expression")
                if name in self._smodel.peak_names:
                    return name
                return param_name
            expr = self._smodel.params[paramname].expr
            return re.sub(r"\b[A-Za-z][A-Za-z0-9]*_[a-z]+", param_repl, expr)
        raise ValueError("Constraint '{}' does not exist".format(constraint))

    @property
    def model(self):
        """Returns model."""
        return self._model

    @property
    def shape(self):
        """Returns peak shape."""
        return self._shape

    @property
    def area(self):
        """Returns area value."""
        return self._smodel.params["{}_amplitude".format(self.name)].value

    @area.setter
    def area(self, value):
        """Set area value."""
        param = self._smodel.params["{}_amplitude".format(self.name)]
        param.set(value=value)
        self._emit("changed-peak")

    @property
    def fwhm(self):
        """Returns fwhm value."""
        return self._smodel.params["{}_fwhm".format(self.name)].value

    @fwhm.setter
    def fwhm(self, value):
        """Sets peak width."""
        param = self._smodel.params["{}_fwhm".format(self.name)]
        param.set(value=value)
        self._emit("changed-peak")

    @property
    def position(self):
        """Returns position value."""
        return self._smodel.params["{}_center".format(self.name)].value

    @position.setter
    def position(self, value):
        """Sets peak position."""
        param = self._smodel.params["{}_center".format(self.name)]
        param.set(value=value)
        self._emit("changed-peak")

    @property
    def alpha(self):
        """Returns model specific value 1."""
        if self._shape == "PseudoVoigt":
            return self._smodel.params["{}_fraction".format(self.name)].value
        else:
            raise AttributeError("Shape {} has no alpha".format(self._shape))

    @alpha.setter
    def alpha(self, value):
        """Sets model specific value 1."""
        if self._shape == "PseudoVoigt":
            param = self._smodel.params["{}_fraction".format(self.name)]
            param.set(value=value)
        else:
            raise AttributeError("Shape {} has no alpha".format(self._shape))
        self._emit("changed-peak")

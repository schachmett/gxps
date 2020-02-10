"""Spectrum class represents spectrum data."""
# pylint: disable=too-many-instance-attributes
# pylint: disable=logging-format-interpolation

import logging
import re
import uuid

import numpy as np
from lmfit import Parameters
from lmfit.models import PseudoVoigtModel

from gxps.utility import Observable
from gxps.processing import (
    intensity_at_energy,
    calculate_background,
    make_equidistant,
    make_increasing,
    calculate_normalization_divisor
)


LOG = logging.getLogger(__name__)


class SpectrumContainer(Observable): #, Borg):
    """Manages a list of several spectra.
    """
    _signals = (
        "changed-spectra",
        "changed-spectrum",
        "changed-metadata",
        "changed-fit",
        "changed-peak"
    )
    def __init__(self, *args, **kwargs):
        self._spectra = {}
        super().__init__(*args, **kwargs)
        LOG.debug("{} created".format(self))

    @property
    def spectra(self):
        """Returns spectrum objects."""
        return list(self._spectra.values())

    @property
    def spectrum_keys(self):
        """Returns list of spectrum keys."""
        return list(self._spectra.keys())

    def add_spectrum(self, spectrum=None, **specdict):
        """Adds a spectrum."""
        if not spectrum:
            spectrum = Spectrum(**specdict)
        if spectrum.key in self._spectra:
            spectrum.rekey()
        self._spectra[spectrum.key] = spectrum
        self._start_propagating(spectrum, "changed-spectrum")
        self._start_propagating(spectrum, "changed-metadata")
        self._start_propagating(spectrum, "changed-fit")
        self._start_propagating(spectrum, "changed-peak")
        LOG.debug("Added spectrum {} to {}".format(spectrum, self))
        self._emit("changed-spectra")
        return spectrum

    def remove_spectrum(self, spectrum):
        """Removes a spectrum."""
        self._stop_propagating_all(spectrum)
        self._spectra.pop(spectrum.key)
        LOG.debug("Removed spectrum {} from {}".format(spectrum.key, self))
        self._emit("changed-spectra")

    def clear_spectra(self):
        """Clear all spectra from self."""
        for spectrum in self._spectra:
            self._stop_propagating_all(spectrum)
        self._spectra.clear()
        LOG.debug("Cleared container {}".format(self))
        self._emit("changed-spectra")

    def __iter__(self):
        for spectrum_key in self._spectra:
            yield self._spectra[spectrum_key]

    def __len__(self):
        return len(self._spectra)

    def __getitem__(self, iter_):
        return self._spectra[self.spectrum_keys[iter_]]


class StatefulSpectrumContainer(SpectrumContainer):
    """Spectrum container that keeps subsets of spectra and peaks as
    "active", i.e. the subsets where operations should apply to.
    """
    # __shared_state = {}
    _signals = (
        *SpectrumContainer._signals,
        "changed-active-spectra",
        "changed-active-peaks",
    )
    def __init__(self, *args, **kwargs):
        super().__init__()
        self._active_spectra = []
        self._active_peaks = []
        self.connect("changed-spectra", self._update_active)

    @property
    def active_spectra(self):
        """Currently active spectra.
        """
        self.active_spectra = self._active_spectra
        return self._active_spectra.copy()

    @active_spectra.setter
    def active_spectra(self, spectra):
        """Activates given spectra.
        """
        if spectra == self._active_spectra:
            return
        for spectrum in spectra.copy():
            if spectrum not in self.spectra:
                spectra.remove(spectrum)
        self._active_spectra.clear()
        self._active_spectra.extend(spectra)
        self._emit("changed-active-spectra")

    @property
    def active_peaks(self):
        """Currently active peaks.
        """
        self.active_peaks = self._active_peaks
        return self._active_peaks.copy()

    @active_peaks.setter
    def active_peaks(self, peaks):
        """Activates given peaks.
        """
        if peaks == self._active_peaks:
            return
        for peak in peaks.copy():
            for spectrum in self.active_spectra:
                if peak in spectrum.model.peaks:
                    break
            else:
                peaks.remove(peak)
        self._active_peaks.clear()
        self._active_peaks.extend(peaks)
        self._emit("changed-active-peaks")

    def _update_active(self, *_args):
        self.active_peaks = self._active_peaks
        self.active_spectra = self._active_spectra


class Spectrum(Observable):
    """
    Holds data from one single spectrum.
    """
    _required = ("energy", "intensity")
    _bg_types = ("none", "linear", "shirley", "tougaard")
    _norm_types = ("none", "manual", "highest", "high_energy", "low_energy")

    def __init__(self, **kwargs):
        super().__init__()
        if not all(a in kwargs for a in self._required):
            raise ValueError("Required attribute(s) missing")
        self._key = None
        self.rekey()

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
        self._normalization_energy = None

        self.meta = SpectrumMeta(**kwargs)
        self._start_propagating(self.meta, "changed-metadata")
        self.model = SpectrumModel()
        self._start_propagating(self.model, "changed-fit")
        self._start_propagating(self.model, "changed-peak")
        LOG.debug(
            "Spectrum '{}' created ({}, {}, {})"
            "".format(self.key, self, self.meta, self.model)
        )

    @property
    def key(self):
        """Wrapping self.meta.key."""
        return self._key

    def rekey(self):
        """Gets a new key for self."""
        self._key = uuid.uuid1()

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
        LOG.debug("'{}' changed bg type to '{}'".format(self, value))
        self._emit("changed-spectrum", attr="background_type")

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
        self._background_bounds = np.array(sorted(list(value)))
        self._background_bounds -= self._energy_calibration
        self._background = calculate_background(
            self.background_type,
            self.background_bounds,
            self.energy,
            self.intensity
        )
        LOG.debug("'{}' changed bg bounds to '{}'".format(self, value))
        self._emit("changed-spectrum", attr="background_bounds")

    def add_background_bounds(self, emin, emax):
        """Adds one pair of background boundaries."""
        if emin > emax:
            emin, emax = emax, emin
        old_bounds = self.background_bounds
        self.background_bounds = np.append(old_bounds, [emin, emax])

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
        LOG.debug("'{}' changed energy cal to '{}'".format(self, value))
        self._emit("changed-spectrum", attr="energy_calibration")

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
                self._intensity
            )
            self._background *= old_divisor / self._normalization_divisor
            LOG.debug("'{}' changed norm type to '{}'".format(self, value))
        self._emit("changed-spectrum", attr="normalization_type")

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
        LOG.debug("'{}' changed norm divisor to '{}'".format(self, value))
        self._emit("changed-spectrum", attr="normalization_divisor")

    @property
    def normalization_energy(self):
        """Energy at which the normalization is done."""
        return self._normalization_energy

    @normalization_energy.setter
    def normalization_energy(self, value):
        """Setting this affects the divisor and type directly."""
        self.normalization_divisor = intensity_at_energy(
            self.energy,
            self._intensity,
            value
        )
        self._normalization_energy = value


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
            LOG.debug("'{}' changed '{}' to '{}'".format(self, attr, value))
            self._emit("changed-metadata", attr=attr, value=value)

    def get(self, attr):
        """Convenience method for getattr."""
        if not hasattr(self, attr):
            return None
        return getattr(self, attr)

    def set(self, attr, value):
        """Convenience method for setattr."""
        setattr(self, attr, value)


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
        LOG.debug("'{}' fitted".format(self))
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
        self._stop_propagating_all(peak)
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
        LOG.debug("Peak '{}' created ({})".format(self.name, self))

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
                LOG.warning("Invalid constraint value '{}'".format(arg))
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
                LOG.info("Invalid expression '{}'".format(expr))
                raise ValueError("Invalid expression '{}'".format(expr))
        elif expr == "":
            param_.set(expr="", vary=True)
        param_.set(min=min, max=max, vary=vary, value=value)
        LOG.debug(
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

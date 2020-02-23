"""Spectrum class represents spectrum data."""
# pylint: disable=too-many-instance-attributes
# pylint: disable=logging-format-interpolation
# pylint: disable=invalid-name

import logging
import re

import numpy as np
from lmfit import Parameters
from lmfit.models import PseudoVoigtModel, ConstantModel

from gxps.utility import Observable, MetaDataContainer
from gxps.processing import (
    IgnoreUnderflow,
    intensity_at_energy,
    calculate_background,
    make_equidistant,
    make_increasing,
    calculate_normalization_divisor,
    pah2fwhm,
    pah2area
)


LOG = logging.getLogger(__name__)


class SpectrumContainer(Observable):
    """
    Manages a list of several spectra.
    """
    _signals = ("changed-spectra", )

    def __init__(self, *args, **kwargs):
        self._spectra = []
        super().__init__(*args, **kwargs)
        LOG.info("{} created".format(self))

    @property
    def spectra(self):
        """Returns spectrum objects."""
        return self._spectra.copy()

    def add_spectrum(self, spectrum=None, **specdict):
        """Adds a spectrum."""
        if not spectrum:
            spectrum = ModeledSpectrum(**specdict)
        self._spectra.append(spectrum)
        # QODO
        spectrum.register_queue(self._queues[0])

        LOG.info("Added spectrum {} to {}".format(spectrum, self))
        self.emit("changed-spectra")
        return spectrum

    def remove_spectrum(self, spectrum):
        """Removes a spectrum."""
        LOG.info("Removing spectrum {} from {}".format(spectrum, self))
        self._spectra.remove(spectrum)
        self.emit("changed-spectra")

    def clear(self):
        """Clear all spectra from self."""
        self._spectra.clear()
        LOG.info("Cleared container {}".format(self))
        self.emit("changed-spectra")


class Spectrum(Observable, MetaDataContainer):
    """
    Holds data from one single spectrum.
    """
    _signals = ("changed-spectrum", "changed-spectrum-meta")
    _required = ("energy", "intensity", "name", "filename", "notes")
    _bg_types = ("none", "linear", "shirley", "tougaard")
    _norm_types = ("none", "highest", "high_energy", "low_energy", "manual")

    def __init__(self, **kwargs):
        if not all(a in kwargs for a in self._required):
            raise ValueError("Required attribute(s) missing")
        super().__init__()
        self._default_meta_value = ""

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

        for key, value in kwargs.items():
            self.set_meta(key, value, silent=True)

        LOG.info("Spectrum '{}' created ({})".format(self.name, self))

    def _set_meta(self, attr, value):
        """Ensure that setting meta data creates an event."""
        LOG.info("'{}' changes '{}' to '{}'".format(self, attr, value))
        self.emit("changed-spectrum-meta", attr=attr, value=value)

    @property
    def name(self):
        """Expose metadatum "name"."""
        return self.get_meta("name")

    # Energy-related
    @property
    def energy(self):
        """Energy numpy array."""
        return self._energy + self._energy_calibration

    @property
    def kinetic_energy(self):
        """Kinetic energy numpy array."""
        raise NotImplementedError

    @property
    def photon_energy(self):
        """Photon energy numpy array."""
        raise NotImplementedError

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
        LOG.info("'{}' changed energy cal to '{}'".format(self, value))
        self.emit("changed-spectrum", attr="energy_calibration")

    # Intensity-related
    @property
    def intensity(self):
        """Intensity numpy array."""
        return self._intensity / self._normalization_divisor

    def intensity_of_E(self, energy):
        """Intensity at energy."""
        return intensity_at_energy(self.energy, self.intensity, energy)

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
        if self._normalization_type != "manual":
            self._normalization_divisor = calculate_normalization_divisor(
                self.normalization_type,
                self.normalization_divisor,
                self.energy,
                self._intensity
            )
        LOG.info("'{}' changed norm type to '{}'".format(self, value))
        self.emit("changed-spectrum", attr="normalization_type")

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
        self._normalization_divisor = value
        LOG.info("'{}' changed norm divisor to '{}'".format(self, value))
        self.emit("changed-spectrum", attr="normalization_divisor")

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

    # Background-related
    @property
    def background(self):
        """Background numpy array."""
        return self._background / self._normalization_divisor

    def background_of_E(self, energy):
        """Intensity at energy."""
        return intensity_at_energy(self.energy, self.background, energy)

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
            self._intensity
        )
        LOG.info("'{}' changed bg type to '{}'".format(self, value))
        self.emit("changed-spectrum", attr="background_type")

    @property
    def background_bounds(self):
        """Even-length numpy array with boundary values of slices where
        background will be subtracted via method defined in
        self.background_type.
        """
        return self._background_bounds + self._energy_calibration

    @background_bounds.setter
    def background_bounds(self, value):
        """Only even-length numeral sequence-types are valid."""
        if len(value) % 2 != 0:
            raise ValueError("Background bounds must be pairwise.")
        if not any(value):
            self._background_bounds = np.array([])
            self.background_type = self._background_type
        for bound in value:
            if bound > self.energy.max() or bound < self.energy.min():
                raise ValueError("Background bound out of energy range.")
        self._background_bounds = np.array(sorted(list(value)))
        self._background_bounds -= self._energy_calibration
        self._background = calculate_background(
            self.background_type,
            self.background_bounds,
            self.energy,
            self._intensity
        )
        LOG.info("'{}' changed bg bounds to '{}'".format(self, value))
        self.emit("changed-spectrum", attr="background_bounds")

    def add_background_bounds(self, emin, emax):
        """Adds one pair of background boundaries."""
        if emin > emax:
            emin, emax = emax, emin
        old_bounds = self.background_bounds
        self.background_bounds = np.append(old_bounds, [emin, emax])

    def remove_background_bounds(self, emin, emax):
        """Removes one pair of background boundaries."""
        if emin > emax:
            emin, emax = emax, emin
        old_bounds = self.background_bounds.copy()
        self.background_bounds = np.setdiff1d(old_bounds, [emin, emax])


class ModeledSpectrum(Spectrum):
    """Holds information on the Fit and provides methods for fitting.
    """
    _signals = ("changed-fit", "changed-spectrum", "changed-spectrum-meta")
    _required = ("energy", "intensity", "name", "filename", "notes")
    _bg_types = ("none", "linear", "shirley", "tougaard")
    _norm_types = ("none", "manual", "highest", "high_energy", "low_energy")

    def __init__(self, *args, **kwargs):
        self.params = Parameters()
        self._peaks = []
        super().__init__(*args, **kwargs)

    @property
    def peaks(self):
        """Returns peaks."""
        return self._peaks.copy()

    @property
    def fit(self):
        """Returns fit result on whole energy range."""
        with IgnoreUnderflow():
            fit = self.model.eval(params=self.params, x=self.energy)
        return fit

    def fit_of_E(self, energy):
        """Returns model intensity at given energy."""
        energy = np.array([energy])
        with IgnoreUnderflow():
            fit = self.model.eval(params=self.params, x=energy)
        return fit

    @property
    def model(self):
        """Returns the sum of all peak models."""
        model = ConstantModel(prefix="BASE_")
        model.set_param_hint("c", vary=False, value=0)
        self.params += model.make_params()

        for peak in self._peaks:
            model += peak.model
        return model

    def do_fit(self):
        """Returns the fitted cps values."""
        with IgnoreUnderflow():
            result = self.model.fit(
                self.intensity - self.background,
                self.params,
                x=self.energy
            )
        self.params.update(result.params)
        LOG.info("'{}' fitted".format(self))
        self.emit("changed-fit")

    def add_peak(self, name, **kwargs):
        """
        Add a peak with given parameters. Valid parameters:
        area, fwhm, position and model specific parameters:
            PseudoVoigt: fraction, gausswidth
        """
        if name in [peak.name for peak in self._peaks]:
            raise ValueError("Peak already exists")
        if "fwhm" not in kwargs and "height" in kwargs and "angle" in kwargs:
            kwargs["fwhm"] = pah2fwhm(
                kwargs["position"],
                kwargs["angle"],
                kwargs["height"],
                kwargs["shape"]
                )
        if "area" not in kwargs and "height" in kwargs:
            kwargs["area"] = pah2area(
                kwargs["position"],
                kwargs["angle"],
                kwargs["height"],
                kwargs["shape"]
                )
        kwargs.pop("angle", None)
        kwargs.pop("height", None)
        peak = Peak(name, self, **kwargs)
        self._peaks.append(peak)
        peak.register_queue(self._queues[0])
        self.emit("changed-fit", attr="peaks")
        return peak

    def add_guessed(self, name):
        """Add a peak while guessing parameters."""
        raise NotImplementedError

    def remove_peak(self, peak):
        """Remove a peak specified by its name."""
        pars_to_del = [
            par for par in self.params
            if re.match(r"{}_[a-z]+".format(peak.name), par)
        ]
        self._peaks.remove(peak)
        for par in pars_to_del:
            self.params.pop(par)
        self.emit("changed-fit", attr="peaks")


class Peak(Observable):
    """
    Provides read access to peak parameters and provides methods to
    constrain them.
    """
    _signals = (
        "changed-peak",
        "changed-peak-meta"
    )
    shapes = ["PseudoVoigt", "Doniach Sunjic", "Voigt"]

    def __init__(
            self, name, spectrum,
            area=None, fwhm=None, position=None,
            shape="PseudoVoigt", alpha=0.5, beta=None
        ):
        # pylint: disable=too-many-arguments
        super().__init__()
        self.name = name
        self.spectrum = spectrum
        self.params = spectrum.params
        self._shape = shape
        self._label = "Peak {}".format(name)
        if None in (area, fwhm, position):
            raise ValueError("Required attribute(s) missing")

        if self._shape == "PseudoVoigt":
            self._model = PseudoVoigtModel(prefix="{}_".format(name))
            self._model.set_param_hint("fraction", vary=False, value=alpha)
        else:
            self._model = (beta, )
            raise NotImplementedError("Only PseudoVoigt shape supported")

        self.param_aliases = {
            "area": "amplitude",
            "fwhm": "fwhm",
            "position": "center"
        }
        if self._shape == "PseudoVoigt":
            self.param_aliases["alpha"] = "fraction"
            self.param_aliases["beta"] = None

        self.params += self._model.make_params()
        # self.params["{}_fwhm".format(name)].set(
        #     value=abs(fwhm), vary=True, min=0
        # )
        self.get_param("fwhm").set(value=abs(fwhm), vary=True, min=0)
        self.get_param("sigma").set(expr="{}_fwhm/2".format(name))
        self.get_param("amplitude").set(value=abs(area), min=0)
        self.get_param("center").set(value=abs(position), min=0)
        LOG.info("Peak '{}' created ({})".format(self.name, self))

    def get_param(self, param_name):
        """Shortcut for getting the Parameter object called
        "peak.name_param_name"
        """
        return self.params["{}_{}".format(self.name, param_name)]

    @property
    def model(self):
        """Returns model."""
        return self._model

    @property
    def label(self):
        """A label, for example denoting the core level."""
        return self._label

    @label.setter
    def label(self, value):
        """Emit a signal when changing the label."""
        self._label = value
        self.emit("changed-peak-meta", attr="label", value=value)

    @property
    def intensity(self):
        """Intensity array over whole energy range of parent spectrum."""
        with IgnoreUnderflow():
            intensity = self._model.eval(
                params=self.params,
                x=self.spectrum.energy
            )
        return intensity

    def intensity_of_E(self, energy):
        """Returns model intensity at given energy."""
        with IgnoreUnderflow():
            intensity = self._model.eval(params=self.params, x=energy)
        return intensity

    def set_constraint(
            self, param_alias,
            value=None, vary=None, min=None, max=None, expr=None
        ):
        """Sets a constraint for param. None values will unset the constraint.
        """
        # pylint: disable=too-many-arguments
        # pylint: disable=redefined-builtin
        param_name = self.param_aliases[param_alias]
        if param_name is None:
            raise ValueError(
                "{}s model '{}' does not support Parameter '{}'"
                "".format(self, self.shape, param_alias)
            )
        param = self.get_param(param_name)
        old_par = self.get_constraints(param_alias)

        for arg in (value, vary, min, max):
            try:
                if arg and abs(arg) > -1:  # fail if x is not in (None, number)
                    pass
            except TypeError:
                LOG.warning("Invalid constraint value '{}'".format(arg))
                raise TypeError("Invalid constraint value '{}'".format(arg))

        if min is None:
            min = 0
        if max is None:
            max = np.inf
        if vary is None:
            vary = value is None

        param.set(min=min, max=max, vary=vary, value=value, expr="")

        if expr is not None:
            expr = self.relation2expr(expr, param_name)
            try:
                param.set(expr=expr, min=-np.inf, max=np.inf)
                self.params.valuesdict()
            except (SyntaxError, NameError, TypeError):
                old_par["expr"] = ""
                param.set(**old_par)
                self.emit("changed-peak")
                LOG.warning("Invalid expression '{}'".format(expr))

        LOG.info("Fit parameter set to '{}'".format(param))
        self.emit("changed-peak")

    def get_constraints(self, param_alias):
        """Returns a string containing min/max or expr."""
        param_name = self.param_aliases[param_alias]
        if param_name is None:
            return None
        param = self.get_param(param_name)

        relation = ""
        if param.expr is not None:
            relation = self.expr2relation(param.expr)
        constraints = {
            "value": param.value,
            "min": param.min,
            "max": param.max,
            "vary": param.vary,
            "expr": relation
        }
        return constraints

    def expr2relation(self, expr):
        """Translates technical expr string into a human-readable relation.
        """
        def param_repl(matchobj):
            """Replaces 'peakname_param' by 'peakname'"""
            param_key = matchobj.group(0)
            name = param_key.split("_")[0]
            if self in self.spectrum.peaks:
                return name
            return param_key
        regex = r"\b[A-Za-z][A-Za-z0-9]*_[a-z]+"
        relation = re.sub(regex, param_repl, expr)
        return relation

    def relation2expr(self, relation, param_name):
        """Translates a human-readable arithmetic relation to an expr string.
        """
        def name_repl(matchobj):
            """Replaces 'peakname' by 'peakname_param' (searches
            case-insensitive).
            """
            name = matchobj.group(0)
            name = name.upper()
            if name == self.name.upper():
                raise ValueError("Self-reference in peak constraint")
            if name in [peak.name.upper() for peak in self.spectrum.peaks]:
                return "{}_{}".format(name, param_name)
            return name
        regex = r"\b[A-Za-z][A-Za-z0-9]*"
        expr = re.sub(regex, name_repl, relation)
        return expr

    @property
    def shape(self):
        """Returns peak shape."""
        return self._shape

    @shape.setter
    def shape(self, value):
        """Sets the peak shape."""
        if value == "PseudoVoigt":
            self._shape = value
        else:
            raise NotImplementedError

    @property
    def area(self):
        """Returns area value."""
        return self.params["{}_amplitude".format(self.name)].value

    @area.setter
    def area(self, value):
        """Set area value."""
        param = self.params["{}_amplitude".format(self.name)]
        param.set(value=value)
        self.emit("changed-peak")

    @property
    def fwhm(self):
        """Returns fwhm value."""
        return self.params["{}_fwhm".format(self.name)].value

    @fwhm.setter
    def fwhm(self, value):
        """Sets peak width."""
        param = self.params["{}_fwhm".format(self.name)]
        param.set(value=value)
        self.emit("changed-peak")

    @property
    def position(self):
        """Returns position value."""
        return self.params["{}_center".format(self.name)].value

    @position.setter
    def position(self, value):
        """Sets peak position."""
        param = self.params["{}_center".format(self.name)]
        param.set(value=value)
        self.emit("changed-peak")

    @property
    def alpha_name(self):
        """Gives the name of the parameter alpha."""
        if self.shape == "PseudoVoigt":
            return "Alpha"
        return None

    @property
    def alpha(self):
        """Returns model specific value 1."""
        if self._shape == "PseudoVoigt":
            return self.params["{}_fraction".format(self.name)].value
        return None

    @alpha.setter
    def alpha(self, value):
        """Sets model specific value 1."""
        if self._shape == "PseudoVoigt":
            param = self.params["{}_fraction".format(self.name)]
            param.set(value=value)
        else:
            raise AttributeError("Shape {} has no alpha".format(self._shape))
        self.emit("changed-peak")

    @property
    def beta_name(self):
        """Gives the name of the parameter alpha."""
        return None

    @property
    def beta(self):
        """Returns model specific value 2."""
        return None

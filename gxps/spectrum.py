"""Spectrum class represents spectrum data."""
# pylint: disable=too-many-instance-attributes
# pylint: disable=logging-format-interpolation
# pylint: disable=invalid-name

import logging
import re

import numpy as np
from lmfit import Parameters
from lmfit.models import ConstantModel#, PseudoVoigtModel

from gxps.utility import Observable, MetaDataContainer
from gxps.processing import (
    IgnoreUnderflow,
    intensity_at_energy,
    calculate_background,
    make_equidistant,
    make_increasing,
    calculate_normalization_divisor,
)
from gxps.models import(
    pah2fwhm,
    pah2area,
    DoniachSunjicModel,
    VoigtModel,
    PseudoVoigtModel
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
    def children(self):
        """Observable children objects."""
        return self.spectra

    @property
    def spectra(self):
        """Returns spectrum objects."""
        return self._spectra.copy()

    def add_spectrum(self, spectrum=None, **specdict):
        """Adds a spectrum."""
        if not spectrum:
            spectrum = ModeledSpectrum(**specdict)
        self._spectra.append(spectrum)

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
    bg_types = ("none", "linear", "shirley", "tougaard")
    norm_types = ("none", "highest", "high_energy", "low_energy", "manual")

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
        """Normalization type has to be in self.norm_types."""
        if self._normalization_type == value:
            return
        if value not in self.norm_types:
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
        """Only values from self.bg_types are valid."""
        if value not in self.bg_types:
            raise ValueError("Background type {} not valid".format(value))
        if self._background_type == value:
            return
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
    bg_types = ("none", "linear", "shirley", "tougaard")
    norm_types = ("none", "manual", "highest", "high_energy", "low_energy")

    def __init__(self, *args, **kwargs):
        self.params = Parameters()
        self._peaks = []
        super().__init__(*args, **kwargs)

    @property
    def children(self):
        """Observable children objects."""
        return self.peaks

    @property
    def peaks(self):
        """Returns peaks."""
        return self._peaks.copy()

    @property
    def fit(self):
        """Returns fit result on whole energy range."""
        with IgnoreUnderflow():
            fit = self.model.eval(params=self.params, x=self.energy)
        try:
            if len(fit) != len(self.energy):
                LOG.warning("Fit array has different length as energy array.")
        except TypeError:
            fit = np.zeros(self.energy.shape)
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
        self.emit("changed-fit", attr="peaks")
        return peak

    def add_guessed(self, name):
        """Add a peak while guessing parameters."""
        raise NotImplementedError

    def remove_peak(self, peak):
        """Remove a peak specified by its name."""
        # pars_to_del = [
        #     par for par in self.params
        #     if re.match(r"{}_[a-z]+".format(peak.name), par)
        # ]
        peak.clear_params()
        self._peaks.remove(peak)
        # for par in pars_to_del:
        #     self.params.pop(par)
        self.emit("changed-fit", attr="peaks")


class Peak(Observable):
    """
    Provides read access to peak parameters and provides methods to
    constrain them.
    Whereever possible, parameter "aliases" are used. Independent of
    model, every peak should have:
        area
        fwhm
        position
    and optionally:
        alpha
        beta
    in the aliases, each of these properties are mapped to "real" parameters
    in a way that they all act similar.
    This ensures a consistent API.
    """
    _signals = ("changed-peak", "changed-peak-meta")
    _default_aliases = {
        "alpha": None,
        "beta": None,
        "gamma": None
    }
    _defaults = {
        "alpha": 0.5,
        "beta": 0,
        "gamma": 0
    }
    _default_constraints = {
        "value": None,
        "vary": True,
        "min": 0,
        "max": np.inf,
        "expr": ""
    }
    shapes = ["PseudoVoigt", "DoniachSunjic", "Voigt"]

    def __init__(
            self, name, spectrum,
            area=None, fwhm=None, position=None,
            shape="PseudoVoigt", alpha=None, beta=None, gamma=None
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

        self._model = None
        self.initialize_model(area, fwhm, position, alpha, beta, gamma)
        LOG.info("Peak '{}' created ({})".format(self.name, self))

    def initialize_model(self, area, fwhm, position, alpha, beta, gamma):
        """Initialize the peak model and the parameters."""
        # pylint: disable=too-many-arguments
        self.clear_params()
        self.param_aliases = {
            "area": "amplitude",
            "fwhm": "fwhm",
            "position": "center"
        }
        if self._shape == "PseudoVoigt":
            self.param_aliases["alpha"] = "fraction"
            if alpha is None:
                alpha = 0.5
            self._model = PseudoVoigtModel(prefix="{}_".format(self.name))
            self._model.set_param_hint("fraction", min=0, value=alpha)
        elif self._shape == "DoniachSunjic":
            self.param_aliases["alpha"] = "asym"
            if alpha is None:
                alpha = 0.1
            self._model = DoniachSunjicModel(prefix="{}_".format(self.name))
            self._model.set_param_hint("asym", min=0, value=alpha)
        elif self._shape == "Voigt":
            self.param_aliases["alpha"] = "fwhm_l"
            if alpha is None:
                alpha = 0.5
            self._model = VoigtModel(prefix="{}_".format(self.name))
            self._model.set_param_hint("fwhm_l", min=0, value=alpha)
        else:
            if "" in (beta, gamma, ):
                pass #only for linter
            raise NotImplementedError("Unkown shape '{}'".format(self._shape))

        self.params += self._model.make_params()
        self.get_param("fwhm").set(value=abs(fwhm), min=0, vary=True)
        self.get_param("amplitude").set(value=abs(area), min=0, vary=True)
        self.get_param("center").set(value=abs(position), min=0, vary=True)
        # if self._shape == "PseudoVoigt":
        #     self.get_param("sigma").set(expr="{}_fwhm/2".format(self.name))

    def get_param_by_real_name(self, param_name):
        """Shortcut for getting the Parameter object called
        "peak.name_param_name"
        """
        return self.params["{}_{}".format(self.name, param_name)]

    def get_param(self, param_alias):
        """Even shorter cut for getting the Parameter object
        by the param alias.
        """
        aliases = {**self._default_aliases, **self.param_aliases}
        param_name = aliases.get(param_alias, param_alias)
        if param_name is None:
            raise ValueError(
                "{}s model '{}' does not support Parameter '{}'"
                "".format(self, self.shape, param_alias)
            )
        return self.params["{}_{}".format(self.name, param_name)]

    def clear_params(self):
        """Clear this peaks' parameters from the model."""
        pars_to_del = [
            par for par in self.params
            if re.match(r"{}_[a-z]+".format(self.name), par)
        ]
        for par in pars_to_del:
            self.params.pop(par)

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

    def set_constraints(
            self, param_alias,
            value=None, vary=None, min=0, max=np.inf, expr=""
        ):
        """Sets a constraint for param. None values will unset the constraint.
        """
        # pylint: disable=too-many-arguments
        # pylint: disable=redefined-builtin
        if vary is None:
            vary = value is None and expr == ""

        try:
            param = self.get_param(param_alias)
        except ValueError:
            LOG.debug(f"Skipped parameter {param_alias} (model {self.model})")
            return

        new = {
            "value": value, "vary": vary, "min": min, "max": max, "expr": expr
        }
        old = self.get_constraints(param_alias)

        for key, arg in new.items():
            if arg != old[key] and arg is not None:
                break
        else:
            return

        if expr == "":
            param.set(**new)
        else:
            expr = self.relation2expr(expr, param_alias)
            try:
                param.set(expr=expr, min=0, max=np.inf)
                self.params.valuesdict()
            except (SyntaxError, NameError, TypeError):
                old["expr"] = ""
                param.set(**old)
                self.emit("changed-peak")
                LOG.warning("Invalid expression '{}'".format(expr))

        LOG.info("Fit parameter set: '{}'".format(param))
        self.emit("changed-peak")

    def get_constraints(self, param_alias):
        """Returns a string containing min/max or expr."""
        try:
            param = self.get_param(param_alias)
        except ValueError:
            return self._default_constraints

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
        regex = r"\b[A-Za-z][A-Za-z0-9]*_[a-z_]+"
        relation = re.sub(regex, param_repl, expr)
        return relation

    def relation2expr(self, relation, param_alias):
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
            for peak in self.spectrum.peaks:
                if peak.name.upper() == name:
                    other = peak
                    param_name = other.param_aliases[param_alias]
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
        if self._shape == value:
            return
        fwhm = self.get_constraints("fwhm")
        area = self.get_constraints("area")
        position = self.get_constraints("position")
        alpha = self.get_constraints("alpha")
        beta = self.get_constraints("beta")
        gamma = self.get_constraints("gamma")
        # only change shape after getting constraints!
        if value in ("PseudoVoigt", "DoniachSunjic", "Voigt"):
            self._shape = value
        else:
            raise NotImplementedError

        self.initialize_model(
            area["value"], fwhm["value"], position["value"],
            alpha["value"], beta["value"], gamma["value"]
        )
        self.set_constraints("fwhm", **fwhm)
        self.set_constraints("area", **area)
        self.set_constraints("position", **position)
        self.set_constraints("alpha", **alpha)
        self.set_constraints("beta", **beta)
        self.set_constraints("gamma", **gamma)
        self.emit("changed-peak")

    def get_area(self):
        """Returns measured area under the peak."""
        return self._model.get_area(self.params)

    def get_fwhm(self):
        """Returns measured fwhm of the peak."""
        return self._model.get_fwhm(self.params)

    @property
    def alpha_name(self):
        """Gives the name of the parameter alpha."""
        if self.shape == "PseudoVoigt":
            return "Fraction"
        if self.shape == "DoniachSunjic":
            return "Asym"
        if self.shape == "Voigt":
            return "Lor. FWHM"
        return None

    @property
    def beta_name(self):
        """Gives the name of the parameter beta."""
        return None

    @property
    def gamma_name(self):
        """Gives the name of the parameter gamma."""
        return None

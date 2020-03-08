"""Provides functions for processing spectrum data."""
# pylint: disable=invalid-name
# pylint: disable=logging-format-interpolation

import logging

import numpy as np
from lmfit.model import Model
from lmfit.models import guess_from_peak, update_param_vals


LOG = logging.getLogger(__name__)

s2 = np.sqrt(2)
ln2 = 1 * np.log(2)
sqrtln2 = np.sqrt(ln2)


class IgnoreUnderflow:
    """Context manager for suppressing numpy underflow runtime errors."""
    # pylint: disable=too-few-public-methods
    def __init__(self):
        self.old_settings = {}

    def __enter__(self):
        self.old_settings = np.seterr(under="ignore")

    def __exit__(self, exc_type, exc_value, traceback):
        np.seterr(**self.old_settings)


class DoniachSunjicModel(Model):
    """x-axis reversed Doniach model (general formula taken from lmfit)."""
    # pylint: disable=dangerous-default-value
    # pylint: disable=arguments-differ
    # pylint: disable=abstract-method
    def __init__(self, **kwargs):
        kwargs["independent_vars"] = kwargs.get("independent_vars", ["x"])
        kwargs["prefix"] = kwargs.get("prefix", "")
        kwargs["nan_policy"] = kwargs.get("nan_policy", "raise")

        def realdoniach(x, amplitude=1.0, center=0, fwhm=1.0, gamma=0.0):
            """Lineshape for a x-axis reversed doniach."""
            sigma = fwhm / 2
            arg = (x-center)/sigma
            arg = -arg          # this is the reversal
            gm1 = (1.0 - gamma)
            scale = amplitude/(sigma**gm1)
            ds = (
                scale
                * np.cos(np.pi * gamma / 2 + gm1 * np.arctan(arg))
                / (1 + arg ** 2) ** (gm1 / 2)
            )
            return ds
        super().__init__(realdoniach, **kwargs)
        self._set_paramhints_prefix()

    def _set_paramhints_prefix(self):
        fmt = ("{prefix:s}amplitude/({prefix:s}fwhm/2**(1-{prefix:s}gamma))"
               "*cos(pi*{prefix:s}gamma/2)")
        self.set_param_hint('height', expr=fmt.format(prefix=self.prefix))

    def guess(self, data, x=None, negative=False, **kwargs):
        """Guess the pars."""
        pars = guess_from_peak(self, data, x, negative, ampscale=0.5)
        return update_param_vals(pars, self.prefix, **kwargs)


def calculate_background(bg_type, bg_bounds, energy, intensity):
    """Calculates a numpy array representing the background."""
    background = intensity.copy()
    if bg_type == "none":
        return np.zeros(energy.shape)
    if bg_bounds.size == 0:
        bg_bounds = [energy.min(), energy.max()]
    for lower, upper in zip(bg_bounds[0::2], bg_bounds[1::2]):
        idx1, idx2 = sorted([
            np.searchsorted(energy, lower),
            np.searchsorted(energy, upper)
        ])
        if idx1 == idx2:
            continue
        if bg_type == "shirley":
            try:
                background[idx1:idx2] = shirley(
                    energy[idx1:idx2], intensity[idx1:idx2]
                )
            except FloatingPointError:
                LOG.warning("shirley: division by zero")
        elif bg_type == "linear":
            background[idx1:idx2] = linear_bg(
                energy[idx1:idx2], intensity[idx1:idx2]
            )
        elif bg_type == "tougaard":
            raise NotImplementedError("Tougaard not implemented")
        else:
            raise ValueError("Unknown background type '{}'".format(bg_type))
    return background


def intensity_at_energy(energy, intensity, energy_value):
    """Gives back the intensity value at energy_value."""
    idx = np.searchsorted(energy, energy_value)
    return intensity[idx]


def shirley(energy, intensity, tol=1e-5, maxit=20):
    """Calculates shirley background for given x, y values."""
    if energy[-1] < energy[0]:
        raise ValueError("Energy not increasing.")
    if not is_equidistant(energy):
        raise ValueError("Energy not evenly spaced.")

    energy = energy[::-1]
    intensity = intensity[::-1]
    np.seterr(all="raise")

    background = np.ones(energy.shape) * intensity[-1]
    integral = np.zeros(energy.shape)
    spacing = (energy[-1] - energy[0]) / (len(energy) - 1)

    rest = intensity - background
    ysum = rest.sum() - np.cumsum(rest)
    integral = spacing * (ysum - 0.5 * (rest + rest[-1]))

    for _ in range(maxit):
        rest = intensity - background
        integral = spacing * (rest.sum() - np.cumsum(rest))
        bnew = (
            (intensity[0] - intensity[-1])
            * integral / integral[0]
            + intensity[-1]
        )
        if np.linalg.norm((bnew - background) / intensity[0]) < tol:
            background = bnew
            break
        else:
            background = bnew
    else:
        LOG.warning("shirley: Max iterations exceeded before convergence.")

    return background[::-1]

def linear_bg(energy, intensity):
    """Calculates linear background for given x, y values."""
    samples = len(energy)
    background = np.linspace(intensity[0], intensity[-1], samples)
    return background

def calculate_normalization_divisor(norm_type, norm_div, _energy, intensity):
    """Calculates normalization divisor."""
    new_divisor = 1.0
    if norm_type == "highest":
        new_divisor = intensity.max()
    elif norm_type == "manual":
        new_divisor = norm_div
    elif norm_type == "none":
        pass
    elif norm_type == "high_energy":
        span = intensity.max() - intensity.min()
        for i, intensity_value in enumerate(intensity[::-1]):
            if i > 0 and abs(intensity_value - intensity[-1]) > 0.05 * span:
                new_divisor = intensity[-i:].mean()
                break
        else:
            new_divisor = intensity[-1]
    elif norm_type == "low_energy":
        span = intensity.max() - intensity.min()
        for i, intensity_value in enumerate(intensity):
            if i > 0 and abs(intensity_value - intensity[0]) > 0.05 * span:
                new_divisor = intensity[:i].mean()
                break
        else:
            new_divisor = intensity[0]
    else:
        ValueError("Invalid normalization type '{}'".format(norm_type))
    return new_divisor

def pah2fwhm(_position, angle, height, shape):
    """Calculates fwhm from position, angle, height depending on shape."""
    if shape == "PseudoVoigt":
        return np.tan(angle) * height
    elif shape == "DoniachSunjic":
        return np.tan(angle) * height #TODO experimental
    raise NotImplementedError

def pah2area(_position, angle, height, shape):
    """Calculates area from position, angle, height depending on shape."""
    if shape == "PseudoVoigt":
        fwhm = np.tan(angle) * height
        area = (
            height
            * (fwhm * np.sqrt(np.pi / ln2))
            / (1 + np.sqrt(1 / (np.pi * ln2)))
        )
        return area
    elif shape == "DoniachSunjic":
        fwhm = np.tan(angle) * height
        area = (
            height
            * (fwhm * np.sqrt(np.pi / ln2))
            / (1 + np.sqrt(1 / (np.pi * ln2)))
        )
        return area #TODO experimental
    raise NotImplementedError

def is_equidistant(energy, tol=1e-08):
    """Returns True only when energy is equidistant."""
    spacings = np.unique(np.diff(energy))
    for spacing in spacings[1:]:
        if not np.isclose(spacing, spacings[0], atol=tol):
            return False
    return True

def make_increasing(energy, intensity):
    """Makes energy increasing and sorts intensity accordingly."""
    idxes = energy.argsort()
    incr_energy = energy[idxes]
    incr_intensity = intensity[idxes]
    return incr_energy, incr_intensity

def make_equidistant(energy, intensity):
    """Makes x, y pair so that x is equidistant."""
    spacings = np.unique(np.diff(energy))
    # try to eliminate spacings that are too small
    while np.isclose(0, spacings.min()):
        spacings.remove(spacings.min())
    if all([np.isclose(spacing, spacings[0]) for spacing in spacings]):
        return energy, intensity
    samples = int((energy.max() - energy.min()) / spacings.min())
    spaced_energy = np.linspace(energy.min(), energy.max(), samples)
    spaced_intensity = np.interp(spaced_energy, energy, intensity)
    return spaced_energy, spaced_intensity

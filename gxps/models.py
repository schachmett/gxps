"""Models for the peaks."""
# pylint: disable=invalid-name
# pylint: disable=logging-format-interpolation
# pylint: disable=abstract-method
# pylint: disable=too-many-arguments

import logging

import numpy as np
import scipy.special as ss
from lmfit.model import Model
from lmfit.models import guess_from_peak, update_param_vals


LOG = logging.getLogger(__name__)

s2 = np.sqrt(2)
s2pi = np.sqrt(2 * np.pi)
ln2 = 1 * np.log(2)
sln2 = np.sqrt(ln2)
s2ln2 = np.sqrt(2 * ln2)
sqrtln2 = np.sqrt(ln2)
tiny = 1e-5

# ideas for further shapes: sech2-function


def pure_ds(x, amplitude=1.0, center=0.0, fwhm=1.0, asym=0.5):
    """Roughly taken from
    https://rdrr.io/github/GSperanza/RxpsG/src/R/XPSFitAlgorithms.r
    """
    sigma = max(fwhm / 2, tiny)
    arg = center - x
    am1 = 1 - asym
    y = (
        amplitude / np.pi * ss.gamma(am1)
        / (arg**2 + sigma**2) ** (am1 / 2)
        * np.cos(np.pi * asym / 2 + am1 * np.arctan(arg / sigma))
    )
    return y

def gaussian(x, amplitude=1.0, center=0.0, fwhm=1.0):
    """Standard gaussian with amplitude = area."""
    sigma = max(tiny, fwhm / (2 * s2ln2))
    arg = center - x
    y = amplitude / (s2pi * sigma) * np.exp(-arg**2 / (2 * sigma**2))
    return y

def lorentzian(x, amplitude=1.0, center=0.0, fwhm=1.0):
    """Standard lorentzian with amplitude = area."""
    gamma = max(tiny, fwhm / 2)
    arg = center - x
    y = amplitude / (gamma * np.pi) * gamma**2 / (arg**2 + gamma**2)
    return y

def voigt(x, amplitude=1.0, center=0.0, fwhm=1.0, fwhm_l=None):
    """Voigt function using Faddeeva function wofz.
    https://en.wikipedia.org/wiki/Voigt_profile
    Taken from lmfit module, modified to take fwhms:
    Gaussian fwhm and Lorentzian fwhm_l
    """
    if fwhm_l is None:
        fwhm_l = fwhm
    sigma = max(tiny, fwhm / (2 * s2ln2))
    gamma = max(tiny, fwhm_l / 2)
    arg = center - x
    z = (arg + 1j * gamma) / (sigma * s2)
    # pylint: disable=no-member
    y = amplitude * ss.wofz(z).real / (sigma * s2pi)
    return y

def voigt_defined_fwhm(x, amplitude=1.0, center=0.0, fwhm=1.0, fwhm_g=None):
    """Voigt function using Faddeeva function wofz.
    https://en.wikipedia.org/wiki/Voigt_profile
    Taken from lmfit module, modified to take fwhms:
    Full fwhm and Gaussian fwhm (Lorentzian fwhm is inferred, see bottom
    of wikipedia link)
    """
    if fwhm_g is None:
        fwhm_g = fwhm / 1.6376
    sigma = max(tiny, fwhm_g / (2 * s2ln2))
    fwhm_l = 7.72575 * fwhm - np.sqrt(45.23566 * fwhm**2 + 14.4514 * fwhm_g**2)
    gamma = max(tiny, fwhm_l / 2)
    arg = center - x
    z = (arg + 1j * gamma) / (sigma * s2)
    # pylint: disable=no-member
    y = amplitude * ss.wofz(z).real / (sigma * s2pi)
    return y

def gl_sum(x, amplitude=1.0, center=0.0, fwhm=1.0, fraction=0.5):
    """Sum of a gaussian and a lorentzian component."""
    G = gaussian(x, amplitude=amplitude, center=center, fwhm=fwhm)
    L = lorentzian(x, amplitude=amplitude, center=center, fwhm=fwhm)
    return (1 - fraction) * G + fraction * L

def gl_prod(x, amplitude=1.0, center=0.0, fwhm=1.0, fraction=0.5):
    """Product form of a gaussian and a lorentzian component."""
    # area and fwhm are not determined - don't use!
    fwhm_g = fwhm / (1 - fraction)
    fwhm_l = fwhm / fraction
    sigma = max(tiny, fwhm_g / (2 * s2ln2))
    gamma = max(tiny, fwhm_l / 2)
    arg = center - x
    # pylint: disable=no-member
    norm_area = (
        gamma * np.exp(gamma**2 / (4 * sigma**2))
        * ss.erfc(gamma / (2 * sigma))
        / (s2pi * sigma * gamma)
    )
    amplitude /= norm_area
    GL = (
        amplitude #/ (s2pi * sigma * gamma * np.pi)
        * np.exp(-arg**2 / (2 * sigma**2) * 4 * ln2 * (1 - fraction))
        * gamma**2 / (4 * fraction) / (arg**2 + gamma**2 / (4 * fraction))
    )
    # G = gaussian(x, amplitude=amplitude, center=center, fwhm=fwhm_g)
    # L = lorentzian(x, amplitude=amplitude, center=center, fwhm=fwhm_l)
    return GL

def gelius(x, amplitude=1.0, center=0.0, fwhm=1.0, a=0.5, b=0.5, fwhm_l=0.5):
    """See http://www.casaxps.com/help_manual/line_shapes.htm
    Modified to use Voigt profile instead of GL product"""
    if fwhm_l is None:
        fwhm_l = fwhm
    arg = center - x
    below_c = (x <= center).astype(int)
    AW = np.exp(-(2 * sln2 * arg / (fwhm - a * 2 * sln2 * arg))**2)
    w = b * (0.7 + 0.3 / (a + 0.01))
    V = voigt(x, amplitude=amplitude, center=center, fwhm=fwhm, fwhm_l=fwhm_l)
    G = gaussian(x, amplitude=amplitude, center=center, fwhm=fwhm)
    y = V + below_c * (w * (AW - G))
    return y

def asymm_tail(x, center=0, fwhm=1.0, tail=1.0):
    """Tail for dampening asymmetric lines below x = center."""
    arg = (center - x) / fwhm
    try:
        zeros = np.zeros(len(x))
    except TypeError:
        zeros = 0
    y = np.exp(-np.maximum(arg, zeros) * tail)
    return y

def centered_ds(x, amplitude=1.0, center=0.0, fwhm=1.0, asym=0.5):
    """DS lineshape with maximum at center."""
    emax = fwhm / (2 * np.tan(np.pi / (2 - asym)))
    center += emax
    y = pure_ds(x, amplitude=amplitude, center=center, fwhm=fwhm, asym=asym)
    return y

def tailed_ds(x, amplitude=1.0, center=0.0, fwhm=1.0, asym=0.5, tail=1.0):
    """Centered DS with exponential tail at lower x."""
    emax = fwhm / (2 * np.tan(np.pi / (2 - asym)))
    center += emax
    ds = pure_ds(x, amplitude=amplitude, center=center, fwhm=fwhm, asym=asym)
    as_tail = asymm_tail(x, center=center, fwhm=fwhm, tail=tail)
    return ds * as_tail


class PeakModel(Model):
    """Generic model for peaks."""
    def __init__(self, func, **kwargs):
        kwargs["independent_vars"] = kwargs.get("independent_vars", ["x"])
        kwargs["prefix"] = kwargs.get("prefix", "")
        kwargs["nan_policy"] = kwargs.get("nan_policy", "raise")
        self.fwhm_res = kwargs.get("fwhm_res", 0.01)
        self.area_res = kwargs.get("area_res", 0.1)
        self.area_range = kwargs.get("area_range", 20)
        for arg in ("amplitude", "fwhm", "center"):
            if arg not in func.__code__.co_varnames:
                raise ValueError("Function has wrong parameters for PeakModel")
        super().__init__(func, **kwargs)

    def guess(self, data, **kwargs):
        """Guess the pars."""
        x = kwargs.get("x", None)
        negative = kwargs.get("negative", False)
        pars = guess_from_peak(self, data, x, negative, ampscale=0.5)
        return update_param_vals(pars, self.prefix, **kwargs)

    def get_fwhm(self, params, x=None):
        """Generic FWHM calculator:
        Searches from center in both directions for values below maximum / 2
        """
        if x:
            pass
        funcargs = self.make_funcargs(params)
        center = funcargs["center"]
        fwhm = funcargs["fwhm"]
        hm = self.func(x=center, **funcargs) / 2
        x_min, x_max = center, center
        while self.func(x=x_max, **funcargs) >= hm:
            x_max += self.fwhm_res
            if x_max > center + 5 * fwhm:
                LOG.warning("Could not calculate correct FWHM")
                break
        while self.func(x=x_min, **funcargs) >= hm:
            x_min -= self.fwhm_res
            if x_min < center - 5 * fwhm:
                LOG.warning("Could not calculate correct FWHM")
                break
        return x_max - x_min

    def get_area(self, params, x=None):
        """Generic area calculator: Integrates interval
        (center - self.area_range/2, center + self.area_range/2)
        with resolution self.area_res.
        """
        funcargs = self.make_funcargs(params)
        if x:
            start = x.min()
            end = x.max()
            N = len(x)
            res = (end - start) / N
        else:
            center = funcargs["center"]
            start = center - self.area_range / 2
            end = center + self.area_range / 2
            N = self.area_range / self.area_res
            res = self.area_res
        x = np.linspace(start, end, int(N))
        y = self.func(x=x, **funcargs)
        return sum(y) * res


class VoigtModel(PeakModel):
    """Voigt model with a defined fwhm."""
    def __init__(self, **kwargs):
        super().__init__(voigt_defined_fwhm, **kwargs)

class PseudoVoigtModel(PeakModel):
    """Standard Gaussian-Lorentzian product."""
    def __init__(self, **kwargs):
        super().__init__(gl_sum, **kwargs)

class DoniachSunjicModel(PeakModel):
    """x-axis reversed Doniach model (general formula taken from lmfit)."""
    def __init__(self, **kwargs):
        super().__init__(centered_ds, **kwargs)

class TailedDoniachSunjicModel(PeakModel):
    """DS line shape with an exponentially decaying tail on the asymmetric
    side."""
    def __init__(self, **kwargs):
        super().__init__(tailed_ds, **kwargs)



def pah2fwhm(_position, angle, height, shape):
    """Calculates fwhm from position, angle, height depending on shape."""
    if shape == "PseudoVoigt":
        return np.tan(angle) * height
    elif shape == "DoniachSunjic":
        return np.tan(angle) * height
    elif shape == "Voigt":
        return np.tan(angle) * height
    raise NotImplementedError

def pah2area(_position, angle, height, shape):
    """Calculates area from position, angle, height depending on shape."""
    if shape == "PseudoVoigt":
        fwhm = np.tan(angle) * height
        area = (height * (fwhm * np.sqrt(np.pi / ln2))
                / (1 + np.sqrt(1 / (np.pi * ln2))))
        return area
    elif shape == "DoniachSunjic":
        fwhm = np.tan(angle) * height
        area = height / pure_ds(0, amplitude=1, center=0, fwhm=fwhm, asym=0.5)
        return area
    elif shape == "Voigt":
        fwhm = np.tan(angle) * height
        area = height / voigt(0, amplitude=1, center=0, fwhm=fwhm, fwhm_l=0.5)
        return area
    raise NotImplementedError

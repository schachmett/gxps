"""Provides functions for processing spectrum data."""
# pylint: disable=invalid-name

import logging

import numpy as np


logger = logging.getLogger(__name__)


def calculate_background(bg_type, bg_bounds, energy, intensity):
    """Calculates a numpy array representing the background."""
    background = intensity.copy()
    if bg_type == "none":
        return background
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
                logger.warning("shirley: division by zero")
        elif bg_type == "linear":
            background[idx1:idx2] = linear_bg(
                energy[idx1:idx2], intensity[idx1:idx2]
            )
        elif bg_type == "tougaard":
            raise NotImplementedError("Tougaard not implemented")
        else:
            raise ValueError("Unknown background type '{}'".format(bg_type))
    return background


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
        logger.warning("shirley: Max iterations exceeded before convergence.")

    return background[::-1]

def linear_bg(energy, intensity):
    """Calculates linear background for given x, y values."""
    samples = len(energy)
    background = np.linspace(intensity[0], intensity[-1], samples)
    return background

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
    if all([np.isclose(spacing, spacings[0]) for spacing in spacings]):
        return energy, intensity
    samples = int((energy.max() - energy.min()) / spacings.min())
    spaced_energy = np.linspace(energy.min(), energy.max(), samples)
    spaced_intensity = np.interp(spaced_energy, energy, intensity)
    return spaced_energy, spaced_intensity

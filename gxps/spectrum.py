"""Spectrum class represents spectrum data."""


class SpectrumList:
    """
    Manages a list of several spectra.
    """
    pass

class Spectrum:
    """
    Holds data from one single spectrum.
    """
    def __init__(self, **kwargs):
        pass

    @property
    def energy(self):
        """Returns energy numpy array."""
        pass

    @property
    def intensity(self):
        """Returns intensity numpy array."""
        pass

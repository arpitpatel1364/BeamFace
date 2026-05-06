"""
Speaker array geometry utilities for BeamFace.

Provides functions to compute physical speaker positions for a uniform
linear array (ULA) centered at the origin.
"""

import numpy as np
from core.config import NUM_SPEAKERS, SPEAKER_SPACING


def get_speaker_positions() -> np.ndarray:
    """
    Return the x-positions (in meters) of all speakers in the linear array.

    Speakers are evenly spaced and centered at x=0. The formula positions
    speaker n at: x_n = (n - (N-1)/2) * spacing

    Returns
    -------
    np.ndarray
        Shape (NUM_SPEAKERS,), dtype float64. Each element is the
        x-coordinate of the corresponding speaker in meters.
    """
    n = np.arange(NUM_SPEAKERS, dtype=np.float64)
    positions = (n - (NUM_SPEAKERS - 1) / 2.0) * SPEAKER_SPACING
    return positions

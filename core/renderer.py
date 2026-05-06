"""
Acoustic rendering utilities for BeamFace.

Converts beamformed speaker signals into a stereo audio signal that
simulates the listener's perceived spatial sound field.
"""

import numpy as np
from core.config import SPEED_OF_SOUND, SAMPLE_RATE, NUM_SPEAKERS
from core.beamformer import apply_delay_to_signal


def propagate_to_listener(
    speaker_signals: np.ndarray,
    listener_angle_deg: float,
    speaker_positions: np.ndarray,
) -> np.ndarray:
    """
    Sum all speaker signals as perceived by a far-field listener at a given angle.

    Each speaker's signal is shifted by the propagation delay corresponding
    to the listener's angular position, then all contributions are summed.
    The result is normalized to prevent clipping.

    Parameters
    ----------
    speaker_signals : np.ndarray
        Shape (NUM_SPEAKERS, N), float32.
    listener_angle_deg : float
        Listener angle in degrees from broadside.
    speaker_positions : np.ndarray
        Speaker x-positions in meters.

    Returns
    -------
    np.ndarray
        Float32 mono array of length N.
    """
    theta_rad = np.radians(listener_angle_deg)
    delays_sec = (speaker_positions * np.sin(theta_rad)) / SPEED_OF_SOUND
    delay_samples = np.round(delays_sec * SAMPLE_RATE).astype(np.int32)

    n_samples = speaker_signals.shape[1]
    summed = np.zeros(n_samples, dtype=np.float32)

    for i in range(NUM_SPEAKERS):
        propagated = apply_delay_to_signal(speaker_signals[i], int(delay_samples[i]))
        summed += propagated

    # Normalize to prevent clipping
    peak = np.max(np.abs(summed))
    if peak > 0.0:
        summed = summed / peak

    return summed


def render_stereo(
    speaker_signals: np.ndarray,
    listener_angle_deg: float,
    speaker_positions: np.ndarray,
) -> np.ndarray:
    """
    Render a stereo output from beamformed speaker signals.

    Simulates binaural hearing by computing the left and right ear signals
    at slightly different angles (3 degrees apart), mimicking the inter-aural
    time difference that gives spatial hearing cues.

    Parameters
    ----------
    speaker_signals : np.ndarray
        Shape (NUM_SPEAKERS, N), float32.
    listener_angle_deg : float
        Central listener angle in degrees.
    speaker_positions : np.ndarray
        Speaker x-positions in meters.

    Returns
    -------
    np.ndarray
        Float32 stereo array of shape (N, 2). Column 0 = left, column 1 = right.
    """
    left = propagate_to_listener(
        speaker_signals, listener_angle_deg - 3.0, speaker_positions
    )
    right = propagate_to_listener(
        speaker_signals, listener_angle_deg + 3.0, speaker_positions
    )

    n_samples = len(left)
    stereo = np.zeros((n_samples, 2), dtype=np.float32)
    stereo[:, 0] = left
    stereo[:, 1] = right

    return stereo


def compute_rms(signal: np.ndarray) -> float:
    """
    Compute the root-mean-square amplitude of a signal.

    Parameters
    ----------
    signal : np.ndarray
        Input audio array.

    Returns
    -------
    float
        RMS value.
    """
    return float(np.sqrt(np.mean(signal.astype(np.float64) ** 2)))


def compute_rms_db(signal: np.ndarray) -> float:
    """
    Compute the RMS amplitude in decibels (dBFS).

    Parameters
    ----------
    signal : np.ndarray
        Input audio array.

    Returns
    -------
    float
        RMS in dB. Returns approximately -200 for silence.
    """
    rms = compute_rms(signal)
    return float(20.0 * np.log10(rms + 1e-10))

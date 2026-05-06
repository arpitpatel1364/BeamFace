"""
Acoustic beamforming computation engine for BeamFace.

Implements delay-and-sum beamforming for a uniform linear array (ULA).
All physics is based on far-field plane-wave propagation assumptions.
"""

import numpy as np
from core.config import SPEED_OF_SOUND, SAMPLE_RATE, NUM_SPEAKERS


def compute_delays(
    steering_angle_deg: float,
    speaker_positions: np.ndarray,
) -> np.ndarray:
    """
    Compute per-speaker time delays required to steer the beam.

    Physics: for a plane wave arriving from angle theta, the delay for
    speaker at position x_n is:
        delay_sec = (x_n * sin(theta)) / c
    where c is the speed of sound. A positive delay means the wave reaches
    that speaker later (the speaker should fire earlier to compensate).

    Parameters
    ----------
    steering_angle_deg : float
        Desired beam steering angle in degrees. 0 = broadside (forward),
        positive = right of array, negative = left.
    speaker_positions : np.ndarray
        Array of speaker x-positions in meters, shape (N,).

    Returns
    -------
    np.ndarray
        Integer delay values in samples, shape (NUM_SPEAKERS,).
        Positive = signal delayed (fireed late relative to center).
    """
    theta_rad = np.radians(steering_angle_deg)
    # Propagation delay: time for wavefront to travel across the array
    delay_sec = (speaker_positions * np.sin(theta_rad)) / SPEED_OF_SOUND
    delay_samples = np.round(delay_sec * SAMPLE_RATE).astype(np.int32)
    return delay_samples


def apply_delay_to_signal(signal: np.ndarray, delay_samples: int) -> np.ndarray:
    """
    Shift a signal by a given number of samples using zero-padding.

    Positive delay: pads zeros at the start, trims the tail.
    Negative delay: pads zeros at the end, trims the head.
    Never uses np.roll (which wraps around rather than padding with silence).

    Parameters
    ----------
    signal : np.ndarray
        Input mono audio signal, float32.
    delay_samples : int
        Number of samples to shift. Positive = delay, negative = advance.

    Returns
    -------
    np.ndarray
        Float32 array of the same length as the input signal.
    """
    n = len(signal)
    signal = signal.astype(np.float32)

    if delay_samples == 0:
        return signal.copy()

    if delay_samples > 0:
        # Insert silence at the front, discard samples from the tail
        pad = np.zeros(delay_samples, dtype=np.float32)
        delayed = np.concatenate([pad, signal])
        return delayed[:n]
    else:
        # Advance the signal: discard samples from the front, pad the tail
        advance = -delay_samples
        pad = np.zeros(advance, dtype=np.float32)
        advanced = np.concatenate([signal[advance:], pad])
        return advanced[:n]


def apply_beamforming(
    signal: np.ndarray,
    steering_angle_deg: float,
    speaker_positions: np.ndarray,
) -> np.ndarray:
    """
    Apply delay-and-sum beamforming to produce per-speaker output signals.

    Processing pipeline:
      1. Compute per-speaker time delays based on steering angle.
         This implements phase coherence: when summed at a distant listener
         in the steering direction, all speaker contributions arrive in phase.
      2. Apply a Hanning window across the aperture (amplitude taper).
         This reduces sidelobes in the beam pattern at the cost of slightly
         widening the main lobe. The Hanning weights smoothly roll off
         toward the array edges.
      3. Each speaker signal is the input delayed by its steering delay
         and scaled by its aperture weight.

    Parameters
    ----------
    signal : np.ndarray
        Mono source audio block, float32.
    steering_angle_deg : float
        Beam steering angle in degrees.
    speaker_positions : np.ndarray
        Array of speaker x-positions in meters.

    Returns
    -------
    np.ndarray
        Float32 array of shape (NUM_SPEAKERS, len(signal)).
        Row i contains the signal to be fed to speaker i.
    """
    delays = compute_delays(steering_angle_deg, speaker_positions)

    # Hanning window provides aperture amplitude taper.
    # Reduces grating lobes and suppresses spatial aliasing.
    weights = np.hanning(NUM_SPEAKERS).astype(np.float32)

    n_samples = len(signal)
    speaker_signals = np.zeros((NUM_SPEAKERS, n_samples), dtype=np.float32)

    for i in range(NUM_SPEAKERS):
        # Apply time delay: each speaker fires early or late so that
        # signals converge at the target angle in the far field.
        delayed = apply_delay_to_signal(signal, int(delays[i]))
        # Apply aperture taper: controls the spatial frequency content
        # of the array and shapes the beam directivity pattern.
        speaker_signals[i] = delayed * weights[i]

    return speaker_signals


def compute_pattern_db(
    speaker_signals: np.ndarray,
    speaker_positions: np.ndarray,
    angle_range: tuple = (-90, 90),
    resolution: int = 1,
):
    """
    Compute the far-field beam pattern in dB by sweeping listener angles.

    For each candidate listener angle, propagation delays from all speakers
    are computed. Each speaker signal is shifted to simulate arrival at
    that listener position, then summed. The RMS of the summed signal gives
    the effective response. The pattern is normalized so the peak is 0 dB.

    Parameters
    ----------
    speaker_signals : np.ndarray
        Shape (NUM_SPEAKERS, N), float32. Per-speaker output signals.
    speaker_positions : np.ndarray
        Speaker x-positions in meters.
    angle_range : tuple
        (min_angle, max_angle) in degrees.
    resolution : int
        Angular resolution in degrees.

    Returns
    -------
    tuple[np.ndarray, np.ndarray]
        (angles_deg, db_values) both normalized to peak = 0 dB.
    """
    angles = np.arange(angle_range[0], angle_range[1] + resolution, resolution)
    rms_values = np.zeros(len(angles), dtype=np.float64)

    for idx, angle in enumerate(angles):
        # Propagation delay from each speaker to a far-field listener at 'angle'
        theta_rad = np.radians(angle)
        delays_sec = (speaker_positions * np.sin(theta_rad)) / SPEED_OF_SOUND
        delay_samples = np.round(delays_sec * SAMPLE_RATE).astype(np.int32)

        summed = np.zeros(speaker_signals.shape[1], dtype=np.float32)
        for i in range(NUM_SPEAKERS):
            propagated = apply_delay_to_signal(
                speaker_signals[i], int(delay_samples[i])
            )
            summed += propagated

        # RMS gives the effective acoustic pressure amplitude
        rms = np.sqrt(np.mean(summed ** 2))
        rms_values[idx] = rms

    # Convert to dB scale
    db_values = 20.0 * np.log10(rms_values + 1e-10)

    # Normalize so maximum is 0 dB
    db_peak = np.max(db_values)
    db_values = db_values - db_peak

    return angles, db_values

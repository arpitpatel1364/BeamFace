"""
Audio source generation and loading utilities for BeamFace.

Provides functions to synthesize test tones, load WAV files,
and extract looping blocks for real-time processing.
"""

import numpy as np
from scipy.io import wavfile
from core.config import SAMPLE_RATE, DEFAULT_FREQUENCY, DEFAULT_DURATION


def generate_sine_tone(
    frequency: float = DEFAULT_FREQUENCY,
    duration: float = DEFAULT_DURATION,
    sample_rate: int = SAMPLE_RATE,
) -> np.ndarray:
    """
    Generate a normalized mono sine tone as a float32 array.

    Parameters
    ----------
    frequency : float
        Tone frequency in Hz.
    duration : float
        Duration in seconds.
    sample_rate : int
        Sample rate in Hz.

    Returns
    -------
    np.ndarray
        Float32 array normalized to [-1.0, 1.0].
    """
    num_samples = int(duration * sample_rate)
    t = np.linspace(0.0, duration, num_samples, endpoint=False)
    signal = np.sin(2.0 * np.pi * frequency * t)
    return signal.astype(np.float32)


def load_wav(filepath: str):
    """
    Load a WAV file, convert to mono float32, and normalize.

    Parameters
    ----------
    filepath : str
        Path to the WAV file on disk.

    Returns
    -------
    tuple[np.ndarray, int]
        (signal, sample_rate) where signal is float32 mono, normalized.

    Raises
    ------
    FileNotFoundError
        If the specified file does not exist.
    """
    import os
    if not os.path.isfile(filepath):
        raise FileNotFoundError(
            f"Audio file not found: {filepath}. "
            "Please provide a valid WAV file path."
        )
    rate, data = wavfile.read(filepath)

    # Convert to float32
    if data.dtype == np.int16:
        data = data.astype(np.float32) / 32768.0
    elif data.dtype == np.int32:
        data = data.astype(np.float32) / 2147483648.0
    elif data.dtype == np.uint8:
        data = (data.astype(np.float32) - 128.0) / 128.0
    else:
        data = data.astype(np.float32)

    # Collapse to mono if stereo
    if data.ndim == 2:
        data = data.mean(axis=1)

    # Normalize to [-1, 1]
    peak = np.max(np.abs(data))
    if peak > 0.0:
        data = data / peak

    return data, rate


def get_looping_block(
    source_signal: np.ndarray,
    block_index: int,
    block_size: int,
) -> np.ndarray:
    """
    Extract a block from the source signal using modulo for seamless looping.

    Parameters
    ----------
    source_signal : np.ndarray
        The full source audio signal.
    block_index : int
        Index of the block to extract (zero-based).
    block_size : int
        Number of samples per block.

    Returns
    -------
    np.ndarray
        Float32 array of length block_size.
    """
    total = len(source_signal)
    start = (block_index * block_size) % total
    end = start + block_size

    if end <= total:
        block = source_signal[start:end].copy()
    else:
        # Wrap around: concatenate tail and head
        tail = source_signal[start:total]
        head = source_signal[: end - total]
        block = np.concatenate([tail, head])

    return block.astype(np.float32)

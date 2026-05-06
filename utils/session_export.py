"""
Session data export utilities for BeamFace.

Provides functions to save the beam pattern plot as PNG and to export
the session log as a CSV file. All files are written to the configured
output directory with auto-generated timestamped filenames.
"""

import csv
import logging
import os
from datetime import datetime
from typing import List

from core.config import OUTPUT_DIR

logger = logging.getLogger("beamface.session_export")

_TIMESTAMP_FMT = "%Y%m%d_%H%M%S"

_CSV_FIELDNAMES = [
    "timestamp",
    "face_detected",
    "raw_angle",
    "smoothed_angle",
    "beam_angle",
    "target_angle",
    "rms_db",
]


def _ensure_output_dir():
    """Create the output directory if it does not exist."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def export_beam_pattern_png(figure, filename: str = None) -> str:
    """
    Save a matplotlib Figure to a PNG file in the output directory.

    Parameters
    ----------
    figure : matplotlib.figure.Figure
        The figure object to save.
    filename : str or None
        Destination filename (basename only, no path). If None, a timestamped
        name is generated automatically.

    Returns
    -------
    str
        Absolute path to the saved PNG file.
    """
    _ensure_output_dir()

    if filename is None:
        ts = datetime.now().strftime(_TIMESTAMP_FMT)
        filename = f"beam_pattern_{ts}.png"

    path = os.path.join(OUTPUT_DIR, filename)
    figure.savefig(path, dpi=150, bbox_inches="tight", facecolor=figure.get_facecolor())
    logger.info("Beam pattern saved to: %s", path)
    return os.path.abspath(path)


def export_session_csv(rows: List[dict], filename: str = None) -> str:
    """
    Save session tracking data to a CSV file in the output directory.

    Parameters
    ----------
    rows : list[dict]
        List of dicts with keys matching _CSV_FIELDNAMES.
    filename : str or None
        Destination filename (basename only). Auto-generated if None.

    Returns
    -------
    str
        Absolute path to the saved CSV file.
    """
    _ensure_output_dir()

    if filename is None:
        ts = datetime.now().strftime(_TIMESTAMP_FMT)
        filename = f"session_{ts}.csv"

    path = os.path.join(OUTPUT_DIR, filename)

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_CSV_FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    logger.info("Session CSV saved to: %s (%d rows)", path, len(rows))
    return os.path.abspath(path)

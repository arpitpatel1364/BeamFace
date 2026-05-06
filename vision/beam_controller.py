"""
Thread-safe beam steering controller for BeamFace.

Bridges face detection results to the beamformer by maintaining a smoothed,
interpolated steering angle that all threads can safely read and write.
"""

import threading
import logging

import numpy as np

from core.config import SMOOTHING_FACTOR, MAX_ANGLE_HISTORY
from vision.face_detector import FaceData

logger = logging.getLogger("beamface.beam_controller")


class BeamController:
    """
    Thread-safe controller for beam angle state.

    Maintains the current steering angle with exponential smoothing and
    a rolling weighted average to reduce noise from face detection jitter.
    All public methods are safe to call from any thread.
    """

    def __init__(self):
        """Initialize the BeamController with default angle state."""
        self._lock = threading.RLock()
        self._current_angle = 0.0
        self._target_angle = 0.0
        self._smoothing = SMOOTHING_FACTOR
        self._angle_history = []
        self.face_detected = False
        self.current_rms_db = -60.0

    def update_from_face(self, face_data: FaceData):
        """
        Update the target angle based on face detection results.

        If a face is detected, applies rolling-average smoothing to the raw
        angle and sets it as the new target. If no face, returns to 0 degrees.

        Parameters
        ----------
        face_data : FaceData
            Detection result from FaceDetector.get_face_data().
        """
        if face_data.detected:
            smoothed = self._smooth(face_data.angle_deg)
            self.set_target(smoothed)
            self.face_detected = True
        else:
            self.set_target(0.0)
            self.face_detected = False

    def _smooth(self, angle: float) -> float:
        """
        Apply a weighted rolling average to reduce face angle jitter.

        More recent values receive higher weights [1, 2, 3, 4, 5] (trimmed
        to the available history length). This gives a smooth trajectory
        without the lag of a simple moving average.

        Parameters
        ----------
        angle : float
            Raw detected angle in degrees.

        Returns
        -------
        float
            Smoothed angle in degrees.
        """
        with self._lock:
            self._angle_history.append(angle)
            if len(self._angle_history) > MAX_ANGLE_HISTORY:
                self._angle_history = self._angle_history[-MAX_ANGLE_HISTORY:]

            history_len = len(self._angle_history)
            weights = np.arange(1, MAX_ANGLE_HISTORY + 1, dtype=np.float32)
            weights = weights[-history_len:]
            weighted_avg = float(
                np.average(self._angle_history, weights=weights)
            )
            return weighted_avg

    def set_target(self, angle_deg: float):
        """
        Set the beam target angle, clamped to the valid steering range.

        Parameters
        ----------
        angle_deg : float
            Desired target angle in degrees.
        """
        with self._lock:
            self._target_angle = float(np.clip(angle_deg, -80.0, 80.0))

    def lerp_step(self):
        """
        Advance the current angle toward the target using linear interpolation.

        The smoothing factor controls how quickly the beam tracks the target.
        When the difference is below the threshold, snap to avoid floating point
        oscillation at convergence.
        """
        with self._lock:
            diff = self._target_angle - self._current_angle
            self._current_angle += self._smoothing * diff
            if abs(diff) < 0.05:
                self._current_angle = self._target_angle

    def get_current_angle(self) -> float:
        """Return the current (smoothed/lerped) beam steering angle in degrees."""
        with self._lock:
            return self._current_angle

    def get_target_angle(self) -> float:
        """Return the target beam steering angle in degrees."""
        with self._lock:
            return self._target_angle

    def set_smoothing(self, value: float):
        """
        Set the lerp smoothing coefficient.

        Parameters
        ----------
        value : float
            Smoothing factor clamped to [0.01, 1.0]. Higher = faster tracking.
        """
        with self._lock:
            self._smoothing = float(np.clip(value, 0.01, 1.0))

    def get_status(self) -> dict:
        """
        Return a snapshot of the controller's current state.

        Returns
        -------
        dict
            Keys: current_angle, target_angle, smoothing,
                  face_detected, current_rms_db.
        """
        with self._lock:
            return {
                "current_angle": self._current_angle,
                "target_angle": self._target_angle,
                "smoothing": self._smoothing,
                "face_detected": self.face_detected,
                "current_rms_db": self.current_rms_db,
            }

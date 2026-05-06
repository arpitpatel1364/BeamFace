"""
Face detection and camera interface for BeamFace.

Provides a unified face detection interface using MediaPipe as the primary
detector with Haar cascade as a fallback. Also computes the angular position
and estimated distance of the detected face.
"""

import logging
from dataclasses import dataclass, field

import cv2
import numpy as np

from core.config import (
    CAMERA_FOV_DEG,
    FACE_REAL_WIDTH_CM,
    DEFAULT_FOCAL_LENGTH,
)

logger = logging.getLogger("beamface.face_detector")


@dataclass
class FaceData:
    """
    Container for per-frame face detection results.

    Attributes
    ----------
    detected : bool
        Whether a face was found in this frame.
    bbox : tuple
        Bounding box as (x, y, w, h) in pixels.
    center : tuple
        Face center as (cx, cy) in pixels.
    angle_deg : float
        Horizontal angle of the face relative to camera center, in degrees.
    distance_cm : float
        Estimated distance from camera in centimeters.
    """
    detected: bool
    bbox: tuple = (0, 0, 0, 0)
    center: tuple = (0, 0)
    angle_deg: float = 0.0
    distance_cm: float = 999.0


class FaceDetector:
    """
    Manages camera capture and face detection with MediaPipe + Haar fallback.

    Uses MediaPipe face detection as the primary method due to its superior
    accuracy and speed. Falls back to OpenCV Haar cascades when MediaPipe
    is unavailable or produces no detections.
    """

    def __init__(self, camera_index: int = 0):
        """Initialize FaceDetector targeting the given camera device index."""
        self.camera_index = camera_index
        self.cap = None
        self.haar = None
        self.mp_detector = None
        self.frame_width = 640
        self.frame_height = 480
        self._mp_available = False

    def initialize(self):
        """
        Open the camera, warm it up, and load detection models.

        Raises
        ------
        RuntimeError
            If the camera cannot be opened.
        """
        self.cap = cv2.VideoCapture(self.camera_index)
        if not self.cap.isOpened():
            raise RuntimeError(
                f"Failed to open camera at index {self.camera_index}. "
                "Check that a webcam is connected and not in use by another process."
            )

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.frame_width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.frame_height)

        # Warm up the camera: discard initial frames which may be underexposed
        for _ in range(10):
            self.cap.read()

        # Load Haar cascade as fallback detector
        haar_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        self.haar = cv2.CascadeClassifier(haar_path)
        if self.haar.empty():
            logger.warning("Haar cascade failed to load from %s", haar_path)

        # Attempt to load MediaPipe
        try:
            import mediapipe as mp
            self.mp_detector = mp.solutions.face_detection.FaceDetection(
                model_selection=0,
                min_detection_confidence=0.6,
            )
            self._mp_available = True
            logger.info("MediaPipe face detector initialized")
        except Exception as exc:
            logger.warning(
                "MediaPipe not available, using Haar only: %s", exc
            )
            self._mp_available = False

        logger.info(
            "Camera opened at index %d (%dx%d)",
            self.camera_index,
            self.frame_width,
            self.frame_height,
        )

    def read_frame(self):
        """
        Read one frame from the camera.

        Returns
        -------
        np.ndarray or None
            BGR frame, or None if capture failed.
        """
        if self.cap is None:
            return None
        ret, frame = self.cap.read()
        if not ret:
            return None
        return frame

    def detect_faces(self, frame: np.ndarray):
        """
        Detect faces in a BGR frame.

        Tries MediaPipe first; falls back to Haar cascade if no result.

        Parameters
        ----------
        frame : np.ndarray
            BGR image from the camera.

        Returns
        -------
        list[tuple]
            List of (x, y, w, h) bounding boxes in pixels.
        """
        faces = []

        if self._mp_available and self.mp_detector is not None:
            try:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                result = self.mp_detector.process(rgb)
                if result.detections:
                    h, w = frame.shape[:2]
                    for det in result.detections:
                        bb = det.location_data.relative_bounding_box
                        x = int(bb.xmin * w)
                        y = int(bb.ymin * h)
                        bw = int(bb.width * w)
                        bh = int(bb.height * h)
                        # Clamp to frame boundaries
                        x = max(0, x)
                        y = max(0, y)
                        bw = min(bw, w - x)
                        bh = min(bh, h - y)
                        faces.append((x, y, bw, bh))
                    return faces
            except Exception as exc:
                logger.debug("MediaPipe detection error, falling back: %s", exc)

        # Haar fallback
        if self.haar and not self.haar.empty():
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            detections = self.haar.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(60, 60),
            )
            if len(detections) > 0:
                for (x, y, w, h) in detections:
                    faces.append((int(x), int(y), int(w), int(h)))

        return faces

    def pixel_to_angle(self, pixel_x: float) -> float:
        """
        Convert a horizontal pixel position to a steering angle in degrees.

        Maps the pixel coordinate to [-FOV/2, FOV/2] degrees, with 0 at center.

        Parameters
        ----------
        pixel_x : float
            Horizontal pixel coordinate.

        Returns
        -------
        float
            Angle in degrees, clamped to [-80, 80].
        """
        normalized = (pixel_x - self.frame_width / 2.0) / (self.frame_width / 2.0)
        angle = normalized * (CAMERA_FOV_DEG / 2.0)
        return float(np.clip(angle, -80.0, 80.0))

    def estimate_distance(self, face_width_px: float) -> float:
        """
        Estimate face distance from camera using the pinhole camera model.

        Formula: distance = (real_width * focal_length) / pixel_width

        Parameters
        ----------
        face_width_px : float
            Width of the detected face bounding box in pixels.

        Returns
        -------
        float
            Estimated distance in centimeters. Returns 999.0 if invalid.
        """
        if face_width_px == 0:
            return 999.0
        return (FACE_REAL_WIDTH_CM * DEFAULT_FOCAL_LENGTH) / face_width_px

    def get_face_data(self, frame: np.ndarray) -> FaceData:
        """
        Run detection on a frame and return structured face data.

        Selects the largest detected face (by bounding box area) as the
        primary tracking target.

        Parameters
        ----------
        frame : np.ndarray
            BGR camera frame.

        Returns
        -------
        FaceData
            Detected=False if no faces found, otherwise populated with
            bbox, center, angle and distance.
        """
        faces = self.detect_faces(frame)
        if not faces:
            return FaceData(detected=False)

        # Select the face with the largest bounding box area
        largest = max(faces, key=lambda f: f[2] * f[3])
        x, y, w, h = largest

        center_x = x + w / 2.0
        center_y = y + h / 2.0
        angle = self.pixel_to_angle(center_x)
        distance = self.estimate_distance(w)

        return FaceData(
            detected=True,
            bbox=(x, y, w, h),
            center=(int(center_x), int(center_y)),
            angle_deg=angle,
            distance_cm=distance,
        )

    def release(self):
        """Release the camera resource."""
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        if self._mp_available and self.mp_detector is not None:
            self.mp_detector.close()
        logger.info("Camera released")

"""
Live camera feed panel with face detection overlay for BeamFace.

Reads frames from FaceDetector, draws detection overlays, updates
the BeamController, and emits signals for the rest of the UI.
"""

import logging

import time

import cv2
import numpy as np
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import QLabel, QVBoxLayout, QWidget

from ui.theme import (
    ACCENT_COLOR,
    BORDER_COLOR,
    DANGER_COLOR,
)

logger = logging.getLogger("beamface.camera_panel")

# Drawing constants (derived from theme hex values as BGR tuples)
_COLOR_ACCENT = (255, 170, 0)       # ACCENT_COLOR in BGR
_COLOR_FACE_BOX = (255, 170, 0)     # face bounding box
_COLOR_FACE_CENTER = (255, 170, 0)  # center dot
_COLOR_NO_FACE = (51, 51, 255)      # "NO FACE DETECTED" text in BGR
_COLOR_WHITE = (255, 255, 255)
_COLOR_CROSSHAIR = (60, 60, 60)
_COLOR_BEAM_LINE = (0, 170, 255)    # beam angle line BGR = ACCENT_COLOR (#00aaff)
_COLOR_TRACKING_LINE = (0, 170, 255)
_FRAME_RATE_MS = 33                 # ~30fps timer interval


class VideoWorker(QThread):
    """
    Worker thread to read camera frames and run face detection off the main UI thread.
    Emits frame_processed(frame, face_data) when a frame is ready.
    """
    frame_processed = pyqtSignal(object, object)

    def __init__(self, face_detector):
        super().__init__()
        self.face_detector = face_detector
        self._running = True

    def run(self):
        while self._running:
            start_time = time.time()
            
            frame = self.face_detector.read_frame()
            if frame is not None:
                face_data = self.face_detector.get_face_data(frame)
                self.frame_processed.emit(frame, face_data)
                
            elapsed = time.time() - start_time
            sleep_time = max(0, (_FRAME_RATE_MS / 1000.0) - elapsed)
            time.sleep(sleep_time)

    def stop(self):
        self._running = False
        self.wait()


class CameraPanel(QWidget):
    """
    Widget displaying the live camera feed with face-tracking overlays.

    Reads frames at ~30fps via QTimer, runs face detection, updates the
    BeamController, draws annotations, and emits frame_updated signals
    for downstream UI components.
    """

    frame_updated = pyqtSignal(object, dict)

    def __init__(self, face_detector, beam_controller, parent=None):
        """Initialize the CameraPanel with detector and controller references."""
        super().__init__(parent)
        self.face_detector = face_detector
        self.beam_controller = beam_controller
        self._face_detected = False

        self._build_ui()

        self._worker = VideoWorker(self.face_detector)
        self._worker.frame_processed.connect(self.update_frame)
        self._worker.start()

    def _build_ui(self):
        """Create and arrange the video display label."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.video_label = QLabel(self)
        self.video_label.setFixedSize(640, 480)
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setStyleSheet(
            f"border: 2px solid {BORDER_COLOR}; background-color: #000000;"
        )
        layout.addWidget(self.video_label)

    def update_frame(self, frame, face_data):
        """
        Receive processed frame and face_data from the worker thread.
        Update controller, draw overlays, and emit frame_updated signal.
        """
        self.beam_controller.update_from_face(face_data)
        self.beam_controller.lerp_step()

        self._draw_overlays(frame, face_data)
        self._update_border(face_data.detected)
        self._display_frame(frame)

        status = self.beam_controller.get_status()
        self.frame_updated.emit(face_data, status)

    def _draw_overlays(self, frame: np.ndarray, face_data):
        """Draw all detection and beam annotations onto the frame in-place."""
        h, w = frame.shape[:2]
        cx_frame = w // 2
        cy_frame = h // 2

        # Crosshair at frame center
        cv2.line(frame, (cx_frame - 15, cy_frame), (cx_frame + 15, cy_frame), _COLOR_CROSSHAIR, 1)
        cv2.line(frame, (cx_frame, cy_frame - 15), (cx_frame, cy_frame + 15), _COLOR_CROSSHAIR, 1)

        if face_data.detected:
            x, y, bw, bh = face_data.bbox
            cx, cy = face_data.center

            # Bounding box
            cv2.rectangle(frame, (x, y), (x + bw, y + bh), _COLOR_FACE_BOX, 2)

            # Center dot
            cv2.circle(frame, (cx, cy), 4, _COLOR_FACE_CENTER, -1)

            # Angle label above box
            angle_text = f"Angle: {face_data.angle_deg:.1f} deg"
            cv2.putText(
                frame, angle_text,
                (x, max(y - 8, 14)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, _COLOR_WHITE, 1, cv2.LINE_AA,
            )

            # Distance label below box
            dist_text = f"Dist: {face_data.distance_cm:.0f} cm"
            cv2.putText(
                frame, dist_text,
                (x, min(y + bh + 18, h - 4)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, _COLOR_WHITE, 1, cv2.LINE_AA,
            )

            # Horizontal line from frame center to face center
            cv2.line(frame, (cx_frame, cy), (cx, cy), _COLOR_TRACKING_LINE, 1)

            # Beam angle indicator (bottom-left)
            beam_angle = self.beam_controller.get_current_angle()
            beam_text = f"Beam: {beam_angle:.1f} deg"
            cv2.putText(
                frame, beam_text,
                (8, h - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, _COLOR_BEAM_LINE, 1, cv2.LINE_AA,
            )
        else:
            # No face indicator
            cv2.putText(
                frame, "NO FACE DETECTED",
                (w // 2 - 100, h // 2 + 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, _COLOR_NO_FACE, 1, cv2.LINE_AA,
            )

            beam_angle = self.beam_controller.get_current_angle()
            beam_text = f"Beam: {beam_angle:.1f} deg"
            cv2.putText(
                frame, beam_text,
                (8, h - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, _COLOR_BEAM_LINE, 1, cv2.LINE_AA,
            )

    def _update_border(self, detected: bool):
        """Update the border color of the video label based on detection state."""
        if detected != self._face_detected:
            self._face_detected = detected
            border_hex = ACCENT_COLOR if detected else BORDER_COLOR
            self.video_label.setStyleSheet(
                f"border: 2px solid {border_hex}; background-color: #000000;"
            )

    def _display_frame(self, frame: np.ndarray):
        """Convert a BGR frame to QImage and update the display label."""
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        bytes_per_line = ch * w
        # Must use bytes(rgb.data) or rgb.tobytes() so the QImage owns a
        # copy of the pixel data; passing rgb.data directly gives QImage a
        # raw pointer that becomes dangling once numpy GC's the array.
        qimg = QImage(rgb.tobytes(), w, h, bytes_per_line, QImage.Format_RGB888)
        self.video_label.setPixmap(QPixmap.fromImage(qimg))

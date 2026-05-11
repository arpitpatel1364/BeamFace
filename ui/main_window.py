"""
Main application window for BeamFace.

Assembles all panels into the full application layout, manages the component
lifecycle (camera, audio engine, beam controller), and wires all inter-panel
signals. This module owns the top-level QMainWindow.
"""

import logging
import time
import traceback

import numpy as np
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from core.array_geometry import get_speaker_positions
from core.audio_engine import AudioEngine
from core.beamformer import apply_beamforming, compute_pattern_db
from core.audio_source import generate_sine_tone
from core.config import (
    APP_NAME,
    APP_VERSION,
    DEFAULT_FREQUENCY,
    SAMPLE_RATE,
)
from utils.logger import setup_logger
from utils.session_export import export_beam_pattern_png, export_session_csv
from vision.beam_controller import BeamController
from vision.face_detector import FaceDetector

from ui.panels.beam_panel import BeamPanel
from ui.panels.camera_panel import CameraPanel
from ui.panels.control_panel import ControlPanel
from ui.panels.status_bar import StatusBar
from ui.theme import (
    ACCENT_COLOR,
    BACKGROUND_CARD,
    BACKGROUND_DARK,
    BACKGROUND_PANEL,
    BORDER_COLOR,
    FONT_SIZE_LARGE,
    FONT_SIZE_SMALL,
    FONT_SIZE_TITLE,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TEXT_MUTED,
    WARNING_COLOR,
    get_stylesheet,
)

logger = setup_logger("beamface.main_window")


class MainWindow(QMainWindow):
    """
    Top-level application window that integrates all BeamFace subsystems.

    Instantiates core components (FaceDetector, BeamController, AudioEngine),
    assembles the panel layout, connects all signals, and manages shutdown.
    """

    def __init__(self):
        """Initialize the main window, core components, and layout."""
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} - Acoustic Beamforming System")
        self.setMinimumSize(1280, 780)
        self.setStyleSheet(get_stylesheet())

        self._fps_counter = 0
        self._fps_last_time = time.monotonic()
        self._fps_value = 0.0
        self._session_rows = []
        self._mode = "auto"
        self._audio_active = False

        self._init_core_components()
        self._build_ui()
        self._connect_signals()
        self._start_timers()

        logger.info("MainWindow initialized")

    def _init_core_components(self):
        """Initialize speaker array, face detector, beam controller, and audio engine."""
        self.speaker_positions = get_speaker_positions()

        self.beam_controller = BeamController()

        # Attempt camera initialization; fall back to simulation-only mode on failure
        self.face_detector = FaceDetector(camera_index=0)
        self._camera_available = True
        try:
            self.face_detector.initialize()
            logger.info("Camera initialized successfully")
        except RuntimeError as exc:
            logger.warning("Camera initialization failed: %s", exc)
            self._camera_available = False
            QMessageBox.warning(
                None,
                "Camera Not Available",
                f"Could not open camera:\n{exc}\n\n"
                "Continuing in simulation-only mode.\n"
                "Use Manual Override for beam steering.",
            )

        self.audio_engine = AudioEngine(self.beam_controller)
        self.audio_engine.load_source()

    def _build_ui(self):
        """Construct the full window layout from panels and info cards."""
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_header())

        content = QHBoxLayout()
        content.setContentsMargins(8, 8, 8, 8)
        content.setSpacing(8)
        content.addWidget(self._build_left_column(), 0)
        content.addWidget(self._build_center_column(), 1)
        content.addWidget(self._build_right_column(), 0)

        content_widget = QWidget()
        content_widget.setLayout(content)
        root.addWidget(content_widget, 1)

        self.status_bar_widget = StatusBar()
        root.addWidget(self.status_bar_widget)

    def _build_header(self) -> QWidget:
        """Build the top header bar with app name and version."""
        header = QWidget()
        header.setFixedHeight(48)
        header.setStyleSheet(
            f"background-color: {BACKGROUND_PANEL}; "
            f"border-bottom: 1px solid {BORDER_COLOR};"
        )
        layout = QHBoxLayout(header)
        layout.setContentsMargins(16, 0, 16, 0)

        lbl_name = QLabel(APP_NAME)
        lbl_name.setStyleSheet(
            f"color: {TEXT_PRIMARY}; font-size: {FONT_SIZE_TITLE}pt; font-weight: bold;"
        )

        lbl_subtitle = QLabel("Acoustic Beamforming Simulation")
        lbl_subtitle.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: {FONT_SIZE_SMALL}pt;"
        )

        lbl_version = QLabel(f"v{APP_VERSION}")
        lbl_version.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: {FONT_SIZE_SMALL}pt;"
        )
        lbl_version.setAlignment(Qt.AlignVCenter | Qt.AlignRight)

        layout.addWidget(lbl_name)
        layout.addSpacing(12)
        layout.addWidget(lbl_subtitle)
        layout.addStretch()
        layout.addWidget(lbl_version)

        return header

    def _build_left_column(self) -> QWidget:
        """Build the left column: camera feed and three info cards."""
        col = QWidget()
        col.setFixedWidth(660)
        layout = QVBoxLayout(col)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Camera panel
        cam_card = self._wrap_in_card(padding=4)
        cam_layout = QVBoxLayout(cam_card)
        cam_layout.setContentsMargins(6, 6, 6, 6)

        self.camera_panel = CameraPanel(self.face_detector, self.beam_controller)
        cam_layout.addWidget(self.camera_panel)
        layout.addWidget(cam_card)

        # Info cards row
        cards_row = QHBoxLayout()
        cards_row.setSpacing(8)

        self.lbl_current_angle = self._make_info_card("Current Angle", "0.0 deg")
        self.lbl_target_angle = self._make_info_card("Target Angle", "0.0 deg")
        self.lbl_distance = self._make_info_card("Distance", "--- cm")

        cards_row.addWidget(self.lbl_current_angle[0])
        cards_row.addWidget(self.lbl_target_angle[0])
        cards_row.addWidget(self.lbl_distance[0])
        layout.addLayout(cards_row)
        layout.addStretch()

        return col

    def _make_info_card(self, title: str, initial_value: str):
        """
        Create a small metric display card.

        Returns
        -------
        tuple[QWidget, QLabel]
            The card widget and the value label (for live updates).
        """
        card = self._wrap_in_card(padding=12)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        lbl_title = QLabel(title)
        lbl_title.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: {FONT_SIZE_SMALL}pt;"
        )
        lbl_title.setAlignment(Qt.AlignCenter)

        lbl_value = QLabel(initial_value)
        lbl_value.setStyleSheet(
            f"color: {TEXT_PRIMARY}; font-size: {FONT_SIZE_LARGE}pt; "
            "font-family: 'Courier New', Courier, monospace; font-weight: bold;"
        )
        lbl_value.setAlignment(Qt.AlignCenter)

        layout.addWidget(lbl_title)
        layout.addWidget(lbl_value)

        return card, lbl_value

    def _build_center_column(self) -> QWidget:
        """Build the center column: polar beam plot and speaker array visualization."""
        col = QWidget()
        layout = QVBoxLayout(col)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.beam_panel = BeamPanel(self.beam_controller, self.speaker_positions)
        beam_card = self._wrap_in_card(padding=4)
        beam_card_layout = QVBoxLayout(beam_card)
        beam_card_layout.setContentsMargins(4, 4, 4, 4)
        beam_card_layout.addWidget(self.beam_panel)
        layout.addWidget(beam_card, 1)

        layout.addWidget(self._build_speaker_array_bar())

        return col

    def _build_speaker_array_bar(self) -> QWidget:
        """Build the Hanning-weighted speaker array visualization strip."""
        bar = self._wrap_in_card(padding=8)
        bar.setFixedHeight(52)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(6)

        lbl = QLabel("Speaker Array")
        lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 8pt;")
        layout.addWidget(lbl)

        weights = np.hanning(8)
        weights = weights / weights.max()

        self._speaker_indicators = []
        for i in range(8):
            alpha = int(weights[i] * 255)
            color_hex = f"#{alpha:02x}aa{255:02x}"  # blue with variable alpha via lightness
            # Use a simple opacity-weighted blue
            intensity = int(weights[i] * 255)
            r = 0
            g = int(170 * weights[i])
            b = 255
            color = f"rgb({r},{g},{b})"
            sq = QLabel()
            sq.setFixedSize(24, 24)
            sq.setStyleSheet(
                f"background-color: {color}; border: 1px solid {BORDER_COLOR}; "
                "border-radius: 3px;"
            )
            layout.addWidget(sq)
            self._speaker_indicators.append(sq)

        layout.addStretch()
        return bar

    def _build_right_column(self) -> QWidget:
        """Build the right column: scrollable ControlPanel."""
        col = QWidget()
        col.setFixedWidth(260)
        layout = QVBoxLayout(col)
        layout.setContentsMargins(0, 0, 0, 0)

        self.control_panel = ControlPanel(self.beam_controller, self.audio_engine)
        layout.addWidget(self.control_panel)

        return col

    def _wrap_in_card(self, padding: int = 8) -> QWidget:
        """Create a styled card widget with dark background and subtle border."""
        card = QWidget()
        card.setStyleSheet(
            f"background-color: {BACKGROUND_CARD}; "
            f"border: 1px solid {BORDER_COLOR}; "
            "border-radius: 6px;"
        )
        return card

    def _connect_signals(self):
        """Connect all inter-panel signals to their handlers."""
        self.camera_panel.frame_updated.connect(self._on_frame_updated)

        self.control_panel.mode_changed.connect(self._on_mode_changed)
        self.control_panel.camera_restart_requested.connect(self._on_camera_restart)
        self.control_panel.angle_test_requested.connect(self._run_angle_test)
        self.control_panel.export_pattern_requested.connect(self._export_pattern)
        self.control_panel.export_csv_requested.connect(self._export_csv)

    def _start_timers(self):
        """Start the beam pattern update timer."""
        self._pattern_timer = QTimer(self)
        self._pattern_timer.timeout.connect(self.beam_panel.recompute_pattern)
        self._pattern_timer.start(100)

        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self._update_status_bar)
        self._status_timer.start(200)

    def _on_frame_updated(self, face_data, controller_status):
        """Handle a new camera frame: update info cards and FPS, log session row."""
        self._fps_counter += 1
        now = time.monotonic()
        elapsed = now - self._fps_last_time
        if elapsed >= 1.0:
            self._fps_value = self._fps_counter / elapsed
            self._fps_counter = 0
            self._fps_last_time = now

        self.lbl_current_angle[1].setText(
            f"{controller_status['current_angle']:+.1f} deg"
        )
        self.lbl_target_angle[1].setText(
            f"{controller_status['target_angle']:+.1f} deg"
        )
        if face_data.detected:
            self.lbl_distance[1].setText(f"{face_data.distance_cm:.0f} cm")
        else:
            self.lbl_distance[1].setText("--- cm")

        # Accumulate session log row
        import datetime
        row = {
            "timestamp": datetime.datetime.now().isoformat(),
            "face_detected": face_data.detected,
            "raw_angle": face_data.angle_deg,
            "smoothed_angle": controller_status["target_angle"],
            "beam_angle": controller_status["current_angle"],
            "target_angle": controller_status["target_angle"],
            "rms_db": controller_status["current_rms_db"],
        }
        self._session_rows.append(row)
        # Keep last 10 000 rows to bound memory
        if len(self._session_rows) > 10000:
            self._session_rows = self._session_rows[-10000:]

    def _update_status_bar(self):
        """Push current system status to the status bar widget."""
        status = self.beam_controller.get_status()
        self.status_bar_widget.update_status(
            {
                "fps": self._fps_value,
                "beam_angle": status["current_angle"],
                "target_angle": status["target_angle"],
                "rms_db": status["current_rms_db"],
                "face_detected": status["face_detected"],
                "audio_active": self._audio_active,
                "mode": self._mode,
            }
        )

    def _on_mode_changed(self, mode: str):
        """Handle steering mode changes from the control panel."""
        self._mode = mode
        logger.info("Steering mode set to: %s", mode)

    def _on_camera_restart(self, camera_index: int):
        """Restart the camera at the specified device index."""
        logger.info("Restarting camera at index %d", camera_index)
        self.camera_panel._worker.stop()
        self.face_detector.release()
        self.face_detector = FaceDetector(camera_index=camera_index)
        try:
            self.face_detector.initialize()
            self.camera_panel.face_detector = self.face_detector
            
            from ui.panels.camera_panel import VideoWorker
            self.camera_panel._worker = VideoWorker(self.face_detector)
            self.camera_panel._worker.frame_processed.connect(self.camera_panel.update_frame)
            self.camera_panel._worker.start()
            
            logger.info("Camera restarted successfully")
        except RuntimeError as exc:
            logger.error("Camera restart failed: %s", exc)
            QMessageBox.warning(
                self,
                "Camera Restart Failed",
                f"Could not open camera at index {camera_index}:\n{exc}",
            )

    def _run_angle_test(self):
        """Run beamforming at three test angles and log RMS dB results."""
        test_angles = [-45.0, 0.0, 45.0]
        signal = generate_sine_tone(DEFAULT_FREQUENCY, 0.1, SAMPLE_RATE)
        logger.info("--- Angle Test Results ---")
        for angle in test_angles:
            speaker_signals = apply_beamforming(signal, angle, self.speaker_positions)
            _, db_values = compute_pattern_db(speaker_signals, self.speaker_positions)
            peak_db = float(np.max(db_values))
            logger.info(
                "Angle: %+.1f deg | Peak pattern dB: %.2f dB", angle, peak_db
            )
        logger.info("--- End Angle Test ---")

    def _export_pattern(self):
        """Export the current beam panel plot as a PNG file."""
        try:
            path = export_beam_pattern_png(self.beam_panel.figure)
            logger.info("Beam pattern exported to: %s", path)
            QMessageBox.information(self, "Export Complete", f"Pattern saved to:\n{path}")
        except Exception:
            logger.error("Pattern export failed:\n%s", traceback.format_exc())
            QMessageBox.warning(self, "Export Failed", "Could not export beam pattern.")

    def _export_csv(self):
        """Export the session log as a CSV file."""
        try:
            path = export_session_csv(self._session_rows)
            logger.info("Session CSV exported to: %s", path)
            QMessageBox.information(self, "Export Complete", f"Session data saved to:\n{path}")
        except Exception:
            logger.error("CSV export failed:\n%s", traceback.format_exc())
            QMessageBox.warning(self, "Export Failed", "Could not export session CSV.")

    def closeEvent(self, event):
        """Clean up all resources on window close."""
        logger.info("Shutting down BeamFace")
        try:
            self.camera_panel._worker.stop()
            self._pattern_timer.stop()
            self._status_timer.stop()
            self.audio_engine.stop()
            self.face_detector.release()
        except Exception:
            logger.error("Error during shutdown:\n%s", traceback.format_exc())
        event.accept()

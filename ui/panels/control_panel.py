"""
User controls panel for BeamFace.

Provides all runtime controls: audio source selection, beam steering mode,
simulation tests, camera settings, and audio output toggle. No business logic
lives here; the panel only emits signals and calls controller methods directly.
"""

import logging

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ui.theme import DANGER_COLOR, TEXT_SECONDARY, WARNING_COLOR

logger = logging.getLogger("beamface.control_panel")


class ControlPanel(QWidget):
    """
    Vertical scrollable panel containing all user-facing controls.

    Emits signals for audio source changes, mode changes, and camera restarts.
    Directly calls beam_controller and audio_engine methods for low-latency
    parameter updates (e.g., smoothing, manual angle).
    """

    # Signals emitted by this panel
    audio_source_changed = pyqtSignal(str, int)    # (filepath_or_empty, frequency_hz)
    mode_changed = pyqtSignal(str)                  # "auto" or "manual"
    camera_restart_requested = pyqtSignal(int)      # camera index
    angle_test_requested = pyqtSignal()
    export_pattern_requested = pyqtSignal()
    export_csv_requested = pyqtSignal()

    def __init__(self, beam_controller, audio_engine, parent=None):
        """Initialize the ControlPanel with references to controller and engine."""
        super().__init__(parent)
        self.beam_controller = beam_controller
        self.audio_engine = audio_engine
        self._wav_filepath = ""
        self._audio_active = False

        self._build_ui()
        self._connect_signals()

    def _build_ui(self):
        """Build the scrollable panel with all control sections."""
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(8, 8, 8, 8)
        container_layout.setSpacing(12)

        container_layout.addWidget(self._build_audio_source_section())
        container_layout.addWidget(self._build_beam_control_section())
        container_layout.addWidget(self._build_simulation_section())
        container_layout.addWidget(self._build_camera_section())
        container_layout.addWidget(self._build_audio_output_section())
        container_layout.addStretch()

        scroll.setWidget(container)
        outer_layout.addWidget(scroll)

    def _build_audio_source_section(self) -> QGroupBox:
        """Build the Audio Source control group."""
        group = QGroupBox("Audio Source")
        layout = QVBoxLayout(group)
        layout.setSpacing(6)

        self.radio_sine = QRadioButton("Sine Tone")
        self.radio_sine.setChecked(True)
        self.radio_wav = QRadioButton("Load WAV File")

        self._audio_source_group = QButtonGroup(self)
        self._audio_source_group.addButton(self.radio_sine)
        self._audio_source_group.addButton(self.radio_wav)

        self.btn_browse = QPushButton("Browse...")
        self.btn_browse.setEnabled(False)

        self.lbl_file = QLabel("Default: 1 kHz sine tone")
        self.lbl_file.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 8pt;")
        self.lbl_file.setWordWrap(True)

        freq_row = QHBoxLayout()
        freq_row.addWidget(QLabel("Frequency (Hz)"))
        self.spin_frequency = QSpinBox()
        self.spin_frequency.setRange(100, 8000)
        self.spin_frequency.setValue(1000)
        freq_row.addWidget(self.spin_frequency)

        self.btn_apply_audio = QPushButton("Apply Audio Settings")

        layout.addWidget(self.radio_sine)
        layout.addWidget(self.radio_wav)
        layout.addWidget(self.btn_browse)
        layout.addWidget(self.lbl_file)
        layout.addLayout(freq_row)
        layout.addWidget(self.btn_apply_audio)

        return group

    def _build_beam_control_section(self) -> QGroupBox:
        """Build the Beam Control group with mode selector and sliders."""
        group = QGroupBox("Beam Control")
        layout = QVBoxLayout(group)
        layout.setSpacing(6)

        layout.addWidget(QLabel("Steering Mode"))
        self.combo_mode = QComboBox()
        self.combo_mode.addItems(["Face Tracking (Auto)", "Manual Override"])
        layout.addWidget(self.combo_mode)

        self.lbl_manual_angle = QLabel("Manual Angle: 0.0 deg")
        self.slider_angle = QSlider(Qt.Horizontal)
        self.slider_angle.setRange(-80, 80)
        self.slider_angle.setValue(0)
        self.slider_angle.setEnabled(False)

        layout.addWidget(self.lbl_manual_angle)
        layout.addWidget(self.slider_angle)

        layout.addWidget(QLabel("Smoothing Factor"))
        self.lbl_smoothing = QLabel("Smoothing: 0.15")
        self.slider_smoothing = QSlider(Qt.Horizontal)
        self.slider_smoothing.setRange(1, 100)
        self.slider_smoothing.setValue(15)

        layout.addWidget(self.lbl_smoothing)
        layout.addWidget(self.slider_smoothing)

        return group

    def _build_simulation_section(self) -> QGroupBox:
        """Build the Simulation Test control group."""
        group = QGroupBox("Simulation Test")
        layout = QVBoxLayout(group)
        layout.setSpacing(6)

        self.btn_angle_test = QPushButton("Run Angle Test")
        self.btn_export_pattern = QPushButton("Export Beam Pattern")
        self.btn_export_csv = QPushButton("Export Session CSV")

        layout.addWidget(self.btn_angle_test)
        layout.addWidget(self.btn_export_pattern)
        layout.addWidget(self.btn_export_csv)

        return group

    def _build_camera_section(self) -> QGroupBox:
        """Build the Camera control group."""
        group = QGroupBox("Camera")
        layout = QVBoxLayout(group)
        layout.setSpacing(6)

        cam_row = QHBoxLayout()
        cam_row.addWidget(QLabel("Camera Index"))
        self.spin_camera = QSpinBox()
        self.spin_camera.setRange(0, 4)
        self.spin_camera.setValue(0)
        cam_row.addWidget(self.spin_camera)

        self.btn_restart_camera = QPushButton("Restart Camera")
        self.lbl_resolution = QLabel("Resolution: 640 x 480")
        self.lbl_resolution.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 8pt;")

        layout.addLayout(cam_row)
        layout.addWidget(self.btn_restart_camera)
        layout.addWidget(self.lbl_resolution)

        return group

    def _build_audio_output_section(self) -> QGroupBox:
        """Build the Audio Output control group."""
        group = QGroupBox("Audio Output")
        layout = QVBoxLayout(group)
        layout.setSpacing(6)

        self.chk_audio_enable = QCheckBox("Enable Audio Output")
        self.chk_audio_enable.setChecked(False)

        warning = QLabel(
            "Requires multi-channel audio device for full beamforming output. "
            "Stereo simulation always available."
        )
        warning.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 8pt;")
        warning.setWordWrap(True)

        layout.addWidget(self.chk_audio_enable)
        layout.addWidget(warning)

        return group

    def _connect_signals(self):
        """Wire internal widget signals to handlers."""
        self.radio_sine.toggled.connect(self._on_source_mode_changed)
        self.radio_wav.toggled.connect(self._on_source_mode_changed)
        self.btn_browse.clicked.connect(self._on_browse)
        self.btn_apply_audio.clicked.connect(self._on_apply_audio)

        self.combo_mode.currentIndexChanged.connect(self._on_mode_changed)
        self.slider_angle.valueChanged.connect(self._on_manual_angle_changed)
        self.slider_smoothing.valueChanged.connect(self._on_smoothing_changed)

        self.btn_angle_test.clicked.connect(self.angle_test_requested.emit)
        self.btn_export_pattern.clicked.connect(self.export_pattern_requested.emit)
        self.btn_export_csv.clicked.connect(self.export_csv_requested.emit)

        self.btn_restart_camera.clicked.connect(
            lambda: self.camera_restart_requested.emit(self.spin_camera.value())
        )
        self.chk_audio_enable.stateChanged.connect(self._on_audio_toggle)

    def _on_source_mode_changed(self):
        """Enable or disable the Browse button based on selected source mode."""
        wav_selected = self.radio_wav.isChecked()
        self.btn_browse.setEnabled(wav_selected)
        if not wav_selected:
            self._wav_filepath = ""
            self.lbl_file.setText("Default: 1 kHz sine tone")

    def _on_browse(self):
        """Open a file dialog and store the selected WAV path."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Select WAV File", "", "WAV Files (*.wav)"
        )
        if path:
            self._wav_filepath = path
            short = path if len(path) <= 40 else "..." + path[-37:]
            self.lbl_file.setText(short)
        else:
            self.lbl_file.setText("No file selected")

    def _on_apply_audio(self):
        """Reload the audio engine source with current UI settings."""
        filepath = self._wav_filepath if self.radio_wav.isChecked() else None
        frequency = self.spin_frequency.value()
        logger.info(
            "Applying audio settings: filepath=%s, freq=%d Hz", filepath, frequency
        )
        self.audio_engine.load_source(filepath=filepath, frequency=frequency)
        self.audio_source_changed.emit(filepath or "", frequency)

    def _on_mode_changed(self, index: int):
        """Switch between auto face-tracking and manual override mode."""
        if index == 0:
            self.slider_angle.setEnabled(False)
            self.mode_changed.emit("auto")
            logger.info("Steering mode: auto (face tracking)")
        else:
            self.slider_angle.setEnabled(True)
            self.mode_changed.emit("manual")
            logger.info("Steering mode: manual override")

    def _on_manual_angle_changed(self, value: int):
        """Push manual angle to the beam controller."""
        self.lbl_manual_angle.setText(f"Manual Angle: {value:.1f} deg")
        if self.combo_mode.currentIndex() == 1:
            self.beam_controller.set_target(float(value))

    def _on_smoothing_changed(self, value: int):
        """Update the beam controller's smoothing factor."""
        smoothing = value / 100.0
        self.lbl_smoothing.setText(f"Smoothing: {smoothing:.2f}")
        self.beam_controller.set_smoothing(smoothing)

    def _on_audio_toggle(self, state: int):
        """Start or stop the audio engine based on checkbox state."""
        if state == Qt.Checked:
            self.audio_engine.start()
            self._audio_active = True
            logger.info("Audio output enabled")
        else:
            self.audio_engine.stop()
            self._audio_active = False
            logger.info("Audio output disabled")

    def is_audio_active(self) -> bool:
        """Return whether audio output is currently enabled."""
        return self._audio_active

    def get_mode(self) -> str:
        """Return the current steering mode string: 'auto' or 'manual'."""
        return "auto" if self.combo_mode.currentIndex() == 0 else "manual"

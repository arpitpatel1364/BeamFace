"""
Status bar widget for BeamFace.

Displays a compact horizontal strip of live system metrics at the bottom
of the main window, including FPS, beam angle, RMS level, face detection
state, audio state, and steering mode.
"""

import logging

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget

from core.config import APP_NAME, APP_VERSION
from ui.theme import (
    BACKGROUND_PANEL,
    BORDER_COLOR,
    DANGER_COLOR,
    SUCCESS_COLOR,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    FONT_SIZE_SMALL,
)

logger = logging.getLogger("beamface.status_bar")

_MONOSPACE_STYLE = "font-family: 'Courier New', Courier, monospace; font-size: 9pt;"


def _make_divider() -> QFrame:
    """Create a vertical separator line for the status bar."""
    line = QFrame()
    line.setFrameShape(QFrame.VLine)
    line.setStyleSheet(f"color: {BORDER_COLOR}; background-color: {BORDER_COLOR};")
    line.setFixedWidth(1)
    return line


def _make_label(text: str, mono: bool = True) -> QLabel:
    """Create a status bar label with consistent styling."""
    lbl = QLabel(text)
    if mono:
        lbl.setStyleSheet(_MONOSPACE_STYLE + f" color: {TEXT_PRIMARY};")
    else:
        lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: {FONT_SIZE_SMALL}pt;")
    lbl.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
    return lbl


class StatusBar(QWidget):
    """
    Fixed-height horizontal status strip displayed at the bottom of the window.

    All fields update from status dicts passed to update_status(). The widget
    never modifies application state; it is strictly read-only display.
    """

    HEIGHT = 36

    def __init__(self, parent=None):
        """Initialize the StatusBar and build all status labels."""
        super().__init__(parent)
        self.setFixedHeight(self.HEIGHT)
        self.setStyleSheet(
            f"background-color: {BACKGROUND_PANEL}; "
            f"border-top: 1px solid {BORDER_COLOR};"
        )
        self._build_ui()

    def _build_ui(self):
        """Create and arrange all status labels and dividers."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(10)

        self.lbl_fps = _make_label("FPS: --.-")
        self.lbl_beam = _make_label("Beam:   0.0 deg")
        self.lbl_target = _make_label("Target:  0.0 deg")
        self.lbl_rms = _make_label("RMS: -60.0 dB")
        self.lbl_face = _make_label("Face: NONE")
        self.lbl_audio = _make_label("Audio: OFF")
        self.lbl_mode = _make_label("Mode: Auto")

        self.lbl_version = QLabel(f"{APP_NAME} v{APP_VERSION}")
        self.lbl_version.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: {FONT_SIZE_SMALL}pt;"
        )
        self.lbl_version.setAlignment(Qt.AlignVCenter | Qt.AlignRight)

        items = [
            self.lbl_fps,
            self.lbl_beam,
            self.lbl_target,
            self.lbl_rms,
            self.lbl_face,
            self.lbl_audio,
            self.lbl_mode,
        ]

        for item in items:
            layout.addWidget(item)
            layout.addWidget(_make_divider())

        layout.addStretch()
        layout.addWidget(self.lbl_version)

    def update_status(self, status_dict: dict):
        """
        Update all displayed status fields from a status dictionary.

        Parameters
        ----------
        status_dict : dict
            Expected keys (all optional, missing keys are skipped):
              fps, beam_angle, target_angle, rms_db,
              face_detected, audio_active, mode
        """
        if "fps" in status_dict:
            self.lbl_fps.setText(f"FPS: {status_dict['fps']:4.1f}")

        if "beam_angle" in status_dict:
            angle = status_dict["beam_angle"]
            self.lbl_beam.setText(f"Beam: {angle:+6.1f} deg")

        if "target_angle" in status_dict:
            angle = status_dict["target_angle"]
            self.lbl_target.setText(f"Target: {angle:+6.1f} deg")

        if "rms_db" in status_dict:
            rms = status_dict["rms_db"]
            self.lbl_rms.setText(f"RMS: {rms:+6.1f} dB")

        if "face_detected" in status_dict:
            detected = status_dict["face_detected"]
            if detected:
                self.lbl_face.setText("Face: DETECTED")
                self.lbl_face.setStyleSheet(
                    _MONOSPACE_STYLE + f" color: {SUCCESS_COLOR};"
                )
            else:
                self.lbl_face.setText("Face: NONE")
                self.lbl_face.setStyleSheet(
                    _MONOSPACE_STYLE + f" color: {DANGER_COLOR};"
                )

        if "audio_active" in status_dict:
            active = status_dict["audio_active"]
            if active:
                self.lbl_audio.setText("Audio: ON")
                self.lbl_audio.setStyleSheet(
                    _MONOSPACE_STYLE + f" color: {SUCCESS_COLOR};"
                )
            else:
                self.lbl_audio.setText("Audio: OFF")
                self.lbl_audio.setStyleSheet(
                    _MONOSPACE_STYLE + f" color: {TEXT_SECONDARY};"
                )

        if "mode" in status_dict:
            mode = status_dict["mode"]
            display = "Auto" if mode == "auto" else "Manual"
            self.lbl_mode.setText(f"Mode: {display}")

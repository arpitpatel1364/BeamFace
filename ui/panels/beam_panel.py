"""
Real-time polar beam pattern visualization panel for BeamFace.

Embeds a matplotlib polar plot in a PyQt5 widget. The pattern is recomputed
at a reduced rate (every PATTERN_UPDATE_INTERVAL frames) to balance
visual responsiveness with CPU cost.
"""

import logging
import traceback


import numpy as np
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt5.QtWidgets import QVBoxLayout, QWidget

from core.audio_source import generate_sine_tone
from core.beamformer import apply_beamforming, compute_pattern_db
from core.config import (
    DEFAULT_FREQUENCY,
    PATTERN_UPDATE_INTERVAL,
    SAMPLE_RATE,
)
from ui.theme import (
    FONT_SIZE_NORMAL,
    PLOT_BG,
    PLOT_BEAM,
    PLOT_GRID,
    PLOT_LINE,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    WARNING_COLOR,
    BACKGROUND_DARK,
)

logger = logging.getLogger("beamface.beam_panel")

_PATTERN_BLOCK_SECONDS = 0.1    # short block for fast pattern computation
_RLIM_MIN = -40                  # minimum dB shown on radial axis
_RLIM_MAX = 3                    # maximum dB (slightly above 0 for headroom)


class BeamPanel(QWidget):
    """
    Widget displaying the live acoustic beam pattern as a polar plot.

    Recomputes the pattern on each timer tick and updates the embedded
    matplotlib canvas. The plot is styled to match the application's dark theme.
    """

    def __init__(self, beam_controller, speaker_positions, parent=None):
        """Initialize the BeamPanel with beam_controller and speaker_positions."""
        super().__init__(parent)
        self.beam_controller = beam_controller
        self.speaker_positions = speaker_positions
        self.update_counter = 0

        self._build_plot()
        self._build_ui()

    def _build_plot(self):
        """Create and configure the matplotlib figure and polar axes."""
        self.figure = Figure(facecolor=BACKGROUND_DARK)
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.setStyleSheet(f"background-color: {BACKGROUND_DARK};")

        self.ax = self.figure.add_subplot(111, projection="polar")
        self.ax.set_facecolor(PLOT_BG)
        self.ax.tick_params(colors=TEXT_SECONDARY, labelsize=7)
        self.ax.spines["polar"].set_edgecolor(PLOT_GRID)
        self.figure.subplots_adjust(left=0.05, right=0.95, top=0.88, bottom=0.05)

    def _build_ui(self):
        """Embed the matplotlib canvas in the widget layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas)

    def recompute_pattern(self):
        """
        Recompute the beam pattern and redraw the polar plot.

        Generates a short test block at the current steering angle, computes
        the directivity pattern across all angles, and updates the plot.
        Errors are caught and logged so a single bad frame never crashes the UI.
        """
        try:
            status = self.beam_controller.get_status()
            current_angle = status["current_angle"]
            target_angle = status["target_angle"]

            # Generate a short block (faster than full buffer for pattern compute)
            n_samples = int(_PATTERN_BLOCK_SECONDS * SAMPLE_RATE)
            test_signal = generate_sine_tone(
                DEFAULT_FREQUENCY, _PATTERN_BLOCK_SECONDS, SAMPLE_RATE
            )

            speaker_signals = apply_beamforming(
                test_signal, current_angle, self.speaker_positions
            )
            angles_deg, db_values = compute_pattern_db(
                speaker_signals, self.speaker_positions
            )

            self._update_plot(angles_deg, db_values, current_angle, target_angle)

        except Exception:
            logger.error(
                "Error computing beam pattern:\n%s", traceback.format_exc()
            )

    def _update_plot(
        self,
        angles_deg: np.ndarray,
        db_values: np.ndarray,
        current_angle: float,
        target_angle: float,
    ):
        """
        Redraw the polar plot with new pattern data and angle indicators.

        Parameters
        ----------
        angles_deg : np.ndarray
            Angle values in degrees for the pattern sweep.
        db_values : np.ndarray
            Corresponding beam response in dB (normalized, peak = 0).
        current_angle : float
            Current beam steering angle in degrees.
        target_angle : float
            Target beam steering angle in degrees.
        """
        self.ax.clear()

        # Convert angles to radians for polar plot
        # Polar convention: 0 = East; shift so 0 deg = North (up)
        angles_rad = np.radians(angles_deg + 90.0)
        db_clipped = np.maximum(db_values, _RLIM_MIN)

        # Main beam pattern fill
        self.ax.fill(angles_rad, db_clipped - _RLIM_MIN,
                     color=PLOT_LINE, alpha=0.12)

        # Main beam pattern line
        self.ax.plot(
            angles_rad, db_clipped - _RLIM_MIN,
            color=PLOT_LINE, linewidth=1.5, label="Pattern",
        )

        # Current steering angle indicator
        current_rad = np.radians(current_angle + 90.0)
        self.ax.plot(
            [current_rad, current_rad],
            [0, _RLIM_MAX - _RLIM_MIN],
            color=PLOT_BEAM, linewidth=2, label=f"Current {current_angle:.1f} deg",
        )

        # Target angle indicator (dashed)
        target_rad = np.radians(target_angle + 90.0)
        self.ax.plot(
            [target_rad, target_rad],
            [0, _RLIM_MAX - _RLIM_MIN],
            color=WARNING_COLOR, linewidth=1, linestyle="--",
            label=f"Target {target_angle:.1f} deg",
        )

        # Configure axes appearance
        r_range = _RLIM_MAX - _RLIM_MIN
        self.ax.set_rlim(0, r_range)
        rticks_db = [-40, -30, -20, -10, 0]
        rticks_plot = [v - _RLIM_MIN for v in rticks_db]
        self.ax.set_yticks(rticks_plot)
        self.ax.set_yticklabels(
            [f"{v} dB" for v in rticks_db],
            color=TEXT_SECONDARY, fontsize=7,
        )

        # Theta grid: 0 deg at North (top), clockwise
        self.ax.set_theta_zero_location("N")
        self.ax.set_theta_direction(-1)
        self.ax.set_thetagrids(
            [0, 30, 60, 90, 120, 150, 180, 210, 240, 270, 300, 330],
            labels=["0", "30", "60", "90", "120", "150",
                    "180", "-150", "-120", "-90", "-60", "-30"],
            color=TEXT_SECONDARY, fontsize=7,
        )

        self.ax.set_facecolor(PLOT_BG)
        self.ax.grid(color=PLOT_GRID, linewidth=0.5)
        self.ax.tick_params(colors=TEXT_SECONDARY, labelsize=7)
        self.ax.spines["polar"].set_edgecolor(PLOT_GRID)

        self.ax.set_title(
            f"Beam Pattern  |  Steering: {current_angle:.1f} deg",
            color=TEXT_PRIMARY,
            fontsize=FONT_SIZE_NORMAL,
            pad=12,
        )

        self.canvas.draw()

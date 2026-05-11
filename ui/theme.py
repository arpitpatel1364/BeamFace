"""
Visual theme constants and stylesheet for BeamFace.

All colors, fonts, and sizes are defined here. No other module should
hardcode visual values. The get_stylesheet() function returns the full
PyQt5 QSS string for the application.
"""

# Background colors
BACKGROUND_DARK = "#0f172a"
BACKGROUND_PANEL = "#1e293b"
BACKGROUND_CARD = "#334155"

# Borders
BORDER_COLOR = "#475569"

# Accent colors
ACCENT_COLOR = "#38bdf8"
ACCENT_SECONDARY = "#0ea5e9"

# Text colors
TEXT_PRIMARY = "#f8fafc"
TEXT_SECONDARY = "#94a3b8"
TEXT_MUTED = "#64748b"

# Semantic colors
SUCCESS_COLOR = "#10b981"
WARNING_COLOR = "#f59e0b"
DANGER_COLOR = "#ef4444"

# Plot colors
PLOT_BG = "#0f172a"
PLOT_GRID = "#334155"
PLOT_LINE = "#38bdf8"
PLOT_BEAM = "#f59e0b"

# Typography
FONT_FAMILY = "Inter, Segoe UI, Roboto"
FONT_SIZE_SMALL = 9
FONT_SIZE_NORMAL = 10
FONT_SIZE_LARGE = 13
FONT_SIZE_TITLE = 16
FONT_SIZE_HEADER = 12


def get_stylesheet() -> str:
    """
    Return the full PyQt5 QSS stylesheet string for the BeamFace application.

    Applies dark theme to all standard widgets. Interactive elements use the
    accent color. Cards have rounded corners and subtle borders.
    """
    return f"""
    /* ====== Base ====== */
    QMainWindow, QDialog {{
        background-color: {BACKGROUND_DARK};
        color: {TEXT_PRIMARY};
        font-family: "{FONT_FAMILY}", Arial, sans-serif;
        font-size: {FONT_SIZE_NORMAL}pt;
    }}

    QWidget {{
        background-color: {BACKGROUND_DARK};
        color: {TEXT_PRIMARY};
        font-family: "{FONT_FAMILY}", Arial, sans-serif;
        font-size: {FONT_SIZE_NORMAL}pt;
    }}

    /* ====== Labels ====== */
    QLabel {{
        background-color: transparent;
        color: {TEXT_PRIMARY};
        font-family: "{FONT_FAMILY}", Arial, sans-serif;
    }}

    QLabel[class="secondary"] {{
        color: {TEXT_SECONDARY};
    }}

    QLabel[class="muted"] {{
        color: {TEXT_MUTED};
    }}

    /* ====== Buttons ====== */
    QPushButton {{
        background-color: {BACKGROUND_CARD};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER_COLOR};
        border-radius: 6px;
        padding: 8px 16px;
        font-size: {FONT_SIZE_NORMAL}pt;
        font-weight: 500;
        font-family: "{FONT_FAMILY}", Arial, sans-serif;
    }}

    QPushButton:hover {{
        background-color: {ACCENT_COLOR};
        color: #0f172a;
        border: 1px solid {ACCENT_COLOR};
    }}

    QPushButton:pressed {{
        background-color: {ACCENT_SECONDARY};
        color: #0f172a;
    }}

    QPushButton:disabled {{
        background-color: {BACKGROUND_PANEL};
        color: {TEXT_MUTED};
        border: 1px solid {BORDER_COLOR};
    }}

    /* ====== Sliders ====== */
    QSlider::groove:horizontal {{
        height: 4px;
        background: {BORDER_COLOR};
        border-radius: 2px;
    }}

    QSlider::handle:horizontal {{
        background: {ACCENT_COLOR};
        border: none;
        width: 14px;
        height: 14px;
        margin: -5px 0;
        border-radius: 7px;
    }}

    QSlider::sub-page:horizontal {{
        background: {ACCENT_COLOR};
        border-radius: 2px;
    }}

    QSlider::groove:vertical {{
        width: 4px;
        background: {BORDER_COLOR};
        border-radius: 2px;
    }}

    QSlider::handle:vertical {{
        background: {ACCENT_COLOR};
        border: none;
        width: 14px;
        height: 14px;
        margin: 0 -5px;
        border-radius: 7px;
    }}

    QSlider:disabled::handle:horizontal,
    QSlider:disabled::handle:vertical {{
        background: {TEXT_MUTED};
    }}

    /* ====== ComboBox ====== */
    QComboBox {{
        background-color: {BACKGROUND_CARD};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER_COLOR};
        border-radius: 4px;
        padding: 4px 8px;
        font-size: {FONT_SIZE_NORMAL}pt;
    }}

    QComboBox:hover {{
        border: 1px solid {ACCENT_COLOR};
    }}

    QComboBox QAbstractItemView {{
        background-color: {BACKGROUND_PANEL};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER_COLOR};
        selection-background-color: {ACCENT_SECONDARY};
    }}

    QComboBox::drop-down {{
        border: none;
        width: 20px;
    }}

    /* ====== GroupBox ====== */
    QGroupBox {{
        background-color: {BACKGROUND_PANEL};
        border: 1px solid {BORDER_COLOR};
        border-radius: 8px;
        margin-top: 14px;
        padding: 12px;
        font-size: {FONT_SIZE_NORMAL}pt;
        color: {TEXT_SECONDARY};
    }}

    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 0 6px;
        color: {TEXT_SECONDARY};
        font-size: {FONT_SIZE_NORMAL}pt;
    }}

    /* ====== SpinBox ====== */
    QSpinBox, QDoubleSpinBox {{
        background-color: {BACKGROUND_CARD};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER_COLOR};
        border-radius: 4px;
        padding: 4px 6px;
        font-size: {FONT_SIZE_NORMAL}pt;
    }}

    QSpinBox:hover, QDoubleSpinBox:hover {{
        border: 1px solid {ACCENT_COLOR};
    }}

    QSpinBox::up-button, QSpinBox::down-button,
    QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
        background-color: {BACKGROUND_PANEL};
        border: none;
        width: 14px;
    }}

    /* ====== CheckBox ====== */
    QCheckBox {{
        color: {TEXT_PRIMARY};
        spacing: 6px;
        font-size: {FONT_SIZE_NORMAL}pt;
    }}

    QCheckBox::indicator {{
        width: 14px;
        height: 14px;
        background-color: {BACKGROUND_CARD};
        border: 1px solid {BORDER_COLOR};
        border-radius: 3px;
    }}

    QCheckBox::indicator:checked {{
        background-color: {ACCENT_COLOR};
        border: 1px solid {ACCENT_COLOR};
    }}

    /* ====== RadioButton ====== */
    QRadioButton {{
        color: {TEXT_PRIMARY};
        spacing: 6px;
        font-size: {FONT_SIZE_NORMAL}pt;
    }}

    QRadioButton::indicator {{
        width: 14px;
        height: 14px;
        background-color: {BACKGROUND_CARD};
        border: 1px solid {BORDER_COLOR};
        border-radius: 7px;
    }}

    QRadioButton::indicator:checked {{
        background-color: {ACCENT_COLOR};
        border: 2px solid {BACKGROUND_DARK};
        outline: 1px solid {ACCENT_COLOR};
    }}

    /* ====== TabWidget ====== */
    QTabWidget::pane {{
        background-color: {BACKGROUND_PANEL};
        border: 1px solid {BORDER_COLOR};
        border-radius: 6px;
    }}

    QTabBar::tab {{
        background-color: {BACKGROUND_DARK};
        color: {TEXT_SECONDARY};
        padding: 6px 14px;
        border: 1px solid {BORDER_COLOR};
        border-bottom: none;
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
    }}

    QTabBar::tab:selected {{
        background-color: {BACKGROUND_PANEL};
        color: {TEXT_PRIMARY};
        border-bottom: 2px solid {ACCENT_COLOR};
    }}

    /* ====== ProgressBar ====== */
    QProgressBar {{
        background-color: {BACKGROUND_CARD};
        border: 1px solid {BORDER_COLOR};
        border-radius: 4px;
        text-align: center;
        color: {TEXT_PRIMARY};
        height: 12px;
    }}

    QProgressBar::chunk {{
        background-color: {ACCENT_COLOR};
        border-radius: 3px;
    }}

    /* ====== Frame ====== */
    QFrame {{
        border: none;
        background-color: transparent;
    }}

    QFrame[frameShape="4"],
    QFrame[frameShape="5"] {{
        background-color: {BORDER_COLOR};
    }}

    /* ====== ScrollArea ====== */
    QScrollArea {{
        background-color: {BACKGROUND_DARK};
        border: none;
    }}

    QScrollBar:vertical {{
        background: {BACKGROUND_PANEL};
        width: 8px;
        border-radius: 4px;
    }}

    QScrollBar::handle:vertical {{
        background: {TEXT_MUTED};
        border-radius: 4px;
        min-height: 30px;
    }}

    QScrollBar::handle:vertical:hover {{
        background: {TEXT_SECONDARY};
    }}

    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}

    QScrollBar:horizontal {{
        background: {BACKGROUND_PANEL};
        height: 8px;
        border-radius: 4px;
    }}

    QScrollBar::handle:horizontal {{
        background: {TEXT_MUTED};
        border-radius: 4px;
        min-width: 30px;
    }}

    QScrollBar::handle:horizontal:hover {{
        background: {TEXT_SECONDARY};
    }}

    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0;
    }}

    /* ====== Tooltips ====== */
    QToolTip {{
        background-color: {BACKGROUND_CARD};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER_COLOR};
        padding: 4px 8px;
        border-radius: 4px;
        font-size: {FONT_SIZE_SMALL}pt;
    }}
    """

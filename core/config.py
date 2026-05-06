"""
System-wide configuration constants for BeamFace.

All physical, audio, vision, and application constants are defined here.
No other module should hardcode numeric or string values that belong here.
"""

# Array geometry
NUM_SPEAKERS = 8
SPEAKER_SPACING = 0.05          # meters between adjacent speakers

# Audio processing
SAMPLE_RATE = 44100             # Hz, standard CD-quality sample rate
SPEED_OF_SOUND = 343.0          # m/s at ~20 degrees Celsius, sea level
BLOCK_SIZE = 2048               # audio samples per processing block
DEFAULT_FREQUENCY = 1000        # Hz, default sine tone frequency
DEFAULT_DURATION = 10.0         # seconds of pre-generated audio buffer

# Vision and camera
CAMERA_FOV_DEG = 60.0           # horizontal field of view of webcam in degrees
FACE_REAL_WIDTH_CM = 14.0       # average adult human face width in centimeters
DEFAULT_FOCAL_LENGTH = 600.0    # estimated focal length in pixels

# Beam steering
SMOOTHING_FACTOR = 0.15         # lerp coefficient for beam angle smoothing (0..1)
MAX_ANGLE_HISTORY = 5           # rolling average window size for face angle
PATTERN_UPDATE_INTERVAL = 20    # frames between full beam pattern recomputes

# Filesystem
OUTPUT_DIR = "beamface/output"
LOG_DIR = "beamface/logs"

# Application metadata
APP_NAME = "BeamFace"
APP_VERSION = "1.0.0"

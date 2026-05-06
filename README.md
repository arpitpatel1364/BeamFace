# BeamFace - Acoustic Beamforming Simulation System

## Overview

BeamFace is a real-time desktop application that combines acoustic
beamforming simulation with live face-tracked beam steering. The system
simulates an 8-element uniform linear speaker array, computes per-speaker
delay-and-sum signals to steer a directional audio beam, and continuously
tracks the user's face via webcam to keep the beam aimed at the listener.

**Beamforming** is a signal processing technique where multiple speakers
(or microphones) are driven with individually delayed versions of the same
signal. Because the delayed signals arrive in phase only at the target
angle, they constructively interfere there and destructively cancel
elsewhere, creating a directional "beam" of sound. The direction of the
beam is controlled purely by adjusting the per-speaker time delays.

**Face tracking integration** allows the system to automatically steer the
beam toward whoever is in front of the camera. A MediaPipe neural network
detector (with an OpenCV Haar cascade fallback) locates the face in each
video frame, converts its horizontal pixel position to an angle relative
to the camera's field of view, and feeds that angle into the beamformer
in real time. A rolling weighted average and exponential lerp smooth out
jitter so the beam tracks faces without stuttering.

---

## Requirements

- Python 3.8 or later
- numpy
- scipy
- PyQt5
- opencv-python
- mediapipe
- sounddevice
- matplotlib

---

## Installation

```bash
# Clone or download the repository
git clone <repository-url>
cd beamface

# Install all dependencies
pip install -r requirements.txt

# Launch the application
python main.py
```

If no webcam is detected, the application starts in simulation-only mode
and allows manual beam angle control via the control panel.

---

## How It Works

### Signal Processing Pipeline

1. An audio source is generated (sine tone) or loaded from a WAV file.
2. The source is split into blocks of 2048 samples per processing cycle.
3. For the current steering angle, per-speaker propagation delays are
   computed using the formula:
   `delay = (x_n * sin(theta)) / speed_of_sound`
4. Each speaker's signal is time-shifted by its delay and amplitude-tapered
   using a Hanning window to reduce sidelobes.
5. To simulate stereo playback, the beamformed speaker array output is
   summed as perceived by left and right ear positions (3 degrees apart).
6. The stereo block is pushed to a queue consumed by the SoundDevice
   audio callback thread.

### Face Detection Pipeline

1. The camera is polled at approximately 30 frames per second via a QTimer
   on the main thread.
2. Each frame is processed by MediaPipe face detection (model_selection=0
   for close-range detection). If MediaPipe is unavailable or finds nothing,
   an OpenCV Haar cascade is used as fallback.
3. The largest detected face is selected. Its horizontal center pixel is
   converted to a steering angle using the camera's field of view.
4. The raw angle passes through a 5-frame weighted rolling average, then
   through an exponential lerp (smoothing factor adjustable in the UI).
5. The smoothed current angle is read by the audio producer thread on every
   block to steer the beam.

### Thread Architecture

| Thread | Responsibility |
|---|---|
| Main (Qt event loop) | UI rendering, camera frame reads, OpenCV drawing |
| QTimer (33ms) | Triggers camera_panel.update_frame() at ~30 fps |
| Audio producer (daemon) | Beamforming computation, queue fill |
| SoundDevice callback | Real-time audio output, queue drain |

The BeamController uses a reentrant lock (RLock) so all four threads can
safely read and write the current angle without data races. The audio queue
(max 4 blocks) decouples the variable-speed producer from the constant-rate
audio callback.

---

## Controls

| UI Control | What It Does |
|---|---|
| Sine Tone / Load WAV | Select the audio source type |
| Browse... | Choose a WAV file from disk |
| Frequency (Hz) | Set the sine tone frequency (100-8000 Hz) |
| Apply Audio Settings | Reload the audio engine with new source settings |
| Steering Mode | Toggle between face tracking (auto) and manual override |
| Manual Angle slider | Set the beam angle manually when in Manual Override mode |
| Smoothing slider | Adjust how quickly the beam tracks the face (0.01 = slow, 1.0 = instant) |
| Run Angle Test | Compute and log beam RMS at -45, 0, and +45 degrees |
| Export Beam Pattern | Save the current polar plot as a PNG to the output folder |
| Export Session CSV | Save all tracked angle and RMS data to a CSV file |
| Camera Index | Select which camera device index to use (0 = default) |
| Restart Camera | Re-initialize the camera at the selected index |
| Enable Audio Output | Start or stop audio playback through the system output device |

---

## Output Files

All output files are written to the `beamface/output/` directory:

- `beam_pattern_YYYYMMDD_HHMMSS.png` — Polar beam pattern snapshot
- `session_YYYYMMDD_HHMMSS.csv` — Per-frame session log with columns:
  timestamp, face_detected, raw_angle, smoothed_angle, beam_angle,
  target_angle, rms_db

Log files are written to `beamface/logs/beamface_YYYYMMDD.log` with
rotating file handler (5 MB max, 3 backups).

---

## Known Limitations

- No physical speaker hardware is required; all audio is simulated in software.
  A stereo headphone or speaker output is sufficient for the rendered output.
- The beam pattern plot updates approximately every 100ms to balance
  visual responsiveness with CPU usage. The actual beamformer update rate
  matches the audio block rate (~21 Hz at 44100 Hz / 2048 samples).
- Distance estimation from face width assumes a fixed focal length of
  600 pixels and an average face width of 14 cm. For accurate results,
  camera calibration with known target dimensions is required.
- Beamforming directivity gain is frequency-dependent. At the default 1 kHz
  tone with 5 cm speaker spacing, the half-wavelength condition
  (lambda/2 = 17 cm) is met at 3430 Hz. Below this frequency the array
  provides meaningful directivity; above it, spatial aliasing introduces
  grating lobes.
- MediaPipe face detection requires an internet connection on first run to
  download model weights. After the initial download, the model is cached
  locally and no further network access is needed.

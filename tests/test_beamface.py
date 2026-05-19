import unittest
import numpy as np
import os
from scipy.io import wavfile

from core.config import SAMPLE_RATE, NUM_SPEAKERS, DEFAULT_FREQUENCY, DEFAULT_DURATION
from core.array_geometry import get_speaker_positions
from core.beamformer import compute_delays, apply_beamforming, compute_pattern_db
from core.renderer import propagate_to_listener, render_stereo
from core.audio_source import generate_sine_tone, load_wav, get_looping_block
from vision.beam_controller import BeamController, FaceData

class TestArrayGeometry(unittest.TestCase):
    def test_get_speaker_positions(self):
        positions = get_speaker_positions()
        self.assertEqual(len(positions), NUM_SPEAKERS)
        # Check center of the array is at 0
        self.assertAlmostEqual(np.mean(positions), 0.0)
        # Check spacing
        spacing = positions[1] - positions[0]
        self.assertAlmostEqual(spacing, 0.05)

class TestBeamformer(unittest.TestCase):
    def test_compute_delays_broadside(self):
        positions = get_speaker_positions()
        delays = compute_delays(0.0, positions)
        np.testing.assert_allclose(delays, 0.0, atol=1e-7)

    def test_compute_delays_steered(self):
        positions = get_speaker_positions()
        delays = compute_delays(30.0, positions)
        # For positive angle (right), delays should increase with speaker index (left to right)
        # so leftmost speaker fires early (negative delay), rightmost fires late (positive delay).
        self.assertTrue(np.all(np.diff(delays) > 0))

    def test_apply_beamforming(self):
        positions = get_speaker_positions()
        signal = generate_sine_tone(1000, 0.1, SAMPLE_RATE)
        speaker_signals = apply_beamforming(signal, 30.0, positions)
        self.assertEqual(speaker_signals.shape, (NUM_SPEAKERS, len(signal)))

    def test_compute_pattern_db(self):
        positions = get_speaker_positions()
        signal = generate_sine_tone(1000, 0.1, SAMPLE_RATE)
        speaker_signals = apply_beamforming(signal, 15.0, positions)
        angles, db_values = compute_pattern_db(speaker_signals, positions)
        # The peak of normalized db_values must be 0.0
        self.assertAlmostEqual(float(np.max(db_values)), 0.0, places=5)

class TestRenderer(unittest.TestCase):
    def test_propagate_to_listener_coherence(self):
        positions = get_speaker_positions()
        signal = generate_sine_tone(1000, 0.1, SAMPLE_RATE)
        # Beam steered at 30 degrees
        speaker_signals = apply_beamforming(signal, 30.0, positions)
        
        # Under correct physical model, propagation to a listener at 30 deg should result in
        # in-phase coherent addition (maximum amplitude), whereas propagation to -30 deg
        # should result in out-of-phase destructive interference (significantly lower amplitude).
        prop_30 = propagate_to_listener(speaker_signals, 30.0, positions)
        prop_neg30 = propagate_to_listener(speaker_signals, -30.0, positions)
        
        peak_30 = np.max(np.abs(prop_30))
        peak_neg30 = np.max(np.abs(prop_neg30))
        self.assertGreater(peak_30, peak_neg30 * 1.5)

    def test_render_stereo_normalization(self):
        positions = get_speaker_positions()
        signal = generate_sine_tone(1000, 0.1, SAMPLE_RATE)
        speaker_signals = apply_beamforming(signal, 30.0, positions)
        
        stereo = render_stereo(speaker_signals, 30.0, positions)
        self.assertEqual(stereo.shape, (len(signal), 2))
        
        # The joint peak of the stereo channels must be exactly 1.0
        peak = np.max(np.abs(stereo))
        self.assertAlmostEqual(peak, 1.0, places=6)

class TestAudioSource(unittest.TestCase):
    def test_generate_sine_tone(self):
        signal = generate_sine_tone(DEFAULT_FREQUENCY, 0.5, SAMPLE_RATE)
        self.assertEqual(len(signal), int(0.5 * SAMPLE_RATE))
        self.assertAlmostEqual(float(np.max(signal)), 1.0, places=4)
        self.assertAlmostEqual(float(np.min(signal)), -1.0, places=4)

    def test_get_looping_block(self):
        signal = np.arange(10, dtype=np.float32)
        # Block size fits within signal
        block = get_looping_block(signal, 0, 4)
        np.testing.assert_allclose(block, [0, 1, 2, 3])
        # Wrap around block
        block_wrap = get_looping_block(signal, 2, 4)
        np.testing.assert_allclose(block_wrap, [8, 9, 0, 1])

    def test_load_wav_resampling(self):
        # Create a temporary WAV file at a different sample rate (e.g. 16000 Hz)
        temp_filename = "temp_test_16k.wav"
        t = np.linspace(0, 0.2, 3200, endpoint=False)
        data = (np.sin(2 * np.pi * 500 * t) * 16384).astype(np.int16)
        
        wavfile.write(temp_filename, 16000, data)
        try:
            loaded_data, loaded_rate = load_wav(temp_filename)
            self.assertEqual(loaded_rate, SAMPLE_RATE)
            self.assertEqual(len(loaded_data), int(0.2 * SAMPLE_RATE))
        finally:
            if os.path.exists(temp_filename):
                os.remove(temp_filename)

class TestBeamController(unittest.TestCase):
    def test_modes_and_smoothing(self):
        controller = BeamController()
        self.assertEqual(controller.mode, "auto")
        
        # Update from face detection in auto mode
        face_data = FaceData(detected=True, angle_deg=25.0, distance_cm=150.0)
        controller.update_from_face(face_data)
        self.assertTrue(controller.face_detected)
        self.assertAlmostEqual(controller.get_target_angle(), 25.0, places=1)
        
        # Switch to manual mode
        controller.set_mode("manual")
        self.assertEqual(controller.mode, "manual")
        
        # Manually set target
        controller.set_target(42.0)
        self.assertAlmostEqual(controller.get_target_angle(), 42.0)
        
        # Update from face detection in manual mode should NOT overwrite target
        face_data_new = FaceData(detected=True, angle_deg=-10.0, distance_cm=120.0)
        controller.update_from_face(face_data_new)
        self.assertTrue(controller.face_detected)  # Status updates
        self.assertAlmostEqual(controller.get_target_angle(), 42.0)  # Target is unchanged!

        # Lerp steps towards target
        controller.set_smoothing(0.5)
        controller.lerp_step()
        self.assertAlmostEqual(controller.get_current_angle(), 21.0, places=1)

if __name__ == "__main__":
    unittest.main()

"""
Real-time audio engine for BeamFace.

Runs a producer thread that continuously generates beamformed stereo audio
blocks and enqueues them. A SoundDevice callback drains the queue and writes
to the audio output device. The architecture decouples signal processing from
the real-time audio callback to avoid underruns.
"""

import queue
import threading
import logging
import traceback
import subprocess
import time

import numpy as np

from core.config import SAMPLE_RATE, BLOCK_SIZE, DEFAULT_FREQUENCY, DEFAULT_DURATION
from core.array_geometry import get_speaker_positions
from core.audio_source import generate_sine_tone, load_wav, get_looping_block
from core.beamformer import apply_beamforming
from core.renderer import render_stereo, compute_rms_db

logger = logging.getLogger("beamface.audio_engine")


class PulseAudioHelper:
    def __init__(self):
        self.original_sink = None
        self.original_source = None
        self.module_id = None
        self.is_configured = False

    def setup(self):
        """Set up the virtual sink and route system audio to it."""
        try:
            # 1. Get current default sink and source
            self.original_sink = subprocess.check_output(
                ["pactl", "get-default-sink"], text=True
            ).strip()
            try:
                self.original_source = subprocess.check_output(
                    ["pactl", "get-default-source"], text=True
                ).strip()
            except Exception:
                self.original_source = None

            logger.info("Original default sink: %s", self.original_sink)
            logger.info("Original default source: %s", self.original_source)

            # 2. Check if beamface_sink is already loaded
            sinks = subprocess.check_output(["pactl", "list", "sinks", "short"], text=True)
            if "beamface_sink" not in sinks:
                # Load the null sink module
                out = subprocess.check_output([
                    "pactl", "load-module", "module-null-sink",
                    "sink_name=beamface_sink",
                    "sink_properties=device.description=BeamFace_Virtual_Sink"
                ], text=True)
                self.module_id = out.strip()
                logger.info("Loaded virtual sink module, ID: %s", self.module_id)
                # Wait a small moment for the device to register
                time.sleep(0.5)
            else:
                logger.info("Virtual sink 'beamface_sink' is already loaded.")

            # 3. Route system audio to the virtual sink
            subprocess.check_call(["pactl", "set-default-sink", "beamface_sink"])
            subprocess.check_call(["pactl", "set-default-source", "beamface_sink.monitor"])
            logger.info("System audio successfully routed to BeamFace_Virtual_Sink.")
            self.is_configured = True

        except Exception as e:
            logger.error("Failed to configure PulseAudio routing: %s", e)
            self.restore()

    def restore(self):
        """Restore the original audio routing."""
        if not self.is_configured:
            return
        try:
            if self.original_sink:
                subprocess.check_call(["pactl", "set-default-sink", self.original_sink])
                logger.info("Restored default sink to: %s", self.original_sink)
            if self.original_source:
                subprocess.check_call(["pactl", "set-default-source", self.original_source])
                logger.info("Restored default source to: %s", self.original_source)
            self.is_configured = False
        except Exception as e:
            logger.error("Failed to restore PulseAudio routing: %s", e)


class AudioEngine:
    """
    Manages real-time beamformed audio generation and playback.

    The engine runs two threads:
      - A producer thread that applies beamforming and fills a queue.
      - A SoundDevice callback thread that reads from the queue.

    The BeamController reference allows the producer to query the current
    steering angle on every block, enabling sub-50ms beam tracking latency.
    """

    def __init__(self, beam_controller_ref):
        """Initialize the AudioEngine with a reference to the BeamController."""
        self.beam_controller = beam_controller_ref
        self.speaker_positions = get_speaker_positions()
        self.sample_rate = SAMPLE_RATE
        self.block_size = BLOCK_SIZE
        self.audio_queue = queue.Queue(maxsize=4)
        self.is_running = False
        self.source_signal = None
        self.block_index = 0
        self.stream = None
        self._producer_thread = None
        self.source_mode = "sine"
        self.pa_helper = PulseAudioHelper()

    def set_source_mode(self, mode: str):
        """Set the audio source mode ('sine', 'wav', or 'system')."""
        self.source_mode = mode
        logger.info("Audio source mode set to: %s", mode)

    def load_source(self, filepath: str = None, frequency: float = DEFAULT_FREQUENCY):
        """
        Load or generate the audio source signal.

        Parameters
        ----------
        filepath : str or None
            Path to a WAV file. If None, a sine tone is generated.
        frequency : float
            Frequency in Hz for the generated sine tone (ignored if filepath given).
        """
        if filepath:
            try:
                signal, _ = load_wav(filepath)
                self.source_signal = signal
                self.source_mode = "wav"
                logger.info("Loaded audio source from file: %s", filepath)
            except Exception as exc:
                logger.error("Failed to load WAV file: %s", exc)
                self.source_signal = generate_sine_tone(frequency, DEFAULT_DURATION, self.sample_rate)
                self.source_mode = "sine"
                logger.info("Falling back to generated sine tone at %.1f Hz", frequency)
        else:
            self.source_signal = generate_sine_tone(frequency, DEFAULT_DURATION, self.sample_rate)
            self.source_mode = "sine"
            logger.info("Generated sine tone source at %.1f Hz", frequency)

    def producer_loop(self):
        """
        Background daemon thread: continuously generate and enqueue audio blocks.

        On each iteration, queries the beam controller for the current steering
        angle, applies beamforming, renders to stereo, and pushes to the queue.
        """
        logger.info("Audio producer thread started")
        while self.is_running:
            try:
                if self.source_signal is None:
                    self.load_source()

                block = get_looping_block(
                    self.source_signal, self.block_index, self.block_size
                )
                angle = self.beam_controller.get_current_angle()

                speaker_signals = apply_beamforming(
                    block, angle, self.speaker_positions
                )
                stereo = render_stereo(speaker_signals, angle, self.speaker_positions)

                # Update RMS in the beam controller for UI display (thread-safe)
                rms_db = compute_rms_db(stereo)
                self.beam_controller.set_rms_db(rms_db)

                try:
                    self.audio_queue.put(stereo, timeout=0.1)
                except queue.Full:
                    pass  # Skip block if consumer is stalled; prevents backpressure

                self.block_index += 1

            except Exception:
                logger.error(
                    "Exception in audio producer thread:\n%s", traceback.format_exc()
                )

        logger.info("Audio producer thread stopped")

    def audio_callback(self, outdata, frames, time_info, status):
        """
        SoundDevice real-time callback: write queued audio blocks to output.

        Called by the audio driver on a high-priority thread. Must return quickly.
        If the queue is empty, writes silence to avoid glitches.
        """
        if status:
            logger.warning("SoundDevice callback status: %s", status)

        try:
            block = self.audio_queue.get_nowait()
            if len(block) == frames:
                outdata[:] = block
            else:
                # Block size mismatch fallback: silence
                outdata[:] = np.zeros((frames, 2), dtype=np.float32)
        except queue.Empty:
            outdata[:] = np.zeros((frames, 2), dtype=np.float32)

    def system_audio_callback(self, indata, outdata, frames, time_info, status):
        """
        SoundDevice real-time duplex callback for system audio routing.
        """
        if status:
            logger.warning("SoundDevice duplex callback status: %s", status)

        try:
            # 1. Convert input block to mono
            if indata.shape[1] > 1:
                mono_input = indata.mean(axis=1)
            else:
                mono_input = indata[:, 0]

            # 2. Get steering angle from controller
            angle = self.beam_controller.get_current_angle()

            # 3. Apply beamforming & render stereo
            speaker_signals = apply_beamforming(mono_input, angle, self.speaker_positions)
            stereo = render_stereo(speaker_signals, angle, self.speaker_positions)

            # 4. Write to output buffer
            outdata[:] = stereo

            # 5. Update RMS level for UI
            rms_db = compute_rms_db(stereo)
            self.beam_controller.set_rms_db(rms_db)

        except Exception:
            logger.error("Exception in system audio callback:\n%s", traceback.format_exc())
            outdata[:] = np.zeros((frames, 2), dtype=np.float32)

    def find_devices(self):
        """Find the virtual input sink monitor and physical output device."""
        try:
            import sounddevice as sd
            devices = sd.query_devices()
        except Exception as exc:
            logger.error("Failed to query audio devices: %s", exc)
            return None, None

        input_idx = None
        output_idx = None

        # Look for the virtual sink monitor
        for idx, dev in enumerate(devices):
            name = dev.get('name', '')
            max_inputs = dev.get('max_input_channels', 0)
            if max_inputs > 0 and ("beamface_sink.monitor" in name or "BeamFace_Virtual_Sink.monitor" in name or "BeamFace_Audio_Sink.monitor" in name):
                input_idx = idx
                break

        # Fallback to default devices if not found
        try:
            default_devices = sd.default.device
            if input_idx is None:
                input_idx = default_devices[0]
            output_idx = default_devices[1]
        except Exception:
            logger.error("Failed to get default audio devices.")
            
        return input_idx, output_idx

    def start(self):
        """Start the audio engine using either system duplex routing or local generator."""
        if self.is_running:
            logger.warning("AudioEngine.start() called while already running")
            return

        self.is_running = True
        self.block_index = 0

        if self.source_mode == "system":
            try:
                # 1. Setup PulseAudio routing
                self.pa_helper.setup()

                # 2. Find proper devices
                import sounddevice as sd
                output_device = self.find_physical_output()
                input_device = "default"

                logger.info("Using system audio duplex devices: input=%s, output=%s", input_device, output_device)

                self.stream = sd.Stream(
                    device=(input_device, output_device),
                    samplerate=self.sample_rate,
                    blocksize=self.block_size,
                    dtype=np.float32,
                    channels=(2, 2),  # Stereo input, stereo output
                    callback=self.system_audio_callback,
                )
                self.stream.start()
                logger.info("Real-time system audio duplex stream started.")
            except Exception:
                logger.error(
                    "Failed to open duplex audio stream for system routing:\n%s",
                    traceback.format_exc()
                )
                self.is_running = False
        else:
            if self.source_signal is None:
                self.load_source()

            # Drain the queue to ensure no stale audio blocks are played
            while not self.audio_queue.empty():
                try:
                    self.audio_queue.get_nowait()
                except queue.Empty:
                    break

            self._producer_thread = threading.Thread(
                target=self.producer_loop, daemon=True, name="AudioProducer"
            )
            self._producer_thread.start()

            try:
                import sounddevice as sd
                self.stream = sd.OutputStream(
                    samplerate=self.sample_rate,
                    channels=2,
                    blocksize=self.block_size,
                    dtype=np.float32,
                    callback=self.audio_callback,
                )
                self.stream.start()
                logger.info(
                    "Audio stream started: %d Hz, block size %d", self.sample_rate, self.block_size
                )
            except Exception:
                logger.error(
                    "Failed to open audio output stream:\n%s", traceback.format_exc()
                )
                self.is_running = False

    def find_physical_output(self):
        """Find the physical output hardware card (bypassing virtual loopback)."""
        try:
            import sounddevice as sd
            devices = sd.query_devices()
        except Exception as exc:
            logger.error("Failed to query audio devices: %s", exc)
            return None

        # 1. Search for front output
        for idx, dev in enumerate(devices):
            if dev.get('max_output_channels', 0) > 0 and dev.get('name', '') == 'front':
                return idx
        # 2. Search for PCH card Analog
        for idx, dev in enumerate(devices):
            name = dev.get('name', '')
            if dev.get('max_output_channels', 0) > 0 and ('Analog' in name or 'hw:0,0' in name or 'ALC897' in name):
                return idx
        # 3. Fallback to default output
        try:
            return sd.default.device[1]
        except Exception:
            return None

    def stop(self):
        """Stop the audio producer thread and close the SoundDevice stream."""
        self.is_running = False

        # Wait for the producer thread to finish before closing the stream so
        # it does not attempt a queue.put() after the stream is gone.
        if self._producer_thread is not None and self._producer_thread.is_alive():
            self._producer_thread.join(timeout=2.0)
            self._producer_thread = None

        if self.stream is not None:
            try:
                self.stream.stop()
                self.stream.close()
                logger.info("Audio stream closed")
            except Exception:
                logger.error(
                    "Error closing audio stream:\n%s", traceback.format_exc()
                )
            self.stream = None

        # Restore original system audio routing settings
        self.pa_helper.restore()

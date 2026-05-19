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


import numpy as np

from core.config import SAMPLE_RATE, BLOCK_SIZE, DEFAULT_FREQUENCY, DEFAULT_DURATION
from core.array_geometry import get_speaker_positions
from core.audio_source import generate_sine_tone, load_wav, get_looping_block
from core.beamformer import apply_beamforming
from core.renderer import render_stereo, compute_rms_db

logger = logging.getLogger("beamface.audio_engine")


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
                logger.info("Loaded audio source from file: %s", filepath)
            except Exception as exc:
                logger.error("Failed to load WAV file: %s", exc)
                self.source_signal = generate_sine_tone(frequency, DEFAULT_DURATION, self.sample_rate)
                logger.info("Falling back to generated sine tone at %.1f Hz", frequency)
        else:
            self.source_signal = generate_sine_tone(frequency, DEFAULT_DURATION, self.sample_rate)
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

    def start(self):
        """Start the audio producer thread and open the SoundDevice output stream."""
        if self.is_running:
            logger.warning("AudioEngine.start() called while already running")
            return

        if self.source_signal is None:
            self.load_source()

        self.is_running = True
        self.block_index = 0

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
            
            # pyrefly: ignore [missing-import]
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

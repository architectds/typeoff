"""Continuous audio recorder with ring buffer and callback."""
import threading
import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000


class Recorder:
    """Records audio continuously, makes the growing buffer available."""

    def __init__(self, sr=SAMPLE_RATE, max_duration=30):
        self.sr = sr
        self.max_duration = max_duration
        self._buffer = []
        self._lock = threading.Lock()
        self._stream = None
        self._recording = False

    def _callback(self, indata, frames, time_info, status):
        """sounddevice callback — runs in audio thread."""
        with self._lock:
            self._buffer.append(indata[:, 0].copy())

    def start(self):
        """Start recording."""
        with self._lock:
            self._buffer = []
        self._recording = True
        self._stream = sd.InputStream(
            samplerate=self.sr,
            channels=1,
            dtype="float32",
            callback=self._callback,
            blocksize=int(self.sr * 0.1),  # 100ms blocks
        )
        self._stream.start()

    def stop(self):
        """Stop recording, return full audio."""
        self._recording = False
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        return self.get_audio()

    def get_audio(self):
        """Get current audio buffer as a single numpy array."""
        with self._lock:
            if not self._buffer:
                return np.array([], dtype=np.float32)
            return np.concatenate(self._buffer)

    def get_duration(self):
        """Get current recording duration in seconds."""
        with self._lock:
            total = sum(len(chunk) for chunk in self._buffer)
        return total / self.sr

    @property
    def is_recording(self):
        return self._recording

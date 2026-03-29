"""Continuous audio recorder with ring buffer and callback."""
import threading
import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000


class Recorder:
    """Records audio continuously, makes the growing buffer available."""

    def __init__(self, sr=SAMPLE_RATE, max_duration=30, device=None):
        self.sr = sr
        self.max_duration = max_duration
        self.device = device
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
            device=self.device,
        )
        self._stream.start()

    def stop(self):
        """Stop recording, return full audio and release buffer."""
        self._recording = False
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        audio = self.get_audio()
        with self._lock:
            self._buffer = []
        return audio

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

    def trim_before(self, sample_index):
        """Release audio buffer before sample_index to free memory."""
        with self._lock:
            if not self._buffer:
                return
            # Find which chunks to drop
            total = 0
            drop = 0
            for i, chunk in enumerate(self._buffer):
                total += len(chunk)
                if total >= sample_index:
                    drop = i
                    break
            if drop > 0:
                self._buffer = self._buffer[drop:]

    @property
    def is_recording(self):
        return self._recording

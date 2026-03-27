"""Voice Activity Detection — only checks the tail of audio."""
import numpy as np

SAMPLE_RATE = 16000


class VAD:
    """Detects speech end via RMS energy on the tail only."""

    def __init__(self, silence_threshold=0.001, silence_duration=8.0, sr=SAMPLE_RATE):
        self.silence_threshold = silence_threshold  # very low — some mics are quiet
        self.silence_duration = silence_duration
        self.sr = sr

    def is_silence(self, audio_chunk):
        if len(audio_chunk) == 0:
            return True
        rms = np.sqrt(np.mean(audio_chunk ** 2))
        return rms < self.silence_threshold

    def detect_end_of_speech(self, full_audio):
        """Check if audio TAIL has enough silence. Only reads last N seconds."""
        silence_samples = int(self.silence_duration * self.sr)
        if len(full_audio) < silence_samples:
            return False

        # Only look at the tail — not the whole buffer
        tail = full_audio[-silence_samples:]
        window = int(0.5 * self.sr)  # 500ms windows (fewer checks)
        for i in range(0, len(tail), window):
            chunk = tail[i:i + window]
            if not self.is_silence(chunk):
                return False
        return True

    def has_speech(self, full_audio, min_speech_duration=0.3):
        """Check if audio contains any speech. Only scans first 10s + last 10s."""
        window = int(0.2 * self.sr)
        needed = int(min_speech_duration / 0.2)
        speech_windows = 0

        # Only scan first 10s and last 10s (not entire buffer)
        scan_samples = int(10 * self.sr)
        if len(full_audio) > scan_samples * 2:
            regions = [full_audio[:scan_samples], full_audio[-scan_samples:]]
        else:
            regions = [full_audio]

        for region in regions:
            for i in range(0, len(region), window):
                chunk = region[i:i + window]
                if not self.is_silence(chunk):
                    speech_windows += 1
                if speech_windows >= needed:
                    return True
        return False

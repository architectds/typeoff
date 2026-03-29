"""Human voice bandpass filter — keep 50Hz-3400Hz, cut everything else."""
import numpy as np
from scipy.signal import butter, sosfilt

# Human voice frequency range
LOW_CUT = 50      # Hz — generous low end, catches all voice fundamentals
HIGH_CUT = 3400   # Hz — upper harmonics for clarity, sibilance (s/z) up to ~4kHz

def _design_filter(sr=16000, order=5):
    """Design a Butterworth bandpass filter."""
    nyq = sr / 2
    low = LOW_CUT / nyq
    high = min(HIGH_CUT / nyq, 0.99)  # can't exceed Nyquist
    return butter(order, [low, high], btype='band', output='sos')

# Pre-compute for 16kHz (most common)
_SOS_16K = _design_filter(16000)

def voice_filter(audio, sr=16000):
    """Apply bandpass filter to keep only human voice frequencies.

    Args:
        audio: numpy float32 array
        sr: sample rate

    Returns:
        filtered numpy float32 array (same length)
    """
    if len(audio) < 100:
        return audio

    if sr == 16000:
        sos = _SOS_16K
    else:
        sos = _design_filter(sr)

    return sosfilt(sos, audio).astype(np.float32)

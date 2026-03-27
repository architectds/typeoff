"""Windows/Linux backend: faster-whisper (CTranslate2, CUDA/CPU)."""
import numpy as np


class FasterBackend:
    def __init__(self, model_name="small"):
        self.model_name = model_name
        self._model = None

    def load(self):
        """Pre-load model into memory."""
        if self._model is not None:
            return
        from faster_whisper import WhisperModel

        device, compute = "cpu", "int8"

        self._model = WhisperModel(
            self.model_name,
            device=device,
            compute_type=compute,
        )
        print(f"[typeoff] faster-whisper loaded: {self.model_name} on {device}")

    def transcribe(self, audio, sr=16000, language=None):
        """Transcribe audio array → text."""
        if self._model is None:
            self.load()

        opts = {"beam_size": 1, "vad_filter": False}
        if language:
            opts["language"] = language

        segments, _ = self._model.transcribe(audio, **opts)
        return " ".join(seg.text.strip() for seg in segments)

    @property
    def name(self):
        return f"faster-whisper ({self.model_name})"

"""Mac backend: mlx-whisper (Metal GPU acceleration)."""
import numpy as np


class MLXBackend:
    def __init__(self, model_name="small"):
        self.model_name = f"mlx-community/whisper-{model_name}-mlx"
        self._loaded = False

    def load(self):
        """Pre-load model into memory."""
        if self._loaded:
            return
        import mlx_whisper
        # Warm up with a tiny silent clip to force model load
        dummy = np.zeros(16000, dtype=np.float32)  # 1s silence
        mlx_whisper.transcribe(dummy, path_or_hf_repo=self.model_name)
        self._loaded = True
        print(f"[typeoff] MLX model loaded: {self.model_name}")

    def transcribe(self, audio, sr=16000, language=None):
        """Transcribe audio array → text.

        Args:
            audio: numpy float32 array, mono, at sample rate sr
            sr: sample rate (default 16000)
            language: language hint (e.g. "en", "zh") or None for auto-detect

        Returns:
            str: transcribed text
        """
        import mlx_whisper

        opts = {
            "path_or_hf_repo": self.model_name,
            "fp16": True,
            "verbose": False,
        }
        if language:
            opts["language"] = language

        result = mlx_whisper.transcribe(audio, **opts)
        return result.get("text", "").strip()

    @property
    def name(self):
        return f"MLX ({self.model_name})"

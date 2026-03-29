"""Windows/Linux backend: faster-whisper (CTranslate2, CUDA/CPU)."""
import os
import sys
import glob
import numpy as np

# Add NVIDIA DLL paths (pip-installed CUDA libs) to PATH on Windows
if sys.platform == "win32":
    site_packages = os.path.join(os.path.dirname(sys.executable), "Lib", "site-packages", "nvidia")
    for dll_dir in glob.glob(os.path.join(site_packages, "*", "bin")):
        os.environ["PATH"] = dll_dir + os.pathsep + os.environ.get("PATH", "")

# Models natively supported by faster-whisper (Systran fp16, runtime int8)
# These are passed directly by name — no manual download needed
NATIVE_MODELS = {
    "tiny", "base", "small", "medium",
    "large-v2", "large-v3", "large-v3-turbo",
    "distil-large-v2", "distil-large-v3",
}


class FasterBackend:
    def __init__(self, model_name="small"):
        self.model_name = model_name
        self._model = None

    def load(self):
        """Pre-load model into memory."""
        if self._model is not None:
            return
        from faster_whisper import WhisperModel
        import ctranslate2

        # Auto-detect CUDA
        device, compute = "cpu", "int8"
        try:
            cuda_types = ctranslate2.get_supported_compute_types("cuda")
            if cuda_types:
                device = "cuda"
                # Prefer int8_float16 (Turing+), fallback to int8 (Pascal)
                if "int8_float16" in cuda_types:
                    compute = "int8_float16"
                else:
                    compute = "int8"
                pass  # CUDA detected
        except Exception:
            pass  # CPU fallback

        self._model = WhisperModel(
            self.model_name,
            device=device,
            compute_type=compute,
        )

    def transcribe(self, audio, sr=16000, language=None):
        """Transcribe audio array → text."""
        if self._model is None:
            self.load()

        opts = {
            "beam_size": 1,
            "vad_filter": False,
            "initial_prompt": "以下是一段语音转录。",
        }
        if language:
            opts["language"] = language

        segments, _ = self._model.transcribe(audio, **opts)
        return " ".join(seg.text.strip() for seg in segments)

    @property
    def name(self):
        device = "GPU" if self._model and str(getattr(self._model, 'device', 'cpu')) != 'cpu' else "CPU"
        return f"faster-whisper ({self.model_name}, {device})"

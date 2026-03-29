"""Auto-select Whisper backend by platform."""
import platform

def get_backend(model_name="small"):
    system = platform.system()
    if system == "Darwin":
        from .mlx_backend import MLXBackend
        return MLXBackend(model_name)
    else:
        from .faster_backend import FasterBackend
        return FasterBackend(model_name)

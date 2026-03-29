#!/usr/bin/env python3
"""
Typeoff — Offline Speech-to-Text Tool for Windows
Webview UI + system tray + global hotkey (Ctrl+Space) + auto-paste.

NOTE: Never call window.evaluate_js() from background threads — it deadlocks
pywebview on Windows. All state sync is done via JS polling get_state().
"""

import sys
import os
import time
import json
import threading
import platform
import webview
import numpy as np
import sounddevice as sd

_verbose = False

def log(msg):
    """Print only in verbose mode."""
    if _verbose:
        print(msg)

from backends import get_backend
from engine.recorder import Recorder
from engine.vad import VAD
from engine.streamer import StreamingTranscriber
from engine.paster import paste_text
from engine.audio_filter import voice_filter
from engine.corrector import Corrector

# ─── Paths ────────────────────────────────────────────────────────
APP_DIR = os.path.dirname(os.path.abspath(__file__))
UI_DIR = os.path.join(APP_DIR, "ui")
CONFIG_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "Typeoff")
CONFIG_FILE = os.path.join(CONFIG_DIR, "settings.json")

DEFAULT_CONFIG = {
    "model": "distil-large-v3",
    "language": "auto",
    "hotkey": "double_shift",
    "record_mode": "toggle",
    "auto_paste": True,
    "auto_stop_silence": True,
    "silence_duration": 2.0,
    "max_duration": 60,
    "input_device": None,
    "theme": "dark",
    "start_minimized": False,
    "verbose": False,
    "correction_mode": "off",           # "off" | "local" | "api"
    "correction_model": "Qwen/Qwen2.5-0.5B-Instruct",
    "correction_api_url": "",
    "correction_api_key": "",
}

MODELS = [
    {"id": "distil-large-v3", "name": "Distil Large v3", "desc": "~750MB, fast + accurate (English only)"},
    {"id": "large-v3-turbo",  "name": "Large v3 Turbo",  "desc": "~800MB, fast + accurate (multilingual)"},
    {"id": "small",           "name": "Small",           "desc": "~460MB, good balance (multilingual)"},
    {"id": "base",            "name": "Base",            "desc": "~140MB, fast, basic accuracy"},
    {"id": "tiny",            "name": "Tiny",            "desc": "~75MB, fastest, lower accuracy"},
    {"id": "medium",          "name": "Medium",          "desc": "~1.5GB, high accuracy (recommended)"},
    {"id": "large-v3",        "name": "Large v3",        "desc": "~3GB, best accuracy, slowest"},
]

LANGUAGES = [
    {"id": "auto", "name": "Auto-detect"},
    {"id": "en",   "name": "English"},
    {"id": "zh",   "name": "Chinese / \u4e2d\u6587"},
    {"id": "ja",   "name": "Japanese / \u65e5\u672c\u8a9e"},
    {"id": "ko",   "name": "Korean / \ud55c\uad6d\uc5b4"},
    {"id": "es",   "name": "Spanish / Espa\u00f1ol"},
    {"id": "fr",   "name": "French / Fran\u00e7ais"},
    {"id": "de",   "name": "German / Deutsch"},
    {"id": "ru",   "name": "Russian / \u0420\u0443\u0441\u0441\u043a\u0438\u0439"},
    {"id": "pt",   "name": "Portuguese / Portugu\u00eas"},
    {"id": "ar",   "name": "Arabic / \u0627\u0644\u0639\u0631\u0628\u064a\u0629"},
    {"id": "it",   "name": "Italian / Italiano"},
]

HOTKEY_OPTIONS = [
    {"id": "double_shift",     "name": "Double Shift (recommended)"},
    {"id": "ctrl+shift+space", "name": "Ctrl + Shift + Space"},
    {"id": "ctrl+space",       "name": "Ctrl + Space"},
]


def load_config():
    config = DEFAULT_CONFIG.copy()
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config.update(json.load(f))
    except Exception:
        pass
    return config


def save_config(config):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def list_input_devices():
    devices = []
    try:
        for i, dev in enumerate(sd.query_devices()):
            if dev["max_input_channels"] > 0:
                devices.append({"id": i, "name": dev["name"]})
    except Exception:
        pass
    return devices


# ─── JS Bridge ───────────────────────────────────────────────────
class Api:
    def __init__(self, app):
        self._app = app

    def toggle_recording(self):
        self._app.toggle()

    def get_state(self):
        return self._app.get_state()

    def get_config(self):
        return self._app.config

    def save_config(self, new_config):
        return self._app.apply_config(new_config)

    def get_models(self):
        return MODELS

    def get_languages(self):
        return LANGUAGES

    def get_hotkeys(self):
        return HOTKEY_OPTIONS

    def get_input_devices(self):
        return list_input_devices()

    def minimize_window(self):
        self._app.minimize()

    def quit(self):
        self._app.quit()


# ─── Hotkey ──────────────────────────────────────────────────────
def _parse_hotkey(hotkey_str):
    from pynput import keyboard
    parts = hotkey_str.lower().split("+")
    keys = set()
    for p in parts:
        p = p.strip()
        if p == "ctrl":
            keys.add(keyboard.Key.ctrl_l)
        elif p == "shift":
            keys.add(keyboard.Key.shift_l)
        elif p == "alt":
            keys.add(keyboard.Key.alt_l)
        elif p == "space":
            keys.add(keyboard.Key.space)
        elif p.startswith("f") and p[1:].isdigit():
            keys.add(getattr(keyboard.Key, p))
        elif len(p) == 1 and p.isalpha():
            keys.add(keyboard.KeyCode.from_char(p))
    return keys


# ─── Main App ────────────────────────────────────────────────────
class TypeoffApp:
    def __init__(self):
        self.config = load_config()
        global _verbose
        _verbose = self.config.get("verbose", False) or "--verbose" in sys.argv or "-v" in sys.argv
        self.backend = None
        self.corrector = Corrector(self.config)
        self._active = False
        self._lock = threading.Lock()
        self._model_ready = False
        self._window = None
        self._mini_root = None
        self._mini_visible = False
        self._listener = None
        self._hotkey_keys = set()

        # State dict — JS polls this via get_state(), never pushed
        self._state = {
            "status": "loading",
            "text": "",
            "elapsed": 0,
            "message": "Loading model...",
        }

    def get_state(self):
        return dict(self._state)

    def _update_state(self, **kwargs):
        """Update state dict. JS will pick it up on next poll."""
        self._state.update(kwargs)

    def _load_model(self):
        model = self.config["model"]
        self._update_state(status="loading", message=f"Loading {model} model...")
        self.backend = get_backend(model)
        self.backend.load()
        self._model_ready = True
        self._update_state(status="ready", message=f"Ready \u2014 {self.backend.name}")
        log(f"[typeoff] Model loaded: {self.backend.name}")

    def apply_config(self, new_config):
        old_model = self.config["model"]
        old_hotkey = self.config["hotkey"]
        self.config.update(new_config)
        save_config(self.config)
        # Update verbose mode live
        global _verbose
        _verbose = self.config.get("verbose", False)
        log(f"[typeoff] Settings saved: hotkey={self.config['hotkey']} (was {old_hotkey})")

        if new_config.get("model") and new_config["model"] != old_model:
            self._model_ready = False
            threading.Thread(target=self._load_model, daemon=True).start()

        new_hotkey = new_config.get("hotkey", "")
        if new_hotkey and new_hotkey != old_hotkey:
            log(f"[typeoff] Rebinding hotkey: {old_hotkey} → {new_hotkey}")
            self._setup_hotkey()

        return {"ok": True, "message": "Settings saved"}

    def toggle(self):
        with self._lock:
            if self._active:
                self._active = False
            else:
                if not self._model_ready:
                    return
                self._active = True
                threading.Thread(target=self._session, daemon=True).start()

    def _paste_to_target(self, text):
        if not text:
            return
        if self._window:
            self._window.minimize()
        time.sleep(0.3)
        paste_text(text)
        # Don't restore — stay in the target app, user can bring back Typeoff via hotkey or tray

    def _session(self):
        cfg = self.config
        lang = cfg["language"] if cfg["language"] != "auto" else None
        silence_dur = float(cfg.get("silence_duration") or 2.0)
        max_dur = int(cfg.get("max_duration") or 60)

        recorder = Recorder(max_duration=max_dur, device=cfg["input_device"])
        vad = VAD(silence_duration=silence_dur)
        streamer = StreamingTranscriber(self.backend, interval=3.0)

        self._update_state(status="recording", text="", elapsed=0, message="Listening...")
        self.show_mini()
        silence_detected = threading.Event()
        start_time = time.time()

        def vad_watcher():
            while self._active and recorder and recorder.is_recording:
                audio = recorder.get_audio()
                duration = recorder.get_duration()
                if duration > max_dur:
                    silence_detected.set()
                    return
                if cfg["auto_stop_silence"] and duration > silence_dur + 1.0:
                    if vad.has_speech(audio) and vad.detect_end_of_speech(audio):
                        silence_detected.set()
                        return
                time.sleep(0.2)

        def time_updater():
            while self._active and recorder and recorder.is_recording:
                try:
                    elapsed = round(time.time() - start_time, 1)
                    spectrum = []
                    rms = 0.0
                    audio = recorder.get_audio()
                    if len(audio) > 2048:
                        # RMS from last 100ms
                        rms = float(np.sqrt(np.mean(audio[-1600:] ** 2)))
                        # FFT spectrum
                        chunk = audio[-2048:]
                        fft = np.abs(np.fft.rfft(chunk * np.hanning(len(chunk))))
                        n = len(fft)
                        bands = 16
                        for i in range(bands):
                            lo = int(n * (2 ** (i / bands * 4)) / (2 ** 4))
                            hi = int(n * (2 ** ((i + 1) / bands * 4)) / (2 ** 4))
                            lo, hi = max(0, lo), min(n, max(lo + 1, hi))
                            val = float(np.mean(fft[lo:hi])) if hi > lo else 0.0
                            spectrum.append(val)
                        peak = max(spectrum) if spectrum else 1.0
                        if peak > 0:
                            spectrum = [min(1.0, v / peak) for v in spectrum]
                    self._update_state(elapsed=elapsed, rms=rms, spectrum=spectrum)
                except Exception:
                    pass
                time.sleep(0.15)

        try:
            recorder.start()
            threading.Thread(target=vad_watcher, daemon=True).start()
            threading.Thread(target=time_updater, daemon=True).start()

            last_transcribe_time = 0

            while self._active and not silence_detected.is_set():
                duration = recorder.get_duration()
                if duration < 1.5:
                    time.sleep(0.2)
                    continue

                now = time.time()
                if now - last_transcribe_time < 3.0:
                    if silence_detected.wait(timeout=0.3):
                        break
                    continue

                raw_audio = recorder.get_audio()
                if not vad.has_speech(raw_audio):
                    time.sleep(0.3)
                    continue

                audio = voice_filter(raw_audio)
                new_sentence, pending = streamer.rolling_transcribe(audio, language=lang)
                last_transcribe_time = time.time()

                # Paste locked sentence directly (no window minimize — target app has focus)
                if new_sentence and cfg["auto_paste"]:
                    if self.corrector.enabled:
                        new_sentence = self.corrector.correct(new_sentence)
                    paste_text(new_sentence)
                    log(f"[typeoff] pasted: \"{new_sentence}\"")

                # Show live text: locked + latest raw transcription
                from engine.streamer import _join_tokens
                raw_current = _join_tokens(streamer._prev_words)
                if raw_current:
                    display = (streamer._locked_text + raw_current).strip()
                else:
                    display = streamer.get_all_text()

                if display:
                    self._update_state(text=display)
                    log(f"[typeoff] streaming: \"{display}\"")

            # Final pass
            self._update_state(status="transcribing", message="Transcribing...")
            raw_audio = recorder.stop()

            if not vad.has_speech(raw_audio):
                self._update_state(status="ready", message="No speech detected", text="")
                return

            audio = voice_filter(raw_audio)
            del raw_audio
            final_remainder, full_text = streamer.final_transcribe(audio, language=lang)
            # Release audio immediately after final transcription
            del audio
            self._update_state(status="done", text=full_text, message="Pasting...")

            if cfg["auto_paste"] and final_remainder:
                if self.corrector.enabled:
                    final_remainder = self.corrector.correct(final_remainder)
                paste_text(final_remainder)
                log(f"[typeoff] pasted final: \"{final_remainder}\"")

            self._update_state(message="Done!")
            log(f'[typeoff] Done: "{full_text}"')

            time.sleep(2)
            self._update_state(status="ready", message="Ready", text="")

        except Exception as e:
            import traceback
            print(f"[typeoff] Error: {e}")
            traceback.print_exc()
            self._update_state(status="error", message=str(e))
        finally:
            # Clean up all resources
            try:
                recorder.stop()
            except Exception:
                pass
            try:
                streamer.reset()
            except Exception:
                pass
            # Release local references
            recorder = None
            vad = None
            streamer = None
            # Clear spectrum/rms from state
            self._update_state(spectrum=[], rms=0.0)
            # Force garbage collection
            import gc
            gc.collect()
            self._active = False
            time.sleep(1.5)
            self.hide_mini()

    def _setup_hotkey(self):
        from pynput import keyboard

        if self._listener:
            self._listener.stop()

        hotkey_id = self.config["hotkey"]
        is_double_shift = hotkey_id == "double_shift"

        if is_double_shift:
            last_shift_release = [0]
            shift_was_solo = [False]  # True if no other key was pressed during shift hold

            def on_press(key):
                if key in (keyboard.Key.shift_l, keyboard.Key.shift_r):
                    shift_was_solo[0] = True
                else:
                    shift_was_solo[0] = False  # another key pressed, not a solo shift tap

            def on_release(key):
                if key in (keyboard.Key.shift_l, keyboard.Key.shift_r) and shift_was_solo[0]:
                    now = time.time()
                    if now - last_shift_release[0] < 0.4:
                        last_shift_release[0] = 0  # reset to avoid triple-trigger
                        self.toggle()
                    else:
                        last_shift_release[0] = now
        else:
            self._hotkey_keys = _parse_hotkey(hotkey_id)

            alt_keys = set()
            for k in self._hotkey_keys:
                if k == keyboard.Key.ctrl_l:
                    alt_keys.add(keyboard.Key.ctrl_r)
                elif k == keyboard.Key.shift_l:
                    alt_keys.add(keyboard.Key.shift_r)
                elif k == keyboard.Key.alt_l:
                    alt_keys.add(keyboard.Key.alt_r)

            current_keys = set()
            hotkey_fired = [False]

            def matches():
                for k in self._hotkey_keys:
                    if k not in current_keys:
                        found = False
                        for ak in alt_keys:
                            if ak in current_keys:
                                found = True
                                break
                        if not found:
                            return False
                return True

            def on_press(key):
                current_keys.add(key)
                if matches():
                    if hotkey_fired[0]:
                        return
                    hotkey_fired[0] = True
                    self.toggle()

            def on_release(key):
                current_keys.discard(key)
                if not matches():
                    hotkey_fired[0] = False

        self._listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        self._listener.daemon = True
        self._listener.start()

    def _setup_tray(self):
        try:
            import pystray
            from PIL import Image, ImageDraw

            def make_image():
                img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
                d = ImageDraw.Draw(img)
                d.ellipse([8, 8, 56, 56], fill="#89b4fa")
                d.rounded_rectangle([24, 16, 40, 40], radius=8, fill="#1e1e2e")
                d.arc([18, 28, 46, 48], 0, 180, fill="#1e1e2e", width=2)
                d.rectangle([30, 44, 34, 52], fill="#1e1e2e")
                return img

            def on_quit(icon, item):
                icon.stop()
                self.quit()

            hk = self.config["hotkey"].replace("+", " + ").title()
            menu = pystray.Menu(
                pystray.MenuItem(f"Typeoff \u2014 {hk}", None, enabled=False),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Quit", on_quit),
            )
            self._tray = pystray.Icon("typeoff", make_image(), "Typeoff", menu)
            threading.Thread(target=self._tray.run, daemon=True).start()
        except ImportError:
            pass

    def minimize(self):
        if self._window:
            self._window.minimize()

    def show_mini(self):
        """Request mini overlay to show. Thread-safe via flag."""
        self._mini_visible = True
        if not self._mini_root:
            threading.Thread(target=self._run_mini, daemon=True).start()

    def hide_mini(self):
        """Request mini overlay to hide. Thread-safe via flag."""
        self._mini_visible = False

    def _run_mini(self):
        """Mini recording overlay — runs in its own thread with its own tkinter mainloop."""
        import tkinter as tk

        root = tk.Tk()
        self._mini_root = root
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.attributes("-alpha", 0.92)
        root.configure(bg="#1a1b2e")
        root.withdraw()  # start hidden

        w, h = 400, 44
        sx = root.winfo_screenwidth()
        sy = root.winfo_screenheight()
        root.geometry(f"{w}x{h}+{sx // 2 - w // 2}+{sy - h - 50}")

        frame = tk.Frame(root, bg="#1a1b2e")
        frame.pack(fill="both", expand=True)

        # Spectrum bars
        bar_count = 16
        bar_w, bar_gap = 3, 1
        canvas_w = bar_count * (bar_w + bar_gap) + 4
        canvas_h = 30
        canvas = tk.Canvas(frame, width=canvas_w, height=canvas_h,
                           bg="#1a1b2e", highlightthickness=0)
        canvas.pack(side="left", padx=(12, 6))
        bars = []
        for i in range(bar_count):
            x = 2 + i * (bar_w + bar_gap)
            b = canvas.create_rectangle(x, canvas_h, x + bar_w, canvas_h,
                                        fill="#f38ba8", outline="")
            bars.append(b)

        label = tk.Label(frame, text="Recording...", font=("Segoe UI", 10),
                         fg="#a6adc8", bg="#1a1b2e", anchor="w")
        label.pack(side="left", fill="x", expand=True, padx=(4, 4))

        timer_lbl = tk.Label(frame, text="0s", font=("Segoe UI", 10, "bold"),
                             fg="#f38ba8", bg="#1a1b2e")
        timer_lbl.pack(side="right", padx=(4, 12))

        smooth = [0.0] * bar_count
        was_visible = [False]

        def tick():
            """Single update loop — handles visibility, spectrum, text, timer."""
            if not self._mini_root:
                return

            # Show/hide based on flag
            if self._mini_visible and not was_visible[0]:
                root.deiconify()
                was_visible[0] = True
            elif not self._mini_visible and was_visible[0]:
                root.withdraw()
                was_visible[0] = False

            if not was_visible[0]:
                root.after(100, tick)
                return

            state = self._state
            status = state.get("status", "")

            # Spectrum
            spectrum = state.get("spectrum", [])
            for i in range(bar_count):
                target = spectrum[i] if i < len(spectrum) else 0.0
                if target > smooth[i]:
                    smooth[i] = smooth[i] * 0.3 + target * 0.7
                else:
                    smooth[i] = smooth[i] * 0.7 + target * 0.3

                h_px = max(2, int(smooth[i] * (canvas_h - 2)))
                x = 2 + i * (bar_w + bar_gap)
                canvas.coords(bars[i], x, canvas_h - h_px, x + bar_w, canvas_h)

                # Color gradient
                r = int(243 - i * 6)
                g = int(139 + i * 4)
                b_c = int(168 + i * 5)
                color = f"#{r:02x}{g:02x}{b_c:02x}"
                if status == "transcribing":
                    color = "#fab387"
                elif status == "done":
                    color = "#a6e3a1"
                canvas.itemconfig(bars[i], fill=color)

            # Text + timer
            if status == "recording":
                secs = int(state.get("elapsed", 0))
                mins = secs // 60
                s = secs % 60
                t = f"{mins}:{s:02d}" if mins > 0 else f"{s}s"
                timer_lbl.config(text=t, fg="#f38ba8")
                txt = state.get("text", "")
                display = ("..." + txt[-47:]) if len(txt) > 50 else (txt or "Recording...")
                label.config(text=display)
            elif status == "transcribing":
                label.config(text="Transcribing...")
                timer_lbl.config(text="", fg="#fab387")
            elif status == "done":
                label.config(text="Done!")
                timer_lbl.config(text="", fg="#a6e3a1")

            root.after(80, tick)

        tick()
        root.mainloop()

    def quit(self):
        self._mini_visible = False
        self._mini_root = None
        if self._window:
            self._window.destroy()
        os._exit(0)

    def run(self):
        self._setup_hotkey()
        self._setup_tray()
        threading.Thread(target=self._load_model, daemon=True).start()

        api = Api(self)
        self._window = webview.create_window(
            "Typeoff",
            url=os.path.join(UI_DIR, "index.html"),
            js_api=api,
            width=440,
            height=520,
            resizable=False,
            frameless=True,
            on_top=False,
            background_color="#1a1b2e",
        )
        webview.start(debug=False)


if __name__ == "__main__":
    app = TypeoffApp()
    app.run()

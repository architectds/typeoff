#!/usr/bin/env python3
"""
Typeoff — Local Speech-to-Text with GUI
Click Record → speak → text appears. Copy or auto-paste.
"""

import sys
import time
import platform
import threading
import tkinter as tk
from tkinter import ttk

from backends import get_backend
from engine.recorder import Recorder
from engine.vad import VAD
from engine.paster import paste_text

PLATFORM = platform.system()


class TypeoffApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Typeoff")
        self.root.geometry("420x320")
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)  # always on top

        # Dark theme colors
        self.bg = "#1e1e2e"
        self.fg = "#cdd6f4"
        self.accent = "#89b4fa"
        self.red = "#f38ba8"
        self.green = "#a6e3a1"
        self.surface = "#313244"

        self.root.configure(bg=self.bg)

        self._recording = False
        self._model_ready = False
        self.backend = None
        self.recorder = None
        self.streamer = None

        self._build_ui()
        self._load_model()

    def _build_ui(self):
        # Title
        tk.Label(
            self.root, text="Typeoff", font=("Helvetica", 18, "bold"),
            bg=self.bg, fg=self.fg
        ).pack(pady=(15, 5))

        tk.Label(
            self.root, text="Local voice-to-text · Fully offline",
            font=("Helvetica", 10), bg=self.bg, fg="#6c7086"
        ).pack()

        # Status
        self.status_var = tk.StringVar(value="Loading model...")
        self.status_label = tk.Label(
            self.root, textvariable=self.status_var,
            font=("Helvetica", 11), bg=self.bg, fg=self.accent
        )
        self.status_label.pack(pady=(15, 10))

        # Record button
        self.btn_frame = tk.Frame(self.root, bg=self.bg)
        self.btn_frame.pack(pady=5)

        self.record_btn = tk.Button(
            self.btn_frame, text="🎙  Record", font=("Helvetica", 14, "bold"),
            bg=self.accent, fg="#1e1e2e", activebackground="#74c7ec",
            width=14, height=2, relief="flat", cursor="hand2",
            command=self._toggle_record, state="disabled"
        )
        self.record_btn.pack()

        # Text output
        self.text_frame = tk.Frame(self.root, bg=self.surface, padx=2, pady=2)
        self.text_frame.pack(padx=20, pady=(15, 5), fill="x")

        self.text_box = tk.Text(
            self.text_frame, height=4, wrap="word",
            font=("Helvetica", 11), bg=self.surface, fg=self.fg,
            insertbackground=self.fg, relief="flat", padx=8, pady=6
        )
        self.text_box.pack(fill="x")

        # Bottom buttons
        btn_row = tk.Frame(self.root, bg=self.bg)
        btn_row.pack(pady=(5, 10))

        self.copy_btn = tk.Button(
            btn_row, text="Copy", font=("Helvetica", 10),
            bg=self.surface, fg=self.fg, relief="flat", padx=15, pady=3,
            cursor="hand2", command=self._copy_text
        )
        self.copy_btn.pack(side="left", padx=5)

        self.clear_btn = tk.Button(
            btn_row, text="Clear", font=("Helvetica", 10),
            bg=self.surface, fg=self.fg, relief="flat", padx=15, pady=3,
            cursor="hand2", command=self._clear_text
        )
        self.clear_btn.pack(side="left", padx=5)

        self.paste_btn = tk.Button(
            btn_row, text="Paste to app", font=("Helvetica", 10),
            bg=self.surface, fg=self.fg, relief="flat", padx=15, pady=3,
            cursor="hand2", command=self._paste_to_app
        )
        self.paste_btn.pack(side="left", padx=5)

    def _load_model(self):
        def _do():
            self.backend = get_backend("base")
            self.backend.load()
            self._model_ready = True
            self.root.after(0, self._on_model_ready)

        threading.Thread(target=_do, daemon=True).start()

    def _on_model_ready(self):
        self.status_var.set("Ready — click Record to speak")
        self.status_label.config(fg=self.green)
        self.record_btn.config(state="normal")

    def _toggle_record(self):
        if not self._recording:
            self._start_recording()
        else:
            self._stop_recording()

    def _start_recording(self):
        self._recording = True
        self.record_btn.config(text="⏹  Stop", bg=self.red)
        self.status_var.set("🎙  Recording...")
        self.status_label.config(fg=self.red)

        self.recorder = Recorder(max_duration=600)
        self.vad = VAD(silence_duration=8.0)
        self._latest_text = ""
        self._locked_text = ""      # text from earlier chunks, finalized
        self._lock_sample = 0       # audio sample where locked text ends

        self.recorder.start()

        # Start rolling transcription in background
        threading.Thread(target=self._recording_loop, daemon=True).start()

    def _recording_loop(self):
        """Background: rolling transcription + auto-stop on silence."""
        last_transcribe = 0
        import numpy as np
        start_time = time.time()

        print(f"\n=== RECORDING STARTED at {time.strftime('%H:%M:%S')} ===")

        while self._recording:
            duration = self.recorder.get_duration()
            audio = self.recorder.get_audio()
            elapsed_wall = time.time() - start_time
            audio_mb = len(audio) * 4 / 1024 / 1024  # float32 = 4 bytes

            # Log every 5s
            if int(elapsed_wall) % 5 == 0 and int(elapsed_wall) > 0:
                tail_rms = 0
                if len(audio) > 16000:
                    tail_1s = audio[-16000:]
                    tail_rms = np.sqrt(np.mean(tail_1s ** 2))
                print(f"  📊 {elapsed_wall:.0f}s wall | {duration:.1f}s audio | {audio_mb:.1f}MB | tail_rms={tail_rms:.4f}")

            # Auto-stop on silence (8s pause)
            if duration > 8.0 and self.vad.has_speech(audio):
                if self.vad.detect_end_of_speech(audio):
                    print(f"  🛑 SILENCE DETECTED at {elapsed_wall:.1f}s wall / {duration:.1f}s audio")
                    self.root.after(0, self._stop_recording)
                    return

            # Rolling transcription every 3s with sliding window
            now = time.time()
            if duration >= 1.5 and now - last_transcribe >= 3.0:
                if self.vad.has_speech(audio):
                    window_audio = audio[self._lock_sample:]
                    window_duration = len(window_audio) / 16000

                    t0 = time.time()
                    text = self.backend.transcribe(window_audio, sr=16000)
                    tx_elapsed = time.time() - t0
                    print(f"  🎤 [{tx_elapsed:.1f}s transcribe] [{window_duration:.0f}s window] [{elapsed_wall:.0f}s wall] \"{text}\"")

                    if text.strip():
                        full_text = (self._locked_text + " " + text.strip()).strip()
                        self._latest_text = full_text
                        self.root.after(0, self._update_text, full_text)

                    # Lock text every 30s to keep window short
                    if window_duration > 30:
                        print(f"  🔒 LOCKING at {elapsed_wall:.0f}s — \"{self._latest_text[-50:]}...\"")
                        self._locked_text = self._latest_text
                        self._lock_sample = len(audio)

                    last_transcribe = time.time()
                else:
                    print(f"  ⚠️  no speech detected at {elapsed_wall:.1f}s / {duration:.1f}s audio")

            time.sleep(0.2)

        print(f"=== RECORDING LOOP EXITED at {elapsed_wall:.1f}s (self._recording={self._recording}) ===")

    def _stop_recording(self):
        if not self._recording:
            return
        self._recording = False

        self.record_btn.config(text="🎙  Record", bg=self.accent, state="disabled")
        self.status_var.set("Transcribing...")
        self.status_label.config(fg=self.accent)

        threading.Thread(target=self._finalize, daemon=True).start()

    def _finalize(self):
        """Final transcription pass on complete audio."""
        audio = self.recorder.stop()

        if not self.vad.has_speech(audio):
            self.root.after(0, self._set_status, "No speech detected", self.red)
            self.root.after(0, lambda: self.record_btn.config(state="normal"))
            return

        # Final pass — transcribe complete audio for best accuracy
        text = self.backend.transcribe(audio, sr=16000)
        if text.strip():
            self._latest_text = text.strip()

        self.root.after(0, self._update_text, self._latest_text)
        self.root.after(0, self._set_status, "Done — Copy or Paste", self.green)
        self.root.after(0, lambda: self.record_btn.config(state="normal"))

    def _update_text(self, text):
        self.text_box.delete("1.0", "end")
        self.text_box.insert("1.0", text)

    def _set_status(self, msg, color):
        self.status_var.set(msg)
        self.status_label.config(fg=color)

    def _copy_text(self):
        text = self.text_box.get("1.0", "end").strip()
        if text:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.status_var.set("Copied!")
            self.status_label.config(fg=self.green)

    def _clear_text(self):
        self.text_box.delete("1.0", "end")
        self.status_var.set("Ready — click Record to speak")
        self.status_label.config(fg=self.green)

    def _paste_to_app(self):
        """Minimize window, paste text into whatever app is behind."""
        text = self.text_box.get("1.0", "end").strip()
        if not text:
            return
        self.root.iconify()  # minimize
        time.sleep(0.3)      # let the other app get focus
        paste_text(text)
        self.root.after(500, self.root.deiconify)  # restore after paste

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = TypeoffApp()
    app.run()

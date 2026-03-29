#!/usr/bin/env python3
"""
Typeoff — Local Speech-to-Text Input Method
Press hotkey → speak → text streams into active app. Fully offline.

Sentence-based streaming:
    Record continuously → transcribe rolling window → lock complete sentences →
    paste sentence-by-sentence → final pass for last fragment → done.
"""

import sys
import time
import platform
import threading

from backends import get_backend
from engine.recorder import Recorder
from engine.vad import VAD
from engine.streamer import StreamingTranscriber
from engine.paster import paste_text

# ─── Config ───────────────────────────────────────────────────────
MODEL = "small"
ROLL_INTERVAL = 3.0         # seconds between rolling transcriptions
SILENCE_DURATION = 2.0      # seconds of silence to auto-stop
MAX_DURATION = 30           # max recording seconds
MIN_AUDIO_FOR_ROLL = 1.5    # minimum seconds before first transcription
LANGUAGE = None             # None=auto, "en", "zh", etc.
PLATFORM = platform.system()

# ─── State ────────────────────────────────────────────────────────
_active = False
_lock = threading.Lock()


def run_session(backend):
    """One voice input session: record → stream-transcribe → paste."""
    global _active

    recorder = Recorder(max_duration=MAX_DURATION)
    vad = VAD(silence_duration=SILENCE_DURATION)
    streamer = StreamingTranscriber(backend, interval=ROLL_INTERVAL)

    silence_detected = threading.Event()
    last_transcribe_time = 0

    # ─── VAD thread: checks for silence independently ─────────
    def vad_watcher():
        while _active and recorder.is_recording:
            audio = recorder.get_audio()
            duration = recorder.get_duration()

            if duration > MAX_DURATION:
                print("  Max duration reached.")
                silence_detected.set()
                return

            if duration > SILENCE_DURATION + 1.0 and vad.has_speech(audio):
                if vad.detect_end_of_speech(audio):
                    print("  Silence detected, finishing...")
                    silence_detected.set()
                    return

            time.sleep(0.2)

    vad_thread = threading.Thread(target=vad_watcher, daemon=True)

    try:
        recorder.start()
        print("\n🎙  Recording... (speak now)")
        vad_thread.start()

        # ─── Rolling transcription loop ───────────────────────
        while _active and not silence_detected.is_set():
            duration = recorder.get_duration()

            if duration < MIN_AUDIO_FOR_ROLL:
                time.sleep(0.2)
                continue

            now = time.time()
            if now - last_transcribe_time < ROLL_INTERVAL:
                if silence_detected.wait(timeout=0.3):
                    break
                continue

            audio = recorder.get_audio()

            if not vad.has_speech(audio):
                time.sleep(0.3)
                continue

            # Rolling transcription — returns locked sentences to paste
            new_sentence, pending = streamer.rolling_transcribe(
                audio, language=LANGUAGE
            )
            last_transcribe_time = time.time()

            # Paste complete sentence immediately
            if new_sentence:
                paste_text(new_sentence)

        # ─── Final pass: transcribe remaining fragment ────────
        audio = recorder.stop()

        if not vad.has_speech(audio):
            print("  No speech detected, skipped.")
            return

        print("  Final transcription...")
        final_remainder, full_text = streamer.final_transcribe(
            audio, language=LANGUAGE
        )

        # Paste the last fragment (no replacement needed — it wasn't pasted yet)
        if final_remainder:
            paste_text(final_remainder)

        print(f'  ✓ Done: "{full_text}"')

    except Exception as e:
        print(f"  Error: {e}")
        recorder.stop()
    finally:
        streamer.reset()


def main():
    from pynput import keyboard

    print("─── Typeoff ───")
    print(f"Model: {MODEL} | Platform: {PLATFORM}")
    backend = get_backend(MODEL)

    def warmup():
        print("Loading model (first run downloads weights)...")
        backend.load()
        print(f"Ready: {backend.name}")

    threading.Thread(target=warmup, daemon=True).start()

    if PLATFORM == "Darwin":
        HOTKEY_COMBO = {keyboard.Key.cmd, keyboard.Key.shift, keyboard.Key.space}
        hotkey_label = "Cmd+Shift+Space"
    else:
        HOTKEY_COMBO = {keyboard.Key.ctrl, keyboard.Key.shift, keyboard.Key.space}
        hotkey_label = "Ctrl+Shift+Space"

    current_keys = set()

    def on_press(key):
        global _active
        current_keys.add(key)
        if HOTKEY_COMBO.issubset(current_keys):
            with _lock:
                if not _active:
                    _active = True
                    threading.Thread(target=_session, args=(backend,), daemon=True).start()

    def on_release(key):
        current_keys.discard(key)

    def _session(be):
        global _active
        try:
            run_session(be)
        finally:
            _active = False

    print(f"Hotkey: {hotkey_label}")
    print("Press hotkey → speak → text appears in active app.")
    print("Ctrl+C to quit.\n")

    with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
        listener.join()


if __name__ == "__main__":
    main()

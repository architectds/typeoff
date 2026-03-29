# Typeoff — Technical Architecture

## Overview

Typeoff is an offline speech-to-text tool. Press a hotkey, speak, text appears in your active app. Everything runs locally — no cloud, no API keys.

Three implementations exist:
- **Rust version** (`rs/`) — primary, cross-platform (Mac/Win/Linux), Tauri v2 UI
- **Python version** (`python/`) — reference implementation, feature-complete
- **iOS version** (`ios/`) — archived, input method via SwiftWhisper

## Core Pipeline

```
                    ┌─────────────────────────────────────────────┐
                    │              Recording Session              │
                    │                                             │
  Microphone ──→ Voice Filter ──→ RMS VAD ──→ Rolling Transcribe
  (16kHz f32)   (50-3400Hz BP)  (energy)    (every 3s)          │
                                                                  │
                    ┌─────────────────────────────────────────────┤
                    │         StreamingTranscriber                 │
                    │                                             │
                    │  ┌─ Tokenize (CJK-aware) ─┐                │
                    │  │                         │                │
                    │  ├─ Fuzzy Agreement (80%) ──┤               │
                    │  │  (compare with prev run) │               │
                    │  │                         │                │
                    │  ├─ LOCK on punctuation ────┤──→ LLM Fix ──→ Paste
                    │  │  or 40+ chars           │  (optional)    to app
                    │  │                         │                │
                    │  ├─ Fail Safe (3 passes) ──┤──→ Paste      │
                    │  │  push to last punct     │    to app     │
                    │  │                         │                │
                    │  └─ Slide Window ──────────┘                │
                    │    (only re-transcribe new audio)           │
                    └─────────────────────────────────────────────┘
                                      │
                                      ▼
                              Filler Removal
                           (嗯, uh, um, 那个...)
                                      │
                                      ▼
                              Final Pass
                           (transcribe remaining)
                                      │
                                      ▼
                              Paste to Target App
```

## Key Algorithms

### 1. Streaming Transcription (LocalAgreement + Fuzzy Matching)

**Problem**: Whisper is a batch model — it transcribes complete audio segments. We need real-time streaming output.

**Solution**: Rolling window transcription with agreement-based confirmation.

```
Every 3 seconds:
  1. Transcribe current audio window → current_words
  2. Compare with previous transcription → prev_words
  3. Agreement check:
     a. Strict prefix match (≥3 tokens identical) → agree
     b. Fuzzy match (≥80% tokens match positionally) → agree
     c. Neither → increment pass_count
  4. If agreed + punctuation found → LOCK + push + slide window
  5. If agreed + >40 chars → force LOCK + push + slide window
  6. If pass_count ≥ 3 → FAIL SAFE: push to last punctuation + slide
```

**Why fuzzy**: Whisper often swaps homophones between runs (噪音↔烧音). Strict matching would never agree. 80% threshold tolerates 1-2 char differences in a 10-char sequence.

**Why fail safe**: If Whisper produces wildly different results each time (rare), we can't wait forever. After 3 passes (~9 seconds), push what we have up to the last punctuation mark, keep the tail for the next window.

### 2. CJK-Aware Tokenization

**Problem**: Chinese/Japanese/Korean text has no spaces between words. Standard `split()` tokenization treats an entire sentence as one token.

**Solution**: Per-character tokenization for CJK, whitespace tokenization for Latin.

```python
"今天weather很好" → ["今", "天", "weather", "很", "好"]
```

Joining respects this: no spaces between adjacent CJK characters, spaces around Latin words.

### 3. Sliding Window

**Problem**: Re-transcribing the entire recording gets slower as audio grows.

**Solution**: After LOCK, estimate where the locked audio ends and advance the window start.

```
[=====LOCKED=====|---window---]
                  ↑ _window_start_sample

After LOCK:
[=====LOCKED=====|==NEW LOCK==|---window---]
                               ↑ new start
```

The window position is estimated by ratio: `(locked_tokens / total_tokens) × window_length`.

### 4. Voice Activity Detection

**Current**: RMS energy-based VAD. Simple, reliable, no dependencies.

```
- has_speech(): scan first/last 10s for windows with RMS > threshold
- detect_end_of_speech(): check if tail has silence_duration seconds of silence
- Threshold: 0.005 RMS (configurable)
```

**Future (Rust)**: Silero VAD v4 with onset/hangover/prefill for better accuracy.

### 5. Filler Word Removal

Post-processing step that cleans up transcription output:

- **Chinese fillers**: 嗯, 啊, 那个, 就是, 然后, 这个, 对吧, 那么
- **English fillers**: uh, um, you know, like, I mean
- **Stutter collapse**: "我我我想" → "我想"
- Language auto-detection based on character analysis

Only removes fillers at syntactic boundaries (after punctuation, at start/end), not when part of meaningful phrases.

### 6. Voice Bandpass Filter

Pre-processing step that removes non-voice frequencies before transcription:

```
Input audio → Butterworth bandpass (50-3400Hz, order 5) → Cleaned audio
```

- **Below 50Hz**: HVAC rumble, traffic, desk vibration, electrical hum
- **Above 3400Hz**: keyboard clicks, mouse clicks, hiss, electronic noise
- **Kept**: human voice fundamentals (85-300Hz) + harmonics + sibilance
- Pre-computed filter coefficients for 16kHz (zero overhead per call)
- Uses `scipy.signal.butter` + `sosfilt` (second-order sections for stability)

### 7. LLM Text Correction

Optional post-processing step using a small language model to fix homophone errors.

```
LOCK text → Qwen2.5-0.5B-Instruct → Corrected text → Paste

Prompt: "只纠正同音字错误，不改变意思/语序/风格/标点，保持原文语言"
```

**Architecture**:
- **Corrector class** with pluggable backends: `local` (Qwen) or `api` (future)
- Local: `transformers` + `Qwen/Qwen2.5-0.5B-Instruct`, GPU auto-detected
- Model stays resident in memory (~1GB GPU / ~2GB CPU) — no reload per session
- Safety guard: if output length deviates >50% from input, keep original
- Applied per LOCK push (each sentence), not on full text
- Setting: `correction_mode` = "off" | "local" | "api"

**Rust equivalent**: Use `llama.cpp` or `candle` with GGML Q4 Qwen model (~300MB).

## Module Structure

### Python Version (`python/`)

```
typeoff.py                 — App entry point: webview UI, hotkey, tray, session loop
ui/
  index.html               — Webview UI: settings panel, text display
  mini.html                — Mini recording overlay (unused, replaced by tkinter)
backends/
  __init__.py              — Auto-select backend by platform
  faster_backend.py        — faster-whisper (CTranslate2): Windows/Linux
  mlx_backend.py           — MLX Whisper: Mac Apple Silicon
engine/
  recorder.py              — Audio capture (sounddevice, 16kHz mono)
  audio_filter.py          — Bandpass filter (50-3400Hz, human voice only)
  streamer.py              — Streaming transcription (LocalAgreement, sliding window)
  vad.py                   — Voice activity detection (RMS energy)
  fillers.py               — Filler word removal
  corrector.py             — LLM text correction (Qwen2.5-0.5B / API)
  paster.py                — Clipboard paste (pbcopy/clip.exe + Ctrl+V/Cmd+V)
```

### Rust Version (`rs/`)

```
src/
  lib.rs                   — Library exports (all pipeline modules)
  main.rs                  — CLI entry point + test commands
  config.rs                — JSON settings (serde), model path search
  recorder.rs              — Audio capture (cpal, 48kHz→16kHz resampling)
  audio_filter.rs          — Bandpass filter (50-3400Hz, biquad cascade)
  vad.rs                   — Voice activity detection (RMS energy)
  transcriber.rs           — whisper.cpp inference (whisper-rs, Metal/CUDA/CPU)
  streamer.rs              — Streaming transcription (fuzzy agreement + fail-safe)
  fillers.rs               — Filler word removal (Chinese + English + stutter)
  corrector.rs             — LLM correction stub (Qwen via llama-cpp-2, deferred)
  hotkey.rs                — Double-shift detection (rdev)
  paster.rs                — Clipboard paste (arboard + enigo, Cmd+V / Ctrl+V)
src-tauri/
  src/main.rs              — Tauri desktop app entry point
  src/lib.rs               — Tauri commands (toggle, get_state, config, etc.)
  tauri.conf.json          — Window config (440x520, frameless, dark bg)
  capabilities/            — Tauri permissions
ui/
  index.html               — Webview UI (Catppuccin theme, settings, status)
```

#### Rust Dependencies

| Crate | Version | Purpose |
|-------|---------|---------|
| whisper-rs | 0.16 | whisper.cpp bindings (Metal/CUDA/CPU) |
| cpal | 0.15 | Cross-platform audio capture |
| biquad | 0.4 | Audio bandpass filter |
| rdev | 0.5 | Global hotkey (double-shift) |
| arboard | 3 | Cross-platform clipboard |
| enigo | 0.2 | Keyboard simulation (paste) |
| regex | 1 | Filler word removal |
| tauri | 2 | Desktop app framework |
| serde/serde_json | 1 | Settings serialization |
| dirs | 6 | Platform config directories |

## Model Support

### Python (faster-whisper / CTranslate2)

| Model | Download | Runtime Memory | Languages |
|-------|----------|---------------|-----------|
| tiny | ~75MB (fp16) | ~150MB (int8) | 99 |
| base | ~140MB | ~300MB | 99 |
| small | ~460MB | ~500MB | 99 |
| medium | ~1.5GB | ~1.5GB | 99 |
| large-v3 | ~3GB | ~3GB | 99 |
| distil-large-v3 | ~750MB | ~750MB | English only |
| large-v3-turbo | ~800MB | ~800MB | 99 |

GPU: CUDA auto-detected. int8 on GPU (GTX 1060+), int8 on CPU.

### Rust (whisper.cpp / GGML)

| Model | GGML fp16 | GGML Q5_0 |
|-------|-----------|-----------|
| small | 466MB | ~180MB |
| medium | 1.5GB | ~500MB |

GPU: CUDA, Metal, Vulkan supported at compile time.

## Configuration

Settings stored in `%APPDATA%/Typeoff/settings.json` (Windows) or `~/.config/Typeoff/settings.json` (Mac/Linux).

```json
{
  "model": "small",
  "language": "auto",
  "hotkey": "double_shift",
  "auto_paste": true,
  "auto_stop_silence": true,
  "silence_duration": 2.0,
  "max_duration": 60,
  "correction_mode": "local",
  "correction_model": "Qwen/Qwen2.5-0.5B-Instruct",
  "verbose": false
}
```

## Performance

Benchmarks on NVIDIA GTX 1060 6GB, Whisper small model:

| Metric | CPU | GPU (CUDA) |
|--------|-----|------------|
| Transcription per pass | 3-4s | 0.5-0.8s |
| Streaming latency | ~6-9s | ~3-6s |
| First word appearance | ~4.5s | ~1.5s |

## Distribution

| | Python | Rust |
|---|---|---|
| Binary size | ~200MB (PyInstaller) | ~3MB (exe) |
| + Model | +460MB (small) | +180MB (Q5) |
| Total | ~660MB | ~183MB |
| Dependencies | Python runtime, numpy, torch, etc. | None |
| GPU support | pip install nvidia-cublas-cu12 | Compiled in |

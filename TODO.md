# Typeoff — TODO

## Rust Version (rs/) — Current Focus

### Done
- [x] **Core pipeline working**: mic → bandpass filter → VAD → whisper → streaming agreement → filler removal → LLM correction → paste
- [x] **Fuzzy LocalAgreement**: 80% positional token match, prefers latest run on mismatch
- [x] **Fail-safe**: force push after 3 passes on same window
- [x] **Bandpass filter**: 50-3400Hz via biquad (highpass + lowpass cascade)
- [x] **Filler removal**: Chinese + English fillers, CJK/word stutter collapse
- [x] **LLM correction**: Qwen2.5-0.5B via llama-cpp-2, ChatML prompt, safety guard
- [x] **Cross-platform paste**: Cmd+V via osascript (Mac), Ctrl+V via enigo (Win/Linux)
- [x] **GPU auto-detect**: Apple Silicon → Metal GPU for both whisper + llama.cpp; AMD/Intel → CPU fallback
- [x] **Chinese + English transcription verified**: auto-detect language (98%+ confidence)
- [x] **Tauri v2 UI**: Catppuccin dark theme, settings page, status pill, RMS waveform, drag, minimize, close
- [x] **Double-shift hotkey**: via fufesou/rdev fork (fixes macOS TSM crash)
- [x] **Suppress verbose logs**: whisper.cpp decoder output silenced via GGML_LOG_LEVEL
- [x] **CLI test commands**: --test-record, --test-transcribe, --test-filter, --test-fillers, --test-correct
- [x] **Tested on Apple Silicon**: Metal GPU, fast transcription (~0.5s/pass)
- [x] **Tested on Intel Mac**: CPU fallback, working (~3.5s/pass)
- [x] **ios/ removed**: moved to separate repo to avoid identity leak from Xcode signing

### Next Up
- [ ] **System tray**: Tauri v2 built-in TrayIconBuilder
- [ ] **LLM correction quality**: try larger model (1.5B) or better quant for homophone accuracy
- [ ] **LLM model selector in UI**: dropdown in settings to pick correction model
- [ ] **Model auto-download**: fetch GGML/GGUF models on first run if missing

### Platform Status

| Component | Mac (Apple Silicon) | Mac (Intel) | Windows | Linux |
|-----------|-------------------|-------------|---------|-------|
| Whisper | Metal GPU ✓ | CPU ✓ | CUDA / CPU | CUDA / CPU |
| LLM (Qwen) | Metal GPU ✓ | CPU ✓ | CUDA / CPU | CUDA / CPU |
| Audio capture | CoreAudio ✓ | CoreAudio ✓ | WASAPI ✓* | ALSA/Pulse ✓ |
| Hotkey | fufesou/rdev ✓ | fufesou/rdev ✓ | rdev ✓ | rdev (X11) |
| Paste | osascript ✓ | osascript ✓ | enigo Ctrl+V | enigo Ctrl+V |
| Tauri UI | WKWebView ✓ | WKWebView ✓ | WebView2 | WebKitGTK |

*Windows WASAPI may need auto-gain detection (int16-as-float bug)

### Backlog
- [ ] **Windows WASAPI gain**: auto-detect quiet audio, apply gain if RMS < 0.001
- [ ] **Linux Wayland**: rdev/enigo X11-only — need rdevin fork or platform code
- [ ] **Better resampling**: sinc/polyphase instead of linear interpolation
- [ ] **Input device selection**: let user pick microphone in settings
- [ ] **Shorter rolling interval**: 1.5-2s on GPU (whisper.cpp is fast enough)
- [ ] **RNNoise**: noise reduction before Whisper (~85KB model)
- [ ] **Mini overlay**: slim recording bar (port from Python mini.html)

## Python Version (python/) — Reference Implementation
- Feature-complete prototype, used as reference for Rust port
- Known issues: resource leak, hotkey settings, occasional text loss

## iOS Version — Separate Repo
- Moved to TypeOff_ios to isolate Xcode signing identity
- Input method based on SwiftWhisper + CoreML, on hold

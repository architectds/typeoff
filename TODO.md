# Typeoff — TODO

## Rust Version (rs/) — Current Focus

### Done
- [x] Core pipeline: mic → filter → VAD → whisper → streaming agreement → filler removal → LLM correction → auto-paste
- [x] Streaming flush: locked sentences paste mid-recording as confirmed
- [x] Fuzzy LocalAgreement (80% match) + fail-safe (3 passes)
- [x] Bandpass filter 50-3400Hz + filler removal (Chinese + English + stutter)
- [x] LLM correction via llama-cpp-2 + Qwen 0.5B GGUF
- [x] CGEvent paste on macOS (replaces osascript — no permission chain issues)
- [x] AXIsProcessTrustedWithOptions — proper Accessibility permission prompt on startup
- [x] GPU auto-detect: Apple Silicon → Metal, AMD/Intel Mac → CPU fallback
- [x] Tauri v2 UI: Catppuccin dark theme, settings, status pill, RMS waveform
- [x] System tray: app starts hidden, tray icon, double-click shows UI, close hides to tray
- [x] Tray icon switches between idle (T+dot) and recording (T+play) states
- [x] Double-shift hotkey via fufesou/rdev fork
- [x] Autostart (launch at login) via tauri-plugin-autostart
- [x] Model download prompt on first launch
- [x] Model switch in settings triggers reload or download prompt
- [x] Suppress verbose whisper.cpp/ggml logging
- [x] Quit crash fix (drop Metal models before exit)
- [x] Standalone binary tested on Intel Mac — works end-to-end
- [x] Chinese + English verified, auto-detect language (98%+ confidence)

### Distribution & Packaging
- [ ] **Mac universal binary**: single `.dmg` for both Intel + Apple Silicon (`--target universal-apple-darwin`)
- [ ] **Mac .dmg build**: `cargo tauri build` on Apple Silicon, test installer flow
- [ ] **Windows .msi/.exe build**: `cargo tauri build` on Windows, test installer flow
- [ ] **Windows CPU build**: default build, works on any Windows PC
- [ ] **Windows CUDA build**: separate build with `--features cuda` for NVIDIA GPU users
- [ ] **GitHub Actions CI**: auto-build Mac + Windows installers on git tag/release
- [ ] **Code signing**: macOS notarization + Windows code signing for trusted installs
- [ ] **Auto-update**: Tauri updater plugin for seamless version updates

### Model Management
- [ ] **Download progress bar**: show real progress during model download (currently blocks UI)
- [ ] **Model selector with download**: clicking a model in settings checks if installed, offers download if not
- [ ] **Multiple model support**: allow switching between tiny/base/small/medium without re-download
- [ ] **Model storage display**: show which models are installed and their sizes
- [ ] **Delete model**: allow removing downloaded models to free disk space
- [ ] **Qwen model download**: same download flow for LLM correction model
- [ ] **Model integrity check**: verify downloaded model isn't corrupted (file size or hash check)

### UI & UX
- [ ] **Mic device selection**: enumerate audio devices via cpal, let user pick in settings
- [ ] **Permission onboarding**: first-launch wizard for Microphone + Accessibility + Input Monitoring
- [ ] **Recording indicator**: visual feedback in target app (menu bar flash or overlay)
- [ ] **Text history**: keep recent transcriptions, allow copy/re-paste
- [ ] **Error messages in UI**: show errors in the app instead of only in terminal logs
- [ ] **Settings sync**: reload config when changed from settings page without restart

### Platform Status

| | Mac (Apple Silicon) | Mac (Intel) | Windows | Linux |
|---|---|---|---|---|
| Whisper | Metal GPU ✓ | CPU ✓ | CUDA / CPU | CUDA / CPU |
| LLM (Qwen) | Metal GPU ✓ | CPU ✓ | CUDA / CPU | CUDA / CPU |
| Audio | CoreAudio ✓ | CoreAudio ✓ | WASAPI | ALSA/Pulse |
| Hotkey | fufesou/rdev ✓ | fufesou/rdev ✓ | rdev | rdev (X11) |
| Paste | CGEvent ✓ | CGEvent ✓ | enigo Ctrl+V | enigo Ctrl+V |
| UI | WKWebView ✓ | WKWebView ✓ | WebView2 | WebKitGTK |
| Tested | ✓ (fast) | ✓ (slow but works) | Pending | Pending |

### Windows-Specific
- [ ] **Windows WASAPI gain**: auto-detect quiet audio, apply gain if RMS < 0.001
- [ ] **Windows CUDA detection**: runtime check for NVIDIA GPU, graceful fallback to CPU
- [ ] **Windows paste testing**: verify enigo Ctrl+V works in common apps
- [ ] **Windows installer testing**: full install → run → uninstall flow

### Linux-Specific
- [ ] **Wayland support**: rdev/enigo X11-only — need rdevin fork or platform code
- [ ] **Linux packaging**: .deb, .AppImage, or Flatpak

### Backlog
- [ ] **Better resampling**: sinc/polyphase instead of linear interpolation
- [ ] **Shorter rolling interval**: 1.5-2s on GPU (whisper.cpp is fast enough)
- [ ] **RNNoise**: noise reduction before Whisper (~85KB model)
- [ ] **Mini overlay**: slim recording bar (port from Python mini.html)
- [ ] **Multi-mode LLM**: voice-driven mode switching (see PLAN_MODES.md)
- [ ] **Larger LLM model**: Qwen 3B/7B for better correction + translation
- [ ] **Safeword trigger**: "Toff, translate" voice commands

## Python Version (python/) — Reference Implementation
- Feature-complete, used as reference for Rust port
- Not actively maintained

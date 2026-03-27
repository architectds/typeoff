# Typeoff iOS — Build Plan

## Product
- **Name**: Typeoff
- **Pitch**: Free for 7 days. Then $9.99. Forever. No subscription. No cloud. Your voice stays on your device.
- **Target**: iOS 17+ (iPhone 13+, any iPad with A15+)
- **Size**: ~150-200MB (74MB model + app)

## Architecture

```
Typeoff.app (main app)
├── Onboarding — permissions guide (mic, keyboard)
├── Record screen — big mic button, live text preview
├── Settings — silence duration, language
└── StoreKit 2 — 7-day trial → $9.99 IAP

TypeoffKeyboard.appex (keyboard extension)
├── Mic button in keyboard toolbar
├── Records → transcribes → inserts text into any app
└── Shares CoreML model with main app (App Group)
```

## Files to Build

### Engine (shared between app + keyboard)
- [x] `WhisperEngine.swift` — CoreML model load/unload/transcribe
- [x] `AudioRecorder.swift` — AVAudioEngine mic recording with buffer
- [x] `SilenceDetector.swift` — RMS-based, 8s silence, tail-only scan
- [ ] `TranscriptionSession.swift` — rolling window orchestrator (ties above together)
  - Start recording → every 3s transcribe window → update text
  - Lock text every 30s, slide window
  - Detect 8s silence → final transcription → done

### App UI (SwiftUI)
- [ ] `TypeoffApp.swift` — app entry, scene
- [ ] `OnboardingView.swift` — 3 screens: welcome → mic permission → keyboard setup
- [ ] `RecordView.swift` — main screen: big Record button, live text, copy/paste
- [ ] `SettingsView.swift` — silence duration slider, language picker
- [ ] `PaywallView.swift` — trial expired → $9.99 unlock

### Keyboard Extension
- [ ] `KeyboardViewController.swift` — UIInputViewController subclass
- [ ] `KeyboardView.swift` — SwiftUI view embedded in keyboard
  - Mic button + status indicator + text preview
  - Tap mic → record → transcribe → insertText()

### StoreKit
- [ ] `StoreManager.swift` — StoreKit 2, product fetch, purchase, trial check
- [ ] `TrialManager.swift` — track first launch date, 7-day window
  - Store first_launch in UserDefaults (App Group shared with keyboard)
  - After 7 days: lock transcription, show paywall

### CoreML Model
- [ ] Convert Whisper base to CoreML format
  - Use `whisper-kit` or `coremltools` to convert
  - Or download pre-converted from HuggingFace (`coreml-community/whisper-base`)
- [ ] Bundle as `.mlmodelc` in app + share via App Group

### Xcode Project
- [ ] Create project with 2 targets: app + keyboard extension
- [ ] App Group: `group.com.typeoff.shared` (share model + UserDefaults)
- [ ] Info.plist: NSMicrophoneUsageDescription
- [ ] Keyboard extension Info.plist: RequestsOpenAccess = YES

## App Store Listing

### Screenshots (6.7" + 6.1")
1. Hero: "Voice to text. Offline. Private." with mic animation
2. Keyboard extension in iMessage
3. Recording in ChatGPT app
4. Settings screen
5. "No subscription" comparison badge

### Description
```
Talk instead of type. Typeoff turns your voice into text — instantly, privately, offline.

• Works everywhere — use as a keyboard in any app
• 100% offline — your voice never leaves your device
• No subscription — $9.99 once, yours forever
• Fast — text appears as you speak
• Private — no cloud, no account, no data collection

Free for 7 days. Then $9.99. That's it.

Powered by OpenAI's Whisper speech recognition, running entirely on your iPhone.
```

### Keywords
voice typing, dictation, speech to text, offline, whisper, voice input, keyboard

### Category
Productivity

### Price
Free (with In-App Purchase: $9.99 "Typeoff Unlimited")

## Build Order (Friday sprint)

1. **Xcode project setup** — 2 targets, App Group, entitlements (30 min)
2. **CoreML model** — convert/download, bundle (30 min)
3. **Engine** — TranscriptionSession tying together recorder + whisper + silence (1 hr)
4. **RecordView** — main app UI, test on device (30 min)
5. **Keyboard extension** — mic button, record, insertText (1 hr)
6. **StoreKit + trial** — IAP product, trial logic (30 min)
7. **Onboarding** — permission flow with animations (30 min)
8. **Polish + test** — edge cases, UI tweaks (1 hr)
9. **App Store Connect** — screenshots, listing, submit (30 min)

**Total: ~6 hours**

## Key Decisions
- English-only v1 (base model). Multilingual = v2 with downloadable `small` model.
- Keyboard extension is the main UX. Standalone app is for onboarding + settings.
- 7-day trial stored locally (not server-side). Accept that users can reset by reinstalling — the $9.99 price is low enough that this isn't worth fighting.
- No account system. No analytics beyond what App Store provides.

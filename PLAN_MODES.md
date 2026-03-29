# Typeoff — Multi-Mode LLM Pipeline Plan

## Vision

Once Whisper → LLM exists in the pipeline, the distance from "correction" to "translation/rewriting/email" is just a prompt swap + temperature change. No architecture change needed. Typeoff becomes not just a voice input method, but a voice-driven agent interface that can switch between modes on command.

## Mode Spectrum

```
Low creativity                                              High creativity
    ↓                                                            ↓
  直接输入    →    纠错    →    润色    →    翻译    →    写邮件    →    自由写作
  (bypass)      (correct)    (polish)   (translate)   (email)      (freewrite)
  temp=0        temp=0       temp=0.3   temp=0.3      temp=0.5     temp=0.7
```

All modes share the same pipeline. The only difference is the system prompt and temperature sent to the LLM.

## Triggering Modes

Two trigger mechanisms, both active simultaneously:

### 1. Safeword Trigger (Voice)

User says **"Toff, [command]"** at any point during dictation. The safeword "Toff" is stripped from transcription and treated as a mode-switch command.

```
User speaks: "Toff, 翻译模式"
Whisper outputs: "Toff, 翻译模式"
Detection: starts_with("Toff") → extract "翻译模式" → switch mode
Action: switch LLM prompt to translate, do NOT paste "Toff, 翻译模式"

User speaks: "The weather is nice today"
Whisper outputs: "The weather is nice today"
Detection: no "Toff" prefix → normal pipeline
Action: LLM translates → paste "今天天气很好"
```

**Safeword matching rules:**
- Match: "Toff," / "toff," / "Toff " / "TOFF," (case-insensitive, with comma or space after)
- The word "Toff" appearing mid-sentence is NOT a trigger: "This toffee is good" → normal text
- Only triggers when "Toff" is the first word of a new transcription segment

**Command matching:**
After stripping the safeword, fuzzy-match against known commands:

| Voice Command | Mode | Language Variants |
|---------------|------|-------------------|
| "直接输入" / "direct" / "bypass" | Bypass (no LLM) | |
| "纠错" / "纠错模式" / "correct" / "correction" | Correction | |
| "润色" / "polish" / "rewrite" | Polish | |
| "翻译" / "翻译成中文" / "translate" / "translate to English" | Translate | detect target from command |
| "写邮件" / "email" / "formal email" | Email | |
| "总结" / "summarize" | Summarize | |
| "恢复" / "reset" / "normal" | Back to default mode | |

### 2. UI Mode Selector (Physical)

A dropdown or segmented control in the Tauri UI and settings page. User sets a **default mode** that persists across sessions. The safeword trigger overrides this temporarily until "Toff, 恢复" resets to default.

```
┌──────────────────────────────┐
│ Mode: [纠错 ▾]               │  ← dropdown in header or settings
├──────────────────────────────┤
│ ● Bypass (直接输入)          │
│ ● Correction (纠错) ✓       │  ← default
│ ● Polish (润色)              │
│ ● Translate (翻译)           │
│ ● Email (写邮件)             │
│ ● Custom...                  │
└──────────────────────────────┘
```

Settings config:
```json
{
  "default_mode": "correct",
  "modes": {
    "correct": {
      "name": "纠错",
      "system_prompt": "只纠正同音字错误...",
      "temperature": 0.0
    },
    "translate_zh": {
      "name": "翻译成中文",
      "system_prompt": "翻译以下文本为中文...",
      "temperature": 0.3
    }
  }
}
```

## Architecture Changes

### What stays the same
- Whisper pipeline (mic → filter → VAD → transcribe → streaming agreement)
- Filler removal
- Paste mechanism
- Tauri UI shell

### What changes

```
Current:
  Whisper → filler removal → LLM(correction prompt) → paste

New:
  Whisper → safeword detect ──→ [command] → switch mode (don't paste)
                              └→ [text] → filler removal → LLM(active mode prompt, temp) → paste
```

### New modules

**1. `modes.rs` — Mode registry**
```rust
struct Mode {
    id: String,
    name: String,
    system_prompt: String,
    temperature: f32,
}

struct ModeManager {
    modes: HashMap<String, Mode>,
    active_mode: String,
    default_mode: String,
}
```

Built-in modes hardcoded. Custom modes from config. Active mode switchable at runtime.

**2. `command.rs` — Safeword detection + command routing**
```rust
const SAFEWORD: &str = "toff";

enum CommandResult {
    Command(String),     // "Toff, 翻译模式" → Command("translate_zh")
    Text(String),        // "Hello world" → Text("Hello world")
}

fn detect_command(text: &str) -> CommandResult;
```

Simple prefix match. No ML needed — just string matching after Whisper output.

**3. Changes to `corrector.rs` → rename to `llm.rs`**

The corrector becomes a general-purpose LLM step that takes a mode config:
```rust
fn process(&mut self, text: &str, mode: &Mode) -> String {
    // Build prompt from mode.system_prompt + text
    // Set temperature from mode.temperature
    // Run inference
    // Safety guard
}
```

### Pipeline flow in session loop

```rust
// In rolling_transcribe callback:
if let Some(sentence) = new_sentence {
    let cleaned = fillers::remove_fillers(&sentence);

    // Check for safeword command
    match command::detect_command(&cleaned) {
        CommandResult::Command(mode_id) => {
            mode_manager.switch_to(&mode_id);
            // Update UI to show new mode
            // Do NOT paste
        }
        CommandResult::Text(text) => {
            let processed = if mode_manager.active().id == "bypass" {
                text
            } else {
                llm.process(&text, mode_manager.active())
            };
            paste_text(&processed);
        }
    }
}
```

## Model Requirements

| Mode | Min Model Size | Reason |
|------|---------------|--------|
| Correction | 0.5B Q8 | Simple homophone fixes |
| Polish | 1.5B+ | Needs sentence-level understanding |
| Translate | 3B+ | Cross-lingual requires more parameters |
| Email/Freewrite | 3B+ | Creative generation needs capacity |

**Recommendation:** Ship with Qwen2.5-3B-Instruct Q4 (~2GB) as the default. It handles all modes well. Keep 0.5B as a lightweight option for correction-only users.

For users with powerful GPUs, allow Qwen2.5-7B (~4GB) for best quality.

## Implementation Order

### Phase 1: Mode infrastructure (no new models needed)
1. Create `modes.rs` with built-in mode registry
2. Create `command.rs` with safeword detection
3. Rename corrector to general LLM processor
4. Add mode dropdown to Tauri UI
5. Add `default_mode` to config
6. Wire mode switching into session loop

### Phase 2: Better model
7. Download and test Qwen2.5-3B Q4 (~2GB GGUF)
8. Add model selector in settings (0.5B / 3B / 7B)
9. Benchmark latency per mode on Apple Silicon vs CPU

### Phase 3: Advanced
10. Custom mode editor in UI (user writes own system prompts)
11. Context carry-over (previous sentences inform translation context)
12. Streaming LLM output (show correction/translation in real-time)
13. Tool call support (voice-triggered actions beyond text: "Toff, 搜索天气")

## Example User Flows

### Flow 1: Default correction mode
```
[User sets default mode to "纠错" in settings]
[Double-shift to record]
User: "今天的天汽很好，我想去公园"
Pipeline: Whisper → "今天的天汽很好" → LLM(correct) → "今天的天气很好" → paste
```

### Flow 2: Voice-triggered translate
```
[Recording]
User: "Toff, 翻译成英文"
Pipeline: Whisper → "Toff, 翻译成英文" → command detected → switch to translate_en
[Still recording]
User: "今天天气很好，我们去公园吧"
Pipeline: Whisper → "今天天气很好" → LLM(translate_en) → "The weather is nice today, let's go to the park" → paste
```

### Flow 3: Email mode
```
User: "Toff, 写邮件"
Pipeline: switch to email mode
User: "跟老板说这周五的会议改到下周一"
Pipeline: Whisper → LLM(email) →
  "Dear [Boss],
   I would like to request that Friday's meeting be rescheduled to next Monday.
   Please let me know if this works for you.
   Best regards" → paste
```

### Flow 4: Reset to default
```
User: "Toff, 恢复"
Pipeline: switch back to default mode (correction)
```

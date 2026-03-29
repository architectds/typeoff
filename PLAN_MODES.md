# Typeoff — Multi-Mode LLM Pipeline Plan

## Vision

Typeoff is not just a voice input method — it's a **voice-driven AI writing assistant**. Two core modes:

- **Fast Mode** (current): real-time transcription → sentence-by-sentence paste. For chat, quick input.
- **Think Mode** (new): accumulate full speech → LLM rewrites everything → paste clean output. For emails, documents, structured content.

Fast Mode competes with 豆包/微信语音输入. Think Mode competes with Typeless ($19/month cloud service). Both run fully offline.

## Product Positioning

| | 豆包/微信语音 | Typeoff Fast | Typeless | Typeoff Think |
|---|---|---|---|---|
| Transcription | Cloud | Local (Whisper) | Cloud | Local (Whisper) |
| Output | Literal | Literal + filler removal | Restructured | Restructured |
| Latency | ~1s | ~3-6s streaming | ~5-10s batch | ~5-10s batch |
| Intent understanding | No | No | Yes | Yes (LLM) |
| Handles "前面说错了" | No | No | Yes | Yes (session memory) |
| Offline | No | Yes | No (crashes) | Yes |
| Price | Free | Free | $19/month | Free |

## Two-Mode Architecture

### Fast Mode (Current)

```
Mic → Filter → VAD → Whisper (every 3s) → Agreement → Filler Removal → [Optional LLM Correction] → Paste
```

- Sentences paste as you speak
- Low latency, real-time feel
- LLM correction is optional (0.5B, homophones only)
- Best for: chat, messaging, quick text entry

### Think Mode (New)

```
Mic → Filter → VAD → Whisper (full session) → Full Transcript → LLM 7B (rewrite) → Paste
```

- Nothing pastes during recording
- When you stop, LLM processes the entire transcript
- Removes filler, fixes errors, restructures, understands corrections
- Produces clean, structured output
- Best for: emails, documents, notes, long-form content

**Key difference:** Fast Mode processes sentence-by-sentence (streaming). Think Mode processes the whole session at once (batch). Think Mode needs a larger LLM (3B-7B) but only runs once at the end.

## Think Mode: How It Works

### Session Flow

```
1. User starts recording (double-shift)
2. User speaks freely for 30s - 5min
   - Can ramble, repeat, correct themselves
   - "其实前面说的不对，应该是..."
   - "嗯，那个，就是说..."
3. User stops recording (double-shift or silence)
4. Whisper transcribes full audio → raw transcript
5. LLM 7B processes raw transcript with system prompt:
   - Remove all filler words
   - Understand corrections ("前面说错了" → apply the correction)
   - Restructure into clean paragraphs
   - Maintain original meaning and tone
   - Output in same language as input
6. Clean result pasted into active app
```

### System Prompt (Think Mode)

```
你是一个语音转文字助手。用户通过语音说了以下内容。请将其整理为清晰、结构化的文字：

规则：
1. 去除所有口语填充词（嗯、啊、那个、就是、然后）
2. 如果用户在说话中纠正了前面的内容（如"前面说错了"），应用纠正
3. 去除重复和犹豫
4. 保持原文的意思和风格，不要添加用户没说的内容
5. 如果用户说的是列表或要点，输出为结构化列表
6. 保持原文语言，不要翻译
7. 只输出整理后的文字，不要解释

原始转录：
{raw_transcript}
```

### Model Requirements

| Mode | Model | Size | Latency (Apple Silicon) |
|------|-------|------|------------------------|
| Fast (correction) | Qwen 0.5B Q8 | ~530MB | ~0.3s/sentence |
| Think (rewrite) | Qwen 7B Q4 | ~4GB | ~3-5s for full rewrite |
| Think (lighter) | Qwen 3B Q4 | ~2GB | ~2-3s for full rewrite |

For Think Mode, the LLM runs once after the full recording, not per-sentence. So a 7B model is practical even on CPU (10-20s).

## Mode Switching

### Safeword Trigger (Voice)

User says **"Toff, [command]"** to switch modes:

| Voice Command | Mode | Description |
|---------------|------|-------------|
| "Toff, 快速模式" / "Toff, fast" | Fast Mode | Real-time streaming paste |
| "Toff, 整理模式" / "Toff, think" | Think Mode | Full session → rewrite → paste |
| "Toff, 翻译成英文" / "Toff, translate" | Translate Mode | Think mode + translate |
| "Toff, 写邮件" / "Toff, email" | Email Mode | Think mode + formal email format |
| "Toff, 总结" / "Toff, summarize" | Summarize Mode | Think mode + bullet point summary |
| "Toff, 恢复" / "Toff, reset" | Back to default | Reset to configured default mode |

### UI Mode Selector

Dropdown in settings or header bar. Persists across sessions.

```
┌──────────────────────────────┐
│ Mode: [Fast ▾]               │
├──────────────────────────────┤
│ ● Fast (直接输入)        ✓   │
│ ● Think (整理模式)           │
│ ● Translate (翻译)           │
│ ● Email (写邮件)             │
│ ● Summarize (总结)           │
│ ● Custom...                  │
└──────────────────────────────┘
```

## Implementation Plan

### Phase 1: Think Mode MVP
1. Add "mode" field to config (fast/think)
2. In Think Mode, skip streaming paste — accumulate full transcript
3. After recording stops, send full transcript to LLM with rewrite prompt
4. Paste the rewritten result
5. UI: mode selector dropdown
6. Model: Qwen 3B Q4 (~2GB) as default Think Mode model

### Phase 2: Better Think Mode
7. Session memory — accumulate across multiple recordings
8. Intent detection — understand "前面说错了" style corrections
9. Structured output — detect when user is listing items, output as bullet points
10. Larger model option — Qwen 7B Q4 for best quality

### Phase 3: Mode Ecosystem
11. Safeword voice trigger ("Toff, think")
12. Custom mode editor — user writes own system prompts
13. Mode-specific UI — show "thinking..." animation in Think Mode
14. API mode — send to cloud LLM (GPT-4, Claude) for users who want best quality

### Phase 4: Advanced
15. Context carry-over — previous session informs current rewrite
16. Multi-turn — keep talking after first rewrite, LLM appends
17. Tool calls — "Toff, search weather" triggers actions beyond text
18. Voice agent — continuous conversation with the LLM

## Competitive Analysis

### vs Typeless ($19/month)
- **Advantage**: Fully offline, no subscription, no server crashes
- **Advantage**: Privacy — nothing leaves the device
- **Advantage**: Fast Mode for quick input (Typeless only does batch)
- **Disadvantage**: Smaller model = lower quality rewrite (until 7B)
- **Disadvantage**: No cloud fallback for complex tasks

### vs 豆包/微信语音输入 (Free)
- **Advantage**: Think Mode for structured output
- **Advantage**: Offline, private
- **Advantage**: Filler removal, restructuring
- **Disadvantage**: Slower (local model vs cloud)
- **Disadvantage**: Requires model download

### Our Unique Position
**The only fully offline voice-to-structured-text tool.** Combines real-time transcription (Fast Mode) with AI-powered rewriting (Think Mode). No subscription, no cloud dependency, no data leaves the device.

## Example User Flows

### Flow 1: Fast Mode (Chat)
```
[Fast Mode active]
User: "今天下午三点开会，别忘了"
→ Paste: "今天下午三点开会，别忘了"
(Real-time, literal, filler-removed)
```

### Flow 2: Think Mode (Email)
```
[Think Mode active]
User: "嗯，那个，我想跟老板说一下，就是这周五的会议，
       啊，能不能改到下周一，因为，嗯，我这边有个客户要来，
       对，就是那个大客户，所以周五走不开"

→ Whisper: "嗯那个我想跟老板说一下就是这周五的会议啊能不能改到下周一
            因为嗯我这边有个客户要来对就是那个大客户所以周五走不开"

→ LLM rewrite: "这周五的会议能否改到下周一？我周五有重要客户来访，无法参加。"

→ Paste: "这周五的会议能否改到下周一？我周五有重要客户来访，无法参加。"
```

### Flow 3: Think Mode with Correction
```
[Think Mode active]
User: "这个项目的预算是50万，啊不对，是80万，
       主要花在三个方面，第一是人力成本，第二是设备采购，
       第三是...嗯...第三是场地租赁"

→ LLM understands "啊不对是80万" is a correction

→ Paste: "项目预算80万，主要分三部分：
          1. 人力成本
          2. 设备采购
          3. 场地租赁"
```

### Flow 4: Voice-triggered Mode Switch
```
[Fast Mode active]
User: "Toff, 整理模式"
→ Switch to Think Mode (no paste)

User: [speaks for 2 minutes about project update]

→ LLM produces structured project update

User: "Toff, 快速模式"
→ Switch back to Fast Mode
```

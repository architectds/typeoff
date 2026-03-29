"""Streaming transcription — sentence-based sliding window + LocalAgreement."""
import re
import time

# Common Whisper hallucinations on silence/noise
HALLUCINATIONS = {
    "", "you", "thank you.", "thanks for watching!", "thanks for watching.",
    "subscribe", "bye.", "bye", "thank you", "you.", "the end.",
    "thanks for listening.", "see you next time.", "thank you for watching.",
    "...", "MBC 뉴스 , 이덕영입니다.", "字幕by索兰娅梦", "请不吝点赞 订阅 转发 打赏支持明镜与点点栏目",
}

# Punctuation that triggers LOCK (sentence-ending + clause-ending)
SENTENCE_END = re.compile(r'[.!?。！？,，;；:：、]\s*$')
SENTENCE_SPLIT = re.compile(r'(?<=[.!?。！？,，;；:：、])\s*')

# Sliding window config
MAX_WINDOW_SECONDS = 12.0  # max audio to re-transcribe (~1.5 sentences)


def _is_cjk(char):
    """Check if a character is CJK (Chinese/Japanese/Korean)."""
    cp = ord(char)
    return (0x4E00 <= cp <= 0x9FFF or 0x3400 <= cp <= 0x4DBF or
            0x3040 <= cp <= 0x309F or 0x30A0 <= cp <= 0x30FF or
            0xAC00 <= cp <= 0xD7AF or 0xFF00 <= cp <= 0xFFEF)


def _tokenize(text):
    """Split text into tokens. CJK: per-character. Others: by whitespace."""
    tokens = []
    buf = []
    for ch in text:
        if _is_cjk(ch):
            if buf:
                tokens.append("".join(buf))
                buf = []
            tokens.append(ch)
        elif ch.isspace():
            if buf:
                tokens.append("".join(buf))
                buf = []
        else:
            buf.append(ch)
    if buf:
        tokens.append("".join(buf))
    return tokens


def _join_tokens(tokens):
    """Join tokens back into text. No spaces between adjacent CJK characters."""
    if not tokens:
        return ""
    parts = [tokens[0]]
    for i in range(1, len(tokens)):
        prev, cur = tokens[i - 1], tokens[i]
        # Add space unless both sides are CJK
        if prev and cur and _is_cjk(prev[-1]) and _is_cjk(cur[0]):
            parts.append(cur)
        else:
            parts.append(" " + cur)
    return "".join(parts)


def _common_prefix_words(words_a, words_b):
    """Longest common prefix between two word lists."""
    length = min(len(words_a), len(words_b))
    for i in range(length):
        if words_a[i] != words_b[i]:
            return words_a[:i]
    return words_a[:length]


def _fuzzy_agree(words_a, words_b, threshold=0.8):
    """Fuzzy agreement: if 80%+ tokens match positionally, return agreed tokens.

    Walks both lists simultaneously. Matching tokens are kept.
    Mismatches: take the token from the LATEST run (words_b).
    Returns (agreed_tokens, match_ratio) or ([], 0.0) if below threshold.
    """
    length = min(len(words_a), len(words_b))
    if length == 0:
        return [], 0.0

    matches = 0
    agreed = []
    for i in range(length):
        if words_a[i] == words_b[i]:
            matches += 1
            agreed.append(words_b[i])
        else:
            agreed.append(words_b[i])  # prefer latest

    ratio = matches / length
    if ratio >= threshold:
        return agreed, ratio
    return [], ratio


def _extract_complete_sentences(text):
    """Split text into (complete_sentences, remainder).

    complete_sentences: text up to and including the last sentence-ending punctuation
    remainder: text after that (the in-progress sentence)
    """
    # Find last sentence-ending punctuation
    parts = SENTENCE_SPLIT.split(text)
    if len(parts) <= 1:
        # Check if the single part ends with punctuation
        if SENTENCE_END.search(text):
            return text, ""
        return "", text

    # Everything except the last part is complete
    # But check if the last part also ends with punctuation
    if SENTENCE_END.search(parts[-1]):
        return text, ""

    complete = " ".join(parts[:-1])
    remainder = parts[-1]
    return complete, remainder


class StreamingTranscriber:
    """Sentence-based sliding window transcription.

    Strategy:
        1. Record continuously, transcribe rolling buffer every N seconds
        2. Word-level LocalAgreement: only trust words that match across 2 runs
        3. When a complete sentence is confirmed → LOCK it, paste it, slide window
        4. Re-transcribe only the audio after the locked sentence (~5-10s)
        5. Final pass: re-transcribe last incomplete sentence for accuracy

    This keeps the buffer short (~10s max) so transcription stays fast (~0.5s),
    and pasting is sentence-by-sentence (clean, no fragile char-count replacement).
    """

    def __init__(self, backend, interval=3.0, sr=16000):
        self.backend = backend
        self.interval = interval
        self.sr = sr

        self._prev_words = []           # words from previous transcription
        self._confirmed_words = []      # words confirmed by agreement

        self._locked_sentences = []     # complete sentences, pasted and done
        self._locked_text = ""          # joined locked sentences
        self._pending_text = ""         # current in-progress sentence (not yet pasted)

        self._window_start_sample = 0   # audio sample index where current window starts

        # Fail safe: force push after N transcriptions of same window
        self._window_pass_count = 0     # how many times current window has been transcribed
        self._max_passes = 3            # force push after this many passes

    def rolling_transcribe(self, full_audio, language=None):
        """Run one rolling transcription pass with fuzzy agreement + fail safe.

        Returns:
            (new_sentence: str or None, pending_text: str)
        """
        window_audio = full_audio[self._window_start_sample:]

        if len(window_audio) < int(0.5 * self.sr):
            return None, self._pending_text

        t0 = time.time()
        text = self.backend.transcribe(window_audio, sr=self.sr, language=language)
        elapsed = time.time() - t0

        if text.lower().strip() in HALLUCINATIONS:
            return None, self._pending_text

        current_words = _tokenize(text)
        self._window_pass_count += 1

        # --- Agreement logic ---
        agreed_words = []

        if self._prev_words:
            # Try strict prefix first
            strict = _common_prefix_words(self._prev_words, current_words)
            if len(strict) >= 3:
                agreed_words = list(strict)
            else:
                # Try fuzzy agreement (80% threshold)
                fuzzy, ratio = _fuzzy_agree(self._prev_words, current_words, threshold=0.8)
                if fuzzy:
                    agreed_words = fuzzy

        self._prev_words = current_words

        # Update confirmed words
        if agreed_words and len(agreed_words) > len(self._confirmed_words):
            self._confirmed_words = agreed_words

        confirmed_text = _join_tokens(self._confirmed_words)

        # --- Fail safe: force push after N passes on same window ---
        if self._window_pass_count >= self._max_passes:
            full_text = _join_tokens(current_words)
            if full_text.strip():
                # Push up to last punctuation, keep the rest for next window
                complete, remainder = _extract_complete_sentences(full_text)
                if complete:
                    self._do_lock(complete, current_words, window_audio, remainder)
                    return complete, self._pending_text
                else:
                    # No punctuation at all — push everything as last resort
                    self._do_lock(full_text, current_words, window_audio)
                    return full_text, self._pending_text

        # --- Normal lock: agreement + punctuation or length ---
        new_sentence = None

        if confirmed_text:
            complete, remainder = _extract_complete_sentences(confirmed_text)

            if complete:
                new_sentence = complete
                self._do_lock(complete, current_words, window_audio, remainder)
            elif len(confirmed_text) > 40:
                new_sentence = confirmed_text
                self._do_lock(confirmed_text, current_words, window_audio)
            else:
                self._pending_text = confirmed_text
        else:
            self._pending_text = _join_tokens(current_words)

        return new_sentence, self._pending_text

    def _do_lock(self, lock_text, current_words, window_audio, remainder=""):
        """Lock text, slide window, reset agreement state."""
        if self._locked_text:
            self._locked_text = self._locked_text + lock_text
        else:
            self._locked_text = lock_text
        self._locked_sentences.append(lock_text)
        self._pending_text = remainder

        # Slide window
        if len(current_words) > 0:
            locked_count = len(_tokenize(lock_text))
            ratio = locked_count / len(current_words)
            self._window_start_sample += int(ratio * len(window_audio))

        # Reset
        remaining = _tokenize(remainder) if remainder else []
        self._prev_words = remaining
        self._confirmed_words = remaining.copy()
        self._window_pass_count = 0

    def final_transcribe(self, full_audio, language=None):
        """Final pass on remaining audio after last locked sentence.

        Returns:
            (final_remainder: str, full_text: str)
            final_remainder: the last bit of text to paste
            full_text: complete transcription (locked + remainder)
        """
        # Only transcribe audio after locked sentences
        window_audio = full_audio[self._window_start_sample:]

        if len(window_audio) < int(0.3 * self.sr):
            return "", self._locked_text

        text = self.backend.transcribe(window_audio, sr=self.sr, language=language)

        if text.lower().strip() in HALLUCINATIONS:
            text = ""

        # The final remainder to paste
        final_remainder = text.strip()
        if final_remainder and self._locked_text:
            final_remainder = " " + final_remainder

        full_text = self._locked_text + final_remainder

        return final_remainder, full_text

    def get_all_text(self):
        """Return all text produced so far (locked + pending)."""
        if self._pending_text:
            return (self._locked_text + " " + self._pending_text).strip()
        return self._locked_text

    def get_window_duration(self):
        """Current window duration in seconds."""
        return self._window_start_sample / self.sr

    def reset(self):
        """Reset state for next utterance."""
        self._prev_words = []
        self._confirmed_words = []
        self._locked_sentences = []
        self._locked_text = ""
        self._pending_text = ""
        self._window_start_sample = 0
        self._window_pass_count = 0

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

# Sentence-ending punctuation (covers English, Chinese, etc.)
SENTENCE_END = re.compile(r'[.!?。！？]\s*$')
SENTENCE_SPLIT = re.compile(r'(?<=[.!?。！？])\s+')

# Sliding window config
MAX_WINDOW_SECONDS = 12.0  # max audio to re-transcribe (~1.5 sentences)


def _tokenize(text):
    """Split text into words."""
    return text.split()


def _common_prefix_words(words_a, words_b):
    """Longest common prefix between two word lists."""
    length = min(len(words_a), len(words_b))
    for i in range(length):
        if words_a[i] != words_b[i]:
            return words_a[:i]
    return words_a[:length]


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

    def rolling_transcribe(self, full_audio, language=None):
        """Run one rolling transcription pass.

        Args:
            full_audio: complete audio buffer from recorder
            language: language hint

        Returns:
            (new_sentence: str or None, pending_text: str)
            new_sentence: a complete sentence to paste (or None)
            pending_text: current in-progress text (for display, not pasting)
        """
        # Slice to current window (audio after locked sentences)
        window_audio = full_audio[self._window_start_sample:]

        # Skip if window too short
        if len(window_audio) < int(0.5 * self.sr):
            return None, self._pending_text

        t0 = time.time()
        text = self.backend.transcribe(window_audio, sr=self.sr, language=language)
        elapsed = time.time() - t0

        # Filter hallucinations
        if text.lower().strip() in HALLUCINATIONS:
            return None, self._pending_text

        current_words = _tokenize(text)

        # Word-level LocalAgreement
        agreed = _common_prefix_words(self._prev_words, current_words)
        new_confirmed = agreed[len(self._confirmed_words):]
        self._prev_words = current_words

        if new_confirmed:
            self._confirmed_words = agreed

        confirmed_text = " ".join(self._confirmed_words)

        # Check for complete sentences in confirmed text
        complete, remainder = _extract_complete_sentences(confirmed_text)

        new_sentence = None
        if complete and complete != self._locked_text:
            # New complete sentence(s) confirmed — lock and slide
            new_sentence = complete[len(self._locked_text):].strip()
            if self._locked_text:
                new_sentence = " " + new_sentence

            self._locked_text = complete
            self._locked_sentences.append(new_sentence)
            self._pending_text = remainder

            # Slide window: estimate where the locked audio ends
            # Rough heuristic: (locked words / total words) * total audio
            if len(current_words) > 0:
                locked_word_count = len(_tokenize(complete))
                ratio = locked_word_count / len(current_words)
                self._window_start_sample += int(ratio * len(window_audio))

            # Reset agreement state for new window
            self._prev_words = _tokenize(remainder) if remainder else []
            self._confirmed_words = self._prev_words.copy()

            print(f"  [{elapsed:.1f}s] LOCKED: \"{new_sentence.strip()}\"")
            print(f"         pending: \"{remainder}\"")
        else:
            self._pending_text = confirmed_text[len(self._locked_text):] if confirmed_text.startswith(self._locked_text) else confirmed_text
            print(f"  [{elapsed:.1f}s] \"{text}\"")
            print(f"         confirmed: \"{confirmed_text}\" | pending: \"{self._pending_text}\"")

        return new_sentence, self._pending_text

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

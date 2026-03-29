"""Post-processing: remove filler words and collapse stutters."""
import re

# --- Filler word lists ---

CHINESE_FILLERS = {"嗯", "啊", "那个", "就是", "然后", "这个", "对吧", "那么"}

ENGLISH_FILLERS = {"uh", "um", "you know", "like", "so", "right", "i mean"}

# Multi-word fillers need special handling (matched before single-word)
ENGLISH_MULTI_FILLERS = {"uh huh", "you know", "i mean"}

# --- CJK helpers ---

def _is_cjk(char):
    cp = ord(char)
    return (0x4E00 <= cp <= 0x9FFF or 0x3400 <= cp <= 0x4DBF or
            0x3040 <= cp <= 0x309F or 0x30A0 <= cp <= 0x30FF or
            0xAC00 <= cp <= 0xD7AF or 0xFF00 <= cp <= 0xFFEF)


def _is_cjk_text(text):
    """Check if text is primarily CJK."""
    cjk_count = sum(1 for c in text if _is_cjk(c))
    return cjk_count > len(text) * 0.3 if text else False


# --- Chinese filler removal ---

def _remove_chinese_fillers(text):
    """Remove standalone Chinese filler words.

    A filler is standalone if it appears at start/end of text,
    or is surrounded by punctuation/spaces (not embedded in a compound word).
    """
    for filler in sorted(CHINESE_FILLERS, key=len, reverse=True):
        # Remove filler at start of text (optionally followed by comma/space)
        text = re.sub(r'^' + re.escape(filler) + r'[,，、\s]*', '', text)
        # Remove filler at end of text (optionally preceded by comma/space)
        text = re.sub(r'[,，、\s]*' + re.escape(filler) + r'$', '', text)
        # Remove filler between punctuation/sentence boundaries
        # Match filler preceded and followed by punctuation or CJK chars
        text = re.sub(
            r'([。！？,，;；:：、])\s*' + re.escape(filler) + r'\s*',
            r'\1',
            text,
        )
        # Remove filler followed by comma (standalone usage mid-sentence)
        text = re.sub(
            re.escape(filler) + r'[,，、]\s*',
            '',
            text,
        )
    return text.strip()


# --- English filler removal ---

def _remove_english_fillers(text):
    """Remove standalone English filler words/phrases.

    Only removes fillers when they appear as standalone tokens:
    - At sentence boundaries (start, end, after/before punctuation)
    - Separated by commas
    - Not when they're part of a meaningful phrase
    """
    # Handle multi-word fillers first
    for filler in ENGLISH_MULTI_FILLERS:
        # At start of text
        text = re.sub(
            r'(?i)^' + re.escape(filler) + r'[,;]?\s*',
            '',
            text,
        )
        # At end of text
        text = re.sub(
            r'(?i)[,;]?\s*' + re.escape(filler) + r'[.!?]?\s*$',
            '',
            text,
        )
        # Between commas / after punctuation
        text = re.sub(
            r'(?i)([.!?,;])\s*' + re.escape(filler) + r'\s*([,;]?\s*)',
            r'\1 ',
            text,
        )
        # Comma-delimited standalone
        text = re.sub(
            r'(?i),\s*' + re.escape(filler) + r'\s*,',
            ',',
            text,
        )

    # Single-word fillers (only match whole words via \b)
    for filler in sorted(ENGLISH_FILLERS - ENGLISH_MULTI_FILLERS, key=len, reverse=True):
        # At start of text (with optional comma after)
        text = re.sub(
            r'(?i)^\b' + re.escape(filler) + r'\b[,;]?\s*',
            '',
            text,
        )
        # At end of text (with optional comma before)
        text = re.sub(
            r'(?i)[,;]?\s*\b' + re.escape(filler) + r'\b[.!?]?\s*$',
            '',
            text,
        )
        # After sentence-ending punctuation (filler starting new clause)
        text = re.sub(
            r'(?i)([.!?])\s*\b' + re.escape(filler) + r'\b[,;]?\s+',
            r'\1 ',
            text,
        )
        # Comma-separated standalone filler
        text = re.sub(
            r'(?i),\s*\b' + re.escape(filler) + r'\b\s*,',
            ',',
            text,
        )

    # Clean up multiple spaces
    text = re.sub(r'  +', ' ', text)
    return text.strip()


# --- Stutter collapse ---

def _collapse_stutters(text, max_repeats=2):
    """If the same word appears 3+ times consecutively, keep only 1.

    Works for both CJK characters and space-separated words.
    """
    # Handle CJK character repetition (e.g., 嗯嗯嗯 -> 嗯)
    # Match any single CJK char repeated 3+ times
    text = re.sub(
        r'([\u4e00-\u9fff\u3400-\u4dbf\u3040-\u309f\u30a0-\u30ff])\1{2,}',
        r'\1',
        text,
    )

    # Handle word-level repetition for non-CJK (e.g., "the the the" -> "the")
    words = text.split()
    if len(words) < 3:
        return text

    result = []
    i = 0
    while i < len(words):
        word = words[i]
        # Count consecutive occurrences
        count = 1
        while i + count < len(words) and words[i + count].lower() == word.lower():
            count += 1

        if count >= 3:
            # Keep only 1 occurrence
            result.append(word)
        else:
            # Keep all (1 or 2 repetitions are fine)
            result.extend(words[i:i + count])
        i += count

    return ' '.join(result)


# --- Public API ---

def remove_fillers(text):
    """Remove filler words and collapse stutters from transcription output.

    Applies both Chinese and English filler removal (safe to run on mixed text),
    then collapses stutters.

    Args:
        text: Transcribed text string.

    Returns:
        Cleaned text with fillers removed and stutters collapsed.
    """
    if not text or not text.strip():
        return text

    text = text.strip()

    # Apply both — the regex patterns are specific enough to not cross-interfere
    if _is_cjk_text(text):
        text = _remove_chinese_fillers(text)
    else:
        text = _remove_english_fillers(text)

    text = _collapse_stutters(text)

    # Final cleanup: remove leading/trailing punctuation artifacts
    text = re.sub(r'^[,，、;；\s]+', '', text)
    text = re.sub(r'[,，、;；\s]+$', '', text)

    return text.strip()

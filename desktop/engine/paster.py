"""Cross-platform text paste into active application."""
import platform
import subprocess
import time

PLATFORM = platform.system()


def paste_text(text):
    """Copy text to clipboard and simulate paste keystroke."""
    if not text:
        return

    if PLATFORM == "Darwin":
        _paste_mac(text)
    elif PLATFORM == "Windows":
        _paste_windows(text)
    else:
        _paste_linux(text)


def replace_text(old_length, new_text):
    """Select and replace previously pasted text.

    Used for final correction: select back `old_length` chars, then paste new text.
    """
    if not new_text:
        return

    if PLATFORM == "Darwin":
        # Select back old_length characters via Shift+Left, then paste
        script = f'''
        tell application "System Events"
            repeat {old_length} times
                key code 123 using shift down
            end repeat
        end tell
        '''
        subprocess.run(["osascript", "-e", script], check=False)
        time.sleep(0.05)
        _paste_mac(new_text)

    elif PLATFORM == "Windows":
        from pynput.keyboard import Controller, Key
        kb = Controller()
        for _ in range(old_length):
            kb.press(Key.left)
            kb.release(Key.left)
        time.sleep(0.05)
        _paste_windows(new_text)

    else:
        _paste_linux(new_text)


def _paste_mac(text):
    """macOS: pbcopy + Cmd+V via osascript."""
    proc = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
    proc.communicate(text.encode("utf-8"))
    subprocess.run([
        "osascript", "-e",
        'tell application "System Events" to keystroke "v" using command down'
    ], check=False)


def _paste_windows(text):
    """Windows: clip.exe + Ctrl+V via pynput."""
    proc = subprocess.Popen(["clip.exe"], stdin=subprocess.PIPE)
    proc.communicate(text.encode("utf-16-le"))
    from pynput.keyboard import Controller, Key
    kb = Controller()
    kb.press(Key.ctrl)
    kb.press('v')
    kb.release('v')
    kb.release(Key.ctrl)


def _paste_linux(text):
    """Linux: xclip + Ctrl+V via pynput."""
    proc = subprocess.Popen(["xclip", "-selection", "clipboard"], stdin=subprocess.PIPE)
    proc.communicate(text.encode("utf-8"))
    from pynput.keyboard import Controller, Key
    kb = Controller()
    kb.press(Key.ctrl)
    kb.press('v')
    kb.release('v')
    kb.release(Key.ctrl)

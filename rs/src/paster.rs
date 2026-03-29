/// Cross-platform text paste into active application.
///
/// Port of python/engine/paster.py.
/// Mac: Cmd+V, Windows/Linux: Ctrl+V.

use arboard::Clipboard;
use std::thread;
use std::time::Duration;

/// Copy text to clipboard and simulate paste keystroke.
pub fn paste_text(text: &str) {
    if text.is_empty() {
        return;
    }

    // Copy to clipboard
    match Clipboard::new() {
        Ok(mut clipboard) => {
            if let Err(e) = clipboard.set_text(text.to_string()) {
                eprintln!("[typeoff] Failed to set clipboard: {}", e);
                return;
            }
        }
        Err(e) => {
            eprintln!("[typeoff] Failed to open clipboard: {}", e);
            return;
        }
    }

    thread::sleep(Duration::from_millis(50));

    // Simulate paste keystroke
    // Each call creates a fresh Enigo — avoids stale state issues
    #[cfg(target_os = "macos")]
    paste_macos();

    #[cfg(target_os = "windows")]
    paste_windows();

    #[cfg(target_os = "linux")]
    paste_linux();
}

#[cfg(target_os = "macos")]
fn paste_macos() {
    // Small delay to let the target app regain focus after any window changes
    thread::sleep(Duration::from_millis(100));

    // Use osascript to send Cmd+V to the frontmost app
    // This requires Accessibility permission for System Events
    let _ = std::process::Command::new("osascript")
        .arg("-e")
        .arg("tell application \"System Events\" to keystroke \"v\" using command down")
        .output();
}

#[cfg(target_os = "windows")]
fn paste_windows() {
    use enigo::{Enigo, Key, Keyboard, Settings};
    if let Ok(mut enigo) = Enigo::new(&Settings::default()) {
        let _ = enigo.key(Key::Control, enigo::Direction::Press);
        let _ = enigo.key(Key::Unicode('v'), enigo::Direction::Click);
        let _ = enigo.key(Key::Control, enigo::Direction::Release);
    }
}

#[cfg(target_os = "linux")]
fn paste_linux() {
    use enigo::{Enigo, Key, Keyboard, Settings};
    if let Ok(mut enigo) = Enigo::new(&Settings::default()) {
        let _ = enigo.key(Key::Control, enigo::Direction::Press);
        let _ = enigo.key(Key::Unicode('v'), enigo::Direction::Click);
        let _ = enigo.key(Key::Control, enigo::Direction::Release);
    }
}

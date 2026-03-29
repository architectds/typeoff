use rdev::{listen, Event, EventType, Key};
use std::sync::mpsc::Sender;
use std::time::Instant;

/// Listen for double-shift (two taps within 400ms).
/// Sends a signal on each double-shift detected.
pub fn listen_double_shift(tx: Sender<()>) {
    let mut last_shift_release = Instant::now() - std::time::Duration::from_secs(10);
    let mut shift_solo = false;

    listen(move |event: Event| {
        match event.event_type {
            EventType::KeyPress(key) => {
                if key == Key::ShiftLeft || key == Key::ShiftRight {
                    shift_solo = true;
                } else {
                    shift_solo = false; // Another key pressed during shift hold
                }
            }
            EventType::KeyRelease(key) => {
                if (key == Key::ShiftLeft || key == Key::ShiftRight) && shift_solo {
                    let now = Instant::now();
                    if now.duration_since(last_shift_release).as_millis() < 400 {
                        // Double shift detected
                        let _ = tx.send(());
                        last_shift_release = Instant::now() - std::time::Duration::from_secs(10); // Reset
                    } else {
                        last_shift_release = now;
                    }
                }
            }
            _ => {}
        }
    })
    .expect("Failed to listen for hotkeys");
}

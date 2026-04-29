use std::io;

/// Click at an absolute screen position using evdev/uinput.
///
/// This replaces the Python mouse_service.py Unix socket approach
/// with direct uinput writes — no IPC overhead.
pub fn click(x: i32, y: i32, button: u32, repeat: u32) -> io::Result<()> {
    use evdev::uinput::VirtualDeviceBuilder;
    use evdev::{AbsInfo, AbsoluteAxisType, AttributeSet, EventType, InputEvent, Key, UinputAbsSetup};
    use std::thread;
    use std::time::Duration;

    // Screen dimensions (reasonable defaults; evdev normalizes anyway)
    let abs_max: i32 = 10000;

    let abs_x_setup = UinputAbsSetup::new(
        AbsoluteAxisType::ABS_X,
        AbsInfo::new(0, 0, abs_max, 0, 0, 1),
    );
    let abs_y_setup = UinputAbsSetup::new(
        AbsoluteAxisType::ABS_Y,
        AbsInfo::new(0, 0, abs_max, 0, 0, 1),
    );

    let mut keys = AttributeSet::<Key>::new();
    keys.insert(Key::BTN_LEFT);
    keys.insert(Key::BTN_RIGHT);
    keys.insert(Key::BTN_MIDDLE);

    let mut device = VirtualDeviceBuilder::new()?
        .name("qhints-rs mouse")
        .with_absolute_axis(&abs_x_setup)?
        .with_absolute_axis(&abs_y_setup)?
        .with_keys(&keys)?
        .build()?;

    // Small delay for uinput device to register
    thread::sleep(Duration::from_millis(30));

    // Move to position (absolute coordinates)
    // We need to get screen size to normalize; use a reasonable default
    let move_events = [
        InputEvent::new(EventType::ABSOLUTE, AbsoluteAxisType::ABS_X.0, x),
        InputEvent::new(EventType::ABSOLUTE, AbsoluteAxisType::ABS_Y.0, y),
        InputEvent::new(EventType::SYNCHRONIZATION, 0, 0),
    ];
    device.emit(&move_events)?;
    thread::sleep(Duration::from_millis(10));

    // Map button number to evdev key
    let btn = match button {
        1 => Key::BTN_LEFT,
        2 => Key::BTN_MIDDLE,
        3 => Key::BTN_RIGHT,
        _ => Key::BTN_LEFT,
    };

    // Click
    for _ in 0..repeat {
        let click_events = [
            InputEvent::new(EventType::KEY, btn.code(), 1), // down
            InputEvent::new(EventType::SYNCHRONIZATION, 0, 0),
        ];
        device.emit(&click_events)?;
        thread::sleep(Duration::from_millis(10));

        let release_events = [
            InputEvent::new(EventType::KEY, btn.code(), 0), // up
            InputEvent::new(EventType::SYNCHRONIZATION, 0, 0),
        ];
        device.emit(&release_events)?;
        thread::sleep(Duration::from_millis(10));
    }

    Ok(())
}

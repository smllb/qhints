use std::io::Write;
use std::os::unix::net::UnixStream;

pub fn click(
    x: i32,
    y: i32,
    button: u32,
    repeat: u32,
) -> Result<(), Box<dyn std::error::Error>> {
    let socket_path = "/tmp/hints_mouse_service";
    let mut stream = UnixStream::connect(socket_path)?;

    // Payload matches hintsd json expectations
    let payload = serde_json::json!({
        "method": "click",
        "args": [x, y, button, [1, 0]],
        "kwargs": {
            "repeat": repeat,
            "absolute": true
        }
    });

    let msg = payload.to_string();
    stream.write_all(msg.as_bytes())?;
    
    // hintsd replies with an empty dict or result, optionally wait or return immediately
    Ok(())
}

use crate::child::Child;
use crate::config::ApplicationRule;
use crate::window_system::WindowInfo;

use x11rb::connection::Connection;
use x11rb::protocol::xproto::{ConnectionExt, ImageFormat};
use x11rb::rust_connection::RustConnection;

pub fn get_children(
    window_info: &WindowInfo,
    rule: &ApplicationRule,
) -> Result<Vec<Child>, Box<dyn std::error::Error>> {
    // 1. Take screenshot
    let (x, y, mut w, mut h) = window_info.extents;
    if w <= 0 { w = 1; }
    if h <= 0 { h = 1; }

    let (conn, screen_num) = RustConnection::connect(None)?;
    let setup = conn.setup();
    let root = setup.roots[screen_num].root;

    let reply = conn.get_image(ImageFormat::Z_PIXMAP, root, x as i16, y as i16, w as u16, h as u16, !0)?.reply()?;
    let data = reply.data;

    if data.len() < (w * h * 4) as usize {
        return Err("Image data too short".into());
    }

    // 2. Convert BGRA to Luma8 directly
    let mut luma = image::GrayImage::new(w as u32, h as u32);
    for (i, chunk) in data.chunks_exact(4).enumerate() {
        if i >= (w * h) as usize {
            break;
        }
        let b = chunk[0] as f32;
        let g = chunk[1] as f32;
        let r = chunk[2] as f32;
        // BT.601 conversion: 0.299 R + 0.587 G + 0.114 B
        let l = (0.299 * r + 0.587 * g + 0.114 * b) as u8;
        
        let cx = (i as u32) % (w as u32);
        let cy = (i as u32) / (w as u32);
        luma.put_pixel(cx, cy, image::Luma([l]));
    }

    // 3. Edge detection
    let edges = imageproc::edges::canny(&luma, rule.canny_min_val as f32, rule.canny_max_val as f32);

    // 4. Dilate
    // OpenCV uses a kernel of size NxN. A 3x3 square kernel is equivalent to LInf norm distance 1.
    // So the radius (k) for imageproc is kernel_size / 2.
    let radius = (rule.kernel_size / 2) as u8;
    let dilated = imageproc::morphology::dilate(&edges, imageproc::distance_transform::Norm::LInf, radius);

    // 5. Find contours and bounding boxes
    let contours = imageproc::contours::find_contours(&dilated);
    let mut children = Vec::new();

    for contour in contours {
        // Find bounding rect
        let mut min_x = u32::MAX;
        let mut min_y = u32::MAX;
        let mut max_x = 0;
        let mut max_y = 0;

        for pt in contour.points {
            if pt.x < min_x { min_x = pt.x; }
            if pt.y < min_y { min_y = pt.y; }
            if pt.x > max_x { max_x = pt.x; }
            if pt.y > max_y { max_y = pt.y; }
        }

        let child_w = max_x.saturating_sub(min_x).saturating_add(1) as i32;
        let child_h = max_y.saturating_sub(min_y).saturating_add(1) as i32;

        children.push(Child {
            absolute_position: ((x + min_x as i32) as f64, (y + min_y as i32) as f64),
            relative_position: (min_x as f64, min_y as f64),
            width: child_w as f64,
            height: child_h as f64,
        });
    }

    Ok(children)
}

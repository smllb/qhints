mod backend;
mod child;
mod config;
mod hints;
mod mouse;
mod overlay;
mod window_system;

use crate::child::Child;
use crate::window_system::WindowSystem;
use clap::Parser;
use std::collections::{HashMap, HashSet};
use std::time::Instant;

#[derive(Parser)]
#[command(name = "qhints-rs", about = "Keyboard-driven UI navigation for Linux")]
struct Cli {
    /// Mode: hint or scroll
    #[arg(short, long, default_value = "hint")]
    mode: String,

    /// Verbosity level
    #[arg(short, long, action = clap::ArgAction::Count)]
    verbose: u8,
}

fn main() {
    let total_start = Instant::now();

    let cli = Cli::parse();

    // Initialize logging
    let log_level = match cli.verbose {
        0 => log::LevelFilter::Info,
        1 => log::LevelFilter::Debug,
        _ => log::LevelFilter::Trace,
    };
    env_logger::Builder::new().filter_level(log_level).init();

    // Load config
    let t = Instant::now();
    let config = config::load_config();
    log::debug!("Config loaded in {:?}", t.elapsed());

    match cli.mode.as_str() {
        "hint" => hint_mode(&config, total_start),
        "scroll" => {
            log::warn!("Scroll mode not yet implemented in Rust binary");
        }
        _ => {
            log::error!("Unknown mode: {}", cli.mode);
        }
    }
}

fn hint_mode(config: &config::Config, total_start: Instant) {
    // Initialize X11 window system
    let t = Instant::now();
    let ws = match window_system::x11::X11::new() {
        Ok(ws) => ws,
        Err(e) => {
            log::error!("Failed to initialize X11: {}", e);
            return;
        }
    };
    log::debug!("X11 init in {:?}", t.elapsed());

    let win_info = ws.focused_window().clone();
    log::debug!(
        "Active window: '{}' (PID {}) at {:?}",
        win_info.app_name,
        win_info.pid,
        win_info.extents
    );

    // Get application rules (use app-specific or default)
    let rule = config
        .application_rules
        .get(&win_info.app_name)
        .cloned()
        .unwrap_or_else(|| {
            config
                .application_rules
                .get("default")
                .cloned()
                .unwrap_or_default()
        });

    // AT-SPI tree walk (async)
    let t = Instant::now();
    let mut children = {
        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .expect("Failed to create tokio runtime");

        rt.block_on(async {
            match tokio::time::timeout(std::time::Duration::from_millis(150), async {
                let backend = backend::atspi::AtspiBackend::new(win_info.clone(), rule.clone()).await?;
                backend.get_children().await
            }).await {
                Ok(Ok(children)) => children,
                Ok(Err(e)) => {
                    log::debug!("AT-SPI error: {}", e);
                    Vec::new()
                }
                Err(_) => {
                    log::debug!("AT-SPI timed out after 150ms");
                    Vec::new()
                }
            }
        })
    };
    log::debug!("AT-SPI tree walk: {:?} ({} children)", t.elapsed(), children.len());

    // Imageproc fallback
    if children.is_empty() {
        log::debug!("AT-SPI found no children. Falling back to Imageproc.");
        let cv_start = Instant::now();
        children = backend::imageproc::get_children(&win_info, &rule).unwrap_or_else(|e| {
            log::error!("Imageproc fallback failed: {}", e);
            Vec::new()
        });
        log::debug!("Imageproc fallback: {:?} ({} children)", cv_start.elapsed(), children.len());
    }

    if children.is_empty() {
        log::debug!("No accessible children found");
        return;
    }

    // Compute hints
    let t = Instant::now();
    let (_, _, w, h) = win_info.extents;
    let hint_map = hints::get_hints(&children, &config.alphabet, Some((w as f64, h as f64)));
    log::debug!("Hint computation: {:?} ({} hints)", t.elapsed(), hint_map.len());

    // Cull overlapping hints and relabel to 2-char max, preserving zone-based first key
    let hint_map = cull_and_relabel(config, &hint_map, &children, (w as f64, h as f64));
    log::debug!("After culling/relabeling: {} hints", hint_map.len());

    log::debug!("Total pre-overlay: {:?}", total_start.elapsed());

    // Show overlay
    let (x, y, width, height) = win_info.extents;
    if let Some(action) = overlay::show_overlay(config, &hint_map, &children, x, y, width, height) {
        log::debug!("Action: {:?}", action);
        
        match action.action.as_str() {
            "click" | "hover" => {
                // Spawn a background process to click after GTK fully exits
                std::process::Command::new("sh")
                    .arg("-c")
                    .arg(format!(
                        "xdotool mousemove {} {} click {}",
                        action.x, action.y, action.button
                    ))
                    .spawn()
                    .expect("Failed to spawn xdotool");
            }
            _ => {
                log::debug!("Unhandled action: {}", action.action);
            }
        }
    }
}

/// Cull overlapping hints and relabel survivors with zone-based 1-2 character labels
/// Cull overlapping hints and relabel survivors with zone-based 2-character labels
/// Cull overlapping hints and relabel survivors with zone-based 2-character labels
fn cull_and_relabel(
    config: &config::Config,
    hints: &HashMap<String, usize>,
    children: &[Child],
    window_size: (f64, f64),
) -> HashMap<String, usize> {
    let alpha_chars: Vec<char> = config.alphabet.chars().collect();
    let h = &config.hints;
    let (width, height) = window_size;
    
    // Build rectangles for overlap detection
    let mut items: Vec<(String, usize, f64, f64, f64, f64)> = Vec::new();
    for (label, &child_idx) in hints {
        let child = &children[child_idx];
        let (rx, ry) = child.relative_position;
        let w = (label.len() as f64 * 12.0) + h.hint_width_padding;
        let hh = h.hint_height;
        items.push((label.clone(), child_idx, rx, ry, w, hh));
    }
    
    if items.is_empty() {
        return HashMap::new();
    }
    
    // Calculate grid alignment scores for each item
    let alignment_scores: Vec<f64> = items.iter().map(|item| {
        let (_, _, x, y, w, h) = *item;
        let cx = x + w / 2.0;
        let cy = y + h / 2.0;
        
        // Score based on how well this element aligns with others
        let mut horizontal_alignments = 0;
        let mut vertical_alignments = 0;
        
        for other in &items {
            let (_, _, ox, oy, ow, oh) = *other;
            let ocx = ox + ow / 2.0;
            let ocy = oy + oh / 2.0;
            
            // Check horizontal alignment (similar y)
            if (cy - ocy).abs() < h * 1.5 && (cx - ocx).abs() > w * 0.5 {
                horizontal_alignments += 1;
            }
            // Check vertical alignment (similar x)
            if (cx - ocx).abs() < w * 1.5 && (cy - ocy).abs() > h * 0.5 {
                vertical_alignments += 1;
            }
        }
        
        // Bonus for being part of aligned groups
        (horizontal_alignments as f64 + vertical_alignments as f64) * 0.1 + 
        // Bonus for larger elements (more important)
        (w * h).sqrt() / 100.0
    }).collect();
    
    // Create scored indices and sort by quality
    let mut scored_indices: Vec<(usize, f64)> = (0..items.len())
        .map(|i| (i, alignment_scores[i]))
        .collect();
    
    // Sort by score (highest first) but keep shorter labels as tiebreaker
    scored_indices.sort_by(|a, b| {
        b.1.partial_cmp(&a.1)
            .unwrap_or(std::cmp::Ordering::Equal)
            .then(items[a.0].0.len().cmp(&items[b.0].0.len()))
    });
    
    // Cull using spatial grid with minimum distance
    let min_distance = 30.0; // Minimum distance between hint centers
    let mut keep = vec![true; items.len()];
    
    for &(i, _) in &scored_indices {
        if !keep[i] { continue; }
        
        let (_, _, x1, y1, w1, h1) = items[i];
        let cx1 = x1 + w1 / 2.0;
        let cy1 = y1 + h1 / 2.0;
        let r1 = (x1, y1, x1 + w1, y1 + h1);
        
        for &(j, _) in &scored_indices {
            if i == j || !keep[j] { continue; }
            
            let (_, _, x2, y2, w2, h2) = items[j];
            let cx2 = x2 + w2 / 2.0;
            let cy2 = y2 + h2 / 2.0;
            let r2 = (x2, y2, x2 + w2, y2 + h2);
            
            // Check center distance
            let dx = cx1 - cx2;
            let dy = cy1 - cy2;
            let distance = (dx * dx + dy * dy).sqrt();
            
            // Check overlap
            let ix1 = r1.0.max(r2.0);
            let iy1 = r1.1.max(r2.1);
            let ix2 = r1.2.min(r2.2);
            let iy2 = r1.3.min(r2.3);
            
            let has_overlap = ix1 < ix2 && iy1 < iy2;
            
            // Remove if too close OR significantly overlapping
            if distance < min_distance || (has_overlap && {
                let intersection = (ix2 - ix1) * (iy2 - iy1);
                let area1 = (r1.2 - r1.0) * (r1.3 - r1.1);
                let area2 = (r2.2 - r2.0) * (r2.3 - r2.1);
                let min_area = area1.min(area2);
                min_area > 0.0 && intersection / min_area > 0.3
            }) {
                // Keep the higher-scored one
                if alignment_scores[i] >= alignment_scores[j] {
                    keep[j] = false;
                } else {
                    keep[i] = false;
                    break;
                }
            }
        }
    }
    
    // Group kept children by zone
    let zone_keys = &crate::config::KEYBOARD_ZONES;
    let mut zone_children: HashMap<(usize, usize), Vec<usize>> = HashMap::new();
    for (i, _) in keep.iter().enumerate().filter(|(_, &k)| k) {
        let child_idx = items[i].1;
        let child = &children[child_idx];
        let (rx, ry) = child.relative_position;
        let zone = get_zone(rx, ry, width, height);
        zone_children.entry(zone).or_default().push(child_idx);
    }
    
    // Sort each zone's children top-to-bottom, left-to-right
    for bucket in zone_children.values_mut() {
        bucket.sort_by(|&a, &b| {
            let (ax, ay) = children[a].relative_position;
            let (bx, by) = children[b].relative_position;
            ay.partial_cmp(&by).unwrap_or(std::cmp::Ordering::Equal)
                .then(ax.partial_cmp(&bx).unwrap_or(std::cmp::Ordering::Equal))
        });
    }
    
    // Relabel with zone-based 2-char labels only
    let mut new_hints = HashMap::new();
    
    for (&(row, col), child_list) in &zone_children {
        let keys: Vec<char> = zone_keys[row][col].chars().collect();
        let n = child_list.len();
        
        let mut labels = Vec::new();
        
        'outer: for &first in &keys {
            for &second in &alpha_chars {
                labels.push(format!("{}{}", first, second));
                if labels.len() >= n {
                    break 'outer;
                }
            }
        }
        
        for (&child_idx, label) in child_list.iter().zip(labels.into_iter()) {
            new_hints.insert(label, child_idx);
        }
    }
    
    new_hints
}
/// Map a child's relative position to a 3x3 screen zone.
fn get_zone(rx: f64, ry: f64, width: f64, height: f64) -> (usize, usize) {
    let nx = if width > 0.0 { (rx / width).clamp(0.0, 1.0) } else { 0.5 };
    let ny = if height > 0.0 { (ry / height).clamp(0.0, 1.0) } else { 0.5 };
    let col = ((nx * 3.0) as usize).min(2);
    let row = ((ny * 3.0) as usize).min(2);
    (row, col)
}
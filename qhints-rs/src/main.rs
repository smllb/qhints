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
use std::collections::HashMap;
use std::fs::OpenOptions;
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

fn try_acquire_lock() -> Option<std::fs::File> {
    let file = OpenOptions::new()
        .write(true)
        .create(true)
        .open("/tmp/qhints.lock")
        .ok()?;

    use std::os::unix::io::AsRawFd;
    let ret = unsafe { libc::flock(file.as_raw_fd(), libc::LOCK_EX | libc::LOCK_NB) };

    if ret == 0 { Some(file) } else { None }
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
    // Prevent re-entry if overlay is already active
    let _lock = match try_acquire_lock() {
        Some(f) => f,
        None => {
            log::warn!("qhints already running, ignoring trigger");
            return;
        }
    };

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
log::info!("hints before relabel: {}", hint_map.len());

let hint_map = cull_and_relabel(config, &hint_map, &children, (w as f64, h as f64));

log::info!("hints after relabel: {}", hint_map.len());
    log::debug!("Total pre-overlay: {:?}", total_start.elapsed());

    // Show overlay
    let (x, y, width, height) = win_info.extents;
    if let Some(action) = overlay::show_overlay(config, &hint_map, &children, x, y, width, height) {
        log::debug!("Action: {:?}", action);

        match action.action.as_str() {
            "click" | "hover" => {
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
    // _lock drops here, releasing the flock
}

/// Cull overlapping hints and relabel survivors with zone-based 2-character labels
fn cull_and_relabel(
    config: &config::Config,
    hints: &HashMap<String, usize>,
    children: &[Child],
    window_size: (f64, f64),
) -> HashMap<String, usize> {
    let alpha_chars: Vec<char> = config.alphabet.chars().collect();
    let (width, height) = window_size;

    // Sort all hints top-to-bottom, left-to-right for deterministic labeling
    let mut items: Vec<(usize, f64, f64)> = hints
        .values()
        .map(|&child_idx| {
            let (rx, ry) = children[child_idx].relative_position;
            (child_idx, rx, ry)
        })
        .collect();

    items.sort_by(|a, b| {
        a.2.partial_cmp(&b.2)
            .unwrap_or(std::cmp::Ordering::Equal)
            .then(a.1.partial_cmp(&b.1).unwrap_or(std::cmp::Ordering::Equal))
    });

    // Group by zone
    let zone_keys = &crate::config::KEYBOARD_ZONES;
    let mut zone_children: std::collections::BTreeMap<(usize, usize), Vec<usize>> =
        std::collections::BTreeMap::new();

    for (child_idx, rx, ry) in &items {
        let zone = get_zone(*rx, *ry, width, height);
        zone_children.entry(zone).or_default().push(*child_idx);
    }

    // Relabel each zone with 2-char labels
    let mut new_hints = HashMap::new();

    for (&(row, col), child_list) in &zone_children {
        let keys: Vec<char> = zone_keys[row][col].chars().collect();

        let mut labels = Vec::new();
        'outer: for &first in &keys {
            for &second in &alpha_chars {
                labels.push(format!("{}{}", first, second));
                if labels.len() >= child_list.len() {
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
fn get_zone(rx: f64, ry: f64, width: f64, height: f64) -> (usize, usize) {
    let nx = if width > 0.0 { (rx / width).clamp(0.0, 1.0) } else { 0.5 };
    let ny = if height > 0.0 { (ry / height).clamp(0.0, 1.0) } else { 0.5 };
    let col = ((nx * 3.0) as usize).min(2);
    let row = ((ny * 3.0) as usize).min(2);
    (row, col)
}
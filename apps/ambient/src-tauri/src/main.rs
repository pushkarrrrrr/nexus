// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::{Deserialize, Serialize};
use std::time::Duration;
use tauri::{Manager, WebviewWindow};
use tokio::time::timeout;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AppContext {
    pub app_name: String,
    pub window_title: String,
}

const CONTEXT_QUERY_TIMEOUT_MS: u64 = 500;

/// Asynchronously query the frontmost macOS application and active window title.
/// Enforces a strict 500ms timeout and catches TCC accessibility permission failures gracefully.
#[tauri::command]
async fn get_frontmost_app() -> Result<AppContext, String> {
    #[cfg(target_os = "macos")]
    {
        let query_task = tokio::task::spawn_blocking(|| {
            let script = r#"
                tell application "System Events"
                    try
                        set frontApp to first application process whose frontmost is true
                        set appName to name of frontApp
                        set winTitle to ""
                        try
                            set winTitle to name of front window of frontApp
                        end try
                        return appName & ":::" & winTitle
                    on error
                        return "Unknown:::"
                    end try
                end tell
            "#;

            let output = std::process::Command::new("/usr/bin/osascript")
                .arg("-e")
                .arg(script)
                .output();

            match output {
                Ok(out) if out.status.success() => {
                    let result_str = String::from_utf8_lossy(&out.stdout).trim().to_string();
                    let parts: Vec<&str> = result_str.split(":::").collect();
                    let app_name = parts.first().unwrap_or(&"Unknown").trim().to_string();
                    let window_title = parts.get(1).unwrap_or(&"").trim().to_string();
                    AppContext {
                        app_name: if app_name.is_empty() {
                            "Unknown".to_string()
                        } else {
                            app_name
                        },
                        window_title,
                    }
                }
                _ => AppContext {
                    app_name: "Unknown".to_string(),
                    window_title: String::new(),
                },
            }
        });

        match timeout(Duration::from_millis(CONTEXT_QUERY_TIMEOUT_MS), query_task).await {
            Ok(Ok(context)) => Ok(context),
            Ok(Err(_join_err)) => Ok(AppContext {
                app_name: "Unknown".to_string(),
                window_title: String::new(),
            }),
            Err(_timeout_err) => Ok(AppContext {
                app_name: "Unknown".to_string(),
                window_title: String::new(),
            }),
        }
    }

    #[cfg(not(target_os = "macos"))]
    {
        Ok(AppContext {
            app_name: "Browser / Desktop".to_string(),
            window_title: "Active Session".to_string(),
        })
    }
}

/// Explicit opt-in command to retrieve currently selected text via simulated keystroke.
/// Enforces non-blocking execution with 500ms timeout and returns empty string if unavailable or timed out.
#[tauri::command]
async fn get_selected_text() -> Result<String, String> {
    #[cfg(target_os = "macos")]
    {
        let query_task = tokio::task::spawn_blocking(|| {
            let script = r#"
                tell application "System Events"
                    try
                        keystroke "c" using {command down}
                    on error
                        return ""
                    end try
                end tell
                delay 0.05
                try
                    return (the clipboard as text)
                on error
                    return ""
                end try
            "#;

            let output = std::process::Command::new("/usr/bin/osascript")
                .arg("-e")
                .arg(script)
                .output();

            match output {
                Ok(out) if out.status.success() => {
                    String::from_utf8_lossy(&out.stdout).trim().to_string()
                }
                _ => String::new(),
            }
        });

        match timeout(Duration::from_millis(CONTEXT_QUERY_TIMEOUT_MS), query_task).await {
            Ok(Ok(text)) => Ok(text),
            _ => Ok(String::new()),
        }
    }

    #[cfg(not(target_os = "macos"))]
    {
        Ok(String::new())
    }
}

/// Hide the HUD window without terminating background agent tasks.
#[tauri::command]
fn hide_hud(window: WebviewWindow) -> Result<(), String> {
    window.hide().map_err(|e| e.to_string())
}

/// Position the round liquid glass orb horizontally centered and comfortably floating above the Dock (at ~62% screen height).
fn position_orb(window: &WebviewWindow) -> Result<(), String> {
    if let Ok(Some(monitor)) = window.current_monitor() {
        let screen_size = monitor.size();
        let screen_pos = monitor.position();
        let scale = monitor.scale_factor();
        let win_size = window
            .outer_size()
            .unwrap_or(tauri::PhysicalSize {
                width: (200.0 * scale) as u32,
                height: (200.0 * scale) as u32,
            });

        let x = screen_pos.x + ((screen_size.width as i32 - win_size.width as i32) / 2);
        let y = screen_pos.y + (((screen_size.height as i32 - win_size.height as i32) * 62) / 100);

        eprintln!("[NEXUS Ambient] Positioning Voice Orb: scale={scale}, screen_size={:?}, target_pos=({x}, {y})", screen_size);
        let _ = window.set_position(tauri::PhysicalPosition { x, y });
    } else {
        let _ = window.center();
    }
    let _ = window.set_always_on_top(true);
    let _ = window.show();
    let _ = window.set_focus();
    Ok(())
}

/// Show and focus the HUD orb.
#[tauri::command]
fn show_hud(window: WebviewWindow) -> Result<(), String> {
    position_orb(&window)?;
    window.show().map_err(|e| e.to_string())?;
    window.set_focus().map_err(|e| e.to_string())
}

/// Toggle show/hide state of the HUD orb.
#[tauri::command]
fn toggle_hud(window: WebviewWindow) -> Result<bool, String> {
    let is_visible = window.is_visible().unwrap_or(false);
    if is_visible {
        window.hide().map_err(|e| e.to_string())?;
        Ok(false)
    } else {
        position_orb(&window)?;
        window.show().map_err(|e| e.to_string())?;
        window.set_focus().map_err(|e| e.to_string())?;
        Ok(true)
    }
}

/// Native macOS Text-to-Speech using Apple Siri female voice ("Tara (English (India))" or "Samantha").
/// Runs asynchronously in a background thread so the UI never blocks.
#[tauri::command]
fn speak_text(text: String, voice: Option<String>) -> Result<(), String> {
    #[cfg(target_os = "macos")]
    {
        let voice_name = voice.unwrap_or_else(|| "Tara (English (India))".to_string());
        std::thread::spawn(move || {
            let output = std::process::Command::new("/usr/bin/say")
                .arg("-v")
                .arg(&voice_name)
                .arg("-r")
                .arg("185")
                .arg(&text)
                .output();

            if let Ok(out) = output {
                if !out.status.success() {
                    // Fallback to Apple Siri Samantha
                    let _ = std::process::Command::new("/usr/bin/say")
                        .arg("-v")
                        .arg("Samantha")
                        .arg("-r")
                        .arg("185")
                        .arg(&text)
                        .output();
                }
            }
        });
        Ok(())
    }
    #[cfg(not(target_os = "macos"))]
    {
        let _ = text;
        let _ = voice;
        Ok(())
    }
}

#[tauri::command]
fn check_engine_status() -> Result<bool, String> {
    let addr: std::net::SocketAddr = ([127, 0, 0, 1], 8000).into();
    Ok(std::net::TcpStream::connect_timeout(&addr, Duration::from_millis(200)).is_ok())
}

use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::{Arc, Mutex};
use tauri_plugin_global_shortcut::{Code, GlobalShortcutExt, Modifiers, Shortcut, ShortcutState};

/// Structure to locate and supervise the embedded backend engine sidecar.
pub struct EngineSupervisor {
    child: Arc<Mutex<Option<Child>>>,
}

impl EngineSupervisor {
    pub fn new() -> Self {
        Self {
            child: Arc::new(Mutex::new(None)),
        }
    }

    pub fn terminate(&self) {
        if let Ok(mut lock) = self.child.lock() {
            if let Some(mut child) = lock.take() {
                eprintln!("[NEXUS Supervisor] Terminating backend engine sidecar (PID: {})...", child.id());
                let _ = child.kill();
                let _ = child.wait();
                eprintln!("[NEXUS Supervisor] Backend engine terminated cleanly.");
            }
        }
    }

    pub fn ensure_running(&self, binary_path: PathBuf) {
        let addr: std::net::SocketAddr = ([127, 0, 0, 1], 8000).into();

        // 1. Check if port 8000 is already active
        if std::net::TcpStream::connect_timeout(&addr, Duration::from_millis(200)).is_ok() {
            eprintln!("[NEXUS Supervisor] Backend engine is already active on port 8000. Reusing existing instance.");
            return;
        }

        eprintln!("[NEXUS Supervisor] Spawning backend engine sidecar: {:?}", binary_path);
        let mut cmd = Command::new(&binary_path);
        cmd.arg("--port").arg("8000");
        cmd.arg("--host").arg("127.0.0.1");

        #[cfg(target_os = "macos")]
        {
            if let Some(home) = std::env::var_os("HOME") {
                let data_dir = PathBuf::from(home)
                    .join("Library")
                    .join("Application Support")
                    .join("NEXUS");
                let _ = std::fs::create_dir_all(&data_dir);
                cmd.arg("--data-dir").arg(data_dir);
            }
        }

        cmd.stdout(Stdio::inherit());
        cmd.stderr(Stdio::inherit());

        match cmd.spawn() {
            Ok(child_proc) => {
                let pid = child_proc.id();
                eprintln!("[NEXUS Supervisor] Backend engine spawned with PID: {}", pid);
                if let Ok(mut lock) = self.child.lock() {
                    *lock = Some(child_proc);
                }

                // Poll port 8000 for up to 5 seconds
                for i in 0..50 {
                    std::thread::sleep(Duration::from_millis(100));
                    if std::net::TcpStream::connect_timeout(&addr, Duration::from_millis(100)).is_ok() {
                        eprintln!("[NEXUS Supervisor] Backend engine verified healthy after {}ms!", (i + 1) * 100);
                        break;
                    }
                }
            }
            Err(e) => {
                eprintln!("[NEXUS Supervisor] ERROR: Failed to spawn backend engine sidecar: {e}");
            }
        }
    }
}

/// Locates the nexus-engine sidecar binary across packaged app bundle, resources, and dev directories.
fn find_engine_binary(app_handle: &tauri::AppHandle) -> Option<PathBuf> {
    let mut candidates: Vec<PathBuf> = Vec::new();

    // 1. Packaged macOS bundle locations (Contents/MacOS or Contents/Resources)
    if let Ok(exe_path) = std::env::current_exe() {
        if let Some(exe_dir) = exe_path.parent() {
            candidates.push(exe_dir.join("nexus-engine"));
            candidates.push(exe_dir.join("nexus-engine-aarch64-apple-darwin"));
            if let Some(bundle_dir) = exe_dir.parent() {
                let res_dir = bundle_dir.join("Resources");
                candidates.push(res_dir.join("nexus-engine"));
                candidates.push(res_dir.join("nexus-engine-aarch64-apple-darwin"));
                candidates.push(res_dir.join("binaries").join("nexus-engine-aarch64-apple-darwin"));
            }
        }
    }

    // 2. Tauri path resolver resource dir
    if let Ok(res_dir) = app_handle.path().resource_dir() {
        candidates.push(res_dir.join("nexus-engine"));
        candidates.push(res_dir.join("nexus-engine-aarch64-apple-darwin"));
        candidates.push(res_dir.join("binaries").join("nexus-engine-aarch64-apple-darwin"));
    }

    // 3. Development workspace paths
    candidates.push(PathBuf::from("binaries/nexus-engine-aarch64-apple-darwin"));
    candidates.push(PathBuf::from("src-tauri/binaries/nexus-engine-aarch64-apple-darwin"));
    candidates.push(PathBuf::from("apps/ambient/src-tauri/binaries/nexus-engine-aarch64-apple-darwin"));

    if let Ok(curr_dir) = std::env::current_dir() {
        candidates.push(curr_dir.join("binaries").join("nexus-engine-aarch64-apple-darwin"));
        candidates.push(curr_dir.join("apps/ambient/src-tauri/binaries/nexus-engine-aarch64-apple-darwin"));
        if let Some(parent) = curr_dir.parent() {
            candidates.push(parent.join("apps/ambient/src-tauri/binaries/nexus-engine-aarch64-apple-darwin"));
        }
    }

    for path in candidates {
        if path.is_file() {
            return Some(path.canonicalize().unwrap_or(path));
        }
    }

    None
}

fn main() {
    let supervisor = Arc::new(EngineSupervisor::new());
    let supervisor_setup = supervisor.clone();
    let supervisor_exit = supervisor.clone();

    tauri::Builder::default()
        .plugin(
            tauri_plugin_global_shortcut::Builder::new()
                .with_handler(|app, _shortcut, event| {
                    if event.state() == ShortcutState::Pressed {
                        if let Some(window) = app.get_webview_window("main") {
                            let _ = toggle_hud(window);
                        }
                    }
                })
                .build(),
        )
        .invoke_handler(tauri::generate_handler![
            get_frontmost_app,
            get_selected_text,
            hide_hud,
            show_hud,
            toggle_hud,
            speak_text,
            check_engine_status,
        ])
        .setup(move |app| {
            if let Some(window) = app.get_webview_window("main") {
                let _ = position_orb(&window);
                let win_clone = window.clone();
                window.on_window_event(move |event| {
                    if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                        api.prevent_close();
                        let _ = win_clone.hide();
                    }
                });
            }

            // Register global hotkeys: Cmd+Shift+Space and Cmd+Shift+P
            let shortcut_space = Shortcut::new(Some(Modifiers::SUPER | Modifiers::SHIFT), Code::Space);
            if let Err(err) = app.global_shortcut().register(shortcut_space) {
                eprintln!("[NEXUS Ambient] Warning: Failed to register Cmd+Shift+Space shortcut: {err}");
            }
            let shortcut_p = Shortcut::new(Some(Modifiers::SUPER | Modifiers::SHIFT), Code::KeyP);
            if let Err(err) = app.global_shortcut().register(shortcut_p) {
                eprintln!("[NEXUS Ambient] Warning: Failed to register Cmd+Shift+P shortcut: {err}");
            }

            // Supervise backend engine lifecycle in background thread
            if let Some(bin) = find_engine_binary(app.handle()) {
                let sup = supervisor_setup.clone();
                std::thread::spawn(move || {
                    sup.ensure_running(bin);
                });
            } else {
                eprintln!("[NEXUS Ambient] Notice: Sidecar binary not found at default paths. Assuming standalone server on 127.0.0.1:8000.");
            }

            // Status bar tray icon for convenient click-to-summon in macOS menu bar
            let mut tray_builder = tauri::tray::TrayIconBuilder::new()
                .tooltip("NEXUS Ambient HUD")
                .title(" ✦ NEXUS ");

            if let Some(icon) = app.default_window_icon() {
                tray_builder = tray_builder.icon(icon.clone());
            }

            // Build tray context menu with Quit option
            use tauri::menu::{Menu, MenuItem};
            let show_item = MenuItem::with_id(app, "toggle_hud", "Toggle HUD (Cmd+Shift+Space)", true, None::<&str>)?;
            let quit_item = MenuItem::with_id(app, "quit", "Quit NEXUS", true, None::<&str>)?;
            let tray_menu = Menu::with_items(app, &[&show_item, &quit_item])?;

            let supervisor_tray = supervisor_setup.clone();
            let _ = tray_builder
                .menu(&tray_menu)
                .on_menu_event(move |app_handle, event| {
                    match event.id.as_ref() {
                        "quit" => {
                            supervisor_tray.terminate();
                            app_handle.exit(0);
                        }
                        "toggle_hud" => {
                            if let Some(window) = app_handle.get_webview_window("main") {
                                let _ = toggle_hud(window);
                            }
                        }
                        _ => {}
                    }
                })
                .on_tray_icon_event(|tray, event| {
                    if let tauri::tray::TrayIconEvent::Click {
                        button: tauri::tray::MouseButton::Left,
                        button_state: tauri::tray::MouseButtonState::Up,
                        ..
                    } = event
                    {
                        let app = tray.app_handle();
                        if let Some(window) = app.get_webview_window("main") {
                            let _ = toggle_hud(window);
                        }
                    }
                })
                .build(app);

            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while running NEXUS ambient application")
        .run(move |_app_handle, event| {
            match event {
                tauri::RunEvent::ExitRequested { .. } => {
                    supervisor_exit.terminate();
                }
                tauri::RunEvent::Exit => {
                    supervisor_exit.terminate();
                }
                _ => {}
            }
        });
}

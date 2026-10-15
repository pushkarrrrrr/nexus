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

use tauri_plugin_global_shortcut::{Code, GlobalShortcutExt, Modifiers, Shortcut, ShortcutState};

fn main() {
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
        ])
        .setup(|app| {
            if let Some(window) = app.get_webview_window("main") {
                let _ = position_orb(&window);
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

            // Status bar tray icon for convenient click-to-summon in macOS menu bar
            let mut tray_builder = tauri::tray::TrayIconBuilder::new()
                .tooltip("NEXUS Ambient HUD (Click to Toggle)")
                .title(" ✦ NEXUS ");

            if let Some(icon) = app.default_window_icon() {
                tray_builder = tray_builder.icon(icon.clone());
            }

            let _ = tray_builder
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
        .run(|_app_handle, event| {
            if let tauri::RunEvent::ExitRequested { api, .. } = event {
                api.prevent_exit();
            }
        });
}

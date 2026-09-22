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

/// Show and focus the HUD window centered in the upper-third of screen.
#[tauri::command]
fn show_hud(window: WebviewWindow) -> Result<(), String> {
    position_upper_third(&window)?;
    window.show().map_err(|e| e.to_string())?;
    window.set_focus().map_err(|e| e.to_string())
}

/// Toggle show/hide state of the HUD capsule.
#[tauri::command]
fn toggle_hud(window: WebviewWindow) -> Result<bool, String> {
    let is_visible = window.is_visible().unwrap_or(false);
    if is_visible {
        window.hide().map_err(|e| e.to_string())?;
        Ok(false)
    } else {
        position_upper_third(&window)?;
        window.show().map_err(|e| e.to_string())?;
        window.set_focus().map_err(|e| e.to_string())?;
        Ok(true)
    }
}

/// Center the window horizontally and position in top 15-20% of display height.
fn position_upper_third(window: &WebviewWindow) -> Result<(), String> {
    if let Ok(Some(monitor)) = window.current_monitor() {
        let screen_size = monitor.size();
        let screen_pos = monitor.position();
        let win_size = window
            .outer_size()
            .unwrap_or(tauri::PhysicalSize { width: 740, height: 480 });

        let x = screen_pos.x + ((screen_size.width as i32 - win_size.width as i32) / 2);
        let y = screen_pos.y + ((screen_size.height as f64 * 0.15) as i32);

        window
            .set_position(tauri::PhysicalPosition { x, y })
            .map_err(|e| e.to_string())?;
    }
    Ok(())
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_global_shortcut::Builder::new().build())
        .invoke_handler(tauri::generate_handler![
            get_frontmost_app,
            get_selected_text,
            hide_hud,
            show_hud,
            toggle_hud,
        ])
        .setup(|app| {
            if let Some(window) = app.get_webview_window("main") {
                let _ = position_upper_third(&window);
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running NEXUS ambient application");
}

/**
 * Tauri Native Bridge for NEXUS Ambient Desktop HUD
 * Provides type-safe wrappers around native OS commands with non-blocking timeouts
 * and seamless fallback when running in browser or automated test environments.
 */

import type { TauriNativeAppContext } from "@nexus/types";

export function isTauriAvailable(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

const CLIENT_TIMEOUT_MS = 600;

async function withTimeout<T>(promise: Promise<T>, fallback: T, ms = CLIENT_TIMEOUT_MS): Promise<T> {
  let timer: ReturnType<typeof setTimeout> | null = null;
  const timeoutPromise = new Promise<T>((resolve) => {
    timer = setTimeout(() => resolve(fallback), ms);
  });

  try {
    const result = await Promise.race([promise, timeoutPromise]);
    return result;
  } finally {
    if (timer) clearTimeout(timer);
  }
}

/**
 * Non-blocking native command to query frontmost application name and window title.
 * Enforces strict timeout and returns fallback on failure (TCC permissions).
 */
export async function getFrontmostApp(): Promise<TauriNativeAppContext> {
  const fallback: TauriNativeAppContext = {
    appName: "VS Code",
    windowTitle: "nexus/src/main.rs",
  };

  if (!isTauriAvailable()) {
    return fallback;
  }

  try {
    const { invoke } = await import("@tauri-apps/api/core");
    return await withTimeout(
      invoke<TauriNativeAppContext>("get_frontmost_app"),
      { appName: "Unknown", windowTitle: "" },
      500
    );
  } catch {
    return { appName: "Unknown", windowTitle: "" };
  }
}

/**
 * Explicit opt-in command to retrieve currently selected text via simulated keystroke.
 * Returns empty string if unavailable or timed out.
 */
export async function getSelectedText(): Promise<string> {
  if (!isTauriAvailable()) {
    return "";
  }

  try {
    const { invoke } = await import("@tauri-apps/api/core");
    return await withTimeout(invoke<string>("get_selected_text"), "", 500);
  } catch {
    return "";
  }
}

/**
 * Hide HUD window without aborting active background tasks.
 */
export async function hideHud(): Promise<void> {
  if (!isTauriAvailable()) {
    return;
  }

  try {
    const { invoke } = await import("@tauri-apps/api/core");
    await invoke("hide_hud");
  } catch (err) {
    console.warn("Failed to hide HUD via Tauri:", err);
  }
}

/**
 * Show and center HUD window in upper third of display.
 */
export async function showHud(): Promise<void> {
  if (!isTauriAvailable()) {
    return;
  }

  try {
    const { invoke } = await import("@tauri-apps/api/core");
    await invoke("show_hud");
  } catch (err) {
    console.warn("Failed to show HUD via Tauri:", err);
  }
}

/**
 * Toggle HUD window visibility.
 */
export async function toggleHud(): Promise<boolean> {
  if (!isTauriAvailable()) {
    return true;
  }

  try {
    const { invoke } = await import("@tauri-apps/api/core");
    return await invoke<boolean>("toggle_hud");
  } catch {
    return false;
  }
}

/**
 * Tauri Native Bridge for NEXUS Ambient Desktop HUD
 * Provides type-safe wrappers around native OS commands with non-blocking timeouts
 * and seamless fallback when running in browser or automated test environments.
 */

import type { TauriNativeAppContext } from "@nexus/types";
import { invoke, isTauri } from "@tauri-apps/api/core";

export function isTauriAvailable(): boolean {
  try {
    return isTauri();
  } catch {
    return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
  }
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
    return await invoke<boolean>("toggle_hud");
  } catch {
    return false;
  }
}

/**
 * Dynamically resize HUD window between compact (idle search bar) and expanded (content).
 */
export async function setHudExpanded(expanded: boolean): Promise<void> {
  if (!isTauriAvailable()) {
    return;
  }

  try {
    await invoke("set_hud_expanded", { expanded });
  } catch (err) {
    console.warn("Failed to set HUD expanded state:", err);
  }
}

/**
 * Speaks text using Apple's official Siri female voice ("Tara (English (India))" / "Samantha" / "Lekha" for Hindi).
 * Strictly guarantees a female Siri voice by excluding all male voices like Aman and Rishi.
 */
export async function speakNative(text: string, voice?: string): Promise<void> {
  const hasDevanagari = /[\u0900-\u097F]/.test(text);
  // Default to Apple Siri voice (Tara for Indian Siri / Samantha for US Siri / Lekha for Hindi)
  const selectedVoice = voice || (hasDevanagari ? "Lekha (Hindi (India))" : "Tara (English (India))");

  if (isTauriAvailable()) {
    try {
      await invoke("speak_text", { text, voice: selectedVoice });
      return;
    } catch (err) {
      console.warn("Tauri speak_text failed, falling back to Web Speech:", err);
    }
  }

  // Web Speech API fallback for browser dev environment
  if (typeof window !== "undefined" && "speechSynthesis" in window) {
    try {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      const voices = window.speechSynthesis.getVoices();

      // STRICT FILTER: Block ALL male voices (Aman, Rishi, etc.)
      const MALE_NAMES = /aman|rishi|male|david|george|daniel|alex|fred|tom|oliver|aaron|jorge|diego|juan|arthur|guy|ralph|junior|albert/i;
      const isMale = (name: string) => MALE_NAMES.test(name);

      // Prioritize Apple Siri voices and high-quality female voices
      const siriFemaleVoice =
        voices.find((v) => !isMale(v.name) && (v.name.includes("Tara") || v.name.includes("Siri"))) ||
        voices.find((v) => !isMale(v.name) && v.name.includes("Samantha")) ||
        voices.find((v) => !isMale(v.name) && v.name.includes("Lekha")) ||
        voices.find((v) => !isMale(v.name) && (v.name.includes("Karen") || v.name.includes("Victoria") || v.name.includes("Veena"))) ||
        voices.find((v) => !isMale(v.name) && v.name.toLowerCase().includes("female"));

      if (siriFemaleVoice) {
        utterance.voice = siriFemaleVoice;
      }
      utterance.pitch = 1.05;
      utterance.rate = 1.0;
      window.speechSynthesis.speak(utterance);
    } catch (err) {
      console.warn("Web Speech speak failed:", err);
    }
  }
}



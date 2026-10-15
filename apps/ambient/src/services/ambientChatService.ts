/**
 * Ultra-resilient Ambient Chat Service
 * Queries the NEXUS core ambient chat API — races IPv4 + localhost in parallel
 * for minimum latency, with direct Gemini REST fallback if backend is offline.
 */

const GEMINI_API_KEY = (import.meta as any).env?.VITE_GEMINI_API_KEY || "";

const SYSTEM_INSTRUCTION =
  "You are NEXUS, a friendly, concise, and helpful AI voice assistant for macOS. " +
  "Respond in 1 to 2 short sentences suitable for text-to-speech voice playback. " +
  "Never use markdown asterisks or bullet points. Support Hindi, English, and Hinglish naturally.";

/** Attempt a single backend endpoint with a given timeout (ms). Returns null on any failure. */
async function tryBackendEndpoint(
  url: string,
  body: object,
  headers: Record<string, string>,
  timeoutMs: number
): Promise<string | null> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...headers },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    clearTimeout(timeoutId);
    if (!res.ok) return null;
    const data = await res.json();
    const reply = data.reply ?? data.final_result;
    if (reply && typeof reply === "string") {
      return reply.replace(/[*#_`]/g, "").trim();
    }
    return null;
  } catch {
    clearTimeout(timeoutId);
    return null;
  }
}

/** Call Gemini directly (no backend required). Returns null on failure. */
async function tryGeminiDirect(
  model: string,
  message: string
): Promise<string | null> {
  if (!GEMINI_API_KEY) return null;
  try {
    const url = `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${GEMINI_API_KEY}`;
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        contents: [{ role: "user", parts: [{ text: `${SYSTEM_INSTRUCTION}\n\nUser: ${message}` }] }],
        generationConfig: { maxOutputTokens: 120, temperature: 0.7 },
      }),
    });
    if (!res.ok) return null;
    const data = await res.json();
    const parts: { text?: string }[] = data?.candidates?.[0]?.content?.parts ?? [];
    const text = parts.map((p) => p.text ?? "").join("").trim();
    return text ? text.replace(/[*#_`]/g, "").trim() : null;
  } catch {
    return null;
  }
}

export async function sendAmbientChatMessage(
  message: string,
  context?: { app_name?: string; window_title?: string } | null,
  apiToken?: string
): Promise<string> {
  const cleanMsg = message.trim();
  if (!cleanMsg) return "I'm listening!";

  const requestBody = {
    message: cleanMsg,
    context: context ? { app_name: context.app_name, window_title: context.window_title } : null,
  };
  const authHeaders: Record<string, string> = {
    "X-Client-Surface": "ambient",
    ...(apiToken ? { Authorization: `Bearer ${apiToken}` } : {}),
  };

  // 1. Try primary IPv4 loopback endpoint first (fast, single connection)
  let backendResult = await tryBackendEndpoint("http://127.0.0.1:8000/api/v1/ambient/chat", requestBody, authHeaders, 5000);
  if (!backendResult) {
    backendResult = await tryBackendEndpoint("http://localhost:8000/api/v1/ambient/chat", requestBody, authHeaders, 4000);
  }

  if (backendResult) return backendResult;

  // 2. Race both Gemini fallback models simultaneously for lowest latency.
  const geminiResult = await Promise.any([
    tryGeminiDirect("gemini-3.5-flash-lite", cleanMsg),
    tryGeminiDirect("gemini-3.1-flash-lite", cleanMsg),
  ]).catch(() => null);

  if (geminiResult) return geminiResult;

  return "Main theek hoon! Aaj aapki kya madad kar sakta hoon?";
}

const WINDOW_MS = 60_000;
const MAX_PER_WINDOW = 18;
const MAX_TEXT_LENGTH = 1_500;

const DEFAULT_ORIGIN = "https://harbour-trust-voice-capstone-10.vercel.app";
const recentRequests = globalThis.__harbourFishTtsRequests || new Map();
globalThis.__harbourFishTtsRequests = recentRequests;

function setCommonHeaders(res) {
  res.setHeader("Cache-Control", "no-store");
  res.setHeader("X-Content-Type-Options", "nosniff");
}

function isAllowedOrigin(value) {
  if (!value) return false;
  try {
    const { protocol, hostname } = new URL(value);
    if (protocol === "http:" && ["localhost", "127.0.0.1"].includes(hostname)) return true;
    if (protocol !== "https:") return false;
    return hostname === new URL(DEFAULT_ORIGIN).hostname ||
      /^harbour-trust-voice-capstone-10-[a-z0-9]+-sahil-2006s-projects\.vercel\.app$/.test(hostname);
  } catch {
    return false;
  }
}

function allowedForCaller(req) {
  const forwarded = req.headers["x-forwarded-for"];
  const address = (Array.isArray(forwarded) ? forwarded[0] : forwarded || req.socket.remoteAddress || "unknown")
    .split(",")[0].trim();
  const now = Date.now();
  const recent = (recentRequests.get(address) || []).filter(time => now - time < WINDOW_MS);
  if (recent.length >= MAX_PER_WINDOW) return false;
  recent.push(now);
  recentRequests.set(address, recent);
  if (recentRequests.size > 1_000) {
    for (const [key, times] of recentRequests) {
      if (!times.some(time => now - time < WINDOW_MS)) recentRequests.delete(key);
    }
  }
  return true;
}

module.exports = async function handler(req, res) {
  setCommonHeaders(res);
  if (req.method === "GET") {
    return res.status(200).json({ available: Boolean(process.env.FISH_AUDIO_API_KEY) });
  }
  if (req.method !== "POST") {
    res.setHeader("Allow", "GET, POST");
    return res.status(405).json({ error: "Method not allowed" });
  }
  if (!isAllowedOrigin(req.headers.origin)) {
    return res.status(403).json({ error: "Request origin is not allowed" });
  }
  if (!process.env.FISH_AUDIO_API_KEY) {
    return res.status(503).json({ error: "Fish Audio voice is not configured" });
  }
  if (!allowedForCaller(req)) {
    return res.status(429).json({ error: "Please wait before requesting more speech" });
  }

  let body = req.body;
  if (typeof body === "string") {
    try { body = JSON.parse(body); }
    catch { return res.status(400).json({ error: "Invalid request" }); }
  }
  const text = typeof body?.text === "string" ? body.text.trim() : "";
  if (!text || text.length > MAX_TEXT_LENGTH || /[\u0000-\u0008\u000B\u000C\u000E-\u001F]/.test(text)) {
    return res.status(400).json({ error: "Speech text is empty or too long" });
  }

  try {
    const upstream = await fetch("https://api.fish.audio/v1/tts", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${process.env.FISH_AUDIO_API_KEY}`,
        "Content-Type": "application/json",
        model: "s2.1-pro-free"
      },
      body: JSON.stringify({ text, format: "mp3", latency: "balanced", normalize: true, language: "en" }),
      signal: AbortSignal.timeout(25_000)
    });
    if (!upstream.ok) {
      return res.status(upstream.status === 429 ? 429 : 502).json({ error: "Fish Audio could not generate speech" });
    }
    const contentType = upstream.headers.get("content-type") || "audio/mpeg";
    if (!contentType.startsWith("audio/")) {
      return res.status(502).json({ error: "Fish Audio returned an unsupported response" });
    }
    const audio = Buffer.from(await upstream.arrayBuffer());
    if (!audio.length || audio.length > 8_000_000) {
      return res.status(502).json({ error: "Fish Audio returned invalid audio" });
    }
    res.setHeader("Content-Type", contentType);
    res.setHeader("Content-Length", String(audio.length));
    return res.status(200).send(audio);
  } catch {
    return res.status(502).json({ error: "Fish Audio is temporarily unavailable" });
  }
};

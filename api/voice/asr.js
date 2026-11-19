const WINDOW_MS = 60_000;
const MAX_PER_WINDOW = 12;
const MAX_AUDIO_DATA_URL_LENGTH = 1_300_000;
const DEFAULT_ORIGIN = "https://harbour-trust-voice-capstone-10.vercel.app";
const recentRequests = globalThis.__harbourQwenAsrRequests || new Map();
globalThis.__harbourQwenAsrRequests = recentRequests;
const REGIONS = new Set(["ap-southeast-1", "cn-beijing"]);

function configured() {
  const workspace = process.env.DASHSCOPE_WORKSPACE_ID || "";
  const region = process.env.DASHSCOPE_REGION || "ap-southeast-1";
  return Boolean(process.env.DASHSCOPE_API_KEY && /^[a-zA-Z0-9-]{2,100}$/.test(workspace) && REGIONS.has(region));
}

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
  } catch { return false; }
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

function parseBody(req) {
  if (typeof req.body === "string") {
    try { return JSON.parse(req.body); }
    catch { return null; }
  }
  return req.body && typeof req.body === "object" ? req.body : null;
}

function endpoint() {
  const workspace = process.env.DASHSCOPE_WORKSPACE_ID;
  const region = process.env.DASHSCOPE_REGION || "ap-southeast-1";
  return `https://${workspace}.${region}.maas.aliyuncs.com/compatible-mode/v1/chat/completions`;
}

module.exports = async function handler(req, res) {
  setCommonHeaders(res);
  if (req.method === "GET") return res.status(200).json({available:configured(), model:"qwen3-asr-flash", maxRecordingMs:15_000});
  if (req.method !== "POST") {
    res.setHeader("Allow", "GET, POST");
    return res.status(405).json({error:"Method not allowed"});
  }
  if (!isAllowedOrigin(req.headers.origin)) return res.status(403).json({error:"Request origin is not allowed"});
  if (!configured()) return res.status(503).json({error:"Qwen transcription is not configured; browser speech recognition is available as a fallback"});
  if (!allowedForCaller(req)) return res.status(429).json({error:"Please wait before requesting another transcription"});

  const body = parseBody(req);
  const audio = typeof body?.audio === "string" ? body.audio : "";
  const match = audio.match(/^data:(audio\/(?:webm|mp4|ogg|wav|mpeg|x-wav))(?:;codecs=[a-z0-9.-]+)?;base64,([a-z0-9+/]+={0,2})$/i);
  const durationMs = Number(body?.durationMs);
  if (!match || audio.length > MAX_AUDIO_DATA_URL_LENGTH || durationMs < 250 || durationMs > 15_000) {
    return res.status(400).json({error:"Provide a supported audio clip up to 15 seconds long"});
  }
  const encodedAudio = match[2];
  const decodedLength = Buffer.from(encodedAudio, "base64").length;
  if (!decodedLength || decodedLength > 975_000) return res.status(400).json({error:"The audio clip is too large"});
  const mimeType = match[1].toLowerCase();
  const dataUrl = `data:${mimeType};base64,${encodedAudio}`;

  try {
    const upstream = await fetch(endpoint(), {
      method:"POST",
      headers:{Authorization:`Bearer ${process.env.DASHSCOPE_API_KEY}`, "Content-Type":"application/json"},
      body:JSON.stringify({
        model:"qwen3-asr-flash",
        messages:[{role:"user",content:[{type:"input_audio",input_audio:{data:dataUrl}}]}],
        stream:false,
        asr_options:{language:"en",enable_itn:true}
      }),
      signal:AbortSignal.timeout(25_000)
    });
    if (!upstream.ok) return res.status(upstream.status === 429 ? 429 : 502).json({error:"Qwen transcription is temporarily unavailable"});
    const result = await upstream.json();
    const text = result?.choices?.[0]?.message?.content;
    if (typeof text !== "string" || !text.trim() || text.length > 1_000) return res.status(502).json({error:"Qwen returned no usable transcript"});
    return res.status(200).json({text:text.trim()});
  } catch {
    return res.status(502).json({error:"Qwen transcription is temporarily unavailable"});
  }
};

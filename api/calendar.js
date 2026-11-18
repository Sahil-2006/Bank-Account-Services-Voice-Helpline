const cachedCalendar = require("../helpline/uk-bank-holidays-cache.json");

function validCalendar(value) {
  const events = value?.["england-and-wales"]?.events;
  return Array.isArray(events) && events.length > 0 && events.every(event =>
    typeof event?.date === "string" && /^\d{4}-\d{2}-\d{2}$/.test(event.date) &&
    Number.isFinite(Date.parse(`${event.date}T00:00:00Z`))
  );
}

module.exports = async function handler(req, res) {
  res.setHeader("Cache-Control", "no-store");
  res.setHeader("X-Content-Type-Options", "nosniff");
  if (req.method !== "GET") {
    res.setHeader("Allow", "GET");
    return res.status(405).json({ error: "Method not allowed" });
  }

  try {
    const upstream = await fetch("https://www.gov.uk/bank-holidays.json", {
      headers: { Accept: "application/json" },
      signal: AbortSignal.timeout(4_000)
    });
    if (upstream.ok) {
      const feed = await upstream.json();
      if (validCalendar(feed)) return res.status(200).json({ source: "live", feed });
    }
  } catch {
    // A bundled snapshot keeps the fictional clearing-date check available offline.
  }

  return res.status(200).json({ source: "cache", feed: cachedCalendar });
};

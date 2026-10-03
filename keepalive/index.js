export default {
  async scheduled(event, env, ctx) {
    ctx.waitUntil(ping());
  },
  async fetch() {
    const r = await ping();
    return new Response(JSON.stringify(r), { headers: { "Content-Type": "application/json" } });
  }
};

async function ping() {
  const out = {};
  for (const path of ["/api/status", "/"]) {
    try {
      const r = await fetch("https://collections-ledger.onrender.com" + path, { cf: { cacheTtl: 0 } });
      out[path] = r.status;
    } catch (e) {
      out[path] = "error: " + e.message;
    }
  }
  return out;
}

export async function onRequest(context) {
  return new Response(JSON.stringify({ status: 'ok', gateway: 'Cloudflare Pages', timestamp: new Date().toISOString() }), {
    headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' }
  });
}

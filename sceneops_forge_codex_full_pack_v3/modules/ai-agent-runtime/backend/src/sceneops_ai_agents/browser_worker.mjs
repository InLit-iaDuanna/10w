// Private product worker. Input is assembled by the server, never by a model.
import { createRequire } from 'node:module';
import fs from 'node:fs';

const require = createRequire(import.meta.url);
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const result = { status: 'failed', failure_code: null, loaded: false,
  screenshot_collected: false, gameplay_verified: false, visual_reviewed: false,
  console_errors: [], page_errors: [], network_errors: [], blocked_requests: [],
  diagnostics: null, diagnostics_status: 'missing', mode: 'live' };
const add = (key, text) => { if (result[key].length < 100) result[key].push(String(text).slice(0, 2000)); };
let browser;
process.once('SIGTERM', async () => {
  if (browser) await browser.close();
  process.exit(0);
});
try {
  let chromium;
  try { ({ chromium } = require(input.playwright_module || 'playwright')); }
  catch { throw Object.assign(new Error('Playwright runtime is not configured; nothing was installed.'), { code: 'BROWSER_UNAVAILABLE' }); }
  browser = await chromium.launch({ headless: true, chromiumSandbox: true,
    timeout: 10000, args: ['--disable-quic', '--force-webrtc-ip-handling-policy=disable_non_proxied_udp'] });
  result.browser_version = browser.version();
  const context = await browser.newContext({ viewport: { width: 1280, height: 720 },
    serviceWorkers: 'block', acceptDownloads: false, permissions: [] });
  const page = await context.newPage();
  const origin = new URL(input.url).origin;
  const policy = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; media-src 'self' blob:; connect-src 'self'; worker-src 'none'; frame-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'";
  // No route continues to Chromium's network stack. Redirects are fetched without
  // following them; each resulting request must pass the same exact-origin rule.
  await context.route('**/*', async route => {
    const request = route.request();
    let allowed = false;
    try {
      const url = new URL(request.url());
      allowed = url.origin === origin && !url.username && !url.password
        && ['GET', 'HEAD'].includes(request.method()) && request.frame() === page.mainFrame();
    } catch { /* Worker or opaque-origin requests are outside current-view. */ }
    if (!allowed) {
      add('blocked_requests', request.url());
      await route.abort('blockedbyclient');
      return;
    }
    try {
      const response = await route.fetch({ maxRedirects: 0, timeout: 8000,
        headers: { accept: request.headers().accept || '*/*' } });
      if (response.status() >= 400) add('network_errors', `${response.status()} ${request.url()}`);
      await route.fulfill({ response, headers: { ...response.headers(),
        'content-security-policy': policy, 'referrer-policy': 'no-referrer' } });
    } catch (error) {
      add('network_errors', `${request.url()} ${error.message}`);
      await route.abort('failed').catch(() => {});
    }
  });
  await context.routeWebSocket('**/*', socket => {
    add('blocked_requests', socket.url());
    socket.close();
  });
  context.on('page', popup => { if (popup !== page) void popup.close(); });
  page.on('dialog', dialog => void dialog.dismiss());
  page.on('console', message => { if (message.type() === 'error') add('console_errors', message.text()); });
  page.on('pageerror', error => add('page_errors', error.message));
  page.on('requestfailed', request => add('network_errors', `${request.url()} ${request.failure()?.errorText}`));
  const response = await page.goto(input.url, { waitUntil: 'domcontentloaded', timeout: 12000 });
  result.loaded = !!response && response.ok() && new URL(page.url()).origin === origin;
  if (!result.loaded) throw Object.assign(new Error('Build document failed to load.'), { code: 'BROWSER_LOAD_FAILED' });
  await page.waitForTimeout(1000);
  if (new URL(page.url()).origin !== origin) {
    throw Object.assign(new Error('Page left the registered preview.'), { code: 'BROWSER_LOAD_FAILED' });
  }
  // Fixed basic DOM diagnostics work without game hooks. No caller-provided JS.
  result.diagnostics = await page.evaluate(() => ({ title: document.title,
    ready_state: document.readyState, canvas_count: document.querySelectorAll('canvas').length,
    viewport: { width: innerWidth, height: innerHeight } }));
  result.diagnostics_status = 'dom_only_game_diagnostics_missing';
  await page.screenshot({ path: input.screenshot_path, timeout: 5000 });
  result.screenshot_collected = true;
  result.status = 'succeeded';
} catch (error) {
  result.failure_code = error.code || (error.message.includes("Executable doesn't exist")
    ? 'BROWSER_UNAVAILABLE' : error.name === 'TimeoutError' ? 'BROWSER_TIMEOUT' : 'BROWSER_LOAD_FAILED');
  result.reason = String(error.message).slice(0, 2000);
} finally {
  if (browser) await browser.close();
}
process.stdout.write(JSON.stringify(result));

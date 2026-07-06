#!/usr/bin/env node
/**
 * export_demo_gif.js
 *
 * Generic HTML-video-prototype -> GIF (+ optional MP4) exporter.
 * Captures frames from a self-contained HTML file via Puppeteer, then
 * encodes them with ffmpeg. No project-specific branding or variant
 * registry — pass the HTML path directly.
 *
 * Usage:
 *   node scripts/export_demo_gif.js docs/images/demo/openmolclaw-demo.html
 *   node scripts/export_demo_gif.js <html> --fps 8 --width 720
 *   node scripts/export_demo_gif.js <html> --viewport 1280x800 --mp4
 *   node scripts/export_demo_gif.js <html> --out docs/images/openmolclaw-demo
 *   node scripts/export_demo_gif.js <html> --keep-frames
 *
 * Requirements:
 *   - ffmpeg on PATH (brew install ffmpeg)
 *   - Puppeteer: set PUPPETEER_MODULE_PATH to a require()-able puppeteer
 *     install, or `npm install puppeteer` and it will be found via
 *     require('puppeteer') resolution from this script's directory.
 *
 * The HTML file must expose:
 *   window.setGlobalTime(t)  — set playback position (seconds)
 *   window.VIDEO_TOTAL       — total duration (seconds)
 */

const path = require('path');
const fs = require('fs');
const { execSync, spawnSync } = require('child_process');

const DEFAULT_FPS = 8;
const DEFAULT_WIDTH = 720;
const DEFAULT_VIEW_W = 1280;
const DEFAULT_VIEW_H = 800;
const SETTLE_MS = 100;

function resolvePuppeteer() {
  if (process.env.PUPPETEER_MODULE_PATH) {
    return require(process.env.PUPPETEER_MODULE_PATH);
  }
  try {
    return require('puppeteer');
  } catch (e) {
    const fallback = '/opt/homebrew/lib/node_modules/@mermaid-js/mermaid-cli/node_modules/puppeteer';
    if (fs.existsSync(fallback)) return require(fallback);
    throw new Error(
      'Puppeteer not found. Install locally (npm install puppeteer) or set ' +
      'PUPPETEER_MODULE_PATH to an existing install.'
    );
  }
}

function chromeExecutableCandidates() {
  const envPath = process.env.PUPPETEER_EXECUTABLE_PATH || process.env.CHROME_PATH;
  if (envPath && fs.existsSync(envPath)) return envPath;
  const darwin = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
  if (process.platform === 'darwin' && fs.existsSync(darwin)) return darwin;
  return undefined;
}

const args = process.argv.slice(2);
const htmlArg = args[0];

if (!htmlArg || htmlArg.startsWith('--')) {
  console.error(
    'Usage: node scripts/export_demo_gif.js <html-file> [--fps N] [--width N] ' +
    '[--viewport WxH] [--mp4] [--out <path-without-ext>] [--keep-frames]'
  );
  process.exit(1);
}

function argVal(flag, def) {
  const i = args.indexOf(flag);
  return i !== -1 ? args[i + 1] : def;
}

const FPS = parseInt(argVal('--fps', DEFAULT_FPS), 10);
const WIDTH = parseInt(argVal('--width', DEFAULT_WIDTH), 10);
const WANT_MP4 = args.includes('--mp4');
const KEEP_FRAMES = args.includes('--keep-frames');

let VIEWPORT_W = DEFAULT_VIEW_W;
let VIEWPORT_H = DEFAULT_VIEW_H;
const viewportStr = argVal('--viewport', null);
if (viewportStr) {
  const m = /^(\d+)x(\d+)$/.exec(viewportStr.trim());
  if (!m) {
    console.error('Invalid --viewport. Use e.g. --viewport 1280x800');
    process.exit(1);
  }
  VIEWPORT_W = parseInt(m[1], 10);
  VIEWPORT_H = parseInt(m[2], 10);
}

const HTML_FILE = path.resolve(process.cwd(), htmlArg);
if (!fs.existsSync(HTML_FILE)) {
  console.error('HTML file not found:', HTML_FILE);
  process.exit(1);
}

const baseName = path.basename(HTML_FILE, path.extname(HTML_FILE));
const outArg = argVal('--out', null);
const OUT_BASE = outArg
  ? path.resolve(process.cwd(), outArg)
  : path.join(path.dirname(HTML_FILE), baseName);

const FRAMES_DIR = `${OUT_BASE}-frames`;
const GIF_OUT = `${OUT_BASE}.gif`;
const MP4_OUT = `${OUT_BASE}.mp4`;
const PALETTE_F = `${OUT_BASE}-palette.png`;

(async () => {
  const ffmpegCheck = spawnSync('which', ['ffmpeg']);
  if (ffmpegCheck.status !== 0) {
    console.error('ffmpeg not found. Run: brew install ffmpeg');
    process.exit(1);
  }

  if (fs.existsSync(FRAMES_DIR)) fs.rmSync(FRAMES_DIR, { recursive: true });
  fs.mkdirSync(FRAMES_DIR, { recursive: true });

  console.log(`\nCapturing: ${path.basename(HTML_FILE)}`);
  console.log(`  FPS: ${FPS}  Viewport: ${VIEWPORT_W}x${VIEWPORT_H}  GIF width: ${WIDTH}px`);
  console.log(`  Frames: ${FRAMES_DIR}`);
  console.log(`  GIF out: ${GIF_OUT}`);
  if (WANT_MP4) console.log(`  MP4 out: ${MP4_OUT}`);
  console.log('');

  const puppeteer = resolvePuppeteer();
  const chromePath = chromeExecutableCandidates();
  const browser = await puppeteer.launch({
    headless: 'new',
    executablePath: chromePath,
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
  });

  const page = await browser.newPage();
  await page.setViewport({ width: VIEWPORT_W, height: VIEWPORT_H, deviceScaleFactor: 1 });

  const fileUrl = 'file://' + HTML_FILE;
  await page.goto(fileUrl, { waitUntil: 'networkidle0', timeout: 30000 });

  await page.waitForFunction('typeof window.setGlobalTime === "function"', { timeout: 10000 });
  await page.waitForFunction('typeof window.VIDEO_TOTAL === "number"', { timeout: 5000 });

  const total = await page.evaluate(() => window.VIDEO_TOTAL);
  const totalFrames = Math.ceil(total * FPS);
  console.log(`  Duration: ${total}s -> ${totalFrames} frames\n`);

  for (let i = 0; i <= totalFrames; i++) {
    const t = i / FPS;
    if (t > total) break;

    await page.evaluate((time) => window.setGlobalTime(time), t);
    await new Promise((r) => setTimeout(r, SETTLE_MS));

    await page.evaluate(() => {
      const fixed = document.querySelectorAll(
        '[style*="position: fixed"], [style*="position:fixed"], [data-export-hide]'
      );
      fixed.forEach((el) => { el.dataset._wasVisible = el.style.display; el.style.display = 'none'; });
    });

    const framePad = String(i).padStart(5, '0');
    await page.screenshot({
      path: path.join(FRAMES_DIR, `frame_${framePad}.png`),
      clip: { x: 0, y: 0, width: VIEWPORT_W, height: VIEWPORT_H },
    });

    await page.evaluate(() => {
      const fixed = document.querySelectorAll('[data-_wasVisible]');
      fixed.forEach((el) => { el.style.display = el.dataset._wasVisible || ''; delete el.dataset._wasVisible; });
    });

    if (i % 20 === 0) process.stdout.write(`  Frame ${i}/${totalFrames} (t=${t.toFixed(1)}s)\r`);
  }

  await browser.close();
  console.log(`\n\nFrames captured (${totalFrames + 1} total)\n`);

  console.log('Generating palette...');
  execSync(
    `ffmpeg -y -framerate ${FPS} -i "${FRAMES_DIR}/frame_%05d.png" ` +
    `-vf "fps=${FPS},scale=${WIDTH}:-1:flags=lanczos,palettegen=max_colors=128" ` +
    `"${PALETTE_F}"`,
    { stdio: 'inherit' }
  );

  console.log('\nEncoding GIF...');
  execSync(
    `ffmpeg -y -framerate ${FPS} -i "${FRAMES_DIR}/frame_%05d.png" ` +
    `-i "${PALETTE_F}" ` +
    `-filter_complex "fps=${FPS},scale=${WIDTH}:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=5" ` +
    `"${GIF_OUT}"`,
    { stdio: 'inherit' }
  );
  if (fs.existsSync(PALETTE_F)) fs.unlinkSync(PALETTE_F);

  if (WANT_MP4) {
    console.log('\nEncoding MP4 (H.264)...');
    execSync(
      `ffmpeg -y -framerate ${FPS} -i "${FRAMES_DIR}/frame_%05d.png" ` +
      `-c:v libx264 -pix_fmt yuv420p -crf 20 -movflags +faststart "${MP4_OUT}"`,
      { stdio: 'inherit' }
    );
    const mp4Mb = (fs.statSync(MP4_OUT).size / 1024 / 1024).toFixed(1);
    console.log(`MP4 ready: ${path.basename(MP4_OUT)} (${mp4Mb} MB)`);
  }

  if (!KEEP_FRAMES) fs.rmSync(FRAMES_DIR, { recursive: true });

  const gifMb = (fs.statSync(GIF_OUT).size / 1024 / 1024).toFixed(1);
  console.log(`\nGIF ready: ${path.basename(GIF_OUT)} (${gifMb} MB)\n`);
})();

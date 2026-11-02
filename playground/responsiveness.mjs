// Measures page timer scheduling while the dedicated worker decodes a file.
import { chromium } from 'playwright';
import { resolve } from 'node:path';
import { writeFile, mkdir } from 'node:fs/promises';
const fixture = resolve(process.argv[2] || 'validation/cache/flac-test-files/subset/34 - samplerate 192kHz, using only 32nd order predictors.flac');
const backend = process.argv[3] || 'js';
const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage();
  await page.goto('http://127.0.0.1:8080');
  await page.locator('#backend').selectOption(backend);
  await page.evaluate(() => {
    window.tickDelays = [];
    let previous = performance.now();
    window.ticker = setInterval(() => { const now = performance.now(); window.tickDelays.push(now - previous); previous = now; }, 10);
  });
  await page.locator('#file').setInputFiles(fixture);
  await page.waitForFunction(() => /Decoded\.|Invalid\(|Limit\(|PreviewError/.test(document.querySelector('#status').textContent), null, { timeout: 120000 });
  const result = await page.evaluate(() => {
    clearInterval(window.ticker);
    return { status: document.querySelector('#status').textContent, details: document.querySelector('#details').textContent, pageTimerTicks: window.tickDelays.length, maxTimerGapMs: Math.max(...window.tickDelays) };
  });
  await mkdir('validation/results/browser', { recursive: true });
  await writeFile(`validation/results/browser/responsiveness-${backend}.json`, JSON.stringify({ fixture, backend, ...result }, null, 2) + '\n');
  console.log(result);
  if (!result.status.includes('Decoded.') || !result.pageTimerTicks) process.exitCode = 1;
} finally { await browser.close(); }

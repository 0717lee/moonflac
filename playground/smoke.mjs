// Run after starting serve.mjs. Uses an already installed Playwright package.
import { chromium } from 'playwright';
import { resolve } from 'node:path';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import assert from 'node:assert/strict';
const fixture = resolve(process.argv[2] || 'validation/cache/generated/depth-07-channels-2.flac');
const backend = process.argv[3] || 'js';
await mkdir('validation/results/browser', { recursive: true });
const browser = await chromium.launch({ headless: true });
try {
const page = await browser.newPage({ viewport: { width: 1280, height: 1000 } });
const errors = [];
const artifactRequests = [];
page.on('pageerror', error => errors.push(error.message));
page.on('request', request => { if (/decoder\.(js|wasm)$/.test(request.url())) artifactRequests.push(request.url()); });
await page.addInitScript(() => {
  AudioContext.prototype.decodeAudioData = () => { throw Error('Browser compressed decoding is forbidden in this test'); };
});
await page.goto('http://127.0.0.1:8080');
await page.locator('#backend').selectOption(backend);
await page.locator('#file').setInputFiles(fixture);
await page.waitForFunction(() => /Decoded\.|Invalid\(|PreviewError|Limit\(/.test(document.querySelector('#status').textContent), null, { timeout: 30000 });
assert.match(await page.locator('#status').textContent(), /Decoded\./);
assert.match(await page.locator('#details').textContent(), backend === 'wasm-gc' ? /WebAssembly GC/ : /JavaScript/);
const playbackAvailable = await page.locator('#play').isEnabled();
if (playbackAvailable) await page.locator('#play').click();
else assert.match(await page.locator('#status').textContent(), /Playback unavailable/);
const duration = Number(await page.locator('#seek').getAttribute('max'));
if (playbackAvailable && duration > 0.5) {
  await page.waitForFunction(() => document.querySelector('#position').textContent !== '00:00.000');
  assert.match(await page.locator('#play').textContent(), /Pause/);
  await page.locator('#play').click();
  assert.match(await page.locator('#play').textContent(), /Play/);
  assert.notEqual(await page.locator('#position').textContent(), '00:00.000');
}
await page.locator('#seek').fill('0.01');
await page.locator('#stop').click();
const downloadPromise = page.waitForEvent('download');
await page.locator('#export').click();
const download = await downloadPromise;
await download.saveAs(`validation/results/browser/export-${backend}.wav`);
await page.screenshot({ path: `validation/results/browser/desktop-${backend}.png`, fullPage: true });
await page.setViewportSize({ width: 390, height: 844 });
await page.screenshot({ path: `validation/results/browser/mobile-${backend}.png`, fullPage: true });
const result = await page.evaluate(() => ({ status: document.querySelector('#status').textContent, details: document.querySelector('#details').textContent, horizontalOverflow: document.documentElement.scrollWidth > innerWidth }));
result.initialArtifactRequests = [...artifactRequests];
assert.equal(artifactRequests.length, 1);
assert.ok(artifactRequests[0].endsWith(backend === 'wasm-gc' ? 'decoder.wasm' : 'decoder.js'));
const otherBackend = backend === 'js' ? 'wasm-gc' : 'js';
await page.locator('#backend').selectOption(otherBackend);
await page.waitForFunction(() => document.querySelector('#status').textContent.includes('Decoded.'));
assert.match(await page.locator('#details').textContent(), otherBackend === 'wasm-gc' ? /WebAssembly GC/ : /JavaScript/);
const alternateDownloadPromise = page.waitForEvent('download');
await page.locator('#export').click();
const alternateDownload = await alternateDownloadPromise;
const alternatePath = `validation/results/browser/switch-${backend}-to-${otherBackend}.wav`;
await alternateDownload.saveAs(alternatePath);
assert.deepEqual(await readFile(alternatePath), await readFile(`validation/results/browser/export-${backend}.wav`));
result.backendSwitchWavIdentical = true;
await page.locator('#backend').selectOption(backend);
await page.waitForFunction(() => document.querySelector('#status').textContent.includes('Decoded.'));
const bytes = Array.from(await readFile(fixture));
await page.evaluate(bytes => {
  const transfer = new DataTransfer();
  transfer.items.add(new File([new Uint8Array(bytes)], 'dropped.flac'));
  document.querySelector('#drop').dispatchEvent(new DragEvent('drop', { dataTransfer: transfer, bubbles: true }));
}, bytes);
await page.waitForFunction(() => document.querySelector('#status').textContent.includes('Decoded.'));
assert.equal(await page.locator('#filename').textContent(), 'dropped.flac');
await page.locator('#file').setInputFiles({ name: 'invalid.flac', mimeType: 'audio/flac', buffer: Buffer.from('not FLAC') });
await page.waitForFunction(() => !document.querySelector('#status').textContent.includes('Decoding') && !document.querySelector('#status').textContent.includes('Reading'));
assert.equal(await page.locator('#play').isDisabled(), true);
result.invalidDiagnostic = await page.locator('#status').textContent();
const report = JSON.stringify({ fixture, backend, ...result, errors }, null, 2);
await writeFile(`validation/results/browser/smoke-${backend}.json`, report + '\n');
console.log(report);
if (errors.length || result.horizontalOverflow) process.exitCode = 1;
} finally { await browser.close(); }

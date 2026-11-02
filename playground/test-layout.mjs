// Fixtures are generated independently by cmd/test_cli.py using libFLAC.
// Start serve.mjs and build both artifacts before running this regression.
import { chromium } from 'playwright';
import assert from 'node:assert/strict';
import { readFile, mkdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
const fixtures = resolve('validation/cache/review-layout');
const out = resolve('validation/results/review-browser');
await mkdir(out, { recursive: true });
function wave(bytes) {
  const chunks = new Map();
  for (let p = 12; p + 8 <= bytes.length;) {
    const n = bytes.readUInt32LE(p + 4); chunks.set(bytes.toString('ascii', p, p + 4), bytes.subarray(p + 8, p + 8 + n)); p += 8 + n + (n & 1);
  }
  const fmt = chunks.get('fmt ');
  return { mask: fmt.readUInt16LE(0) === 0xfffe ? fmt.readUInt32LE(20) : null, pcm: chunks.get('data') };
}
const cases = [
  { name: 'side51', mask: 0x60f, play: false },
  { name: 'undefined4', mask: 0, play: false },
  { name: 'partial4', mask: 3, play: true },
  { name: 'default51', mask: 0x3f, play: true },
  { name: 'absent', mask: 0x3f, play: true, raw: 'six.raw', explicit: false },
  { name: 'explicitdefault', mask: 0x3f, play: true, raw: 'six.raw' },
  { name: 'mixedcase', mask: 0x60f, play: false, raw: 'six.raw' },
  { name: 'compatible', ext: 'oga', mask: 0x3f, play: true, raw: 'six.raw', repeat: 2, explicit: false },
  { name: 'incompatible', ext: 'oga', error: /speaker layout/ },
  { name: 'stereo', path: resolve('validation/cache/generated/depth-16-channels-2.flac'), mask: null, effective: 3, play: true, rawPath: resolve('validation/cache/generated/depth-16-channels-2.pcm'), explicit: false },
  { name: 'default8', path: resolve('validation/cache/generated/depth-32-channels-8.flac'), mask: 0x63f, play: false, rawPath: resolve('validation/cache/generated/depth-32-channels-8.pcm'), explicit: false },
];
const browser = await chromium.launch({ headless: true });
const reports = [];
try {
  for (const backend of ['js', 'wasm-gc']) {
    const page = await browser.newPage();
    const errors = []; page.on('pageerror', e => errors.push(e.message));
    await page.addInitScript(() => { AudioContext.prototype.decodeAudioData = () => { throw Error('Compressed browser decoding forbidden'); }; });
    await page.goto('http://127.0.0.1:8080');
    await page.locator('#backend').selectOption(backend);
    for (const item of cases) {
      await page.locator('#file').setInputFiles(item.path || resolve(fixtures, `${item.name}.${item.ext || 'flac'}`));
      await page.waitForFunction(() => /Decoded\.|Invalid\(|PreviewError|Limit\(/.test(document.querySelector('#status').textContent));
      const status = await page.locator('#status').textContent();
      if (item.error) {
        assert.match(status, item.error); assert.equal(await page.locator('#play').isDisabled(), true); assert.equal(await page.locator('#export').isDisabled(), true);
        reports.push({ backend, name: item.name, status }); continue;
      }
      assert.match(status, /Decoded\./);
      assert.equal(await page.locator('#play').isEnabled(), item.play, `${backend}/${item.name} playback`);
      if (!item.play) assert.match(status, /Playback unavailable/);
      if (item.name === 'partial4') assert.match(status, /2 named channels; 2 unnamed channels/);
      const metadata = await page.locator('#metadata').textContent();
      assert.ok(metadata.includes(`0x${(item.effective ?? item.mask).toString(16).padStart(4, '0')}`));
      assert.ok(metadata.includes(item.explicit === false ? 'FLAC default' : 'explicit metadata'));
      if (item.name === 'side51' || item.name === 'partial4') {
        await page.locator('details').evaluate(el => { el.open = true; });
        await page.screenshot({ path: resolve(out, `${backend}-${item.name}.png`), fullPage: true });
      }
      const downloadPromise = page.waitForEvent('download'); await page.locator('#export').click();
      const download = await downloadPromise; const dest = resolve(out, `${backend}-${item.name}.wav`); await download.saveAs(dest);
      const actual = wave(await readFile(dest)); assert.equal(actual.mask, item.mask);
      let reference;
      if (item.raw || item.rawPath) reference = await readFile(item.rawPath || resolve(fixtures, item.raw));
      else { const ref = wave(await readFile(resolve(fixtures, `${item.name}-reference.wav`))); if (item.mask !== 0) assert.equal(actual.mask, ref.mask); reference = ref.pcm; }
      assert.deepEqual(actual.pcm, Buffer.concat(Array(item.repeat || 1).fill(reference)));
      if (backend === 'wasm-gc') assert.deepEqual(await readFile(dest), await readFile(resolve(out, `js-${item.name}.wav`)));
      reports.push({ backend, name: item.name, mask: actual.mask, pcmBytes: actual.pcm.length, playEnabled: item.play, status, referenceMatch: true });
    }
    const impulses = await page.evaluate(async () => {
      const { playbackLayout, playbackBuffer } = await import('./playback.js');
      const invalidLayout = playbackLayout(2, 0x3f);
      if (invalidLayout.available || !/more positions/.test(invalidLayout.notice)) throw Error('Unrepresentable layout lacks an explicit playback notice');
      const tests = [
        { channels: 2, mask: 3, output: 2, slots: [0, 1] },
        { channels: 4, mask: 3, output: 2, slots: [0, 1, -1, -1] },
        { channels: 3, mask: 7, output: 6, slots: [0, 1, 2] },
        { channels: 4, mask: 0x33, output: 4, slots: [0, 1, 2, 3] },
        { channels: 6, mask: 0x3f, output: 6, slots: [0, 1, 2, 3, 4, 5] },
        { channels: 1, mask: 4, output: 6, slots: [2] },
      ];
      for (const t of tests) {
        const context = new OfflineAudioContext(t.output, 128, 48000);
        const pcm = { samples: 128, rate: 48000, pcm: Array.from({ length: t.channels }, (_, channel) => { const a = new Float32Array(128); a[channel * 16] = .25; return a; }) };
        const source = context.createBufferSource(); source.buffer = playbackBuffer(context, pcm, playbackLayout(t.channels, t.mask)); source.connect(context.destination); source.start();
        const rendered = await context.startRendering();
        for (let channel = 0; channel < t.output; channel++) for (let i = 0; i < 128; i++) {
          const expected = t.slots.some((slot, input) => slot === channel && i === input * 16) ? .25 : 0;
          if (rendered.getChannelData(channel)[i] !== expected) throw Error(`Impulse routing failed mask=${t.mask} output=${channel} sample=${i}`);
        }
      }
      return tests;
    });
    assert.deepEqual(errors, []); reports.push({ backend, offlineImpulseRoutes: impulses, pageErrors: errors });
    await page.close();
  }
} finally { await browser.close(); }
await writeFile(resolve(out, 'layout-regression.json'), JSON.stringify(reports, null, 2) + '\n');
console.log(`PASS: ${cases.length * 2} artifact/layout cases plus 12 offline impulse renderings; exports match independent libFLAC/source PCM.`);

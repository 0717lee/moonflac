let decoded, input, wavChunks, decoder, backend;
async function loadDecoder(selected) {
  if (selected === 'js') {
    const module = await import('./decoder.js');
    return { decode: () => module.decode_browser(input), export: () => module.export_browser(input) };
  }
  if (selected !== 'wasm-gc') throw Error(`Unknown backend: ${selected}`);
  let bytes, kind;
  const imports = { moonflac: {
    input_length: () => input.length,
    input_byte: index => input[index],
    begin: (...args) => globalThis.moonflacBegin(...args),
    layout: (mask, explicit) => globalThis.moonflacLayout(mask, Boolean(explicit)),
    pcm_sample: (channel, index, value) => { decoded.pcm[channel][index] = value; },
    bytes_begin: (type, length) => { kind = type; bytes = new Uint8Array(length); },
    bytes_put: (index, value) => { bytes[index] = value; },
    bytes_end: () => {
      if (kind === 3) { globalThis.moonflacWav(bytes); return; }
      const text = new TextDecoder().decode(bytes);
      if (kind === 0) globalThis.moonflacStatus(text);
      else if (kind === 1) globalThis.moonflacMetadata(text);
      else throw Error(text);
    },
  } };
  const response = await fetch('./decoder.wasm');
  if (!response.ok) throw Error('Wasm decoder not built. Run node playground/build.mjs.');
  const { instance } = await WebAssembly.instantiate(await response.arrayBuffer(), imports);
  return { decode: () => instance.exports.run_decode(), export: () => instance.exports.run_export() };
}
globalThis.moonflacWav = value => wavChunks.push(value);
globalThis.moonflacBegin = (rate, channels, bits, samples) => {
  if (samples * channels > 32 * 1024 * 1024) throw Error('Preview PCM limit: 32 million channel samples. Use the streaming CLI for larger recordings.');
  decoded = { rate, bits, samples, pcm: Array.from({ length: channels }, () => new Int32Array(samples)) };
};
globalThis.moonflacChannel = (channel, offset, values) => decoded.pcm[channel].set(values, offset);
globalThis.moonflacStatus = value => { decoded.integrity = value; };
globalThis.moonflacMetadata = value => { decoded.metadata = value; };
globalThis.moonflacLayout = (mask, explicit) => { decoded.channelMask = mask >>> 0; decoded.explicitChannelMask = explicit; };
self.onmessage = async ({ data }) => {
  try {
    if (data.type === 'export') {
      wavChunks = []; decoder.export();
      const length = wavChunks.reduce((sum, part) => sum + part.length, 0);
      const output = new Uint8Array(length); let offset = 0;
      for (const part of wavChunks) { output.set(part, offset); offset += part.length; }
      const buffer = output.buffer; wavChunks = null; self.postMessage({ type: 'wav', buffer }, [buffer]); return;
    }
    decoded = null;
    backend = data.backend;
    const loadStarted = performance.now(); decoder = await loadDecoder(backend);
    const loadElapsed = performance.now() - loadStarted;
    const started = performance.now(); input = new Uint8Array(data.buffer); decoder.decode();
    const elapsed = performance.now() - started;
    const scale = 2 ** (decoded.bits - 1);
    const pcm = decoded.pcm.map(channel => Float32Array.from(channel, sample => sample / scale));
    const peaks = new Float32Array(4096);
    for (let bin = 0; bin < 2048; bin++) {
      const from = Math.floor(bin * decoded.samples / 2048), to = Math.max(from + 1, Math.floor((bin + 1) * decoded.samples / 2048));
      for (const channel of pcm) for (let i = from; i < to; i++) {
        peaks[bin * 2] = Math.min(peaks[bin * 2], channel[i] || 0);
        peaks[bin * 2 + 1] = Math.max(peaks[bin * 2 + 1], channel[i] || 0);
      }
    }
    self.postMessage({ type: 'decoded', ...decoded, pcm, peaks, elapsed, backend, loadElapsed }, [...pcm.map(c => c.buffer), peaks.buffer]);
    decoded = null;
  } catch (error) { self.postMessage({ type: 'error', message: String(error.message || error) }); }
};


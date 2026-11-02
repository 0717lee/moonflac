import { playbackLayout, playbackBuffer } from './playback.js';
const $ = id => document.getElementById(id);
let worker, pcm, audio, source, audioBuffer, offset = 0, started = 0, playing = false, filename = '', generation = 0;
let playbackRequest = 0;
let selectedFile;
const time = seconds => `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${(seconds % 60).toFixed(3).padStart(6, '0')}`;
function position() { return playing ? Math.min(pcm.samples / pcm.rate, offset + audio.currentTime - started) : offset; }
function pause() { playbackRequest++; offset = position(); playing = false; if (source) { source.onended = null; source.stop(); source = null; } $('play').textContent = '▶ Play'; }
async function play() {
  if (playing) { pause(); return; }
  const request = ++playbackRequest;
  try {
    audio ||= new AudioContext(); await audio.resume();
    if (request !== playbackRequest || !pcm) return;
    const layout = playbackLayout(pcm.pcm.length, pcm.channelMask);
    if (!layout.available) throw Error(layout.notice);
    if (!audioBuffer) {
      audioBuffer = playbackBuffer(audio, pcm, layout);
    }
    const buffer = audioBuffer;
    if (offset >= buffer.duration) offset = 0;
    source = audio.createBufferSource(); source.buffer = buffer; source.connect(audio.destination);
    started = audio.currentTime; playing = true; source.start(0, offset); $('play').textContent = 'Ⅱ Pause';
    source.onended = () => { playing = false; offset = buffer.duration; source = null; $('play').textContent = '▶ Play'; };
  } catch (error) { $('status').textContent = `Playback unavailable: ${error.message}. WAV export remains available.`; }
}
function draw() {
  const canvas = $('wave'), width = canvas.clientWidth, height = canvas.clientHeight;
  const scale = devicePixelRatio || 1; canvas.width = width * scale; canvas.height = height * scale;
  const ctx = canvas.getContext('2d'); ctx.scale(scale, scale); ctx.strokeStyle = '#3a433c';
  ctx.beginPath(); ctx.moveTo(0, height / 2); ctx.lineTo(width, height / 2); ctx.stroke();
  if (!pcm) return;
  ctx.strokeStyle = '#d6ee91'; ctx.beginPath();
  for (let x = 0; x < width; x++) {
    const from = Math.floor(x * 2048 / width), to = Math.max(from + 1, Math.floor((x + 1) * 2048 / width));
    let min = 0, max = 0;
    for (let i = from; i < to; i++) { min = Math.min(min, pcm.peaks[i * 2] || 0); max = Math.max(max, pcm.peaks[i * 2 + 1] || 0); }
    ctx.moveTo(x, height / 2 - max * height * .46); ctx.lineTo(x, height / 2 - min * height * .46);
  } ctx.stroke();
}
function enabled(value) { for (const id of ['play', 'stop', 'seek', 'export']) $(id).disabled = !value; }
async function load(file) {
  if (!file) return;
  selectedFile = file;
  const current = ++generation; pause(); worker?.terminate(); pcm = null; audioBuffer = null; offset = 0; enabled(false); draw();
  $('filename').textContent = filename = file.name; $('status').textContent = 'Reading recording…';
  if (file.size > 64 * 1024 * 1024) { $('status').textContent = 'Preview limit: 64 MiB compressed. Use the CLI for larger recordings.'; return; }
  try {
    const buffer = await file.arrayBuffer(); if (current !== generation) return;
    worker = new Worker('./worker.js', { type: 'module' });
    worker.onerror = event => { $('status').textContent = `Worker could not run: ${event.message}. Build the decoder first (see README).`; };
    worker.onmessage = ({ data }) => {
      if (data.type === 'error') { $('status').textContent = data.message; $('export').disabled = !pcm; return; }
      if (data.type === 'wav') {
        const url = URL.createObjectURL(new Blob([data.buffer], { type: 'audio/wav' }));
        const link = document.createElement('a'); link.href = url; link.download = filename.replace(/\.[^.]*$/, '') + '.wav'; link.click();
        setTimeout(() => URL.revokeObjectURL(url), 1000); $('export').disabled = false; $('status').textContent = 'WAV exported with original integer precision.'; return;
      }
      pcm = data; enabled(true); $('seek').max = data.samples / data.rate; $('seek').value = 0;
      const layout = playbackLayout(data.pcm.length, data.channelMask);
      $('play').disabled = !layout.available;
      $('rate').textContent = `${(data.rate / 1000).toFixed(3)} kHz`; $('bits').textContent = `${data.bits} bit`;
      $('channels').textContent = data.pcm.length; $('timing').textContent = `${data.elapsed.toFixed(1)} ms`;
      $('duration').textContent = time(data.samples / data.rate);
      const backendName = data.backend === 'wasm-gc' ? 'WebAssembly GC' : 'JavaScript';
      $('details').textContent = `Backend: MoonBit → ${backendName} / Worker. ${data.samples.toLocaleString()} samples per channel. Integrity: ${data.integrity}. Decode + input/PCM bridge: ${data.elapsed.toFixed(2)} ms; ${(data.samples / data.rate / (data.elapsed / 1000)).toFixed(1)}× realtime. Backend load/compile: ${data.loadElapsed.toFixed(2)} ms (excluded). Web Audio receives only MoonBit PCM.`;
      $('metadata').textContent = `Speaker mask: 0x${data.channelMask.toString(16).padStart(4, '0')} (${data.explicitChannelMask ? 'explicit metadata' : 'FLAC default'}).\n${data.metadata || ''}`;
      $('status').textContent = `Decoded. ${layout.notice}`; draw();
    };
    $('status').textContent = 'Decoding in worker… Choose another file to cancel.';
    worker.postMessage({ type: 'decode', buffer, backend: $('backend').value }, [buffer]);
  } catch (error) { $('status').textContent = error.message; }
}
$('file').addEventListener('change', event => load(event.target.files[0]));
$('backend').addEventListener('change', () => { if (selectedFile) load(selectedFile); });
for (const type of ['dragenter','dragover']) $('drop').addEventListener(type, event => { event.preventDefault(); $('drop').classList.add('drag'); });
for (const type of ['dragleave','drop']) $('drop').addEventListener(type, event => { event.preventDefault(); $('drop').classList.remove('drag'); });
$('drop').addEventListener('drop', event => load(event.dataTransfer.files[0]));
$('play').onclick = play; $('stop').onclick = () => { pause(); offset = 0; };
$('seek').oninput = () => { const resume = playing; pause(); offset = Number($('seek').value); if (resume) play(); };
$('export').onclick = () => { $('export').disabled = true; $('status').textContent = 'Preparing lossless WAV…'; worker.postMessage({ type: 'export' }); };
setInterval(() => { $('position').textContent = time(position()); if (pcm) $('seek').value = position(); }, 100);
new ResizeObserver(draw).observe($('wave')); draw();

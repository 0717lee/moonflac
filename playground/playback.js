// W3C Web Audio speaker layouts are mono, stereo, quad (back L/R), and
// 5.1 (front L/R/C, LFE, back L/R). Side/height positions are not aliases.
// https://www.w3.org/TR/webaudio/#channel-up-mixing-and-down-mixing
export function playbackLayout(channels, mask) {
  const hex = `0x${mask.toString(16).padStart(4, '0')}`;
  if (!mask) return { available: false, notice: 'Playback unavailable: the channel mask explicitly leaves every speaker unspecified. WAV export preserves all channels.' };
  if (mask & ~0x3f) return { available: false, notice: `Playback unavailable: speaker layout ${hex} contains positions outside Web Audio’s mono/stereo/quad/5.1 speaker model. WAV export preserves all channels.` };
  const speakers = [];
  for (let bit = 0; bit < 6; bit++) if (mask & (1 << bit)) speakers.push(bit);
  if (speakers.length > channels) return { available: false, notice: 'Playback unavailable: the speaker mask names more positions than PCM channels. WAV export preserves the supplied layout.' };
  let outputChannels, slots;
  if (mask === 4 && speakers.length === channels) { outputChannels = 1; slots = [0]; }
  else if (!(mask & ~3)) { outputChannels = 2; slots = speakers; }
  else if (!(mask & ~0x33)) { outputChannels = 4; slots = speakers.map(bit => bit < 2 ? bit : bit - 2); }
  else { outputChannels = 6; slots = speakers; }
  const omitted = channels - speakers.length;
  return { available: true, outputChannels, slots, notice: omitted ? `Playing ${speakers.length} named channels; ${omitted} unnamed channels are silent in playback and retained in WAV export.` : `Playback uses ${outputChannels === 1 ? 'mono' : outputChannels === 2 ? 'stereo' : outputChannels === 4 ? 'quad' : '5.1'} speaker routing; the audio device may downmix.` };
}

export function playbackBuffer(context, pcm, layout) {
  if (!layout.available) throw Error(layout.notice);
  const buffer = context.createBuffer(layout.outputChannels, pcm.samples, pcm.rate);
  layout.slots.forEach((slot, channel) => buffer.copyToChannel(pcm.pcm[channel], slot));
  return buffer;
}

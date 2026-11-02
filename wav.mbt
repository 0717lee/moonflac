///|
/// Serialize owned interleaved PCM. Raw PCM is signed, little endian and
/// sign-extended. WAV PCM is left-aligned and its 8-bit container is unsigned.
pub fn frame_pcm(frame : Frame, wav~ : Bool = false) -> Bytes {
  let width = (frame.bits_per_sample + 7) / 8
  let count = frame.channels.length()
  Bytes::makei(frame.block_size * count * width, i => {
    let sample = frame.channels[i / width % count][i / (width * count)]
    let aligned = if wav {
      sample << (width * 8 - frame.bits_per_sample)
    } else {
      sample
    }
    let value = if wav && width == 1 { aligned + 128 } else { aligned }
    ((value >> (i % width * 8)) & 255).to_byte()
  })
}

///|
fn wav_put(out : Array[Byte], value : Int64, size : Int32) -> Unit {
  for i in 0..<size {
    out.push(((value >> (8 * i)) & 255L).to_int().to_byte())
  }
}

///|
fn wav_tag(out : Array[Byte], tag : Bytes) -> Unit {
  for byte in tag {
    out.push(byte)
  }
}

///|
/// Header only, allowing RF64 size planning without PCM allocation. Append
/// exactly samples * channels * ceil(bits/8) data bytes and, when odd, one zero
/// pad byte. The pad is included in RIFF/ds64 size but excluded from data size.
pub fn wav_header(
  info : StreamInfo,
  samples : Int64,
  channel_mask? : UInt32,
  rf64~ : Bool = false,
) -> Bytes raise FlacError {
  if info.bits_per_sample < 4 ||
    info.bits_per_sample > 32 ||
    info.channels < 1 ||
    info.channels > 8 ||
    info.sample_rate < 1 ||
    info.sample_rate > 1048575 ||
    samples < 0L {
    raise Invalid(0L, "invalid WAV audio dimensions")
  }
  let width = (info.bits_per_sample + 7) / 8
  let align = width * info.channels
  if samples > (9223372036854775807L - 128L) / align.to_int64() {
    raise Limit("WAV size exceeds signed 64-bit range")
  }
  let data_size = samples * align.to_int64()
  let mask = channel_mask.unwrap_or(default_channel_mask(info.channels))
  let extensible = info.channels > 2 ||
    info.bits_per_sample > 16 ||
    info.bits_per_sample % 8 != 0 ||
    channel_mask is Some(_)
  let fmt_size = if extensible { 40 } else { 16 }
  let base_size = (12 + 8 + fmt_size + 8 - 8).to_int64() +
    data_size +
    (data_size & 1L)
  let large = rf64 || base_size > 4294967295L
  let out : Array[Byte] = []
  wav_tag(out, if large { b"RF64" } else { b"RIFF" })
  wav_put(out, if large { 4294967295L } else { base_size }, 4)
  wav_tag(out, b"WAVE")
  if large {
    wav_tag(out, b"ds64")
    wav_put(out, 28L, 4)
    wav_put(out, base_size + 36L, 8)
    wav_put(out, data_size, 8)
    wav_put(out, samples, 8)
    wav_put(out, 0L, 4)
  }
  wav_tag(out, b"fmt ")
  wav_put(out, fmt_size.to_int64(), 4)
  wav_put(out, if extensible { 65534L } else { 1L }, 2)
  wav_put(out, info.channels.to_int64(), 2)
  wav_put(out, info.sample_rate.to_int64(), 4)
  wav_put(out, (info.sample_rate * align).to_int64(), 4)
  wav_put(out, align.to_int64(), 2)
  wav_put(out, (width * 8).to_int64(), 2)
  if extensible {
    wav_put(out, 22L, 2)
    wav_put(out, info.bits_per_sample.to_int64(), 2)
    wav_put(out, mask.to_int64(), 4)
    wav_tag(
      out, b"\x01\x00\x00\x00\x00\x00\x10\x00\x80\x00\x00\xaa\x00\x38\x9b\x71",
    )
  }
  wav_tag(out, b"data")
  wav_put(out, if large { 4294967295L } else { data_size }, 4)
  Bytes::makei(out.length(), i => out[i])
}

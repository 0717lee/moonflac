///|
fn ogg_encoder_test_samples(count : Int32, channels : Int32) -> Array[Int32] {
  let samples : Array[Int32] = []
  let mut value : Int32 = 0
  for _i = 0; _i < count; _i = _i + 1 {
    for _c = 0; _c < channels; _c = _c + 1 {
      value = (value + 37) % 2001 - 1000
      samples.push(value)
    }
  }
  samples
}

///|
test "Ogg mux roundtrip preserves PCM and stream metadata" {
  let samples = ogg_encoder_test_samples(8192, 2)
  let config = EncoderConfig::new(
    { sample_rate: 48000, channels: 2, bits_per_sample: 16, },
    block_size=1024,
    effort=0,
  )
  let native = encode_pcm(samples, config)
  let ogg = ogg_from_flac(native)
  assert_eq(ogg[:4], b"OggS")
  let audio = decode(ogg)
  assert_eq(audio.frames.length(), 8)
  assert_eq(audio.frames[0].block_size, 1024)
  assert_eq(audio.metadata.info.sample_rate, 48000)
  assert_eq(audio.metadata.info.channels, 2)
  assert_eq(audio.metadata.comments.unwrap().vendor, "MoonFLAC")
  let mut at = 0
  for frame in audio.frames {
    for i = 0; i < frame.block_size; i = i + 1 {
      for c = 0; c < 2; c = c + 1 {
        assert_eq(frame.channels[c][i], samples[at])
        at += 1
      }
    }
  }
  assert_eq(at, samples.length())
}

///|
test "Ogg mux continues a frame across pages" {
  let samples : Array[Int32] = Array::make(2048 * 8, 0)
  let config = EncoderConfig::new(
    { sample_rate: 48000, channels: 8, bits_per_sample: 32, },
    block_size=2048,
    effort=0,
  )
  let native = encode_pcm(samples, config)
  let ogg = ogg_from_flac(native)
  let audio = decode(ogg)
  assert_eq(audio.frames.length(), 1)
  assert_eq(audio.frames[0].block_size, 2048)
  assert_eq(audio.frames[0].channels.length(), 8)
  assert_eq(audio.frames[0].channels[7][2047], 0)
}

///|
test "Ogg mux honors serial and vendor options" {
  let samples = ogg_encoder_test_samples(1024, 2)
  let config = EncoderConfig::new(
    { sample_rate: 48000, channels: 2, bits_per_sample: 16, },
    block_size=1024,
    effort=0,
  )
  let native = encode_pcm(samples, config)
  let ogg = ogg_from_flac(native, serial=0x12345678U, vendor="MoonTest")
  assert_eq(ogg[14].to_int(), 0x78)
  assert_eq(ogg[15].to_int(), 0x56)
  assert_eq(ogg[16].to_int(), 0x34)
  assert_eq(ogg[17].to_int(), 0x12)
  let audio = decode(ogg)
  assert_eq(audio.metadata.comments.unwrap().vendor, "MoonTest")
}

///|
test "Ogg mux rejects non-FLAC input" {
  let invalid = try {
    let _ = ogg_from_flac(b"not a flac stream")
    false
  } catch {
    Invalid(_, _) => true
    _ => false
  }
  assert_true(invalid)
}

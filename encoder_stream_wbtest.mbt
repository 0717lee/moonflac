///|
fn encstream_collect(
  samples : Array[Int32],
  config : EncoderConfig,
  cut : Int32,
) -> (Bytes, Bytes, EncoderSummary, Int32) raise {
  let encoder = Encoder::new(config)
  assert_eq(encoder.push(samples), 0)
  let chunks : Array[Bytes] = []
  let mut cursor = 0
  while true {
    match encoder.next() {
      EncodedBytes(bytes) => chunks.push(bytes)
      NeedPcm =>
        if cursor == samples.length() {
          encoder.finish()
          encoder.finish()
        } else {
          let end = if cursor + cut < samples.length() {
            cursor + cut
          } else {
            samples.length()
          }
          cursor += encoder.push(samples[cursor:end].to_owned())
        }
      EncoderDone(summary) => {
        let raw = @buffer.Buffer()
        let patched = @buffer.Buffer()
        assert_eq(summary.final_header.length(), chunks[0].length())
        patched.write_bytes(summary.final_header)
        for i in 0..<chunks.length() {
          raw.write_bytes(chunks[i])
          if i > 0 {
            patched.write_bytes(chunks[i])
          }
        }
        match encoder.next() {
          EncoderDone(again) => assert_eq(again.md5, summary.md5)
          _ => fail("encoder completion is not stable")
        }
        encoder.finish()
        let rejected = try {
          ignore(encoder.push([]))
          false
        } catch {
          Invalid(_, _) => true
          _ => false
        }
        assert_true(rejected)
        return (
          patched.to_bytes(),
          raw.to_bytes(),
          summary,
          encoder.peak_buffered_samples(),
        )
      }
    }
  } nobreak {
    raise Invalid(0L, "encoder test did not complete")
  }
}

///|
test "encoder scalar chunking is deterministic and nonseekable output remains valid" {
  let samples = Array::makei(111, i => i * 37 % 511 - 255)
  let format : PcmFormat = {
    sample_rate: 48000,
    channels: 3,
    bits_per_sample: 12,
  }
  let config = EncoderConfig::new(format, block_size=16, effort=0)
  let whole = encode_pcm(samples, config)
  let expected = Md5::new()
  expected.update(
    Bytes::makei(samples.length() * 2, i => {
      ((samples[i / 2] >> (i % 2 * 8)) & 255).to_byte()
    }),
  )
  for cut in 1..<=samples.length() {
    let (patched, raw, summary, peak) = encstream_collect(samples, config, cut)
    assert_eq(patched, whole)
    assert_eq(summary.total_samples, 37L)
    assert_eq(summary.md5, expected.digest())
    assert_true(peak <= 48)
    assert_eq(decode(raw).integrity, Md5Unavailable)
    let audio = decode(patched)
    assert_eq(audio.integrity, Md5Verified)
    let mut cursor = 0
    for frame in audio.frames {
      for i in 0..<frame.block_size {
        for c in 0..<3 {
          assert_eq(frame.channels[c][i], samples[cursor])
          cursor += 1
        }
      }
    }
    assert_eq(cursor, samples.length())
  }
}

///|
test "encoder push backpressure copies accepted PCM and retains bounded prefixes" {
  let config = EncoderConfig::new(
    { sample_rate: 44100, channels: 2, bits_per_sample: 16, },
    block_size=16,
    effort=0,
  )
  let encoder = Encoder::new(config)
  let input = Array::makei(40, i => i - 20)
  assert_eq(encoder.push(input), 0)
  assert_eq(encoder.buffered_samples(), 0)
  assert_true(encoder.next() is EncodedBytes(_))
  assert_eq(encoder.push(input), 32)
  assert_eq(encoder.push([9]), 0)
  assert_eq(encoder.buffered_samples(), 32)
  input.fill(30000)
  let body = match encoder.next() {
    EncodedBytes(bytes) => bytes
    _ => fail("missing compressed frame")
  }
  assert_eq(encoder.buffered_samples(), 0)
  encoder.finish()
  let summary = match encoder.next() {
    EncoderDone(value) => value
    _ => fail("missing summary")
  }
  let decoded = decode(summary.final_header + body)
  assert_eq(decoded.frames[0].channels[0][0], -20)
  assert_eq(decoded.frames[0].channels[1][15], 11)
  assert_eq(encoder.peak_buffered_samples(), 32)
}

///|
test "encoder invalid PCM and EOF failures remain terminal" {
  let config = EncoderConfig::new(
    { sample_rate: 48000, channels: 2, bits_per_sample: 4, },
    block_size=16,
  )
  for data in [[], [0], [0, 8], [0, -9]] {
    let encoder = Encoder::new(config)
    ignore(encoder.next())
    let rejected = try {
      ignore(encoder.push(data))
      encoder.finish()
      false
    } catch {
      Invalid(_, _) => true
      _ => false
    }
    assert_true(rejected)
    let terminal = try {
      ignore(encoder.next())
      false
    } catch {
      Invalid(_, _) => true
      _ => false
    }
    assert_true(terminal)
  }
  let encoder = Encoder::new(config)
  ignore(encoder.next())
  assert_eq(encoder.push([-8, 7]), 2)
  encoder.finish()
  assert_true(encoder.next() is EncodedBytes(_))
}

///|
test "encoder validates configuration and 36-bit total sample limit" {
  let base = EncoderConfig::new({
    sample_rate: 48000,
    channels: 1,
    bits_per_sample: 16,
  })
  let invalid = [
    { ..base, block_size: 15, },
    { ..base, block_size: 65536, },
    { ..base, effort: -1, },
    { ..base, effort: 9, },
    { ..base, format: { ..base.format, channels: 0, }, },
    { ..base, format: { ..base.format, channels: 9, }, },
    { ..base, format: { ..base.format, bits_per_sample: 3, }, },
    { ..base, format: { ..base.format, bits_per_sample: 33, }, },
    { ..base, format: { ..base.format, sample_rate: -1, }, },
    { ..base, format: { ..base.format, sample_rate: 1048576, }, },
    { ..base, format: { ..base.format, sample_rate: 0, }, },
    { ..base, max_metadata_bytes: 41, },
  ]
  for config in invalid {
    let rejected = try {
      ignore(Encoder::new(config))
      false
    } catch {
      _ => true
    }
    assert_true(rejected)
  }
  let encoder = Encoder::new({ ..base, block_size: 16, })
  ignore(encoder.next())
  // White-box boundary setup avoids allocating 2^36 samples; all actual
  // encoding still enters through the public push/next protocol.
  encoder.samples = 68719476735L
  ignore(encoder.push(Array::make(16, 0)))
  let overflow = try {
    ignore(encoder.next())
    false
  } catch {
    Limit(_) => true
    _ => false
  }
  assert_true(overflow)
  let numbered = Encoder::new({ ..base, block_size: 16, })
  ignore(numbered.next())
  numbered.frames = 2147483648L
  ignore(numbered.push(Array::make(16, 0)))
  let frame_overflow = try {
    ignore(numbered.next())
    false
  } catch {
    Limit(_) => true
    _ => false
  }
  assert_true(frame_overflow)
}

///|
test "encoder supports maximum blocks explicit nonaudio and actual variable boundaries" {
  let format : PcmFormat = { sample_rate: 0, channels: 1, bits_per_sample: 32, }
  let max_config = EncoderConfig::new(
    format,
    block_size=65535,
    effort=0,
    non_audio=true,
  )
  let max_audio = decode(
    encode_pcm(Array::make(65535, -2147483648), max_config),
  )
  assert_eq(max_audio.frames[0].block_size, 65535)
  assert_eq(max_audio.frames[0].sample_rate, 0)
  assert_eq(max_audio.frames[0].channels[0][65534], -2147483648)
  let samples = Array::makei(96, i => {
    if i < 32 {
      0
    } else if i % 2 == 0 {
      1000
    } else {
      -1000
    }
  })
  let fixed = EncoderConfig::new(
    { sample_rate: 48000, channels: 1, bits_per_sample: 16, },
    block_size=64,
    effort=0,
  )
  let fixed_audio = decode(encode_pcm(samples, fixed))
  assert_eq(fixed_audio.frames.map(f => f.block_size), [64, 32])
  let variable = { ..fixed, variable_block: true, }
  let (patched, _, _, _) = encstream_collect(samples, variable, 1)
  assert_eq(patched, encode_pcm(samples, variable))
  let variable_audio = decode(patched)
  assert_eq(variable_audio.frames.map(f => f.block_size), [32, 64])
  assert_eq(variable_audio.frames.map(f => f.number), [0L, 32L])
  assert_true(variable_audio.frames.all(f => f.variable_block))
}

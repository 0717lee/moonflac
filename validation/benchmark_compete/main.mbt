// Arguments: input.raw output.flac channels bits sample-rate block-size batch effort
// Each process warms once, then measures one fixed batch of encode_pcm calls.
// Input unpacking, byte comparisons and output writes are outside core timing.

///|
fn run() -> Unit raise {
  let args = @env.args()
  let channels = @string.parse_int(args[3])
  let bits = @string.parse_int(args[4])
  let rate = @string.parse_int(args[5])
  let block_size = @string.parse_int(args[6])
  let batch = @string.parse_int(args[7])
  let effort = @string.parse_int(args[8])
  assert_true(batch > 0 && effort >= 0 && effort <= 8)
  assert_true(channels >= 1 && channels <= 8 && bits >= 4 && bits <= 32)
  let raw = @fs.read_file_to_bytes(args[1])
  let width = (bits + 7) / 8
  assert_true(raw.length() > 0 && raw.length() % (width * channels) == 0)
  let pcm = Array::makei(raw.length() / width, i => {
    let mut value = 0
    for j = 0; j < width; j = j + 1 {
      value = value | (raw[i * width + j].to_int() << (j * 8))
    }
    if width < 4 {
      value << (32 - width * 8) >> (32 - width * 8)
    } else {
      value
    }
  })
  let config = @flac.EncoderConfig::new(
    { sample_rate: rate, channels, bits_per_sample: bits, },
    block_size~,
    effort~,
  )
  let warm_start = @bench.monotonic_clock_start()
  let expected = @flac.encode_pcm(pcm, config)
  let warm_elapsed = @bench.monotonic_clock_end(warm_start)
  let per_call = Array::make(batch, 0.0)
  let mut elapsed = 0.0
  for repetition = 0; repetition < batch; repetition = repetition + 1 {
    let start = @bench.monotonic_clock_start()
    let encoded = @flac.encode_pcm(pcm, config)
    let duration = @bench.monotonic_clock_end(start) / 1000000.0
    per_call[repetition] = duration
    elapsed = elapsed + duration
    assert_eq(encoded, expected)
  }
  @fs.write_bytes_to_file(args[2], expected)
  let warm_seconds = warm_elapsed / 1000000.0
  let durations = StringBuilder()
  durations.write_string("[")
  for i = 0; i < batch; i = i + 1 {
    if i > 0 {
      durations.write_string(",")
    }
    durations.write_string(per_call[i].to_string())
  }
  durations.write_string("]")
  println(
    "MOON_CORE {\"batch\":\{batch},\"effort\":\{effort},\"seconds\":\{elapsed},\"warm_seconds\":\{warm_seconds},\"bytes\":\{expected.length()},\"per_call_seconds\":\{durations.to_string()}}",
  )
}

///|
fn main {
  run() catch {
    error => {
      println("benchmark failed: \{error}")
      panic()
    }
  }
}

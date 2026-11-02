// Isolated encode_pcm time: source I/O, integer unpacking and output I/O excluded.
// Arguments: input.raw output.flac channels bits sample-rate effort

///|
fn run() -> Unit raise {
  let args = @env.args()
  let channels = @string.parse_int(args[3])
  let bits = @string.parse_int(args[4])
  let rate = @string.parse_int(args[5])
  let effort = @string.parse_int(args[6])
  let raw = @fs.read_file_to_bytes(args[1])
  let width = (bits + 7) / 8
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
    block_size=1024,
    effort~,
  )
  let mut expected = b""
  for repetition = 0; repetition < 6; repetition = repetition + 1 {
    let start = @bench.monotonic_clock_start()
    let encoded = @flac.encode_pcm(pcm, config)
    let elapsed = @bench.monotonic_clock_end(start)
    if repetition == 0 {
      expected = encoded
    } else {
      assert_eq(encoded, expected)
    }
    println("CORE \{repetition} \{elapsed} \{encoded.length()}")
  }
  @fs.write_bytes_to_file(args[2], expected)
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

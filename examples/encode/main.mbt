///|
/// Interleaved stereo PCM: the caller advances by the accepted scalar count.
fn run() -> Unit raise {
  let config = @flac.EncoderConfig::new(
    { sample_rate: 48000, channels: 2, bits_per_sample: 24, },
    block_size=16,
    effort=5,
  )
  let pcm = Array::makei(40, i => if i % 2 == 0 { -i * 100 } else { i * 100 })
  let encoder = @flac.Encoder::new(config)
  let mut cursor = 0
  let mut bytes = 0
  while true {
    match encoder.next() {
      EncodedBytes(chunk) =>
        // A non-seekable sink can write this owned chunk immediately.
        bytes += chunk.length()
      NeedPcm =>
        if cursor == pcm.length() {
          encoder.finish()
        } else {
          cursor += encoder.push(pcm[cursor:].to_owned())
        }
      EncoderDone(summary) => {
        // A seekable sink replaces its first header with summary.final_header.
        println(
          "Encoded \{summary.total_samples} stereo frames in \{summary.frames} FLAC frames (\{bytes} bytes)",
        )
        break
      }
    }
  }
  let complete = @flac.encode_pcm(pcm, config)
  println(
    "Whole-file API finalized \{complete.length()} bytes including STREAMINFO MD5",
  )
}

///|
fn main {
  run() catch {
    error => println(error)
  }
}

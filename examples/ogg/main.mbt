// Encode a short stereo signal to Ogg FLAC and decode it with the same library.
// This is a whole-buffer example; use Encoder for bounded streaming input.

///|
fn run() -> Unit raise @flac.FlacError {
  let samples : Array[Int32] = []
  for i = 0; i < 4096; i = i + 1 {
    let value : Int32 = if i % 64 < 32 { 12000 } else { -12000 }
    samples.push(value)
    samples.push(value / 2)
  }
  let format : @flac.PcmFormat = {
    sample_rate: 48000,
    channels: 2,
    bits_per_sample: 16,
  }
  let config = @flac.EncoderConfig::new(format, block_size=1024, effort=0)
  let ogg = @flac.encode_ogg_pcm(samples, config)
  let audio = @flac.decode(ogg)
  println("Ogg bytes: \{ogg.length()}")
  println(
    "frames: \{audio.frames.length()}; samples: \{audio.frames[0].block_size}",
  )
  println("first left sample: \{audio.frames[0].channels[0][0]}")
  println("integrity: \{audio.integrity}")
}

///|
fn main {
  run() catch {
    error => println("Ogg example failed: \{error}")
  }
}

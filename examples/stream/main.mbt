// RFC 9639 Appendix D.1, a complete independent one-sample stereo file.
// The input is deliberately fed one byte at a time.

///|
fn run() -> Unit raise @flac.FlacError {
  let input = b"\x66\x4c\x61\x43\x80\x00\x00\x22\x10\x00\x10\x00\x00\x00\x0f\x00\x00\x0f\x0a\xc4\x42\xf0\x00\x00\x00\x01\x3e\x84\xb4\x18\x07\xdc\x69\x03\x07\x58\x6a\x3d\xad\x1a\x2e\x0f\xff\xf8\x69\x18\x00\x00\xbf\x03\x58\xfd\x03\x12\x8b\xaa\x9a"
  let decoder = @flac.Decoder::new()
  let mut cursor = 0
  let mut samples = 0L
  while true {
    match decoder.next() {
      MetadataReady(metadata) =>
        println("sample rate: \{metadata.info.sample_rate}")
      AudioFrame(frame) => {
        samples += frame.block_size.to_int64()
        println("left: \{frame.channels[0][0]}, right: \{frame.channels[1][0]}")
        // Consume or copy the owned PCM here; retaining it is optional.
      }
      LinkEnd(integrity) => println("link complete: \{integrity}")
      NeedInput =>
        if cursor < input.length() {
          let accepted = decoder.push(input[cursor:cursor + 1].to_owned())
          cursor += accepted
        } else {
          decoder.finish()
        }
      Done(integrity) => {
        println("samples: \{samples}; integrity: \{integrity}")
        break
      }
    }
  }
}

///|
fn main {
  run() catch {
    error => println("decoding failed: \{error}")
  }
}

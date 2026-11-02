///|
/// A validation-only framed PCM format: LE32 block/rate/bits/channels + PCM32.
fn put(out : @buffer.Buffer, value : Int32) -> Unit {
  for shift = 0; shift < 32; shift = shift + 8 {
    out.write_byte(((value >> shift) & 255).to_byte())
  }
}

///|
fn emit(out : @buffer.Buffer, frame : @flac.Frame) -> Unit {
  put(out, frame.block_size)
  put(out, frame.sample_rate)
  put(out, frame.bits_per_sample)
  put(out, frame.channels.length())
  for i = 0; i < frame.block_size; i = i + 1 {
    for c = 0; c < frame.channels.length(); c = c + 1 {
      put(out, frame.channels[c][i])
    }
  }
}

///|
fn run(args : Array[String]) -> Unit raise {
  let data = @fs.read_file_to_bytes(args[1])
  let out = @buffer.Buffer()
  let mut cursor = 0
  if args[3] == "raw" {
    let decoder = @flac.RawDecoder::new()
    while true {
      match decoder.next() {
        RawFrame(frame) => emit(out, frame)
        Skipped(offset, count) => println("skipped \{offset} \{count}")
        RawDone => break
        RawNeedInput =>
          if cursor == data.length() {
            decoder.finish()
          } else {
            let end = if cursor + 4093 < data.length() {
              cursor + 4093
            } else {
              data.length()
            }
            cursor += decoder.push(data[cursor:end].to_owned())
          }
      }
    }
  } else {
    let decoder = @flac.Decoder::new()
    while true {
      match decoder.next() {
        AudioFrame(frame) => emit(out, frame)
        MetadataReady(_) | LinkEnd(_) => ()
        Done(_) => break
        NeedInput =>
          if cursor == data.length() {
            decoder.finish()
          } else {
            let end = if cursor + 4093 < data.length() {
              cursor + 4093
            } else {
              data.length()
            }
            cursor += decoder.push(data[cursor:end].to_owned())
          }
      }
    }
  }
  @fs.write_bytes_to_file(args[2], out.to_bytes())
}

///|
fn main {
  run(@env.args()) catch {
    error => {
      println(error)
      @sys.exit(1)
    }
  }
}

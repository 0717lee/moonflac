///|
const USAGE : String =
  #|MoonFLAC — pure MoonBit FLAC codec
  #|Usage:
  #|  moonflac info INPUT [--json]
  #|  moonflac verify INPUT [--json]
  #|  moonflac decode INPUT OUTPUT [--raw] [--start SAMPLE] [--end SAMPLE] [--rf64]
  #|  moonflac encode INPUT OUTPUT [--raw --sample-rate N --channels N --bits N]
  #|    [--channel-mask HEX] [--block-size N] [--effort 0..8] [--variable-block] [--non-audio]
  #|  moonflac ogg INPUT OUTPUT [--serial HEX] [--vendor NAME]
  #|All commands accept --max-buffer BYTES (default 33554432, minimum 4).
  #|Sample ranges are zero-based and end-exclusive. Raw PCM is signed,
  #|interleaved, little-endian, unshifted, in ceil(bit-depth/8) bytes.
  #|Exit codes: 0 success; 2 usage; 3 invalid audio/resource limit; 4 file I/O failure.

///|
struct Options {
  command : String
  input : String
  output : String
  raw : Bool
  json : Bool
  start : Int64
  end : Int64?
  rf64 : Bool
  max_buffer : Int32
  sample_rate : Int32?
  channels : Int32?
  bits : Int32?
  channel_mask : UInt32?
  block_size : Int32
  effort : Int32
  variable_block : Bool
  non_audio : Bool
  serial : UInt32
  vendor : String
}

///|
fn mask_argument(value : String) -> UInt32? {
  let chars = value.to_array()
  let start = if chars.length() >= 2 &&
    chars[0] == '0' &&
    (chars[1] == 'x' || chars[1] == 'X') {
    2
  } else {
    0
  }
  if start == chars.length() {
    return None
  }
  let mut result = 0UL
  for i in start..<chars.length() {
    let c = chars[i]
    let digit = if c >= '0' && c <= '9' {
      c.to_int() - 48
    } else if c >= 'a' && c <= 'f' {
      c.to_int() - 87
    } else if c >= 'A' && c <= 'F' {
      c.to_int() - 55
    } else {
      return None
    }
    result = result * 16UL + digit.to_uint64()
    if result > 4294967295UL {
      return None
    }
  }
  Some(result.to_uint())
}

///|
fn sample_argument(value : String) -> Int64? {
  if value.is_empty() {
    return None
  }
  let mut result = 0L
  for c in value {
    if c < '0' || c > '9' {
      return None
    }
    let digit = (c.to_int() - 48).to_int64()
    if result > (9223372036854775807L - digit) / 10 {
      return None
    }
    result = result * 10 + digit
  }
  Some(result)
}

///|
fn parse(args : Array[String]) -> Options? {
  if args.length() < 2 {
    return None
  }
  let command = args[0]
  if command != "info" &&
    command != "verify" &&
    command != "decode" &&
    command != "encode" &&
    command != "ogg" {
    return None
  }
  let mut raw = false
  let mut json = false
  let mut start = 0L
  let mut end : Int64? = None
  let mut rf64 = false
  let mut max_buffer = 33554432
  let mut output = ""
  let mut sample_rate : Int32? = None
  let mut channels : Int32? = None
  let mut bits : Int32? = None
  let mut channel_mask : UInt32? = None
  let mut block_size = 4096
  let mut effort = 5
  let mut variable_block = false
  let mut non_audio = false
  let mut serial = 0x4d464c43U
  let mut vendor = "MoonFLAC"
  let mut i = 2
  if command == "decode" || command == "encode" || command == "ogg" {
    if args.length() < 3 {
      return None
    }
    output = args[2]
    if output == args[1] {
      return None
    }
    i = 3
  }
  while i < args.length() {
    match args[i] {
      "--json" if command == "info" || command == "verify" => json = true
      "--raw" if command == "decode" || command == "encode" => raw = true
      "--rf64" if command == "decode" => rf64 = true
      "--variable-block" if command == "encode" => variable_block = true
      "--non-audio" if command == "encode" => non_audio = true
      "--channel-mask" if command == "encode" => {
        if i + 1 >= args.length() {
          return None
        }
        channel_mask = mask_argument(args[i + 1])
        if channel_mask is None {
          return None
        }
        i += 1
      }
      "--serial" if command == "ogg" => {
        if i + 1 >= args.length() {
          return None
        }
        serial = match mask_argument(args[i + 1]) {
          Some(value) => value
          None => return None
        }
        i += 1
      }
      "--vendor" if command == "ogg" => {
        if i + 1 >= args.length() || args[i + 1].is_empty() {
          return None
        }
        vendor = args[i + 1]
        i += 1
      }
      "--sample-rate" | "--channels" | "--bits" | "--block-size" | "--effort" if command ==
        "encode" => {
        if i + 1 >= args.length() {
          return None
        }
        let value = match sample_argument(args[i + 1]) {
          Some(n) if n <= 2147483647L => n.to_int()
          _ => return None
        }
        match args[i] {
          "--sample-rate" => sample_rate = Some(value)
          "--channels" => channels = Some(value)
          "--bits" => bits = Some(value)
          "--block-size" => block_size = value
          _ => effort = value
        }
        i += 1
      }
      "--max-buffer" => {
        if i + 1 >= args.length() {
          return None
        }
        match sample_argument(args[i + 1]) {
          Some(value) if value >= 4L && value <= 2147483647L =>
            max_buffer = value.to_int()
          _ => return None
        }
        i += 1
      }
      "--start" | "--end" if command == "decode" => {
        if i + 1 >= args.length() {
          return None
        }
        let value = match sample_argument(args[i + 1]) {
          Some(value) => value
          None => return None
        }
        if args[i] == "--start" {
          start = value
        } else {
          end = Some(value)
        }
        i += 1
      }
      _ => return None
    }
    i += 1
  }
  if raw && rf64 {
    return None
  }
  if end is Some(value) && value < start {
    return None
  }
  if command == "encode" {
    if block_size < 16 || block_size > 65535 || effort < 0 || effort > 8 {
      return None
    }
    if raw {
      match (sample_rate, channels, bits) {
        (Some(rate), Some(count), Some(depth)) if rate <= 1048575 &&
          count >= 1 &&
          count <= 8 &&
          depth >= 4 &&
          depth <= 32 &&
          (rate != 0 || non_audio) => ()
        _ => return None
      }
    } else if sample_rate is Some(_) || channels is Some(_) || bits is Some(_) {
      return None
    }
  }
  Some({
    command,
    input: args[1],
    output,
    raw,
    json,
    start,
    end,
    rf64,
    max_buffer,
    sample_rate,
    channels,
    bits,
    channel_mask,
    block_size,
    effort,
    variable_block,
    non_audio,
    serial,
    vendor,
  })
}

///|
#borrow(bytes)
extern "C" fn stderr_bytes(bytes : Bytes, length : Int32) -> Int32 = "moonflac_stderr"

///|
fn diagnostic(message : String) -> Unit {
  let bytes = @utf8.encode("moonflac: " + message + "\n")
  ignore(stderr_bytes(bytes, bytes.length()))
}

///|
#borrow(path)
extern "C" fn open_input(path : Bytes, length : Int32) -> Int32 = "moonflac_open_input"

///|
#borrow(path)
extern "C" fn open_output(path : Bytes, length : Int32) -> Int32 = "moonflac_open_output"

///|
#borrow(bytes)
extern "C" fn read_chunk(bytes : FixedArray[Byte], length : Int32) -> Int32 = "moonflac_read"

///|
#borrow(bytes)
extern "C" fn write_chunk(bytes : Bytes, length : Int32) -> Int32 = "moonflac_write"

///|
extern "C" fn rewind_output() -> Int32 = "moonflac_rewind_output"

///|
extern "C" fn close_files() -> Int32 = "moonflac_close"

///|
suberror CliFailure {
  CliFailure(Int32, String)
}

///|
fn output_bytes(bytes : Bytes) -> Unit raise CliFailure {
  if write_chunk(bytes, bytes.length()) != 0 {
    raise CliFailure(4, "cannot write output")
  }
}

///|
fn metadata_json(metadata : @flac.Metadata) -> Json {
  let blocks : Array[Json] = metadata.blocks.map(block => {
    "type": block.kind.to_json(),
    "bytes": block.data.length().to_json(),
  })
  let pictures : Array[Json] = metadata.pictures.map(picture => {
    "type": picture.kind.to_json(),
    "media_type": picture.media_type.to_json(),
    "description": picture.description.to_json(),
    "width": picture.width.to_json(),
    "height": picture.height.to_json(),
    "depth": picture.depth.to_json(),
    "colors": picture.colors.to_json(),
    "bytes": picture.data.length().to_json(),
  })
  let comments : Json = match metadata.comments {
    None => Json::null()
    Some(value) =>
      { "vendor": value.vendor.to_json(), "entries": value.entries.to_json() }
  }
  {
    "blocks": blocks.to_json(),
    "comments": comments,
    "seek_points": metadata.seek_points.length().to_json(),
    "cuesheets": metadata.cuesheets.length().to_json(),
    "pictures": pictures.to_json(),
  }
}

///|
fn read_entire_input() -> Bytes raise CliFailure {
  let buffer : FixedArray[Byte] = FixedArray::make(65536, 0)
  let bytes : Array[Byte] = []
  while true {
    let count = read_chunk(buffer, buffer.length())
    if count < 0 {
      raise CliFailure(4, "cannot read input")
    }
    if count == 0 {
      break
    }
    for i = 0; i < count; i = i + 1 {
      bytes.push(buffer[i])
    }
  }
  Bytes::from_array(bytes)
}

///|
fn execute_ogg(options : Options) -> Unit raise {
  let path = @utf8.encode(options.input)
  if open_input(path, path.length()) != 0 {
    raise CliFailure(4, "cannot open native FLAC input")
  }
  let native = read_entire_input()
  let ogg = @flac.ogg_from_flac(
    native,
    serial=options.serial,
    vendor=options.vendor,
  )
  let destination = @utf8.encode(options.output)
  let status = open_output(destination, destination.length())
  if status == -2 {
    raise CliFailure(2, "input and output refer to the same file")
  }
  if status != 0 {
    raise CliFailure(4, "cannot open Ogg output")
  }
  output_bytes(ogg)
  println("Wrote \{ogg.length()} Ogg FLAC bytes to \{options.output}")
}

///|
fn execute_encode(options : Options) -> Unit raise {
  let path = @utf8.encode(options.input)
  if open_input(path, path.length()) != 0 {
    raise CliFailure(4, "cannot open PCM input")
  }
  let reader = if options.raw {
    @flac.PcmInput::raw({
      sample_rate: options.sample_rate.unwrap(),
      channels: options.channels.unwrap(),
      bits_per_sample: options.bits.unwrap(),
    })
  } else {
    @flac.PcmInput::wav()
  }
  let buffer : FixedArray[Byte] = FixedArray::make(65536, 0)
  let mut pending : Bytes = b""
  let mut encoder : @flac.Encoder? = None
  let mut pcm : Array[Int32] = []
  let mut pcm_at = 0
  let mut input_ended = false
  let mut pcm_done = false
  let mut encoder_ended = false
  while true {
    if encoder is Some(value) {
      match value.next() {
        @flac.EncodedBytes(bytes) => {
          output_bytes(bytes)
          continue
        }
        @flac.EncoderDone(summary) => {
          if rewind_output() != 0 {
            raise CliFailure(4, "cannot seek output to finalize FLAC header")
          }
          output_bytes(summary.final_header)
          println(
            "Encoded \{summary.total_samples} samples in \{summary.frames} frames to \{options.output}",
          )
          return
        }
        @flac.NeedPcm => {
          if pcm_at < pcm.length() {
            let accepted = value.push(pcm[pcm_at:].to_owned())
            if accepted <= 0 {
              raise CliFailure(3, "encoder made no progress accepting PCM")
            }
            pcm_at += accepted
            continue
          }
          if pcm_done {
            if encoder_ended {
              raise CliFailure(3, "encoder requested PCM after finish")
            }
            value.finish()
            encoder_ended = true
            continue
          }
        }
      }
    }
    match reader.next() {
      @flac.PcmFormatReady(format, mask) => {
        let layout = match options.channel_mask {
          Some(value) => Some(value)
          None => mask
        }
        let config = @flac.EncoderConfig::new(
          format,
          block_size=options.block_size,
          effort=options.effort,
          variable_block=options.variable_block,
          channel_mask?=layout,
          non_audio=options.non_audio,
          max_metadata_bytes=options.max_buffer,
        )
        encoder = Some(@flac.Encoder::new(config))
        let destination = @utf8.encode(options.output)
        let status = open_output(destination, destination.length())
        if status == -2 {
          raise CliFailure(2, "input and output refer to the same file")
        }
        if status != 0 {
          raise CliFailure(4, "cannot open encoded output")
        }
      }
      @flac.PcmSamples(samples) => {
        pcm = samples
        pcm_at = 0
      }
      @flac.PcmNeedInput => {
        if pending.is_empty() {
          if input_ended {
            raise CliFailure(3, "PCM reader requested data after end of input")
          }
          let count = read_chunk(buffer, buffer.length())
          if count < 0 {
            raise CliFailure(4, "cannot read PCM input")
          }
          if count == 0 {
            reader.finish()
            input_ended = true
            continue
          }
          pending = Bytes::makei(count, i => buffer[i])
        }
        let accepted = reader.push(pending)
        pending = pending[accepted:].to_owned()
      }
      @flac.PcmInputDone => pcm_done = true
    }
  }
}

///|
fn execute(options : Options) -> Unit raise {
  if options.command == "ogg" {
    execute_ogg(options)
    return
  }
  if options.command == "encode" {
    execute_encode(options)
    return
  }
  let path = @utf8.encode(options.input)
  if open_input(path, path.length()) != 0 {
    raise CliFailure(4, "cannot open input")
  }
  let decoder = @flac.Decoder::new(max_buffer_bytes=options.max_buffer)
  let buffer : FixedArray[Byte] = FixedArray::make(65536, 0)
  let mut pending : Bytes = b""
  let mut eof = false
  let mut metadata : @flac.Metadata? = None
  let mut samples = 0L
  let mut written = 0L
  let mut frames = 0
  let mut use_rf64 = options.rf64
  let mut done = false
  let mut integrity = @flac.Md5Unavailable
  let mut links = 0
  let mut md5_unavailable = false
  let mut first_read = true
  let mut is_ogg = false
  let mut output_mask : UInt32? = None
  let mut output_layout : UInt32? = None
  while !done {
    match decoder.next() {
      @flac.NeedInput => {
        if pending.is_empty() {
          if eof {
            raise CliFailure(3, "decoder requested data after end of input")
          }
          let count = read_chunk(buffer, buffer.length())
          if count < 0 {
            raise CliFailure(4, "cannot read input")
          }
          if count == 0 {
            eof = true
            decoder.finish()
            continue
          }
          pending = Bytes::makei(count, i => buffer[i])
          if first_read {
            is_ogg = count >= 4 && pending[:4].to_owned() == b"OggS"
            first_read = false
          }
        }
        let accepted = decoder.push(pending)
        pending = pending[accepted:].to_owned()
      }
      @flac.MetadataReady(value) => {
        links += 1
        if options.command == "decode" && !options.raw {
          let layout = value.effective_channel_mask()
          if output_layout is Some(previous) && previous != layout {
            raise CliFailure(
              3, "WAV export requires consistent channel layout across links",
            )
          }
          output_layout = Some(layout)
          if links == 1 {
            output_mask = value.channel_mask()
          }
        }
        if metadata is None {
          metadata = Some(value)
        }
        if options.command == "decode" && links == 1 {
          let destination = @utf8.encode(options.output)
          let status = open_output(destination, destination.length())
          if status == -2 {
            raise CliFailure(2, "input and output refer to the same file")
          }
          if status != 0 {
            raise CliFailure(4, "cannot open output")
          }
          if !options.raw {
            let info = value.info
            let expected = options.end.unwrap_or(info.total_samples)
            let sample_width = info.channels.to_int64() *
              ((info.bits_per_sample + 7) / 8).to_int64()
            use_rf64 = options.rf64 ||
              is_ogg ||
              info.total_samples == 0L ||
              expected > 4294967167L / sample_width
            output_bytes(
              @flac.wav_header(
                info,
                0L,
                channel_mask?=output_mask,
                rf64=use_rf64,
              ),
            )
          }
        }
      }
      @flac.AudioFrame(frame) => {
        if metadata is Some(value) &&
          (
            frame.sample_rate != value.info.sample_rate ||
            frame.bits_per_sample != value.info.bits_per_sample ||
            frame.channels.length() != value.info.channels
          ) {
          if options.command == "decode" && !options.raw {
            raise CliFailure(
              3, "PCM export requires consistent sample rate, channel count and bit depth",
            )
          }
        }
        let frame_end = samples + frame.block_size.to_int64()
        if options.command == "decode" {
          let left = if options.start > samples {
            options.start
          } else {
            samples
          }
          let right = match options.end {
            Some(end) if end < frame_end => end
            _ => frame_end
          }
          if left < right {
            let first = (left - samples).to_int()
            let last = (right - samples).to_int()
            let clipped : @flac.Frame = {
              ..frame,
              sample_number: left,
              block_size: last - first,
              channels: frame.channels.map(channel => {
                channel[first:last].to_owned()
              }),
            }
            output_bytes(@flac.frame_pcm(clipped, wav=!options.raw))
            written += right - left
          }
        }
        samples = frame_end
        frames += 1
      }
      @flac.Done(value) => {
        integrity = if md5_unavailable { @flac.Md5Unavailable } else { value }
        done = true
      }
      @flac.LinkEnd(value) =>
        if value == @flac.Md5Unavailable {
          md5_unavailable = true
        }
    }
  }
  let metadata = match metadata {
    Some(value) => value
    None => raise CliFailure(3, "missing STREAMINFO")
  }
  let info = metadata.info
  if options.command == "decode" {
    if options.start > samples || options.end.unwrap_or(samples) > samples {
      raise CliFailure(
        2,
        "sample range exceeds decoded stream (\{samples} samples)",
      )
    }
    if !options.raw {
      if written *
        info.channels.to_int64() *
        ((info.bits_per_sample + 7) / 8).to_int64() %
        2 !=
        0 {
        output_bytes(b"\x00")
      }
      if rewind_output() != 0 {
        raise CliFailure(4, "cannot seek output to finalize WAV header")
      }
      output_bytes(
        @flac.wav_header(
          info,
          written,
          channel_mask?=output_mask,
          rf64=use_rf64,
        ),
      )
    }
    println("Wrote \{written} samples to \{options.output}")
  } else if options.json {
    let details = metadata_json(metadata).stringify()
    println(
      "{\"sample_rate\":\{info.sample_rate},\"channels\":\{info.channels},\"bits_per_sample\":\{info.bits_per_sample},\"samples\":\{samples},\"frames\":\{frames},\"links\":\{links},\"peak_compressed_buffer\":\{decoder.peak_buffered_bytes()},\"integrity\":\"\{integrity}\",\"metadata\":\{details}}",
    )
  } else {
    println(
      "\{info.sample_rate} Hz, \{info.channels} channels, \{info.bits_per_sample}-bit, \{samples} samples, \{frames} frames",
    )
    println(
      "Integrity: \{integrity}; peak compressed buffer: \{decoder.peak_buffered_bytes()} bytes",
    )
    if options.command == "info" {
      println(metadata_json(metadata).stringify(indent=2))
    }
  }
}

///|
fn run(options : Options) -> Int32 {
  let status = try {
    execute(options)
    0
  } catch {
    CliFailure(code, message) => {
      diagnostic(message)
      code
    }
    error => {
      diagnostic("\{error}")
      3
    }
  }
  let closed = close_files()
  if closed != 0 && status == 0 {
    diagnostic("cannot close files")
    return 4
  }
  status
}

///|
fn main {
  let process_args = @env.args()
  let args = if process_args.is_empty() {
    []
  } else {
    process_args[1:].to_owned()
  }
  let status = if args == ["--help"] || args == ["-h"] {
    println(USAGE)
    0
  } else {
    match parse(args) {
      Some(options) => run(options)
      None => {
        diagnostic(USAGE)
        2
      }
    }
  }
  @sys.exit(status)
}

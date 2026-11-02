///|
fn seektable_test_frame(
  number : Int32,
  variable : Bool,
  value : Int32,
) -> Bytes {
  let bits = []
  frame_test_bits(bits, 0L, 8)
  frame_test_bits(bits, value.to_int64(), 16)
  let bytes = frame_test_pack(bits, 0).to_array()
  bytes[1] = if variable { 249 } else { 248 }
  bytes[4] = number.to_byte()
  bytes[6] = frame_crc(Bytes::from_array(bytes), 0, 6, 8).to_byte()
  let crc = frame_crc(Bytes::from_array(bytes), 0, bytes.length() - 2, 16)
  bytes[bytes.length() - 2] = (crc >> 8).to_byte()
  bytes[bytes.length() - 1] = crc.to_byte()
  Bytes::from_array(bytes)
}

///|
fn seektable_test_file(
  variable : Bool,
  wrong_offset : Bool,
  wrong_sample : Bool,
) -> Bytes {
  let frames = [
    seektable_test_frame(0, variable, 11),
    seektable_test_frame(if variable { 16 } else { 1 }, variable, 22),
    seektable_test_frame(if variable { 32 } else { 2 }, variable, 33),
  ]
  let point : Array[Byte] = []
  let sample = if wrong_sample { 15UL } else { 16UL }
  let offset = (frames[0].length() + (if wrong_offset { 1 } else { 0 })).to_uint64()
  for value in [sample, offset] {
    for i = 7; i >= 0; i = i - 1 {
      point.push((value >> (i * 8)).to_byte())
    }
  }
  point.push(0)
  point.push(16)
  let data = meta_test_stream(metadata_test_block(131, point)).to_array()
  for frame in frames {
    for b in frame {
      data.push(b)
    }
  }
  Bytes::from_array(data)
}

///|
test "SEEKTABLE direct fixed and variable precise crop" {
  for variable in [false, true] {
    let input = seektable_test_file(variable, false, false)
    let selected = decode_seektable_range(input, 19L, 39L)
    assert_true(selected.integrity == FrameCrcOnly)
    assert_eq(selected.frames.length(), 2)
    assert_eq(selected.frames[0].sample_number, 19L)
    assert_eq(selected.frames[0].channels[0], Array::make(13, 22))
    assert_eq(selected.frames[1].channels[0], Array::make(7, 33))
    let full = decode_range(input, 19L, 39L)
    assert_eq(
      full.frames.map(f => f.channels),
      selected.frames.map(f => f.channels),
    )
    // An earlier damaged audio frame is outside this API's integrity scope.
    let broken = input.to_array()
    broken[64] = 0
    let result = decode_seektable_range(Bytes::from_array(broken), 19L, 39L)
    assert_eq(result.frames[0].channels[0][0], 22)
  }
}

///|
test "SEEKTABLE invalid selected point never falls back" {
  for flags in [(true, false), (false, true)] {
    let (offset, sample) = flags
    let invalid = try {
      let _ = decode_seektable_range(
        seektable_test_file(false, offset, sample),
        19L,
        39L,
      )
      false
    } catch {
      Invalid(_, _) => true
      _ => false
    }
    assert_true(invalid)
  }
  let empty = decode_seektable_range(
    seektable_test_file(false, false, false),
    20L,
    20L,
  )
  assert_eq(empty.frames.length(), 0)
  let bad = try {
    let _ = decode_seektable_range(
      seektable_test_file(false, false, false),
      40L,
      49L,
    )
    false
  } catch {
    Invalid(_, _) => true
    _ => false
  }
  assert_true(bad)
}

///|
test "SEEKTABLE start before first point and selected CRC failure" {
  let file = seektable_test_file(false, false, false)
  let early = decode_seektable_range(file, 3L, 5L)
  assert_eq(early.frames[0].channels[0], [11, 11])
  let bytes = file.to_array()
  let (_, audio_start) = parse_metadata(file)
  let second = audio_start + seektable_test_frame(0, false, 11).length()
  bytes[second + 8] = (bytes[second + 8].to_int() ^ 1).to_byte()
  let invalid = try {
    let _ = decode_seektable_range(Bytes::from_array(bytes), 19L, 39L)
    false
  } catch {
    Invalid(_, _) => true
    _ => false
  }
  assert_true(invalid)
}

///|
test "SEEKTABLE range retains legal frame property changes" {
  let original = seektable_test_file(true, false, false)
  let (_, audio_start) = parse_metadata(original)
  let second = audio_start + seektable_test_frame(0, true, 11).length()
  let bytes = original.to_array()
  bytes[second + 2] = 106 // Explicit 48 kHz; STREAMINFO and surrounding frames 44.1 kHz.
  bytes[second + 6] = frame_crc(Bytes::from_array(bytes), second, second + 6, 8).to_byte()
  let frame_end = second + seektable_test_frame(16, true, 22).length()
  let crc = frame_crc(Bytes::from_array(bytes), second, frame_end - 2, 16)
  bytes[frame_end - 2] = (crc >> 8).to_byte()
  bytes[frame_end - 1] = crc.to_byte()
  let selected = decode_seektable_range(Bytes::from_array(bytes), 19L, 39L)
  assert_eq(selected.frames[0].sample_rate, 48000)
  assert_eq(selected.frames[1].sample_rate, 44100)
  assert_eq(selected.frames[0].channels[0], Array::make(13, 22))
}

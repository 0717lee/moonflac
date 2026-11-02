///|
fn wav_test_info(bits : Int32, channels : Int32) -> StreamInfo {
  {
    min_block_size: 16,
    max_block_size: 4096,
    min_frame_size: 0,
    max_frame_size: 0,
    sample_rate: 48000,
    channels,
    bits_per_sample: bits,
    total_samples: 0L,
    md5: Bytes::makei(16, _ => 0),
  }
}

///|
fn wav_test_frame(bits : Int32, channels : Array[Array[Int32]]) -> Frame {
  {
    sample_number: 0L,
    number: 0L,
    variable_block: false,
    sample_rate: 48000,
    bits_per_sample: bits,
    channels,
    block_size: channels[0].length(),
    byte_offset: 0L,
    byte_length: 0,
  }
}

///|
fn wav_test_le(bytes : Bytes, start : Int32, size : Int32) -> Int64 {
  let mut value = 0L
  for i in 0..<size {
    value = value | (bytes[start + i].to_int().to_int64() << (i * 8))
  }
  value
}

///|
test "PCM raw sign extension and WAV valid-bit alignment" {
  let four = wav_test_frame(4, [[-8, -1, 0, 7]])
  assert_eq(frame_pcm(four), b"\xf8\xff\x00\x07")
  assert_eq(frame_pcm(four, wav=true), b"\x00\x70\x80\xf0")
  let twenty = wav_test_frame(20, [[-524288, 524287], [-1, 0]])
  assert_eq(
    frame_pcm(twenty),
    b"\x00\x00\xf8\xff\xff\xff\xff\xff\x07\x00\x00\x00",
  )
  assert_eq(
    frame_pcm(twenty, wav=true),
    b"\x00\x00\x80\xf0\xff\xff\xf0\xff\x7f\x00\x00\x00",
  )
  assert_eq(
    frame_pcm(wav_test_frame(32, [[-2147483648, 2147483647]])),
    b"\x00\x00\x00\x80\xff\xff\xff\x7f",
  )
}

///|
test "RIFF extensible and RF64 headers including odd padding" {
  let small = wav_header(wav_test_info(8, 1), 3L)
  assert_eq(small.length(), 44)
  assert_eq(wav_test_le(small, 4, 4), 40L)
  assert_eq(wav_test_le(small, 40, 4), 3L)
  let ext = wav_header(wav_test_info(20, 8), 10L)
  assert_eq(ext.length(), 68)
  assert_eq(wav_test_le(ext, 20, 2), 65534L)
  assert_eq(wav_test_le(ext, 34, 2), 24L)
  assert_eq(wav_test_le(ext, 38, 2), 20L)
  assert_eq(wav_test_le(ext, 40, 4), 1599L)
  let large = wav_header(wav_test_info(32, 8), 134217728L)
  assert_eq(large.length(), 104)
  assert_eq(wav_test_le(large, 4, 4), 4294967295L)
  assert_eq(wav_test_le(large, 20, 8), 4294967392L)
  assert_eq(wav_test_le(large, 28, 8), 4294967296L)
  assert_eq(wav_test_le(large, 36, 8), 134217728L)
  let forced = wav_header(wav_test_info(16, 2), 1L, rf64=true)
  assert_eq(forced.length(), 80)
  assert_eq(wav_test_le(forced, 20, 8), 76L)
}

///|
test "WAV rejects arithmetic overflow" {
  let rejected = try {
    ignore(wav_header(wav_test_info(32, 8), 9223372036854775807L))
    false
  } catch {
    Limit(_) => true
    _ => false
  }
  assert_true(rejected)
}

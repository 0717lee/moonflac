///|
fn encoder_test_seek_block(
  sample : Int64,
  offset : Int64,
  count : Int32,
) -> MetadataBlock {
  let bytes = @buffer.Buffer()
  bytes.write_int64_be(sample)
  bytes.write_int64_be(offset)
  bytes.write_byte((count >> 8).to_byte())
  bytes.write_byte(count.to_byte())
  { kind: 3, data: bytes.to_bytes(), }
}

///|
test "encoder seek points must match actual frame offsets and sample boundaries" {
  let config = EncoderConfig::new(
    { sample_rate: 48000, channels: 1, bits_per_sample: 16, },
    block_size=16,
    effort=1,
  )
  let pcm = Array::makei(37, i => i * 3 - 51)
  let initial = encode_pcm(pcm, config)
  let index = build_index(initial)
  let offset = index.frames[0].bytes.to_int64()
  let with_seek = {
    ..config,
    metadata: [encoder_test_seek_block(16L, offset, 16)],
  }
  let encoded = encode_pcm(pcm, with_seek)
  let audio = decode_seektable_range(encoded, 17L, 34L)
  let result : Array[Int32] = []
  for frame in audio.frames {
    for value in frame.channels[0] {
      result.push(value)
    }
  }
  assert_eq(result, pcm[17:34].to_owned())
  for
    block in [
      encoder_test_seek_block(16L, offset + 1L, 16),
      encoder_test_seek_block(17L, offset, 16),
      encoder_test_seek_block(16L, offset, 15),
      encoder_test_seek_block(48L, offset, 16),
    ] {
    let rejected = try {
      ignore(encode_pcm(pcm, { ..config, metadata: [block], }))
      false
    } catch {
      Invalid(_, _) => true
      _ => false
    }
    assert_true(rejected)
  }
  let placeholder = encoder_test_seek_block(-1L, 0L, 0)
  let preserved = encode_pcm(pcm, { ..config, metadata: [placeholder], })
  assert_eq(decode(preserved).frames.length(), 3)
}

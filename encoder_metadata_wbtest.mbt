///|
fn encmeta_test_config() -> EncoderConfig {
  {
    format: { sample_rate: 48000, channels: 6, bits_per_sample: 24, },
    block_size: 4096,
    variable_block: false,
    effort: 5,
    channel_mask: None,
    metadata: [],
    non_audio: false,
    max_metadata_bytes: 67108864,
  }
}

///|
test "encoder STREAMINFO unfinished finalized and 36-bit boundary" {
  let config = encmeta_test_config()
  let unfinished = encoder_header(config, 0L, Bytes::make(16, 0), 0, 0)
  let (metadata, end) = parse_metadata(unfinished)
  assert_eq(end, 42)
  assert_eq(metadata.info.channels, 6)
  assert_eq(metadata.info.sample_rate, 48000)
  assert_eq(metadata.info.bits_per_sample, 24)
  assert_eq(metadata.info.min_block_size, 4096)
  assert_eq(metadata.info.max_block_size, 4096)
  let digest = Bytes::makei(16, i => i.to_byte())
  let finalized = encoder_header(
    { ..config, variable_block: true, },
    0xfffffffffL,
    digest,
    12,
    6000,
  )
  let (metadata, _) = parse_metadata(finalized)
  assert_eq(metadata.info.min_block_size, 16)
  assert_eq(metadata.info.total_samples, 0xfffffffffL)
  assert_eq(metadata.info.md5, digest)
  assert_eq(metadata.info.min_frame_size, 12)
  assert_eq(metadata.info.max_frame_size, 6000)
  for count in [-1L, 0x1000000000L] {
    let rejected = try {
      let _ = encoder_header(config, count, digest, 0, 0)
      false
    } catch {
      Invalid(_, _) => true
      _ => false
    }
    assert_true(rejected)
  }
}

///|
test "encoder metadata preserves all block types and unknown payloads" {
  let cue : Array[Byte] = Array::make(395, 0)
  cue.push(1)
  for _i = 0; _i < 8; _i = _i + 1 {
    cue.push(0)
  }
  cue.push(255)
  for _i = 0; _i < 27; _i = _i + 1 {
    cue.push(0)
  }
  let picture : Array[Byte] = [0, 0, 0, 3, 0, 0, 0, 3, 45, 45, 62, 0, 0, 0, 0]
  for _i = 0; _i < 16; _i = _i + 1 {
    picture.push(0)
  }
  for b in [0, 0, 0, 3, 97, 98, 99] {
    picture.push(b.to_byte())
  }
  let blocks : Array[MetadataBlock] = [
    { kind: 1, data: b"\x00\x00", },
    { kind: 2, data: b"TESTpayload", },
    { kind: 3, data: b"", },
    {
      kind: 4,
      data: encmeta_comment(
        { vendor: "厂商🎵", entries: ["TITLE=曲目"], },
        1000,
      ),
    },
    { kind: 5, data: Bytes::from_array(cue), },
    { kind: 6, data: Bytes::from_array(picture), },
    { kind: 126, data: b"unknown", },
  ]
  let config = { ..encmeta_test_config(), metadata: blocks, }
  let header = encoder_header(config, 0L, Bytes::make(16, 0), 0, 0)
  let (metadata, end) = parse_metadata(header)
  assert_eq(end, header.length())
  assert_eq(metadata.blocks.length(), 8)
  for i = 0; i < blocks.length(); i = i + 1 {
    assert_eq(metadata.blocks[i + 1].data, blocks[i].data)
  }
  assert_eq(metadata.comments.unwrap().vendor, "厂商🎵")
  let final_header = encoder_header(config, 1234L, Bytes::make(16, 2), 10, 20)
  assert_eq(final_header[42:], header[42:])
}

///|
test "encoder channel mask merges without losing tags or vendor" {
  let comment = encmeta_comment(
    { vendor: "external", entries: ["TITLE=hello", "ARTIST=音乐"], },
    1000,
  )
  let config = {
    ..encmeta_test_config(),
    channel_mask: Some(0x60fU),
    metadata: [{ kind: 4, data: comment, }],
  }
  let (metadata, _) = parse_metadata(
    encoder_header(config, 0L, Bytes::make(16, 0), 0, 0),
  )
  assert_eq(metadata.channel_mask(), Some(0x60fU))
  assert_eq(metadata.comments.unwrap().vendor, "external")
  assert_eq(metadata.comments.unwrap().values("artist"), ["音乐"])
  for mask in [0U, 3U] {
    let config = { ..encmeta_test_config(), channel_mask: Some(mask), }
    let (metadata, _) = parse_metadata(
      encoder_header(config, 0L, Bytes::make(16, 0), 0, 0),
    )
    assert_eq(metadata.channel_mask(), Some(mask))
  }
  let original = encmeta_comment(
    { vendor: "keep", entries: ["waveformatextensible_channel_mask=0X0060F"], },
    1000,
  )
  let config = { ..config, metadata: [{ kind: 4, data: original, }], }
  let (metadata, _) = parse_metadata(
    encoder_header(config, 0L, Bytes::make(16, 0), 0, 0),
  )
  assert_eq(metadata.blocks[1].data, original)
  let conflict = try {
    let _ = encoder_header(
      { ..config, channel_mask: Some(0U), },
      0L,
      Bytes::make(16, 0),
      0,
      0,
    )
    false
  } catch {
    Invalid(_, _) => true
    _ => false
  }
  assert_true(conflict)
}

///|
test "encoder metadata rejects illegal supplied blocks and limits" {
  let config = encmeta_test_config()
  let comment = encmeta_comment({ vendor: "x", entries: [], }, 1000)
  for
    blocks in [
      [{ kind: 0, data: Bytes::make(34, 0), }],
      [{ kind: 127, data: b"", }],
      [{ kind: 1, data: b"\x01", }],
      [{ kind: 2, data: b"abc", }],
      [{ kind: 4, data: comment, }, { kind: 4, data: comment, }],
      [{ kind: 3, data: b"", }, { kind: 3, data: b"", }],
    ] {
    let invalid = try {
      let _ = encoder_header(
        { ..config, metadata: blocks, },
        0L,
        Bytes::make(16, 0),
        0,
        0,
      )
      false
    } catch {
      Invalid(_, _) => true
      _ => false
    }
    assert_true(invalid)
  }
  let limited = try {
    let _ = encoder_header(
      { ..config, max_metadata_bytes: 41, },
      0L,
      Bytes::make(16, 0),
      0,
      0,
    )
    false
  } catch {
    Limit(_) => true
    _ => false
  }
  assert_true(limited)
  let md5_bad = try {
    let _ = encoder_header(config, 0L, b"short", 0, 0)
    false
  } catch {
    Invalid(_, _) => true
    _ => false
  }
  assert_true(md5_bad)
  let zero_rate = { ..config, format: { ..config.format, sample_rate: 0, }, }
  let invalid = try {
    let _ = encoder_header(zero_rate, 0L, Bytes::make(16, 0), 0, 0)
    false
  } catch {
    Invalid(_, _) => true
    _ => false
  }
  assert_true(invalid)
  let (metadata, _) = parse_metadata(
    encoder_header(
      { ..zero_rate, non_audio: true, },
      0L,
      Bytes::make(16, 0),
      0,
      0,
    ),
  )
  assert_eq(metadata.info.sample_rate, 0)
}

///|
test "encoder metadata field limits and injected tag resource cap" {
  let config = encmeta_test_config()
  let oversized : MetadataBlock = { kind: 1, data: Bytes::make(16777216, 0), }
  let limited = try {
    let _ = encoder_header(
      { ..config, metadata: [oversized], },
      0L,
      Bytes::make(16, 0),
      0,
      0,
    )
    false
  } catch {
    Limit(_) => true
    _ => false
  }
  assert_true(limited)
  let limited = try {
    let _ = encoder_header(
      { ..config, channel_mask: Some(0U), max_metadata_bytes: 42, },
      0L,
      Bytes::make(16, 0),
      0,
      0,
    )
    false
  } catch {
    Limit(_) => true
    _ => false
  }
  assert_true(limited)
  for sizes in [(-1, 0), (0, 16777216), (20, 10)] {
    let (minimum, maximum) = sizes
    let invalid = try {
      let _ = encoder_header(config, 0L, Bytes::make(16, 0), minimum, maximum)
      false
    } catch {
      Invalid(_, _) => true
      _ => false
    }
    assert_true(invalid)
  }
}

///|
fn layout_test_metadata(
  channels : Int32,
  entries : Array[String],
) -> Metadata raise FlacError {
  let (metadata, _) = parse_metadata(meta_test_stream([129, 0, 0, 0]))
  {
    ..metadata,
    info: { ..metadata.info, channels, },
    comments: Some({ vendor: "layout test", entries, }),
  }
}

///|
test "channel mask mixed case padded zeros zero and partial speakers" {
  let surround = layout_test_metadata(6, [
    "WaveFormatExtensible_Channel_Mask=0X0000060f",
  ])
  assert_eq(surround.channel_mask(), Some(0x60fU))
  assert_eq(surround.effective_channel_mask(), 0x60fU)
  let zero = layout_test_metadata(4, ["WAVEFORMATEXTENSIBLE_CHANNEL_MASK=0x0"])
  assert_eq(zero.channel_mask(), Some(0U))
  assert_eq(zero.effective_channel_mask(), 0U)
  let partial = layout_test_metadata(4, [
    "waveformatextensible_channel_mask=0x3",
  ])
  assert_eq(partial.effective_channel_mask(), 3U)
  let padded = layout_test_metadata(4, [
    "WAVEFORMATEXTENSIBLE_CHANNEL_MASK=0x0000000000000000000000000003",
  ])
  assert_eq(padded.channel_mask(), Some(3U))
}

///|
test "channel mask absent applies FLAC defaults and equivalent duplicates agree" {
  let defaults : Array[UInt32] = [
    0x4U, 0x3U, 0x7U, 0x33U, 0x37U, 0x3fU, 0x70fU, 0x63fU,
  ]
  for channels = 1; channels <= 8; channels = channels + 1 {
    let metadata = layout_test_metadata(channels, ["TITLE=music"])
    assert_eq(metadata.channel_mask(), None)
    assert_eq(metadata.effective_channel_mask(), defaults[channels - 1])
    let without_comments = { ..metadata, comments: None, }
    assert_eq(without_comments.effective_channel_mask(), defaults[channels - 1])
  }
  let repeated = layout_test_metadata(6, [
    "WAVEFORMATEXTENSIBLE_CHANNEL_MASK=0x060f", "waveformatextensible_channel_mask=0X60F",
  ])
  assert_eq(repeated.channel_mask(), Some(0x60fU))
}

///|
test "channel mask invalid syntax overflow and conflicts produce diagnostics" {
  for
    value in [
      "", "0x", "3", "0xg", "0x 3", " 0x3", "0x3 ", "0x-1", "0x100000000", "0xFFFFFFFFF",
    ] {
    let metadata = layout_test_metadata(2, [
      "WAVEFORMATEXTENSIBLE_CHANNEL_MASK=" + value,
    ])
    let rejected = try {
      let _ = metadata.channel_mask()
      false
    } catch {
      Invalid(_, _) => true
      _ => false
    }
    assert_true(rejected)
  }
  let max = layout_test_metadata(8, [
    "WAVEFORMATEXTENSIBLE_CHANNEL_MASK=0xffffffff",
  ])
  assert_eq(max.channel_mask(), Some(0xffffffffU))
  let conflicting = layout_test_metadata(2, [
    "WAVEFORMATEXTENSIBLE_CHANNEL_MASK=0x3", "waveformatextensible_channel_mask=0x0",
  ])
  let rejected = try {
    let _ = conflicting.channel_mask()
    false
  } catch {
    Invalid(_, _) => true
    _ => false
  }
  assert_true(rejected)
}

///|
test "WAV header preserves nondefault and explicit zero channel masks" {
  for mask in [0x60fU, 0U, 3U] {
    let metadata = layout_test_metadata(6, [
      "WAVEFORMATEXTENSIBLE_CHANNEL_MASK=0x0",
    ])
    let header = wav_header(metadata.info, 16L, channel_mask=mask)
    let actual = header[40].to_uint() |
      (header[41].to_uint() << 8) |
      (header[42].to_uint() << 16) |
      (header[43].to_uint() << 24)
    assert_eq(actual, mask)
  }
}

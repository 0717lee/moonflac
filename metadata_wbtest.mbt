///|
fn meta_test_stream(extra : Array[Byte]) -> Bytes {
  let p : Array[Byte] = [
    102, 76, 97, 67, 0, 0, 0, 34, 0, 16, 0, 16, 0, 0, 0, 0, 0, 0, 10, 196, 64, 240,
    0, 0, 0, 0,
  ]
  for _i = 0; _i < 16; _i = _i + 1 {
    p.push(0)
  }
  for b in extra {
    p.push(b)
  }
  Bytes::from_array(p)
}

///|
test "metadata structured comments unknown and limits" {
  let bytes = meta_test_stream([
    4, 0, 0, 17, 1, 0, 0, 0, 120, 1, 0, 0, 0, 4, 0, 0, 0, 65, 61, 195, 169, 135,
    0, 0, 2, 22, 33,
  ])
  let (meta, end) = parse_metadata(bytes)
  assert_eq(end, bytes.length())
  assert_eq(meta.info.sample_rate, 44100)
  assert_eq(meta.blocks.length(), 3)
  assert_eq(meta.blocks[2].kind, 7)
  assert_eq(meta.comments.unwrap().entries[0], "A=é")
  let limited = try {
    let _ = parse_metadata(bytes, max_metadata_bytes=42)
    false
  } catch {
    Limit(_) => true
    _ => false
  }
  assert_true(limited)
  for n = 0; n < bytes.length(); n = n + 1 {
    let short = Bytes::from_array(Array::makei(n, i => bytes[i]))
    let incomplete = try {
      let _ = parse_metadata(short)
      false
    } catch {
      NeedMore => true
      _ => false
    }
    assert_true(incomplete)
  }
}

///|
test "metadata seek placeholders and malformed comments" {
  let extra : Array[Byte] = [131, 0, 0, 18]
  for _i = 0; _i < 18; _i = _i + 1 {
    extra.push(0)
  }
  let (m, _) = parse_metadata(meta_test_stream(extra))
  assert_eq(m.seek_points[0].sample, 0UL)
  let bad = meta_test_stream([132, 0, 0, 8, 255, 255, 255, 255, 0, 0, 0, 0])
  let invalid = try {
    let _ = parse_metadata(bad)
    false
  } catch {
    Invalid(_, _) => true
    _ => false
  }
  assert_true(invalid)
}

///|
fn metadata_test_block(kind : Byte, data : Array[Byte]) -> Array[Byte] {
  let n = data.length()
  let b = [kind, (n >> 16).to_byte(), (n >> 8).to_byte(), n.to_byte()]
  for v in data {
    b.push(v)
  }
  b
}

///|
test "CUESHEET PICTURE APPLICATION PADDING typed and raw" {
  let cue : Array[Byte] = Array::make(395, 0)
  cue.push(1)
  for _i = 0; _i < 8; _i = _i + 1 {
    cue.push(0)
  }
  cue.push(255)
  for _i = 0; _i < 27; _i = _i + 1 {
    cue.push(0)
  }
  let blocks = metadata_test_block(5, cue)
  for b in metadata_test_block(2, [65, 66, 67, 68, 99]) {
    blocks.push(b)
  }
  for b in metadata_test_block(1, [0, 0]) {
    blocks.push(b)
  }
  let picture : Array[Byte] = [0, 0, 0, 3, 0, 0, 0, 3, 45, 45, 62, 0, 0, 0, 0]
  for _i = 0; _i < 16; _i = _i + 1 {
    picture.push(0)
  }
  for b in [0, 0, 0, 3, 97, 98, 99] {
    picture.push(b.to_byte())
  }
  for b in metadata_test_block(134, picture) {
    blocks.push(b)
  }
  let (m, _) = parse_metadata(meta_test_stream(blocks))
  assert_eq(m.cuesheet.unwrap().tracks[0].number, 255)
  assert_eq(m.pictures[0].media_type, "-->")
  assert_eq(m.pictures[0].data.length(), 3)
  assert_eq(m.blocks[2].data[4], 99)
  let bad = try {
    let _ = parse_metadata(meta_test_stream([129, 0, 0, 1, 1]))
    false
  } catch {
    Invalid(_, _) => true
    _ => false
  }
  assert_true(bad)
}

///|
test "Vorbis tag names are case insensitive and values preserve equals" {
  let tags : VorbisComment = {
    vendor: "test",
    entries: ["TITLE=A=B", "Title=C", "~name=x"],
  }
  assert_eq(tags.values("title"), ["A=B", "C"])
  assert_eq(tags.values("~NAME"), ["x"])
}

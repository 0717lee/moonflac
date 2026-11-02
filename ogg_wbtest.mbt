///|
fn ogg_test_page(
  packet : Array[Byte],
  seq : UInt32,
  flags : Byte,
  granule : UInt64,
) -> Bytes {
  let p : Array[Byte] = [79, 103, 103, 83, 0, flags]
  for i = 0; i < 8; i = i + 1 {
    p.push((granule >> (i * 8)).to_byte())
  }
  p.push(1)
  p.push(0)
  p.push(0)
  p.push(0)
  for i = 0; i < 4; i = i + 1 {
    p.push((seq >> (i * 8)).to_byte())
  }
  for _i = 0; _i < 4; _i = _i + 1 {
    p.push(0)
  }
  p.push(1)
  p.push(packet.length().to_byte())
  for b in packet {
    p.push(b)
  }
  let crc = ogg_crc(p)
  for i = 0; i < 4; i = i + 1 {
    p[22 + i] = (crc >> (i * 8)).to_byte()
  }
  Bytes::from_array(p)
}

///|
fn ogg_test_bos() -> Bytes {
  let p : Array[Byte] = [127, 70, 76, 65, 67, 1, 0, 0, 1]
  let native = meta_test_stream([])
  for b in native {
    p.push(b)
  }
  ogg_test_page(p, 0U, 2, 0UL)
}

///|
test "Ogg every byte split crc sequence eos chaining" {
  let pages = [
    ogg_test_bos(),
    ogg_test_page([132, 0, 0, 8, 0, 0, 0, 0, 0, 0, 0, 0], 1U, 0, 0UL),
    ogg_test_page(ogg_test_audio(), 2U, 4, 16UL),
  ]
  let d = OggDemux::new()
  let out = []
  for _chain = 0; _chain < 2; _chain = _chain + 1 {
    for page in pages {
      for b in page {
        for packet in d.push(Bytes::from_array([b])) {
          out.push(packet)
        }
      }
    }
  }
  d.finish()
  assert_eq(out.length(), 6)
  assert_eq(out[0].length(), 42)
  assert_eq(d.buffered_bytes(), 0)
  assert_true(d.peak_buffered_bytes() < 200)
  let bad = Array::makei(pages[0].length(), i => pages[0][i])
  bad[40] = 99
  let invalid = try {
    let _ = OggDemux::new().push(Bytes::from_array(bad))
    false
  } catch {
    Invalid(_, _) => true
    _ => false
  }
  assert_true(invalid)
  let truncated = try {
    let d = OggDemux::new()
    let _ = d.push(pages[0])
    d.finish()
    false
  } catch {
    Invalid(_, _) => true
    _ => false
  }
  assert_true(truncated)
}

///|
test "Ogg packet continuation limits and wrong sequence" {
  let head = ogg_test_bos()
  let padding = metadata_test_block(129, Array::make(296, 0))
  let start = ogg_test_page(Array::makei(255, i => padding[i]), 1U, 0, 0UL)
  let end = ogg_test_page(Array::makei(45, i => padding[i + 255]), 2U, 1, 0UL)
  let d = OggDemux::new()
  let _ = d.push(head)
  assert_eq(d.push(start).length(), 0)
  let packets = d.push(end)
  assert_eq(packets[0].length(), 300)
  let _ = d.push(ogg_test_page(ogg_test_audio(), 3U, 4, 16UL))
  d.finish()
  let limited = try {
    let d = OggDemux::new(max_packet_bytes=255)
    let _ = d.push(head)
    let _ = d.push(start)
    let _ = d.push(end)
    false
  } catch {
    Limit(_) => true
    _ => false
  }
  assert_true(limited)
  let bad = try {
    let d = OggDemux::new()
    let _ = d.push(head)
    let _ = d.push(ogg_test_page([132, 0, 0, 0], 2U, 0, 0UL))
    false
  } catch {
    Invalid(_, _) => true
    _ => false
  }
  assert_true(bad)
}

///|
fn ogg_test_audio() -> Array[Byte] {
  let bits : Array[Int32] = []
  frame_test_bits(bits, 0L, 8)
  frame_test_bits(bits, 0L, 16)
  frame_test_pack(bits, 0).to_array()
}

///|
test "Ogg rejects combined frames and inconsistent granules" {
  let combined = ogg_test_audio()
  for b in ogg_test_audio() {
    combined.push(b)
  }
  let invalid = try {
    let d = OggDemux::new()
    let _ = d.push(ogg_test_bos())
    let _ = d.push(
      ogg_test_page([132, 0, 0, 8, 0, 0, 0, 0, 0, 0, 0, 0], 1U, 0, 0UL),
    )
    let _ = d.push(ogg_test_page(combined, 2U, 4, 32UL))
    false
  } catch {
    Invalid(_, _) => true
    _ => false
  }
  assert_true(invalid)
  let invalid = try {
    let d = OggDemux::new()
    let _ = d.push(ogg_test_bos())
    let _ = d.push(
      ogg_test_page([132, 0, 0, 8, 0, 0, 0, 0, 0, 0, 0, 0], 1U, 0, 0UL),
    )
    let _ = d.push(ogg_test_page(ogg_test_audio(), 2U, 0, 16UL))
    let _ = d.push(ogg_test_page(ogg_test_audio(), 3U, 4, 31UL))
    false
  } catch {
    Invalid(_, _) => true
    _ => false
  }
  assert_true(invalid)
}

///|
test "Ogg mapping declared header count excludes initial packet" {
  let first = ogg_test_bos().to_array()
  first[36] = 3
  let crc = ogg_crc(first)
  for i = 0; i < 4; i = i + 1 {
    first[22 + i] = (crc >> (8 * i)).to_byte()
  }
  let invalid = try {
    let d = OggDemux::new()
    let _ = d.push(Bytes::from_array(first))
    let _ = d.push(
      ogg_test_page([132, 0, 0, 8, 0, 0, 0, 0, 0, 0, 0, 0], 1U, 0, 0UL),
    )
    false
  } catch {
    Invalid(_, _) => true
    _ => false
  }
  assert_true(invalid)
}

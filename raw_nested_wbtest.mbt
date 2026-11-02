///|
/// A complete constant frame appears as ordinary PCM inside a verbatim frame.
/// The earlier candidate must win even when only the inner frame is available.
fn raw_nested_fixture() -> Bytes {
  let inner = raw_test_frame(123, 10, 4)
  let outer : Array[Byte] = [0xff, 0xf8, 0x6a, 0x08, 0, 15]
  outer.push(
    frame_crc(Bytes::from_array(outer), 0, outer.length(), 8).to_byte(),
  )
  outer.push(2)
  for byte in inner {
    outer.push(byte)
  }
  for _ in inner.length()..<32 {
    outer.push(0)
  }
  let crc = frame_crc(Bytes::from_array(outer), 0, outer.length(), 16)
  outer.push((crc >> 8).to_byte())
  outer.push(crc.to_byte())
  Bytes::from_array(outer)
}

///|
test "raw nested valid frame stays PCM while earlier candidate is incomplete" {
  let bytes = raw_nested_fixture()
  assert_eq(bytes.length(), 42)
  let decoder = RawDecoder::new()
  ignore(decoder.push(bytes[:20].to_owned()))
  assert_true(decoder.next() is RawNeedInput)
  ignore(decoder.push(bytes[20:].to_owned()))
  decoder.finish()
  match decoder.next() {
    RawFrame(frame) => {
      assert_eq(frame.channels[0][0], -8)
      assert_eq(frame.block_size, 16)
    }
    _ => fail("outer frame was lost")
  }
  assert_true(decoder.next() is RawDone)
}

///|
test "raw nested candidate never becomes a fake frame at truncated EOF" {
  let bytes = raw_nested_fixture()
  for end in 1..<bytes.length() {
    let decoder = RawDecoder::new()
    ignore(decoder.push(bytes[:end].to_owned()))
    assert_true(decoder.next() is RawNeedInput)
    decoder.finish()
    let truncated = try {
      ignore(decoder.next())
      false
    } catch {
      Invalid(_, _) => true
      _ => false
    }
    assert_true(truncated)
    let terminal = try {
      ignore(decoder.next())
      false
    } catch {
      Invalid(_, _) => true
      _ => false
    }
    assert_true(terminal)
  }
}

///|
test "raw nested frame buffer limit cannot cause speculative resynchronization" {
  let bytes = raw_nested_fixture()
  for limit in [20, 41] {
    let decoder = RawDecoder::new(max_buffer_bytes=limit)
    assert_eq(decoder.push(bytes), limit)
    let limited = try {
      ignore(decoder.next())
      false
    } catch {
      Limit(_) => true
      _ => false
    }
    assert_true(limited)
    assert_eq(decoder.buffered_bytes(), limit)
  }
}

///|
test "raw nested recovery waits for confirmed corruption" {
  let corrupted = raw_nested_fixture().to_array()
  corrupted[corrupted.length() - 1] = corrupted[corrupted.length() - 1] ^ 1
  let bytes = Bytes::from_array(corrupted) + raw_test_frame(456, 10, 4)
  let decoder = RawDecoder::new()
  ignore(decoder.push(bytes[:20].to_owned()))
  assert_true(decoder.next() is RawNeedInput)
  ignore(decoder.push(bytes[20:].to_owned()))
  decoder.finish()
  // Only the now-confirmed CRC16 failure permits scanning beyond the header.
  match decoder.next() {
    Skipped(offset, count) => {
      assert_eq(offset, 0L)
      assert_eq(count, 8)
    }
    _ => fail("missing explicit corruption recovery event")
  }
  match decoder.next() {
    RawFrame(frame) => assert_eq(frame.channels[0][0], 123)
    _ => fail("missing CRC-validated recovered frame")
  }
  assert_true(decoder.next() is Skipped(_, _))
  match decoder.next() {
    RawFrame(frame) => assert_eq(frame.channels[0][0], 456)
    _ => fail("missing frame following corrupted outer data")
  }
  assert_true(decoder.next() is RawDone)
}

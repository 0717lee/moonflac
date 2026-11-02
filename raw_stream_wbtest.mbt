///|
/// Constant mono, explicit 48kHz/16-bit header, sixteen samples.
fn raw_test_frame(
  value : Int32,
  rate : Int32,
  depth : Int32,
  channels~ : Int32 = 1,
) -> Bytes {
  let h : Array[Byte] = [
    0xff,
    0xf8,
    (0x60 | rate).to_byte(),
    ((depth << 1) | ((channels - 1) << 4)).to_byte(),
    0,
    15,
  ]
  h.push(frame_crc(Bytes::from_array(h), 0, h.length(), 8).to_byte())
  let width = if depth == 6 { 3 } else if depth == 1 { 1 } else { 2 }
  for _ in 0..<channels {
    h.push(0)
    for byte = width - 1; byte >= 0; byte = byte - 1 {
      h.push((value >> (byte * 8)).to_byte())
    }
  }
  let crc = frame_crc(Bytes::from_array(h), 0, h.length(), 16)
  h.push((crc >> 8).to_byte())
  h.push(crc.to_byte())
  Bytes::from_array(h)
}

///|
test "raw arbitrary cuts report prefix and CRC damage while owning PCM" {
  let good = raw_test_frame(-123, 10, 4)
  let bad = good.to_array()
  bad[bad.length() - 1] = 0
  let bytes = b"noise" + Bytes::from_array(bad) + good + good
  for cut in 1..<=bytes.length() {
    let decoder = RawDecoder::new(max_buffer_bytes=64)
    let mut pos = 0
    let mut skipped = 0
    let mut frames = 0
    while true {
      match decoder.next() {
        RawFrame(f) => {
          assert_eq(f.channels[0][0], -123)
          assert_eq(f.sample_number, frames.to_int64() * 16L)
          frames += 1
        }
        Skipped(_, n) => skipped += n
        RawNeedInput =>
          if pos == bytes.length() {
            decoder.finish()
          } else {
            let end = if pos + cut < bytes.length() {
              pos + cut
            } else {
              bytes.length()
            }
            pos += decoder.push(bytes[pos:end].to_owned())
          }
        RawDone => break
      }
    }
    assert_eq(frames, 2)
    assert_eq(skipped, 5 + good.length())
    assert_true(decoder.peak_buffered_bytes() <= 64)
  }
}

///|
test "raw truncation and required external format are explicit" {
  let good = raw_test_frame(7, 10, 4)
  for end in 1..<good.length() {
    let decoder = RawDecoder::new()
    ignore(decoder.push(good[:end].to_owned()))
    decoder.finish()
    let rejected = try {
      ignore(decoder.next())
      false
    } catch {
      Invalid(_, _) => true
      _ => false
    }
    assert_true(rejected)
  }
  let missing = RawDecoder::new()
  ignore(missing.push(raw_test_frame(7, 0, 0)))
  let rejected = try {
    ignore(missing.next())
    false
  } catch {
    Limit(_) => true
    _ => false
  }
  assert_true(rejected)
  let explicit = RawDecoder::new(info=frame_test_info(16))
  ignore(explicit.push(raw_test_frame(7, 0, 0)))
  match explicit.next() {
    RawFrame(f) => assert_eq(f.sample_rate, 48000)
    _ => fail("missing raw frame")
  }
  let zero_rate = RawDecoder::new(info={
    ..frame_test_info(16),
    sample_rate: 0,
  })
  ignore(zero_rate.push(raw_test_frame(7, 0, 0)))
  match zero_rate.next() {
    RawFrame(f) => assert_eq(f.sample_rate, 0)
    _ => fail("missing raw non-audio frame")
  }
}

///|
test "raw permits changing frame rates and rejects buffer overflow" {
  let decoder = RawDecoder::new()
  ignore(
    decoder.push(raw_test_frame(1, 10, 4) + raw_test_frame(2, 9, 6, channels=2)),
  )
  match decoder.next() {
    RawFrame(f) => assert_eq(f.sample_rate, 48000)
    _ => fail("missing frame")
  }
  match decoder.next() {
    RawFrame(f) => {
      assert_eq(f.sample_rate, 44100)
      assert_eq(f.bits_per_sample, 24)
      assert_eq(f.channels.length(), 2)
      assert_eq(f.channels[1][0], 2)
    }
    _ => fail("missing frame")
  }
  decoder.finish()
  assert_true(decoder.next() is RawDone)
  let bounded = RawDecoder::new(max_buffer_bytes=8)
  assert_eq(bounded.push(raw_test_frame(1, 10, 4)), 8)
  let rejected = try {
    ignore(bounded.next())
    false
  } catch {
    Limit(_) => true
    _ => false
  }
  assert_true(rejected)
}

///|
test "raw one-byte delivery of 1MiB frame has geometric parsing and bounded storage" {
  // Eight 32-bit verbatim channels, 32768 samples each. All-zero samples are
  // chosen so the data payload cannot introduce secondary sync candidates.
  let output : Array[Byte] = [0xff, 0xf8, 0x7a, 0x7e, 0, 0x7f, 0xff]
  output.push(
    frame_crc(Bytes::from_array(output), 0, output.length(), 8).to_byte(),
  )
  for _ in 0..<8 {
    output.push(2)
    for _ in 0..<131072 {
      output.push(0)
    }
  }
  let crc = frame_crc(Bytes::from_array(output), 0, output.length(), 16)
  output.push((crc >> 8).to_byte())
  output.push(crc.to_byte())
  let bytes = Bytes::from_array(output)
  assert_true(bytes.length() > 1048576)
  let one_byte = Array::makei(256, i => Bytes::makei(1, _ => i.to_byte()))
  let decoder = RawDecoder::new(max_buffer_bytes=bytes.length() + 1)
  let mut snapshots = 0
  let mut snapshot_bytes = 0L
  let mut previous_pending = 0
  for byte in bytes {
    ignore(decoder.push(one_byte[byte.to_int()]))
    assert_true(decoder.next() is RawNeedInput)
    if decoder.pending.length() != previous_pending {
      snapshots += 1
      snapshot_bytes += decoder.pending.length().to_int64()
      previous_pending = decoder.pending.length()
    }
    assert_true(decoder.buffered_bytes() <= bytes.length() + 1)
  }
  // A final frame smaller than the next retry watermark is flushed by EOF.
  decoder.finish()
  match decoder.next() {
    RawFrame(frame) => {
      assert_eq(frame.block_size, 32768)
      assert_eq(frame.channels.length(), 8)
      assert_eq(frame.channels[7][32767], 0)
    }
    _ => fail("missing large raw frame")
  }
  assert_true(snapshots <= 18)
  assert_true(snapshot_bytes < bytes.length().to_int64() * 2L)
  assert_eq(decoder.peak_buffered_bytes(), bytes.length())
  assert_eq(decoder.buffered_bytes(), 0)
  assert_true(decoder.next() is RawDone)
}

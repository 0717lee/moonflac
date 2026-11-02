///|
/// RFC 9639 Appendix D.1, including its independently specified MD5.
fn stream_rfc_example() -> Bytes {
  b"\x66\x4c\x61\x43\x80\x00\x00\x22\x10\x00\x10\x00\x00\x00\x0f\x00\x00\x0f\x0a\xc4\x42\xf0\x00\x00\x00\x01\x3e\x84\xb4\x18\x07\xdc\x69\x03\x07\x58\x6a\x3d\xad\x1a\x2e\x0f\xff\xf8\x69\x18\x00\x00\xbf\x03\x58\xfd\x03\x12\x8b\xaa\x9a"
}

///|
test "file stream preserves changed properties despite original frame size hints" {
  let head = meta_test_stream([]).to_array()
  head[4] = 128
  let first = raw_test_frame(7, 9, 4)
  head[17] = first.length().to_byte()
  let second = raw_test_frame(8, 10, 6, channels=2).to_array()
  second[4] = 1
  second[6] = frame_crc(Bytes::from_array(second), 0, 6, 8).to_byte()
  let crc = frame_crc(Bytes::from_array(second), 0, second.length() - 2, 16)
  second[second.length() - 2] = (crc >> 8).to_byte()
  second[second.length() - 1] = crc.to_byte()
  let audio = decode(
    Bytes::from_array(head) + first + Bytes::from_array(second),
  )
  assert_eq(audio.frames.length(), 2)
  assert_eq(audio.frames[1].bits_per_sample, 24)
  assert_eq(audio.frames[1].sample_rate, 48000)
  assert_eq(audio.frames[1].channels[1][15], 8)
}

///|
fn stream_test_decode(
  bytes : Bytes,
  chunk : Int32,
) -> (Array[Frame], Integrity, Int32) raise FlacError {
  let decoder = Decoder::new()
  let frames = []
  let mut cursor = 0
  while true {
    match decoder.next() {
      MetadataReady(_) | LinkEnd(_) => ()
      AudioFrame(frame) => frames.push(frame)
      NeedInput =>
        if cursor == bytes.length() {
          decoder.finish()
        } else {
          let end = if bytes.length() - cursor < chunk {
            bytes.length()
          } else {
            cursor + chunk
          }
          cursor += decoder.push(bytes[cursor:end].to_owned())
        }
      Done(integrity) =>
        return (frames, integrity, decoder.peak_buffered_bytes())
    }
  } nobreak {
    raise Invalid(0L, "unfinished test")
  }
}

///|
test "RFC full stream all chunk sizes MD5 and owned PCM" {
  let bytes = stream_rfc_example()
  for chunk = 1; chunk <= bytes.length(); chunk = chunk + 1 {
    let (frames, integrity, peak) = stream_test_decode(bytes, chunk)
    assert_eq(integrity, Md5Verified)
    assert_eq(frames.length(), 1)
    assert_eq(frames[0].channels[0][0], 25588)
    assert_eq(frames[0].channels[1][0], 10416)
    assert_true(peak <= bytes.length())
    frames[0].channels[0][0] = 0
    assert_eq(decode(bytes).frames[0].channels[0][0], 25588)
  }
}

///|
test "finish rejects every RFC truncation and MD5 corruption" {
  let bytes = stream_rfc_example()
  for length = 0; length < bytes.length(); length = length + 1 {
    let rejected = try {
      let _ = stream_test_decode(bytes[:length].to_owned(), 1)
      false
    } catch {
      Invalid(_, _) => true
      _ => false
    }
    assert_true(rejected)
  }
  let bad = bytes.to_array()
  bad[26] = bad[26] ^ 1
  let rejected = try {
    let _ = decode(Bytes::from_array(bad))
    false
  } catch {
    Invalid(_, message) => message == "STREAMINFO MD5 mismatch"
    _ => false
  }
  assert_true(rejected)
}

///|
test "resource limit and terminal error state" {
  let decoder = Decoder::new(max_buffer_bytes=16)
  let _ = decoder.push(stream_rfc_example())
  let early_limit = try {
    let _ = decoder.next()
    false
  } catch {
    Limit(_) => true
    _ => false
  }
  assert_true(early_limit)
  let limited = try {
    let _ = decoder.push(b"x")
    false
  } catch {
    Limit(_) => true
    _ => false
  }
  assert_true(limited)
  let bad = Decoder::new()
  let _ = bad.push(b"nope")
  let rejected = try {
    let _ = bad.next()
    false
  } catch {
    Invalid(_, _) => true
    _ => false
  }
  assert_true(rejected)
  let sticky = try {
    let _ = bad.push(b"fLaC")
    false
  } catch {
    Invalid(_, _) => true
    _ => false
  }
  assert_true(sticky)
}

///|
test "native index exact interval and empty interval" {
  let bytes = stream_rfc_example()
  let index = build_index(bytes)
  assert_eq(index.total_samples, 1L)
  assert_eq(index.frames[0].offset, 42L)
  assert_eq(index.locate(0L).unwrap().offset, 42L)
  assert_true(index.locate(1L) is None)
  let audio = decode_indexed_range(bytes, index, 0L, 1L)
  assert_eq(audio.frames[0].byte_offset, 42L)
  assert_eq(audio.frames[0].channels[1][0], 10416)
  assert_eq(decode_range(bytes, 1L, 1L).frames.length(), 0)
  let outside = try {
    let _ = decode_range(bytes, 0L, 2L)
    false
  } catch {
    Invalid(_, _) => true
    _ => false
  }
  assert_true(outside)
}

///|
test "Ogg chained links decode with per-link metadata and integrity" {
  let link = ogg_test_bos() +
    ogg_test_page([132, 0, 0, 8, 0, 0, 0, 0, 0, 0, 0, 0], 1U, 0, 0UL) +
    ogg_test_page(ogg_test_audio(), 2U, 4, 16UL)
  let links = decode_chained(link + link)
  assert_eq(links.length(), 2)
  assert_eq(links[0].frames[0].block_size, 16)
  assert_eq(links[1].frames[0].sample_number, 0L)
  let (frames, _, _) = stream_test_decode(link + link, 1)
  assert_eq(frames.length(), 2)
  let cropped = decode_range(link + link, 14L, 18L)
  assert_eq(cropped.frames.length(), 2)
  assert_eq(cropped.frames[0].block_size, 2)
  assert_eq(cropped.frames[1].block_size, 2)
  assert_eq(cropped.frames[1].sample_number, 16L)
}

///|
test "one-byte delivery of large metadata uses geometric snapshots" {
  let original = stream_rfc_example()
  let header = original[:42].to_array()
  header[4] = 0
  let bytes = Bytes::from_array(header) +
    b"\x81\x10\x00\x00" +
    Bytes::make(1048576, 0) +
    original[42:].to_owned()
  let decoder = Decoder::new()
  let one_byte = Array::makei(256, i => Bytes::make(1, i.to_byte()))
  let mut snapshots = 0
  let mut previous = 0
  let mut copied = 0L
  for byte in bytes {
    ignore(decoder.push(one_byte[byte.to_int()]))
    assert_true(decoder.next() is NeedInput)
    let length = decoder.pending.length()
    if length != previous {
      snapshots += 1
      copied += length.to_int64()
      previous = length
    }
  }
  assert_true(snapshots < 24)
  assert_true(copied < bytes.length().to_int64() * 2L)
  decoder.finish()
  assert_true(decoder.next() is MetadataReady(_))
  match decoder.next() {
    AudioFrame(frame) => assert_eq(frame.channels[0][0], 25588)
    _ => fail("missing RFC frame after large metadata")
  }
  assert_true(decoder.next() is Done(Md5Verified))
  assert_eq(decoder.buffered_bytes(), 0)
  assert_eq(decoder.peak_buffered_bytes(), bytes.length())
}

///|
test "deterministic mutations terminate with explicit errors" {
  let original = stream_rfc_example()
  for i = 0; i < original.length(); i = i + 1 {
    for bit = 0; bit < 8; bit = bit + 1 {
      let bytes = original.to_array()
      bytes[i] = bytes[i] ^ (1 << bit).to_byte()
      try {
        let audio = decode(Bytes::from_array(bytes))
        // Some metadata edits remain legal; audio still has verified PCM.
        assert_eq(audio.frames[0].channels[0][0], 25588)
        assert_eq(audio.frames[0].channels[1][0], 10416)
      } catch {
        Invalid(_, _) | Limit(_) => ()
        NeedMore => fail("whole decode leaked NeedMore")
        error => raise error
      }
    }
  }
}

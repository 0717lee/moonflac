// Small bitstream vectors describe the format directly; corpus/oracle testing
// additionally compares real encoder output against independent decoders.

///|
fn frame_test_bits(bits : Array[Int32], value : Int64, width : Int32) -> Unit {
  for i = width - 1; i >= 0; i = i - 1 {
    bits.push(((value >> i) & 1L).to_int())
  }
}

///|
fn frame_test_info(depth : Int32) -> StreamInfo {
  {
    min_block_size: 16,
    max_block_size: 16,
    min_frame_size: 0,
    max_frame_size: 0,
    sample_rate: 48000,
    channels: 2,
    bits_per_sample: depth,
    total_samples: 16L,
    md5: Bytes::make(16, 0),
  }
}

///|
fn frame_test_reader(bits : Array[Int32]) -> FrameBits {
  while bits.length() % 8 != 0 {
    bits.push(0)
  }
  let bytes : Array[Byte] = []
  for i = 0; i < bits.length(); i = i + 8 {
    let mut n = 0
    for j = 0; j < 8; j = j + 1 {
      n = (n << 1) | bits[i + j]
    }
    bytes.push(n.to_byte())
  }
  { data: Bytes::from_array(bytes), pos: 0, bit: 0, base: 0L, }
}

///|
fn frame_test_pack(bits : Array[Int32], assignment : Int32) -> Bytes {
  let header = Bytes::from_array([
    0xFF,
    0xF8,
    0x60,
    (assignment << 4).to_byte(),
    0,
    15,
  ])
  let output : Array[Byte] = header.to_array()
  output.push(frame_crc(header, 0, header.length(), 8).to_byte())
  while bits.length() % 8 != 0 {
    bits.push(0)
  }
  for i = 0; i < bits.length(); i = i + 8 {
    let mut n = 0
    for j = 0; j < 8; j = j + 1 {
      n = (n << 1) | bits[i + j]
    }
    output.push(n.to_byte())
  }
  let body = Bytes::from_array(output)
  let crc = frame_crc(body, 0, body.length(), 16)
  output.push((crc >> 8).to_byte())
  output.push(crc.to_byte())
  Bytes::from_array(output)
}

///|
test "32-bit stereo decorrelation preserves extreme samples and 33-bit side" {
  for assignment in [8, 9, 10] {
    let bits : Array[Int32] = []
    let a = if assignment == 8 {
      2147483647L
    } else if assignment == 9 {
      4294967295L
    } else {
      -1L
    }
    let b = if assignment == 9 { -2147483648L } else { 4294967295L }
    frame_test_bits(bits, 0L, 8)
    frame_test_bits(bits, a, if assignment == 9 { 33 } else { 32 })
    frame_test_bits(bits, 0L, 8)
    frame_test_bits(bits, b, if assignment == 9 { 32 } else { 33 })
    let bytes = frame_test_pack(bits, assignment)
    let (frame, end) = parse_frame(bytes, 0, frame_test_info(32), 42L)
    assert_eq(end, bytes.length())
    assert_eq(frame.byte_offset, 42L)
    assert_eq(frame.channels[0][0], 2147483647)
    assert_eq(frame.channels[1][15], -2147483648)
  }
}

///|
test "fixed predictors 0 through 4 and Rice2 zero residual" {
  for order = 0; order <= 4; order = order + 1 {
    let bits : Array[Int32] = []
    frame_test_bits(bits, ((8 + order) << 1).to_int64(), 8)
    for i = 0; i < order; i = i + 1 {
      frame_test_bits(bits, 7L, 16)
    }
    frame_test_bits(bits, 1L, 2) // Rice2
    frame_test_bits(bits, 0L, 4) // one partition
    frame_test_bits(bits, 0L, 5) // parameter 0
    for i = order; i < 16; i = i + 1 {
      frame_test_bits(bits, 1L, 1)
    }
    let (frame, _) = parse_frame(
      frame_test_pack(bits, 0),
      0,
      frame_test_info(16),
      0L,
    )
    for sample in frame.channels[0] {
      assert_eq(sample, if order == 0 { 0 } else { 7 })
    }
  }
}

///|
test "LPC wide intermediate, escaped zero residual, wasted restoration" {
  let bits : Array[Int32] = []
  frame_test_bits(bits, 65L, 8) // LPC order 1, wasted flag
  frame_test_bits(bits, 1L, 1) // one wasted bit
  frame_test_bits(bits, 1073741823L, 31)
  frame_test_bits(bits, 14L, 4) // 15-bit coefficient
  frame_test_bits(bits, 13L, 5)
  frame_test_bits(bits, 8192L, 15)
  frame_test_bits(bits, 0L, 2)
  frame_test_bits(bits, 0L, 4)
  frame_test_bits(bits, 15L, 4) // escape
  frame_test_bits(bits, 0L, 5)
  let (frame, _) = parse_frame(
    frame_test_pack(bits, 0),
    0,
    frame_test_info(32),
    0L,
  )
  assert_eq(frame.channels[0][15], 2147483646)
}

///|
test "verbatim signed widths 4 through 32 and every byte truncation" {
  for depth = 4; depth <= 32; depth = depth + 1 {
    let bits : Array[Int32] = []
    frame_test_bits(bits, 2L, 8)
    let low = -(1L << (depth - 1))
    for i = 0; i < 16; i = i + 1 {
      frame_test_bits(bits, if i % 2 == 0 { low } else { -low - 1L }, depth)
    }
    let bytes = frame_test_pack(bits, 0)
    let (frame, _) = parse_frame(bytes, 0, frame_test_info(depth), 0L)
    assert_eq(frame.channels[0][0].to_int64(), low)
    assert_eq(frame.channels[0][15].to_int64(), -low - 1L)
    for length = 0; length < bytes.length(); length = length + 1 {
      let short = Array::make(length, (0).to_byte())
      for i = 0; i < length; i = i + 1 {
        short[i] = bytes[i]
      }
      let incomplete = try {
        ignore(
          parse_frame(Bytes::from_array(short), 0, frame_test_info(depth), 0L),
        )
        false
      } catch {
        NeedMore => true
        _ => false
      }
      assert_true(incomplete)
    }
  }
}

///|
test "CRC8 CRC16 corruption and nonzero reserved bit are rejected" {
  let bits : Array[Int32] = []
  frame_test_bits(bits, 0L, 8)
  frame_test_bits(bits, 5L, 16)
  let valid = frame_test_pack(bits, 0)
  for index in [3, 6, valid.length() - 1] {
    let bad = valid.to_array()
    bad[index] = (bad[index].to_int() ^ 1).to_byte()
    let rejected = try {
      ignore(parse_frame(Bytes::from_array(bad), 0, frame_test_info(16), 100L))
      false
    } catch {
      Invalid(offset, _) => offset >= 100L
      _ => false
    }
    assert_true(rejected)
  }
}

///|
test "coded numbers require shortest encoding and support 36 bits" {
  let r : FrameBits = {
    data: b"\xfe\xbf\xbf\xbf\xbf\xbf\xbf",
    pos: 0,
    bit: 0,
    base: 0L,
  }
  assert_eq(frame_number(r, true), 68719476735L)
  let overlong : FrameBits = { data: b"\xc0\x80", pos: 0, bit: 0, base: 0L, }
  let rejected = try {
    ignore(frame_number(overlong, false))
    false
  } catch {
    Invalid(_, _) => true
    _ => false
  }
  assert_true(rejected)
}

///|
test "RFC 9639 Appendix D.1 independently specified frame and samples" {
  let bytes = b"\xff\xf8\x69\x18\x00\x00\xbf\x03\x58\xfd\x03\x12\x8b\xaa\x9a"
  let (frame, end) = parse_frame(bytes, 0, frame_test_info(16), 42L)
  assert_eq(end, 15)
  assert_eq(frame.block_size, 1)
  assert_eq(frame.sample_rate, 44100)
  assert_eq(frame.channels[0][0], 25588)
  assert_eq(frame.channels[1][0], 10416)
}

///|
test "Rice2 parameter 30 maximum residual magnitudes and forbidden minimum" {
  for folded in [4294967293L, 4294967294L, 4294967295L] {
    let bits : Array[Int32] = []
    frame_test_bits(bits, 1L, 2)
    frame_test_bits(bits, 0L, 4)
    frame_test_bits(bits, 30L, 5)
    frame_test_bits(bits, 1L, 4) // quotient 3
    frame_test_bits(bits, folded & 1073741823L, 30)
    let samples = [0L]
    let r = frame_test_reader(bits)
    if folded == 4294967295L {
      let rejected = try {
        frame_residual(r, samples, 0)
        false
      } catch {
        Invalid(_, _) => true
        _ => false
      }
      assert_true(rejected)
    } else {
      frame_residual(r, samples, 0)
      assert_eq(
        samples[0],
        if folded == 4294967293L {
          -2147483647L
        } else {
          2147483647L
        },
      )
    }
  }
}

///|
test "all LPC orders including 32 and nonzero escaped residual" {
  for order = 1; order <= 32; order = order + 1 {
    let bits : Array[Int32] = []
    frame_test_bits(bits, ((order + 31) << 1).to_int64(), 8)
    for i = 0; i < order; i = i + 1 {
      frame_test_bits(bits, 1000L, 32)
    }
    frame_test_bits(bits, 1L, 4) // precision 2
    frame_test_bits(bits, 0L, 5)
    for i = 0; i < order; i = i + 1 {
      frame_test_bits(bits, if i == 0 { 1L } else { 0L }, 2)
    }
    frame_test_bits(bits, 0L, 2)
    frame_test_bits(bits, 0L, 4)
    frame_test_bits(bits, 15L, 4)
    frame_test_bits(bits, 3L, 5)
    frame_test_bits(bits, -3L, 3)
    let samples = frame_subframe(frame_test_reader(bits), order + 1, 32)
    assert_eq(samples[order], 997L)
  }
}

///|
test "reserved subframes negative LPC shifts and sample overflow are errors" {
  for kind in [2, 7, 13, 31] {
    let r : FrameBits = {
      data: Bytes::from_array([(kind << 1).to_byte()]),
      pos: 0,
      bit: 0,
      base: 9L,
    }
    let rejected = try {
      ignore(frame_subframe(r, 16, 16))
      false
    } catch {
      Invalid(_, _) => true
      _ => false
    }
    assert_true(rejected)
  }
  let bits : Array[Int32] = []
  frame_test_bits(bits, 64L, 8)
  frame_test_bits(bits, 0L, 16)
  frame_test_bits(bits, 0L, 4)
  frame_test_bits(bits, -1L, 5)
  let rejected = try {
    ignore(frame_subframe(frame_test_reader(bits), 16, 16))
    false
  } catch {
    Invalid(_, _) => true
    _ => false
  }
  assert_true(rejected)
  let overflow : Array[Int32] = []
  frame_test_bits(overflow, 18L, 8) // fixed order 1
  frame_test_bits(overflow, 7L, 4)
  frame_test_bits(overflow, 0L, 2)
  frame_test_bits(overflow, 0L, 4)
  frame_test_bits(overflow, 15L, 4)
  frame_test_bits(overflow, 2L, 5)
  frame_test_bits(overflow, 1L, 2)
  let rejected = try {
    ignore(frame_subframe(frame_test_reader(overflow), 2, 4))
    false
  } catch {
    Invalid(_, _) => true
    _ => false
  }
  assert_true(rejected)
}

///|
test "unary byte skipping preserves all start alignments and remainder bits" {
  for alignment = 0; alignment < 8; alignment = alignment + 1 {
    for zeros = 0; zeros < 40; zeros = zeros + 1 {
      let bits : Array[Int32] = []
      frame_test_bits(bits, 127L, alignment)
      frame_test_bits(bits, 0L, zeros)
      frame_test_bits(bits, 1L, 1)
      frame_test_bits(bits, 21L, 5)
      let r = frame_test_reader(bits)
      ignore(r.read(alignment))
      assert_eq(r.unary(zeros.to_int64()), zeros.to_int64())
      assert_eq(r.read(5), 21L)
    }
  }
}

///|
test "long unary runs truncate and exceed limits without bitwise rescanning" {
  let bytes = Bytes::make(1048576, 0) + b"\x80"
  let r : FrameBits = { data: bytes, pos: 0, bit: 0, base: 0L, }
  assert_eq(r.unary(8388608L), 8388608L)
  assert_eq(r.pos, 1048576)
  assert_eq(r.bit, 1)
  let truncated : FrameBits = {
    data: Bytes::make(4096, 0),
    pos: 0,
    bit: 3,
    base: 0L,
  }
  let incomplete = try {
    ignore(truncated.unary(32768L))
    false
  } catch {
    NeedMore => true
    _ => false
  }
  assert_true(incomplete)
  let excessive : FrameBits = { data: b"\x00\x01", pos: 0, bit: 0, base: 7L, }
  let rejected = try {
    ignore(excessive.unary(14L))
    false
  } catch {
    Invalid(_, _) => true
    _ => false
  }
  assert_true(rejected)
}

///|
fn word_oracle_write(bits : Array[Int32], value : Int64, width : Int32) -> Unit {
  for i = width - 1; i >= 0; i = i - 1 {
    bits.push(((value >> i) & 1L).to_int())
  }
}

///|
fn word_oracle_bytes(bits : Array[Int32], aligned : Bool) -> Bytes {
  let count = if aligned { (bits.length() + 7) / 8 } else { bits.length() / 8 }
  Bytes::makei(count, i => {
    let mut byte = 0
    for j = 0; j < 8; j = j + 1 {
      let at = i * 8 + j
      byte = (byte << 1) | (if at < bits.length() { bits[at] } else { 0 })
    }
    byte.to_byte()
  })
}

///|
/// Private test/header snapshots copy: later writes cannot mutate Bytes.
fn EncoderBits::snapshot(self : EncoderBits) -> Bytes {
  self.materialize()
  Bytes::makei(self.length, i => self.buffer.unsafe_get(i))
}

///|
fn EncoderBits::bit_length(self : EncoderBits) -> Int32 {
  self.length * 8 + self.used
}

///|
test "word writer independent bit oracle all widths and pending offsets" {
  for pending = 0; pending < 64; pending = pending + 1 {
    for width = 0; width <= 64; width = width + 1 {
      for
        value in [
          0L, 1L, -1L, -9223372036854775808L, 9223372036854775807L, 0x13579bdf2468ace0L,
        ] {
        let out = EncoderBits::new()
        let bits : Array[Int32] = []
        out.write(0x123456789abcdefL, pending)
        word_oracle_write(bits, 0x123456789abcdefL, pending)
        out.write(value, width)
        word_oracle_write(bits, value, width)
        assert_eq(out.bit_length(), bits.length())
        let snapshot = out.snapshot()
        let expected = word_oracle_bytes(bits, false)
        assert_eq(snapshot, expected)
        out.write(-1L, 64)
        word_oracle_write(bits, -1L, 64)
        assert_eq(snapshot, expected)
        assert_eq(out.finish(), word_oracle_bytes(bits, true))
        // A finished writer can be reused without mutating returned Bytes.
        out.write(0L, 8)
        assert_eq(snapshot, expected)
      }
    }
  }
}

///|
test "word writer unary resize exact capacity immutable freeze and CRC" {
  for pending = 0; pending < 64; pending = pending + 1 {
    for zeros in [0, 1, 7, 8, 63, 64, 65, 127, 128, 129, 1025] {
      let out = EncoderBits::new()
      let bits : Array[Int32] = []
      out.write(-1L, pending)
      word_oracle_write(bits, -1L, pending)
      out.unary(zeros.to_int64())
      for i = 0; i < zeros; i = i + 1 {
        bits.push(0)
      }
      bits.push(1)
      out.align()
      let expected = word_oracle_bytes(bits, true)
      assert_eq(out.crc(8), frame_crc(expected, 0, expected.length(), 8))
      assert_eq(out.crc(16), frame_crc(expected, 0, expected.length(), 16))
      let done = out.finish()
      assert_eq(done, expected)
      out.write(-1L, 64)
      assert_eq(done, expected)
    }
  }
  for size in [0, 1, 7, 8, 9, 15, 16, 17, 128, 1025] {
    let out = EncoderBits::new()
    out.reserve(size)
    for i = 0; i < size; i = i + 1 {
      out.write(i.to_int64(), 8)
    }
    assert_eq(out.buffer.length(), size)
    assert_eq(out.finish(), Bytes::makei(size, i => i.to_byte()))
  }
}

///|
fn crc_table_serial(state : Int32, byte : Int32, width : Int32) -> Int32 {
  let mut crc = state ^ (byte << (width - 8))
  let polynomial = if width == 8 { 7 } else { 0x8005 }
  let mask = (1 << width) - 1
  for _ in 0..<8 {
    crc = if (crc & (1 << (width - 1))) != 0 {
      ((crc << 1) ^ polynomial) & mask
    } else {
      (crc << 1) & mask
    }
  }
  crc
}

///|
fn crc_table_reference(
  bytes : Bytes,
  start : Int32,
  end : Int32,
  width : Int32,
) -> Int32 {
  let mut crc = 0
  for i = start; i < end; i = i + 1 {
    crc = crc_table_serial(crc, bytes[i].to_int(), width)
  }
  crc
}

///|
test "CRC tables equal independent bit transition including complete linear basis" {
  for width in [8, 16] {
    let table = if width == 8 { frame_crc8_table } else { frame_crc16_table }
    for byte in 0..<256 {
      assert_eq(table[byte], crc_table_serial(0, byte, width))
    }
    for basis in 0..<(width + 8) {
      let state = if basis < width { 1 << basis } else { 0 }
      let byte = if basis >= width { 1 << (basis - width) } else { 0 }
      let actual = if width == 8 {
        table[state ^ byte]
      } else {
        ((state << 8) & 65535) ^ table[(state >> 8) ^ byte]
      }
      assert_eq(actual, crc_table_serial(state, byte, width))
    }
  }
  assert_eq(frame_crc(b"123456789", 0, 9, 8), 0xf4)
  assert_eq(frame_crc(b"123456789", 0, 9, 16), 0xfee8)
  for first in 0..<256 {
    for second in 0..<256 {
      let bytes = Bytes::makei(2, i => {
        (if i == 0 { first } else { second }).to_byte()
      })
      assert_eq(frame_crc(bytes, 0, 2, 8), crc_table_reference(bytes, 0, 2, 8))
    }
  }
}

///|
test "CRC arbitrary slices empty ranges random data and large buffers match serial oracle" {
  let mut seed = 9639U
  let bytes = Bytes::makei(1048640, _ => {
    seed = seed * 1664525U + 1013904223U
    (seed >> 24).to_byte()
  })
  for width in [8, 16] {
    assert_eq(frame_crc(b"", 0, 0, width), 0)
    assert_eq(frame_crc(bytes, 65, 64, width), 0)
    for start in 0..<64 {
      for length in 0..<129 {
        assert_eq(
          frame_crc(bytes, start, start + length, width),
          crc_table_reference(bytes, start, start + length, width),
        )
      }
    }
    assert_eq(
      frame_crc(bytes, 37, 1048613, width),
      crc_table_reference(bytes, 37, 1048613, width),
    )
  }
}

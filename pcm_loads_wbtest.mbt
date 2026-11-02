///|
/// Frozen bytewise oracle: independent Int64 assembly, no SDK word loads.
fn pcm_loads_byte_oracle(
  data : BytesView,
  width : Int32,
  raw : Bool,
) -> Array[Int32] {
  let values : Array[Int32] = []
  for i in 0..<(data.length() / width) {
    let mut unsigned = 0L
    for j in 0..<width {
      unsigned = unsigned | (data[i * width + j].to_int64() << (j * 8))
    }
    let value = if !raw && width == 1 {
      unsigned - 128L
    } else if (unsigned & (1L << (width * 8 - 1))) != 0L {
      unsigned - (1L << (width * 8))
    } else {
      unsigned
    }
    values.push(value.to_int())
  }
  values
}

///|
fn pcm_loads_full_fixture(width : Int32) -> Bytes {
  match width {
    1 => b"\x80\xff\x00\x01\x7f"
    2 => b"\x00\x80\xff\xff\x00\x00\x01\x00\xff\x7f"
    3 => b"\x00\x00\x80\xff\xff\xff\x00\x00\x00\x01\x00\x00\xff\xff\x7f"
    _ =>
      b"\x00\x00\x00\x80\xff\xff\xff\xff\x00\x00\x00\x00\x01\x00\x00\x00\xff\xff\xff\x7f"
  }
}

///|
test "full container loads match frozen byte oracle at every view alignment and exact EOF" {
  for width in [1, 2, 3, 4] {
    let data = pcm_loads_full_fixture(width)
    let expected = [
      (-(1L << (width * 8 - 1))).to_int(),
      -1,
      0,
      1,
      ((1L << (width * 8 - 1)) - 1L).to_int(),
    ]
    assert_eq(pcm_loads_byte_oracle(data[:], width, true), expected)
    for start in 0..<8 {
      // No suffix: the final 24-bit sample has exactly three addressable bytes.
      let storage = FixedArray::make(start + data.length(), (0x5a : Byte))
      for i in 0..<data.length() {
        storage[start + i] = data[i]
      }
      let backing = storage.unsafe_reinterpret_as_bytes()
      let format : PcmFormat = {
        sample_rate: 48000,
        channels: 1,
        bits_per_sample: width * 8,
      }
      let reader = PcmInput::raw(format)
      reader.pending = backing[start:]
      reader.offset = 71L
      let actual = reader.read_samples(format, data.length())
      assert_eq(actual, expected)
      assert_eq(reader.offset, 71L + data.length().to_int64())
      assert_eq(reader.samples, 5L)
      assert_eq(reader.pending.length(), 0)
      storage[start] = 0
      assert_eq(actual, expected)
    }
  }
}

///|
test "full container loads retain arbitrary input splits and reject partial EOF frames" {
  for width in [1, 2, 3, 4] {
    let data = pcm_loads_full_fixture(width)
    let joined = @buffer.Buffer()
    joined.write_bytes(data)
    joined.write_bytes(data)
    let raw = joined.to_bytes()
    let format : PcmFormat = {
      sample_rate: 48000,
      channels: 2,
      bits_per_sample: width * 8,
    }
    let expected = pcm_loads_byte_oracle(raw[:], width, true)
    for cut in [1, 2, 3, 4, 7, 65536] {
      let (_, _, actual) = pcm_test_collect(PcmInput::raw(format), raw, cut)
      assert_eq(actual, expected)
      let truncated = try {
        ignore(
          pcm_test_collect(
            PcmInput::raw(format),
            raw[:raw.length() - 1].to_owned(),
            cut,
          ),
        )
        false
      } catch {
        _ => true
      }
      assert_true(truncated)
    }
  }
}

///|
test "full WAV8 loads remain unsigned while raw8 remains signed" {
  let data = b"\x00\x7f\x80\x81\xff"
  let out = @buffer.Buffer()
  out.write_bytes(b"RIFF")
  out.write_int_le(42)
  out.write_bytes(b"WAVEfmt ")
  out.write_int_le(16)
  out.write_uint16_le(1)
  out.write_uint16_le(1)
  out.write_int_le(48000)
  out.write_int_le(48000)
  out.write_uint16_le(1)
  out.write_uint16_le(8)
  out.write_bytes(b"data")
  out.write_int_le(5)
  out.write_bytes(data)
  out.write_byte(0)
  for cut in [1, 2, 7, 65536] {
    let (_, _, wav_values) = pcm_test_collect(
      PcmInput::wav(),
      out.to_bytes(),
      cut,
    )
    assert_eq(wav_values, [-128, -1, 0, 1, 127])
    assert_eq(wav_values, pcm_loads_byte_oracle(data[:], 1, false))
    let (_, _, raw_values) = pcm_test_collect(
      PcmInput::raw({ sample_rate: 48000, channels: 1, bits_per_sample: 8, }),
      data,
      cut,
    )
    assert_eq(raw_values, [0, 127, -128, -127, -1])
  }
}

///|
test "full container exact-size output covers the maximum scalar batch" {
  for width in [1, 2, 3, 4] {
    let backing = Bytes::makei(3 + 4096 * width, i => {
      ((i * 53 + i / 7) % 256).to_byte()
    })
    let view = backing[3:]
    let expected = pcm_loads_byte_oracle(view, width, true)
    let format : PcmFormat = {
      sample_rate: 48000,
      channels: 8,
      bits_per_sample: width * 8,
    }
    let reader = PcmInput::raw(format)
    reader.pending = view
    let actual = reader.read_samples(format, view.length())
    assert_eq(actual.length(), 4096)
    assert_eq(actual, expected)
    assert_eq(reader.samples, 512L)
    assert_eq(reader.pending.length(), 0)
  }
}

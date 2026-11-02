///|
fn pcm_test_collect(
  reader : PcmInput,
  data : Bytes,
  cut : Int32,
) -> (PcmFormat, UInt32?, Array[Int32]) raise FlacError {
  let mut at = 0
  let mut finished = false
  let mut format : PcmFormat? = None
  let mut mask : UInt32? = None
  let values : Array[Int32] = []
  while true {
    match reader.next() {
      PcmFormatReady(value, layout) => {
        format = Some(value)
        mask = layout
      }
      PcmSamples(samples) =>
        for sample in samples {
          values.push(sample)
        }
      PcmNeedInput =>
        if at == data.length() {
          if finished {
            raise Invalid(0L, "test reader stuck after finish")
          }
          reader.finish()
          finished = true
        } else {
          let end = if at + cut < data.length() {
            at + cut
          } else {
            data.length()
          }
          at += reader.push(data[at:end].to_owned())
        }
      PcmInputDone => return (format.unwrap(), mask, values)
    }
  } nobreak {
    abort("unreachable")
  }
}

///|
/// Independent explicit RIFF fixture; samples -1,0,1 in 32-bit containers.
fn pcm_test_wav(bits : Int32, rf64 : Bool) -> Bytes {
  let out = @buffer.Buffer()
  let pcm : Array[Int32] = [-1, 0, 1]
  out.write_bytes(if rf64 { b"RF64" } else { b"RIFF" })
  out.write_uint_le(if rf64 { 0xffffffffU } else { 72U })
  out.write_bytes(b"WAVE")
  if rf64 {
    out.write_bytes(b"ds64")
    out.write_int_le(28)
    out.write_int64_le(108L)
    out.write_int64_le(12L)
    out.write_int64_le(3L)
    out.write_int_le(0)
  }
  out.write_bytes(b"fmt ")
  out.write_int_le(40)
  out.write_uint16_le(65534)
  out.write_uint16_le(1)
  out.write_int_le(48000)
  out.write_int_le(192000)
  out.write_uint16_le(4)
  out.write_uint16_le(32)
  out.write_uint16_le(22)
  out.write_uint16_le(bits.to_uint16())
  out.write_uint_le(0)
  out.write_bytes(
    b"\x01\x00\x00\x00\x00\x00\x10\x00\x80\x00\x00\xaa\x00\x38\x9b\x71",
  )
  out.write_bytes(b"data")
  out.write_uint_le(if rf64 { 0xffffffffU } else { 12U })
  for sample in pcm {
    out.write_int_le(sample << (32 - bits))
  }
  out.to_bytes()
}

///|
test "PCM reader preserves valid bits and explicit zero across arbitrary RIFF/RF64 splits" {
  for bits in 4..<=32 {
    for rf64 in [false, true] {
      for cut in [1, 2, 7, 65536] {
        let (format, mask, values) = pcm_test_collect(
          PcmInput::wav(),
          pcm_test_wav(bits, rf64),
          cut,
        )
        assert_eq(format.bits_per_sample, bits)
        assert_eq(mask, Some(0U))
        assert_eq(values, [-1, 0, 1])
      }
    }
  }
}

///|
test "raw reader groups channels and rejects truncated or non-sign-extended values" {
  let format : PcmFormat = { sample_rate: 0, channels: 2, bits_per_sample: 4, }
  let (_, _, values) = pcm_test_collect(
    PcmInput::raw(format),
    b"\xff\x07\xf8\x00",
    1,
  )
  assert_eq(values, [-1, 7, -8, 0])
  let bads = [b"\xff", b"\x0f\x00"]
  for bad in bads {
    let result = try {
      ignore(pcm_test_collect(PcmInput::raw(format), bad, 1))
      false
    } catch {
      _ => true
    }
    assert_true(result)
  }
}

///|
test "WAV rejects low padding bits and truncation with sticky errors" {
  let valid = pcm_test_wav(24, false)
  let bad = Bytes::makei(valid.length(), i => if i == 68 { 1 } else { valid[i] })
  let reader = PcmInput::wav()
  let result = try {
    ignore(pcm_test_collect(reader, bad, 1))
    false
  } catch {
    _ => true
  }
  assert_true(result)
  let sticky = try {
    ignore(reader.next())
    false
  } catch {
    _ => true
  }
  assert_true(sticky)
  for cut in [0, 1, 11, 40, valid.length() - 1] {
    let result = try {
      ignore(pcm_test_collect(PcmInput::wav(), valid[:cut].to_owned(), 7))
      false
    } catch {
      _ => true
    }
    assert_true(result)
  }
}

///|
test "WAV skips large unknown chunks within bounded staging" {
  let valid = pcm_test_wav(32, false)
  let out = @buffer.Buffer()
  out.write_bytes(b"RIFF")
  out.write_int_le(72 + 8 + 131072)
  out.write_bytes(b"WAVEJUNK")
  out.write_int_le(131072)
  out.write_bytes(Bytes::make(131072, 42))
  out.write_bytes(valid[12:])
  let reader = PcmInput::wav()
  let (_, _, values) = pcm_test_collect(reader, out.to_bytes(), 65536)
  assert_eq(values, [-1, 0, 1])
  assert_eq(reader.buffered_bytes(), 0)
}

///|
test "RF64 preserves 64-bit unknown chunk sizes without allocating the payload" {
  let out = @buffer.Buffer()
  out.write_bytes(b"RF64\xff\xff\xff\xffWAVEds64")
  out.write_int_le(40)
  out.write_int64_le(4294967400L)
  out.write_int64_le(0L)
  out.write_int64_le(0L)
  out.write_int_le(1)
  out.write_bytes(b"JUNK")
  out.write_int64_le(4294967297L)
  out.write_bytes(b"JUNK\xff\xff\xff\xff")
  let reader = PcmInput::wav()
  ignore(reader.push(out.to_bytes()))
  assert_true(reader.next() is PcmNeedInput)
  assert_eq(reader.chunk_left, 4294967297L)
  assert_eq(reader.buffered_bytes(), 0)
  reader.finish()
  let truncated = try {
    ignore(reader.next())
    false
  } catch {
    _ => true
  }
  assert_true(truncated)
}

///|
test "PCM staging copies only its accepted prefix and releases drained storage" {
  let reader = PcmInput::raw({
    sample_rate: 48000,
    channels: 1,
    bits_per_sample: 8,
  })
  let caller_storage = FixedArray::make(1048576, (0 : Byte))
  // Exercise copy ownership even when a caller can still mutate its backing
  // allocation. The decoder must never retain this oversized input allocation.
  let input = caller_storage.unsafe_reinterpret_as_bytes()
  assert_eq(reader.push(input), 65536)
  assert_eq(reader.pending.data().length(), 65536)
  caller_storage[0] = 7
  caller_storage[65535] = 9
  assert_true(reader.next() is PcmFormatReady(_, _))
  let mut count = 0
  while count < 65536 {
    match reader.next() {
      PcmSamples(samples) => {
        assert_true(samples.length() <= 4096)
        for value in samples {
          assert_eq(value, 0)
        }
        count += samples.length()
        assert_eq(reader.buffered_bytes(), 65536 - count)
        assert_true(reader.pending.data().length() <= 65536)
      }
      _ => fail("unexpected event while draining accepted PCM")
    }
  }
  assert_eq(reader.pending.data().length(), 0)
  reader.finish()
  assert_true(reader.next() is PcmInputDone)
}

///|
test "PCM compaction preserves partial channel groups and absolute sticky error positions" {
  for last in [7, 15] {
    let reader = PcmInput::raw({
      sample_rate: 48000,
      channels: 2,
      bits_per_sample: 4,
    })
    assert_eq(reader.push(Bytes::make(65535, 0)), 65535)
    assert_true(reader.next() is PcmFormatReady(_, _))
    let mut count = 0
    while count < 65534 {
      match reader.next() {
        PcmSamples(samples) => {
          for value in samples {
            assert_eq(value, 0)
          }
          count += samples.length()
        }
        _ => fail("partial channel group was consumed or lost")
      }
    }
    assert_true(reader.next() is PcmNeedInput)
    assert_eq(reader.offset, 65534L)
    assert_eq(reader.buffered_bytes(), 1)
    assert_eq(reader.push(Bytes::make(1, last.to_byte())), 1)
    assert_eq(reader.pending.data().length(), 2)
    if last == 7 {
      match reader.next() {
        PcmSamples(samples) => assert_eq(samples, [0, 7])
        _ => fail("compacted channel group was not emitted")
      }
      reader.finish()
      assert_true(reader.next() is PcmInputDone)
    } else {
      for _ in 0..<2 {
        let position = try {
          ignore(reader.next())
          -1L
        } catch {
          Invalid(at, _) => at
          _ => -2L
        }
        assert_eq(position, 65535L)
      }
      let finish_position = try {
        reader.finish()
        -1L
      } catch {
        Invalid(at, _) => at
        _ => -2L
      }
      assert_eq(finish_position, 65535L)
    }
  }
}

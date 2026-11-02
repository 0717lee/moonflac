///|
fn encoder_test_info(format : PcmFormat, size : Int32) -> StreamInfo {
  {
    min_block_size: if size < 16 {
      16
    } else {
      size
    },
    max_block_size: if size < 16 {
      16
    } else {
      size
    },
    min_frame_size: 0,
    max_frame_size: 0,
    sample_rate: format.sample_rate,
    channels: format.channels,
    bits_per_sample: format.bits_per_sample,
    total_samples: size.to_int64(),
    md5: Bytes::make(16, 0),
  }
}

///|
test "encoder bit writer signed33 and partial byte unary exact bytes" {
  let out = EncoderBits::new()
  out.write(-1L, 33)
  out.unary(2L)
  out.write(5L, 4)
  assert_eq(out.snapshot(), b"\xff\xff\xff\xff\x95")
}

///|
test "encoder canonical extended numbers exact octets" {
  let values = [
    127L, 128L, 2048L, 65536L, 2097152L, 67108864L, 2147483648L, 68719476735L,
  ]
  let expected = [
    b"\x7f", b"\xc2\x80", b"\xe0\xa0\x80", b"\xf0\x90\x80\x80", b"\xf8\x88\x80\x80\x80",
    b"\xfc\x84\x80\x80\x80\x80", b"\xfe\x82\x80\x80\x80\x80\x80", b"\xfe\xbf\xbf\xbf\xbf\xbf\xbf",
  ]
  for i = 0; i < values.length(); i = i + 1 {
    let out = EncoderBits::new()
    encoder_number(out, values[i], true)
    assert_eq(out.snapshot(), expected[i])
  }
}

///|
test "encoder every bit depth and channel count extrema" {
  for depth = 4; depth <= 32; depth = depth + 1 {
    for channels = 1; channels <= 8; channels = channels + 1 {
      let format : PcmFormat = {
        sample_rate: 1048575,
        channels,
        bits_per_sample: depth,
      }
      let low = -(1L << (depth - 1))
      let planes = Array::makei(channels, c => {
        Array::makei(17, i => {
          if (i + c) % 2 == 0 {
            low.to_int()
          } else {
            (-low - 1L).to_int()
          }
        })
      })
      let bytes = encode_frame(format, planes, 0L, false, 1)
      let (frame, end) = parse_frame(
        bytes,
        0,
        encoder_test_info(format, 17),
        0L,
      )
      assert_eq(end, bytes.length())
      for c = 0; c < channels; c = c + 1 {
        for i = 0; i < 17; i = i + 1 {
          assert_eq(frame.channels[c][i], planes[c][i])
        }
      }
    }
  }
}

///|
test "encoder natural constant fixed verbatim and wasted selection" {
  assert_eq(encoder_subframe(Array::make(64, -3L), 24, 8).kind, 0)
  let silence = encoder_subframe(Array::make(64, 0L), 32, 8)
  assert_eq(silence.kind, 8)
  assert_eq(silence.bits, 23L)
  let ramp = Array::makei(256, i => i.to_int64() * 32L)
  let sub = encoder_subframe(ramp, 24, 4)
  assert_eq(sub.kind, 10)
  assert_true(sub.wasted > 0)
  let noisy = Array::makei(32, i => {
    if i % 2 == 0 {
      -2147483648L
    } else {
      2147483647L
    }
  })
  assert_eq(encoder_subframe(noisy, 32, 1).kind, 1)
}

///|
test "encoder optimal partition order15 and Rice2 parameter30" {
  let residual = Array::makei(32768, i => {
    if i % 2 == 0 {
      0L
    } else {
      2147483647L
    }
  })
  let plan = encoder_residual_plan(residual, 0, 15)
  assert_eq(plan.order, 15)
  assert_true(plan.rice2)
  assert_eq(plan.parts[1].parameter, 30)
  assert_eq(plan.parts[0].parameter, 0)
}

///|
test "encoder escaped residual width0 through31 costs" {
  let empty : EncoderRiceNode = {
    quotients: Array::make(31, 0L),
    count: 64,
    width: 0,
  }
  let (part, cost) = encoder_partition(empty, false)
  assert_eq(part.width, 0)
  assert_eq(part.parameter, 15)
  assert_eq(cost, 9L)
  for width = 1; width <= 31; width = width + 1 {
    let value = -(1L << (width - 1))
    assert_eq(encoder_signed_width(value), width)
    let folded = -2L * value - 1L
    let node : EncoderRiceNode = {
      quotients: Array::makei(31, k => (folded >> k) * 64L),
      count: 64,
      width,
    }
    let (part, cost) = encoder_partition(node, true)
    assert_true(cost <= 10L + width.to_int64() * 64L)
    if part.width >= 0 {
      assert_eq(part.width, width)
    }
  }
}

///|
test "encoder all fixed and LPC subframe orders serialized" {
  for kind = 8; kind <= 63; kind = kind + 1 {
    if kind > 12 && kind < 32 {
      continue
    }
    let order = if kind >= 32 { kind - 31 } else { kind - 8 }
    let samples = Array::make(64, 1073741823L)
    let coefficients = if kind >= 32 {
      Array::makei(order, i => if i == 0 { 8192L } else { 0L })
    } else {
      encoder_fixed_coefficients(order)
    }
    let shift = if kind >= 32 { 13 } else { 0 }
    let residual = encoder_predictor(samples, coefficients, shift).unwrap()
    let plan = encoder_residual_plan(residual, order, 6)
    let sub : EncoderSubframe = {
      kind,
      wasted: 0,
      depth: 32,
      samples,
      coefficients,
      shift,
      precision: 15,
      residual,
      plan: Some(plan),
      bits: 0L,
    }
    let out = EncoderBits::new()
    encoder_write_subframe(out, sub)
    out.align()
    let r : FrameBits = { data: out.snapshot(), pos: 0, bit: 0, base: 0L, }
    let decoded = frame_subframe(r, 64, 32)
    assert_eq(decoded[63], 1073741823L)
  }
}

///|
test "encoder domain errors and residual INT32MIN" {
  assert_true(encoder_predictor([-2147483648L], [], 0) is None)
  let format : PcmFormat = {
    sample_rate: 44100,
    channels: 1,
    bits_per_sample: 4,
  }
  let rejected = try {
    ignore(encode_frame(format, [[8]], 0L, false, 0))
    false
  } catch {
    Invalid(_, _) => true
    _ => false
  }
  assert_true(rejected)
  let rejected = try {
    ignore(encode_frame(format, [[]], 0L, false, 0))
    false
  } catch {
    Invalid(_, _) => true
    _ => false
  }
  assert_true(rejected)
}

///|
test "encoder naturally selects LPC for an integer oscillator" {
  let samples : Array[Int64] = [0L, 1000000L]
  for i = 2; i < 1024; i = i + 1 {
    samples.push(((127L * samples[i - 1]) >> 6) - samples[i - 2])
  }
  let sub = encoder_subframe(samples, 24, 4)
  assert_true(sub.kind >= 32)
  let format : PcmFormat = {
    sample_rate: 48000,
    channels: 1,
    bits_per_sample: 24,
  }
  let bytes = encode_frame(
    format,
    [samples.map(x => x.to_int())],
    68719475711L,
    true,
    4,
  )
  let (frame, _) = parse_frame(bytes, 0, encoder_test_info(format, 1024), 0L)
  assert_true(frame.variable_block)
  assert_eq(frame.number, 68719475711L)
  for i = 0; i < 1024; i = i + 1 {
    assert_eq(frame.channels[0][i].to_int64(), samples[i])
  }
}

///|
test "encoder chosen residual cost equals number of serialized bits" {
  for order = 0; order < 5; order = order + 1 {
    let samples = Array::makei(128, i => {
      if i < 64 {
        3L
      } else {
        (i * i - i * 3).to_int64()
      }
    })
    let coefficients = encoder_fixed_coefficients(order)
    let residual = encoder_predictor(samples, coefficients, 0).unwrap()
    let plan = encoder_residual_plan(residual, order, 7)
    let sub : EncoderSubframe = {
      kind: order + 8,
      wasted: 0,
      depth: 16,
      samples,
      coefficients,
      shift: 0,
      precision: 0,
      residual,
      plan: Some(plan),
      bits: 8L + (order * 16).to_int64() + plan.bits,
    }
    let out = EncoderBits::new()
    encoder_write_subframe(out, sub)
    assert_eq(out.bit_length().to_int64(), sub.bits)
  }
}

// Whitebox producer for an EXTERNAL libFLAC gate. Expected PCM comes directly
// from the test signal, never from MoonFLAC's decoder. No force API is public.

///|
fn encoder_fixture_emit(
  name : String,
  subs : Array[EncoderSubframe],
  assignment : Int32,
  expected : Array[Array[Int32]],
) -> Unit {
  let size = expected[0].length()
  let header = EncoderBits::new()
  header.write(0x664c6143L, 32)
  header.write(0x80000022L, 32)
  header.write(size.to_int64(), 16)
  header.write(size.to_int64(), 16)
  header.write(0L, 24)
  header.write(0L, 24)
  header.write(48000L, 20)
  header.write((expected.length() - 1).to_int64(), 3)
  header.write(31L, 5)
  header.write(size.to_int64(), 36)
  for _i = 0; _i < 16; _i = _i + 1 {
    header.write(0L, 8)
  }
  let out = EncoderBits::new()
  out.write(0xfff8L, 16)
  out.write(if size <= 256 { 0x60L } else { 0x70L }, 8)
  out.write((assignment << 4).to_int64(), 8)
  out.write(0L, 8)
  out.write((size - 1).to_int64(), if size <= 256 { 8 } else { 16 })
  let prefix = out.snapshot()
  out.write(frame_crc(prefix, 0, prefix.length(), 8).to_int64(), 8)
  for sub in subs {
    encoder_write_subframe(out, sub)
  }
  out.align()
  let body = out.snapshot()
  out.write(frame_crc(body, 0, body.length(), 16).to_int64(), 16)
  let file = header.snapshot() + out.snapshot()
  let hex = StringBuilder()
  let digits = "0123456789abcdef"
  for byte in file {
    hex.write_char(digits[byte.to_int() >> 4].to_char().unwrap())
    hex.write_char(digits[byte.to_int() & 15].to_char().unwrap())
  }
  let pcm = StringBuilder()
  for i = 0; i < size; i = i + 1 {
    for c = 0; c < expected.length(); c = c + 1 {
      if i != 0 || c != 0 {
        pcm.write_string(",")
      }
      pcm.write_string(expected[c][i].to_string())
    }
  }
  println(
    "ENCODER-FORCED \{name} \{hex.to_string()} \{expected.length()} 32 48000 \{pcm.to_string()}",
  )
}

///|
test "encoder external forced syntax fixtures" {
  for kind = 8; kind <= 63; kind = kind + 1 {
    if kind > 12 && kind < 32 {
      continue
    }
    let order = if kind >= 32 { kind - 31 } else { kind - 8 }
    let samples = Array::make(64, 1073741823L)
    let coefficients = if kind >= 32 {
      Array::makei(order, i => if i == 0 { 8192L } else { 0L })
    } else {
      encoder_fixed_coefficients(order)
    }
    let shift = if kind >= 32 { 13 } else { 0 }
    let residual = encoder_predictor(samples, coefficients, shift).unwrap()
    let sub : EncoderSubframe = {
      kind,
      wasted: 0,
      depth: 32,
      samples,
      coefficients,
      shift,
      precision: 15,
      residual,
      plan: Some(encoder_residual_plan(residual, order, 6)),
      bits: 0L,
    }
    encoder_fixture_emit("kind-\{kind}", [sub], 0, [
      samples.map(x => x.to_int()),
    ])
  }
  for k = 0; k <= 30; k = k + 1 {
    let samples = Array::makei(64, i => if i % 2 == 0 { 0L } else { -1L })
    let plan : EncoderResidual = {
      order: 0,
      rice2: k >= 15,
      parts: [{ parameter: k, width: -1, count: 64, }],
      bits: 0L,
    }
    let sub : EncoderSubframe = {
      kind: 8,
      wasted: 0,
      depth: 32,
      samples,
      coefficients: [],
      shift: 0,
      precision: 0,
      residual: samples,
      plan: Some(plan),
      bits: 0L,
    }
    encoder_fixture_emit("rice-\{k}", [sub], 0, [samples.map(x => x.to_int())])
  }
  for width = 0; width <= 31; width = width + 1 {
    let samples = Array::make(
      64,
      if width == 0 {
        0L
      } else {
        -(1L << (width - 1))
      },
    )
    let plan : EncoderResidual = {
      order: 0,
      rice2: false,
      parts: [{ parameter: 15, width, count: 64, }],
      bits: 0L,
    }
    let sub : EncoderSubframe = {
      kind: 8,
      wasted: 0,
      depth: 32,
      samples,
      coefficients: [],
      shift: 0,
      precision: 0,
      residual: samples,
      plan: Some(plan),
      bits: 0L,
    }
    encoder_fixture_emit("escape-\{width}", [sub], 0, [
      samples.map(x => x.to_int()),
    ])
  }
  for wasted = 1; wasted <= 31; wasted = wasted + 1 {
    let samples = Array::make(64, -1L)
    let sub : EncoderSubframe = {
      kind: 0,
      wasted,
      depth: 32 - wasted,
      samples,
      coefficients: [],
      shift: 0,
      precision: 0,
      residual: [],
      plan: None,
      bits: 0L,
    }
    encoder_fixture_emit("wasted-\{wasted}", [sub], 0, [
      Array::make(64, (-1L << wasted).to_int()),
    ])
  }
  for assignment in [1, 8, 9, 10] {
    let a = if assignment == 1 || assignment == 8 {
      2147483647L
    } else if assignment == 9 {
      4294967295L
    } else {
      -1L
    }
    let b = if assignment == 1 || assignment == 9 {
      -2147483648L
    } else {
      4294967295L
    }
    let subs = [
      encoder_subframe(
        Array::make(64, a),
        if assignment == 9 {
          33
        } else {
          32
        },
        0,
      ),
      encoder_subframe(
        Array::make(64, b),
        if assignment >= 8 && assignment != 9 {
          33
        } else {
          32
        },
        0,
      ),
    ]
    encoder_fixture_emit("stereo-\{assignment}", subs, assignment, [
      Array::make(64, 2147483647),
      Array::make(64, -2147483648),
    ])
  }
  let samples = Array::makei(64, i => (i * 7919 - 200000).to_int64())
  let sub : EncoderSubframe = {
    kind: 1,
    wasted: 0,
    depth: 32,
    samples,
    coefficients: [],
    shift: 0,
    precision: 0,
    residual: [],
    plan: None,
    bits: 0L,
  }
  encoder_fixture_emit("verbatim", [sub], 0, [samples.map(x => x.to_int())])
  let samples = Array::make(32768, 0L)
  let plan : EncoderResidual = {
    order: 15,
    rice2: false,
    parts: Array::makei(32768, _ => { parameter: 0, width: -1, count: 1, }),
    bits: 0L,
  }
  let sub : EncoderSubframe = {
    kind: 8,
    wasted: 0,
    depth: 32,
    samples,
    coefficients: [],
    shift: 0,
    precision: 0,
    residual: samples,
    plan: Some(plan),
    bits: 0L,
  }
  encoder_fixture_emit("partition-15", [sub], 0, [Array::make(32768, 0)])
}

///|
test "encoder naturally selects left side right side and mid side" {
  let mut state = 12345U
  let noise = Array::makei(256, _ => {
    state = state * 1664525U + 1013904223U
    ((state >> 18).to_int() - 8192) * 4
  })
  let format : PcmFormat = {
    sample_rate: 48000,
    channels: 2,
    bits_per_sample: 16,
  }
  for assignment in [8, 9, 10] {
    let left = if assignment == 9 { noise.map(x => x + 1) } else { noise }
    let right = if assignment == 8 {
      noise.map(x => x + 1)
    } else if assignment == 9 {
      noise
    } else {
      noise.map(x => -x)
    }
    let bytes = encode_frame(format, [left, right], 0L, false, 1)
    assert_eq(bytes[3].to_int() >> 4, assignment)
  }
}

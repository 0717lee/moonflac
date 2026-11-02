// Independent scalar oracle: rescan residual samples for every candidate.
// No quotient tree, convex search, CLZ width, or production planning helper.

///|
fn plan_oracle(
  samples : Array[Int64],
  predictor : Int32,
  max_partition : Int32,
) -> EncoderResidual {
  let mut best : EncoderResidual = {
    order: 0,
    rice2: false,
    parts: [],
    bits: 9223372036854775807L,
  }
  // Ascending order and Rice first implement all plan ties by strict <.
  for order = 0; order <= max_partition; order = order + 1 {
    let partitions = 1 << order
    if samples.length() % partitions != 0 ||
      samples.length() / partitions <= predictor {
      continue
    }
    let size = samples.length() / partitions
    for rice2 in [false, true] {
      let pb = if rice2 { 5 } else { 4 }
      let maximum = if rice2 { 30 } else { 14 }
      let parts : Array[EncoderPartition] = []
      let mut bits = 6L
      for p = 0; p < partitions; p = p + 1 {
        let start = if p == 0 { predictor } else { p * size }
        let end = (p + 1) * size
        let count = end - start
        let mut width = 0
        for i = start; i < end; i = i + 1 {
          let value = samples[i]
          let mut w = if value == 0L { 0 } else { 1 }
          while w > 0 && (value < -(1L << (w - 1)) || value >= 1L << (w - 1)) {
            w += 1
          }
          if w > width {
            width = w
          }
        }
        let mut cost = 9223372036854775807L
        let mut parameter = 0
        let mut escape_width = -1
        for k = 0; k <= maximum; k = k + 1 {
          let mut candidate = pb.to_int64()
          for i = start; i < end; i = i + 1 {
            let value = samples[i]
            let folded = if value < 0L {
              -(value + 1L) * 2L + 1L
            } else {
              value * 2L
            }
            candidate += (folded >> k) + (k + 1).to_int64()
          }
          if candidate < cost {
            cost = candidate
            parameter = k
          }
        }
        let escaped = (pb + 5).to_int64() + count.to_int64() * width.to_int64()
        if width <= 31 && escaped < cost {
          cost = escaped
          parameter = (1 << pb) - 1
          escape_width = width
        }
        parts.push({ parameter, width: escape_width, count, })
        bits += cost
      }
      if bits < best.bits {
        best = { order, rice2, parts, bits, }
      }
    }
  }
  best
}

///|
fn plan_oracle_equal(
  actual : EncoderResidual,
  expected : EncoderResidual,
) -> Unit raise {
  assert_eq(actual.bits, expected.bits)
  assert_eq(actual.order, expected.order)
  assert_eq(actual.rice2, expected.rice2)
  assert_eq(actual.parts.length(), expected.parts.length())
  for i = 0; i < expected.parts.length(); i = i + 1 {
    assert_eq(actual.parts[i].parameter, expected.parts[i].parameter)
    assert_eq(actual.parts[i].width, expected.parts[i].width)
    assert_eq(actual.parts[i].count, expected.parts[i].count)
  }
}

///|
test "residual plan oracle exhaustive small distributions and warmups" {
  let alphabet = [-2L, -1L, 0L, 1L, 2L]
  let mut combinations = 1
  for size = 1; size <= 5; size = size + 1 {
    combinations *= alphabet.length()
    for code = 0; code < combinations; code = code + 1 {
      let mut digits = code
      let samples = Array::make(size, 0L)
      for i = 0; i < size; i = i + 1 {
        samples[i] = alphabet[digits % alphabet.length()]
        digits /= alphabet.length()
      }
      for predictor = 0; predictor < size; predictor = predictor + 1 {
        plan_oracle_equal(
          encoder_residual_plan(samples, predictor, 4),
          plan_oracle(samples, predictor, 4),
        )
      }
    }
  }
}

///|
test "residual plan oracle nonstationary boundary widths and ownership" {
  let mut state = 96392026U
  let workspace : Array[Array[Int64]] = []
  for trial = 0; trial < 256; trial = trial + 1 {
    let size = if trial % 3 == 0 { 1 << (trial % 9) } else { 1 + trial }
    let predictor = trial % (if size < 33 { size } else { 33 })
    let samples = Array::make(size, 0L)
    for i = 0; i < size; i = i + 1 {
      state = state * 1664525U + 1013904223U
      samples[i] = if i < predictor {
        // Warmup values must not enter the first residual partition.
        1099511627775L
      } else if trial % 4 == 0 {
        let edges = [
          -2147483648L, -1073741825L, -1073741824L, 1073741823L, 1073741824L, 2147483647L,
          0L,
        ]
        edges[i % edges.length()]
      } else {
        state.reinterpret_as_int().to_int64() >> ((i / 7 + trial) % 32)
      }
    }
    let expected = plan_oracle(samples, predictor, 15)
    let retained = encoder_residual_plan(samples, predictor, 15, workspace~)
    plan_oracle_equal(retained, expected)
    // Mutate the source and reuse planning storage at different dimensions.
    for i = 0; i < size; i = i + 1 {
      samples[i] = 0L
    }
    plan_oracle_equal(
      encoder_residual_plan(samples, 0, 0, workspace~),
      plan_oracle(samples, 0, 0),
    )
    let later = Array::make(512, -123456789L)
    plan_oracle_equal(
      encoder_residual_plan(later, 31, 15, workspace~),
      plan_oracle(later, 31, 15),
    )
    let tiny = [0L, 0L]
    plan_oracle_equal(
      encoder_residual_plan(tiny, 1, 15, workspace~),
      plan_oracle(tiny, 1, 15),
    )
    plan_oracle_equal(retained, expected)
  }
}

///|
test "residual plan oracle explicit parameter escape and method ties" {
  // Folded 1 ties k=0 and k=1; keep the earliest Rice parameter.
  let parameter_tie = encoder_residual_plan([-1L], 0, 15)
  plan_oracle_equal(parameter_tie, plan_oracle([-1L], 0, 15))
  assert_eq(parameter_tie.parts[0].parameter, 0)
  assert_eq(parameter_tie.parts[0].width, -1)
  // Five zeros cost five unary bits, exactly the escape width field.
  let escape_tie = encoder_residual_plan(Array::make(5, 0L), 0, 15)
  assert_eq(escape_tie.parts[0].parameter, 0)
  assert_eq(escape_tie.parts[0].width, -1)
  let escape_wins = encoder_residual_plan(Array::make(6, 0L), 0, 15)
  assert_eq(escape_wins.parts[0].parameter, 15)
  assert_eq(escape_wins.parts[0].width, 0)
  // Rice2 can pay one extra parameter bit to save exactly one residual bit.
  // The oracle chooses Rice first whenever complete method costs tie.
  for value in [8191L, 8192L, 16383L, 16384L, 32767L, 32768L] {
    let samples = [value, -value - 1L, 0L]
    plan_oracle_equal(
      encoder_residual_plan(samples, 0, 15),
      plan_oracle(samples, 0, 15),
    )
  }
}

///|
test "residual plan oracle maximum partition and nondivisible maximum block" {
  for case in [(32768, 0), (65535, 32), (1024, 31)] {
    let (size, predictor) = case
    let samples = Array::make(size, 0L)
    for i = 0; i < size; i = i + 1 {
      samples[i] = if i % 19 == 0 { 1073741823L } else { 0L }
    }
    plan_oracle_equal(
      encoder_residual_plan(samples, predictor, 15),
      plan_oracle(samples, predictor, 15),
    )
  }
}

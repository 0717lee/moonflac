///|
fn fixed_specialized_compare(
  samples : Array[Int64],
  order : Int32,
  depth : Int32,
) -> Unit raise {
  let coefficients = encoder_fixed_coefficients(order)
  let old = EncoderPlanScratch::new()
  let proposed = EncoderPlanScratch::new()
  // Reuse nonzero buffers to prove warm-up clearing is part of the contract.
  old.residual = Array::make(samples.length(), 123456789L)
  proposed.residual = Array::make(samples.length(), -123456789L)
  let expected = old.predict(samples, coefficients, 0)
  let actual = proposed.predict_fixed(samples, coefficients, depth)
  assert_eq(actual, expected)
  if actual {
    assert_eq(proposed.residual, old.residual)
  }
  for i = 0; i < order && i < samples.length(); i = i + 1 {
    assert_eq(proposed.residual[i], 0L)
  }
}

///|
test "fixed specialization all depths orders and extremal patterns match generic" {
  // Depth1..3 represents wasted-bit reduction; depth33 is a stereo side plane.
  for depth = 1; depth <= 33; depth = depth + 1 {
    let low = -(1L << (depth - 1))
    let high = -low - 1L
    for order = 0; order <= 4; order = order + 1 {
      for size in [0, 1, 2, 3, 4, 5, 16, 31, 64, 257] {
        fixed_specialized_compare(Array::make(size, low), order, depth)
        fixed_specialized_compare(Array::make(size, high), order, depth)
        fixed_specialized_compare(
          Array::makei(size, i => if i % 2 == 0 { low } else { high }),
          order,
          depth,
        )
        fixed_specialized_compare(
          Array::makei(size, i => if i % 3 == 0 { high } else { low }),
          order,
          depth,
        )
      }
    }
  }
}

///|
test "fixed specialization deterministic random long blocks and scratch ownership" {
  for depth = 4; depth <= 32; depth = depth + 1 {
    let mask = (1L << depth) - 1L
    let low = -(1L << (depth - 1))
    for size in [17, 256, 4096] {
      let mut state = 9639U + depth.to_uint()
      let samples = Array::makei(size, _ => {
        state = state * 1664525U + 1013904223U
        (state.to_int64() & mask) + low
      })
      for order = 0; order <= 4; order = order + 1 {
        fixed_specialized_compare(samples, order, depth)
      }
    }
  }
  let samples = Array::makei(65535, i => (i * 19 % 1048576).to_int64() - 524288L)
  for order = 0; order <= 4; order = order + 1 {
    fixed_specialized_compare(samples, order, 20)
  }
  let scratch = EncoderPlanScratch::new()
  assert_true(
    scratch.predict_fixed(
      [7L, -8L, 7L, -8L, 7L],
      encoder_fixed_coefficients(4),
      4,
    ),
  )
  let winner = scratch.residual.copy()
  assert_true(
    scratch.predict_fixed(
      [1L, 2L, 3L, 4L, 5L],
      encoder_fixed_coefficients(1),
      4,
    ),
  )
  assert_eq(winner, [0L, 0L, 0L, 0L, 120L])
}

///|
test "fixed specialization exact signed31 bound and generic fallback exclusion" {
  for order = 1; order <= 4; order = order + 1 {
    let depth = 32 - order
    let low = -(1L << (depth - 1))
    let high = -low - 1L
    let weights = match order {
      1 => [1, -1]
      2 => [1, -2, 1]
      3 => [1, -3, 3, -1]
      _ => [1, -4, 6, -4, 1]
    }
    let samples = Array::makei(order + 1, i => {
      if weights[order - i] > 0 {
        high
      } else {
        low
      }
    })
    let scratch = EncoderPlanScratch::new()
    assert_true(
      scratch.predict_fixed(samples, encoder_fixed_coefficients(order), depth),
    )
    assert_eq(
      scratch.residual[order],
      (1L << (order - 1)) * ((1L << depth) - 1L),
    )
    assert_true(scratch.residual[order] < 2147483648L)
  }
  let scratch = EncoderPlanScratch::new()
  assert_true(!scratch.predict_fixed([-2147483648L], [], 32))
  assert_true(!scratch.predict_fixed([-2147483648L, 2147483647L], [1L], 32))
}

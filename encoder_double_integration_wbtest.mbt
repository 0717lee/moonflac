///|
test "C10 fixed specialization remains separate from lazy Double scratch" {
  let scratch = EncoderPlanScratch::new()
  let samples = Array::makei(257, i => (i % 17 - 8).to_int64())
  for order = 0; order <= 4; order = order + 1 {
    let coefficients = encoder_fixed_coefficients(order)
    let expected = Array::make(samples.length(), 0L)
    let legal = encoder_predict_into_integer_reference(
      samples, coefficients, 0, expected,
    )
    assert_eq(scratch.predict_fixed(samples, coefficients, 16), legal)
    assert_eq(scratch.residual, expected)
    assert_eq(scratch.double_tile.length(), 0)
  }
}

///|
test "C10 Double tile reuses capacity without leaking planes or failed suffix" {
  let scratch = EncoderPlanScratch::new()
  for size in [257, 33, 129, 4096, 1, 257] {
    for depth in [4, 16, 32, 33] {
      let bound = 1L << (depth - 1)
      let samples = Array::makei(size, i => {
        if i % 2 == 0 {
          -bound
        } else {
          bound - 1L
        }
      })
      let coefficients = [1L, -1L]
      let expected = Array::make(size, 7654321L)
      scratch.residual = Array::make(size, 7654321L)
      for i = 0; i < 2 && i < size; i = i + 1 {
        expected[i] = 0L
      }
      let legal = encoder_predict_into_integer_reference(
        samples, coefficients, 1, expected,
      )
      assert_eq(
        scratch.predict_lpc_double(
          samples,
          encoder_lpc_double_signal(samples, depth),
          coefficients,
          1,
        ),
        legal,
      )
      assert_eq(scratch.residual, expected)
      assert_eq(scratch.double_tile.length(), 128)
    }
  }
  // Explicit absent/mismatched signal routes still honor integer semantics.
  let values = [1L, 2L, 3L]
  assert_true(scratch.predict_lpc_double(values, None, [1L], 0))
  assert_eq(scratch.residual, [0L, 1L, 1L])
  assert_true(
    scratch.predict_lpc_double(values, Some(FixedArray::make(1, 0.0)), [1L], 0),
  )
  assert_eq(scratch.residual, [0L, 1L, 1L])
}

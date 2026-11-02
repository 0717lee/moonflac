///|
fn fixed_integer_tiles_compare(
  samples : Array[Int64],
  order : Int32,
) -> Unit raise {
  let coefficients = encoder_fixed_coefficients(order)
  let expected = Array::make(samples.length(), 777L)
  let actual = Array::make(samples.length(), 777L)
  let expected_valid = encoder_predict_into(samples, coefficients, 0, expected)
  let actual_valid = encoder_fixed_integer_tiles(
    samples,
    order,
    actual,
    FixedArray::make(128, 333L),
  )
  assert_eq(actual_valid, expected_valid)
  // Includes untouched suffix after the first invalid residual and warmups.
  assert_eq(actual, expected)
}

///|
test "fixed integer tiles exact prefix across boundaries and signed extremes" {
  for size in [0, 1, 4, 5, 127, 128, 129, 132, 133, 255, 256, 257, 65535] {
    for order = 0; order <= 4; order = order + 1 {
      fixed_integer_tiles_compare(
        Array::makei(size, i => i.to_int64() * 8191L),
        order,
      )
      fixed_integer_tiles_compare(Array::make(size, -2147483648L), order)
      fixed_integer_tiles_compare(Array::make(size, 4294967295L), order)
      fixed_integer_tiles_compare(
        Array::makei(size, i => {
          if i % 2 == 0 {
            -4294967296L
          } else {
            4294967295L
          }
        }),
        order,
      )
      for invalid_at in [0, 4, 127, 128, 129, 132, 255] {
        fixed_integer_tiles_compare(
          Array::makei(size, i => {
            if i == invalid_at {
              -2147483648L
            } else {
              0L
            }
          }),
          order,
        )
      }
    }
  }
}

///|
test "fixed integer tiles deterministic full depth and reused scratch" {
  for depth = 28; depth <= 33; depth = depth + 1 {
    let low = -(1L << (depth - 1))
    let mask = (1L << depth) - 1L
    let mut state = 9639U
    let samples = Array::makei(1025, _ => {
      state = state * 1664525U + 1013904223U
      let high = state.to_int64()
      state = state * 1664525U + 1013904223U
      (((high << 16) | state.to_int64()) & mask) + low
    })
    for order = 0; order <= 4; order = order + 1 {
      fixed_integer_tiles_compare(samples, order)
    }
  }
  let scratch = EncoderPlanScratch::new()
  assert_true(scratch.predict_fixed([0L, 1L, 2L, 3L, 4L], [1L], 32))
  let retained = scratch.residual.copy()
  assert_true(!scratch.predict_fixed([0L, -2147483648L, 0L], [1L], 32))
  assert_eq(retained, [0L, 1L, 1L, 1L, 1L])
  assert_true(scratch.predict_fixed([7L, 7L, 7L, 7L, 7L], [1L], 33))
  assert_eq(scratch.residual, [0L, 0L, 0L, 0L, 0L])
}

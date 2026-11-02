///|
fn caller_variance_compare_models(
  samples : Array[Int64],
  order : Int32,
) -> Unit raise {
  let no_old = caller_variance_frozen_models(samples, order)
  let no_new = encoder_lpc_models(samples, order)
  assert_eq(no_old.length(), no_new.length())
  for i = 0; i < no_old.length(); i = i + 1 {
    assert_eq(no_old[i].coefficients, no_new[i].coefficients)
    assert_eq(no_old[i].shift, no_new[i].shift)
    assert_eq(no_old[i].precision, no_new[i].precision)
  }
  let old_variances : Array[Double?] = []
  let new_variances : Array[Double?] = []
  let expected = caller_variance_frozen_models(
    samples,
    order,
    variances=Some(old_variances),
  )
  let actual = encoder_lpc_models(samples, order, variances=Some(new_variances))
  assert_eq(actual.length(), expected.length())
  assert_eq(new_variances.length(), old_variances.length())
  for i = 0; i < actual.length(); i = i + 1 {
    assert_eq(actual[i].coefficients, expected[i].coefficients)
    assert_eq(actual[i].shift, expected[i].shift)
    assert_eq(actual[i].precision, expected[i].precision)
    match (new_variances[i], old_variances[i]) {
      (Some(a), Some(b)) =>
        assert_eq(a.reinterpret_as_uint64(), b.reinterpret_as_uint64())
      (None, None) => ()
      _ => fail("variance presence differs")
    }
  }
}

///|
test "Caller variance frozen C93 model ordering and variance IEEE bits" {
  // Invalid unused lag3 must not force the order2 model onto old full matrix.
  let zero = 0.0
  let correlations = [5.0, 2.0, 1.0, zero / zero]
  let model : LpcModel = { coefficients: [1L, 1L], shift: 1, precision: 2, }
  let full_valid = encoder_lpc_variance_inputs(correlations, 3, 2.0, 4.0)
  assert_eq(full_valid, false)
  assert_eq(encoder_lpc_variance_inputs(correlations, 2, 2.0, 4.0), true)
  let selected = if full_valid {
    encoder_lpc_variance_triangle(correlations, model, 2.0, 4.0)
  } else {
    encoder_lpc_variance(correlations, model, 2.0, 4.0)
  }
  assert_eq(selected, Some(5.5))
  match
    (selected, encoder_lpc_variance_triangle(correlations, model, 2.0, 4.0)) {
    (Some(a), Some(b)) =>
      assert_eq(a.reinterpret_as_uint64(), b.reinterpret_as_uint64())
    _ => fail("unused invalid higher lag changed lower model")
  }

  let mut state = 720073U
  for depth in [4, 8, 16, 24, 32, 33] {
    let low = -(1L << (depth - 1))
    let mask = (1L << depth) - 1L
    for size in [2, 17, 64, 257, 1024] {
      for pattern = 0; pattern < 4; pattern = pattern + 1 {
        let samples = Array::makei(size, i => {
          state = state * 1664525U + 1013904223U
          if pattern == 0 {
            if i == size / 2 {
              -low - 1L
            } else {
              0L
            }
          } else if pattern == 1 {
            (state.to_int64() & mask) + low
          } else if pattern == 2 {
            ((i % 7).to_int64() & mask) + low
          } else if i % 2 == 0 {
            low
          } else {
            -low - 1L
          }
        })
        for order = 1; order <= 32; order = order + 1 {
          caller_variance_compare_models(samples, order)
        }
      }
    }
  }
  let extremes : Array[Int64] = [
    -9223372036854775808L, 9223372036854775807L, 0L, 9007199254740993L, -9007199254740993L,
  ]
  for order = 1; order <= 32; order = order + 1 {
    caller_variance_compare_models(
      Array::makei(65, i => extremes[i % extremes.length()]),
      order,
    )
  }
  caller_variance_compare_models([], 32)
  caller_variance_compare_models([0L], 32)
  caller_variance_compare_models(Array::make(65, 0L), 32)
}

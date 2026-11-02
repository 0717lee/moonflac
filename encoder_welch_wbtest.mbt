///|
test "Welch loop signal and ascending energy IEEE bits across tails and bounds" {
  let edges : Array[Int64] = [
    0L, 1L, -1L, -9223372036854775808L, 9223372036854775807L, 9007199254740991L,
    9007199254740993L, -9007199254740993L, -4294967296L, 4294967295L,
  ]
  for
    size in [
      0, 1, 2, 3, 4, 5, 6, 7, 8, 15, 16, 17, 31, 32, 33, 127, 128, 129, 65535, 65536,
    ] {
    let samples = Array::makei(size, i => edges[i % edges.length()])
    for peak in [1.0, 3.0, 4294967296.0, 9223372036854775808.0] {
      for energy in [false, true] {
        let (expected, old_energy) = welch_frozen_signal(samples, peak, energy)
        let (actual, new_energy) = encoder_lpc_welch(samples, peak, energy)
        assert_eq(actual.length(), expected.length())
        assert_eq(
          new_energy.reinterpret_as_uint64(),
          old_energy.reinterpret_as_uint64(),
        )
        for i = 0; i < size; i = i + 1 {
          assert_eq(
            actual[i].reinterpret_as_uint64(),
            expected[i].reinterpret_as_uint64(),
          )
        }
      }
    }
  }
}

///|
fn welch_compare_models(samples : Array[Int64], order : Int32) -> Unit raise {
  let no_old = welch_frozen_models(samples, order)
  let no_new = encoder_lpc_models(samples, order)
  assert_eq(no_old.length(), no_new.length())
  for i = 0; i < no_old.length(); i = i + 1 {
    assert_eq(no_old[i].coefficients, no_new[i].coefficients)
    assert_eq(no_old[i].shift, no_new[i].shift)
    assert_eq(no_old[i].precision, no_new[i].precision)
  }
  let old_variances : Array[Double?] = []
  let new_variances : Array[Double?] = []
  let expected = welch_frozen_models(
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
test "Welch loop frozen model ordering and variance IEEE bits" {
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
          welch_compare_models(samples, order)
        }
      }
    }
  }
  let extremes : Array[Int64] = [
    -9223372036854775808L, 9223372036854775807L, 0L, 9007199254740993L, -9007199254740993L,
  ]
  for order = 1; order <= 32; order = order + 1 {
    welch_compare_models(
      Array::makei(65, i => extremes[i % extremes.length()]),
      order,
    )
  }
  welch_compare_models([], 32)
  welch_compare_models([0L], 32)
  welch_compare_models(Array::make(65, 0L), 32)
}

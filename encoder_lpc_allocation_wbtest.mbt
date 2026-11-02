///|
fn lpc_allocation_compare_quantizer(
  coefficients : Array[Double],
  precision : Int32,
) -> Unit raise {
  let actual = encoder_lpc_quantize(coefficients, precision)
  let expected = lpc_allocation_frozen_quantize(coefficients, precision)
  match (actual, expected) {
    (Some(a), Some(b)) => {
      assert_eq(a.coefficients, b.coefficients)
      assert_eq(a.shift, b.shift)
      assert_eq(a.precision, b.precision)
      let retained = a.coefficients.copy()
      ignore(encoder_lpc_quantize([0.0, 1000000.0, 0.0], precision))
      ignore(encoder_lpc_quantize([1.98, -0.99, 0.001], precision))
      assert_eq(a.coefficients, retained)
    }
    (None, None) => ()
    _ => fail("quantizer validity differs")
  }
}

///|
test "local LPC allocation quantizer retries boundaries stale suffix and ownership" {
  for precision in [12, 15] {
    for
      coefficients in [
        [],
        [0.0],
        [2047.0 / 32768.0],
        [-2048.0 / 32768.0],
        [0.5 / 32768.0, -0.5 / 32768.0],
        [0.001, 0.09, -0.001],
        [1.98, -0.99],
        [0.0, 4096.0, 0.1],
        [0.01, 1000000.0, 0.02],
      ] {
      lpc_allocation_compare_quantizer(coefficients, precision)
    }
    for length in [1, 2, 3, 15, 16, 31, 32] {
      for failed_at = 0; failed_at < length; failed_at = failed_at + 1 {
        for
          value in [
            0.09,
            1.98,
            4096.0,
            1000000.0,
            0x7ff8000000000000UL.reinterpret_as_double(),
            0x7ff0000000000000UL.reinterpret_as_double(),
            0xfff0000000000000UL.reinterpret_as_double(),
          ] {
          let coefficients = Array::makei(length, i => {
            if i == failed_at {
              value
            } else {
              (i + 1).to_double() / 65536.0
            }
          })
          lpc_allocation_compare_quantizer(coefficients, precision)
        }
      }
    }
  }
}

///|
test "local LPC allocation frozen models variance bits all symmetric pairs and middles" {
  let mut state = 660031U
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
          let old_variances : Array[Double?] = []
          let new_variances : Array[Double?] = []
          let expected = lpc_allocation_frozen_models(
            samples,
            order,
            variances=Some(old_variances),
          )
          let actual = encoder_lpc_models(
            samples,
            order,
            variances=Some(new_variances),
          )
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
      }
    }
  }
}

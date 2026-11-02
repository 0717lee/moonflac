// Candidate4 integer dot-product reference.

///|
fn encoder_predict_into_integer_reference(
  samples : Array[Int64],
  coefficients : Array[Int64],
  shift : Int32,
  residual : Array[Int64],
) -> Bool {
  let order = coefficients.length()
  for i = order; i < samples.length(); i = i + 1 {
    let mut prediction = 0L
    for j = 0; j < order; j = j + 1 {
      // j<order<=i<size proves both coefficient and history bounds.
      prediction += coefficients.unsafe_get(j) * samples.unsafe_get(i - j - 1)
    }
    let value = samples.unsafe_get(i) - (prediction >> shift)
    if value <= -2147483648L || value >= 2147483648L {
      return false
    }
    residual.unsafe_set(i, value)
  }
  true
}

///|
fn double_predictor_compare(
  samples : Array[Int64],
  coefficients : Array[Int64],
  shift : Int32,
  depth : Int32,
) -> Unit raise {
  let old = EncoderPlanScratch::new()
  let proposed = EncoderPlanScratch::new()
  old.residual = Array::make(samples.length(), 123456789L)
  proposed.residual = Array::make(samples.length(), 123456789L)
  let saved = samples.copy()
  for i = 0; i < coefficients.length() && i < samples.length(); i = i + 1 {
    old.residual[i] = 0L
  }
  let expected = encoder_predict_into_integer_reference(
    samples,
    coefficients,
    shift,
    old.residual,
  )
  let actual = proposed.predict_lpc_double(
    samples,
    encoder_lpc_double_signal(samples, depth),
    coefficients,
    shift,
  )
  assert_eq(actual, expected)
  // Separate Double tiles leave even the failed suffix identical to integer.
  assert_eq(proposed.residual, old.residual)
  assert_eq(samples, saved)
}

///|
test "Double tiled LPC exact at every depth order and legal shift" {
  for depth = 4; depth <= 33; depth = depth + 1 {
    let low = -(1L << (depth - 1))
    let high = -low - 1L
    let samples = Array::makei(193, i => if i % 3 == 0 { low } else { high })
    for order = 1; order <= 32; order = order + 1 {
      let coefficients = Array::makei(order, i => {
        if i % 2 == 0 {
          -16384L
        } else {
          16383L
        }
      })
      for shift = 0; shift <= 15; shift = shift + 1 {
        double_predictor_compare(samples, coefficients, shift, depth)
      }
    }
  }
}

///|
test "Double tiled LPC integer product and partial-sum proof boundaries" {
  for
    sample in [
      -4294967296L, -4294967295L, -2147483648L, 0L, 2147483647L, 4294967295L,
    ] {
    for coefficient in [-16384L, -8193L, -1L, 0L, 1L, 8193L, 16383L] {
      let mut integer = 0L
      let mut exact = 0.0
      for _i = 0; _i < 32; _i = _i + 1 {
        integer += sample * coefficient
        exact += sample.to_double() * coefficient.to_double()
        assert_eq(exact.to_int64(), integer)
      }
    }
  }
  let negative = [-31L, 0L]
  for shift = 0; shift <= 15; shift = shift + 1 {
    double_predictor_compare(negative, [1L], shift, 6)
  }
}

///|
test "Double tiled LPC randomized coefficients tile edges and fallback" {
  for depth in [4, 16, 24, 32, 33] {
    let mask = (1L << depth) - 1L
    let low = -(1L << (depth - 1))
    for
      size in [
        0, 1, 31, 32, 33, 127, 128, 129, 159, 160, 161, 255, 256, 257, 4096,
      ] {
      let mut state = 9639U + size.to_uint()
      let samples = Array::makei(size, _ => {
        state = state * 1664525U + 1013904223U
        ((state.to_int64() * 2L) & mask) + low
      })
      for order in [1, 2, 4, 8, 16, 24, 32] {
        let coefficients = Array::makei(order, _ => {
          state = state * 1664525U + 1013904223U
          (state.to_int64() & 32767L) - 16384L
        })
        for shift in [0, 7, 15] {
          double_predictor_compare(samples, coefficients, shift, depth)
        }
      }
    }
  }
  for failed_at in [1, 127, 128, 129, 255, 256, 299] {
    let samples = Array::make(300, 0L)
    samples[failed_at] = -2147483648L
    double_predictor_compare(samples, [1L], 0, 32)
  }
  for shift in [-1, 16, 63, 64] {
    double_predictor_compare(
      [4294967295L, -4294967296L, 0L],
      [16383L],
      shift,
      33,
    )
  }
  double_predictor_compare([0L, 1L, 2L], [16384L], 0, 4)
  double_predictor_compare([0L, 1L, 2L], [-16385L], 0, 4)
  double_predictor_compare([4294967296L, 0L], [1L], 0, 34)
  double_predictor_compare([4294967296L, 0L], [1L], 0, 33)
  double_predictor_compare([-2147483648L], [], 0, 32)
  double_predictor_compare(Array::make(64, 1L), Array::make(33, 1L), 0, 4)
  let long = Array::makei(65535, i => (i * 17 % 65536).to_int64() - 32768L)
  double_predictor_compare(long, [8192L, -4096L], 13, 16)
}

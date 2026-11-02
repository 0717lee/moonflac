// Frozen scalar lag-outer reference from the prototype5 starting snapshot.

///|
fn encoder_lpc_models_sequential_reference(
  samples : Array[Int64],
  max_order : Int32,
) -> Array[LpcModel] {
  let models : Array[LpcModel] = []
  if samples.length() < 2 || max_order < 1 {
    return models
  }
  let limit = if max_order > 32 { 32 } else { max_order }
  let order_limit = if limit >= samples.length() {
    samples.length() - 1
  } else {
    limit
  }
  let mut peak = 0.0
  for sample in samples {
    let magnitude = sample.to_double().abs()
    if magnitude > peak {
      peak = magnitude
    }
  }
  if peak == 0.0 {
    return models
  }
  let n = samples.length()
  let signal = Array::makei(n, i => {
    // Half-sample endpoints keep even a two-sample input observable.
    let position = (2.0 * i.to_double() + 1.0) / n.to_double() - 1.0
    samples[i].to_double() / peak * (1.0 - position * position)
  })
  let correlation = Array::make(order_limit + 1, 0.0)
  for lag in 0..<=order_limit {
    let mut sum = 0.0
    for i = lag; i < n; i = i + 1 {
      sum += signal[i] * signal[i - lag]
    }
    correlation[lag] = sum
  }
  let mut error = correlation[0]
  if error <= 0.0 || error.is_nan() || error.is_inf() {
    return models
  }
  let mut coefficients : Array[Double] = []
  for order in 1..<=order_limit {
    let mut numerator = correlation[order]
    for j in 1..<order {
      numerator -= coefficients[j - 1] * correlation[order - j]
    }
    let reflection = numerator / error
    if reflection.is_nan() || reflection.is_inf() || reflection.abs() >= 1.0 {
      break
    }
    let next = Array::makei(order, j => {
      if j == order - 1 {
        reflection
      } else {
        coefficients[j] - reflection * coefficients[order - j - 2]
      }
    })
    coefficients = next
    for precision in [12, 15] {
      if encoder_lpc_quantize(coefficients, precision) is Some(model) {
        let duplicate = match models.last() {
          Some(previous) =>
            previous.shift == model.shift &&
            previous.coefficients == model.coefficients
          None => false
        }
        if !duplicate {
          models.push(model)
        }
      }
    }
    error *= 1.0 - reflection * reflection
    if error <= correlation[0] * 1.0e-14 {
      break
    }
  }
  models
}

///|
fn lpc_interchange_compare(samples : Array[Int64], order : Int32) -> Unit raise {
  let expected = encoder_lpc_models_sequential_reference(samples, order)
  let actual = encoder_lpc_models(samples, order)
  assert_eq(actual.length(), expected.length())
  for i = 0; i < actual.length(); i = i + 1 {
    assert_eq(actual[i].coefficients, expected[i].coefficients)
    assert_eq(actual[i].shift, expected[i].shift)
    assert_eq(actual[i].precision, expected[i].precision)
  }
}

///|
test "LPC interchange matches sequential reference at every order and small boundary" {
  for size in [0, 1, 2, 3, 15, 16, 31, 32, 33, 63, 64, 65, 255, 256, 257] {
    for order = 0; order <= 33; order = order + 1 {
      lpc_interchange_compare(Array::make(size, 0L), order)
      lpc_interchange_compare(Array::make(size, 1L), order)
      lpc_interchange_compare(
        Array::makei(size, i => {
          if i % 2 == 0 {
            -4294967295L
          } else {
            4294967295L
          }
        }),
        order,
      )
      let mut state = 9639U + size.to_uint()
      let noise = Array::makei(size, _ => {
        state = state * 1664525U + 1013904223U
        state.to_int64() * 2L - 4294967295L
      })
      lpc_interchange_compare(noise, order)
    }
  }
}

///|
test "LPC interchange matches wide random and impulse inputs through maximal blocks" {
  for size in [511, 512, 1023, 1024, 4095, 4096, 4097, 32768, 65535] {
    for order in [1, 2, 8, 16, 24, 32] {
      let mut state = 1337U + size.to_uint()
      let noise = Array::makei(size, _ => {
        state = state * 1664525U + 1013904223U
        state.to_int64() - 2147483648L
      })
      lpc_interchange_compare(noise, order)
      lpc_interchange_compare(
        Array::makei(size, i => {
          if i == size / 2 {
            4294967295L
          } else if i == 0 {
            -4294967295L
          } else {
            0L
          }
        }),
        order,
      )
    }
  }
}

///|
test "LPC interchange matches deterministic voiced transients and oscillator" {
  for size in [33, 129, 256, 1024, 4096, 8192] {
    let oscillator : Array[Int64] = [0L, 1000000L]
    for i = 2; i < size; i = i + 1 {
      oscillator.push(((127L * oscillator[i - 1]) >> 6) - oscillator[i - 2])
    }
    let mut state = 17U
    let speech_shape = Array::makei(size, i => {
      state = state * 1664525U + 1013904223U
      let envelope = if i % 257 < 31 { 0L } else { (i % 127).to_int64() }
      oscillator[i] * envelope / 128L + (state.to_int64() % 8192L - 4096L)
    })
    for order = 1; order <= 32; order = order + 1 {
      lpc_interchange_compare(oscillator, order)
      lpc_interchange_compare(speech_shape, order)
    }
  }
}

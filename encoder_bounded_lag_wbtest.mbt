///|
test "bounded lag registers exact scalar correlation every order and tail" {
  for
    n in [
      2, 3, 15, 16, 17, 31, 32, 33, 63, 64, 65, 127, 128, 129, 255, 256, 257, 65535,
      65536,
    ] {
    let maximum = if n > 32 { 32 } else { n - 1 }
    let signal = FixedArray::makei(n, i => {
      let position = (2.0 * i.to_double() + 1.0) / n.to_double() - 1.0
      (i % 997 - 499).to_double() / 499.0 * (1.0 - position * position)
    })
    for limit = 0; limit <= maximum; limit = limit + 1 {
      if n > 257 && limit != 15 && limit != 16 && limit != 31 && limit != 32 {
        continue
      }
      let actual = encoder_lpc_correlations(signal, limit)
      for lag = 0; lag <= limit; lag = lag + 1 {
        let mut expected = 0.0
        for i = lag; i < n; i = i + 1 {
          expected += signal[i] * signal[i - lag]
        }
        assert_eq(actual[lag], expected)
      }
    }
  }
}

///|
test "bounded lag registers exact full model domain and generic fallback" {
  for n in [17, 32, 33, 257, 65535, 65536] {
    let samples = Array::makei(n, i => (i % 997 - 499).to_int64() * 8191L)
    for order in [1, 14, 15, 16, 17, 30, 31, 32] {
      lpc_interchange_compare(samples, order)
    }
  }
}

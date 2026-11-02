///|
fn lpc_register_compare(
  samples : Array[Int64],
  coefficients : Array[Int64],
  shift : Int32,
) -> Unit raise {
  let signal = FixedArray::makei(samples.length(), i => samples[i].to_double())
  let converted = FixedArray::makei(coefficients.length(), i => {
    coefficients[i].to_double()
  })
  let actual = Array::make(samples.length(), 777L)
  let expected = Array::make(samples.length(), 777L)
  let tile = FixedArray::make(128, 111.0)
  let old_tile = FixedArray::make(128, 111.0)
  let result = encoder_predict_double_into(
    samples, signal, converted, shift, actual, tile,
  )
  let old_result = lpc_register_frozen_predict(
    samples, signal, converted, shift, expected, old_tile,
  )
  assert_eq(result, old_result)
  assert_eq(actual, expected)
  for i in 0..<128 {
    assert_eq(
      tile[i].reinterpret_as_uint64(),
      old_tile[i].reinterpret_as_uint64(),
    )
  }
  double_predictor_compare(samples, coefficients, shift, 33)
}

///|
test "register LPC output orders tails and integer oracle" {
  for order = 1; order <= 32; order = order + 1 {
    for extra in [0, 1, 15, 16, 17, 127, 128, 129, 257] {
      for shift in [0, 1, 7, 15] {
        let samples = Array::makei(order + extra, i => {
          (i * 977 % 8191 - 4095).to_int64()
        })
        let coefficients = Array::makei(order, i => (i % 7 - 3).to_int64())
        lpc_register_compare(samples, coefficients, shift)
      }
    }
  }
}

///|
test "register LPC output wide rejection boundary and generic path" {
  for order in [1, 16, 31, 32] {
    for invalid_at in [0, 15, 16, 127, 128, 255] {
      let samples = Array::make(order + 300, 1L)
      samples[order + invalid_at] = 2147483648L
      lpc_register_compare(samples, Array::make(order, 0L), 0)
    }
    for coefficient in [-16384L, 16383L] {
      let samples = Array::makei(order + 145, i => {
        if i % 2 == 0 {
          -4294967296L
        } else {
          4294967295L
        }
      })
      lpc_register_compare(samples, Array::make(order, coefficient), 15)
    }
  }
  for size in [65535, 65536, 65552] {
    let samples = Array::makei(size, i => (i % 31 - 15).to_int64())
    lpc_register_compare(samples, Array::make(32, 1L), 5)
  }
}

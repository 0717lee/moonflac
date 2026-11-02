///|
fn symmetric_variance_compare_fallback(
  correlation : Array[Double],
  model : LpcModel,
  peak : Double,
  energy : Double,
) -> Unit raise {
  match
    (
      encoder_lpc_variance(correlation, model, peak, energy),
      symmetric_variance_frozen(correlation, model, peak, energy),
    ) {
    (Some(a), Some(b)) =>
      assert_eq(a.reinterpret_as_uint64(), b.reinterpret_as_uint64())
    (None, None) => ()
    _ => fail("fallback presence differs")
  }
}

///|
test "Symmetric variance literal fallback private and exceptional domains" {
  let zero = 0.0
  for order in [0, 1, 32, 33, 65] {
    for shift in [-65, -1, 0, 15, 16, 63, 64] {
      let model : LpcModel = {
        coefficients: Array::make(order, 20000L),
        shift,
        precision: 15,
      }
      symmetric_variance_compare_fallback(
        Array::make(order + 1, 1.0),
        model,
        1.0,
        1.0,
      )
    }
  }
  let model : LpcModel = { coefficients: [1L], shift: 0, precision: 2, }
  for
    value in [
      0.0,
      -0.0,
      -1.0,
      0.5,
      1.0e-201,
      1.0e300,
      1.0 / zero,
      -1.0 / zero,
      zero / zero,
    ] {
    symmetric_variance_compare_fallback([2.0, 1.0], model, value, 1.0)
    symmetric_variance_compare_fallback([2.0, 1.0], model, 1.0, value)
  }
  for
    value in [1.0e-201, 65536.0, 1.0e300, 1.0 / zero, -1.0 / zero, zero / zero] {
    symmetric_variance_compare_fallback([2.0, value], model, 1.0, 1.0)
  }
  symmetric_variance_compare_fallback([], model, 1.0, 1.0)
}

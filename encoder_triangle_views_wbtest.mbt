///|
test "Triangle views guarded domain exact C94 kernel bits" {
  for order in [1, 2, 3, 7, 16, 31, 32] {
    for shift in [0, 1, 8, 15] {
      let model : LpcModel = {
        coefficients: Array::makei(order, i => {
          if i % 2 == 0 {
            -16384L
          } else {
            16383L
          }
        }),
        shift,
        precision: 15,
      }
      for pattern in [0, 1, 2, 3] {
        let correlation = Array::makei(order + 1, i => {
          if pattern == 0 {
            1.0
          } else if pattern == 1 {
            if i % 2 == 0 {
              65535.0
            } else {
              -65535.0
            }
          } else if pattern == 2 {
            1.0e-200
          } else if i == 0 {
            32.0
          } else {
            0.0
          }
        })
        for peak in [1.0, 4294967296.0] {
          for energy in [1.0, 65535.0] {
            assert_true(
              encoder_lpc_variance_inputs(correlation, order, peak, energy),
            )
            match
              (
                encoder_lpc_variance_triangle(correlation, model, peak, energy),
                triangle_views_frozen(correlation, model, peak, energy),
              ) {
              (Some(a), Some(b)) =>
                assert_eq(a.reinterpret_as_uint64(), b.reinterpret_as_uint64())
              (None, None) => ()
              _ => fail("triangle kernel differs")
            }
          }
        }
      }
    }
  }
}

///|
test "biased LPC exact residual endpoints and dyadic ceil" {
  for
    value in [
      -2147483649L, -2147483648L, -2147483647L, -1L, 0L, 1L, 2147483647L, 2147483648L,
      2147483649L,
    ] {
    for shift = 0; shift <= 15; shift = shift + 1 {
      double_predictor_compare([0L, value], [0L], shift, 33)
    }
  }
  // Raw bias rounding would produce zero instead of ceil(1/4)=1 here.
  for
    history in [
      -32769L, -32768L, -32767L, -3L, -1L, 0L, 1L, 3L, 32767L, 32768L, 32769L,
    ] {
    for shift = 0; shift <= 15; shift = shift + 1 {
      for current in [-2147483648L, -2147483647L, 0L, 2147483647L, 2147483648L] {
        double_predictor_compare([history, current], [1L], shift, 33)
      }
    }
  }
}

///|
test "biased LPC outlier rejection cached signal and first invalid suffix" {
  for history in [-4294967296L, 4294967295L] {
    for coefficient in [-16384L, 16383L] {
      for shift in [0, 1, 7, 15] {
        let samples = Array::make(33, history)
        samples[32] = -history - 1L
        double_predictor_compare(
          samples,
          Array::make(32, coefficient),
          shift,
          33,
        )
      }
    }
  }
  for failed_at in [1, 127, 128, 129, 255, 256, 299] {
    for invalid in [-2147483648L, 2147483648L] {
      let samples = Array::make(300, 1L)
      samples[failed_at] = invalid
      double_predictor_compare(samples, [0L], 0, 33)
    }
  }
  let samples = Array::makei(300, i => (i % 37 - 18).to_int64())
  let signal = encoder_lpc_double_signal(samples, 6).unwrap()
  let scratch = EncoderPlanScratch::new()
  for shift = 0; shift <= 15; shift = shift + 1 {
    assert_true(scratch.predict_lpc_double(samples, Some(signal), [1L], shift))
    for i = 0; i < samples.length(); i = i + 1 {
      assert_eq(signal[i], samples[i].to_double())
    }
  }
}

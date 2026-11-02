///|
test "suffix bound preserves exhaustive plans tight budgets and reused scratch" {
  let scratch = EncoderPlanScratch::new()
  for size in [64, 128, 256, 1024] {
    for predictor in [0, 1, 4, 31] {
      for pattern = 0; pattern < 6; pattern = pattern + 1 {
        let samples = Array::makei(size, i => {
          let magnitude = match pattern {
            0 => if i < size / 2 { 0L } else { 32767L }
            1 => if i < size / 2 { 32767L } else { 0L }
            2 => if i % 16 < 8 { 2147483647L } else { 1L }
            3 => if i % 32 == 0 { 16384L } else { 0L }
            4 => i.to_int64() * 104729L % 65536L
            _ => if i < size / 4 || i >= size * 3 / 4 { 1L } else { 1048575L }
          }
          if i % 3 == 0 {
            -magnitude
          } else {
            magnitude
          }
        })
        let expected = plan_oracle(samples, predictor, 15)
        // Rejection may occur with a cheap exact prefix and expensive suffix.
        // A partial choices array must never be returned as a complete plan.
        for
          budget in [
            6L,
            expected.bits - 1L,
            expected.bits,
            expected.bits + 1L,
            40L * size.to_int64(),
          ] {
          let result = encoder_budget_residual_plan(
            samples, predictor, budget, scratch,
          )
          if expected.bits >= budget {
            assert_true(result is None)
          } else {
            plan_oracle_equal(result.unwrap(), expected)
          }
        }
      }
    }
  }
}

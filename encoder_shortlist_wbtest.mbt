///|
test "speed shortlist ranks integer probes stably without changing models" {
  let samples = Array::makei(4096, i => 100L + i.to_int64() * 3L)
  let best : LpcModel = { coefficients: [2L, -1L], precision: 3, shift: 0, }
  let models : Array[LpcModel] = [
    { coefficients: [0L], precision: 1, shift: 0, },
    { coefficients: [1L], precision: 2, shift: 0, },
    best,
    { coefficients: [2L, -1L], precision: 4, shift: 0, },
    { coefficients: [3L, -3L, 1L], precision: 3, shift: 0, },
    { coefficients: [-1L], precision: 2, shift: 0, },
  ]
  let selected = encoder_lpc_shortlist(samples, models, 24)
  assert_eq(selected.length(), ENCODER_LPC_SHORTLIST)
  assert_eq(selected[0].coefficients, best.coefficients)
  assert_eq(selected[0].precision, best.precision)
  assert_eq(models.length(), 6)
  assert_eq(samples[4095], 12385L)
  let again = encoder_lpc_shortlist(samples, models, 24)
  for i = 0; i < selected.length(); i = i + 1 {
    assert_eq(selected[i].coefficients, again[i].coefficients)
    assert_eq(selected[i].precision, again[i].precision)
    assert_eq(selected[i].shift, again[i].shift)
  }
}

///|
test "speed approximate ranking never replaces full residual validation" {
  let samples = Array::make(4096, 1L)
  // Find two consecutive residual positions not touched by the probe grid.
  let probes = Array::make(4096, false)
  for j = 0; j < ENCODER_LPC_PROBES; j = j + 1 {
    probes[1 + j * 4094 / (ENCODER_LPC_PROBES - 1)] = true
  }
  let mut impulse = 2
  while probes[impulse] || probes[impulse + 1] {
    impulse += 1
  }
  samples[impulse] = 2147483647L
  let models : Array[LpcModel] = Array::makei(6, i => {
    coefficients: [(i + 2).to_int64()],
    precision: 5,
    shift: 0,
  })
  let selected = encoder_lpc_shortlist(samples, models, 32)
  assert_eq(selected[0].coefficients, [2L])
  assert_true(encoder_predictor(samples, selected[0].coefficients, 0) is None)
}

///|
test "speed exact residual search keeps fine partitions for isolated impulses" {
  let sparse = Array::makei(4096, i => if i % 8 == 0 { 1073741824L } else { 0L })
  assert_eq(
    encoder_adaptive_residual_plan(sparse, 0).bits,
    encoder_residual_plan(sparse, 0, 15).bits,
  )
  let alternating = Array::makei(4096, i => if i % 2 == 0 { 0L } else { 16383L })
  assert_eq(
    encoder_adaptive_residual_plan(alternating, 0).bits,
    encoder_residual_plan(alternating, 0, 15).bits,
  )
  assert_true(
    encoder_residual_plan(alternating, 0, 15).bits <
    encoder_residual_plan(alternating, 0, ENCODER_PARTITION_CAP).bits,
  )
  assert_eq(
    encoder_adaptive_residual_plan(Array::make(4096, 1L), 0).bits,
    encoder_residual_plan(Array::make(4096, 1L), 0, 15).bits,
  )
  assert_eq(
    encoder_adaptive_residual_plan(Array::make(65535, 0L), 0).bits,
    encoder_residual_plan(Array::make(65535, 0L), 0, 15).bits,
  )
  let full = encoder_residual_plan(sparse, 0, 15)
  let capped = encoder_residual_plan(sparse, 0, ENCODER_PARTITION_CAP)
  assert_true(full.bits < capped.bits)
}

///|
test "speed shortlist backfills full residual overflow before verbatim" {
  let mut state = 29092228U
  let samples : Array[Int64] = []
  for i = 0; i < 4096; i = i + 1 {
    for channel = 0; channel < 5; channel = channel + 1 {
      state = state * 1664525U + 1013904223U
      if channel == 3 {
        let noise = state.to_int64() - 2147483648L
        // Floor division, matching signed arithmetic shifting.
        samples.push(if i % 1000 == 0 { -2147483648L } else { noise >> 13 })
      }
    }
  }
  let frame = encoder_subframe(samples, 32, 8)
  assert_true(frame.kind >= 32)
  assert_true(frame.bits < 4096L * 24L)
}

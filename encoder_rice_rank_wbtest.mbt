// Independent exhaustive order-zero Rice cost: no convex-window or production
// partition planner is used by this oracle.

///|
fn rice_rank_brute(
  samples : Array[Int64],
  model : LpcModel,
  depth : Int32,
) -> Int64? {
  let order = model.coefficients.length()
  let residuals : Array[Int64] = []
  let mut width = 0
  for i = order; i < samples.length(); i = i + 1 {
    let mut predicted = 0L
    for j = 0; j < order; j = j + 1 {
      predicted += samples[i - j - 1] * model.coefficients[j]
    }
    let value = samples[i] - (predicted >> model.shift)
    if value <= -2147483648L || value >= 2147483648L {
      return None
    }
    residuals.push(value)
    let mut bits = if value == 0L { 0 } else { 1 }
    while bits > 0 && (value < -(1L << (bits - 1)) || value >= 1L << (bits - 1)) {
      bits += 1
    }
    if bits > width {
      width = bits
    }
  }
  let mut best = 9223372036854775807L
  for k = 0; k <= 30; k = k + 1 {
    let mut bits = (6 + (if k <= 14 { 4 } else { 5 })).to_int64()
    for value in residuals {
      let folded = if value < 0L { -2L * value - 1L } else { 2L * value }
      bits += (folded >> k) + (k + 1).to_int64()
    }
    if bits < best {
      best = bits
    }
  }
  if width <= 31 {
    let escape = 15L + residuals.length().to_int64() * width.to_int64()
    if escape < best {
      best = escape
    }
  }
  Some(best + (8 + order * depth + 9 + order * model.precision).to_int64())
}

///|
test "Rice-ranked irregular probes disjoint and weighted count exact" {
  for size in [257, 263, 383, 384, 513, 1023, 65535] {
    for edge in [2, 16, 32, 64] {
      let positions = encoder_rice_probe_positions(size, edge)
      for i = 1; i < positions.length(); i = i + 1 {
        assert_true(positions[i] > positions[i - 1])
      }
      assert_eq(positions[0], 0)
      assert_eq(positions[positions.length() - 1], size - 1)
      let interior = size - 2 * edge
      let scale = if interior < 256 { interior } else { 256 }
      assert_eq(positions.length(), 2 * edge + scale)
      if interior <= 256 {
        assert_eq(positions.length(), size)
      }
      for order = 1; order <= edge / 2; order = order + 1 {
        let mut count = 0L
        for i in positions {
          if i >= order {
            count += (if i < edge || i >= size - edge {
              scale
            } else {
              interior
            }).to_int64()
          }
        }
        assert_eq(count, scale.to_int64() * (size - order).to_int64())
      }
    }
  }
}

///|
test "Rice-ranked prime full coverage matches all31parameter oracle" {
  for size in [257, 263] {
    let positions = encoder_rice_probe_positions(size, 64)
    let scale = (size - 128).to_int64()
    for depth in [4, 16, 24, 32, 33] {
      let low = -(1L << (depth - 1))
      let high = -low - 1L
      let pulse = Array::makei(size, i => {
        if i == 3 {
          high
        } else if i == size - 2 {
          low
        } else {
          3L
        }
      })
      let mut state = 9639U
      let noise = Array::makei(size, _ => {
        state = state * 1664525U + 1013904223U
        ((state.to_int64() * 2L) & ((1L << depth) - 1L)) + low
      })
      for samples in [pulse, noise] {
        for order = 1; order <= 32; order = order + 1 {
          for shift in [0, 7, 15] {
            let model : LpcModel = {
              coefficients: Array::makei(order, j => {
                if j % 2 == 0 {
                  8192L
                } else {
                  -4096L
                }
              }),
              shift,
              precision: 15,
            }
            let expected = rice_rank_brute(samples, model, depth)
            let actual = encoder_lpc_rice_score(
              samples, model, depth, 64, positions,
            )
            match expected {
              Some(cost) => assert_eq(actual, Some(cost * scale))
              None => assert_eq(actual, None)
            }
          }
        }
      }
    }
  }
}

///|
test "Rice-ranked zero escape stable ties and probe overflow skip" {
  let a : LpcModel = { coefficients: [1L], shift: 0, precision: 3, }
  let b : LpcModel = { coefficients: [2L], shift: 0, precision: 3, }
  let zero = Array::make(257, 0L)
  let ranking = encoder_lpc_rice_ranking(zero, [b, a], 16)
  assert_eq(ranking.length(), 2)
  assert_eq(ranking[0].coefficients, b.coefficients)
  let positions = encoder_rice_probe_positions(257, 2)
  assert_eq(
    encoder_lpc_rice_score(zero, a, 16, 2, positions),
    Some((8L + 16L + 9L + 3L + 15L) * 253L),
  )
  let bad : LpcModel = { coefficients: [-16384L], shift: 0, precision: 15, }
  let values = Array::make(257, 2147483647L)
  let ranking = encoder_lpc_rice_ranking(values, [bad, a], 32)
  assert_eq(ranking.length(), 1)
  assert_eq(ranking[0].coefficients, a.coefficients)
}

///|
test "Rice-ranked unobserved invalid residual backfills four legal finalists" {
  let size = 1023
  let bad : LpcModel = { coefficients: [-16384L], shift: 0, precision: 15, }
  let legal : LpcModel = { coefficients: [0L], shift: 0, precision: 15, }
  let positions = encoder_rice_probe_positions(size, 2)
  let mut hidden = 3
  while positions.contains(hidden) || positions.contains(hidden + 1) {
    hidden += 1
  }
  let samples = Array::make(size, 0L)
  samples[hidden] = 2147483647L
  let models = [bad, bad, bad, bad, legal, legal, legal, legal]
  let ranking = encoder_lpc_rice_ranking(samples, models, 32)
  assert_eq(ranking.length(), 8)
  assert_eq(ranking[0].coefficients, bad.coefficients)
  // Equal sampled costs retain original order; only fully legal residuals
  // consume the unchanged four-finalist budget.
  let scratch = EncoderPlanScratch::new()
  let mut valid = 0
  let mut attempts = 0
  for model in ranking {
    if valid >= 4 {
      break
    }
    attempts += 1
    if scratch.predict(samples, model.coefficients, model.shift) {
      valid += 1
    }
  }
  assert_eq(valid, 4)
  assert_eq(attempts, 8)
}

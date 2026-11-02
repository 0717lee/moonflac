// Frozen C11 encoder_subframe policy for full differential serialization.

///|
fn encoder_original_fixed_order_policy(
  samples : Array[Int64],
  width : Int32,
  effort : Int32,
) -> EncoderSubframe {
  let size = samples.length()
  let workspace : Array[Array[Int64]] = []
  let plan_scratch = EncoderPlanScratch::new()
  let mut wasted = width - 1
  let mut constant_input = true
  for sample in samples {
    if sample != samples[0] {
      constant_input = false
    }
    if sample != 0L {
      let mut zeros = 0
      while zeros < wasted && (sample & (1L << zeros)) == 0L {
        zeros += 1
      }
      if zeros < wasted {
        wasted = zeros
      }
    }
  }
  let mut best : EncoderSubframe = {
    kind: 1,
    wasted: 0,
    depth: width,
    samples,
    coefficients: [],
    shift: 0,
    precision: 0,
    residual: [],
    plan: None,
    bits: 8L + size.to_int64() * width.to_int64(),
  }
  let choices = if wasted == 0 { [0] } else { [0, wasted] }
  for wasted in choices {
    let depth = width - wasted
    let shifted = if wasted == 0 {
      samples
    } else {
      samples.map(x => x >> wasted)
    }
    let header_bits = 8L + wasted.to_int64()
    let constant = constant_input
    if constant && header_bits + depth.to_int64() < best.bits {
      best = {
        ..best,
        kind: 0,
        wasted,
        depth,
        samples: shifted,
        bits: header_bits + depth.to_int64(),
      }
    }
    let verbatim = header_bits + size.to_int64() * depth.to_int64()
    if verbatim < best.bits {
      best = {
        ..best,
        kind: 1,
        wasted,
        depth,
        samples: shifted,
        plan: None,
        bits: verbatim,
      }
    }
    if effort == 0 {
      continue
    }
    // A constant signal can still be cheaper as fixed order zero (notably
    // wide-depth zero blocks with escape width zero). Higher predictors need
    // a warm-up at least as expensive as the entire constant sample field.
    let max_partition = if constant {
      0
    } else if effort == 8 {
      ENCODER_PARTITION_CAP
    } else {
      effort
    }
    let max_fixed = if constant { 0 } else { 4 }
    for order = 0; order <= max_fixed && order < size; order = order + 1 {
      let coefficients = encoder_fixed_coefficients(order)
      let residual = if order == 0 && depth < 32 {
        // All values at this depth are legal residuals, with no warm-ups.
        Some(shifted)
      } else if plan_scratch.predict_fixed(shifted, coefficients, depth) {
        Some(plan_scratch.residual)
      } else {
        None
      }
      if residual is Some(residual) {
        let plan = if !constant && effort == 8 {
          match
            encoder_budget_residual_plan(
              residual,
              order,
              best.bits - header_bits - (order * depth).to_int64(),
              plan_scratch,
            ) {
            Some(plan) => plan
            None => continue
          }
        } else {
          encoder_residual_plan(residual, order, max_partition, workspace~)
        }
        let cost = header_bits + (order * depth).to_int64() + plan.bits
        if cost < best.bits {
          best = {
            kind: order + 8,
            wasted,
            depth,
            samples: shifted,
            coefficients,
            shift: 0,
            precision: 0,
            // Later predictors reuse scratch; the winner owns its samples.
            residual: residual.copy(),
            plan: Some(plan),
            bits: cost,
          }
        }
      }
    }
    if constant {
      continue
    }
    let limits = [0, 0, 2, 4, 8, 12, 16, 24, 32]
    let max_order = if limits[effort] < size {
      limits[effort]
    } else {
      size - 1
    }
    // A short block already fits within the sampling budget. Evaluate its
    // complete model pool in original order: a width proxy can badly rank
    // shared Rice costs, and offers no sampling reduction at this size.
    // A winning deeply partitioned fixed candidate proves that local residual
    // distributions matter. Global sampled-width ranking is unsuitable there.
    let deep_partitions = match best.plan {
      Some(plan) => size >> plan.order <= 8
      None => false
    }
    // Irregular blocks rank stratified exact integer residual probes by
    // shared Rice costs, including all edge samples around warm-ups.
    let rice_irregular = effort == 8 &&
      size > ENCODER_LPC_PROBES &&
      size % (1 << ENCODER_PARTITION_CAP) != 0 &&
      !deep_partitions
    let shortlist = effort == 8 &&
      size > ENCODER_LPC_PROBES &&
      size % (1 << ENCODER_PARTITION_CAP) == 0 &&
      !deep_partitions
    let variances : Array[Double?] = []
    let models = encoder_lpc_models(
      shifted,
      max_order,
      variances=if shortlist { Some(variances) } else { None },
    )
    let candidates = if rice_irregular {
      encoder_lpc_rice_ranking(shifted, models, depth)
    } else if shortlist {
      // Rank the full pool so an illegal full residual does not consume a
      // finalist slot. Sampled legality cannot establish whole-frame legality.
      encoder_lpc_variance_ranking(shifted, models, variances, depth)
    } else {
      models
    }
    let mut double_signal : FixedArray[Double]? = None
    let mut double_signal_ready = false
    let mut valid_candidates = 0
    for model in candidates {
      if (shortlist || rice_irregular) &&
        valid_candidates >= ENCODER_LPC_SHORTLIST {
        break
      }
      let order = model.coefficients.length()
      if order > 0 &&
        order <= max_order &&
        model.shift >= 0 &&
        model.shift <= 15 &&
        model.precision >= 1 &&
        model.precision <= 15 {
        if !double_signal_ready {
          double_signal = encoder_lpc_double_signal(shifted, depth)
          double_signal_ready = true
        }
        if plan_scratch.predict_lpc_double(
            shifted,
            double_signal,
            model.coefficients,
            model.shift,
          ) {
          let residual = plan_scratch.residual
          valid_candidates += 1
          let plan = if effort == 8 {
            match
              encoder_budget_residual_plan(
                residual,
                order,
                best.bits -
                header_bits -
                (order * depth + 9 + order * model.precision).to_int64(),
                plan_scratch,
              ) {
              Some(plan) => plan
              None => continue
            }
          } else {
            encoder_residual_plan(residual, order, max_partition, workspace~)
          }
          let cost = header_bits +
            (order * depth + 9 + order * model.precision).to_int64() +
            plan.bits
          if cost < best.bits {
            best = {
              kind: order + 31,
              wasted,
              depth,
              samples: shifted,
              coefficients: model.coefficients,
              shift: model.shift,
              precision: model.precision,
              residual: residual.copy(),
              plan: Some(plan),
              bits: cost,
            }
          }
        }
      }
    }
  }
  best
}

///|
fn fixed_policy_serialized(sub : EncoderSubframe) -> Bytes {
  let out = EncoderBits::new()
  encoder_write_subframe(out, sub)
  out.align()
  out.snapshot()
}

///|
fn fixed_policy_compare(
  samples : Array[Int64],
  width : Int32,
  effort : Int32,
) -> Unit raise {
  let before = encoder_original_fixed_order_policy(samples, width, effort)
  let after = encoder_subframe(samples, width, effort)
  assert_eq(after.bits, before.bits)
  assert_eq(fixed_policy_serialized(after), fixed_policy_serialized(before))
}

///|
test "sampled fixed ordering matches frozen full policy over varied real predictor inputs" {
  let mut state = 963921U
  for trial in 0..<54 {
    let size = [257, 384, 1024][trial % 3]
    let width = [4, 16, 24, 32, 33][trial % 5]
    let bound = 1L << (width - 1)
    let samples = Array::makei(size, i => {
      state = state * 1664525U + 1013904223U
      let value = match trial % 9 {
        0 => (i % 11 - 5).to_int64()
        1 => (i * i % 1009 - 504).to_int64()
        2 => if i % 37 == 0 { bound - 1L } else { 0L }
        3 => if i % 2 == 0 { -bound } else { bound - 1L }
        4 => ((i / 13 % 7 - 3) * 8).to_int64()
        5 =>
          if i < size / 2 {
            0L
          } else {
            state.reinterpret_as_int().to_int64() >> 16
          }
        6 => 0L
        7 => bound / 2L
        _ => state.reinterpret_as_int().to_int64() >> (trial % 16)
      }
      if value < -bound {
        -bound
      } else if value >= bound {
        bound - 1L
      } else {
        value
      }
    })
    fixed_policy_compare(samples, width, 8)
  }
}

///|
test "fixed ordering preserves short and effort0 through7 policy and illegal residual handling" {
  for size in [1, 15, 64, 256, 257] {
    let samples = Array::makei(size, i => {
      if i % 3 == 0 {
        -2147483648L
      } else {
        2147483647L
      }
    })
    for effort in 0..<=8 {
      fixed_policy_compare(samples, 32, effort)
    }
  }
  let side = Array::makei(513, i => {
    if i % 2 == 0 {
      -4294967295L
    } else {
      4294967295L
    }
  })
  fixed_policy_compare(side, 33, 8)
}

///|
// Independently found by Python scalar Rice costs: orders0/1 tie at280bits;
// remaining fixed costs286/293/305. The signed-width ordering prefers order1.
let fixed_policy_tie : Array[Int64] = [
  0L, 0L, 0L, 0L, 0L, 0L, 0L, 0L, 0L, 0L, 0L, 0L, 0L, 0L, 0L, 0L, 0L, 0L, 0L, 0L,
  0L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L,
  -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L,
  -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L,
  -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L,
  -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L,
  -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L,
  -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L,
  -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L,
  -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L,
  -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L,
  -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L,
  -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L,
  -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L,
  -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L,
  -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L, -1L,
]

///|
test "real fixed cost tie keeps lower original order across reordered and wasted choices" {
  let ranked = encoder_fixed_ordering(fixed_policy_tie, 5)
  assert_true(ranked[0] != 0)
  let sub = encoder_subframe(fixed_policy_tie, 5, 8)
  assert_eq(sub.kind, 8)
  assert_eq(sub.bits, 280L)
  fixed_policy_compare(fixed_policy_tie, 5, 8)
  let wasted = fixed_policy_tie.map(x => x << 3)
  let shifted = encoder_subframe(wasted, 8, 8)
  assert_true(shifted.wasted > 0)
  fixed_policy_compare(wasted, 8, 8)
}

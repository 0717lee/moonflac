// Exact budgeted residual planning. Scratch belongs to one encoder instance;
// returned plans own only scalar choices, never any reusable prefix storage.

///|
// Budget planning receives validated signed 32-bit residuals. Folding fits
// UInt exactly, including the full unsigned high bit. Quotient sums remain
// Int64: at most 65535 values of at most 2^32-1 fit below 2^48.
fn encoder_fold_u32(value : Int64) -> UInt32 {
  let signed = value.to_int()
  (signed.reinterpret_as_uint() << 1) ^ (signed >> 31).reinterpret_as_uint()
}

///|
priv struct EncoderPlanScratch {
  mut residual : Array[Int64]
  mut double_tile : FixedArray[Double]
  mut fixed_tile : FixedArray[Int64]
  mut folded : Array[UInt32]
  prefixes : Array[Array[Int64]]
  ready : Array[Bool]
  mut widths : Array[Int32]
  mut width_sums : Array[Int32]
  mut sums : Array[Int64]
  mut choices0 : Array[Int32]
  mut choices1 : Array[Int32]
}

///|
fn EncoderPlanScratch::new() -> EncoderPlanScratch {
  {
    residual: [],
    double_tile: FixedArray::make(0, 0.0),
    fixed_tile: FixedArray::make(0, 0L),
    folded: [],
    prefixes: Array::makei(31, _ => []),
    ready: Array::make(31, false),
    widths: [],
    width_sums: [],
    sums: [],
    choices0: [],
    choices1: [],
  }
}

///|
fn EncoderPlanScratch::predict(
  self : EncoderPlanScratch,
  samples : Array[Int64],
  coefficients : Array[Int64],
  shift : Int32,
) -> Bool {
  let size = samples.length()
  if self.residual.length() != size {
    self.residual = Array::make(size, 0L)
  }
  // Warm-ups are not residuals; retain the existing zero-prefix contract.
  for i = 0; i < coefficients.length() && i < size; i = i + 1 {
    self.residual.unsafe_set(i, 0L)
  }
  encoder_predict_into(samples, coefficients, shift, self.residual)
}

///|
fn encoder_prepare_leaf_prefixes(
  scratch : EncoderPlanScratch,
  size : Int32,
  leaves : Int32,
  low : Int32,
  high : Int32,
) -> Unit {
  // The convex window contains at most three columns. Q(0) is already
  // available in the leaf sum tree, and ready columns are never rebuilt.
  let mut k0 = -1
  let mut k1 = -1
  let mut k2 = -1
  for k = low; k <= high; k = k + 1 {
    if k > 0 && !scratch.ready[k] {
      if scratch.prefixes[k].length() < leaves + 1 {
        scratch.prefixes[k] = Array::make(leaves + 1, 0L)
      }
      if k0 < 0 {
        k0 = k
      } else if k1 < 0 {
        k1 = k
      } else {
        k2 = k
      }
    }
  }
  if k0 < 0 {
    return
  }
  let a = scratch.prefixes[k0]
  let b = if k1 >= 0 { scratch.prefixes[k1] } else { a }
  let c = if k2 >= 0 { scratch.prefixes[k2] } else { a }
  a.unsafe_set(0, 0L)
  b.unsafe_set(0, 0L)
  c.unsafe_set(0, 0L)
  let folded = scratch.folded
  let step = size / leaves
  let mut total0 = 0L
  let mut total1 = 0L
  let mut total2 = 0L
  for leaf = 0; leaf < leaves; leaf = leaf + 1 {
    for i = leaf * step; i < (leaf + 1) * step; i = i + 1 {
      let value = folded.unsafe_get(i)
      total0 += (value >> k0).to_int64()
      if k1 >= 0 {
        total1 += (value >> k1).to_int64()
      }
      if k2 >= 0 {
        total2 += (value >> k2).to_int64()
      }
    }
    a.unsafe_set(leaf + 1, total0)
    if k1 >= 0 {
      b.unsafe_set(leaf + 1, total1)
    }
    if k2 >= 0 {
      c.unsafe_set(leaf + 1, total2)
    }
  }
  scratch.ready[k0] = true
  if k1 >= 0 {
    scratch.ready[k1] = true
  }
  if k2 >= 0 {
    scratch.ready[k2] = true
  }
}

///|
fn encoder_prefix_quotient(
  scratch : EncoderPlanScratch,
  start_leaf : Int32,
  end_leaf : Int32,
  parameter : Int32,
) -> Int64 {
  let prefix = scratch.prefixes[parameter]
  // Every legal coarser partition is a union of finest leaves. Warm-ups
  // were zeroed before prefix construction, so first-partition start is 0.
  prefix.unsafe_get(end_leaf) - prefix.unsafe_get(start_leaf)
}

///|
fn encoder_single_partition_plan(
  samples : Array[Int64],
  predictor : Int32,
  budget : Int64,
) -> EncoderResidual? {
  let size = samples.length()
  let mut sum = 0L
  let mut width = 0
  let mut width_sum = 0L
  for i = predictor; i < size; i = i + 1 {
    let value = samples.unsafe_get(i)
    let folded = encoder_fold_u32(value)
    sum += folded.to_int64()
    let w = 32 - folded.clz()
    if w > width {
      width = w
    }
    width_sum += (w + 1).to_int64()
  }
  encoder_single_partition_from_stats(
    samples, predictor, budget, sum, width, width_sum,
  )
}

///|
fn encoder_single_partition_from_stats(
  samples : Array[Int64],
  predictor : Int32,
  budget : Int64,
  sum : Int64,
  width : Int32,
  width_sum : Int64,
) -> EncoderResidual? {
  let size = samples.length()
  let count = (size - predictor).to_int64()
  let escape = 9L + count * width.to_int64()
  let rice_lower = 4L + width_sum
  let lower = if width <= 31 && escape < rice_lower {
    escape
  } else {
    rice_lower
  }
  if 6L + lower >= budget {
    return None
  }
  let mut low = 0
  let mut high = 0
  if sum > count {
    let difference = count.clz() - sum.clz()
    let m = if sum >= count << difference { difference } else { difference - 1 }
    low = if m > 0 { m - 1 } else { 0 }
    high = if sum == count << m { m } else { m + 1 }
    if low > 30 {
      low = 30
    }
    if high > 30 {
      high = 30
    }
  }
  // One partition has no prefix reuse. Accumulate the at most three window
  // columns (and Rice's clipped k=14) together, without N-sized scratch.
  let mut q_low = 0L
  let mut q_next = 0L
  let mut q_last = 0L
  let mut q14 = 0L
  for i = predictor; i < size; i = i + 1 {
    let value = samples.unsafe_get(i)
    let folded = encoder_fold_u32(value)
    q_low += (folded >> low).to_int64()
    if high > low {
      q_next += (folded >> (low + 1)).to_int64()
    }
    if high > low + 1 {
      q_last += (folded >> high).to_int64()
    }
    if low > 14 {
      q14 += (folded >> 14).to_int64()
    }
  }
  let mut parameter = low
  let mut cost = q_low + count * (low + 1).to_int64()
  let next_cost = q_next + count * (low + 2).to_int64()
  if high > low && next_cost < cost {
    parameter = low + 1
    cost = next_cost
  }
  let last_cost = q_last + count * (high + 1).to_int64()
  if high > low + 1 && last_cost < cost {
    parameter = high
    cost = last_cost
  }
  let k0 = if parameter > 14 { 14 } else { parameter }
  let rice0 = if parameter <= 14 {
    cost
  } else {
    let quotient = if low > 14 {
      q14
    } else if low == 14 {
      q_low
    } else {
      // At most three columns, so crossing 14 from below means low=13.
      q_next
    }
    quotient + count * 15L
  }
  let escaped0 = width <= 31 && escape < rice0 + 4L
  let escaped1 = width <= 31 && escape + 1L < cost + 5L
  let cost0 = if escaped0 { escape } else { rice0 + 4L }
  let cost1 = if escaped1 { escape + 1L } else { cost + 5L }
  let rice2 = cost1 < cost0
  let bits = 6L + (if rice2 { cost1 } else { cost0 })
  if bits >= budget {
    return None
  }
  let escaped = if rice2 { escaped1 } else { escaped0 }
  Some({
    order: 0,
    rice2,
    parts: [
      {
        parameter: if escaped {
          if rice2 {
            31
          } else {
            15
          }
        } else if rice2 {
          parameter
        } else {
          k0
        },
        width: if escaped {
          width
        } else {
          -1
        },
        count: size - predictor,
      },
    ],
    bits,
  })
}

///|
fn encoder_depth_lower_bound(
  size : Int32,
  predictor : Int32,
  order : Int32,
  total_width : Int64,
) -> Int64 {
  let parts = 1 << order
  let step = size >> order
  let first = step - predictor
  // Rice >= 4+sum(width)+n; escape >= 9+sum(width).
  // Splitting a legal partition cannot decrease min(n,5), and adds a header.
  6L +
  total_width +
  4L * parts.to_int64() +
  (if first < 5 { first } else { 5 }).to_int64() +
  (parts - 1).to_int64() * (if step < 5 { step } else { 5 }).to_int64()
}

///|
fn encoder_budget_residual_plan(
  samples : Array[Int64],
  predictor : Int32,
  budget : Int64,
  scratch : EncoderPlanScratch,
) -> EncoderResidual? {
  let size = samples.length()
  if budget <= 6L {
    return None
  }
  let mut maximum = 0
  while maximum < 15 &&
        size % (1 << (maximum + 1)) == 0 &&
        size >> (maximum + 1) > predictor {
    maximum += 1
  }
  // Excluded levels cannot beat the caller even with free residual symbols.
  while maximum > 0 && 6L + (4L << maximum) >= budget {
    maximum -= 1
  }
  if maximum == 0 {
    return encoder_single_partition_plan(samples, predictor, budget)
  }
  // This is only the initial collection depth, never a search-order cap.
  let initial_depth = if maximum < 8 { maximum } else { 8 }
  let initial_leaves = 1 << initial_depth
  let leaf_size = size >> initial_depth
  if scratch.folded.length() < size {
    scratch.folded = Array::make(size, 0U)
  }
  if scratch.widths.length() < initial_leaves * 2 {
    scratch.widths = Array::make(initial_leaves * 2, 0)
    scratch.width_sums = Array::make(initial_leaves * 2, 0)
    scratch.sums = Array::make(initial_leaves * 2, 0L)
    scratch.choices0 = Array::make(initial_leaves, 0)
    scratch.choices1 = Array::make(initial_leaves, 0)
  }
  for k = 0; k < 31; k = k + 1 {
    scratch.ready[k] = false
  }
  // Warm-ups are excluded from every partition and from all prefix sums.
  for i = 0; i < predictor; i = i + 1 {
    scratch.folded[i] = 0U
  }
  // Capture backing storage after capacity growth and warmup initialization.
  // Neither samples nor folded is resized while these views are live.
  let sample_view = samples[:]
  let folded_view = scratch.folded.mut_view(end=size)
  for p = 0; p < initial_leaves; p = p + 1 {
    let start = if p == 0 { predictor } else { p * leaf_size }
    let end = (p + 1) * leaf_size
    let mut width = 0
    let mut width_sum = 0
    let mut sum = 0L
    for i = start; i < end; i = i + 1 {
      let value = sample_view.unsafe_get(i)
      let folded = encoder_fold_u32(value)
      let w = 32 - folded.clz()
      if w > width {
        width = w
      }
      width_sum += w + 1
      folded_view.unsafe_set(i, folded)
      sum += folded.to_int64()
    }
    scratch.widths[initial_leaves + p] = width
    scratch.width_sums[initial_leaves + p] = width_sum
    scratch.sums[initial_leaves + p] = sum
  }
  for node = initial_leaves - 1; node > 0; node = node - 1 {
    let left = scratch.widths[node * 2]
    let right = scratch.widths[node * 2 + 1]
    scratch.widths[node] = if left > right { left } else { right }
    scratch.width_sums[node] = scratch.width_sums[node * 2] +
      scratch.width_sums[node * 2 + 1]
    scratch.sums[node] = scratch.sums[node * 2] + scratch.sums[node * 2 + 1]
  }
  let total_width = scratch.width_sums[1].to_int64() -
    (size - predictor).to_int64()
  while maximum > 0 &&
        encoder_depth_lower_bound(size, predictor, maximum, total_width) >=
        budget {
    maximum -= 1
  }
  if encoder_depth_lower_bound(size, predictor, maximum, total_width) >= budget {
    return None
  }
  let mut best : EncoderResidual? = None
  let mut best_bits = budget
  let mut first_order = 0
  if maximum > initial_depth {
    // Reuse root statistics before deciding whether a finer grid is needed.
    // Exact order0 supplies a feasible upper bound; strict ties retain it.
    best = encoder_single_partition_from_stats(
      samples,
      predictor,
      budget,
      scratch.sums[1],
      scratch.widths[1],
      scratch.width_sums[1].to_int64(),
    )
    if best is Some(seed) {
      best_bits = seed.bits
    }
    first_order = 1
    while maximum > 0 &&
          encoder_depth_lower_bound(size, predictor, maximum, total_width) >=
          best_bits {
      maximum -= 1
    }
    if maximum == 0 {
      return best
    }
  }
  let leaves = 1 << maximum
  if maximum > initial_depth {
    // Only this case needs more detailed statistics. Folded bit length equals
    // original signed width, including zero; no original residual reread.
    if scratch.widths.length() < leaves * 2 {
      scratch.widths = Array::make(leaves * 2, 0)
      scratch.width_sums = Array::make(leaves * 2, 0)
      scratch.sums = Array::make(leaves * 2, 0L)
      scratch.choices0 = Array::make(leaves, 0)
      scratch.choices1 = Array::make(leaves, 0)
    }
    let fine_step = size >> maximum
    for p = 0; p < leaves; p = p + 1 {
      let start = if p == 0 { predictor } else { p * fine_step }
      let end = (p + 1) * fine_step
      let mut width = 0
      let mut width_sum = 0
      let mut sum = 0L
      for i = start; i < end; i = i + 1 {
        let value = scratch.folded.unsafe_get(i)
        let w = 32 - value.clz()
        if w > width {
          width = w
        }
        width_sum += w + 1
        sum += value.to_int64()
      }
      scratch.widths[leaves + p] = width
      scratch.width_sums[leaves + p] = width_sum
      scratch.sums[leaves + p] = sum
    }
    for node = leaves - 1; node > 0; node = node - 1 {
      let left = scratch.widths[node * 2]
      let right = scratch.widths[node * 2 + 1]
      scratch.widths[node] = if left > right { left } else { right }
      scratch.width_sums[node] = scratch.width_sums[node * 2] +
        scratch.width_sums[node * 2 + 1]
      scratch.sums[node] = scratch.sums[node * 2] + scratch.sums[node * 2 + 1]
    }
  }
  for order = first_order; order <= maximum; order = order + 1 {
    let parts = 1 << order
    // Every subsequent order has at least this many parameter headers.
    if 6L + 4L * parts.to_int64() >= best_bits {
      break
    }
    let step = size >> order
    let mut lower = 6L
    for p = 0; p < parts; p = p + 1 {
      let count = if p == 0 { step - predictor } else { step }
      let width = scratch.widths[parts + p]
      let rice = 4 + scratch.width_sums[parts + p]
      let escaped = 9 + count * width
      lower += (if width <= 31 && escaped < rice { escaped } else { rice }).to_int64()
      if lower >= best_bits {
        break
      }
    }
    if lower >= best_bits {
      continue
    }
    let mut bits0 = 6L
    let mut bits1 = 6L
    // The complete level bound above already includes every remaining part.
    let mut remaining = lower - 6L
    let mut abandoned = false
    for p = 0; p < parts; p = p + 1 {
      let start = if p == 0 { predictor } else { p * step }
      let end = (p + 1) * step
      let count = (end - start).to_int64()
      let width = scratch.widths[parts + p]
      let part_rice_lower = 4L + scratch.width_sums[parts + p].to_int64()
      let part_escape_lower = 9L + count * width.to_int64()
      remaining -= if width <= 31 && part_escape_lower < part_rice_lower {
        part_escape_lower
      } else {
        part_rice_lower
      }
      // Q(0) is already known from the one collection pass and tree merges.
      let sum = scratch.sums[parts + p]
      // For S>n, m=floor(log2(S/n)) bounds the earliest convex minimum
      // to [max(0,m-1), ceil(log2(S/n))]. At most three k are needed.
      // See scripts/prove_rice_parameter_window.py for strict tie bounds.
      let mut low = 0
      let mut high = 0
      if sum > count {
        let difference = count.clz() - sum.clz()
        let m = if sum >= count << difference {
          difference
        } else {
          difference - 1
        }
        low = if m > 0 { m - 1 } else { 0 }
        high = if sum == count << m { m } else { m + 1 }
        if low > 30 {
          low = 30
        }
        if high > 30 {
          high = 30
        }
      }
      let mut parameter = low
      // Skip only the unchanged builder's no-op all-ready path.
      if (low > 0 && !scratch.ready[low]) ||
        (high > low && !scratch.ready[low + 1]) ||
        (high > low + 1 && !scratch.ready[high]) {
        encoder_prepare_leaf_prefixes(scratch, size, leaves, low, high)
      }
      let leaves_per_part = leaves >> order
      let start_leaf = p * leaves_per_part
      let end_leaf = (p + 1) * leaves_per_part
      let mut rice_cost = (if low == 0 {
          sum
        } else {
          encoder_prefix_quotient(scratch, start_leaf, end_leaf, low)
        }) +
        count * (low + 1).to_int64()
      for k = low + 1; k <= high; k = k + 1 {
        let cost = encoder_prefix_quotient(scratch, start_leaf, end_leaf, k) +
          count * (k + 1).to_int64()
        if cost < rice_cost {
          parameter = k
          rice_cost = cost
        }
      }
      let k0 = if parameter > 14 { 14 } else { parameter }
      let cost0 = (if parameter > 14 {
          if !scratch.ready[14] {
            encoder_prepare_leaf_prefixes(scratch, size, leaves, 14, 14)
          }
          encoder_prefix_quotient(scratch, start_leaf, end_leaf, 14) +
          15L * count
        } else {
          rice_cost
        }) +
        4L
      let cost1 = rice_cost + 5L
      let escaped = 9L + count * width.to_int64()
      if width <= 31 && escaped < cost0 {
        scratch.choices0[p] = 32 + width
        bits0 += escaped
      } else {
        scratch.choices0[p] = k0
        bits0 += cost0
      }
      if width <= 31 && escaped + 1L < cost1 {
        scratch.choices1[p] = 32 + width
        bits1 += escaped + 1L
      } else {
        scratch.choices1[p] = parameter
        bits1 += cost1
      }
      // Rice2 has one additional parameter-header bit per remaining part.
      if bits0 + remaining >= best_bits &&
        bits1 + remaining + (parts - p - 1).to_int64() >= best_bits {
        abandoned = true
        break
      }
    }
    // Prefix costs alone can still be below best_bits after a bound rejection.
    // Never materialize the incomplete choices array as a complete plan.
    if abandoned {
      continue
    }
    let rice2 = bits1 < bits0
    let bits = if rice2 { bits1 } else { bits0 }
    if bits < best_bits {
      let choices = if rice2 { scratch.choices1 } else { scratch.choices0 }
      let selected = Array::makei(parts, p => {
        let choice = choices[p]
        {
          parameter: if choice >= 32 {
            if rice2 {
              31
            } else {
              15
            }
          } else {
            choice
          },
          width: if choice >= 32 {
            choice - 32
          } else {
            -1
          },
          count: if p == 0 {
            step - predictor
          } else {
            step
          },
        }
      })
      best = Some({ order, rice2, parts: selected, bits, })
      best_bits = bits
    }
  }
  best
}

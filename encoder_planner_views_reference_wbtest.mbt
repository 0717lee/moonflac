///|
fn c76_checked_residual_plan(
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
  for p = 0; p < initial_leaves; p = p + 1 {
    let start = if p == 0 { predictor } else { p * leaf_size }
    let end = (p + 1) * leaf_size
    let mut width = 0
    let mut width_sum = 0
    let mut sum = 0L
    for i = start; i < end; i = i + 1 {
      let value = samples[i]
      let folded = encoder_fold_u32(value)
      let w = 32 - folded.clz()
      if w > width {
        width = w
      }
      width_sum += w + 1
      scratch.folded.unsafe_set(i, folded)
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

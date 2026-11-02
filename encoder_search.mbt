// Speed-first search policy. Scores only rank candidates; exact integer
// residuals and legal serialized costs still decide the emitted subframe.

///|
// Ordering only: every fixed predictor still reaches the original full legality
// and exact residual planner. Scores include warmups and at most 256 interior
// positions plus four samples at each edge. Invalid probes rank last, not out.
fn encoder_fixed_ordering(
  samples : Array[Int64],
  depth : Int32,
) -> Array[Int32] {
  let size = samples.length()
  let positions = encoder_rice_probe_positions(size, 4)
  let scores = Array::makei(5, order => {
    let coefficients = encoder_fixed_coefficients(order)
    let mut widths = 0L
    let mut count = 0L
    let mut valid = true
    for i in positions {
      if i < order {
        continue
      }
      let mut value = samples[i]
      for j in 0..<order {
        value -= coefficients[j] * samples[i - j - 1]
      }
      if value <= -2147483648L || value >= 2147483648L {
        valid = false
        break
      }
      widths += encoder_signed_width(value).to_int64()
      count += 1L
    }
    if valid {
      widths * (size - order).to_int64() / count + (order * depth).to_int64()
    } else {
      9223372036854775807L
    }
  })
  let orders = [0, 1, 2, 3, 4]
  for i in 1..<5 {
    let current = orders[i]
    let mut at = i
    while at > 0 && scores[orders[at - 1]] > scores[current] {
      orders[at] = orders[at - 1]
      at -= 1
    }
    orders[at] = current
  }
  orders
}

///|
const ENCODER_LPC_SHORTLIST : Int32 = 4

///|
const ENCODER_LPC_PROBES : Int32 = 256

///|
const ENCODER_PARTITION_CAP : Int32 = 8

///|
fn encoder_rice_probe_positions(
  size : Int32,
  edge_span : Int32,
) -> Array[Int32] {
  let interior = size - 2 * edge_span
  let count = if interior < ENCODER_LPC_PROBES {
    interior
  } else {
    ENCODER_LPC_PROBES
  }
  let positions : Array[Int32] = []
  for i = 0; i < edge_span; i = i + 1 {
    positions.push(i)
  }
  if count > 0 {
    let denominator = if count > 1 { count - 1 } else { 1 }
    let step = if count > 1 { (interior - 1) / denominator } else { 0 }
    let remainder = if count > 1 { (interior - 1) % denominator } else { 0 }
    let mut position = edge_span
    let mut fraction = 0
    for _j = 0; _j < count; _j = _j + 1 {
      positions.push(position)
      position += step
      fraction += remainder
      if fraction >= denominator {
        position += 1
        fraction -= denominator
      }
    }
  }
  for i = size - edge_span; i < size; i = i + 1 {
    positions.push(i)
  }
  positions
}

///|
fn encoder_rice_weighted_quotient(
  folded : Array[Int64],
  weights : Array[Int64],
  parameter : Int32,
) -> Int64 {
  let mut sum = 0L
  for i = 0; i < folded.length(); i = i + 1 {
    sum += (folded.unsafe_get(i) >> parameter) * weights.unsafe_get(i)
  }
  sum
}

///|
/// Stratified order-zero cost in units1/M, not a bound on unseen residuals.
/// Edge probes have multiplicity M; interior probes multiplicity H. The
/// expanded count is exactly M*(n-order), so the convex Rice window is exact
/// for this integer multiset. When H<=256, it is the full order-zero cost*M.
fn encoder_lpc_rice_score(
  samples : Array[Int64],
  model : LpcModel,
  depth : Int32,
  edge_span : Int32,
  positions : Array[Int32],
) -> Int64? {
  let size = samples.length()
  let order = model.coefficients.length()
  let interior = size - 2 * edge_span
  if depth < 1 ||
    depth > 33 ||
    order < 1 ||
    order > 32 ||
    order > edge_span ||
    interior <= 0 ||
    model.shift < 0 ||
    model.shift > 15 ||
    model.precision < 1 ||
    model.precision > 15 {
    return None
  }
  let coefficient_bound = 1L << (model.precision - 1)
  for coefficient in model.coefficients {
    if coefficient < -coefficient_bound || coefficient >= coefficient_bound {
      return None
    }
  }
  let scale = (if interior < ENCODER_LPC_PROBES {
    interior
  } else {
    ENCODER_LPC_PROBES
  }).to_int64()
  let count = scale * (size - order).to_int64()
  let folded : Array[Int64] = []
  let weights : Array[Int64] = []
  let mut sum = 0L
  let mut width = 0
  for i in positions {
    if i < order {
      continue
    }
    let mut prediction = 0L
    for j = 0; j < order; j = j + 1 {
      prediction += model.coefficients.unsafe_get(j) *
        samples.unsafe_get(i - j - 1)
    }
    let residual = samples.unsafe_get(i) - (prediction >> model.shift)
    if residual <= -2147483648L || residual >= 2147483648L {
      return None
    }
    let value = if residual < 0L { -2L * residual - 1L } else { 2L * residual }
    let weight = if i < edge_span || i >= size - edge_span {
      scale
    } else {
      interior.to_int64()
    }
    folded.push(value)
    weights.push(weight)
    sum += value * weight
    let bits = encoder_signed_width(residual)
    if bits > width {
      width = bits
    }
  }
  // S<2^56 and count<2^24 for FLAC blocks, so shifts/costs fit Int64.
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
  let mut best_parameter = low
  let mut rice_cost = encoder_rice_weighted_quotient(folded, weights, low) +
    count * (low + 1).to_int64()
  for parameter = low + 1; parameter <= high; parameter = parameter + 1 {
    let cost = encoder_rice_weighted_quotient(folded, weights, parameter) +
      count * (parameter + 1).to_int64()
    if cost < rice_cost {
      rice_cost = cost
      best_parameter = parameter
    }
  }
  let rice4_cost = if best_parameter > 14 {
    encoder_rice_weighted_quotient(folded, weights, 14) + 15L * count
  } else {
    rice_cost
  }
  let mut cost = 10L * scale + rice4_cost
  let rice2 = 11L * scale + rice_cost
  if rice2 < cost {
    cost = rice2
  }
  if width <= 31 {
    let escape = 15L * scale + count * width.to_int64()
    if escape < cost {
      cost = escape
    }
  }
  // Wasted-bit unary overhead is common to the pool and does not affect ranks.
  Some(
    cost + (8 + order * depth + 9 + order * model.precision).to_int64() * scale,
  )
}

///|
fn encoder_lpc_rice_ranking(
  samples : Array[Int64],
  models : Array[LpcModel],
  depth : Int32,
) -> Array[LpcModel] {
  let mut maximum = 0
  for model in models {
    if model.coefficients.length() <= 32 &&
      model.coefficients.length() > maximum {
      maximum = model.coefficients.length()
    }
  }
  if maximum == 0 {
    return []
  }
  let edge_span = 2 * maximum
  if samples.length() <= 2 * edge_span {
    return []
  }
  let positions = encoder_rice_probe_positions(samples.length(), edge_span)
  let selected : Array[LpcModel] = []
  let scores : Array[Int64] = []
  for model in models {
    if encoder_lpc_rice_score(samples, model, depth, edge_span, positions)
      is Some(score) {
      let mut i = 0
      while i < scores.length() && scores[i] <= score {
        i += 1
      }
      selected.insert(i, model)
      scores.insert(i, score)
    }
  }
  selected
}

///|
/// log2(x) via range reduction to [1,2) and the atanh series through z^11,
/// z=(x-1)/(x+1)<=1/3. Tail error is below 1.6e-7 bits. Ranking only.
fn encoder_variance_log2(value : Double) -> Double {
  let mut x = value
  let mut exponent = 0.0
  while x >= 2.0 {
    x *= 0.5
    exponent += 1.0
  }
  while x < 1.0 {
    x *= 2.0
    exponent -= 1.0
  }
  let z = (x - 1.0) / (x + 1.0)
  let z2 = z * z
  let mut term = z
  let mut sum = z
  for denominator in [3.0, 5.0, 7.0, 9.0, 11.0] {
    term *= z2
    sum += term / denominator
  }
  exponent + 2.8853900817779268 * sum
}

///|
/// A Gaussian-scale coding proxy, max(1, 2 + log2(sigma)), plus actual warmup
/// and coefficient header bits. It is a heuristic ranking, never a pruning
/// proof. Every generated precision/order model remains eligible and exact
/// full residual legality plus the exact budget planner select four finalists.
/// Invalid or cancellation-limited covariance falls back to the prior sampled
/// ranking for the complete pool; no zero/negative variance becomes a winner.
/// One PCM quantum is also an explicit validity boundary: integer prediction
/// floors introduce an error smaller than one sample unit. When any model's
/// estimated residual standard deviation is below that unit (variance < 1),
/// the continuous statistic is not a small-error approximation. Use the prior
/// sampled ranking for the entire pool, preserving its deterministic ordering.
/// This is a dimensional approximation guard, not a compression quality proof.
fn encoder_lpc_variance_ranking(
  samples : Array[Int64],
  models : Array[LpcModel],
  variances : Array[Double?],
  depth : Int32,
) -> Array[LpcModel] {
  if variances.length() != models.length() ||
    variances.any(v => {
      match v {
        None => true
        Some(value) => value < 1.0 || value.is_nan() || value.is_inf()
      }
    }) {
    return encoder_lpc_shortlist(samples, models, depth, limit=models.length())
  }
  let selected : Array[LpcModel] = []
  let scores : Array[Double] = []
  for i in 0..<models.length() {
    let model = models[i]
    let variance = variances[i].unwrap()
    let estimate = 2.0 + 0.5 * encoder_variance_log2(variance)
    let bits = if estimate < 1.0 { 1.0 } else { estimate }
    let order = model.coefficients.length()
    let score = (samples.length() - order).to_double() * bits +
      (order * (depth + model.precision) + 9).to_double()
    let mut index = 0
    while index < scores.length() && scores[index] <= score {
      index += 1
    }
    scores.insert(index, score)
    selected.insert(index, model)
  }
  selected
}

///|
fn encoder_partition_lower_bound(
  widths : Array[Int32],
  predictor : Int32,
  order : Int32,
  stop_at~ : Int64 = 9223372036854775807L,
) -> Int64 {
  let step = widths.length() >> order
  let mut total = 6L
  for p = 0; p < 1 << order; p = p + 1 {
    let start = if p == 0 { predictor } else { p * step }
    let end = (p + 1) * step
    let mut rice = 4
    let mut maximum = 0
    for i = start; i < end; i = i + 1 {
      let width = widths[i]
      rice += width + 1
      if width > maximum {
        maximum = width
      }
    }
    // For folded u, (u >> k) + k + 1 >= bit_length(u) + 1.
    // Signed width equals that bit length, including width zero for zero.
    // Four parameter bits underestimates Rice2's five, so this also bounds it.
    let escaped = 9 + (end - start) * maximum
    total += (if maximum <= 31 && escaped < rice { escaped } else { rice }).to_int64()
    if total >= stop_at {
      return total
    }
  }
  total
}

///|
fn encoder_adaptive_residual_plan(
  samples : Array[Int64],
  predictor : Int32,
  workspace~ : Array[Array[Int64]] = [],
) -> EncoderResidual {
  let coarse = encoder_residual_plan(
    samples,
    predictor,
    ENCODER_PARTITION_CAP,
    workspace~,
  )
  let size = samples.length()
  let mut maximum = ENCODER_PARTITION_CAP
  while maximum < 15 &&
        size % (1 << (maximum + 1)) == 0 &&
        size >> (maximum + 1) > predictor {
    maximum += 1
  }
  if maximum == ENCODER_PARTITION_CAP ||
    6L + (4L << (ENCODER_PARTITION_CAP + 1)) >= coarse.bits {
    return coarse
  }
  let widths = Array::makei(size, i => {
    if i < predictor {
      0
    } else {
      encoder_signed_width(samples[i])
    }
  })
  for order = maximum; order > ENCODER_PARTITION_CAP; order = order - 1 {
    let lower = encoder_partition_lower_bound(
      widths,
      predictor,
      order,
      stop_at=coarse.bits,
    )
    if lower < coarse.bits {
      // Higher levels already have a proven lower bound >= the coarse plan.
      // Exact search through this level therefore retains the global optimum.
      // A tie at a higher level cannot replace the earlier, lower-order plan.
      return encoder_residual_plan(samples, predictor, order, workspace~)
    }
  }
  coarse
}

///|
fn encoder_lpc_shortlist(
  samples : Array[Int64],
  models : Array[LpcModel],
  depth : Int32,
  limit~ : Int32 = ENCODER_LPC_SHORTLIST,
) -> Array[LpcModel] {
  let selected : Array[LpcModel] = []
  let scores : Array[Int64] = []
  for model in models {
    let order = model.coefficients.length()
    let available = samples.length() - order
    let probes = if available < ENCODER_LPC_PROBES {
      available
    } else {
      ENCODER_LPC_PROBES
    }
    let mut sum = 0L
    let mut valid = true
    if probes <= 0 {
      continue
    }
    // Exact floor(j*(available-1)/(probes-1)) via a quotient/remainder
    // recurrence: two divisions per model, not one division per probe.
    let denominator = if probes > 1 { probes - 1 } else { 1 }
    let step = if probes > 1 { (available - 1) / denominator } else { 0 }
    let remainder = if probes > 1 { (available - 1) % denominator } else { 0 }
    let mut i = order
    let mut fraction = 0
    for j = 0; j < probes; j = j + 1 {
      let mut prediction = 0L
      for k = 0; k < order; k = k + 1 {
        // Every probe lies in [order,n); k<order proves history bounds.
        prediction += model.coefficients.unsafe_get(k) *
          samples.unsafe_get(i - k - 1)
      }
      let residual = samples.unsafe_get(i) - (prediction >> model.shift)
      if residual <= -2147483648L || residual >= 2147483648L {
        valid = false
        break
      }
      sum += (encoder_signed_width(residual) + 1).to_int64()
      i += step
      fraction += remainder
      if fraction >= denominator {
        i += 1
        fraction -= denominator
      }
    }
    if valid && probes > 0 {
      let score = sum * available.to_int64() / probes.to_int64() +
        (order * (depth + model.precision) + 9).to_int64()
      let mut index = 0
      while index < scores.length() && scores[index] <= score {
        index += 1
      }
      if index < limit {
        scores.insert(index, score)
        selected.insert(index, model)
        if scores.length() > limit {
          scores.pop() |> ignore
          selected.pop() |> ignore
        }
      }
    }
  }
  selected
}

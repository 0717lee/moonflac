///|
fn lpc_register_frozen_predict(
  samples : Array[Int64],
  signal : FixedArray[Double],
  coefficients : FixedArray[Double],
  shift : Int32,
  residual : Array[Int64],
  tile : FixedArray[Double],
) -> Bool {
  let order = coefficients.length()
  let size = samples.length()
  let scale = 1.0 / (1L << shift).to_double()
  for start = order; start < size; start = start + 128 {
    let count = if size - start < 128 { size - start } else { 128 }
    for i = 0; i < count; i = i + 1 {
      tile.unsafe_set(i, 0.0)
    }
    for j = 0; j < order; j = j + 1 {
      let coefficient = coefficients.unsafe_get(j)
      for i = 0; i < count; i = i + 1 {
        // j<order<=start and i<count<=size-start prove all indices.
        tile.unsafe_set(
          i,
          tile.unsafe_get(i) +
          coefficient * signal.unsafe_get(start + i - j - 1),
        )
      }
    }
    // This pass touches scratch only: a later failed lane must leave the
    // residual suffix unchanged, just like the scalar integer predictor.
    for i = 0; i < count; i = i + 1 {
      let difference = signal.unsafe_get(start + i) - tile.unsafe_get(i) * scale
      let biased = difference + 6755399441055744.0
      let rounded = biased - 6755399441055744.0
      tile.unsafe_set(
        i,
        biased + (if rounded < difference { 1.0 } else { 0.0 }),
      )
    }
    for i = 0; i < count; i = i + 1 {
      let bits = tile.unsafe_get(i).reinterpret_as_uint64()
      // The accepted biased doubles encode precisely -2^31+1 .. 2^31-1.
      if bits - 0x4337ffff80000001UL >= 0xffffffffUL {
        return false
      }
      residual.unsafe_set(start + i, bits.to_int().to_int64())
    }
  }
  true
}

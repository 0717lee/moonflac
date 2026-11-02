// RFC 9639 section 9. Sample arithmetic stays in Int64 through decorrelation.

///|
priv struct FrameBits {
  data : Bytes
  mut pos : Int32
  mut bit : Int32
  base : Int64
}

///|
fn FrameBits::bad(self : FrameBits, message : String) -> Unit raise FlacError {
  raise Invalid(self.base + self.pos.to_int64(), message)
}

///|
fn FrameBits::read(self : FrameBits, width : Int32) -> Int64 raise FlacError {
  let mut result = 0L
  let mut left = width
  while left > 0 {
    if self.pos >= self.data.length() {
      raise NeedMore
    }
    let take = if left < 8 - self.bit { left } else { 8 - self.bit }
    let part = (self.data[self.pos].to_int() >> (8 - self.bit - take)) &
      ((1 << take) - 1)
    result = (result << take) | part.to_int64()
    self.bit += take
    if self.bit == 8 {
      self.bit = 0
      self.pos += 1
    }
    left -= take
  }
  result
}

///|
fn FrameBits::signed(self : FrameBits, width : Int32) -> Int64 raise FlacError {
  if width == 0 {
    return 0L
  }
  let n = self.read(width)
  if (n & (1L << (width - 1))) != 0L {
    n - (1L << width)
  } else {
    n
  }
}

///|
fn FrameBits::unary(self : FrameBits, maximum : Int64) -> Int64 raise FlacError {
  let mut n = 0L
  while self.pos < self.data.length() {
    let available = 8 - self.bit
    let tail = self.data[self.pos].to_int() & ((1 << available) - 1)
    if tail == 0 {
      // Long Rice quotients are legal. Skip each all-zero byte in one step,
      // including the unused tail when the code starts mid-byte.
      n += available.to_int64()
      self.pos += 1
      self.bit = 0
    } else {
      let mut zeros = 0
      let mut mask = 1 << (available - 1)
      while (tail & mask) == 0 {
        zeros += 1
        mask = mask >> 1
      }
      n += zeros.to_int64()
      self.bit += zeros + 1
      if self.bit == 8 {
        self.bit = 0
        self.pos += 1
      }
      if n > maximum {
        self.bad("unary value exceeds legal range")
      }
      return n
    }
    if n > maximum {
      self.bad("unary value exceeds legal range")
    }
  }
  raise NeedMore
}

///|
// Generated MSB-first polynomial 0x0007, initial zero.
// Private process-lifetime table; no writes or references escape this module.
let frame_crc8_table : FixedArray[Int32] = [
  0, 7, 14, 9, 28, 27, 18, 21, 56, 63, 54, 49, 36, 35, 42, 45, 112, 119, 126, 121,
  108, 107, 98, 101, 72, 79, 70, 65, 84, 83, 90, 93, 224, 231, 238, 233, 252, 251,
  242, 245, 216, 223, 214, 209, 196, 195, 202, 205, 144, 151, 158, 153, 140, 139,
  130, 133, 168, 175, 166, 161, 180, 179, 186, 189, 199, 192, 201, 206, 219, 220,
  213, 210, 255, 248, 241, 246, 227, 228, 237, 234, 183, 176, 185, 190, 171, 172,
  165, 162, 143, 136, 129, 134, 147, 148, 157, 154, 39, 32, 41, 46, 59, 60, 53, 50,
  31, 24, 17, 22, 3, 4, 13, 10, 87, 80, 89, 94, 75, 76, 69, 66, 111, 104, 97, 102,
  115, 116, 125, 122, 137, 142, 135, 128, 149, 146, 155, 156, 177, 182, 191, 184,
  173, 170, 163, 164, 249, 254, 247, 240, 229, 226, 235, 236, 193, 198, 207, 200,
  221, 218, 211, 212, 105, 110, 103, 96, 117, 114, 123, 124, 81, 86, 95, 88, 77,
  74, 67, 68, 25, 30, 23, 16, 5, 2, 11, 12, 33, 38, 47, 40, 61, 58, 51, 52, 78, 73,
  64, 71, 82, 85, 92, 91, 118, 113, 120, 127, 106, 109, 100, 99, 62, 57, 48, 55,
  34, 37, 44, 43, 6, 1, 8, 15, 26, 29, 20, 19, 174, 169, 160, 167, 178, 181, 188,
  187, 150, 145, 152, 159, 138, 141, 132, 131, 222, 217, 208, 215, 194, 197, 204,
  203, 230, 225, 232, 239, 250, 253, 244, 243,
]

///|
// Generated MSB-first polynomial 0x8005, initial zero.
// Private process-lifetime table; no writes or references escape this module.
let frame_crc16_table : FixedArray[Int32] = [
  0, 32773, 32783, 10, 32795, 30, 20, 32785, 32819, 54, 60, 32825, 40, 32813, 32807,
  34, 32867, 102, 108, 32873, 120, 32893, 32887, 114, 80, 32853, 32863, 90, 32843,
  78, 68, 32833, 32963, 198, 204, 32969, 216, 32989, 32983, 210, 240, 33013, 33023,
  250, 33003, 238, 228, 32993, 160, 32933, 32943, 170, 32955, 190, 180, 32945, 32915,
  150, 156, 32921, 136, 32909, 32903, 130, 33155, 390, 396, 33161, 408, 33181, 33175,
  402, 432, 33205, 33215, 442, 33195, 430, 420, 33185, 480, 33253, 33263, 490, 33275,
  510, 500, 33265, 33235, 470, 476, 33241, 456, 33229, 33223, 450, 320, 33093, 33103,
  330, 33115, 350, 340, 33105, 33139, 374, 380, 33145, 360, 33133, 33127, 354, 33059,
  294, 300, 33065, 312, 33085, 33079, 306, 272, 33045, 33055, 282, 33035, 270, 260,
  33025, 33539, 774, 780, 33545, 792, 33565, 33559, 786, 816, 33589, 33599, 826,
  33579, 814, 804, 33569, 864, 33637, 33647, 874, 33659, 894, 884, 33649, 33619,
  854, 860, 33625, 840, 33613, 33607, 834, 960, 33733, 33743, 970, 33755, 990, 980,
  33745, 33779, 1014, 1020, 33785, 1000, 33773, 33767, 994, 33699, 934, 940, 33705,
  952, 33725, 33719, 946, 912, 33685, 33695, 922, 33675, 910, 900, 33665, 640, 33413,
  33423, 650, 33435, 670, 660, 33425, 33459, 694, 700, 33465, 680, 33453, 33447,
  674, 33507, 742, 748, 33513, 760, 33533, 33527, 754, 720, 33493, 33503, 730, 33483,
  718, 708, 33473, 33347, 582, 588, 33353, 600, 33373, 33367, 594, 624, 33397, 33407,
  634, 33387, 622, 612, 33377, 544, 33317, 33327, 554, 33339, 574, 564, 33329, 33299,
  534, 540, 33305, 520, 33293, 33287, 514,
]

///|
// Width is 8 or 16 at all private callers. Checked data indexing retains
// the original slice-bound failure behavior; an empty/reversed range is 0.
fn frame_crc(data : Bytes, start : Int32, end : Int32, width : Int32) -> Int32 {
  let mut crc = 0
  if width == 8 {
    for i = start; i < end; i = i + 1 {
      crc = frame_crc8_table.unsafe_get(crc ^ data[i].to_int())
    }
  } else {
    for i = start; i < end; i = i + 1 {
      let index = (crc >> 8) ^ data[i].to_int()
      crc = ((crc << 8) & 65535) ^ frame_crc16_table.unsafe_get(index)
    }
  }
  crc
}

///|
fn frame_number(r : FrameBits, variable : Bool) -> Int64 raise FlacError {
  let first = r.read(8).to_int()
  if first < 128 {
    return first.to_int64()
  }
  let mut count = 0
  let mut mask = 128
  while (first & mask) != 0 && mask > 0 {
    count += 1
    mask = mask >> 1
  }
  if count < 2 || count > (if variable { 7 } else { 6 }) {
    r.bad("invalid coded frame/sample number")
  }
  let mut n = (first & (mask - 1)).to_int64()
  for i = 1; i < count; i = i + 1 {
    let b = r.read(8)
    if (b & 0xC0L) != 0x80L {
      r.bad("invalid coded-number continuation")
    }
    n = (n << 6) | (b & 63L)
  }
  let minima : Array[Int64] = [
    0L, 0L, 128L, 2048L, 65536L, 2097152L, 67108864L, 2147483648L,
  ]
  if n < minima[count] {
    r.bad("overlong coded frame/sample number")
  }
  n
}

///|
fn frame_residual(
  r : FrameBits,
  samples : Array[Int64],
  order : Int32,
) -> Unit raise FlacError {
  let coding = r.read(2).to_int()
  if coding > 1 {
    r.bad("reserved residual coding method")
  }
  let partition_order = r.read(4).to_int()
  let partitions = 1 << partition_order
  let size = samples.length() / partitions
  if samples.length() % partitions != 0 || size <= order {
    r.bad("invalid residual partition order")
  }
  let parameter_bits = coding + 4
  let mut index = order
  for p = 0; p < partitions; p = p + 1 {
    let count = if p == 0 { size - order } else { size }
    let parameter = r.read(parameter_bits).to_int()
    if parameter == (1 << parameter_bits) - 1 {
      let width = r.read(5).to_int()
      for i = 0; i < count; i = i + 1 {
        samples[index] = r.signed(width)
        index += 1
      }
    } else {
      for i = 0; i < count; i = i + 1 {
        let quotient = r.unary(4294967294L >> parameter)
        let folded = (quotient << parameter) | r.read(parameter)
        if folded > 4294967294L {
          r.bad("residual outside signed 31-bit magnitude")
        }
        samples[index] = if (folded & 1L) == 0L {
          folded >> 1
        } else {
          -(folded >> 1) - 1L
        }
        index += 1
      }
    }
  }
}

///|
fn frame_range(
  r : FrameBits,
  sample : Int64,
  width : Int32,
) -> Unit raise FlacError {
  let bound = 1L << (width - 1)
  if sample < -bound || sample >= bound {
    r.bad("decoded sample exceeds declared bit depth")
  }
}

///|
fn frame_subframe(
  r : FrameBits,
  size : Int32,
  width : Int32,
) -> Array[Int64] raise FlacError {
  if r.read(1) != 0L {
    r.bad("nonzero subframe padding bit")
  }
  let kind = r.read(6).to_int()
  let wasted = if r.read(1) == 0L {
    0
  } else {
    r.unary((width - 2).to_int64()).to_int() + 1
  }
  let depth = width - wasted
  let samples = Array::make(size, 0L)
  if kind == 0 {
    let value = r.signed(depth)
    samples.fill(value)
  } else if kind == 1 {
    for i = 0; i < size; i = i + 1 {
      samples[i] = r.signed(depth)
    }
  } else if (kind >= 8 && kind <= 12) || kind >= 32 {
    let order = if kind >= 32 { kind - 31 } else { kind - 8 }
    if order >= size {
      r.bad("predictor order is not smaller than block size")
    }
    for i = 0; i < order; i = i + 1 {
      samples[i] = r.signed(depth)
    }
    let coefficients : Array[Int64] = []
    let mut shift = 0
    if kind >= 32 {
      let precision = r.read(4).to_int() + 1
      if precision == 16 {
        r.bad("forbidden LPC coefficient precision")
      }
      shift = r.signed(5).to_int()
      if shift < 0 {
        r.bad("negative LPC shift is forbidden")
      }
      for i = 0; i < order; i = i + 1 {
        coefficients.push(r.signed(precision))
      }
    }
    frame_residual(r, samples, order)
    for i = order; i < size; i = i + 1 {
      let prediction = if kind >= 32 {
        let mut sum = 0L
        for j = 0; j < order; j = j + 1 {
          sum += coefficients[j] * samples[i - j - 1]
        }
        sum >> shift
      } else {
        match order {
          0 => 0L
          1 => samples[i - 1]
          2 => 2L * samples[i - 1] - samples[i - 2]
          3 => 3L * samples[i - 1] - 3L * samples[i - 2] + samples[i - 3]
          _ =>
            4L * samples[i - 1] -
            6L * samples[i - 2] +
            4L * samples[i - 3] -
            samples[i - 4]
        }
      }
      samples[i] += prediction
      // Validate before feeding a sample into another prediction: malformed
      // streams cannot grow coefficients into an Int64 overflow.
      frame_range(r, samples[i], depth)
    }
  } else {
    r.bad("reserved subframe type")
  }
  for i = 0; i < size; i = i + 1 {
    samples[i] = samples[i] << wasted
  }
  samples
}

///|
fn parse_frame(
  data : Bytes,
  start : Int32,
  info : StreamInfo,
  absolute_offset : Int64,
) -> (Frame, Int32) raise FlacError {
  if start < 0 || start > data.length() {
    raise Invalid(absolute_offset, "invalid frame offset")
  }
  let r : FrameBits = {
    data,
    pos: start,
    bit: 0,
    base: absolute_offset - start.to_int64(),
  }
  if r.read(15) != 0x7FFCL {
    r.bad("invalid frame sync")
  }
  let explicit_variable = r.read(1) != 0L
  let block_code = r.read(4).to_int()
  // Appendix B.1: pre-2007 encoders signaled variable blocking through
  // STREAMINFO and used only explicit block-size codes for these streams.
  let variable_block = explicit_variable ||
    (
      info.min_block_size != info.max_block_size &&
      (block_code == 6 || block_code == 7)
    )
  let rate_code = r.read(4).to_int()
  let assignment = r.read(4).to_int()
  let depth_code = r.read(3).to_int()
  if r.read(1) != 0L {
    r.bad("nonzero reserved frame header bit")
  }
  if block_code == 0 || rate_code == 15 || assignment > 10 || depth_code == 3 {
    r.bad("reserved frame header value")
  }
  let number = frame_number(r, variable_block)
  let block_size = match block_code {
    1 => 192
    2 | 3 | 4 | 5 => 144 << block_code
    6 => r.read(8).to_int() + 1
    7 => r.read(16).to_int() + 1
    _ => 1 << block_code
  }
  if block_size > 65535 {
    r.bad("forbidden block size 65536")
  }
  let sample_rate = match rate_code {
    0 => info.sample_rate
    1 => 88200
    2 => 176400
    3 => 192000
    4 => 8000
    5 => 16000
    6 => 22050
    7 => 24000
    8 => 32000
    9 => 44100
    10 => 48000
    11 => 96000
    12 => r.read(8).to_int() * 1000
    13 => r.read(16).to_int()
    _ => r.read(16).to_int() * 10
  }
  let bits_per_sample = match depth_code {
    0 => info.bits_per_sample
    1 => 8
    2 => 12
    4 => 16
    5 => 20
    6 => 24
    _ => 32
  }
  if bits_per_sample < 4 || bits_per_sample > 32 {
    r.bad("invalid sample bit depth")
  }
  let header_crc = frame_crc(data, start, r.pos, 8)
  if r.read(8).to_int() != header_crc {
    r.bad("frame header CRC8 mismatch")
  }
  let channel_count = if assignment < 8 { assignment + 1 } else { 2 }
  let decoded : Array[Array[Int64]] = []
  for channel = 0; channel < channel_count; channel = channel + 1 {
    let side = (assignment == 8 && channel == 1) ||
      (assignment == 9 && channel == 0) ||
      (assignment == 10 && channel == 1)
    decoded.push(
      frame_subframe(
        r,
        block_size,
        bits_per_sample + (if side { 1 } else { 0 }),
      ),
    )
  }
  if r.bit != 0 && r.read(8 - r.bit) != 0L {
    r.bad("nonzero frame alignment padding")
  }
  let crc = frame_crc(data, start, r.pos, 16)
  if r.read(16).to_int() != crc {
    r.bad("frame CRC16 mismatch")
  }
  if assignment >= 8 {
    for i = 0; i < block_size; i = i + 1 {
      let a = decoded[0][i]
      let b = decoded[1][i]
      if assignment == 8 {
        decoded[1][i] = a - b
      } else if assignment == 9 {
        decoded[0][i] = a + b
      } else {
        let mid = (a << 1) | (b & 1L)
        decoded[0][i] = (mid + b) >> 1
        decoded[1][i] = (mid - b) >> 1
      }
    }
  }
  let channels : Array[Array[Int32]] = []
  for channel in decoded {
    let output = Array::make(block_size, 0)
    for i = 0; i < block_size; i = i + 1 {
      frame_range(r, channel[i], bits_per_sample)
      output[i] = channel[i].to_int()
    }
    channels.push(output)
  }
  let sample_number = if variable_block {
    number
  } else {
    number * info.max_block_size.to_int64()
  }
  (
    {
      sample_number,
      number,
      variable_block,
      sample_rate,
      bits_per_sample,
      channels,
      block_size,
      byte_offset: absolute_offset,
      byte_length: r.pos - start,
    },
    r.pos,
  )
}

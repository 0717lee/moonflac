///|
/// Standard FLAC channel order, RFC 9639 section 9.1.3.
fn default_channel_mask(channels : Int32) -> UInt32 raise FlacError {
  match channels {
    1 => 0x4U
    2 => 0x3U
    3 => 0x7U
    4 => 0x33U
    5 => 0x37U
    6 => 0x3fU
    7 => 0x70fU
    8 => 0x63fU
    _ => raise Invalid(0L, "channel count outside FLAC range")
  }
}

///|
/// Read the optional RFC 9639 channel-layout tag. None means the standard
/// FLAC ordering; Some(0) explicitly leaves every channel's speaker undefined.
/// Fewer named speakers than audio channels is legal and is preserved.
/// Repeated equivalent tags are accepted; conflicting tags are an error.
pub fn Metadata::channel_mask(self : Metadata) -> UInt32? raise FlacError {
  let comments = match self.comments {
    None => return None
    Some(comments) => comments
  }
  let mut position = 4L
  for block in self.blocks {
    if block.kind == 4 {
      break
    }
    position += 4L + block.data.length().to_int64()
  }
  let mut mask : UInt32? = None
  for text in comments.values("WAVEFORMATEXTENSIBLE_CHANNEL_MASK") {
    if text.length() < 3 || !(text.has_prefix("0x") || text.has_prefix("0X")) {
      raise Invalid(
        position, "channel mask must contain 0x followed by hexadecimal digits",
      )
    }
    let mut value = 0U
    for char in text[2:] {
      let code = char.to_int()
      let digit = if code >= 48 && code <= 57 {
        code - 48
      } else if code >= 65 && code <= 70 {
        code - 65 + 10
      } else if code >= 97 && code <= 102 {
        code - 97 + 10
      } else {
        raise Invalid(position, "invalid hexadecimal digit in channel mask")
      }
      if value > 0x0fffffffU {
        raise Invalid(position, "channel mask exceeds unsigned 32-bit range")
      }
      value = (value << 4) | digit.to_uint()
    }
    if mask is Some(previous) {
      if previous != value {
        raise Invalid(position, "conflicting channel mask tags")
      }
    }
    mask = Some(value)
  }
  mask
}

///|
/// Resolve absent layout metadata to the standard FLAC channel assignment.
/// Explicit zero and partial assignments remain unchanged.
pub fn Metadata::effective_channel_mask(
  self : Metadata,
) -> UInt32 raise FlacError {
  match self.channel_mask() {
    Some(mask) => mask
    None => default_channel_mask(self.info.channels)
  }
}

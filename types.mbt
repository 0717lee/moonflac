///|
/// Positioned format errors, incomplete input, and explicit resource limits.
#derive(Debug)
pub suberror FlacError {
  NeedMore
  Invalid(Int64, String)
  Limit(String)
}

///|
/// Human-readable message for CLI and browser error surfaces.
pub impl Show for FlacError with fn to_string(self) {
  match self {
    NeedMore => "NeedMore"
    Invalid(offset, message) => "Invalid(\{offset}, \{message})"
    Limit(message) => "Limit(\{message})"
  }
}

///|
/// MoonBit 0.10.21 removed implicit promotion of trait methods; expose the
/// Show implementation as regular methods explicitly.
pub extend FlacError with Show::{to_string, output}

///|
/// STREAMINFO values. A zero total_samples or all-zero MD5 means unknown.
#derive(Debug)
pub(all) struct StreamInfo {
  min_block_size : Int32
  max_block_size : Int32
  min_frame_size : Int32
  max_frame_size : Int32
  sample_rate : Int32
  channels : Int32
  bits_per_sample : Int32
  total_samples : Int64
  md5 : Bytes
}

///|
/// Owned planar signed PCM, unshifted at its original bit depth.
#derive(Debug)
pub(all) struct Frame {
  sample_number : Int64
  number : Int64
  variable_block : Bool
  sample_rate : Int32
  bits_per_sample : Int32
  channels : Array[Array[Int32]]
  block_size : Int32
  byte_offset : Int64
  byte_length : Int32
}

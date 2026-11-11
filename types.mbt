///|
/// Positioned format errors, incomplete input, and explicit resource limits.
#derive(Show)
pub suberror FlacError {
  NeedMore
  Invalid(Int64, String)
  Limit(String)
}

///|
/// STREAMINFO values. A zero total_samples or all-zero MD5 means unknown.
#derive(Show)
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
#derive(Show)
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

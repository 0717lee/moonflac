///|
/// Signed unshifted integer PCM format; a sample is one channel value.
pub(all) struct PcmFormat {
  sample_rate : Int32
  channels : Int32
  bits_per_sample : Int32
} derive(Debug, Eq)

///|
/// Effort bounds candidate searches, never the accepted PCM domain.
pub(all) struct EncoderConfig {
  format : PcmFormat
  block_size : Int32
  variable_block : Bool
  effort : Int32
  channel_mask : UInt32?
  metadata : Array[MetadataBlock]
  non_audio : Bool
  max_metadata_bytes : Int32
}

///|
pub fn EncoderConfig::new(
  format : PcmFormat,
  block_size~ : Int32 = 4096,
  variable_block~ : Bool = false,
  effort~ : Int32 = 5,
  channel_mask? : UInt32,
  metadata~ : Array[MetadataBlock] = [],
  non_audio~ : Bool = false,
  max_metadata_bytes~ : Int32 = 67108864,
) -> EncoderConfig {
  {
    format,
    block_size,
    variable_block,
    effort,
    channel_mask,
    metadata,
    non_audio,
    max_metadata_bytes,
  }
}

///|
/// final_header replaces the original same-length header for seekable output.
/// Non-seekable output remains valid with zero unknown totals/digest fields.
pub(all) struct EncoderSummary {
  total_samples : Int64
  frames : Int64
  min_frame_size : Int32
  max_frame_size : Int32
  md5 : Bytes
  final_header : Bytes
}

///|
/// Each emitted byte chunk is owned and is never reused by the encoder.
pub(all) enum EncodeEvent {
  EncodedBytes(Bytes)
  NeedPcm
  EncoderDone(EncoderSummary)
}

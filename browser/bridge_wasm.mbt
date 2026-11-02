///|
/// Host imports only move bytes and numbers. The shared MoonBit decoder does
/// all parsing, integrity validation, prediction and integer WAV serialization.
fn input_length() -> Int32 = "moonflac" "input_length"

///|
fn input_byte(index : Int32) -> Int32 = "moonflac" "input_byte"

///|
fn begin(rate : Int32, channels : Int32, bits : Int32, samples : Int32) -> Unit = "moonflac" "begin"

///|
fn speaker_layout(mask : UInt32, explicit : Bool) -> Unit = "moonflac" "layout"

///|
fn pcm_sample(channel : Int32, index : Int32, value : Int32) -> Unit = "moonflac" "pcm_sample"

///|
fn bytes_begin(kind : Int32, length : Int32) -> Unit = "moonflac" "bytes_begin"

///|
fn bytes_put(index : Int32, value : Int32) -> Unit = "moonflac" "bytes_put"

///|
fn bytes_end() -> Unit = "moonflac" "bytes_end"

///|
fn channel_data(
  channel : Int32,
  offset : Int32,
  pcm : FixedArray[Int32],
) -> Unit {
  for i = 0; i < pcm.length(); i = i + 1 {
    pcm_sample(channel, offset + i, pcm[i])
  }
}

///|
fn send_bytes(kind : Int32, value : Bytes) -> Unit {
  bytes_begin(kind, value.length())
  for i = 0; i < value.length(); i = i + 1 {
    bytes_put(i, value[i].to_int())
  }
  bytes_end()
}

///|
fn status(value : String) -> Unit {
  send_bytes(0, @utf8.encode(value))
}

///|
fn metadata_text(value : String) -> Unit {
  send_bytes(1, @utf8.encode(value))
}

///|
fn fail(value : String) -> Unit {
  send_bytes(2, @utf8.encode(value))
}

///|
fn wav_data(value : Bytes) -> Unit {
  send_bytes(3, value)
}

///|
pub fn run_decode() -> Unit {
  decode_browser(Bytes::makei(input_length(), i => input_byte(i).to_byte()))
}

///|
pub fn run_export() -> Unit {
  export_browser(Bytes::makei(input_length(), i => input_byte(i).to_byte()))
}

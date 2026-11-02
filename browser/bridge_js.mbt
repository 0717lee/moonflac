///|
/// Browser boundary only: all compressed audio is decoded by the library.
extern "js" fn begin(
  rate : Int32,
  channels : Int32,
  bits : Int32,
  samples : Int32,
) -> Unit =
  #| (rate, channels, bits, samples) => globalThis.moonflacBegin(rate, channels, bits, samples)

///|
extern "js" fn channel_data(
  channel : Int32,
  offset : Int32,
  pcm : FixedArray[Int32],
) -> Unit =
  #| (channel, offset, pcm) => globalThis.moonflacChannel(channel, offset, pcm)

///|
extern "js" fn status(value : String) -> Unit =
  #| value => globalThis.moonflacStatus(value)

///|
extern "js" fn metadata_text(value : String) -> Unit =
  #| value => globalThis.moonflacMetadata(value)

///|
extern "js" fn fail(value : String) -> Unit =
  #| value => { throw new Error(value); }

///|
extern "js" fn wav_data(value : Bytes) -> Unit =
  #| value => globalThis.moonflacWav(value)

///|
extern "js" fn speaker_layout(mask : UInt32, explicit : Bool) -> Unit =
  #| (mask, explicit) => globalThis.moonflacLayout(mask, explicit)

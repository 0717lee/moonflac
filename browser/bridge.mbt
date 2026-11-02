///|
/// Enforce the preview's PCM budget while consuming frames, before whole-file
/// allocation. The library decoder itself remains suitable for longer streams.
suberror PreviewError {
  PreviewError(String)
} derive(Show)

///|
fn preview_audio(data : Bytes) -> @moonflac.Audio raise {
  let decoder = @moonflac.Decoder::new()
  let frames = []
  let mut metadata : @moonflac.Metadata? = None
  let mut cursor = 0
  let mut channel_samples = 0L
  let mut all_verified = true
  while true {
    match decoder.next() {
      MetadataReady(value) =>
        if metadata is Some(first) {
          if first.info.sample_rate != value.info.sample_rate ||
            first.info.bits_per_sample != value.info.bits_per_sample ||
            first.info.channels != value.info.channels {
            raise PreviewError(
              "Chained recording changes audio format. Use the library frame API for each link.",
            )
          }
          if first.effective_channel_mask() != value.effective_channel_mask() {
            raise PreviewError(
              "Chained recording changes speaker layout. Use the library frame API for each link.",
            )
          }
        } else {
          metadata = Some(value)
        }
      LinkEnd(integrity) =>
        if integrity == Md5Unavailable {
          all_verified = false
        }
      AudioFrame(frame) => {
        if metadata is Some(meta) {
          if frame.sample_rate != meta.info.sample_rate ||
            frame.bits_per_sample != meta.info.bits_per_sample ||
            frame.channels.length() != meta.info.channels {
            raise PreviewError(
              "This recording changes audio format between frames. Use the library frame API.",
            )
          }
        }
        channel_samples += frame.block_size.to_int64() *
          frame.channels.length().to_int64()
        if channel_samples > 33554432L {
          raise PreviewError(
            "Preview PCM limit: 32 million channel samples. Use the streaming CLI for larger recordings.",
          )
        }
        frames.push(frame)
      }
      Done(integrity) =>
        match metadata {
          Some(metadata) =>
            return {
              metadata,
              frames,
              integrity: if all_verified {
                integrity
              } else {
                Md5Unavailable
              },
            }
          None => raise PreviewError("missing STREAMINFO")
        }
      NeedInput =>
        if cursor < data.length() {
          let end = if data.length() - cursor > 16384 {
            cursor + 16384
          } else {
            data.length()
          }
          cursor += decoder.push(data[cursor:end].to_owned())
        } else {
          decoder.finish()
        }
    }
  } nobreak {
    raise PreviewError("decoder ended without result")
  }
}

///|
/// Input is a Uint8Array; output is delivered to the worker-owned sinks.
pub fn decode_browser(data : Bytes) -> Unit {
  try {
    let audio = preview_audio(data)
    let info = audio.metadata.info
    let mut count = 0
    for frame in audio.frames {
      count += frame.block_size
    }
    begin(info.sample_rate, info.channels, info.bits_per_sample, count)
    speaker_layout(
      audio.metadata.effective_channel_mask(),
      audio.metadata.channel_mask() is Some(_),
    )
    let mut offset = 0
    for frame in audio.frames {
      for ch = 0; ch < info.channels; ch = ch + 1 {
        channel_data(
          ch,
          offset,
          FixedArray::makei(frame.block_size, i => frame.channels[ch][i]),
        )
      }
      offset += frame.block_size
    }
    status(audio.integrity.to_string())
    let meta = audio.metadata
    let text = StringBuilder()
    text.write_string(
      "Metadata blocks: \{meta.blocks.length()}; seek points: \{meta.seek_points.length()}; pictures: \{meta.pictures.length()}; cue sheets: \{meta.cuesheets.length()}\n",
    )
    if meta.comments is Some(comments) {
      text.write_string("Vendor: \{comments.vendor}\n")
      for entry in comments.entries {
        text.write_string(entry)
        text.write_string("\n")
      }
    }
    metadata_text(text.to_string())
  } catch {
    err => fail(err.to_string())
  }
}

///|
/// Export through the same integer WAV serialization as the CLI.
pub fn export_browser(data : Bytes) -> Unit {
  try {
    let audio = preview_audio(data)
    let info = audio.metadata.info
    let mut samples = 0L
    for frame in audio.frames {
      samples += frame.block_size.to_int64()
    }
    let header = match audio.metadata.channel_mask() {
      Some(mask) => @moonflac.wav_header(info, samples, channel_mask=mask)
      None => @moonflac.wav_header(info, samples)
    }
    wav_data(header)
    for frame in audio.frames {
      wav_data(@moonflac.frame_pcm(frame, wav=true))
    }
    if samples *
      info.channels.to_int64() *
      ((info.bits_per_sample + 7) / 8).to_int64() %
      2L !=
      0L {
      wav_data(b"\x00")
    }
  } catch {
    err => fail(err.to_string())
  }
}

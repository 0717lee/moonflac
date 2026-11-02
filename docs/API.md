# API contracts

Import `0717lee/moonflac` as `@flac` in `moon.pkg`. The library is platform independent; decoding consumes `Bytes` and produces integer PCM, while encoding consumes integer PCM and produces native FLAC `Bytes`. See `examples/stream` for an executable example on all three targets.

`Decoder`, `RawDecoder`, `OggDemux`, `Encoder` and `PcmInput` are opaque state types. Construct and drive them through public methods; mutable parser internals are not part of the exported API.

## Whole input

`decode(data : Bytes) -> Audio raise FlacError` validates one native stream or one Ogg logical link. `Audio` contains `metadata`, owned `frames` and `integrity`. `decode_chained(data)` returns `Array[Audio]`, separating Ogg links so sample counts, MD5 and format changes remain meaningful. Use the latter for chained Ogg; `decode` deliberately rejects multiple links instead of silently joining different formats.

`Frame.channels` is planar `Array[Array[Int]]`: `channels[channel][sample]`. Integers carry the original signed sample values without left alignment. `block_size` is samples per channel; `sample_rate` and `bits_per_sample` describe this frame. `sample_number` is the per-link first sample, `number` retains the coded header number, and `variable_block` identifies the interpreted strategy. Native `byte_offset`/`byte_length` address the compressed source; Ogg positions refer to reconstructed FLAC data, not Ogg page byte addresses.

The initial frame must agree with STREAMINFO; subsequent property changes are permitted by FLAC. After the first property change, original STREAMINFO frame-byte size hints no longer constrain later frames. Always inspect frame properties when consuming PCM. A device or one WAV file may have stricter format requirements than the decoder.

## Incremental input

1. Construct `Decoder::new(max_buffer_bytes=33554432)` or provide another explicit compressed-buffer budget.
2. Call `next()` until it returns `NeedInput`, processing each event immediately.
3. Supply bytes through `push(bytes)`. It copies an accepted prefix and returns its length. Advance the source cursor by exactly that value, retaining the remainder for subsequent calls.
4. At actual source EOF, call `finish()`, then keep calling `next()` until `Done` or an error.

Events are `MetadataReady(Metadata)`, `AudioFrame(Frame)`, `LinkEnd(Integrity)` for a preceding Ogg link, `NeedInput`, and final `Done(Integrity)`. `finish` declares EOF; it does not replace draining. `Done` is stable on repeated calls. A decode error is terminal. Do not push after finishing.

Incomplete parses are retried at geometrically increasing buffered sizes to avoid repeatedly decoding the same partial frame after each tiny chunk. This can add lookahead latency up to approximately the current partial-frame size. `finish` forces the final parse even below that threshold. Applications requiring low latency should deliver natural transport chunks and drain promptly; `NeedInput` is a request for more bytes, not a promise that every possible partial frame has just been reparsed.

CRC checks precede `AudioFrame`. MD5 can only be established at the end of a complete link: previously emitted frames are provisional with respect to global integrity. `Md5Verified` means a supplied MD5 matched. `Md5Unavailable` means STREAMINFO had all-zero MD5; CRC checks still ran. A mismatch is an error, never `Md5Unavailable`.

Output arrays belong to the caller and are not reused by later calls. Mutating an emitted frame does not mutate future frames, but of course changes that caller's PCM. Discard frames after use to avoid accumulating all decoded audio. Retained metadata, output arrays, input held by the caller, Ogg packet assembly and temporary allocations are separate from compressed-buffer counters. `buffered_bytes()` and `peak_buffered_bytes()` describe their documented compressed storage, not total process RSS. The default limit is a resource policy, not a FLAC format limit; valid unusually large metadata/frames may require raising it.

For Ogg-aware accounting, `compressed_storage_bytes()` includes native staging plus retained Ogg pages/partial packets. `peak_compressed_storage_bytes()` adds independently observed native and Ogg peaks; it is a conservative upper bound because those peaks may occur at different times. It still excludes metadata, PCM and temporary host allocations. The default compressed budget is 32 MiB; use a larger configured budget for legitimate large inputs such as subset 55's 87.3 MB file containing 82.2 MB of metadata, validated with a 128 MiB budget.

## Errors and recovery

`FlacError` has `NeedMore`, `Invalid(Int64, String)` and `Limit(String)`. Lower-level parsers use `NeedMore`; the streaming decoder translates incomplete input into `NeedInput` until EOF, and a positioned truncation error after EOF. `Invalid` covers reserved syntax, bounds, CRC/MD5, numbering and malformed data. `Limit` identifies a configured or representational resource boundary. Input errors do not authorize accepting partial output as an intact file.

`RawDecoder` is a separate API for standalone framed FLAC without file metadata, and explicitly reported recovery. Construct it with optional `info` to resolve frame-header codes that refer to STREAMINFO. Its push/next/finish contract resembles `Decoder`, with `RawFrame`, `Skipped(offset,count)`, `RawNeedInput` and `RawDone`. It has no stream MD5 and reports discarded bytes. It is not the strict file decoder. Its returned sample positions count successfully decoded samples locally; original coded numbers remain in `Frame.number`.

Raw synchronization gives priority to the earliest candidate that has not been rejected. An incomplete candidate remains buffered; apparent complete frames inside its payload are not committed. Scanning resumes only after the earlier candidate is conclusively invalid. EOF truncation and resource-limit errors do not authorize speculative recovery. This keeps decoded PCM independent of input chunking, while confirmed corruption still produces explicit `Skipped` events.

## Metadata

`parse_metadata(bytes) -> (Metadata, Int)` parses native FLAC metadata and returns the first frame offset. `Metadata.info` contains STREAMINFO dimensions, bounds, total sample count (zero means unspecified) and MD5. `blocks` preserves raw payloads including application data and unknown block types. Structured fields expose seek points, comments, cuesheets and pictures. `comments.entries` preserves ordering and duplicates. `cuesheets` exposes all parsed sheets; `cuesheet` is the convenience optional entry.

Picture strings and dimensions are metadata only. MoonFLAC does not fetch picture URIs or execute embedded data. A caller displaying externally linked pictures must obtain permission according to RFC 9639 §8.8/§11. Unknown block payloads are retained, not interpreted as recognized extensions.

`metadata.channel_mask()` interprets `WAVEFORMATEXTENSIBLE_CHANNEL_MASK` and returns `UInt?`: absent is `None`, explicit `0x0` is `Some(0)`. Field names, prefix and hexadecimal digits are case-insensitive; leading zero padding and fewer assigned speakers than channels are accepted. Invalid hex, overflow and conflicting duplicate values produce a positioned error; equivalent duplicates agree. `effective_channel_mask()` resolves absence to standard FLAC ordering for the metadata's channel count. Neither method reorders PCM.

Pass `channel_mask?=metadata.channel_mask()` to `wav_header`. The CLI and browser do so for all export headers. They compare effective layouts before combining Ogg links into one WAV. Raw decoding and the frame API can retain links with different layouts. Browser playback maps known positions into Web Audio's mono/stereo/quad/5.1 model; unnamed extra channels are silent, and zero or unrepresentable layouts disable playback with a notice while retaining WAV export.

## Seeking and cropping

`build_index(data)` validates a native file once and returns `SeekIndex` containing frame locations, total samples and integrity. It retains locations rather than output PCM. `index.locate(sample)` uses binary search and returns the preceding frame or `None` outside the stream.

`decode_indexed_range(data,index,start,end)` decodes only intersecting frames, rechecks their CRCs and copies exact `[start,end)` samples. Reuse the index only with the same immutable input. Its integrity field comes from the full validation performed when building the index, not from recomputing MD5 over the cropped samples. Index structures are not authentication tokens for substituted input.

`decode_range(data,start,end)` is the convenience full-validation route. Native input builds an index. Ogg input is demultiplexed sequentially across all links, with a single aggregate sample coordinate: returned `sample_number` values are global across the chain, while frame rate/depth/channels remain those of each original frame. The result retains the first link's metadata. Aggregate integrity is `Md5Verified` only if every link supplied a matching MD5; otherwise it is `Md5Unavailable`. `crop_frame(frame,start,end)` returns a copied overlapping frame or `None`. Cropped metadata retains source STREAMINFO totals/MD5 rather than pretending they describe the excerpt; use the returned frames' lengths for exported duration.

`decode_seektable_range(data,start,end)` uses native SEEKTABLE points directly, validates the selected location and frame CRCs, and returns `FrameCrcOnly`. It does not compute a global MD5 from an excerpt. Without a usable point it starts at the first frame; a selected malformed point is an error rather than an ignored hint. Choose this API for partial access, and `decode_range` for whole-stream validation.

## PCM and WAV

`frame_pcm(frame)` returns signed interleaved little-endian PCM with each sample sign-extended to `ceil(bits_per_sample/8)` bytes. `frame_pcm(frame,wav=true)` left-aligns valid bits and makes an 8-bit container unsigned.

`wav_header(info,samples,channel_mask?,rf64=false)` returns only the header, allowing large-file output without allocating PCM. Append exactly `samples * channels * ceil(bits/8)` data bytes, then one zero padding byte if that size is odd. The padding is excluded from the data size and included in RIFF/RF64 size. RF64 uses `ds64`; extensible output includes valid bits and a channel mask. `samples` is the number being exported, not necessarily STREAMINFO's source total. Use a writer that supports large files; the header function alone does not remove host memory or filesystem limits.

## Native FLAC encoding

`encode_pcm(samples : Array[Int], config : EncoderConfig) -> Bytes raise FlacError` is the whole-buffer convenience API. Input is signed, unshifted, interleaved scalar PCM: stereo `[L0,R0,L1,R1,...]`, unlike the decoder's planar frames. It copies accepted input and does not mutate the supplied array. The output contains native `fLaC` metadata and audio frames, with finalized total samples, frame-size statistics and MD5. This convenience API retains encoded chunks and assembles one `Bytes`, with a 2,147,483,647-byte representational limit; use `Encoder` for long output.

`PcmFormat` contains `sample_rate : Int`, `channels : Int`, and `bits_per_sample : Int`. Valid encoder dimensions are 1–1,048,575 Hz, 1–8 channels and 4–32 bits. Rate zero additionally requires `non_audio=true`. Values must fit the signed declared bit depth; no clipping, resampling or implicit channel conversion occurs. Empty input is rejected.

Construct configuration with `EncoderConfig::new(format, ...)`. Configuration itself is a value; `Encoder::new` validates it.

| Option | Default | Contract |
|---|---|---|
| `block_size` | `4096` | 16–65535 samples per channel; maximum buffered analysis window |
| `variable_block` | `false` | Fixed blocks otherwise; `true` enables deterministic adaptive splitting |
| `effort` | `5` | Integer 0–8 controlling candidate search, not accepted PCM dimensions |
| `channel_mask` | absent | Optional `UInt`; zero and partial speaker assignments are preserved |
| `metadata` | `[]` | Raw `MetadataBlock` payloads excluding STREAMINFO; copied array structure |
| `non_audio` | `false` | Must be enabled for sample rate zero |
| `max_metadata_bytes` | `67108864` | Aggregate native header limit, including signature, STREAMINFO and all block headers/payloads; minimum 42 |

A minimal whole-buffer call, inside a function that can raise `FlacError`, is:

```moonbit
let format : @flac.PcmFormat = {
  sample_rate: 48000,
  channels: 2,
  bits_per_sample: 16,
}
let config = @flac.EncoderConfig::new(format, effort=5)
let flac_bytes = @flac.encode_pcm([0, 0, 100, -100], config)
```

### Ogg FLAC output

`ogg_from_flac(native, serial?=0x4d464c43, vendor?="MoonFLAC")` converts one complete native FLAC `Bytes` into one Ogg FLAC logical stream. It validates the native stream through `build_index` before repackaging, preserves STREAMINFO and all metadata packets, and synthesizes an empty Vorbis-comment packet only when the native stream has no metadata packets; `vendor` applies only to that synthesized packet. The output starts with the 51-byte Ogg FLAC mapping packet on a BOS page, uses CRC-checked pages with correct continuation flags, and ends with an EOS page. A packet larger than one page is split into full-lacing pages and a terminating page.

`encode_ogg_pcm(samples, config, serial?=..., vendor?=...)` is the whole-buffer convenience path: it calls `encode_pcm` and then `ogg_from_flac`. It retains the native and Ogg buffers and is subject to the same whole-buffer size limits; use the native streaming encoder when input or output cannot be held in memory. The native stream's final STREAMINFO counters/MD5 are preserved. `ogg_from_flac` accepts one native stream, not an Ogg chain or a raw framed stream.

### Incremental encoder and finalization

`Encoder::new(config)` creates a state machine with an initial metadata chunk ready. Call `next()` and consume that `EncodedBytes(Bytes)` before attempting to push samples. Subsequent events are `NeedPcm`, further `EncodedBytes`, and `EncoderDone(EncoderSummary)`.

`push(samples) -> Int raise FlacError` returns an accepted prefix length measured in **scalar channel values**, not bytes, frames, or samples per channel. It can return zero while the initial header or a full PCM window must be drained. Only the accepted prefix is copied and range-checked. Advance the source cursor by exactly that count and retry the unaccepted suffix after processing `next()`. A caller's channel group may be split across pushes; the final stream must contain complete groups. Encoding decisions observe complete configured windows rather than push boundaries, so changing chunk sizes does not change the chosen partitioning.

The producer loop is:

1. Drain `next()`: write each `EncodedBytes` chunk to the output in order.
2. On `NeedPcm`, push a prefix from the available PCM, retaining any unaccepted suffix.
3. Once all source PCM has been accepted, call `finish()` exactly at source EOF.
4. Continue draining until `EncoderDone`; only then is the stream successfully finished.

`finish` rejects empty streams and partial interleaved channel groups. A final complete group may form a frame shorter than 16 samples. Repeated successful `finish` is harmless; `push` after finish is rejected without accepting input. Out-of-range PCM, invalid final groups and failures while encoding are terminal and are returned by subsequent state-machine calls. A rejected extra push after successful finalization does not revoke that completed result. `EncoderDone` remains available on repeated `next()` calls.

`buffered_samples()` and `peak_buffered_samples()` count retained scalar PCM, bounded by `block_size * channels`. They do not count caller input, owned compressed output, metadata, temporary planar copies, predictor candidates or total process RSS. Consume/write chunks promptly rather than collecting an entire recording. Output chunks are owned and are not reused by subsequent encoder calls.

Each encoder also reuses private prediction and residual-planning buffers across channels and frames. Their capacities are bounded by FLAC block dimensions, independently of stream duration; they may retain the largest capacity used until that encoder is released. They are excluded from the scalar PCM counters above. Winning residuals and completed output chunks do not alias reusable planning storage.

`EncoderSummary` exposes `total_samples` (per channel), `frames`, `min_frame_size`, `max_frame_size`, `md5`, and `final_header`. Initially emitted STREAMINFO has zero/unknown total samples, frame-size bounds and MD5. The final header has the same length and metadata placement as the initial one. A seekable writer replaces the initial header with `summary.final_header`; replacing just the first 42 bytes also updates STREAMINFO without moving frames. `encode_pcm` and the CLI perform finalization automatically.

A non-seekable writer may keep the initial unknown fields: the frames and their CRCs remain valid, but a later decoder reports `Md5Unavailable`. `EncoderSummary.md5` is still the encoder's computed source PCM digest and can be stored separately. Merely obtaining that summary does not retroactively embed the digest in already-written bytes.

### Compression policy

All efforts consider constant/verbatim coding and legal wasted-bit reduction. Effort 0 does not search predictors or stereo decorrelation. Higher efforts compare exact serialized subframe bit costs; a larger search is an opportunity for compression, not a promise that a particular mode or ratio will be selected.

| Effort | Fixed predictor orders | Maximum LPC order | Maximum Rice partition order |
|---|---|---|---|
| 0 | none | none | none |
| 1 | 0–4 | none | 1 |
| 2 | 0–4 | 2 | 2 |
| 3 | 0–4 | 4 | 3 |
| 4 | 0–4 | 8 | 4 |
| 5 | 0–4 | 12 | 5 |
| 6 | 0–4 | 16 | 6 |
| 7 | 0–4 | 24 | 7 |
| 8 | 0–4 | 32; adaptive full pool or four legal finalists | All legal orders through 15, with exact pruning |

Actual orders are constrained by block length and valid residual partitions. Residual planning considers Rice, Rice2 and escape coding. Stereo efforts 1–8 compare independent, left-side, right-side and mid-side assignments. LPC model analysis uses `Double` autocorrelation/Levinson–Durbin calculations and quantizes bounded coefficients; predictors use exact integer semantics and residuals are range-checked. Unsuitable predictive candidates are excluded while constant/verbatim remain valid representations. Floating-point analysis affects compression choices, not decoded integer sample values.

The covariance estimate evaluates the symmetric quadratic form over one triangle within a checked numerical domain, retaining the original calculation outside it. Its floating addition order can change model rankings and compressed bytes; it does not change the exact PCM contract. Numerical error and near-threshold decisions are tested against independent exact-rational fixtures, while compression size remains governed by the documented empirical budgets.

The encoder's LPC residual kernel may use integer-valued `Double` arithmetic after validating the sample and coefficient bounds. Products have magnitude at most 2^46 and every partial sum at most 2^51, within the 53-bit exact integer range. The sum is converted to `Int64` before the signed prediction shift; complete residual legality is still checked. This kernel uses unnormalized integer PCM, distinct from the approximate floating-point model analysis. Decoder prediction remains checked `Int64` arithmetic.

Effort 8 uses a speed-first search policy. Actual blocks of at most 256 samples, and blocks whose current best subframe uses partitions of at most eight samples, evaluate the complete LPC model pool in its original order. For other blocks, those divisible by 256 use a guarded covariance estimate derived from the quantized LPC model. If any model has an unstable, nonfinite or sub-unit variance estimate, the complete pool is instead ranked by residual widths at up to 256 evenly spaced positions, including endpoints.

Larger irregular blocks (not divisible by 256) use stratified exact integer residual probes: every sample in the first and last twice-maximum-model-order positions, excluding each model's warm-ups, plus up to 256 evenly spaced interior positions. Integer weights preserve the represented residual count. Scores include estimated order-zero Rice/Rice2/escape costs, warm-ups and coefficient headers. Unobserved residuals and finer partitions are not bounded by this estimate. Both ranked paths evaluate full encoded costs for the first four models whose complete residuals are legal; an overflow outside the probe positions does not consume a finalist slot. LPC ranking is a heuristic, not a lower bound or a guarantee of finding the smallest stream.

Residual partition selection remains exact for every candidate that can improve the current winner. Conservative Rice/escape lower bounds reject a predictor or partition order only when it cannot beat the strict cost budget. Shared width/sum statistics and lazily computed quotient columns avoid repeated complete planning; the earliest optimal Rice parameter lies in a proven small window. Ascending partition order and strict improvement preserve ties. There is no zero-density cutoff. Returned winning plans and residuals do not alias reusable scratch. Efforts 0–7 retain their previous search policies, so effort numbers do not promise monotonically increasing time or decreasing size. Integer PCM, frame CRC and STREAMINFO MD5 remain exact at every effort. The newer performance work remains in progress; empirical size budgets and measurements are documented separately in [PERFORMANCE.md](PERFORMANCE.md), and are not bounds for arbitrary future inputs.

The stage18 supplemental audit found six sine inputs beyond the measured-set 3% size comparison, including a 24-bit mono example of 4743 versus 3411 anchor bytes. C83 and C95 produce identical files on these inputs, and independent PCM/integrity checks pass. The [frozen observations and replay command](../validation/evidence/supplemental-quality-stage18/README-v2.md) document this inherited search-quality limitation separately from the declared acceptance sets.

For effort8 blocks above256 samples, fixed predictors may be evaluated in a sampled ranking order, but none is omitted. Equal costs restore the original lower-order priority within the same wasted-bit choice. An exact partition-order-zero plan can tighten the cost budget before allocating a finer partition grid; all partition orders that could improve the result remain eligible.

With `variable_block=true`, a complete configured window of at least 32 samples is compared by summed absolute adjacent-sample differences in its two halves, across channels. A greater-than-fourfold roughness difference causes the next frame to use the first half; otherwise it uses the full window. Remaining PCM is retained for the next window. The policy is deterministic with respect to input sample order and does not inspect caller chunk sizes. Fixed mode uses the configured size except for the final frame.

### Encoder metadata

STREAMINFO is generated by the encoder; including type 0 in `config.metadata` is an error. Standard metadata blocks are structurally validated with the same parser as decoding, including duplicate restrictions, comments, cuesheets and pictures. Unknown legal types 7–126 are retained unchanged; type 127 and invalid types are rejected. Every payload must fit its 24-bit block length and the aggregate metadata budget.

An explicit configuration mask is merged into VORBIS_COMMENT. Existing vendor text and tags are retained; no existing comment creates one with vendor `MoonFLAC`. Equivalent case-insensitive/padded mask values preserve their original raw comment. A conflicting mask is an error. Without a configuration mask, a supplied comment's layout is retained and validated. Zero and partial assignments remain distinct from absence.

A supplied SEEKTABLE is not regenerated for a different encoding. Each non-placeholder point must match an actual emitted frame's first sample, byte offset relative to the first audio frame, and block size. Mismatched points fail during encoding; outstanding non-placeholder points fail at finish. Placeholder entries remain legal. Do not blindly copy an old file's seek table while changing compression settings. This validation can fail after earlier output chunks have already been written, so callers must treat failed output as incomplete.

## Integer PCM file input

`PcmInput::wav()` reads integer PCM RIFF WAVE and RF64 incrementally. It understands WAVE_FORMAT_EXTENSIBLE valid bits and channel masks, RF64 `ds64` sizes, chunk padding and unknown chunks; floating-point formats are rejected. Unknown chunks are skipped rather than mapped to FLAC metadata. Its RF64 size-table resource limit is 65,536 entries.

`PcmInput::raw(format)` reads signed, little-endian, unshifted PCM, sign-extended in `ceil(bits/8)` bytes. WAV uses its own unsigned 8-bit and left-aligned valid-bit conventions; the reader converts both inputs to the encoder's signed unshifted integers. Raw input does not infer sample rate, channels or bit depth from file names or byte contents.

Use `push(bytes)`, `next()`, and `finish()` with the same accepted-prefix discipline as decoding. `PcmFormatReady(PcmFormat, UInt?)` announces format and optional layout; `PcmSamples(Array[Int])` returns owned interleaved complete channel groups; `PcmNeedInput` requests more bytes; `PcmInputDone` confirms end. `finish` declares EOF and `next` detects truncated containers or incomplete PCM. Staging capacity is 64 KiB; pushing while full raises `Limit`, so drain first and retry the unaccepted suffix. `buffered_bytes()` measures staging only. Rate zero is representable in raw format, while the encoder requires explicit non-audio permission.

The native CLI connects this reader to `Encoder`, writes emitted chunks incrementally, and rewrites the finalized header. See the READMEs for its exact switches. These library encoding interfaces run on native, JS and wasm-gc; no Ogg encoder or browser editing interface is provided.

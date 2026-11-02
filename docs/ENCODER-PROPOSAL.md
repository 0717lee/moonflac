# Pure MoonBit encoder extension — implementation and acceptance

Status: implemented and locally accepted, 2026-09-29 (`encoder-authorization-20260929`). The user approved the full native FLAC encoder direction. This document remains the scope and acceptance ledger; all six gates have now executed successfully, including the complete valid corpus. Work remains local without commit/amend, push, publication or deployment.

## Implementation ledger

| Work | State | Acceptance evidence |
|---|---|---|
| Bitstream writer, predictors, Rice optimization and stereo selection | verified | 137 representations independently decoded/analyzed; natural candidate/cost/stereo tests |
| Whole-buffer and bounded streaming encoder, metadata and integrity | verified | scalar split/backpressure/ownership/EOF tests; unpatched streams independently decoded; supplied seek points validated; 5/60/300-second memory measurements |
| WAV/RF64/raw CLI encode | verified | all 29 valid bit depths in RIFF and RF64 independently decoded; masks, raw sign extension, errors and 64-bit chunk handling |
| All PCM formats and real recordings, three backends | verified | 328 native cases/excerpts; 327 FFmpeg audio comparisons; 276 independent streams per backend (828 total), including all 29 depths × 8 channels; all 75 valid corpus files fully encoded as 84 homogeneous streams and independently checked |
| Compression/performance against libFLAC -0/-5/-8 | measured | 18 independently checked encodes on identical sources and block sizes; full size/time/memory report |
| Public API, documentation and final integration | verified locally | 98/98 at feature acceptance, 99/99 per backend after search hardening; check/build/fmt/info and compiled encoder example; existing decoder suite and CLI contracts retained |

## Delivered scope

A pure MoonBit encoder shares the existing PCM, metadata, integrity and error contracts and runs on native, JavaScript and wasm-gc. It writes native FLAC for signed unshifted 4–32-bit PCM, 1–8 channels and the audio sample-rate range 1–1,048,575 Hz. Non-audio rate zero is an explicit mode. Default and custom channel masks, including zero/partial assignments, survive serialization and are verified separately from the reference decoder's explicit-zero WAV substitution.

The encoder provides whole-buffer `encode_pcm` and bounded incremental `Encoder` APIs, plus a native CLI `encode` command taking integer PCM WAV/RF64 or explicitly described raw PCM. Configuration names sample format, block policy, effort level and metadata limits. The API accepts a prefix of interleaved scalar PCM, emits owned byte chunks and finishes explicitly. Empty streams, incomplete final interchannel groups, invalid dimensions, out-of-range values and writes after finish are rejected rather than clipped or silently converted. Valid arbitrary scalar cuts can span interchannel groups before finish. See [API contracts](API.md) and the [compiled encoder example](../examples/encode/main.mbt).

Ogg packetization is a separable follow-up to the native encoder. AudioWorklet playback, general metadata editing, cover editing and CUESHEET splitting remain separate proposals; they are not necessary consequences of adding an encoder.

## Coding and selection

| Component | Implemented behavior | Observable acceptance |
|---|---|---|
| Blocking | Fixed and variable-block streams, valid 16–65,535-sample blocks and short final blocks; coded frame/sample numbers | Independently decoded lengths and boundary sample positions match exactly; header numbering and STREAMINFO bounds are consistent |
| Subframes | Constant, verbatim, fixed predictors 0–4, LPC 1–32 and wasted bits | Crafted fixtures exercise every implemented order and representation, with syntax inspected independently |
| Predictor choice | Evaluate valid candidate bit cost, including warmups, coefficients, residual partitions and headers; deterministic tie-breaking | Selected candidate's measured bit count matches the estimate; a constant or simple polynomial signal does not become larger than its verbatim candidate |
| LPC analysis | Normalized Welch-window autocorrelation and Levinson-Durbin; quantize to legal precision/shift; reconstruct using checked Int64 arithmetic | Floating-point estimation may affect compression, never PCM correctness; unusable models are excluded from legal candidate selection |
| Rice optimization | Rice/Rice2 parameter search, valid partition orders 0–15, escape widths 0–31; checked cost arithmetic | Boundary residuals, zero-width escape and partition/predictor constraints validated by libFLAC and the existing independent fixtures |
| Stereo decorrelation | Evaluate independent, left-side, side-right and mid-side, retaining 33-bit side values | Full-scale 32-bit stereo extremes roundtrip exactly; chosen cost includes both subframes |
| Residual domain | Enforce RFC residual bounds before emitting a predictor representation | Inputs whose residuals cannot be represented use a legal alternate subframe, such as verbatim; no truncated integers or overflowing unary lengths |
| Integrity | CRC8, CRC16 and incremental source-PCM MD5 | Independent libFLAC verification succeeds, and independent PCM digest equals the input digest |
| Metadata and finish | Accurate known values; unknown fields follow the format's unknown-value rules | Seekable output patches final STREAMINFO; non-seekable output leaves unknown total/frame-size/MD5 fields as zero where required and returns the computed final statistics separately |

Effort levels bound the number of predictor and partition candidates, not the accepted PCM domain. Compression decisions do not call libFLAC, FFmpeg, a browser codec or FFI. External codecs remain validation tools only. Variable blocking uses a complete configured window and splits it in half for strong changes in roughness, independent of input chunk boundaries; it is not a claim of globally optimal block placement.

## Independent acceptance gates

1. **Exact sample roundtrip:** encode deterministic source PCM for all 29 bit depths × 8 channel counts, extreme signed values, silence, ramps, impulses, alternating extrema and seeded noise. Decode MoonBit output with libFLAC, comparing signed integer samples. Use FFmpeg as a second independent decoder where its supported formats permit exact comparison. Never use only MoonFLAC decoding as the oracle.
2. **Real recordings and representation coverage:** independently decode the existing valid corpus to PCM, encode it, then independently decode the new output. Changing-format sources become explicitly separate encoder streams. Inspect output frames to prove predictor/Rice/decorrelation coverage instead of inferring it from test totals.
3. **Streaming invariants:** compare whole-input and arbitrary PCM chunking; test every short boundary, finish, backpressure, output ownership and non-seekable headers. Decode every produced stream independently. Measure retained buffers and OS memory over increasing stream lengths, including the maximum block size.
4. **Three backends:** check, format, build and run tests on native/JS/wasm-gc. Require identical decoded PCM and documented deterministic configuration behavior; do not require byte-for-byte equality with libFLAC's distinct optimization choices.
5. **Metadata and CLI interoperability:** native FLAC accepted by official `flac -t`; WAV/RF64 and raw input roundtrips preserve valid bit depth, channel order/mask and sample count. Exercise zero/partial masks explicitly because reference tools can differ in metadata handling even when their PCM is correct.
6. **Compression and speed evidence:** publish per-input encoded bytes, elapsed time, effort settings, CPU/toolchain and peak memory beside libFLAC `-0`, `-5` and `-8`. Record ratios rather than promise an unmeasured speed or compression advantage. Verify that format overhead and the selected candidate explain output size.

## Executed evidence and practical limits

[Independent encoder reports](../validation/encoder/README.md) provide exact commands, source descriptions and machine-readable results in `validation/evidence/encoder-*.json`. Core representation tests exercise the actual writer, and their emitted files are independently decoded and analyzed; natural selection tests separately verify the selector. The 328-case matrix includes ten 8192-frame excerpts and thirteen homogeneous excerpts from changing-format recordings. A separate complete-corpus run then processed all 64 subset and 11 uncommon files, producing 84 homogeneous streams: **50,363,649 sample frames / 313,149,688 source PCM bytes** compared exactly with libFLAC, and every output passed official `flac -t`. This full run includes the raw multicast cases and preserves explicit source channel masks. See `encoder-full-corpus.json`; excerpt and full-recording coverage are reported separately.

The long-memory runs cover 5/60/300 seconds at effort 0, 5/30 seconds with predictors at effort 5, and a 65,535-sample block run. At effort 5, peak working set was 9,216,000 / 9,519,104 bytes over the sixfold duration increase; the maximum-block case used 13,762,560 bytes. See [measurement details](PERFORMANCE-EVIDENCE.md). The [compression benchmark](../validation/evidence/encoder-benchmark.json) shows that higher-effort MoonBit search is slower than libFLAC; compression ratios depend on the signal and no overall performance advantage is claimed.

The CLI reader bounds input staging to 64 KiB and RF64 size-table entries to 65,536. WAV integer containers are 8/16/24/32 bits, with 4–32 valid bits carried by extensible WAV; float/compressed WAV input is explicitly unsupported. The encoder retains at most one configured block of input PCM (plus per-block candidate working storage and bounded metadata); whole-buffer convenience output and caller-retained chunks intentionally accumulate. Non-seekable streams leave unknown STREAMINFO totals/bounds/MD5 as zero and return finalized statistics separately. Seekable CLI output patches the same-length header. Supplied SEEKTABLE points must match actual encoded frame boundaries/offsets or encoding fails explicitly.

CI configuration now includes the independent encoder CLI suite. All listed local checks ran; remote CI and publication did not. Ogg encoding, AudioWorklet playback, and general metadata editing remain the separate directions specified above.

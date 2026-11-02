# MoonFLAC

[简体中文](README.zh-CN.md) · [API](docs/API.md) · [Acceptance matrix](docs/ACCEPTANCE.md) · [Competition walkthrough](docs/CONTEST.md) · [2026 Hackathon note](HACKATHON.md) · [CI](https://github.com/0717lee/moonflac/actions/workflows/ci.yml)

> **2026 MoonBit Hackathon:** one-page project description and the current submission boundary are in [HACKATHON.md](HACKATHON.md). The public repository is the submission record; the codec itself remains a reusable MoonBit library.

MoonFLAC is a pure MoonBit lossless FLAC codec for native, JavaScript and WebAssembly GC, with native FLAC encoding, Ogg FLAC muxing and native/Ogg FLAC decoding. The decoder, bit reader, predictors, channel reconstruction, checksums, metadata parser, Ogg demultiplexer and Ogg muxer are MoonBit. No libFLAC, FFmpeg, FFI or browser audio decoder is used by the codec library. Independent libFLAC is used by the external validation scripts. Encoding also runs entirely in MoonBit; its independent acceptance is tracked separately in [the encoder ledger](docs/ENCODER-PROPOSAL.md).

## Supported format

Local delivery status (2026-10-01): stable C95 passed current Windows/WSL,
long-stream/RF64, sustained-stress and browser checks. Independent functional
final review passed. **Outperforming libFLAC remains an unmet requirement**; see the
[current acceptance status and limits](docs/ACCEPTANCE.md#current-local-delivery-2026-10-01).

| Area | Coverage |
|---|---|
| PCM | 4–32 valid bits, 1–8 channels, 1–1,048,575 Hz; zero-rate non-audio streams can be decoded but cannot be played/exported as ordinary audio WAV |
| Frames | Fixed/variable blocks, 16–65,535 samples with shorter final blocks; extended frame/sample numbers; CRC8 and CRC16 |
| Subframes | Constant, verbatim, fixed predictors 0–4, LPC orders 1–32, Rice/Rice2, escaped partitions, wasted bits |
| Arithmetic | Int64 decoder prediction and stereo reconstruction, including 33-bit side channels, with reconstructed range checks; encoder kernels preserve exact integer semantics, including bounded exact-Double LPC evaluation |
| Metadata | STREAMINFO, PADDING, APPLICATION, SEEKTABLE, VORBIS_COMMENT, CUESHEET, PICTURE; unknown types 7–126 retained as raw blocks; type 127 rejected |
| Integrity | Frame CRCs checked before output; available STREAMINFO MD5 checked at stream/link completion; absent MD5 reported explicitly |
| Containers | Native FLAC and Ogg FLAC decoding, including chained logical links via `decode_chained` or streaming events; Ogg FLAC muxing from native frames |
| Access | Whole-file decode, incremental push/pull decoding, frame index, exact half-open sample cropping |
| Output | Signed interleaved little-endian raw PCM; WAV, WAVE_FORMAT_EXTENSIBLE and RF64 |
| Encoding | Native FLAC from 4–32-bit signed PCM, 1–8 channels; whole-buffer and bounded streaming APIs; fixed or adaptive variable blocks; effort 0–8; Ogg FLAC muxing from native frames and whole-buffer PCM-to-Ogg convenience |

The implementation follows [RFC 9639](https://www.rfc-editor.org/rfc/rfc9639.html), including verified errata [8256](https://www.rfc-editor.org/errata/eid8256) and [8810](https://www.rfc-editor.org/errata/eid8810). See the acceptance matrix for implementation and evidence links. Reserved coding values produce errors. Valid changes to frame audio properties remain visible in frame metadata; a single WAV output requires a uniform format.

## Build and test

Install the [MoonBit toolchain](https://www.moonbitlang.com/download/), a native C toolchain, Node.js and Python 3. Local development used `moon 0.1.20260827`. Run from this directory:

For the exact compiler used here, the official Unix installer accepts a version argument: `bash install-moonbit.sh '0.10.16+b1a0e846e'` after downloading `https://cli.moonbitlang.com/install/unix.sh`. CI pins that compiler/core release; the `moon` build-tool version has a separate numbering scheme.

```sh
moon update
moon fmt --check
moon check --target native
moon test --target native
moon build --target native
moon check --target js
moon test --target js
moon build --target js
moon check --target wasm-gc
moon test --target wasm-gc
moon build --target wasm-gc
moon run examples/stream --target native
moon run examples/ogg --target native
```

The root library has no platform FFI. The CLI is native; the browser bridge targets JavaScript and wasm-gc. Target-specific packages are excluded from incompatible builds. CI configuration is provided in `.github/workflows/ci.yml`; a local passing run is not a claim that remote CI has run.

## CLI

```sh
moon run cmd/moonflac --target native -- info recording.flac --json
moon run cmd/moonflac --target native -- verify recording.flac
moon run cmd/moonflac --target native -- decode recording.flac output.wav
moon run cmd/moonflac --target native -- decode recording.flac output.pcm --raw
moon run cmd/moonflac --target native -- decode recording.flac excerpt.wav --start 48000 --end 96000
moon run cmd/moonflac --target native -- decode recording.flac output.wav --rf64
moon run cmd/moonflac --target native -- encode recording.wav output.flac
moon run cmd/moonflac --target native -- encode recording.rf64 output.flac --effort 8 --variable-block
moon run cmd/moonflac --target native -- encode input.pcm output.flac --raw --sample-rate 48000 --channels 6 --bits 24 --channel-mask 0x060f
moon run cmd/moonflac --target native -- ogg output.flac output.oga
```

Sample intervals are zero-based `[start, end)`, measured per channel. Raw samples are signed, unshifted and sign-extended to `ceil(bits/8)` bytes. WAV stores valid bits left-aligned in its byte container and uses unsigned 8-bit PCM where applicable. Multichannel/high-depth output uses extensible format with its channel mask. RF64 is selected for large sizes or explicitly requested.

Exit codes: **0** success, **2** usage/arguments, **3** invalid input/codec failure, **4** file I/O failure. Diagnostics include the available stream position. The CLI reads 64 KiB chunks and consumes one frame at a time. `info` and `verify` validate the complete input. Export output must be seekable; an existing output is overwritten, and a failed export can leave a partial file.

All commands accept `--max-buffer BYTES` (default 33,554,432; accepted range 4–2,147,483,647). For unusually large valid corpus inputs, use e.g. `verify large.flac --max-buffer 134217728`; hitting the default budget is a resource error, not a declaration that the coding mode is unsupported.

`encode` reads integer PCM RIFF WAVE/RF64 by default, including extensible valid-bit depths and channel masks. Raw input requires all three format switches and uses the signed little-endian representation above. Floating-point WAV and other raw byte orders are not accepted. `--block-size` defaults to 4096 (16–65535), `--effort` to 5 (0–8); `--variable-block` enables adaptive splitting. A raw sample rate of zero requires `--non-audio`. `--channel-mask HEX` overrides the input WAV mask; otherwise that mask is preserved. Unrelated WAV chunks are skipped rather than converted to FLAC tags. The CLI patches final STREAMINFO on its seekable output; `--max-buffer` sets its encoder metadata budget, while PCM input staging remains 64 KiB.

## Ogg FLAC output

`ogg_from_flac(native)` converts one complete native FLAC stream into one Ogg FLAC logical stream. It validates the native frame index first, preserves STREAMINFO and metadata, adds an empty Vorbis-comment packet when the source has no metadata packets, and writes CRC-checked Ogg pages with continuation and granule handling. `encode_ogg_pcm(samples, config)` is the whole-buffer PCM-to-Ogg convenience path; the native streaming encoder remains separately bounded.

```sh
moonflac ogg recording.flac recording.oga
moonflac info recording.oga
```

The `ogg` command stages its native input in memory, so the CLI is intended for ordinary files rather than multi-gigabyte recordings. Use the library's native encoder plus a streaming consumer when the input itself cannot be held in memory. `--serial HEX` overrides the default logical-stream serial number `0x4d464c43`; `--vendor NAME` sets the vendor string used only when the source has no Vorbis comment. [`examples/ogg`](examples/ogg/main.mbt) is a three-target PCM-to-Ogg round trip.

## Library and streaming

Import `0717lee/moonflac` under an alias such as `@flac`. `decode(bytes)` returns owned frames for one stream; `decode_chained(bytes)` returns each Ogg link separately. For long input, use `Decoder::new()`, `push`, `next`, and `finish`, consuming each `AudioFrame` before reading more input. `push` returns the accepted prefix length; always retry the unaccepted suffix. `NeedInput` means more input is needed; it is not EOF. After `finish`, continue until `Done` or an error.

The [compiled streaming example](examples/stream/main.mbt) demonstrates the entire event loop, including link boundaries. [API documentation](docs/API.md) specifies ownership, errors, integrity timing, resource accounting and seeking.

## Native FLAC encoding

`encode_pcm(samples, EncoderConfig::new(format))` returns a finalized native FLAC file. `PcmFormat` specifies sample rate, channels and valid bit depth; input is an interleaved `Array[Int]` of signed, unshifted values. Samples are range-checked without clipping. `EncoderConfig` also accepts block size, variable blocking, effort, an optional channel mask, raw metadata blocks, explicit non-audio mode and a metadata budget (64 MiB by default).

For long streams, drive `Encoder::new`, `next`, `push`, and `finish`. Drain the initial `EncodedBytes` header before pushing PCM. `push` returns the number of accepted **scalar channel values**, which can be less than the supplied array; retry the remainder after draining. Retained PCM is bounded by `block_size * channels`. `finish` rejects empty input and incomplete channel groups; keep draining to `EncoderDone`. Its summary contains the PCM MD5 and a same-length `final_header`. Seekable writers replace the initial header; non-seekable writers can leave valid zero/unknown STREAMINFO totals and MD5. `encode_pcm` performs this replacement automatically.

Effort 0 uses constant/verbatim representations; higher levels search fixed prediction, LPC, Rice/Rice2/escape partitions and stereo assignments. Floating-point LPC analysis proposes models, while integer prediction and residual reconstruction determine lossless correctness. See [encoder contracts and effort limits](docs/API.md#native-flac-encoding) for exact behavior. The encoder's implementation and acceptance ledger is distinct from the decoder baseline evidence below.

The current effort-8 speed-first policy preserves exact residual partition costs using conservative lower bounds. Blocks of at most 256 samples and fine-partition cases evaluate the complete LPC pool. Larger irregular blocks use stratified integer residual probes ranked by Rice/Rice2/escape costs; larger regular blocks use guarded covariance ranking, falling back to sampled residual widths when that estimate is unsuitable. Ranked searches evaluate four fully legal finalists, with illegal full residuals replaced by later candidates. These rankings are heuristics: size increases depend on the input and are not universally limited by measured-set budgets. Every integer sample remains lossless. Six supplemental sine cases include a file about 39% larger than the fixed anchor; [frozen repros](validation/evidence/supplemental-quality-stage18/README-v2.md) preserve this inherited limitation. The goal of outperforming libFLAC remains open.


Recorded encoder feature acceptance passed **103/103 project tests per backend**, **328** independent native cases, **828** independently decoded cross-backend streams, **137** writer representations, and all **75** valid corpus files fully re-encoded as **84** homogeneous streams. The full-recording run compared **50,363,649 sample frames** exactly. See the [encoder ledger](docs/ENCODER-PROPOSAL.md), [independent evidence](validation/encoder/README.md), and [compiled streaming example](examples/encode/main.mbt). Earlier [search hardening measurements](docs/PERFORMANCE.md) include byte-identical output and actual Windows/WSL validation; current numerical analysis may change compressed bytes while preserving PCM. Sustained stress is tracked separately in the [acceptance ledger](docs/ACCEPTANCE.md). High-effort search remains slower than libFLAC.

## Browser playground

```sh
node playground/build.mjs
node playground/serve.mjs
```

Open [the local listening room](http://127.0.0.1:8080). Select/drop a FLAC, choose JavaScript or WebAssembly GC, inspect metadata and a waveform, play/pause/seek, and export WAV. The selected MoonBit artifact runs in a Worker; Web Audio receives decoded PCM. Switching backends re-decodes the file. Decode/bridge timings and backend load/compile timings are separate; unavailable wasm-gc produces an explicit error. Playback uses Float32 and may resample; integer WAV export preserves source sample precision. The preview has explicit input/output limits and can be cancelled by selecting a new file. See [playground details](playground/README.md).

## Independent verification

Install libFLAC (`flac` and `libflac-dev` on Ubuntu; `scripts/prepare-validation.ps1` on Windows), then:

```sh
python scripts/validate.py generate
moon build --target native
python scripts/validate.py compare --cli _build/native/debug/build/cmd/moonflac/moonflac.exe --corpus generated
python scripts/fetch-corpus.py
python scripts/validate.py compare --cli _build/native/debug/build/cmd/moonflac/moonflac.exe --corpus subset --max-buffer 134217728 --timeout 180
python scripts/validate.py frames --cli _build/native/debug/build/validation/runner/runner.exe --corpus uncommon
```

Use the executable path printed by `moon build` if the platform/toolchain differs (Unix may omit `.exe`). The fetcher uses GitHub CLI and saves the fetched revision and Git blob hashes. Public [FLAC test files](https://github.com/ietf-wg-cellar/flac-test-files) must be classified using their group READMEs: `faulty` files are rejection tests, while some `uncommon` inputs are raw framed streams or change properties and need the frame-aware runner instead of a uniform-format CLI comparison. Generated inputs, PCM expectations and source parameters are recorded under `validation/cache/generated`; measured results are under `validation/results`. [Performance notes](docs/PERFORMANCE.md) describe measurement scope.

Recorded decoder baseline acceptance (before the encoder extension): **245/245** generated PCM comparisons, **64/64** subset comparisons, **11/11** uncommon per-frame comparisons, and **11/11** faulty-input rejections. All three targets passed check/build and **67/67** root tests; the independent golden package passed **14/14** on each target. [Preserved evidence](validation/evidence/README.md) records source revision, hashes and exact commands. Real Chromium interaction verified both browser backends and byte-identical exported WAV. No remote CI run is claimed.

Current Ogg-output increment (2026-11-02): native, JavaScript and wasm-gc each pass **196/196** project tests, including three new Ogg mux tests (round-trip metadata/PCM, frame continuation across pages, invalid input). The CLI contract test also muxes a native file, verifies the Ogg output with independent libFLAC, and compares decoded PCM byte-for-byte. Manual libFLAC checks covered 16/24/32-bit and 2/6/8-channel files; 4-bit Ogg output passed `flac -t` but libFLAC's raw-output mode does not accept 4-bit samples for a byte comparison.

## Boundaries and license

This is a FLAC codec and integration toolkit. The encoder writes native FLAC and can mux completed native frames into Ogg FLAC; Ogg output is one logical stream per call, and the CLI stages its input in memory. MP4/Matroska demuxing, unrelated codecs, browser audio editing/AudioWorklet playback and operating-system playback backends are outside its scope. These exclusions do not remove FLAC frame coding features. Container-specific random access for Ogg uses sequential demultiplexing; native input supports reusable byte indexes. Resource limits are explicit errors and can be raised for unusually large valid data.

Apache-2.0. See [LICENSE](LICENSE) and [third-party provenance](THIRD_PARTY.md). This checkout is the public submission; the repository and CI record are linked from [HACKATHON.md](HACKATHON.md).

The subsequent effort-8 follow-up reduces fixed-set median totals by **51.6% core / 51.8% CLI**, with byte-identical output and 103/103 tests on each backend on Windows and WSL2. These are bounded local results; independent review passed, silence/maximum-block cases show no resolved benefit, and high effort remains slower than libFLAC. See [the paired results and reference limitations](docs/PERFORMANCE.md#high-effort-optimization-follow-up-independently-passed).

The revision 7 speed-first follow-up measures **4.83× further CLI speedup** (49.10 → 10.17 s), **3.60× core speedup**, and **8.71× libFLAC `-8` CLI elapsed time** on the unchanged twelve-case set. Complete-file size rises 0.0159%; all declared quality sets satisfy the +1% aggregate / +3% single-case budgets relative to the previous MoonFLAC version. Windows/WSL tests pass **121/121 per backend**. These are empirical bounds; libFLAC remains faster. [Full measurements, preserved failures and limitations](docs/SPEED-FIRST-EVIDENCE.md) and the [acceptance ledger](docs/ACCEPTANCE.md) distinguish current and historical results. Final independent review passed with all confirmed findings closed.


The active `faster-than-libflac-20260929` task has a stricter goal than revision7. Current C95 passes **194/194 tests per backend**, 220 independent cases and 16 long CLI/core outputs, with fixed quality budgets for the declared sets. C95 independent review passed. Direct C95/C83 measurements reduce aggregate core time by 1.55% and CLI time by 2.40%, retaining all regressions. Retained historical single-round normal-libFLAC-8 diagnostic ratios are **1.71 core / 1.45 CLI**, so the goal is still open. Current-artifact Windows/WSL and long-stream/stress gates passed during this closeout; macOS and independent Linux hardware were not tested. Consolidated independent functional final review passed; performance wins and final repeated blocks remain unmet. See [the active contract](docs/ACCEPTANCE.md) and [current measurements](docs/PERFORMANCE.md#selected-triangular-variance-implementation-c95); historical C4 evidence remains preserved in `faster-than-libflac-stage1.json`.

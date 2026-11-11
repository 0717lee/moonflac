# MoonFLAC

[简体中文](README.zh-CN.md) · [API](docs/API.md) · [Acceptance](docs/ACCEPTANCE.md) · [Spec matrix](docs/SPEC-MATRIX.md) · [Hackathon note](HACKATHON.md) · [CI](https://github.com/0717lee/moonflac/actions/workflows/ci.yml)

MoonFLAC is a pure MoonBit lossless FLAC codec for native, JavaScript and WebAssembly GC. It covers decoding, native FLAC encoding, Ogg FLAC muxing, streaming, exact sample cropping, a CLI and a browser playground. The codec library uses no libFLAC, FFmpeg, FFI or browser audio decoder; libFLAC is only an external validation oracle.

## Features

| Area | Coverage |
|---|---|
| PCM | 4–32 valid bits, 1–8 channels, 1–1,048,575 Hz |
| Frames | Fixed/variable blocks, 16–65,535 samples, CRC8 and CRC16 |
| Subframes | Constant, verbatim, fixed 0–4, LPC 1–32, Rice/Rice2, escape, wasted bits |
| Arithmetic | Int64 prediction and stereo reconstruction, including 33-bit side channels |
| Metadata | STREAMINFO, PADDING, APPLICATION, SEEKTABLE, VORBIS_COMMENT, CUESHEET, PICTURE; unknown 7–126 retained |
| Integrity | Frame CRCs before output; available STREAMINFO MD5 checked at stream/link end |
| Containers | Native/Ogg FLAC decode with chained links; Ogg FLAC muxing from native frames |
| Access | Whole-file and incremental decode, frame index, half-open sample cropping |
| Output | Raw PCM, WAV, WAVE_FORMAT_EXTENSIBLE and RF64 |
| Encoding | Native FLAC from 4–32-bit PCM; whole-buffer and bounded streaming APIs; effort 0–8; Ogg output |

The implementation follows [RFC 9639](https://www.rfc-editor.org/rfc/rfc9639.html), including verified errata [8256](https://www.rfc-editor.org/errata/eid8256) and [8810](https://www.rfc-editor.org/errata/eid8810).

## Build and test

Install the [MoonBit toolchain](https://www.moonbitlang.com/download/), a native C toolchain, Node.js and Python 3. CI pins compiler `0.10.20+65efd5b93`.

Install the published library:

```sh
moon add 0717lee/moonflac@0.2.1
```

Mooncakes: <https://mooncakes.io/docs/0717lee/moonflac>

```sh
moon update
moon fmt --check
for target in native js wasm-gc; do
  moon check --target "$target"
  moon test --target "$target"
  moon build --target "$target"
  moon run examples/stream --target "$target"
  moon run examples/encode --target "$target"
  moon run examples/ogg --target "$target"
done
```

The root library has no platform FFI. The CLI is native; the browser bridge targets JavaScript and wasm-gc.

## CLI

```sh
moon run cmd/moonflac --target native -- info recording.flac --json
moon run cmd/moonflac --target native -- verify recording.flac
moon run cmd/moonflac --target native -- decode recording.flac output.wav
moon run cmd/moonflac --target native -- decode recording.flac excerpt.wav --start 48000 --end 96000
moon run cmd/moonflac --target native -- encode recording.wav output.flac
moon run cmd/moonflac --target native -- encode input.pcm output.flac --raw --sample-rate 48000 --channels 6 --bits 24 --channel-mask 0x060f
moon run cmd/moonflac --target native -- ogg output.flac output.oga
```

Sample ranges are zero-based `[start, end)`, per channel. Exit codes: `0` success, `2` usage, `3` invalid input/resource limit, `4` file I/O. All commands accept `--max-buffer BYTES` (default 32 MiB).

`encode` reads integer WAV/RF64. Raw input requires sample rate, channels and bit depth. `--block-size` defaults to 4096, `--effort` to 5, `--variable-block` enables adaptive blocking.

## Ogg FLAC output

`ogg_from_flac(native)` validates one complete native FLAC stream and writes one Ogg FLAC logical stream, preserving STREAMINFO and metadata. `encode_ogg_pcm(samples, config)` is the whole-buffer PCM-to-Ogg path.

```sh
moonflac ogg recording.flac recording.oga
moonflac info recording.oga
```

`--serial HEX` sets the logical-stream serial; `--vendor NAME` sets the vendor only when the source has no Vorbis comment. The CLI stages its input in memory; the native `Encoder` remains the bounded streaming path. [`examples/ogg`](examples/ogg/main.mbt) is a three-target round trip.

## Library and streaming

Import `0717lee/moonflac` as `@flac`. `decode(bytes)` returns one stream; `decode_chained(bytes)` returns Ogg links separately. For long input, use `Decoder::new()`, `push`, `next` and `finish`; consume each frame before reading more data. [API documentation](docs/API.md) defines ownership, errors, integrity timing and resource limits.

`encode_pcm(samples, EncoderConfig::new(format))` returns finalized native FLAC. `Encoder` provides bounded streaming with retained PCM capped at `block_size * channels`. `OggDemux` provides incremental Ogg input.

## Browser playground

```sh
node playground/build.mjs
node playground/serve.mjs
```

Open `http://127.0.0.1:8080`, choose JavaScript or WebAssembly GC, inspect metadata/waveform, play/pause/seek and export WAV. The MoonBit artifact runs in a Worker; integer WAV export preserves source precision. See [playground details](playground/README.md).

## Verification

- Native, JavaScript and wasm-gc: **197/197** project tests each.
- CI: three-target check/test/build, CLI contract tests, libFLAC PCM comparison and browser build.
- Clean clone: three targets 197/197, CLI contract test passes.
- Ogg output: libFLAC `-t` accepted; 16/24/32-bit, 2/6/8-channel PCM matches byte-for-byte.
- Historical decoder/encoder/long-stream evidence remains summarized in [docs/ACCEPTANCE.md](docs/ACCEPTANCE.md).

libFLAC is the independent oracle; MoonFLAC does not use its own decoder as reference. The performance goal of beating libFLAC is not met.

## Boundaries

The `ogg` CLI stages its input in memory. A bounded Ogg streaming writer, MP4/Matroska mappings, OS player backends and AudioWorklet playback are out of scope. Resource limits are explicit errors and can be raised for unusually large valid inputs.

Apache-2.0. See [LICENSE](LICENSE) and [THIRD_PARTY.md](THIRD_PARTY.md). This checkout is the public submission; see [HACKATHON.md](HACKATHON.md).

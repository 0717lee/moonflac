# MoonFLAC acceptance summary

## Current delivery (2026-11-02)

MoonFLAC implements RFC 9639 decoding, native FLAC encoding, Ogg FLAC muxing, native/Ogg input, streaming APIs, sample seeking, a native CLI and a browser playground. The codec library has no libFLAC/FFmpeg/FFI dependency; libFLAC is an external validation oracle.

| Gate | Result |
|---|---|
| Native / JavaScript / wasm-gc | 197/197 project tests each |
| Clean clone | 197/197 on all three targets; CLI contract test passes |
| CI | three-target check/test/build, examples, CLI contracts, libFLAC PCM comparison, browser build |
| Ogg output | libFLAC `-t` accepted; 16/24/32-bit, 2/6/8-channel PCM matched byte-for-byte |
| Browser | JavaScript and wasm-gc artifacts run in a Worker; integer WAV export preserves source precision |
| Release | `v0.2.1` |
| Mooncakes | [`0717lee/moonflac@0.2.1`](https://mooncakes.io/docs/0717lee/moonflac) |

## Historical baseline

Before the Ogg increment, the recorded decoder baseline passed 245/245 generated PCM comparisons, 64/64 public subset comparisons, 11/11 uncommon per-frame comparisons and 11/11 faulty-input rejections. The encoder baseline passed 328 independent native cases, 828 cross-backend streams, 137 writer representations and all 75 valid public files (50,363,649 frames compared exactly). Long-stream tests processed a 5,529,600,104-byte RF64 case.

These results are retained as engineering history, not rerun as part of every commit. The public repository keeps the current Ogg receipt; large historical raw artifacts remain local and are not bundled.

## Limits

- The performance goal of outperforming libFLAC is **not met**.
- `moonflac ogg` stages its input in memory; the native `Encoder` is the bounded streaming path.
- A bounded Ogg streaming writer, MP4/Matroska mappings, system player backends and AudioWorklet playback are out of scope.
- macOS and independent Linux hardware were not tested; Windows, WSL2 and GitHub Actions Linux are covered.

## Reproduction

```sh
moon fmt --check
for target in native js wasm-gc; do
  moon check --target "$target"
  moon test --target "$target"
  moon build --target "$target"
done

python scripts/validate.py generate
python scripts/validate.py compare --cli _build/native/debug/build/cmd/moonflac/moonflac.exe --corpus generated
python cmd/test_cli.py --cli _build/native/debug/build/cmd/moonflac/moonflac.exe --flac "$(command -v flac)"
```

See `validation/evidence/2026-11-02-ogg-mux/README.md` for the current Ogg receipt.

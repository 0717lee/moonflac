# Changelog

## 0.2.0 — 2026-11-02

### Added

- Ogg FLAC output: `ogg_from_flac` converts a validated native FLAC stream into one Ogg logical stream while preserving STREAMINFO and metadata.
- `encode_ogg_pcm` whole-buffer PCM-to-Ogg convenience path.
- Native CLI command `moonflac ogg INPUT OUTPUT [--serial HEX] [--vendor NAME]`.
- Ogg page CRC, sequence, continuation, granule and EOS handling, including frames larger than one page.
- Four Ogg mux tests and a CLI contract test that verifies the output with independent libFLAC.

### Validation

- Native, JavaScript and wasm-gc: 197/197 project tests each.
- libFLAC 1.5.0 accepted Ogg outputs; decoded PCM matched source byte-for-byte for 16/24/32-bit and 2/6/8-channel fixtures.
- Existing decoder, encoder, CLI, browser and long-stream evidence is unchanged and remains described in `docs/ACCEPTANCE.md`.

### Boundaries

- The `ogg` CLI stages the complete native input in memory; the native `Encoder` remains the bounded streaming path.
- A bounded Ogg streaming writer, MP4/Matroska mappings and system player backends are not part of this release.

## 0.1.0 — 2026-10-01

Initial local delivery: pure MoonBit FLAC decoding on native/JS/wasm-gc, native FLAC encoding, native/Ogg decoding, CLI, browser playground, and independent validation. See `docs/ACCEPTANCE.md`.

# Changelog

## 0.2.4 — 2026-11-28

### Changed

- Upgrade CI and development to the official MoonBit `1.0.0-rc1+3c0520448` toolchain (`moon` / `moonrun 0.1.20261126`).
- Resolve every `moon check --deny-warn` diagnostic: migrate the reinterpret
  casts, `Buffer::write_bytes`, `StringView::to_string` and
  `Bytes::from_fixedarray` to their current APIs; derive `Debug` for the public
  value types while keeping a hand-written `Show` for `FlacError` and
  `Integrity`, so user-facing error and status text is unchanged.
- Replace the five catch-all cleanup handlers with explicit error capture so the
  sticky decoder error is recorded outside the handler.
- Move reference helpers used only by white-box tests into `_wbtest.mbt`, wrap
  the over-long golden-test byte literals, and update the golden generator to
  emit the same layout with its black-box imports marked `for "test"`.
- Move the browser exports from `link.*.exports` to `#export_name` wrappers and
  declare the package a foreign library. The emitted JS and wasm export sets are
  unchanged.
- Regenerate the committed public interface.

### Validation

- Three-backend `moon check --deny-warn`: 0 warnings; 197/197 tests pass on
  native, JavaScript and wasm-gc.
- The browser playground builds; JS exports stay `decode_browser` /
  `export_browser` and wasm-gc exports stay `run_decode` / `run_export`.

## 0.2.3 — 2026-11-18

### Changed

- Upgrade CI and development to the current official MoonBit toolchain `0.10.21+06da1ed44`.
- 0.10.21 removed implicit promotion of trait methods: expose `FlacError`'s
  derived `Show` implementation via `pub extend ... with Show::{to_string, output}`
  and replace promoted `.to_string()` calls in the browser bridge with
  `Show::to_string(x)`.
- Regenerate the committed public interface.

### Validation

- `moon fmt --check`, three-backend check/test: 197/197 on native, JavaScript
  and wasm-gc; CLI contract test with libFLAC PCM equality passes.

## 0.2.2 — 2026-11-11

### Changed

- Upgrade CI and local development to the current official MoonBit toolchain `0.10.20+65efd5b93`.
- Replace the removed promoted `to_json()` API with `Json(value)` in the CLI metadata report.
- Migrate `} derive(...)` to `#derive(...)`.

### Validation

- `moon fmt --check`, three-backend check/build/test: 197/197 on native, JavaScript and wasm-gc.
- CLI contract test with libFLAC PCM equality passes on the new toolchain.

## 0.2.1 — 2026-11-02

### Added

- `moonflac ogg --serial HEX --vendor NAME` for custom Ogg logical-stream identity and synthesized vendor text.
- Raw recovery test package restored to the public validation set.
- Published to Mooncakes as `0717lee/moonflac@0.2.1`.

### Changed

- Public tree keeps the current source, tests, examples and validation entry points; historical benchmark snapshots remain local.
- Submission-facing documentation is shorter and points to the current acceptance summary.

### Validation

- Native, JavaScript and wasm-gc: 197/197 project tests each.
- CLI contract test covers Ogg serial/vendor options and libFLAC PCM equality.

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

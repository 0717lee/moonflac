# Independent PCM fixtures

These tests contain libFLAC 1.5.0 encoded inputs and expected integer PCM verified
with libFLAC's decoder. MoonFLAC did not create the expected output.

Regenerate with `python scripts/generate-golden.py` after preparing validation
dependencies and corpus, then `moon fmt validation/golden`. Run with
`moon test --target native|js|wasm-gc validation/golden` (choose one target).

Tests00–08 use deterministic original PCM at depths4/8/12/16/20/24/28/32,
channels1–8, plus Ogg FLAC. Tests09–13 extract the first independently encoded
audio frame from CELLAR subset12/16/31/61/64; only STREAMINFO sample total, frame
size bounds and MD5 are adjusted to make standalone files. They cover LPC
precision15, escaped residuals, LPC order32, predictor overflow and zero-width
escape respectively. The 14 tests compare every output PCM byte, not a decoder
self-roundtrip. `sources.json` records source and fixture SHA-256 values.

Public audio is from Martijn van Beurden's FLAC decoder testbench (CC0), pinned
at Git tree `aa7b0c6cf32994c106ae517a08134c28a96ff5b2`.
See `COPYING.CC0`. Generated synthetic signals and test code use this project's
Apache-2.0 license. libFLAC is an external test-generation tool, not bundled code.

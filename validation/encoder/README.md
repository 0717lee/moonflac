# Independent encoder acceptance

Run from the repository root after preparing the existing validation dependencies:

```sh
python scripts/validate_encoder.py prepare
python scripts/validate_encoder.py cross
python scripts/validate_encoder.py compare --cli PATH_TO_MOONFLAC --ffmpeg PATH_TO_FFMPEG
python scripts/validate_encoder.py full-corpus --cli PATH_TO_MOONFLAC --timeout 600
python scripts/validate_encoder.py forced --log validation/results/encoder-forced.log
moon build --target native --release --target-dir _build/encoder-bench cmd/moonflac
python scripts/validate_encoder.py benchmark --cli _build/encoder-bench/native/release/build/cmd/moonflac/moonflac.exe
```

`prepare` creates328 input cases in ignored `validation/cache/encoder`: all29
bit depths ×8 channel counts; rate0 explicit non-audio and rates1..1048575;
blocks16..65535 and short final blocks; efforts0..8 with fixed/variable blocking;
silence, constant, ramps, polynomials, impulses, signed extrema, wasted bits,
seeded noise, correlated signals and stereo asymmetry; explicit zero, partial and
custom channel masks. Ten real recording segments come from the public CELLAR
subset and thirteen homogeneous segments from changing-format uncommon files.
Segments are the first8192 sample frames of each relevant recording/format part,
not claims that entire recordings were encoded. Source PCM is decoded by libFLAC.

The separate `full-corpus` gate processes every sample of all64 subset and11
uncommon source files. The four changing-format files become13 homogeneous
encoder inputs; together with71 uniform sources, this produces84 streams.
libFLAC source callbacks write interleaved PCM to disk one frame at a time.
MoonFLAC encodes effort5/block4096, then libFLAC callbacks compare every decoded
byte directly with that source PCM file. Official `flac -t` additionally checks
each output. Source channel masks are preserved; unrelated source metadata is
not copied into an audio-encoding test. Only uncommon11 permits the known single
libFLAC LOST_SYNC diagnostic. Checkpoints include every completed source and its
segments in `validation/evidence/encoder-full-corpus.json`.
The executed full-corpus run passed75/75 sources and84/84 output streams:
50,363,649 sample frames,313,149,688 source PCM bytes, and137,693,798 encoded bytes.

The CLI comparator encodes the original PCM with MoonBit, then decodes with
libFLAC1.5.0 and compares every integer. It additionally runs official `flac -t`
and `flac -a`. FFmpeg compares signed32 output scaled back to the source bit
depth for all audio cases. Rate0 is independently verified with libFLAC because
it is explicit non-audio. Channel-mask values are checked in serialized comments.

`cross` regenerates this package's executable source and runs native, JS and
wasm-gc in isolated `_build/encoder-validation` directories. Each backend emits276
streams:232 cases covering every bit depth4–32 × channel count1–8, ten additional
format/metadata cases and34 streaming inputs covering every nonempty
two-part cut of17 stereo32-bit sample frames plus scalar-at-a-time input. The
unpatched streaming output is independently decoded, including its unknown
STREAMINFO values. Expected PCM comes from original input, never MoonFLAC decode.
The full-domain cases contain33 sample frames, a32-sample block followed by one
final sample, signed extrema and seeded random values. All828 emitted streams
passed independent decoding; each named case was also byte-identical across the
three backends in this executed run.

The core writer's whitebox test `encoder external forced syntax fixtures` emits
137 full native FLAC files plus original PCM. Generate the log with:

```sh
moon test encoder_frame_wbtest.mbt --filter "encoder external forced syntax fixtures" --target native --target-dir _build/frame_encoder_native > validation/results/encoder-forced.log 2>&1
```

`forced` feeds every file to libFLAC and official `flac -a`. This independently
checks fixed orders0–4, LPC orders1–32, Rice parameters0–30, escaped widths0–31,
wasted bits1–31, partition order15, all four channel assignments, constant and
verbatim. Forced representations are test-only access to the actual writer;
they do not add production forcing options or replace natural selection tests.

Durable evidence files in `validation/evidence`:

| File | Executed evidence |
|---|---|
| `encoder-native.json` |315 original CLI cases; all exact PCM/official integrity/analysis checks pass |
| `encoder-changing.json` |13 additional real changing-format segments, independently decoded after encoding |
| `encoder-full-corpus.json` |All75 valid public source files in full,84 homogeneous outputs, exact PCM and official integrity verification |
| `encoder-backends.json` |276 streams per backend,828 total independent passes |
| `encoder-forced.json` |137 independent forced-representation passes with analyzer feature records |
| `encoder-constant32.json` |Natural allzero32-bit candidate-selection regression after the final cost fix |
| `encoder-benchmark.json` |18 measured MoonFLAC/libFLAC encode runs; all outputs independently validated |

Benchmark inputs are identical3-second stereo signals: AR-like24-bit, random16-bit,
and a repeated independently decoded recording segment16-bit. Both tools use
1024-sample blocks; libFLAC padding/seek table are disabled. Levels0/5/8 are each
tool's own effort settings, not promises of identical search work. Measurements
include launch/file I/O, exclude oracle decoding, and report complete file size.
Process memory is sampled every5ms (Windows peak working set when available).
These are single-run observations on a shared workstation, not controlled
microbenchmarks or claims of a speed/compression advantage. Python `psutil` is
needed only for benchmark memory sampling.

Long-stream encoder buffer/RSS scaling and WAV/RF64 reader interoperability are
covered separately by the CLI acceptance scripts. This directory does not claim
those gates from its short fixtures. No remote CI execution is implied.

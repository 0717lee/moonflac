# Confirmed review corrections — 2026-09-29

Scope: fix raw FLAC synchronization that depends on input chunking, and preserve RFC 9639 §8.6.2 channel layouts through WAV export and browser playback. Changes stay local. No encoder implementation or Ogg nil-EOS rule change is part of this correction.

Acceptance:

- A CRC8-valid incomplete raw frame takes precedence over apparent complete frames inside its PCM payload. Every split of the 42-byte nested-frame regression must produce the same 16 original samples as whole input and independent libFLAC decoding.
- Corruption recovery remains explicit, EOF still reports truncated candidates, and compressed limits and geometric retry behavior remain bounded.
- Custom masks, including case-insensitive/padded hexadecimal, zero and fewer assigned speakers than channels, propagate to CLI initial/final WAV/RF64 and both browser backends. Compatible chained layouts are retained; incompatible layouts are diagnosed before a misleading combined export/playback.
- Browser playback renders only channels with known, representable speaker positions; unsupported playback remains explicit while lossless export preserves original layout and PCM.
- Run the three-backend suite, focused libFLAC roundtrips and real browser regressions. Update the specification and acceptance records with executed evidence.

Status: both corrections implemented and verified. Earlier completion records describe the pre-review snapshot; the results below establish the corrected behaviors.

## Raw frame synchronization

The original 20-byte split reproduced a failing permanent test before the fix (`validation/results/raw-nested-before.log`). `RawDecoder` now stops scanning at the earliest incomplete header/frame candidate. It retains that candidate until more data arrives or decoding conclusively rejects it; it never commits a later apparent frame from that candidate's PCM merely because the current chunk ends early.

`raw_nested_wbtest.mbt` covers the original failure, every truncated prefix, terminal errors, limits of 20/41 bytes, and recovery after a confirmed CRC failure. Existing 1 MiB one-byte bounded-work testing still passes. `scripts/review_raw.py` independently constructs four payload placements (0/2/8/20), verifies outer and inner frames with libFLAC 1.5.0, and generates fixed expected integer PCM for `validation/review_raw`. Each backend executes 3960 chunkings: all two-part cuts, all three-part cuts and bytewise delivery. Native, JS and wasm-gc each pass. Real raw corpus uncommon 10/11 still matches libFLAC per-frame properties and PCM, with exactly the original no-skip / `Skipped(0,895)` diagnostics.

Evidence: [review-raw.json](../validation/evidence/review-raw.json), [review-raw-corpus.json](../validation/evidence/review-raw-corpus.json). Format/test build outputs live under `_build/review-raw`, so cached formatted tests are not rediscovered as source packages.

## Channel layout propagation and playback

`channel_layout.mbt` provides optional and effective mask interpretation. Absence, explicit zero, case-insensitive/padded hex and partial speaker assignments remain distinct where required. Malformed, overflowing or conflicting tags produce diagnostics. CLI initial and finalized WAV/RF64 headers and the shared JS/wasm-gc browser exporter pass the optional mask to `wav_header`. Ogg links must have compatible effective layouts for a single WAV/preview; raw/info/verify can still consume changing-layout links.

The original independent six-channel 24-bit fixture previously exported `0x003f`. Both browser backends now export `0x060f`, with integer PCM identical to libFLAC. Permanent CLI fixture generation builds extensible WAV input and uses official libFLAC to encode/decode it. Tests include side 5.1, mixed case, partial `0x3` with four channels, explicit zero, a custom two-channel/16-bit extensible header, RF64 and compatible/incompatible chains with cross-link cropping. The two-channel case also verifies that the initial header reserves the correct extensible-header length before PCM is written.

Playback follows Web Audio's actual speaker positions, not merely a channel count. Known named channels are mapped to canonical mono/stereo/quad/5.1 positions; unnamed channels are not rendered. Zero, side/height/back-center or otherwise unrepresentable layouts display a playback-unavailable notice while allowing original-layout WAV export. A `0x060f` side pair is never silently relabeled as the model's back pair.

The real Chromium regression passed 22 cases across JS and wasm-gc and 12 `OfflineAudioContext` impulse renderings that verify channel positions and silence of unnamed channels. General real-audio upload/drop/play/pause/seek/export/backend-switch smoke tests also pass on both backends.

Reference nuance: libFLAC 1.5.0 substitutes the default mask when exporting an explicit-zero mask. For that case, the test uses the original tag and RFC 9639 §8.6.2 as the layout expectation, while still comparing PCM against libFLAC. It does not treat the reference's metadata substitution as the correct expected mask.

Evidence: [CLI regression](../validation/evidence/review-cli-layout.json), [browser cases and routing](../validation/evidence/review-browser-layout.json), [original browser reproduction](../validation/evidence/review-browser-original.json).

## Final checks and reproduction

All three backends pass `moon check`, `moon test` (**67/67 each**) and `moon build`. `moon fmt --check`, `moon info`, dual browser builds, the full independent CLI suite and both real-browser smoke runs pass. Logs are in `validation/results/review-final/`; the [review summary](../validation/evidence/review-fixes.json) records this snapshot. Core Ogg mapping rules were not changed.

```sh
python scripts/review_raw.py
python scripts/review_raw.py --corpus
python cmd/test_cli.py --cli _build/native/debug/build/cmd/moonflac/moonflac.exe --flac validation/cache/libflac/flac-1.5.0-win/Win64/flac.exe --layout-fixtures validation/cache/review-layout
node playground/build.mjs
node playground/serve.mjs
# With the local server running, in a separate terminal:
node playground/test-layout.mjs
node playground/smoke.mjs "validation/cache/flac-test-files/subset/60 - mono audio.flac" js
node playground/smoke.mjs "validation/cache/flac-test-files/subset/60 - mono audio.flac" wasm-gc
```

The CLI/reference executable paths above describe this Windows checkout; supply the installed executables on another host. Permanent tests do not depend on the reviewer's temporary paths. Work remains local, without commit/amend, push, publication or changes to neighboring projects. At this review-fix snapshot, the encoder was a proposal only; its subsequent explicit authorization, implementation and acceptance are tracked in the existing [encoder ledger](ENCODER-PROPOSAL.md).

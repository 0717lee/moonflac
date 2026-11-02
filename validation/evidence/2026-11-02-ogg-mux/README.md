# Ogg FLAC muxing increment — 2026-11-02

This directory records the reproducible checks for the November 2026 increment: native FLAC → Ogg FLAC muxing, the `moonflac ogg` CLI command, and the whole-buffer `encode_ogg_pcm` convenience path.

## Toolchain and inputs

- MoonBit build tool: `moon 0.1.20261023 (3778465 2026-10-23)`
- Compiler used by the project CI: `0.10.16+b1a0e846e`
- libFLAC: `flac 1.5.0` (Win64 build under `validation/cache/libflac`)
- Native fixtures: `validation/cache/generated/depth-{16,24,32}-channels-{2,6,8}.flac`
- Source PCM: the matching `.pcm` files generated from independent libFLAC references.

## Commands

```sh
moon fmt --check
moon check --target native
moon test --target native
moon test --target js
moon test --target wasm-gc

# For each fixture:
moon run cmd/moonflac --target native -- ogg SOURCE.flac OUTPUT.oga
flac -t OUTPUT.oga
flac -d -f --silent --force-raw-format --endian=little --sign=signed -o OUTPUT.raw OUTPUT.oga
# Compare OUTPUT.raw with the fixture's independent source PCM.

python cmd/test_cli.py \
  --cli _build/native/debug/build/cmd/moonflac/moonflac.exe \
  --flac validation/cache/libflac/flac-1.5.0-win/Win64/flac.exe
```

## Observed results

- `moon test` on native, JavaScript and wasm-gc: **196/196 passed, 0 failed** on each target.
- The three new tests cover metadata/PCM round-trip, a frame larger than one Ogg page, and rejection of non-FLAC input.
- libFLAC `-t` accepted all tested Ogg outputs.
- Decoded PCM matched the independent source byte-for-byte:

| Fixture | Ogg bytes | PCM bytes | PCM SHA-256 |
|---|---:|---:|---|
| `depth-16-channels-2` | 5,843 | 8,468 | `974c75cb4e2ba671995351df6821e15cb962a069fd4cf2b285053731fc893304` |
| `depth-24-channels-6` | 26,373 | 38,106 | `382ecba36e4641494874f9b5504a8ff4d2493a084deeb700aa1b7a64e8274fd2` |
| `depth-32-channels-8` | 68,292 | 67,744 | `24ff897e0c58598c7e349559b231fdf3f3145f0302f4127283129670fd47d4cf` |

- `cmd/test_cli.py` passed all existing checks plus:
  `"Ogg mux: libFLAC accepts output and decoded PCM matches source"`.
  Its machine-readable receipt is `cli-contract.json`.
- A 4-bit Ogg output passed `flac -t`; libFLAC's raw-output mode does not accept 4-bit samples, so no 4-bit byte comparison is claimed.

## Scope

The muxer repackages frames from the existing native encoder after `build_index` validation. It is not a second audio encoder. The CLI stages the native input in memory; the native `Encoder` remains the bounded streaming path. A bounded Ogg streaming writer is not claimed.

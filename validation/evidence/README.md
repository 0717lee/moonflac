# Executed independent validation — 2026-09-29

The November 2026 Ogg muxing increment has its own receipt: [2026-11-02-ogg-mux](2026-11-02-ogg-mux/README.md). The tables below retain the initial decoder validation snapshot. The subsequent [confirmed review corrections](../../docs/REVIEW-FIXES.md) are recorded in `review-fixes.json`, `review-raw.json`, `review-raw-corpus.json`, `review-cli-layout.json` and `review-browser-layout.json`. The later encoder and performance-hardening validation passes all three targets with 99/99 tests each on Windows and WSL2. `acceptance-initial.json` preserves the earlier snapshot; the current hardening result is indexed by `hardening-final.json` and the [acceptance ledger](../../docs/ACCEPTANCE.md).

Hardening evidence includes the repeated CLI/core benchmarks, measured profiler
categories and allocation events, `hardening/` full oracle regressions,
`hardening-linux.json`, retained same-seed mutation cases and classifications,
and `hardening-long.json` / `hardening-large-decode.json` for physical >4 GiB
RF64 and hour-scale execution. `hardening-review/` contains unchanged copies of
the independent stage-review reports. The large RF64 output remains in ignored
`validation/cache/encoder-stress/` for inspection; cache contents are not library
release artifacts. See the ledger for the final independent-review status.

Host: Windows x64. Moon `0.1.20260827 (d0aaa07 2026-08-27)`.
Independent oracle: official Xiph libFLAC 1.5.0 Win64, using its C decoder's
signed integer sample callbacks. No MoonFLAC output is used as reference PCM.
Release ZIP SHA-256:
`53f1500f0d6e7c61379d7fee50d4a9f7f504c650009506d9ba015530d76c0dde`.
CELLAR source Git tree: `aa7b0c6cf32994c106ae517a08134c28a96ff5b2`;
all93 source files downloaded and verified against their Git blob hashes.

Validated native CLI SHA-256:
`0f4ebf92df8582ec1fd0594ed14fa7c05c3e360de7482e710c9cc04321810a19`.
Validation runner SHA-256:
`e86bb521fd0ad93f9eaa53eec6208049185ba066d7ea554e32a3a812b7f991fe`.

| Evidence | Executed result |
|---|---|
| `generated-native.json` |245/245 exact PCM comparisons passed; every bit depth4–32 × channels1–8, extrema, high rates/blocks, Ogg |
| `subset-native.json` |64/64 exact PCM comparisons passed, including real spoken multichannel audio, LPC32, Rice escape, predictor overflow, legacy variable blocks,87.3MB file with 82.2MB metadata |
| `frames.json` |11/11 uncommon streams passed exact per-frame block/rate/depth/channel/PCM comparison; property changes and raw multicast included |
| `faulty.json` |11/11 explicitly rejected with exit3 and positioned diagnostic; no timeout/crash |
| `../golden/` |14/14 independent PCM tests passed separately on native, JavaScript and wasm-gc |

Commands:

```sh
moon build --target native cmd/moonflac
moon build --target native validation/runner
python scripts/validate.py compare --cli _build/native/debug/build/cmd/moonflac/moonflac.exe --corpus generated --report validation/results/generated-native.json
python scripts/validate.py compare --cli _build/native/debug/build/cmd/moonflac/moonflac.exe --corpus subset --max-buffer 134217728 --timeout 180 --report validation/results/subset-native.json
python scripts/validate.py frames --cli _build/native/debug/build/validation/runner/runner.exe --corpus uncommon
python scripts/check-faulty.py --cli _build/native/debug/build/cmd/moonflac/moonflac.exe
moon test --target native validation/golden
moon test --target js validation/golden
moon test --target wasm-gc validation/golden
```

`uncommon11` starts with895 garbage bytes. libFLAC reports LOST_SYNC; the explicit
raw API reports `Skipped(0,895)` and all subsequent frame properties/PCM match.
All other libFLAC errors remain failures. Subset55 needs the explicitly raised
128MiB metadata/compressed-buffer cap; default32MiB failure is a resource limit,
not corrupt-format evidence. Tests do not claim every possible FLAC bitstream is
enumerated, nor that remote CI has executed. Runtime benchmark/browser/CLI export
evidence is documented separately by those runners.

Reported native per-case seconds include process startup and PCM file output;
they are not isolated core decoding benchmarks. Full integer PCM comparison is
performed before recording a pass; SHA-256 in the evidence makes successful
outputs independently identifiable.

## High-effort follow-up (2026-09-29)

The independently accepted `hardening-*` reports above are preserved. The separate `effort8-*` reports and `effort8/` directory belong to `high-effort-optimization-20260929`. Baseline identity is `effort8-baseline.json`, the identical measurement overlay is `effort8-benchmark-harness.json`, and the archive is `../baselines/encoder_frame.pre-effort8.mbt.txt`. `effort8-progress.json` tracks unfinished gates and review deduplication.

`effort8/acceptance.json` records current Windows checks and independent encoder oracles; `effort8/linux.json` records actual WSL2 checks; `effort8/bitstream-equivalence.json` compares all 828 generated streams against the accepted prior hashes. Diagnostic profiles deliberately use instrumented copies; allocation timing uses a grouped-allocation variant and cannot be read as controlled throughput. `effort8-core-benchmark.json` and `effort8-cli-benchmark.json` record the balanced six-round protocol, fixed input set, calibration, every result and independent validation. Read each report's status before treating it as complete.

The effort-8 follow-up passed independent review `high-effort-optimization-20260929-independent-01`. `effort8-final.json` indexes the frozen production/validation sources and reports. `effort8-review/` preserves original feedback, review reports, logs, extra oracle source (as `.mbt.txt` to avoid compiling archival material), mathematical proof and packet-transport records. `archive-index.json` maps original locations to byte-identical archived files and hashes. Temporary audio from the packet review was already cleaned by its originating run; the original successful execution record is retained without reconstruction or rerun.

## Speed-first follow-up

`speed-first-*` belongs to the separately authorized speed-first encoder task. Old/new encoded bytes may differ; independent integer PCM and integrity remain mandatory. `speed-first-baseline.json` and `../baselines/speed-first/` freeze the accepted previous implementation. `speed-first-candidate-revision3.json` identifies the current source and executable; its pre-format identity is retained separately. `speed-first-progress.json` records pending gates and review deduplication.

Failed initial holdout sizes are retained in `speed-first-holdout-gate.json`, with variant diagnostics alongside them. The original 17 holdout cases remain regression checks; the 14-case second holdout has its own sealed manifest. The first general-depth check failed because its validation command requested nonexistent `pcm_s20le`; the retry uses strict s32le scaling and retains the failure. `speed-first-final-holdout-replay.json` connects the final executable to all 31 checked streams with byte-identical replay and fresh independent decoding.

`speed-first-checks-revision3/` contains Windows package/CLI/oracle gates; its `final-artifact/` subdirectory checks the actual timed CLI. `speed-first/linux-revision3.json` is actual WSL2 execution. Formatting failures and pre-format runners are preserved, and whitespace-only source changes are explicit. `speed-first-memory-revision3.json` covers affected streaming memory. New benchmark reports retain every warmup/measured observation, complete-file/payload/PCM ratios, balanced positions, calibration and validation. Check each status before citing completion. The final local audit is separate from the subsequent paired independent-review verdict.

Revision4 was the first review-fix delivery. `speed-first-revision4-final.json` supersedes `speed-first-final.json` for current claims; the earlier file is retained as historical evidence, including its reviewed mixed core/CLI ratio. The corrected current core report has no such ratio. `speed-first-short.json` covers145 independently decoded review/neighbor inputs, and `speed-first-revision4-quality.json` rechecks the31 retained quality cases. Original review records, old report/script snapshots and both revision3/revision4 codec source snapshots are indexed under `speed-first-review/`.

Only `speed-first-revision4-cli-benchmark.json` and `speed-first-revision4-core-benchmark.json` are new final-artifact timing measurements. The17-case,32768 and extra-reference timing reports remain explicitly labelled revision3 history. Windows/WSL revision4 gates and the new block256 memory report use their own output paths. The inherited blind-holdout flag in the initial revision4 identity was corrected after timing, with the original metadata archived; all source/artifact/input hashes are unchanged. Both earlier holdout sets are now regression sets, not newly unseen revision4 data.


Revision7 is the independently accepted review-fix delivery (`speed-first-revision7-final.json`, `speed-first-candidate-revision7.json`); revision4 above is historical. Review independent-02, exact partition-bound proof, the frozen32 pulse matrix and retained intermediate failures are preserved. Revision7 verification includes121 tests per backend on Windows/WSL,96 pulse backend/case combinations,145 short cases,31 retained quality cases and six affected memory workloads. Fresh controlled CLI/core results are4.828x/3.601x baseline speedups, with CLI8.709x same-round libFLAC elapsed time. Final independent review passed. `speed-first-completion.json` is the current completion record; the pre-review local audit remains immutable. Original reviewer evidence and fixtures are under `speed-first-review/independent-03/`, with byte hashes in its archive index.

# MoonFLAC development contract and acceptance ledger

Goal: complete pure MoonBit RFC 9639 decoding and the subsequently authorized native FLAC encoder on native, JS and wasm-gc, with native/Ogg decoding, bounded incremental APIs, exact sample seeking, CLI and browser tools. All changes remain local under this project. Ogg output was outside the original closeout scope; the November increment adds muxing from completed native frames. OS playback backends, remote publication and changes to neighboring projects remain outside this scope.

## Ogg output increment, 2026-11-02

The November increment adds `ogg_from_flac`, `encode_ogg_pcm` and the native CLI `ogg` command. It repackages frames produced by the existing native encoder; it does not add a second audio encoder or change FLAC frame coding. The native input is validated by `build_index` before muxing.

| Gate | Result |
|---|---|
| Ogg mapping and framing | 51-byte mapping packet on a BOS page; metadata packets with last-flag handling; CRC, sequence, continuation, granule and EOS checks on the reverse path |
| Metadata preservation | Native metadata blocks retained; an empty Vorbis-comment packet is added only when needed |
| Frame boundaries | Frames at or below 65,024 bytes use one page; larger frames split into full-lacing pages plus a terminating page |
| Tests on all targets | **196/196** project tests on native, JS and wasm-gc, including 3 new mux tests |
| Independent reference | libFLAC 1.5.0 `-t` accepted outputs; decoded PCM matched source byte-for-byte for 16/24/32-bit, 2/6/8-channel cases; 4-bit passed `-t` but libFLAC raw output does not accept 4-bit samples |
| CLI contract | `python cmd/test_cli.py` muxes a native file, verifies the Ogg result with libFLAC, and compares PCM exactly; all existing checks remain green |

The CLI `ogg` command stages the complete native input in memory. The library's native `Encoder` remains the bounded streaming path; a bounded Ogg writer is not claimed in this increment.

## Current local delivery, 2026-10-01

The stable implementation remains **C95**. No C96–C102 experiment was promoted.
Functional closeout checks below pass locally; **the faster-than-libFLAC goal is
not achieved**. Consolidated independent functional final review passed
(`moonflac-closeout-20261001-independent-final`), with no unresolved confirmed
functional findings. The [archived verdict](../validation/evidence/closeout-20261001/independent-final/review.json)
closes this local development round, not the performance objective. Later
sections retain the results and open items of their named historical stages.

| Gate | Current evidence and result |
|---|---|
| Windows native/JS/wasm-gc, API/build/format, CLI, declared quality | Reuse unchanged C95 acceptance: 194 tests/backend, 220 independent cases, 16 long8 outputs, both CLI suites and four memory observations; stage18 independent review passed |
| Current Linux/WSL2 | Fresh check/test/release on all three backends, 194 tests each; 24 independent CLI cases; all 828 existing matrix outputs independently decoded by libFLAC, including 102 streaming cases; all 276 outputs identical across backends |
| Current native long streams | Four 60/3600-second audio cases: stereo24/effort5/block4096 and 8-channel32/effort8/block65535; full libFLAC PCM byte-count/MD5 and CRC checks pass |
| Physical RF64 beyond 4 GiB | Largest input and MoonFLAC-decoded output are each 5,529,600,104 bytes; ds64, full PCM hash and FFmpeg check pass. Moon/FFmpeg follow-up covers this largest case; libFLAC covers all four |
| Current sustained differential stress | One continuous 1,800.89-second run: 3,304 valid encodes and 13,216 mutations; no crash, resource failure or mutually accepted PCM mismatch. All 71 reference-only acceptances are independently classified as invalid STREAMINFO; none remain unclassified |
| Current browser delivery | Fresh isolated JS/wasm-gc assets: 22 layout cases, 12 offline routing renders and four interaction smoke runs, including C95-encoded real audio. Exact tested assets copied into the local Playground; previous assets retained |
| C102 failure closure | Two bounded post-disk-recovery diagnostics: reused cache failed compiler linking; a fresh target passed unchanged native tests and 16 focused tests/backend. No candidate defect reproduced; exact damaged cache artifact was not isolated. Candidate remains unselected |
| Performance acceptance | **Not met.** Retained C95 diagnostic time ratios are 1.708871 core and 1.447868 CLI versus normal libFLAC-8; these are one-round diagnostics, not final acceptance. Original12/long8 wins and two independent warmup-plus-10-round blocks remain unproven |

Reports and exact executed commands are under
[`validation/evidence/closeout-20261001/`](../validation/evidence/closeout-20261001/).
The Windows campaign, Linux `report-full.json`, browser report and asset promotion
receipt bind the current source, tools and outputs. Evidence runners deliberately
reject existing output directories; replay requires fresh work/report locations.
Ordinary portable build and validation commands remain in the [README](../README.md#build-and-test).

The six inherited sine compression-size weaknesses remain reproducible in the
[corrected supplemental record](../validation/evidence/supplemental-quality-stage18/README-v2.md),
including the worst approximately 39% increase. Fixed declared quality budgets
still pass; they are not arbitrary-input size guarantees. C96 repairs those six
files but costs 33.7% more core time on its screen, so it remains unselected.
No further unsupported micro-optimization sequence is planned. The measured
core gap requires about a 41.5% reduction in C95 time; there is currently no
validated proposal that closes it. This is not a claim that improvement is
mathematically impossible, nor a waiver of the speed requirement.

Retention limit: the Linux `/tmp` worktree and ELF are no longer present.
The retained source/tool manifests, 191 Windows-side logs and actual encoded
outputs were independently checked; the original ELF cannot now be reread.
A later WSL restart is consistent with temporary-directory cleanup, but the
cleanup actor and historical UID were not independently established. No evidence
was recreated to replace those missing temporary artifacts.

Platform limits: WSL2 shares the Windows host; independent Linux hardware and
macOS were unavailable. Linux checks use libFLAC; Linux FFmpeg was not installed.
Windows FFmpeg evidence is separate. Remote CI, publishing and deployment were
not performed. Browser playback still holds decoded PCM in an AudioBuffer;
AudioWorklet streaming and an Ogg encoder are outside this delivery scope.

Current root delivery C95 passes 194/194 tests on native, JS and wasm-gc in both the isolated source and actual project, plus default format/API/check/release and both CLI suites. The 220 independent cases and 16 long8 CLI/core outputs pass PCM/integrity and fixed size budgets, including unchanged short/low-effort byte contracts. Outputs match C83 on these sets; general compressed-byte identity is not promised by the numerical analysis. Direct four-round C95/C83 ratios are 0.984459 core and 0.975997 CLI, retaining every regression. Four affected memory observations and actual-root/frozen generated-C correspondence pass. Stage18 independent review passed. See [C95 evidence](PERFORMANCE.md#selected-triangular-variance-implementation-c95).

That audit ran 13 targeted tests per backend, 49 new libFLAC PCM/integrity comparisons (46 also through FFmpeg), and 11,232 independent shared-guard combinations. It also found six supplemental sine inputs more than 3% larger than e681, with the worst 3411→4743 bytes. All 49 outputs match C83, so this is an inherited weakness outside the declared quality sets, not a C95 regression or a failure of those fixed gates. The original supplemental assertion failure remains preserved. All six anchor streams have since passed independent PCM/CRC/MD5 checks. [Frozen repros and a project-relative replay command](../validation/evidence/supplemental-quality-stage18/README-v2.md) make the limitation explicit; no arbitrary-input size guarantee is claimed.

Stage19 diagnosis confirms that useful anchor models are generated but left unattempted by regular proxy ranking and four-legal admission. The trace does not distinguish covariance ranking from sampled-width fallback. The generic C96 residual-ranking experiment passes19 focused tests/backend and restores all six files exactly to anchor bytes, but its representative core cost rises33.7%, so it is not promoted. C95 remains the root delivery. A separate count-only Int32 eligibility study passes13 exact-output checks; C97 subsequently passed five focused tests/backend and24 independent original12 outputs, but core timing did not justify promotion (full12 ratio1.002348). C98 passed six focused tests/backend and24 exact outputs but failed the packed-output codegen gate; it was not timed. Both remain isolated and unselected; current delivery is C95. See PERFORMANCE.md stage20. Stage21 C99/C100 each pass16 focused tests/backend and24 independent exact C95 outputs. C99 full12 core ratio1.002819 does not justify promotion; C100 retains hot-loop spills and adds tuple allocation, so it stopped before timing. Stage20 review's remaining supplemental README attribution was corrected in the versioned linked README-v2; original evidence is preserved.

Retained C95 single-round normal-libFLAC diagnostics are 1.708871 core and 1.447868 CLI times reference time; real-audio subset ratios are 3.507438/1.600463. Quality and calibration pass, speed does not; these reports are ineligible for final acceptance. Actual-root/frozen generated-C correspondence is checked separately from distinct MSVC/Clang binaries. Current-artifact cross-system/hour-stress checks and independent functional final review passed in the closeout above; the final performance gates remain unmet.

Stage15 independently accepted the archived C84–C87 unselected experiments with no findings, checking source/output/timing bindings and independent arithmetic/index oracles. It did not rerun unchanged C83 acceptance. The next C88 variance-bounds and C89 CLI-copy trials also passed their focused correctness gates but remained unselected: full12 core 1.000926 and CLI 0.999830 respectively against C83. These are separate experiments and measurement scopes; their ratios are not combined. The root remained C83 through those trials.

Stage16 independently accepted C88–C90 evidence without findings. Stage17's C91/C92/C93 also remain unselected after focused correctness and representative timing. C93 intentionally changes floating analysis order while preserving the real quadratic formula; its independent Fraction numerical contract and own original12 PCM/integrity/e681 gates pass, but its screen shows no aggregate gain. The fixture syntax failure and serializer-only repair are retained. No full acceptance, long validation or promotion is claimed for these trials. A separate count-only run found just 62 transient partition records in recording28 and does not justify the proposed additional scratch storage. See [stage17](PERFORMANCE.md#numerical-analysis-and-allocation-counts-stage17).

Stage17 independent review passed, including 78 additional exact Fraction cases. C94 subsequently passed 15 focused tests/backend and its own original12 integrity/quality checks, but full12 CLI time regressed despite improved core time; it remains unselected alone. Actual role-specific codegen and paired short/long recording traces do not establish the regression's cause. Its full193/backend, 220-case and long8 runners remain unexecuted. The selected C95 combination has separate executed gates, retaining the original short/low-effort byte-equality requirements.

Independent stage13 review confirmed C77's local optional AVX512 results and found a current-host eligibility gap in the historical replay entry. The new versioned entry freshly checks both artifacts' CPUID/XCR0 requirements before dispatch; four mocked checks and an actual probe plus paired smoke pass. Historical runners are preserved. Stage14 independently closed this limited P2 correction for the guarded entry; generic historical runners remain unguarded. The 220/long8 set was not rerun for this fix. C77 numbers still refer to C76-generated source, not C83. C78/C79, C81 and C84–C86 remain unselected. C84/C85 passed focused correctness and exact-output checks but showed no convincing aggregate timing benefit; C86 passed correctness but failed its codegen gate before timing. No final libFLAC win is claimed.

Stage11 independent review ran fresh targeted tests14/14 per backend and49 new CLI cases against C62/freshMSVC/frozenClang with libFLAC PCM, hashlib MD5 and flac-t verification (46 also checked through FFmpeg). Separate C66/C68 arithmetic/model/index oracles passed. The cache inheritance records, three reference curves, actual-root build boundary and generated-C provenance were checked. Long/memory outputs were compared with previously verified identical C62 bytes; this was not repeated decoding or a new performance run. Stage10's P3 evidence issue is closed. Archive: `validation/evidence/faster-than-libflac-review/independent-stage11/`; the final speed and current-artifact stress/cross-system gates remain open.

The combined independent stage10 review accepted the selected C52/C60/C62 implementation and current artifacts: fresh targeted tests passed17/17 per backend, and49 new CLI cases matched previously reviewed C41 bytes and independent libFLAC PCM/integrity checks (46 also checked with FFmpeg). Its one P3 finding concerned a historical proof locator: the original2218-byte proof was later extended by a471-byte acceptance appendix. The exact original snapshot and explicit binding addendum now preserve both versions without rewriting the original codegen report. See `validation/evidence/faster-than-libflac/candidate62-bounded-lag-registers/codegen-review-binding-addendum.json`; independent reports are archived under `validation/evidence/faster-than-libflac-review/independent-stage10/`. This evidence repair does not require another codec test run or complete the speed goal.

PCM is signed, unshifted Int samples; prediction and stereo intermediate arithmetic uses Int64. Returned frames own their planar arrays. Resource limits produce explicit errors. Integrity is observable independently from incomplete input. Independent libFLAC/FFmpeg PCM is the correctness oracle.

Stage9 C60 was validated in an isolated tree while root delivery was C52: 176/176 tests per backend, check/format/release/API and both CLI suites pass; 220 independent outputs and all long8 CLI/core outputs are exact C52 bytes. Four-round original12 engineering ratios are 0.988881 core and 0.978001 CLI relative to C52. This does not complete the libFLAC speed gate or establish final cross-system/stress acceptance. See [the C60 evidence and limits](PERFORMANCE.md#isolated-c60-residual-conversion-stage9).

Feature acceptance completed locally on 2026-09-29, with two subsequently confirmed review defects corrected and revalidated in [the review addendum](REVIEW-FIXES.md). The subsequent performance-hardening phase has its own gate ledger below. The detailed [RFC matrix](SPEC-MATRIX.md) lists individual coding rules and the [independent evidence](../validation/evidence/README.md) records source revision, reference tools and per-file outcomes. Counts below describe executed cases, not a proof by enumeration of every possible bitstream.

Current performance-stage delivery is C52: actual root tests174/174 on native, JS and wasm-gc, both CLI suites, retained220 independent quality cases and long8 pass. C52 adds exact wide fixed-order integer prediction to C41, preserving output bytes and the public API. Four-round original12 engineering comparisons give C52/C41 core0.976866 and CLI0.979149; these are not final libFLAC acceptance. Numerical LPC, stronger Rice-bound and MD5 alternatives were independently checked but not integrated when broader timing failed to establish benefit. The goal remains open: measured engineering gains do not satisfy the required libFLAC speed gate. Current source, validation, failed-attempt and selection evidence is described in [the performance ledger](PERFORMANCE.md); stage7 evidence remains unchanged.

| Requirement | RFC | Implementation | Verification | Status |
|---|---|---|---|---|
| 4–32 bits, 1–8 channels, full sample/block ranges | 8.2, 9.1 | frame.mbt | 245 generated + 64 subset + 11 uncommon exact independent PCM comparisons; 14 independent golden cases on each backend | verified |
| Fixed/variable blocks, coded numbers, reserved values | 9.1, B.1 | frame.mbt, stream.mbt | subset 24–27, frame tests, faulty 11/11 explicit rejection | verified |
| Constant/verbatim/fixed/LPC, Rice/Rice2/escape/wasted bits | 9.2, Appendix A | frame.mbt | full corpus; all fixed orders, LPC 1–32, Rice2 extremes, escape-zero tests | verified |
| Stereo reconstruction and 32-bit intermediates | 9.1.3, Appendix A | frame.mbt | 33-bit side extrema, 53-bit-safe LPC arithmetic, overflow corpus and golden cases | verified |
| All metadata and unknown block retention | 8 | metadata.mbt | structured metadata tests; subset 45–55, including 87.3 MB file with 82.2 MB metadata with explicit 128 MiB limit | verified |
| CRC8/CRC16 and PCM MD5 | 8.2, 9.1.8, 9.3 | frame.mbt, md5.mbt | RFC D.1 independent digest, RFC 1321 vectors, odd-depth reference PCM, every truncation and bit mutation | verified |
| Native/Ogg mapping and page integrity | 10.1 | ogg.mbt, stream.mbt | independent Ogg 4/16/24/32-bit, serial/chained/range CLI tests, page/packet/granule corruption tests | verified |
| Raw multicast and changing frame properties | 6, 9, C.8 | raw_stream.mbt, stream.mbt | all 11 uncommon frame properties and PCM equal libFLAC; explicit 895 skipped bytes in uncommon 11 | verified |
| Incremental input, finish, ownership and bounded memory | 11 | stream.mbt, raw_stream.mbt | arbitrary cuts; 1 MiB one-byte metadata/frame tests with geometric snapshots; 5/60/300-second OS memory measurement | verified |
| Sample index, seek table and exact crop | 8.5 | seek.mbt, seek_table.mbt | indexed/native/Ogg-chain range tests; seek point corruption; CLI independent PCM slices | verified |
| CLI info/verify/decode, PCM/WAV/extensible/RF64 | tool contract | cmd/, wav.mbt | cmd/test_cli.py libFLAC roundtrip, odd 8-bit padding, four bit depths, chain/cross-link ranges, size overflow and exit codes | verified |
| Browser worker decode, waveform/play/seek/export/performance | tool contract | browser/, playground/ | real Chromium JS + wasm-gc artifacts; file/drop/play/pause/seek/export/mobile/error/backend switching; integer WAV independent equality | verified |
| Raw candidate precedence | review correction | raw_stream.mbt | four independently decoded nested-frame layouts, 3960 chunkings per backend; EOF/limit/corruption regressions | verified |
| Custom channel layout propagation | 8.6.2; review correction | channel_layout.mbt, CLI, browser bridge/playback | independent WAV/RF64 roundtrips; 22 browser cases and 12 offline speaker-routing renderings; zero/partial masks and Ogg-link compatibility | verified |
| Native FLAC encoder, all proposed coding modes and PCM formats | authorized encoder extension | encoder*.mbt | 328 native independent cases; 828 independently decoded cross-backend streams; 137 independently analyzed representations; [six-gate encoder ledger](ENCODER-PROPOSAL.md) | verified |
| Encoder streaming, metadata, CLI PCM/WAV/RF64 and memory | authorized encoder extension | encoder.mbt, encoder_metadata.mbt, pcm_input.mbt, cmd/ | arbitrary scalar/byte cuts, backpressure/EOF/ownership, all 29 WAV valid depths, source MD5/flac -t, 300-second and maximum-block memory evidence | verified |
| Public API, bilingual docs, licensing, CI, reproducibility | delivery contract | pkg.generated.mbti, docs/, examples/, .github/ | moon fmt --check; check/test/build native/JS/wasm-gc; 99/99 tests per target after hardening; compiled examples and moon info | verified locally |

Specification: https://www.rfc-editor.org/rfc/rfc9639.html . Verified errata 8256 and 8810 are applied; rejected erratum 9096 is not applied. Reference: https://github.com/xiph/flac . Corpus: https://github.com/ietf-wg-cellar/flac-test-files at `aa7b0c6cf32994c106ae517a08134c28a96ff5b2`; all 93 source files were blob-verified and validity follows each group README.

## Performance hardening contract (2026-09-29, independently passed)

Assignment `performance-hardening-20260929` preserves the accepted codec features and exact integer PCM. This phase measures hotspots before optimizing encoder search, then validates the same final source/build with independent correctness and controlled performance evidence. Local delivery only; no Ogg encoder, player/editor expansion, commits or publication.

- [x] Freeze source, release binaries, toolchain, hardware and input identities; measure candidate generation, prediction, Rice planning, writing and quotient-array allocation events.
- [x] At least one warm-up and five measured runs per configuration: noise, correlated signals, real recordings and speech, 16/24/32-bit and multichannel; retain raw samples, median/dispersion, size and process/core timing distinction.
- [x] Optimize measured waste with demonstrated improvement beyond variation on search workloads. All 20 paired input/effort outputs remain byte-identical; no compression tradeoff was introduced. Startup-dominated cases do not demonstrate a general speed improvement.
- [x] Final candidate: three-backend tests/build/check (99/99 each), 328 independent libFLAC cases and 327 FFmpeg cases, 137 forced representations, 828 cross-backend streams, CLI and all 75 valid corpus sources / 84 complete output streams.
- [x] Physically process more than 4 GiB PCM/RF64 and hour-scale predictor/high-effort/max-block/multichannel streams: all four long-input cases passed; actual 5,529,600,104-byte RF64 output retained, ds64/format/sample count and original/libFLAC/MoonFLAC/FFmpeg PCM MD5 all match.
- [x] Sustained seeded mutation/differential stress: two actual 30-minute runs; the fully journaled run completed 3,784 encodes and 15,136 mutations, with no crash/timeout/accepted-PCM mismatch. All 84 acceptance differences were independently classified as incorrect STREAMINFO, including all 82 from the earlier 3,715-case run. This is non-coverage-guided stress.
- [x] Execute available Windows and Ubuntu 22.04.5 WSL2: three backends each 99/99, check/release builds, Linux 24 CLI PCM cases and 828 independent backend streams. macOS and independent Linux hardware were unavailable; remote CI was not run.
- [x] Update measured evidence and send deduplicated completion to the paired independent reviewer; final receipt and independent passed verdict confirmed.

Coordination: developer turn `01a0ebea-f65b-72e2-ab54-5c0be1a9a8ae` acknowledged setup `mutual-heartbeat-20260929`. Decoder fixes, native encoder acceptance and this performance-hardening phase have passed independent review (`performance-hardening-independent-review-20260929-final`).

The native acknowledgment was received by the reviewer at 06:48:57 UTC (reviewer turn `01a0ebec-7319-7c01-bf38-2d6f9ca19b82`). The optimization/platform stage was submitted as `performance-hardening-stage-20260929-01` and confirmed received at 07:36:10 UTC (reviewer turn `01a0ec17-aed6-7000-80e0-2ff48b82cd0a`); it explicitly leaves sustained stress gates open. Windows correctness and Linux/WSL execution are complete. Raw measurements are `validation/evidence/hardening-{benchmark,benchmark-speech,core-benchmark,profile-comparison}.json`. Correctness reports are in `validation/evidence/hardening/` and `hardening-linux.json`; all 828 Windows cross-backend outputs also match the accepted pre-optimization hashes.

All four long-input cases passed independent PCM/MD5/CRC verification. The
3,600-second stereo 24-bit effort-5 RF64 physically contained 1,036,800,000 PCM
bytes; encoding took 1,078.49 s with 10,448,896 B peak working set, compared with
8,740,864 B for 60 seconds. The 3,600-second eight-channel 32-bit effort-8,
block-65,535 case physically contained 5,529,600,000 PCM bytes and completed in
5,171.75 s with 26,218,496 B peak, versus 26,312,704 B for its 60-second control.
Source and independent libFLAC PCM MD5 are both
`5ca93440041056a4e6b10d9392778dba`; `flac -t` and decoded byte/sample lengths
passed. These runs overlapped correctness/stress jobs and are not controlled
throughput benchmarks. The actual >4 GiB RF64 output check also passed:
`hardening-large-decode.json` records a 5,529,600,104-byte file, data length
5,529,600,000, 172,800,000 sample frames, and the same PCM MD5 from MoonFLAC's disk
output and FFmpeg 9.0.1. The `0x63f` channel mask and full extensible format fields
are independently recorded in `hardening-review/final.json`. Native decode/export took
172.17 s with 16,904,192 B peak working set. The physical RF64 file remains under
`validation/cache/encoder-stress/` for independent inspection.

Both seeded 30-minute stress jobs completed without codec source changes. The
initial `hardening-fuzz.json` records 3,715 encodes / 14,860 mutations over
1,800.235 s. The fully retained `hardening-fuzz-journal.json` records 3,784 encodes
/ 15,136 mutations over 1,800.031 s; 127 mutually accepted mutations had identical
PCM. No MoonFLAC-only acceptance, crash, timeout or PCM mismatch occurred.
`scripts/classify_stress.py` checked every saved disagreement: 43 inconsistent
frame ranges, 37 forbidden block ranges, two wrong nonzero sample counts, one
wrong fixed-stream maximum block size and one maximum frame size smaller than
the official frame analysis. `hardening-fuzz-classification.json` also proves
that the journal covers all 82 disagreements from the earlier same-seed run.
RFC 9639 §8.2 permits rejecting incorrect STREAMINFO; these acceptance differences
do not establish a valid-input decoder defect. The first 125 cases were also
replayed separately. All 276 Linux/native streams match Windows/native hashes.
The two stress runs use the same seed and the second includes the first prefix;
coverage is 3,784 generated iterations, not the sum of the two run counts.

Stress/classification stage `performance-hardening-stress-20260929-02`, source
turn `01a0ec18-9f72-7c03-98d5-8178290b73ff`, was confirmed received by the reviewer
at 07:52:00 UTC (reviewer turn `01a0ec26-1459-7842-833a-abfde2f1fdc9`). It explicitly
retains the in-flight maximal long-stream and physical RF64 export gates.

The pre-optimization `encoder_frame.mbt` is also retained under
`validation/baselines/encoder_frame.pre-hardening.mbt.txt` with its original
SHA256. `scripts/profile_encoder.py freeze --historical` was exercised in a
separate reconstruction directory: native release build succeeded, the encoded
noise case was byte-identical to the original frozen baseline, and libFLAC PCM
matched. Evidence: `hardening-baseline-reconstruction.json`. This closes the
cache-cleaning reproducibility gap without changing the running candidate.

Independent review `performance-hardening-independent-review-20260929-01`
returned `stage-verdict: passed`, `status: continue` for the first two stage
source turns. It independently checked 1,480,942 Rice parameter selections,
72 additional CLI boundary distributions with libFLAC PCM, repeated all 84
saved disagreement reproductions, and recomputed benchmark medians/MAD. No
blocking defect was found. Copies of the supplied review reports are retained
unchanged under `validation/evidence/hardening-review/`. That stage review left
the maximal long-stream and physical RF64 output gates open; both subsequently
completed and passed the final independent review below.

Independent review `performance-hardening-independent-review-20260929-02`
also passed the historical-baseline supplement (source turn
`01a0ec26-dc05-7472-b00e-95c02dccaa4c`): its TEMP reconstruction called the actual
`freeze(historical=True)`, rebuilt native release, reproduced the frozen encoded
bytes and checked exact libFLAC PCM. The unchanged supplied proof is archived as
`validation/evidence/hardening-review/baseline-reconstruction.json`. Its historical
`continue` status was superseded by the final review below.

Final local audit: `validation/evidence/hardening-final.json` asserts all required
report counts/statuses, the unchanged production source hashes, the same timed
and validated candidate CLI hash, the real output's file size and RF64 header,
and records hashes of the supporting evidence. The complete result passed
final independent review; no new codec feature is part of this phase.

Final request `performance-hardening-final-20260929-04`, source turn
`01a0ec2f-2930-7543-85e9-b430d3576fb0`, was confirmed received at 09:12:22 UTC
(reviewer turn `01a0ec6f-c072-72e0-b0b5-5455606da00d`). Final review
`performance-hardening-independent-review-20260929-final` returned `passed`,
with no blocking findings, from reviewer turn `01a0ec72-08c8-7771-a2db-d9c7c5b2f4b6`.
It checked all 21 production-file, 20 evidence and 8 validation-source hashes,
inspected the physical RF64 fields, and independently compared every one of the
5,529,600,000 decoded libFLAC PCM bytes against the retained RF64, including EOF.
FFmpeg's full-stream digest also matched. The unchanged proof is archived at
`validation/evidence/hardening-review/final.json`. All agreed local gates and
the final independent review are complete; the continuous goal can be closed.

## Executed evidence

- Durable independent reports: [validation/evidence](../validation/evidence/README.md).
- Final command logs: `validation/results/final/`; native linking encountered a running executable lock during corpus execution, then succeeded in isolated `_build/final-acceptance`.
- Native release performance: [measured report](PERFORMANCE-EVIDENCE.md). A 300-second 48 kHz stereo 24-bit generated stream verified in median 2.656305 seconds, with 9,400,320 bytes maximum working set and 25,037 retained compressed bytes.
- Browser: `validation/results/browser/backend-comparison.json`, separate JS/wasm-gc desktop/mobile screenshots and actual exported WAV comparisons. On the measured high-rate file, worker decoding left the page timer's maximum observed gap at 22.1 ms (JS) / 16.6 ms (wasm-gc).

## Concrete boundaries

The default compressed/metadata cap is 32 MiB; raise it through `Decoder::new(max_buffer_bytes=...)` or CLI `--max-buffer`. The valid 87.3 MB large-metadata corpus case passed with 128 MiB; its default-limit error was also observed. Whole-file convenience APIs collect output; the streaming API and CLI discard consumed frames. Global MD5 is established only at complete link end; direct SEEKTABLE excerpts report `FrameCrcOnly`.

The browser preview caps input at 64 MiB and output at 32 million channel samples. It plays a uniform-format AudioBuffer, supports same-format Ogg chains, and explicitly diagnoses changing formats or unsupported Web Audio rates. The library supports those frame property changes. Playback uses Float32/device resampling; WAV export retains original integer precision. Ogg sample seeking is sequential; native FLAC offers indexed and direct SEEKTABLE access.

CI configuration is prepared and its local commands have run; remote CI/publication has not run. All work remains local, with no commit, remote repository creation, push, PR or deployment.

## High-effort optimization contract (2026-09-29, independently passed)

Assignment `high-effort-optimization-20260929` starts from the independently accepted hardening version: CLI SHA256 `179b27506f7bc226750fe7efdddd4653d4df8c9f689b98a7787252c3a84e69fe`, encoder_frame.mbt SHA256 `509361274de453e812649cf9331a85898d177b76f7e81761be2d34f208ea273b`. Reduce measured high-effort core encoding time while preserving the complete candidate search, exact costs and tie order, output bytes, API, valid inputs and bounded memory. Profile Rice statistics, merging, decisions and allocation before selecting changes. No heuristic quality reduction, new format/UI or remote action. Historical evidence remains unchanged.

- [x] Freeze source/binary/input identities and obtain detailed current profiling.
- [x] Implement exact search optimization with exhaustive cost/tie/ownership regressions.
- [x] Measure core and CLI with at least one warmup and six paired, balanced alternating rounds; rotate libFLAC position. Calibrate identical fixed core batches, exclude I/O, use long continuous CLI recordings/noise, cover 16/24/32-bit, multichannel, speech, silence and maximum blocks. Run controlled benchmarks without parallel builds/stress.
- [x] Preserve raw timings, median/MAD, paired differences, fixed-set totals, worst regression, size/throughput/peak memory. Demonstrate repeatable search improvement exceeding variation.
- [x] Compare complete baseline/candidate bytes and independent libFLAC/FFmpeg PCM/MD5/CRC; execute native/JS/wasm-gc plus Windows/WSL2 checks and affected bounded streaming/max-block memory cases.
- [x] Update results and limitations, freeze the candidate and submit one source-turn-deduplicated independent review request; receipt verified.
- [x] Independent verdict passed; no confirmed blocking defects remain.

Local gates passed: core fixed-set median sum 9.997083 → 4.833922 s (51.65% reduction); CLI 105.016845 → 50.633253 s (51.79%). Every paired set total improves at all six round indices and all complete baseline/candidate streams remain byte-identical. Windows/WSL three-backend tests are 103/103 each; independent reference and scoped streaming memory gates passed. The archived-source baseline was rebuilt and independently decoded; fresh-cache reconstruction also preserves existing evidence. See [detailed measurements and limitations](PERFORMANCE.md), `effort8-final.json` and `effort8-progress.json`. The native FFmpeg large-frame input limitation is explicitly isolated and validated using unchanged-frame Ogg transport, with the failed initial core run preserved. The frozen candidate passed paired independent review.

Review request `high-effort-optimization-20260929-review-01` for source turn `01a0ec8a-70f5-72a2-b16d-6d6e319a15fa` was received in reviewer turn `01a0ecc6-9894-7c20-b49f-a5af29d69dff` (2026-09-29T10:47:13+00:00). The reviewer verified source completion at 10:48:26.059Z and subsequently passed the frozen candidate.

Final independent review `high-effort-optimization-20260929-independent-01` passed with no blocking findings. Original evidence is archived byte-for-byte under `validation/evidence/effort8-review/`, with original locations and SHA256 in `archive-index.json`. The reviewer independently recomputed all timing statistics; checked 173,226 mathematical selections and 24,480 CLZ thresholds; ran 512 extra shapes with the plan oracle on all three backends (6/6 targeted tests each); built a fresh native release; and confirmed 75 new PCM cases are byte-identical across accepted baseline, submitted candidate and fresh build, with independent PCM/CRC/MD5. The unchanged-frame FFmpeg transport was independently unpacked and 106 Ogg pages checked. Existing Windows/WSL logs and identities were audited; the reviewer did not rerun the full controlled benchmarks, WSL suite or old hour-scale campaign. All declared local gates and the independent-review gate are complete.

## Speed-first encoder contract (2026-09-29, independently passed)

Assignment `speed-first-encoder-20260929` is separately authorized after the exact effort-8 optimization passed. Freeze CLI `e6817e77aafaa124a30d4e75b9a5f73beca10f0b0da967ddcc2e97c3397fe743` and encoder_frame `6cc097f28ec2207864709a0de037ab7eb5cebcf8c7efb81702490985365ce2c5` as the new baseline. The user now prioritizes speed and permits slightly larger FLAC: search candidates/strategy may change and old/new bitstreams need not match. Integer PCM must remain completely lossless; valid input domain, format/integrity, API, stream ownership and bounded memory remain required. Pure MoonBit core, local delivery only, no unrelated UI/format changes or remote operations.

- [x] Freeze all source/build/input identities and prior evidence; profile predictor/LPC, Rice/statistics/partitioning, writer, MD5/packing and CLI. Inspect actual native C compiler optimization and generated-array/RC/bounds/allocation costs.
- [x] Implement substantial search selection and justified exact savings. Measure strategy variants, retaining every regression; no production double-encoding with the full baseline as a hidden quality guard.
- [x] Size gates on the unchanged original twelve-case CLI set AND a separately selected held-out corpus: each set total full-file bytes <= baseline*1.01, each case <= baseline*1.03. Report payload/full-file/PCM proportions. These are empirical budgets, not guarantees for all possible input. Adjust strategies when a class exceeds budget.
- [x] Seek <=10x libFLAC CLI elapsed time on the same fixed set (approximately >=4.4x improvement over the accepted 43.92x). Continue profiling/strategy/controlled validation if the first candidate falls short; any genuine quality-budget boundary needs measured Pareto/hotspot evidence and independent review, not an unsupported completion claim.
- [x] Core/CLI separate, pinned single CPU, at least one warmup and six balanced paired rounds with libFLAC position rotation; identical old input/parameters and unchanged reference comparison, plus comparable-compression reference settings. Long continuous recordings/holdout and dedicated silence/65535 groups, all raw timings/median/MAD/paired/worst/size/memory retained; no concurrent builds/stress during controlled timing.
- [x] Independent libFLAC/FFmpeg full integer PCM/MD5/CRC, cross-backend determinism and API/boundary/forced/streaming/finish/ownership and affected memory checks; actual Windows/WSL execution. Preserve old golden histories and explain strategy differences. Known maximum-frame FFmpeg native-input limitation uses the explicitly audited original-frame Ogg transport with raw outcomes retained.
- [x] Freeze complete local delivery and audit the local evidence.
- [x] Submit a unique source-turn review request and confirm receipt; send one source-completed event if needed.
- [x] Obtain the independent verdict and address confirmed findings.

Local final audit: `validation/evidence/speed-first-final.json`. The unchanged twelve-case CLI median sum is 49.673120 -> 7.889482 seconds (6.30x faster; 6.83x same-round libFLAC CLI time); core is 5.149403 -> 0.967128 seconds (5.32x). Original full-file size +0.016%, first holdout +0.1194%, fresh second holdout +0.0609%, all individual cases <=+3%. The first holdout rejection and the 32768 native-FFmpeg failure remain preserved. Windows/WSL each pass 108/108 on three backends, final CLI independent matrices and scoped memory pass. [Full executed evidence](SPEED-FIRST-EVIDENCE.md) distinguishes the unchanged main reference from comparable-size libFLAC settings and records limitations. Independent review remains the final open gate.

Review request `speed-first-encoder-20260929-review-01`, source turn `01a0ecdc-c112-7ae2-b065-63890a85f445`, was confirmed received in reviewer turn `01a0ed36-26ff-7373-ac18-e75ba84d96ca`, receipt `fco_01a0ed36-3b12-7622-8d56-07aed47c644c`. The reviewer was explicitly instructed to wait for real source-turn completion. The continuous goal remains active pending the independent verdict.

## Independent-review fixes (revision 4, local gates passed; review pending)

Review `speed-first-encoder-20260929-independent-01` confirmed two P2 findings: LPC proxy truncation caused five 37-sample inputs to exceed the empirical per-case size goal, and the generated report divided core time by reference CLI time. Preserve the complete review and original failures under `validation/evidence/speed-first-review/`. Actual blocks <=256 now use the original complete LPC model order; larger-block policy and MD5 remain unchanged. The core report compares baseline/candidate core time only. No new API or feature scope.

- [x] Five reported cases restore exact accepted-baseline bytes; 145 independent cases and nine permanent golden regressions pass.
- [x] Windows/WSL three-backend gates, independent CLI matrices, retained 31-case quality sets and affected short-block memory pass on revision4.
- [x] Recompute controlled original12 CLI/core measurements from the final artifact, preserving all historical runs.
- [x] Regenerate audited documentation and submit a new source-turn request with confirmed receipt.
- [x] Obtain the final independent verdict.

All original12 timing inputs have actual blocks longer than256 (including tails). Their unchanged byte output is checked again, but current speed claims still use fresh revision4 measurements. Previous17/32768/reference measurements are retained as explicitly labelled revision3 history. The two earlier holdout sets are now retained regression sets, not newly unseen revision4 data.

Revision4 local audit passed: `speed-first-revision4-final.json` verifies current artifact `ef39c3f2a1f574abf684d3a506d75366d492f3afbdebc4d5231405d90b10c1ff`, same-round CLI ratio6.843x and baseline speedup6.080x; valid core speedup5.337x. Nine permanent golden tests and all145 review/neighbor cases pass. All31 retained quality outputs remain byte-identical to revision3. An inherited revision3 holdout-provenance flag was corrected to mark both sets already seen; the original identity was archived, and no source/artifact/input hashes changed.

Revision4 request `speed-first-encoder-20260929-review-02`, source `01a0ed37-2dc5-7e62-ab1b-eb70941e2001`, was confirmed received in reviewer turn `01a0ed60-d49f-7cc0-bc37-6b44bbe56bd2`, receipt `fco_01a0ed60-e29e-78a3-865d-338722ce5995`. Source completion is still pending at send time; reviewer instructed to wait for real completion.


## Independent-review fix: nonzero pulse backgrounds (revision 7)

Review `speed-first-encoder-20260929-independent-02` accepted the previous two fixes and found a further quality failure: 4096-sample blocks with small nonzero backgrounds and large pulses needed partition order 10, which the zero-count cap excluded. The two full files grew 21.715% and 25.995% although PCM remained exact. Original review scripts, logs and reports are archived under `validation/evidence/speed-first-review/independent-02/`; permanent fixtures preserve both raw inputs and the accepted/bad FLAC files.

Revision 7 replaces that heuristic with conservative per-partition Rice/escape lower bounds. Only partition orders proven unable to improve the exact coarse result are omitted; every evaluated predictor retains the full planner's optimum and tie order. LPC shortlisting remains a separate heuristic. Irregular blocks and blocks whose winning fixed predictor needs partitions of at most eight samples use the original complete LPC model pool. Public API, supported PCM domain and efforts 0–7 are unchanged.

The expanded 32-case pulse matrix was frozen before candidate encoding. Revision 5 repaired the two reported files but failed two 8192+257 cases; revision 6 repaired the long frame but still missed the tail's LPC model. Both failed reports remain preserved. Revision 7 passes all 32 cases, with aggregate size +0.001945%, and passes all 145 earlier review/neighbor cases. The 31 retained quality streams also pass independent libFLAC/FFmpeg PCM/CRC/MD5 checks. All sets are now regression gates, not unseen validation data. See `speed-first-candidate-revision7.json` for the frozen artifact.

- [x] Archive review, preserve failures and reproduce both original inputs without TEMP dependencies.
- [x] Exact partition bound proof, permanent planner regressions, 32 pulse and 145 earlier cases, 31 retained quality cases.
- [x] Complete final-source Windows/WSL and affected streaming-memory gates.
- [x] Complete controlled original twelve CLI/core rounds on the actual revision 7 artifact.
- [x] Audit local evidence and regenerate the measured report.
- [x] Send a new unique review request and confirm receipt.
- [x] Obtain the final independent verdict.


Revision 7 final local audit passed (`speed-first-revision7-final.json`). Windows and WSL native/JS/wasm-gc each121/121 plus check/release builds; Windows CLI contracts,328 libFLAC/327 FFmpeg/137 forced/828 cross; WSL24 CLI/828 cross. All32 pulse fixtures additionally pass native/JS/wasm-gc byte identity and independent PCM/CRC/Python MD5 (96 combinations). The two original review files exactly regain baseline24,177/20,231 bytes. Retained145 short and31 quality cases pass. The maximum affected2→20s memory increase is1,011,712 bytes against8MiB; official libFLAC analysis confirms the pulse workload actually uses partition order13.

Current controlled original12 results: CLI49.101317→10.169248s (4.828x), same-round libFLAC1.167634s (candidate/reference8.709x); core4.957022→1.376529s (3.601x, MoonFLAC core comparison only). Full-file aggregate22,809,925→22,813,547 bytes (+0.015879%); all declared sets pass1%/3% gates. Each has one warmup and six balanced pinned-CPU rounds; no build/test/stress overlapped timing. Existing17/32768/reference timing tables remain explicitly revision3 history. Previous hour-scale and unchanged MD5/transport proofs are retained rather than rerun or relabelled. The remaining gate is paired independent review.

Revision7 request `speed-first-encoder-20260929-review-03`, source `01a0ed61-7562-7763-9522-68972c3ffe5c`, was confirmed received in reviewer turn `01a0ed97-fe1d-7531-b76e-f95197caa376`, receipt `fco_01a0ed97-fe67-73d2-83eb-422190048f11`. At send time the source turn was still running; it completed at14:36:46.920Z and the final independent verdict is recorded below.


## Final speed-first acceptance

Independent review `speed-first-encoder-20260929-independent-03` passed for source turn `01a0ed61-7562-7763-9522-68972c3ffe5c`, closing short-block quality, mixed timing ratio and pulse-train long-block quality. Original evidence is preserved byte-for-byte under `validation/evidence/speed-first-review/independent-03/` with an archive index. The reviewer actually ran a fresh native build,21 targeted tests per backend,37 baseline/submitted/fresh integer PCM/CRC/MD5 comparisons and32 additional complete-plan mathematical comparisons; all7 original failures regain accepted-baseline bytes. The reviewer recomputed the preserved six-round timing data, and audited the current Windows/WSL, memory and cross-backend evidence; those full campaigns were not redundantly rerun during review.

A final completion audit rechecked all18 current source hashes, CLI/core binaries and18 indexed evidence files against the reviewed delivery and confirmed the independent performance values equal the local audit. All authorized requirements and all confirmed findings are complete. `validation/evidence/speed-first-completion.json` is the final acceptance record; prior local audit statuses remain immutable historical records. Limits remain empirical quality/speed bounds, heuristic LPC selection, Windows plus same-host WSL2, and no remote CI/macOS/independent Linux hardware claim. All delivery remains local, without commit/amend/push/publication/deployment.


## Faster than libFLAC contract (2026-09-29, active)

Assignment `faster-than-libflac-20260929` supersedes the prior CLI<=10x reference target: both single-thread CLI and true buffer-to-buffer core must beat normally optimized official libFLAC-8 under preregistered conditions. Revision7 is frozen as the performance baseline (`faster-than-libflac-baseline.json`, CLI71be364c…41a9/core48697d6f…671f). Its old8.709x reference elapsed time is the starting gap, not success. Quality stays anchored to accepted e6817e77…743, never a moving per-round baseline: each declared set full-file total<=1.01x and each case<=1.03x. Preserve all31/145/32 regression members and the7 original failures.

Scope: profile actual revision7, implement evidence-driven structural search/statistics/data-path improvements in pure MoonBit, and validate complete integer PCM, supported domains, public API, streaming state/ownership, full MD5/CRC and bounded memory. Test-only native libFLAC harnesses are allowed; product codec delegation to C/libFLAC/FFmpeg is not. No unrelated features, remote changes, commits or publication.

- [x] Freeze revision7 source/artifacts and unchanged original12 manifests; retain all historical accepted evidence.
- [x] Profile actual frozen revision7 with bound source/instrumented/build hashes; distinguish event/inclusive/exclusive observations from uncontended timing. Record adaptive-plan scans/refinement, residual/full-pool/shortlist/backfill work and actual native allocation/copy/compiler evidence. /O2 /MT was already enabled.
- [x] Prepare true native libFLAC buffer-to-buffer core comparison. Prepare PCM outside timing; time equivalent full encoder initialization, input processing, output buffer population, metadata/MD5/CRC, finish and encoder lifecycle. Exclude fileIO, external validation and final returned-output release equally. Retain actual compiler/library/harness identities and normal SIMD/optimization settings.
- [x] Preregister a new representative long music/speech/noise/silence/maximum-block set before new candidate results, with source attribution and exact input/parameter identities. Retain original12 actual CLI cases separately.
- [ ] Implement structural improvements from actual hotspots; preserve exact partition optimum/tie for evaluated predictors and all quality regressions. No arbitrary cap or speculative full-baseline double encode guard.
- [ ] Independent libFLAC/FFmpeg integerPCM/CRC/MD5, three backends, affected stream/state/ownership and memory gates on the actual frozen candidate. Reuse unchanged historical component evidence without claiming reruns.
- [ ] Two independent uncontended measurement blocks, each>=one warmup+10 balanced paired rounds, fixed single CPU, same PCM/format/block parameters and same calibrated short-core batch for both codecs. Keep raw observations, per-case and set median/MAD/paired/worst results and all failures. Aggregate victory in both CLI and truecore on original and long sets must exceed measured variability; report per-case losses explicitly.
- [ ] Measure libFLAC-0..8 reasonable fixed speed/size curve and additionally compare the fastest reference meeting the same quality budget. Do not select only slow exhaustive reference, disable SIMD, skip integrity or compare different timing boundaries.
- [ ] Bind actual source/build/input identities, archive final independent review and close the continuous goal only after real measured victory and review. Intermediate deliveries must state continue and quantify the remaining gap.

The conclusion will be restricted to the preregistered inputs/machine/conditions. No universal all-input/all-machine superiority claim is possible. A concrete toolchain obstacle requires reproducible evidence and continued investigation, not redefining victory.


### Stage1: measurement repair and exact data-path candidates (continue)

Candidate4 CLI0246cc085b17a748e0382ce87c07bf0233c35bbd04d9921c72891a0e51d8f07d is bound to `faster-than-libflac-candidate4.json`; the complete buildable101-file snapshot is `_build/faster-than-libflac/candidate4-source`, indexed by `faster-than-libflac-candidate4-source.json`. Current Windows check/test passes128/128 per backend, format passes, encoder CLI contracts pass, and31/145/32 fixed-anchor regression sets pass. Pure-exact candidate transformations preserve observed revision7 bytes. This is a partial development stage, not final candidate acceptance; current full WSL/memory/cross-corpus gates remain to be completed for the eventual winning artifact.

Actual same-round original12 CLI diagnostic: revision7 10.019908300s, candidate5.744387700s, libFLAC1.116732100s; candidate/reference5.143926373x. Genuine prepared-buffer core: revision7 1.320895994s, candidate0.732397953s, libFLAC0.094417071s; candidate/reference7.757050125x. Every measured category still loses to libFLAC. These are one-round preliminary blocks with `acceptance_eligible:false`, not the final10-round/two-block gate. Original quality bytes remain22,809,925→22,813,547. The long8-member,360-second set is frozen and its e681/revision7 reference outputs are independently verified; it has not been retuned or used to claim candidate victory.

Earlier profile source inventories had an absolute-path filtering bug. Original reports were retained with explicitly post-run inventory supplements; a freshly named corrected revision7 coarse profile captures77 original/78 instrumented source hashes before build and verifies afterward. Test-only native libFLAC harness uses the official1.5 DLL, explicitone thread, normal hardware dispatch, fullnew/init/process/finish/delete and owned-buffer work inside timing, with outputrelease/IO/verification outside just like MoonBit. Three smoke modes and negative identity checks validate tooling, not speed. Next work targets stronger proven partition bounds and remaining LPC/data-path costs. Goal status remains active/continue until actual superiority and final independent review.

Stage1 request `faster-than-libflac-20260929-review-stage1`, source `01a0edb2-97e9-7212-95ec-7f11c973e167`, was confirmed received in reviewer turn `01a0edef-77d4-7990-ab4e-3515e1e94e4c`, receipt `fco_01a0edef-8e94-7f10-95fe-e0fa36820f8a`. This is explicitly a continue-stage review, not a final victory claim. The reviewer was instructed to wait for actual source-turn completion; the continuous goal stays active.


Stage1 independent review `faster-than-libflac-20260929-independent-stage1` passed the implementation stage and reference core harness, but explicitly left the final goal unachieved. Fresh three-backend targeted tests21/21,61 additional baseline/submitted/fresh CLI cases, stream-ownership tests, and100 reference-harness valid cases plus6 invalid inputs passed. The reviewer confirmed one P2 in cross-block DLL identity comparison. The combiner now requires equal `libflac_dll`, `core_runtime_dll` for core, and `independent_tools`; the original synthetic mismatch is rejected, an identical-identity positive case remains accepted, and16 helper/negative checks pass without launching encoders. Original records are archived under `validation/evidence/faster-than-libflac-review/independent-stage1/`; resolution is `faster-than-libflac-combiner-fix-proof.json`. Production C4 can now be unfrozen for continued optimization; no final victory is implied.

### Stage4: C34 integration (continue, 2026-09-30)

At stage4 the root runtime became C34. Historical C10/C24 statements below and in earlier performance sections describe those stages. C34 combines the reviewed C24 arithmetic/search changes with the UInt64 word writer, persistent per-encoder planning scratch and full-container PCM loads. No new predictor or partition cap is introduced. Source and artifact identities, promotion backups and actual root checks are indexed by `validation/evidence/faster-than-libflac-stage4.json`.

Actual root format, check, test and release builds pass on native, JavaScript and wasm-gc: 169/169 tests each. Both freshly built native CLI contract suites pass. The frozen composition passes all 220 outputs from the retained 31/32/145 sets and original12 with exact C10 bytes. Fresh root and frozen generated C match after removing only physical `#line` directives; Clang executable code/data match, with differing timestamp fields recorded rather than treating their raw hashes as equal.

Frozen long8 (360 seconds) passes independent libFLAC/FFmpeg PCM and integrity checks, with matching CLI/core output bytes. Its 50,641,622 bytes remain within the fixed e681 budget (50,640,556 bytes). Four affected memory cases compare explicit C24/C34 artifacts: C34 peak working sets are 12,849,152 and 12,754,944 bytes for 2/20-second stereo streams, and 26,177,536 and 26,206,208 bytes for 5/60-second 8-channel, 32-bit, maximum-block streams. These are bounded observations for these cases, not a universal RSS guarantee or a replacement for final long-duration stress.

Four balanced engineering rounds on original12 give C34/C24 ratios 0.902197 for genuine core (common batch16) and 0.871984 for CLI. Fresh root one-round same-scope diagnostics still lose to normal libFLAC-8: CLI 1.843182 times and core 2.235517 times reference time. Both are explicitly ineligible for final acceptance. The two independent ten-round winning blocks on original12/long8, qualifying libFLAC0–8 curve, final-current cross-system and long stress, and final independent review remain open. The persistent goal stays active.

Independent stage4 review subsequently passed with no confirmed findings. It ran 148 additional CLI cases against C24, submitted Clang and fresh MSVC output with libFLAC integer PCM/MD5/CRC checks; 146 nonmaximum-block cases also passed FFmpeg. Added writer, scratch-reuse and PCM boundary/error tests passed. Saved long8 and memory outputs were independently revalidated; the two maximal-block long cases used lossless Ogg transport for FFmpeg with unchanged frame bytes verified. Reports are archived under `validation/evidence/faster-than-libflac-review/independent-stage4/`. This accepts the C34 implementation stage, not the still-unmet performance goal.

### Stage2: C10 integration (continue, 2026-09-30)

The local project now contains C10. Its exact changes include leaf-boundary quotient prefixes, a proven depth lower bound with finer-tree reconstruction when necessary, UInt32 folded residual storage with Int64 sums, specialized fixed predictors, preserved-order LPC loop interchange, MD5 feed/round optimization and CRC tables. Guarded covariance ranking applies to the existing regular-block shortlist. Irregular effort8 blocks above256 samples use stratified integer Rice-cost ranking, including every edge sample around warm-ups; four fully legal finalists still receive exact full partition planning. This ranking is a quality-tested heuristic, not a bound on unobserved residuals. Short blocks, deep-partition fallback and efforts0–7 retain their existing search policy.

Fresh checks in the actual project directory pass format, check/test/release builds on native/JS/wasm-gc, with150/150 tests each. The newly built native CLI passes `cmd/test_cli.py`, including custom layouts, zero/partial masks, RF64 and cross-link cropping. The isolated source and promoted runtime hashes are bound in `faster-than-libflac-candidate10-root-integration.json`. The31/32/145 independent quality sets pass. The frozen long8 set additionally passes libFLAC/FFmpeg PCM, CRC/MD5 and matching CLI/core output bytes using the Clang AVX2 artifacts:50,640,556 baseline bytes versus50,641,622 candidate bytes (1.0000210503x), with every case within1.03x.

Uncontended original12 diagnostics, one paired round each, are **not acceptance-eligible**:

| Candidate and timing boundary | Candidate / normal libFLAC-8 |
| --- | ---: |
| C9 Clang AVX2, genuine core | 4.110580x |
| C10 MSVC, genuine core | 4.599548x |
| C10 Clang AVX2, genuine core | 3.614815x |
| C10 Clang AVX2, CLI | 2.753215x |

These separate diagnostic blocks are not a paired compiler speedup claim. Clang compiles unchanged MoonBit-generated C with `/O2`, `/MT`, `-ffp-contract=off`, and the original native support/runtime libraries and MSVC linker. AVX2 builds explicitly require the selected Haswell-compatible feature set; the default builds retain baseline x86-64. Neither product codec delegation nor reference SIMD disabling is involved. Original inputs and the e681 quality anchor remain unchanged.

Failed or neutral histogram, moment-bound, covariance and output-buffer experiments remain recorded. In particular, the initial analytical irregular ranking failed two pulse cases; it was not promoted. C11 exact-Double and C12 unchecked-private-index variants remain isolated experiments, outside this delivered C10 stage. Full repeated two-block victory, fastest qualifying libFLAC0–8 comparisons, and final-candidate cross-system/stress acceptance remain outstanding. The continuous goal stays active.

# Speed-first encoder: executed evidence

Local gates and final paired independent review passed. This follows the accepted exact effort-8 optimization and deliberately permits different FLAC bitstreams while preserving exact PCM.

Baseline CLI: `e6817e77aafaa124a30d4e75b9a5f73beca10f0b0da967ddcc2e97c3397fe743`.
Candidate CLI: `71be364ccf233d29d5a3327ddd78ba7ad076bdb4c6fcc34b11a00d0a482041a9`.

The original twelve inputs and parameters are unchanged. Each mode pins logical CPU 8, runs one warmup and six balanced rounds, rotates the libFLAC position, and independently validates every resulting stream. No build, test, profile or stress job ran concurrently. Desktop/background variation remains possible; raw timings, CPU snapshots and median/MAD are retained. Core timing excludes CLI/file I/O and uses a common calibrated batch. Its table compares only the MoonFLAC baseline and candidate; separate libFLAC CLI observations remain in raw JSON, explicitly outside that comparison.

Revision 7 remeasures only the original twelve CLI and core cases. Holdout17, block32768 and additional libFLAC configuration tables below retain revision3 observations with their original artifact identities; they are not current-artifact timings.

## Original twelve CLI cases

| Case | Baseline seconds ± MAD | Candidate seconds ± MAD | libFLAC CLI seconds | Reduction | File size change | Improved pairs |
|---|---:|---:|---:|---:|---:|---:|
| noise-16-2 | 3.891875 ± 0.194196 | 1.209715 ± 0.016423 | 0.072974 | 68.92% | +0.0000% | 6/6 |
| noise-32-2 | 1.069064 ± 0.011806 | 0.551416 ± 0.006049 | 0.077100 | 48.42% | +0.0000% | 6/6 |
| ar-24-2 | 6.525594 ± 0.488177 | 0.858318 ± 0.012323 | 0.090598 | 86.85% | +0.0101% | 6/6 |
| ar-32-2 | 7.004442 ± 0.166365 | 0.969876 ± 0.014327 | 0.144053 | 86.15% | +0.0000% | 6/6 |
| ar-24-6 | 10.442472 ± 0.393302 | 1.360268 ± 0.034506 | 0.124924 | 86.97% | +0.0013% | 6/6 |
| silence-16-2 | 0.131913 ± 0.008875 | 0.120402 ± 0.010739 | 0.046117 | 8.73% | +0.0000% | 4/6 |
| maximum-block-32-8 | 1.969830 ± 0.013832 | 1.891988 ± 0.007274 | 0.267949 | 3.95% | +0.0000% | 5/6 |
| recording-1 | 3.386282 ± 0.012662 | 0.745680 ± 0.022831 | 0.062559 | 77.98% | +0.1920% | 6/6 |
| recording-28 | 13.773921 ± 0.148859 | 2.136351 ± 0.005714 | 0.129184 | 84.49% | +0.0627% | 6/6 |
| recording-39 | 0.506794 ± 0.005822 | 0.163372 ± 0.003803 | 0.054126 | 67.76% | +0.2335% | 6/6 |
| recording-60 | 0.202935 ± 0.002595 | 0.079816 ± 0.003020 | 0.047956 | 60.67% | +0.1140% | 6/6 |
| speech-voices | 0.196193 ± 0.002368 | 0.082047 ± 0.005950 | 0.050094 | 58.18% | +0.1598% | 6/6 |

Sum of case medians: **49.101317 → 10.169248 s**, 4.828× faster; libFLAC CLI sum 1.167634 s. Candidate/reference elapsed-time ratio: 8.709×.
Full-file size: 22,809,925 → 22,813,547 bytes (+0.0159%). All cases remain within +3%; aggregate remains within +1%.
Six paired set differences (baseline minus candidate, seconds): 39.463577, 43.889052, 40.426441, 36.979658, 39.511738, 38.843969.
Source report: `validation/evidence/speed-first-revision7-cli-benchmark.json`. These totals sum separately measured cases; they are not a single simultaneous suite run.

## Original twelve core cases

| Case | Baseline core seconds ± MAD | Candidate core seconds ± MAD | Reduction | File size change | Improved pairs |
|---|---:|---:|---:|---:|---:|
| noise-16-2 | 0.344929 ± 0.000529 | 0.121695 ± 0.000234 | 64.72% | +0.0000% | 6/6 |
| noise-32-2 | 0.100648 ± 0.000917 | 0.045842 ± 0.000343 | 54.45% | +0.0000% | 6/6 |
| ar-24-2 | 0.504318 ± 0.012392 | 0.101229 ± 0.002834 | 79.93% | +0.0491% | 6/6 |
| ar-32-2 | 0.605907 ± 0.007585 | 0.109698 ± 0.001301 | 81.90% | +0.0000% | 6/6 |
| ar-24-6 | 0.876063 ± 0.009253 | 0.152339 ± 0.000909 | 82.61% | +0.0038% | 6/6 |
| silence-16-2 | 0.006181 ± 0.000089 | 0.004372 ± 0.000037 | 29.28% | +0.0000% | 6/6 |
| maximum-block-32-8 | 0.484275 ± 0.002481 | 0.459089 ± 0.000996 | 5.20% | +0.0000% | 6/6 |
| recording-1 | 0.426551 ± 0.000895 | 0.102050 ± 0.000263 | 76.08% | +0.1556% | 6/6 |
| recording-28 | 1.444433 ± 0.012194 | 0.236615 ± 0.002148 | 83.62% | +0.0582% | 6/6 |
| recording-39 | 0.007531 ± 0.000029 | 0.005266 ± 0.000127 | 30.08% | +0.0000% | 6/6 |
| recording-60 | 0.001963 ± 0.000018 | 0.001467 ± 0.000025 | 25.28% | +0.0000% | 6/6 |
| speech-voices | 0.154223 ± 0.000474 | 0.036868 ± 0.000304 | 76.09% | +0.1598% | 6/6 |

Sum of case medians: **4.957022 → 1.376529 s**, 3.601× faster for MoonFLAC core encoding. Separate libFLAC CLI observations are retained in the raw report and are not directly comparable.
Full-file size: 3,775,099 → 3,775,569 bytes (+0.0125%). All cases remain within +3%; aggregate remains within +1%.
Six paired set differences (baseline minus candidate, seconds): 3.619900, 3.549108, 3.603862, 3.565889, 3.564422, 3.761067.
Source report: `validation/evidence/speed-first-revision7-core-benchmark.json`. These totals sum separately measured cases; they are not a single simultaneous suite run.

## First holdout, retained after diagnosis — historical revision3

Historical observations: the candidate in this table is revision3. Current-artifact correctness and size gates are separate; no revision7 timing is inferred from this table.

| Case | Baseline seconds ± MAD | Candidate seconds ± MAD | libFLAC CLI seconds | Reduction | File size change | Improved pairs |
|---|---:|---:|---:|---:|---:|---:|
| holdout-subset-11 | 1.924775 ± 0.003459 | 0.351146 ± 0.002418 | 0.053841 | 81.76% | +0.1541% | 6/6 |
| holdout-subset-17 | 1.998160 ± 0.041313 | 0.346499 ± 0.018967 | 0.057199 | 82.66% | +0.1563% | 6/6 |
| holdout-subset-24 | 1.927345 ± 0.006344 | 0.341521 ± 0.004399 | 0.066383 | 82.28% | +0.2282% | 6/6 |
| holdout-subset-47 | 1.990469 ± 0.007306 | 0.334243 ± 0.007611 | 0.055655 | 83.21% | +0.2388% | 6/6 |
| holdout-subset-56 | 1.924593 ± 0.056722 | 0.325133 ± 0.013598 | 0.058672 | 83.11% | +0.2917% | 6/6 |
| holdout-subset-64 | 0.358819 ± 0.006785 | 0.102432 ± 0.000811 | 0.047354 | 71.45% | +0.2476% | 6/6 |
| holdout-uncommon-05 | 2.387037 ± 0.017293 | 0.407270 ± 0.015409 | 0.078114 | 82.94% | +0.0703% | 6/6 |
| holdout-uncommon-08 | 1.285315 ± 0.008271 | 0.222911 ± 0.004783 | 0.053972 | 82.66% | +0.1287% | 6/6 |
| holdout-uncommon-09 | 0.294296 ± 0.003297 | 0.094701 ± 0.001970 | 0.044311 | 67.82% | +0.1012% | 6/6 |
| holdout-generated-silence | 0.042491 ± 0.001318 | 0.039765 ± 0.001202 | 0.037707 | 6.42% | +0.0000% | 5/6 |
| holdout-generated-nonstationary | 1.029092 ± 0.011330 | 0.342750 ± 0.014556 | 0.054110 | 66.69% | +0.0000% | 6/6 |
| holdout-generated-impulses | 0.531999 ± 0.002866 | 0.227952 ± 0.003971 | 0.051902 | 57.15% | +0.0112% | 6/6 |
| holdout-generated-correlated | 1.632509 ± 0.018691 | 0.298656 ± 0.002832 | 0.053630 | 81.71% | +0.3250% | 6/6 |
| holdout-generated-ramp-reversals | 2.340794 ± 0.018962 | 0.450832 ± 0.006767 | 0.066767 | 80.74% | +0.0000% | 6/6 |
| holdout-generated-maximum-block | 1.382059 ± 0.025877 | 0.322368 ± 0.003104 | 0.071879 | 76.67% | +0.0096% | 6/6 |
| holdout-recording-america-beautiful | 21.257002 ± 1.098526 | 2.592894 ± 0.025462 | 0.167907 | 87.80% | +0.2357% | 6/6 |
| holdout-recording-anarchy | 15.034595 ± 0.223421 | 1.878605 ± 0.016272 | 0.167793 | 87.50% | +0.1338% | 6/6 |

Sum of case medians: **57.341351 → 8.679680 s**, 6.606× faster; libFLAC CLI sum 1.187198 s. Candidate/reference elapsed-time ratio: 7.311×.
Full-file size: 18,887,413 → 18,909,970 bytes (+0.1194%). All cases remain within +3%; aggregate remains within +1%.
Six paired set differences (baseline minus candidate, seconds): 46.589416, 47.921540, 47.920788, 49.567823, 50.201094, 49.595232.
Source report: `validation/evidence/speed-first-holdout-benchmark.json`. These totals sum separately measured cases; they are not a single simultaneous suite run.

## 32768-sample block comparison — historical revision3

Historical observations: the candidate in this table is revision3. Current-artifact correctness and size gates are separate; no revision7 timing is inferred from this table.

| Case | Baseline seconds ± MAD | Candidate seconds ± MAD | libFLAC CLI seconds | Reduction | File size change | Improved pairs |
|---|---:|---:|---:|---:|---:|---:|
| power-two-block-32-8 | 12.666348 ± 0.919537 | 1.190298 ± 0.017980 | 0.262683 | 90.60% | +0.3822% | 6/6 |

Sum of case medians: **12.666348 → 1.190298 s**, 10.641× faster; libFLAC CLI sum 0.262683 s. Candidate/reference elapsed-time ratio: 4.531×.
Full-file size: 7,431,461 → 7,459,863 bytes (+0.3822%). All cases remain within +3%; aggregate remains within +1%.
Six paired set differences (baseline minus candidate, seconds): 11.317873, 11.486868, 11.098583, 9.688161, 13.181141, 12.911598.
Source report: `validation/evidence/speed-first-block32768-packetized-benchmark.json`. These totals sum separately measured cases; they are not a single simultaneous suite run.

## Comparable-size reference observations — historical revision3

The main comparison above keeps the unchanged libFLAC `-8` settings. Additional reference configurations use one warmup and six rotating rounds. These are separately measured CLI observations, not new paired candidate timings. Nearest size means minimum absolute payload-byte distance; equal lossless PCM does not imply equal encoder search effort.

These reference runs and nearest-payload selections belong to the revision3 candidate/report. They are retained history, not a new matched-size comparison with revision7.

| Configuration | Sum of median seconds | Full-file bytes | Payload bytes |
|---|---:|---:|---:|
| libflac-0 | 0.676524 | 28,267,909 | 28,266,877 |
| libflac-5 | 0.753444 | 22,753,889 | 22,752,857 |
| libflac-8 | 1.122449 | 21,379,246 | 21,378,214 |
| libflac-8-exhaustive | 29.535585 | 19,954,002 | 19,952,970 |

Nearest total payload configurations: libflac-5. Per-case selections and all settings, outputs, timings and ratios are retained in `speed-first-reference-benchmark.json`.

## Correctness, quality and scope

Revision 7 source/artifact identities and required correctness, holdout and memory gates are indexed in `validation/evidence/speed-first-revision7-final.json`.
Windows and WSL2 each pass 121/121 on native, JS and wasm-gc, with check/release builds and Windows format/CLI contracts passed. Final Windows artifact matrices cover 328 libFLAC PCM cases, 327 FFmpeg audio cases, 137 forced representations and 828 cross-backend streams; WSL independently checks 24 CLI combinations and 828 streams.
The current artifact replays all 31 prior holdout streams and verifies 145 review/neighbor cases. See `validation/evidence/speed-first-revision7-quality.json` and `validation/evidence/speed-first-short-revision7.json`. Required short-block byte identity and independent PCM/CRC/MD5 checks are asserted by the finalizer.
Current frozen policy: Exact residual partition optimum via conservative lower-bound refinement from order8; full original LPC pool for blocks<=256, blocks not divisible by256, or winning fixed partitions of<=8 samples; otherwise four fully legal ranked LPC candidates.
The 32 frozen pulse cases pass independent libFLAC PCM, CRC/MD5 and Python hashlib checks. Full-file aggregate: 1,645,398 → 1,645,430 bytes (+0.0019%), within +1% aggregate and +3% per case. Evidence: `validation/evidence/speed-first-pulses-revision7.json`.
The partition-bound proof companion passes 4,066,022 scalar-parameter checks, 4,905 partition checks and 189 warm-up/order checks. These finite checks support the algebraic proof; they do not constitute a universal compression-ratio bound. Evidence: `validation/evidence/partition-bound-proof.json`.
All 32 pulse fixtures also pass JS and wasm-gc with exact native byte identity and independent libFLAC PCM/CRC/MD5 checks: 96 backend/case combinations total. Evidence: `validation/evidence/speed-first-pulses-cross-revision7.json`.
Retained quality set `speed-first-revision3-holdout-gate.json`: 17 cases; full-file aggregate 1.00107246× baseline, within the +1% aggregate and +3% per-case budgets. No newly unseen holdout is claimed.
Retained quality set `speed-first-revision3-holdout2-gate-general-depth.json`: 14 cases; full-file aggregate 1.00036522× baseline, within the +1% aggregate and +3% per-case budgets. No newly unseen holdout is claimed.
Current memory group block 32768, 2 channels/16 bits, durations [2, 20]: peak growth 139,264 bytes, limit 8,388,608 bytes.
Current memory group block 32768, 8 channels/25 bits, durations [2, 20]: peak growth 1,011,712 bytes, limit 8,388,608 bytes.
Current memory group block 65535, 8 channels/32 bits, durations [2, 20]: peak growth 225,280 bytes, limit 8,388,608 bytes.
Current Windows/WSL checks and affected streaming-memory groups are retained separately from historical hour-scale results. Artifact acceptance: `validation/evidence/speed-first-checks-revision7/acceptance.json`; memory: `validation/evidence/speed-first-memory-revision7.json`. These memory observations are not controlled speed measurements.
The earlier failed size gates, reference parser failures and review findings remain historical records; their measurements are not replaced by this revision.
Compression size budgets are empirical for the declared sets, not universal guarantees. WSL2 shares host hardware; remote CI and publication are not claimed.

## Reproduction

Replay the exact retained commands in `validation/evidence/speed-first-revision7-benchmark-commands.json` after preparing the frozen sources, fixture identities and toolchain. Run timing without concurrent build/test/profile/stress jobs.

```sh
python scripts/finalize_speed_first.py --revision 7
python scripts/render_speed_first_report.py --revision 7
```

Evidence-producing commands preserve existing reports. Select fresh paths for independent reproduction.


## Final independent acceptance

Review `speed-first-encoder-20260929-independent-03` passed with no findings. The reviewer built a fresh native release, ran21 targeted tests on each backend, replayed37 independent PCM/CRC/MD5 cases (32 pulse fixtures plus5 old short failures), confirmed submitted/fresh byte identity and restored baseline bytes for all7 original failures, and independently checked32 complete partition plans plus14 higher-order bounds. Timing statistics were recomputed from the retained raw rounds; the reviewer did not rerun the complete timing suite, Windows/WSL campaign or historical hour-scale experiments. All18 source and18 evidence hashes plus2 preserved failures matched.

The original review, logs, scripts, replay fixtures and mathematical evidence are byte-preserved under `validation/evidence/speed-first-review/independent-03/`; `archive-index.json` records original locations and hashes. Final completion is recorded in `validation/evidence/speed-first-completion.json`. The immutable `speed-first-revision7-final.json` retains its pre-review handoff status; the completion record supplies the subsequent independent verdict. No required work remains for this authorized phase.

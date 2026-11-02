# Performance and memory measurements

Current local delivery is C95, with 194 passing tests per backend in both the isolated source and actual project. The faster-than-libFLAC goal remains open. Earlier sections retain measurements of their named historical artifacts; their timings are not reassigned to C95.

Development moved to bounded delivery closeout on 2026-10-01. Current Windows
hour-stream/RF64/stress, Linux three-backend/full828 and browser refreshes pass;
see [the current acceptance table](ACCEPTANCE.md#current-local-delivery-2026-10-01).
Independent functional final review passed; the performance objective remains
unmet. This development round is closed without another micro-candidate loop.
C101's packed property reductions passed correctness but regressed on four of
five screen cases (summed median ratio 1.014565), so it was not promoted. C102's
disk-full-era failure did not recur in a fresh build; its existing 16 focused
tests/backend pass, but it remains unselected without timing or promotion.
No new micro-optimization candidates are planned. The one-round C95/libFLAC-8
ratios 1.708871 core / 1.447868 CLI still fail the speed target; no final two-block
performance acceptance or universal compression-size guarantee is claimed.

Independent stage18 review passed C95: 13 targeted tests/backend, 49 fresh
libFLAC PCM/integrity comparisons (46 also through FFmpeg), and 11,232 shared
guard checks. It verified the selected source, logs, bindings and generated C;
historical full/long/memory campaigns and performance were not repeated. The
52-file archive includes six complete raw/encoded repro sets under
`faster-than-libflac-review/independent-stage18/`. The five stage18-bound documents
are preserved in `stage19-prior-docs/`.

The new 49-input set has aggregate size ratio 1.005270, but six sine cases exceed
the 1.03 per-case comparison; the worst is 1.390501. C83 and C95 outputs match
on every input. This inherited weakness lies outside the declared quality sets;
the reviewer preserved the failing supplemental assertion separately from the
passing PCM checks. Independent checks also confirm the six e681 anchor outputs
are lossless. See [frozen observations](../validation/evidence/supplemental-quality-stage18/README-v2.md).
Measured-set budgets do not bound arbitrary-input compression loss.

## Supplemental ranking diagnosis and Int32 eligibility, stage19

Stage20 review confirmed the unselected C97/C98 evidence and identified one
remaining attribution error in the old supplemental README. Current README,
API, acceptance and performance links now point to `README-v2.md`, which states
the trace's branch ambiguity. The original remains immutable; its numeric
observations and all reproduction inputs are unchanged.

Stage19 independent review passed the reproduction and repair-cost evidence,
with a P3 correction to ranking attribution. The corrected interpretation below
and versioned `faster-than-libflac-stage19-v2.json` preserve the observations;
the original index and bound documents remain archived.

All six frozen e681 anchor streams independently pass PCM/CRC/MD5 checks, so
their size comparisons are valid. Actual Moon tracing finds all 29 anchor-winning
subframe models in the generated pools. Rice diagnostic ranking places every
one first; regular proxy ranking and four-legal admission leave 14 unattempted
at ranks 13–30. The trace does not distinguish covariance ranking from its
sampled-width fallback. In case20, the useful LPC2
model ranks16 while the selected LPC21 ranks2. The former's actual residual MSE
is about397 versus a covariance estimate414514; the latter's actual MSE is24706
versus estimate31206. This is a poor proxy for unwindowed residual quality, not
a violation of the floating-point arithmetic error bound. Instrumented output
bytes remain exactly C95. Existing Rice ranking adds382624 predictor MACs/plane;
that operation count is not a runtime measurement.

### Guarded full Int32 predictor experiments, stage20

C97 uses existing analysis peak metadata, validates a lazy owned Int32 plane,
and requires actual coefficient/dot/residual bounds before using an eight-output
integer predictor. Otherwise the original Double/Int64 route remains unchanged.
Five focused tests per backend and 24 original12 CLI/core outputs pass, including
independent PCM/integrity checks and exact C95 bytes. Actual code emits packed
`VPMULLD`, but retains larger-order reduction/packing and scalar Int64 output
commits. Conversion, repeated guards and mixed-plane storage also remain.

Four balanced engineering rounds give C97/C95 summed median ratios **1.008273**
on the five-case screen and **1.002348** on original12 core. Recording1, speech
and noise16 do not improve in the full block despite their high arithmetic
eligibility. All observations are retained; C97 is unselected, with no CLI
timing, full acceptance or promotion.

C98 changes only guarded output arithmetic: Int32 arithmetic right shift and
subtraction, then sign extension of the final residual. The existing absolute
bound proves no overflow and identical negative rounding. Six focused tests
per backend and all 24 independently verified original12 outputs pass exactly
against C95. Generated code still extracts lanes and performs scalar
`SARX32/SUB32/MOVSXD` stores; the intended packed shift/subtraction did not appear.
C98 stopped at this codegen gate without timing or promotion. Root remains C95;
neither experiment establishes a libFLAC speed win.

### Fused peak-scan experiments, stage21

C99 collects signed extrema during the existing constant/wasted-bit traversal
for LPC-capable calls. Arithmetic-shifting both endpoints before converting to
Double reproduces the old peak bits, including negative floor shifts and values
beyond exact Double integer precision. Low-effort/tiny inputs retain the old
scan; standalone LPC callers retain the generic peak scan. No input mutation
occurs between property collection and use. Constants incur added comparisons.

Sixteen focused tests per backend and 24 independently verified original12
CLI/core outputs pass exactly against C95. Actual code removes the trusted-path
peak scan but reads/writes extrema on the stack every sample. Four balanced core
rounds give C99/C95 **0.992902** on the screen and **1.002819** on original12.
The mixed result does not justify promotion. An initial runner preflight assertion
and a subsequent new-test syntax error occurred before numerical tests; original
attempts and versioned repairs are retained. No production repair was needed.

C100 extracts only the fused scan into a private helper. Sixteen tests/backend
and all 24 independently verified original12 outputs pass. Moon's accepted
`#inline(never)` preserves a helper call in generated C, but final Clang inlines
it into the hot subframe. Per-sample stack traffic remains and a 32-byte tuple
allocation/drop is added. Register-held extrema in the unused standalone helper
are not evidence about executed code. The mechanism failed, so C100 was not
timed. Both candidates remain isolated and unselected; no CLI timing, full
acceptance or root promotion ran. C95 remains the delivered implementation.

C96 is an unselected generic repair experiment: regular shortlisted effort8
blocks use the existing residual Rice ranking, with unused variance collection
disabled. Small/fine-partition full pools, efforts0–7, legal-finalist counting
and backfill remain unchanged. All19 focused tests/backend pass, including the
unchanged old-policy comparison. Own original12 quality/integrity passes, and all
six supplemental files match the e681 anchor byte-for-byte. However, the five-case
native core ratio is **1.336638 C96/C95**, including recording28 at1.916281.
No full12/CLI timing, full acceptance or promotion followed. The root remains C95
with its documented supplemental quality limitation.

The project-relative replay script was executed against both C95 and C96. C95
correctly returns exit1 for six supplemental size failures while all PCM/integrity
checks pass; C96 passes both checks. Reports are retained under
`supplemental-quality-stage18/`. The original reviewer script/assertion, frozen
inputs and encoded references remain unchanged.

A separate count-only C95 run observes actually attempted full LPC models on
12 core-sized inputs and long recording28. With actual sample magnitude M and
coefficient absolute sum A, M*A<=INTMAX proves every Int32 partial dot fits;
M+ceil(M*A/2^shift)<=INTMAX additionally proves residual legality. All observed
dot-eligible models satisfy both guards. Recording1, speech and noise16 have
100% eligible potential MAC work; AR24-2 has14.63%. Recording28 has zero on the
core input and only0.1973% on the long input. All13 instrumented outputs match
fresh frozen C95 and independently verified hashes. These counts justify a
narrow-PCM experiment, not a broad speedup or a recording28 claim. No Int32
kernel has yet been built or measured.

## Selected triangular variance implementation, C95

C95 combines C93's numerically bounded symmetric quadratic evaluation, C94's
caller-proven shared input checks and local views inside the triangular helper.
The helper's coefficient/correlation accesses follow from its validated lengths;
neither array changes while views are live. Product grouping, linear/diagonal
placement and the triangular addition order remain exact relative to C94.
Actual CLI/core code removes bounds-to-panic branches, retains packed coefficient
division and scalar unrolling, and has no inner-loop calls/spills or FMA. View
lifetime handling remains outside the loops; code size increases.

Four balanced original12 rounds measured C95/C83 ratios **0.984459 core** and
**0.975997 CLI**. Six core and four CLI cases are slower and remain in the totals.
These are direct composition measurements, not multiplied component gains.
Both isolated and actual-root tests pass **194/194** on native, JS and wasm-gc,
with default format/API/check/release and both CLI contracts. All 220 independent
cases and long8's 16 CLI/core outputs pass PCM/CRC/MD5 and unchanged e681 size
budgets. Existing short/low-effort byte contracts remain mandatory. No output
changes from C83 were observed on these sets, but the numerical analysis does
not promise general compressed-byte identity.

Only `encoder_lpc.mbt` and seven new WB oracle/test files were promoted, with
before snapshots. Actual-root/frozen generated C agrees after only newline and
physical `#line` normalization; fresh root MSVC binaries and frozen Clang AVX2
binaries remain separately identified. Four affected Clang memory observations
pass: stereo16/block32768 at 2/20 seconds peaks at 12,279,808/12,697,600 bytes;
eight-channel32/block65535 at 5/60 seconds peaks at 26,103,808/26,173,440 bytes.
Growth is 417,792/69,632 bytes, below 8 MiB. This is not universal RSS or final
hour-stress evidence. See `faster-than-libflac/c95-root-integration/`.

Fresh normal-priority CPU8 single-round diagnostics still fail the speed goal:
**1.708871 core** and **1.447868 CLI** times normal libFLAC-8; real-audio subset
ratios are 3.507438 and 1.600463. Candidate/reference totals are
0.158796858/0.092925005 seconds for core and 1.607615300/1.110333100 for CLI in
their respective scopes. Quality and calibration pass; acceptance eligibility
is false. These independent blocks cannot replace the direct C83/C95 comparison.
Final original12/long8 wins, two independent ten-round blocks, current-artifact
cross-system/hour-stress verification and independent final review remain open.

Stage14 independent review accepted C83 and closed the limited C77 guarded-entry
issue. It ran 13 targeted tests/backend, 49 new libFLAC comparisons (46 also with
FFmpeg), three append-state cases on native/JS, and 200 Welch groups with 534,064
signal bit patterns and 200 energy values. Long/memory evidence was checked for
byte identity and bindings; this was not new stress or timing. The byte-exact
24-file archive is `validation/evidence/faster-than-libflac-review/independent-stage14/`.
The original stage14-bound documents are retained in `stage15-prior-docs/`.

Stage15 independently accepted the C84–C87 unselected-experiment evidence with
no findings. It checked 58 index bindings, actual formatted source/log bindings,
original timing observations and the unchanged C83 source. Independent arithmetic
checks covered 2,560 dots, 12,800 residuals and 32,928 history indices. It did not
rerun the unchanged codec acceptance or performance measurements. Its eight-file
archive is `validation/evidence/faster-than-libflac-review/independent-stage15/`;
stage15-bound documents are preserved in `stage16-prior-docs/`.

## Variance and CLI copy experiments, stage16

Independent stage16 review accepted the three unselected experiments with no
findings. It checked 45 bindings, unchanged C83 source and original timing/output
records; an independent 1,960-case variance comparison matched 209 Some results
bit-for-bit and 1,751 None results. No new codec or timing run was performed.
The nine-file archive is `faster-than-libflac-review/independent-stage16/`, and
the exact stage16-bound documents are retained in `stage17-prior-docs/`.

C88 replaces the variance quadratic loop's absolute lag selection with two
ascending ranges and proven-safe local view accesses. Linear terms, individual
multiply grouping, both floating-point addition sequences, coefficient conversion
and final guards remain unchanged. Fourteen focused tests/backend and 24 exact
C83 outputs pass. Actual code removes inner bounds checks and lag selection but
retains scalar products; split setup and code size increase. Its five-case core
ratio was 0.979101, while full12 was 1.000926 with seven slower cases. It remains
unselected; the screen improvement is not claimed as a stable gain.

C89 avoids an owned full-slice copy when the CLI first submits each PCM batch.
Subsequent partial suffix copies and the encoder's accepted-prefix copy remain.
This removes 4*S native payload-copy bytes for S scalars in a successful stream,
a static count rather than measured memory traffic. Actual code skips the first
temporary allocation. Twenty-four exact C83 outputs, six independently decoded
raw/WAV fixtures, two matching error cases and both CLI suites pass. Full12 CLI
ratio 0.999830 is insufficient to select it. Neither experiment changed the root
delivery or ran full acceptance, long validation or final libFLAC comparisons.

C90 computes four independent variance products before applying each original
variance/magnitude update in ascending term order. Fourteen tests/backend and
24 exact C83 outputs pass. Actual descending-lag products use packed multiplication;
ascending-lag products remain scalar with Int32 address calculations. The compiler
packs the two separate accumulators into lanes, with four dependent additions,
without horizontal reduction or FMA. Its five-case core screen is mixed/slower,
so it remains unselected without full12/CLI timing, full acceptance or promotion.

## Numerical analysis and allocation counts, stage17

Independent stage17 review accepted the unselected experiments and count evidence
without findings. It verified 51 bindings, unchanged C83 source, original timing
and repair records. Its additional 78 exact Fraction cases (37 definite Some,
34 definite None, seven ambiguous) supported C93's error and decision bounds.
No new codec or performance run was claimed. The eight-file archive is
`faster-than-libflac-review/independent-stage17/`; stage17-bound documents are
preserved under `stage18-prior-docs/`.

C91 bounds the two common ascending-loop address bases under an identity mask,
retaining the unmasked implementation for oversized private orders. Fourteen
tests/backend and 24 exact C83 outputs pass. Both quadratic halves now pack, but
the unchanged coefficient map lost SIMD. The five-case core ratio is 1.007919;
this candidate remains unselected.

C92 captures quantizer read/write views and their common length once. Three
focused tests/backend and 24 exact C83 outputs pass. Actual code removes feedback
loop bounds checks and backing reloads without changing rounding or retry state.
Five-case/full12 core ratios are 0.983961/0.996592. The small mixed full-set result
is insufficient to select it; no CLI timing or full acceptance ran.

C93 evaluates the same real variance quadratic using one triangle and doubled
off-diagonal terms: 528 quadratic products at order32 instead of 1,024. Floating
addition order intentionally changes. A bounded numerical domain uses this path;
other inputs use a literal C83 fallback. An independent exact Fraction full-matrix
oracle checks a documented forward-error bound and rejection margin. Its 59
fixtures contain 42 definite Some, 16 definite None and one explicitly ambiguous
threshold case; all three backends pass 14 focused tests. All inherited tests
remain unchanged. The first generated-fixture syntax failure occurred before
numerical testing; its artifacts and the serializer-only repair are preserved.

C93's own original12 independent PCM/CRC/MD5 and e681 size checks pass: aggregate
1.00003523, worst 1.00159768. All 24 outputs happen to match C83; this does not
establish general encoded-byte identity. Its five-case core ratio is 1.000605,
so it remains unselected without full12/CLI timing, full acceptance or promotion.

A separate count-only C83 run measures actual budget-plan record construction.
Recording28 constructs 462 partitions and returns 400 across 864 calls, leaving
only 62 transient records; noise16, noise32 and maximum-block have zero, AR24 has
1,119. All five outputs match independently verified C83 bytes and a fresh frozen
CLI run. These source-level counts do not measure physical allocations or time.
They do not justify adding a saved-choice scratch structure for the recording
hotspot. Old v3 zero counter placeholders remain uninstrumented, not measurements.

## Shared variance guards and paired traces, stage18

C94 checks shared correlation/peak/energy bounds once per model analysis and uses
the quantizer's established coefficient/shift bounds for direct triangular calls.
If the shared check fails, each model retains the guarded C93 wrapper: an invalid
unused higher lag must not force a lower-order model onto a different arithmetic
path. Fifteen tests/backend and own original12 PCM/integrity/quality checks pass.
The 24 outputs match C93 on this set; general C83 byte identity is not claimed.

Direct C94/C83 four-round ratios are 0.979799 on the core screen, 0.973601 on full12
core, but 1.005448 on full12 CLI. Recording28 CLI is slower in all four paired
rounds. The core manifest uses a one-second excerpt; the CLI uses longer inputs,
so cross-scope timing differences do not establish process-startup overhead.
C94 remains unselected. Full193/backend, 220-case and long8 acceptance runners
are prepared only; existing short/low-effort byte-equality gates remain intact.

Actual CLI/core model and triangle disassembly differs only in allocation-layout
identifiers; the C83-to-C94 CLI quantizer and double predictor are unchanged.
Count-only paired runs on recording28's one-second and 8.73-second inputs also
find identical full ranked/attempted coefficient and validity traces (7,392 and
63,140 lines). Predictions/budget calls are 384/864 and 3,280/7,380 respectively;
all variance fallback counts are zero. Four instrumented outputs match fresh
frozen binaries and bound independent hashes. This rules out changed ranking
work for these inputs, but does not identify the runtime regression's cause.
The runner's first report-schema preflight failure occurred before any build or
audio run; the original and successful versioned repair are retained.

## Bulk PCM and exact Welch loop, stage14

C83 combines C80's validated-prefix bulk append with C82's local Welch loop.
The complete accepted PCM prefix is still validated before any copy; unaccepted
tail values remain unexamined and accepted samples remain owned by the encoder.
The installed native/wasm array implementation grows once and bulk-copies; its
capacity equality with repeated push follows from the installed doubling policy.
JS still uses a native push loop. No public API or CLI call path changes.

Welch generation replaces a per-sample closure and boxed energy updates with
four independent signal calculations. Both divisions and signed conversions
remain; energy uses one accumulator with four ascending additions. Actual Clang
code has packed divisions/multiplication/store, no loop calls or spills, and no
FMA or reciprocal approximation. Signed Int64 conversions remain scalar; the
signal buffer initialization and a local 24-byte tuple remain. There is no
persistent cache or additional N-sized weight array.

The actual composition's four balanced original12 rounds give C83/C76 ratios
**0.956167 core** and **0.967173 CLI**. All 12 core cases improve; two CLI cases
are slower and retained. These are directly measured composition results, not
multiplied C80/C82 gains. Both isolated and actual-root checks pass 190 tests per
backend, default format/API/check/release and both CLI suites. Retained220 outputs
and long8's 16 CLI/core outputs match C76 with independent PCM/CRC/MD5 checks.
Root/frozen generated C is compared separately from distinct MSVC/Clang binaries.

Four affected memory observations pass the 8 MiB growth gate: stereo16/block32768
at 2/20 seconds uses 12,320,768/12,718,080 bytes; eight-channel32/block65535 at
5/60 seconds uses 26,128,384/26,365,952 bytes. These are bounded observations,
not universal RSS or hour-stress evidence. Reports are under
`faster-than-libflac/c83-root-integration/`.

Fresh normal-priority CPU8 original12 single-round diagnostics remain slower
than normal libFLAC-8: **1.702293 core**, **1.554451 CLI** times reference time;
real-audio subset ratios are 3.320934 and 1.575532. Candidate totals are
0.160887838/1.681236700 seconds versus reference 0.094512413/1.081562700 seconds
in their respective scopes. Quality and calibration pass, but final acceptance
eligibility and speed gates are false. These separate blocks do not replace the
direct C76/C83 comparisons above.

The C76 orchestration v3 profile separates PCM acceptance (about 0.88–3.86%),
encoder orchestration (1.16–3.12%), output writes (1.21–7.10%) and residual CLI
work (9.45–14.21%) on five instrumented cases. These are attribution percentages,
not throughput gains. The earlier C69 writer share was 0.86–4.92%; the 7–9%
bucket was subframe selection, not writing. Noise16 timing-process wall intervals
are 52–55 ms with execute intervals about 15.7 ms; the 270 ms observation belongs
to a different accepted-frozen process and must not be mixed with that timer.
Close, profile reporting, initialization and process launch/collection remain
outside the execute interval; their individual costs are not established.

C81's paired backing views enabled SIMD in all four narrow fixed predictors,
but its five-case ratio was 0.991512 with mixed results, so it remains unselected.
It passed six focused tests/backend and 24 exact original12 outputs; no full
acceptance or promotion ran. The early-exit scanner idea was already tested in
C64 and was not repeated. Subsequent C84–C86 shortlist experiments are unselected.
C84 V2 passed six focused tests/backend and 24 exact C83 outputs, but its five-case
core ratio was 1.015986 (AR24 1.116645). V1 remains archived and unexecuted.
C85 moved the guarded Double computation into a whole-probe helper: eight focused
tests/backend and 24 exact outputs passed; five-case/full12 core ratios were
1.000348/0.997442. The small mixed result did not justify promotion or CLI timing.
C86's guarded signed32 operands widened to Int64 passed eight tests/backend and
24 exact outputs. Direct VPMULDQ appeared, but runtime view offsets still required
packing and inner-loop spills; its codegen gate failed and no timing ran. These
are engineering screens, not final performance acceptance or current-root changes.

C87 passes owned arrays to the whole-probe helper and creates its full views
locally. It passed nine focused tests/backend and 24 exact C83 outputs. The basic
four-tap loop uses contiguous loads and direct VPMULDQ without inner-loop spills;
larger grouped paths retain packing and guards. Stack usage fell from C86's
0x218 to 0xF8. Its five-case core ratio is 1.000504, with AR24 at 0.995602;
it remains unselected. The other four cases had no shortlist calls in the retained
profile, so their timing changes are not attributed to this arithmetic. No C87
full12, CLI timing, full acceptance, long validation or promotion ran.

### Stage13 rerun-entry correction

Independent stage13 review confirmed the C77 local results, including 22 new
audio cases, but found that the historical standalone replay trusted saved CPU
eligibility. Use `candidate77-planner-views-avx512/full_validate_host_guard_v2.py`
for new C77 replays. It calls `scripts/host_eligibility.py` before either codec,
binding both binaries to their declared target and checking fresh CPUID/XCR0.
The probe is compiled for baseline x64 without `/arch:AVX`; XGETBV is conditional
on XSAVE and OSXSAVE. Missing features/state or a failed probe reject before
dispatch. Historical runners/reports are retained unchanged; generic old runners
do not gain this guard automatically. Any future direct C77 benchmark must use
`guarded_dispatch` before launching either artifact.

Four mocked rejection/dispatch tests and an actual current-host probe plus one
paired CLI/core smoke pass. Full220/long8 was not repeated for this harness-only
fix. Evidence: `validation/evidence/host-guard-fix/completion.json` and its
`ADDENDUM.md`; stage14 independently confirmed the limited correction. Exact
stage13-bound documents are preserved under `stage14-prior-docs/`.

## Planner backing views, stage12

Independent stage12 review passed without findings: fresh targeted tests10/backend,
49 new CLI comparisons (46 additionally through FFmpeg), and 24 sequential planner
state oracle checks. The reviewer verified the test repair, actual vector loop,
artifact identities and raw paired statistics. The overall speed goal remains open.
Review archive: `faster-than-libflac-review/independent-stage12/`.

C76 captures zero-copy read and mutable views after planner scratch capacity is
established. Only the initial collection loop changes; search policy, partition
range, ties, storage and later checked operations remain unchanged. Actual Clang
code now processes eight residuals per vector iteration, including folded stores,
without repeated backing-descriptor loads. Runtime overlap checks and scalar tails
remain. Packed leading-zero counts use a software sequence; stack size increases
from `0x308` to `0x338`. See the hash-bound `candidate76-planner-views/codegen-review.json`.

Four balanced original12 engineering rounds give C76/C69 ratios **0.963191 core**
and **0.957012 CLI**. Maximum-block core is 1.003823 and CLI 1.029042; all slower
observations remain in the reports. These are same-scope comparisons, not final
libFLAC acceptance or multiplied gains from earlier candidates.

Isolated and actual-root checks pass 185 tests on each backend, default format,
API, release builds and both CLI contracts. The 220 retained independent outputs
and 16 long8 CLI/core outputs are byte-identical to C69. Initial focused tests
failed because an optimum-budget probe mutated only the reference scratch;
the repair uses separate probe scratch and additionally checks equal pre-state.
All original post-state assertions and failed evidence are retained.

C70 residual ownership transfer, C71 broad planner unchecked access, C72 integer
peak reduction and C73 exponent extraction passed their initial correctness gates
but did not improve their five-case aggregate screens; none is included. C74's
installed stable compiler reported LLVM disabled. C75 used an isolated official
nightly SDK and changed only the benchmark parser import: actual LLVM executable
and independent original12 checks passed, but its five-case core ratio was
1.336926 versus C69. This default LLVM configuration is unselected; its internal
CPU/FP defaults were not exposed, and it is not labeled Clang AVX2. Global SDK and
PATH were not changed. All attempts remain under `validation/evidence/faster-than-libflac/`.

Four affected C76 memory observations pass the 8 MiB growth gate: stereo16
block32768 at 2/20 seconds uses 12,238,848/12,611,584 bytes; eight-channel32
block65535 at 5/60 seconds uses 25,481,216/26,263,552 bytes. These observations do
not establish universal RSS or final hour-stress acceptance. Stage12 independent
review and the overall speed/stress/cross-system gates remain open.

Fresh normal-priority CPU8 single-round original12 diagnostics still fail the
normal libFLAC-8 speed gate: **1.966264 core**, **1.499662 CLI** times reference
time (real-audio subset 3.763531 and 1.460106). Calibration and quality pass;
`acceptance_eligible` is false. These fresh blocks are not the controlled C69/C76
comparison above. Root/frozen generated C matches after newline and physical
`#line` normalization; actual-root MSVC and frozen Clang binaries remain distinct.
Reports are under `faster-than-libflac/c76-root-integration/`.

## Optional compiler target and Rice emission trials, stage13

C77 recompiles unchanged C76 generated C with Clang AVX512, PKU disabled and
FP contraction off. It requires the builder's checked Skylake-AVX512 feature set
(including AVX512F/DQ/CD/BW/VL) and OS extended-register state support. It is an
optional host-specific artifact; the default build and C76 source stay unchanged.
Unlike the old C11 scalar initial collector, C77's new initial loop uses direct
`vplzcntd` for 32-sample groups and an eight-sample tail; runtime overlap guards
and scalar tails remain. Stack reservation drops from `0x338` to `0x188`.

Four balanced original12 rounds give C77/C76 ratios **0.973791 core** and
**0.981511 CLI**. Four core and five CLI cases are slower; all remain in the raw
reports. These modest gains do not establish a libFLAC win or two-block acceptance.
Independent retained220 and long8 checks pass with exact C76 output bytes; both CLI
contracts pass. The 538 fresh output-file hashes include validation artifacts,
not 538 distinct audio cases. Existing default-backend tests were not repeated for
this compiler-only experiment. Reproducible guarded build/validation scripts and
actual CPU/compiler/runtime identities are under `candidate77-planner-views-avx512`.

C78 fuses Rice codewords of at most 64 bits through a helper, with the exact old
path for longer codewords. C79 places that same guard/mask/operation directly in
the subframe emitter. Both pass five focused tests/backend and independent
original12 checks with 24 exact C76 CLI/core outputs. C79 tests exercise the actual
emitter at every Rice parameter and pending-bit offset, including the 64-bit
boundary and long-code fallback. Codegen confirms C78's per-residual helper frame
and C79's removal of the short-path helper call; C79 still has a stack reload.
C78 full-core ratio is 0.987704. C79 full-core ratio is 0.977734, but CLI is
1.002570, so neither source variant is selected. Their full acceptance, long8 and
promotion have not run; C79's prepared runner is only a plan. No gain is multiplied
with C77, and no combined artifact is claimed.

The exact documents bound by stage12 are preserved in `stage13-prior-docs/` before
this update. Stage13 review confirmed local results and identified the rerun-entry
issue addressed and independently confirmed in stage14 for the guarded entry.
Final normal-libFLAC wins in
both scopes/sets, two independent ten-round blocks and final-current cross-system,
hour-stress and memory acceptance remain required.

## Reference-curve verification protocol, stage11

`scripts/benchmark_reference_curve_cached.py` delegates measurement to the existing
benchmark runner. Warmup, calibration, all nine reference levels, eighteen balanced
rounds, input/binary identity checks and quality budgets remain unchanged. It fully
verifies each distinct encoded output against the independent PCM/CRC/MD5 checks.
Every subsequent output is hashed; byte-identical outputs explicitly inherit the
first verification record within that case and process. Timings are never reused.
A changed output for the same codec is rejected. Different case contents or
verification options receive separate caches. Reports bind both runners and the
cache implementation, and label full verification versus hash-based inheritance.

Eight protocol tests and a real one-round nine-level CLI smoke pass. The smoke
produced one distinct encoded output: one full verification and seventeen explicitly
recorded inheritance checks. It is not performance acceptance evidence. The old
stage11 campaign was intentionally interrupted because repeated independent decoding
of identical outputs dominated its wall time. Its partial observations remain
untouched and ineligible; the fresh cached campaign uses new block IDs and reports,
without mixing observations. See `faster-than-libflac-reference-cache-protocol-stage11.json`
and `faster-than-libflac-reference-curves-stage11-interruption.json` under
`validation/evidence`.

The fresh original12 CLI curve has completed 18 rounds (1944 timed observations).
No level satisfies both fixed quality budgets. Level8 totals 21379246 bytes against
the 22809925-byte anchor, but recording-39 and recording-60 are 5.3941% and 5.7634%
larger than their anchors, exceeding the 3% per-case budget. These cases remain included; the mandatory
normal-libFLAC-8 speed target is unchanged. This reference-only curve does not measure
candidate speed. The long8 CLI and core curves have also completed eighteen rounds
each (1296 timed observations per scope), with successful core calibration and no
post-calibration batch below the 100 ms target. Neither long curve has a qualifying
level; CLI level8 is 51243599 bytes against the 50640556-byte anchor, already above
the 1% aggregate budget. The three fresh curves total 4536 timed observations,
137 full independent verifications and 4723 explicitly traced hash-inheritance
checks, including warmup and calibration outputs. Their consistency audit is
`faster-than-libflac-reference-curves-cached-stage11-audit.json`. These counts do
not include the separately retained original-core stage7 curve. Final candidate
speed acceptance remains pending.
Report: `faster-than-libflac-reference-curve-original-cli-cli-cached-stage11.json`.

## Isolated LPC candidates, stage11

C66 reuses local LPC coefficient storage with symmetric updates that read both old
operands before storing either result. It allocates the quantizer result once per
call and fully overwrites it on every successful trial. It also replaces the
literal two-element precision iterator with the same two integer iterations.
Actual codegen removes per-order coefficient allocation, retry-loop quantizer
allocation and iterator allocation; conditional coefficient-buffer growth and
other model allocations remain. Fourteen focused tests per backend and 24
independently verified original12 CLI/core outputs pass, with bytes identical to C62.

C68 accumulates sixteen LPC outputs in local accumulators, retaining ascending
coefficient order for each output. Actual Clang code holds them in four YMM
registers without tile traffic or spills inside that loop. The scalar tail,
oversized private-input route, dyadic conversion and first-invalid commit contract
remain intact. Eight focused tests per backend and 24 independent original12
outputs pass, again byte-identical to C62. The first test compilation failed
because a new helper omitted its error effect; the failed source/logs are retained
under `candidate68-lpc-output-registers/attempt1-test-signature`. Only that test
signature was corrected before the successful run.

Serialized four-round, batch16, CPU8 five-case screens give aggregate ratios
C66/C62 **0.976940** and C68/C62 **0.971422**. These are selected engineering subsets,
not original12/long8 acceptance or libFLAC comparisons. Gains must not be multiplied.
The C69 composition passes all 182 tests per backend, check/format/release/API,
both CLI contract suites and the retained 220 independent outputs, byte-identical
to C62. Its direct complete-original12 four-round comparison gives **0.939967 core**
and **0.948990 CLI** versus C62. Three core cases and one CLI case are slower and
remain in the reports. Long8 CLI/core validation passes with all sixteen outputs
byte-identical to C62. C69 is now integrated; fresh actual-root validation also
passes 182 tests per backend, default format/API/check/release and both CLI suites.
Root and frozen generated C match after only newline and physical `#line`
normalization. Root MSVC and frozen Clang artifacts retain distinct identities.
Four memory observations pass the 8 MiB growth gate: C69 stereo16/block32768
peaks are 12521472/12742656 bytes at 2/20 seconds, and 8-channel32/block65535
peaks are 25628672/27099136 bytes at 5/60 seconds. Growth is 221184 and 1470464
bytes respectively. These bounded observations are not universal RSS or final
hour-stress evidence. Fresh one-round normal-libFLAC-8 diagnostics still fail
the speed gate: **2.026512 core** and **1.617765 CLI**; real-audio subset ratios
are 4.042780 and 1.563388. Quality and calibration pass, but both reports remain
explicitly ineligible for final acceptance. A single-round MAD of zero is not
stability evidence. See the C69 memory, memory-gates and Clang diagnostic reports
under `validation/evidence`.
These comparisons do not establish a win against libFLAC or final acceptance.

Actual-root validation initially found archived profiling packages below
`validation/evidence`. A format-only selection fixed formatting but did not fix
default package discovery. The added `validation/evidence/moon.mod` establishes
an archival module boundary; the installed-toolchain probe and successful default
root commands verify it. Historical source bytes and both failed attempts remain
preserved. See `faster-than-libflac/c69-root-integration/module-boundary-repair.json`
and `faster-than-libflac-candidate69-root-integration-attempt3.json`.
Proofs, codegen bindings, first-gate receipts and screen decisions are under each
candidate's directory in `validation/evidence/faster-than-libflac`.

C67's MD5 cursor hoist passes eleven focused tests per backend, independent hashlib
fixtures and 24 byte-identical original12 outputs. Its five-case ratio is 0.991496
with two slower cases; it is not selected alone or included in C69. This keeps the
mixed result visible without expanding full validation for an unselected change.

## C62 exact register accumulation, stage10

C62 combines C60's exact residual conversion with sixteen register-resident autocorrelation accumulators. It preserves each lag's ascending sample order, multiplication/addition sequence, triangular prefix and scalar tail. On legal FLAC blocks, one bounded common history base exposes contiguous accesses to the compiler; the mask is an identity for those indices. The preexisting generic calculation remains for private helper inputs longer than 65535. This is an address calculation optimization, not a predictor limit or changed model-selection policy.

The retained C33 implementation already kept accumulators in registers, but actual machine code assembled its history vectors through scalar loads and index spills. C62 uses four contiguous history-vector loads with lane reversal and keeps all sixteen accumulators in registers. No FMA, history-vector assembly or accumulator spill appears in the grouped loop. Hash-bound inspection records the actual emitted instructions; it does not independently quantify their timing contribution.

Isolated and fresh actual-root validation each pass 178/178 tests per backend, checks, formatting, release builds and both CLI contract suites. Public API listings remain unchanged. All 220 independent 31/32/145/original12 outputs and 16 long8 CLI/core outputs match C60 (and its verified C52 baseline). Promotion changes only `encoder_frame.mbt`, `encoder_lpc.mbt` and their two new white-box test files; historical sources and root-file backups remain retained.

Serialized CPU8 four-round original12 comparisons give C62/C60 **0.972031 core** and **0.982995 CLI**. A separate direct comparison against delivered C52 gives **0.955784 core** and **0.978119 CLI**; these direct measurements are not multiplied estimates from earlier stages. Every case remains in the reports, including CLI recording28's 1.020430 ratio and core silence's 1.020581 ratio versus C52. Core uses batch16; CLI includes the whole process and I/O. These are engineering comparisons, not final normal-libFLAC acceptance.

Rejected C61 regrouped each lag's sample reduction into four lanes. It produced packed code and passed initial independent PCM/size checks, but its four-case full-path ratio was 1.020632 versus C60. It also intentionally broke two prior exact-model assertions; those failures and unchanged tests are retained. C61 is not part of C62, whose original exact-model tests pass unchanged.

The fresh root results are in `faster-than-libflac-candidate62-root-integration.json`; frozen full acceptance and long checks are in `faster-than-libflac-candidate62-bounded-lag-registers-acceptance1-acceptance.json` and `faster-than-libflac-c62-long-quality.json`. Current memory and same-scope libFLAC diagnostic results are recorded separately from these comparisons.

Fresh one-round normal-libFLAC-8 diagnostics remain slower: **2.137870 core** and **1.686650 CLI**, with real-audio subset ratios 4.814399 and 1.544679. PCM/integrity/size and core calibration gates pass, but both reports are explicitly not acceptance-eligible. A single observed round does not establish dispersion. Root/frozen generated CLI/core C is identical after universal-newline and physical-`#line` normalization only; native root binaries and frozen Clang binaries keep distinct identities.

Current memory observations compare 2/20 seconds of stereo16/block32768 and 5/60 seconds of 8-channel32/block65535. C62 peaks are 12607488/12718080 and 26161152/26234880 bytes, with growth 110592 and 73728 bytes. All four outputs pass independent integrity/PCM and match C52 bytes. The existing scratch payload ceiling remains 10225900 bytes; these observations are not a universal RSS bound or final hour-stress proof. Records: `faster-than-libflac-c62-memory.json`, its `-gates.json`, and `faster-than-libflac-c62-clang-core-diagnostic.json` and `faster-than-libflac-c62-clang-cli-diagnostic.json`.

## Isolated C60 residual conversion, stage9

C60 was validated in isolation while root runtime was C52; its conversion is now included in C62. It replaces the scalar LPC prediction conversion with an exact dyadic residual transform. For validated integer sample x, prediction P and shift s, the desired residual is ceil(x-P/2^s). A binary64 bias followed by an explicit rounding correction produces that integer near the legal interval; a full UInt64 interval check rejects outliers before signed extraction. Ascending commits preserve the first-invalid prefix and untouched suffix. The proof and integer oracles cover negative fractions, half ties, residual endpoints and maximum prediction magnitudes. No predictor or partition policy changes, extra buffers, or codec FFI are involved.

Native, JS and wasm-gc each pass 176/176 tests, checks, release builds and formatting. Public API listings are unchanged. The 31/32/145/original12 sets give 220 independently verified outputs identical to C52; both CLI contract suites pass. Frozen long8 CLI/core outputs also match C52, with independent libFLAC/FFmpeg PCM, CRC/MD5 and fixed quality budgets. These results are in `faster-than-libflac-candidate60-bias-correction-acceptance1-acceptance.json` and `faster-than-libflac-c60-long-quality.json` under `validation/evidence`.

Serialized four-round, CPU8 original12 engineering comparisons give C60/C52 **0.988881 core** (batch16) and **0.978001 CLI** (complete process and I/O). Individual regressions remain in both reports. This is not a new libFLAC comparison or final acceptance. Actual Clang code contains a packed 16-output correction loop, but also scale reloads, constant broadcasts and register saves; code inspection alone does not attribute the measured gain. Hash-bound proof and codegen evidence are under `validation/evidence/faster-than-libflac/candidate60-bias-correction/`.

Earlier stage9 candidates are retained without integration: C55 cached exact leaf bounds, C56 fixed prediction/statistics fusion and C57 O3 compilation showed no aggregate benefit. C58 variance-based admission passed the initial size budget but changed compressed bytes without improving aggregate time. C59's exact ceil-based conversion passed integer and output checks but regressed all four screening cases; the compiler expanded ceil into a lengthy sequence. C60 specifically replaces that sequence. One CLI benchmark invocation used the core-domain oracle and was rejected before timing; its correction uses the separately bound C52 CLI oracle, with the failure recorded.

Final two-block normal-libFLAC speed gates, remaining reference curves, final-artifact cross-system/hour stress and independent acceptance remain open. C52's earlier libFLAC ratios must not be relabeled as C60 measurements.

The matched C60 coarse profile uses separate timing/event builds, four representative cases and two observations; all outputs match the frozen CLI. Exclusive planner attribution is 26.37% on noise16, 15.99% on AR24 and 20.82% on recording28; LPC model generation is respectively 20.55%, 18.52% and 21.22%. Maximum-block attribution includes models14.86%, MD5 11.57%, fixed prediction10.52% and Double prediction8.58%. These instrumented shares are not throughput measurements. The isolated profiler adapts one checked-sample counter anchor to the new bit-load statement; its scope and uncovered counter placeholders remain explicit. Stage record: `validation/evidence/faster-than-libflac-stage9.json`.

## Search hardening, 2026-09-29

The paired release experiment uses frozen baseline source
`71de39f0a5027b7f6898c323e3d87a198e6aa25b50740f00e3426916975d3eca`
and candidate CLI SHA256
`179b27506f7bc226750fe7efdddd4653d4df8c9f689b98a7787252c3a84e69fe`.
The host is Windows on Ryzen 7 8845H (8 cores/16 logical CPUs), with the same
MoonBit 0.1.20260827 / compiler 0.10.11+6ff76a5f9 and libFLAC 1.5.0.
No sustained stress or parallel builds ran during these measurements. Child
processes inherited one logical-CPU affinity; warm filesystem cache, power
management and unrelated desktop scheduling still affect the results.

Native monotonic-clock probes in separate source copies first measured Rice
planning at about 84–86% of inclusive subframe search time on three-second
effort-8 noise, correlated and recording inputs. Prediction accounted for most
of the remaining time; writing took under 1% of search time. The implementation
now reuses quotient arrays when merging the partition tree, computes signed
width with count-leading-zeros, and bounds the exact Rice parameter search using
its nondecreasing cost differences. Candidate predictors, partition limits and
tie rules are unchanged. A 1,000-distribution regression compares both Rice
methods against exhaustive parameter costs.

The probes also counted actual quotient-array creation sites: noise dropped
from 6,710,660 to 3,372,368 allocations, and the correlated input from 8,195,324
to 4,117,120. These are array event counts, not total heap allocations or peak
RSS. Inclusive probe categories overlap and must not be summed. Instrumented
timings are diagnostic; the speed comparison uses uninstrumented release builds.

Each of ten inputs has effort 5 and 8 runs: one warm-up and five measured
repetitions for baseline, candidate and libFLAC, alternating command order.
Inputs include deterministic 16/32-bit noise, 24/32-bit correlated stereo,
24-bit six-channel PCM, four contiguous corpus recording excerpts and a complete
VOiCES speech utterance. Source identities, all repetitions, per-run host load,
median, median absolute deviation (MAD), ranges, memory and byte sizes are in
`validation/evidence/hardening-benchmark.json` and
`hardening-benchmark-speech.json`. These short excerpts are not a broad music
collection; two initial excerpts are predominantly silence.

| Input / effort | Baseline median s | Candidate median s | libFLAC median s | Candidate / libFLAC bytes |
|---|---:|---:|---:|---:|
| Noise16 stereo / 8 | 1.246344 | 1.038492 | 0.043398 | 192606 / 192558 |
| Correlated24 stereo / 5 | 0.280385 | 0.240575 | 0.037634 | 75353 / 78720 |
| Correlated24 six-channel / 8 | 2.025535 | 1.620130 | 0.042251 | 345102 / 344474 |
| Recording28 / 8 | 2.841958 | 2.359824 | 0.046008 | 393645 / 394180 |
| VOiCES speech / 8 | 0.457853 | 0.373229 | 0.037652 | 66249 / 66232 |
| Mostly silent recording39 / 5 | 0.073531 | 0.093520 | 0.053236 | 1009 / 967 |

All 20 paired outputs are byte-identical to baseline and independently match
libFLAC integer PCM; `flac -t` also passed every measured output. Thus the
observed compression degradation is zero. Summing the 20 per-case medians gives
13.472382 s before and 11.158284 s after (17.2% reduction); this is an aggregate
of these fixed tasks, not a general throughput guarantee. Search workloads
generally improve beyond their observed MAD. The worst CLI median regression is
the mostly silent recording39 at effort 5 (+27.2%, about 20 ms), with overlapping
run ranges and substantial startup/scheduling variation; it is retained in the
report rather than excluded. Maximum observed process peaks are 10,125,312 B
before and 10,133,504 B after.

`validation/benchmark` separately measures `encode_pcm` after input loading and
integer unpacking, excluding all file I/O. Its one warm-up plus five repetitions
per case and independent output checks are in `hardening-core-benchmark.json`.
The noise16 effort-8 core median changes from 1.5593 to 1.1150 s; speech effort-8
from 0.3332 to 0.2759 s. Some low-cost or noisy cases show no resolved improvement.
Core repetitions run as a baseline batch followed by a candidate batch; they do
not have the CLI experiment's alternating process order. These short-input,
shared-host observations are not a claim of universal or statistical significance.
The encoder remains substantially slower than libFLAC on these workloads;
the optimization does not establish performance parity or universal speedup.

Reproduce with `scripts/profile_encoder.py freeze`, then `profile` and
`profile-candidate` in separate snapshots. `scripts/benchmark_hardening.py`
accepts `--baseline` and `--candidate` native CLI paths; pass `--core` with the
two `validation/benchmark` executable paths for isolated core timing. Preserve
the baseline snapshot before editing codec source. The speech fixture download
is SHA256-checked and attributed in [THIRD_PARTY.md](../THIRD_PARTY.md).
After cleaning generated caches, `freeze --historical` reconstructs the earlier
encoder algorithm from the hash-checked [preserved baseline](../validation/baselines/README.md),
without changing the working implementation.

The sustained and large-file gates are now complete locally. All input bytes
were physically written and processed; these were not header-only size tests.
The long signal is deterministic channel-shifted triangle PCM, not a recording.

| Duration / format / effort / block | PCM bytes | Encode elapsed s | Encoder peak working set B |
|---|---:|---:|---:|
| 60 s / stereo24 / 5 / 4096 | 17,280,000 | 12.49 | 8,740,864 |
| 3600 s / stereo24 / 5 / 4096 | 1,036,800,000 | 1,078.49 | 10,448,896 |
| 60 s / 8ch32 / 8 / 65535 | 92,160,000 | 118.66 | 26,312,704 |
| 3600 s / 8ch32 / 8 / 65535 | 5,529,600,000 | 5,171.75 | 26,218,496 |

The high-effort maximum-block hour ran below real time (about 0.70× audio
duration / wall time). These stress runs overlapped other verification jobs;
they demonstrate execution and bounded process memory for these inputs, not a
controlled throughput comparison. Source/libFLAC/STREAMINFO MD5 agree, and all
four `flac -t` checks passed. The large FLAC file is 175,007,551 bytes; the >4 GiB
gate concerns actual RF64 PCM input/output, not a >4 GiB compressed FLAC file.

MoonFLAC additionally produced a retained 5,529,600,104-byte RF64 file in
172.17 s with 16,904,192 B process peak. Its ds64 sizes, 172,800,000 sample-frame
count and `0x63f` layout are verified; original, libFLAC, disk PCM and FFmpeg
digests are all `5ca93440041056a4e6b10d9392778dba`. See
`hardening-long.json`, `hardening-large-decode.json` and the final independent
physical-format/byte-comparison proof in `hardening-review/final.json`.

Two actual 30-minute seeded mutation runs passed without crash, timeout or
accepted-PCM mismatch. The fully retained run covers 3,784 generated iterations
and 15,136 mutations; its 84 acceptance differences are independently reproduced
incorrect STREAMINFO cases. The runs use the same seed and overlap, so their
counts are not added as unique coverage. This is not coverage-guided fuzzing.
Windows and Ubuntu 22.04.5 WSL2 each ran all three backends (99/99 per backend),
with independent Linux CLI/backend checks. macOS, independent Linux hardware
and remote CI were not exercised. Detailed gates and the final-review status are
in [the acceptance ledger](ACCEPTANCE.md).

## Encoder measurements

The native encoder measurements are separate from the decoder baseline below. [Independent encoder evidence](../validation/encoder/README.md) records 18 encodes of the same three-second stereo sources with MoonFLAC and libFLAC levels 0/5/8. Both tools use 1024-sample blocks; reference padding and seek tables are disabled. Level numbers are each implementation's search policy, not equivalent work budgets. Every output was independently decoded before recording a pass.

For effort 5 on this host, MoonFLAC produced 226,281 bytes for AR-like 24-bit PCM in 0.832 seconds, versus libFLAC's 236,976 bytes in 0.045 seconds; noise16 produced 577,747 / 577,511 bytes in 0.762 / 0.043 seconds; repeated real16 produced 116,102 / 116,558 bytes in 0.596 / 0.048 seconds. Effort 8 took roughly 3.49–4.12 seconds per three-second input. These observations show a slower encoder search, not a speed advantage. They include process startup and file I/O, and are single runs on a shared workstation. Full measured values and memory observations are in `validation/evidence/encoder-benchmark.json`.

[Long-stream evidence](PERFORMANCE-EVIDENCE.md) includes 5/60/300-second effort-0 encoding, predictor-enabled effort 5 at 5/30 seconds, and a 65,535-sample block run. At effort 5, peak working set was 9,216,000 / 9,519,104 bytes as duration increased sixfold; the maximum-block case used 13,762,560 bytes. The encoder's retained scalar PCM is bounded by `block_size * channels`; returned bytes are caller-owned. These counters and measured process working sets are distinct from whole-file convenience API storage and caller-retained output.

## Decoder baseline

Performance evidence must identify backend, optimization mode, toolchain, hardware, input properties, input size and decoded sample count. Correctness is established first by the independent PCM oracle. A fast rejection or an incorrect decode is not a decoding benchmark.

## Available measurements

`scripts/validate.py compare` records per-file native CLI elapsed seconds in its JSON reports. These times include process startup, file I/O, decoding and raw output writing. They are useful end-to-end observations; they are not isolated decoder throughput. [Durable oracle evidence](../validation/evidence/README.md) records 245 generated and 64 subset PCM comparisons, 11 uncommon per-frame comparisons, and 11 faulty-input rejections.

A separate native release CLI measurement on Windows, Ryzen 7 8845H, MoonBit compiler `v0.10.11+6ff76a5f9`, used 48 kHz stereo 24-bit generated tones and three runs per input:

| Audio duration | Median elapsed | Audio duration / elapsed | Maximum process working set | Peak decoder compressed bytes |
|---|---:|---:|---:|---:|
| 5 seconds | 0.088585 s | 56.44× | 9,068,544 B | 24,810 |
| 60 seconds | 0.627185 s | 95.67× | 9,093,120 B | 25,191 |
| 300 seconds | 2.656305 s | 112.94× | 9,400,320 B | 25,037 |

The source is deterministic tones, not a representative music benchmark. The measured command is `verify`: timings include startup, input I/O and complete reconstruction/checksums, but no PCM output writing. Filesystem caches were warm; CPU affinity and power settings were not controlled. Windows process high-water working-set values are distinct from decoder counters. Detailed commands, reference timings and source hashes are in [performance evidence](PERFORMANCE-EVIDENCE.md); raw measurements are `validation/cache/benchmark/results.json`. The 60× duration increase added 324 KiB to peak working set, supporting bounded streaming for these inputs, not an unrestricted memory guarantee for all metadata or frames.

The Playground runs selectable JavaScript and WebAssembly GC artifacts in a Worker. Decode timings include input/PCM host copying; backend loading/compilation is reported separately. Recorded single local Chromium runs are:

| Public corpus input | JavaScript decode + bridge | wasm-gc decode + bridge |
|---|---:|---:|
| Subset 60, real mono audio, 227,247 samples | 117.70 ms | 31.80 ms |
| Subset 34, 192 kHz LPC32, 1,533,344 samples/channel | 4,307.60 ms | 796.90 ms |

Both backends verified MD5 and produced byte-identical WAV during backend-switch testing. The high-rate UI responsiveness run recorded maximum page-timer gaps of 22.1 ms (JS) and 16.6 ms (wasm-gc). Evidence is `validation/results/browser/backend-comparison.json`; [browser reproduction](../playground/README.md) describes the interaction scripts. Browser scheduling, copying and JIT state affect these observations; they are neither an audio-device latency measurement nor a general cross-device performance guarantee.

## Reproduction

Build the requested mode explicitly, retain `moon version --all`, and supply the actual generated CLI path to the oracle runner. For example:

```sh
moon build --target native --release
python scripts/validate.py compare --cli _build/native/release/build/cmd/moonflac/moonflac.exe --corpus generated
```

For a sustained measurement, decode a long real recording and a deterministic reference signal, perform an untimed warm-up, then multiple measured repetitions. Report median elapsed time and decoded interchannel samples/second, alongside audio duration/elapsed time. Keep file I/O inclusion explicit. Preserve individual runs rather than reporting only the best result.

## Memory interpretation

The incremental API is intended to consume one frame at a time. `buffered_bytes()` and `peak_buffered_bytes()` track documented compressed storage. They exclude the caller's source file, returned PCM, retained metadata, host allocations and—in counters documented as native-only—Ogg page/packet staging. They cannot be relabeled as process RSS.

One maximal 65,535-sample eight-channel frame has 524,280 sample values; intermediate Int64 planes and final Int arrays both exist during reconstruction. This is bounded per-frame working storage. Whole-file `decode`, browser playback and any caller that retains frames intentionally accumulate PCM. The native CLI reads a 64 KiB input chunk and writes frame PCM without accumulating it.

Long unary Rice symbols are scanned by byte. Incremental retry scheduling and input buffering must also be considered when testing one-byte cuts: speeding up the inner unary scan alone cannot establish linear total work. Use adversarial small input splits as well as normal 16 KiB transport chunks, and record buffer peaks plus wall-clock time for increasing input lengths.

## High-effort optimization follow-up (independently passed)

The preceding hardening results are independently accepted. The separately authorized `high-effort-optimization-20260929` uses that final version as its baseline and the contract in ACCEPTANCE.md. The completed balanced measurements are stored separately below; independent review passed.

### Exact changes and profiling evidence

`encoder_frame.mbt` now shares the earliest convex Rice optimum between the two methods (clamped at 14 for Rice), obtains the existing conservative lower bound from integer bit lengths, and retains compact scalar choices until the globally winning partition level is known. It reuses quotient arrays within one subframe search and compacts mutable tree nodes through an active prefix. Merge columns at or above the maximum signed width are provably zero and need not be added. Predictor candidates, LPC models, partition orders, escape comparisons, writer and public API are unchanged.

For positive Q=sum(folded) and N=count, let a=floor(log2 Q), b=floor(log2 N). Every k below a-b-2 satisfies N*2^(k+2)<2^a<=Q; the CLZ starting bound therefore skips only strictly improving costs. The existing exact quotient-cost loop refines that bound. C(k+1)-C(k)=N-sum(ceil((u>>k)/2)) is nondecreasing, so clamping the earliest minimum on [0,30] to 14 preserves the earliest minimum on [0,14]. Escape wins only on strictly smaller cost; Rice wins method ties; lower partition order wins equal total cost. All sums and shifted count bounds are below 2^48 for legal encoder residuals.

For L leaves, the tree contains 2L-1 nodes. Two 2L integer arrays store scalar choices (0..30 Rice; 32..63 escape width), and only the winning level allocates partition records. Scratch and nodes never escape the search; returned plans own immutable scalar records. Every reused quotient slot is cleared across all 31 columns. The active-prefix merge consumes both children before overwriting an earlier slot. At most 32768 leaves are possible; allocation is bounded by a block, with no state retained across stream frames.

Diagnostic profiles are `effort8-profile-baseline.json`, `effort8-profile-candidate.json` and `effort8-profile-allocation.json`. On the three recorded inputs, speculative partition-record creation fell from 4,455,718 / 5,433,512 / 10,926,416 to 60,402 / 166,055 / 41,801. Quotient-array allocation fell from 1,119,616 / 1,364,864 / 2,744,576 to 188,928 / 188,928 / 381,952. These are exact event counts. Region timing uses instrumented isolated copies and may overlap correctness jobs; it is diagnostic, not the controlled speedup claim. The allocation variant groups quotient allocation before leaf statistics to avoid a clock call per allocation, and reports its cost separately; its source layout intentionally differs from production.

`encoder_plan_oracle_wbtest.mbt` independently scans every parameter and legal partition order, comparing every returned decision field. Coverage includes 18,555 tiny-array/warmup configurations, nonstationary distributions, Rice/escape ties, integer boundaries, maximum partition order, 65535 odd blocks and explicit reused-scratch ownership.

### Large-frame reference transport and memory boundary

The first core run stopped at the maximum-block case: FFmpeg 9.0.1 returned success with zero PCM bytes for valid two-frame, eight-channel 32-bit FLAC. `effort8-core-benchmark-interrupted.json` preserves that failure and its earlier completed cases; it is excluded from final aggregates. The same behavior reproduced with official libFLAC's own encoding. `effort8-ffmpeg-parser.json` records both inputs, frame offsets/sizes from official `flac -a`, decoder commands and hashes. Wrapping the *unchanged original frames* in standard Ogg FLAC (copied STREAMINFO and an empty comment) gives exact full PCM with both FFmpeg and libFLAC. This isolates the observed failure to FFmpeg's raw-input path, without changing MoonFLAC or its encoded bytes. FFmpeg's [raw FLAC parser](https://github.com/FFmpeg/FFmpeg/blob/master/libavcodec/flac_parser.c) has a header-density heuristic; attribution to that specific branch remains an inference, not a binary-level trace of this 9.0.1 build.

The final benchmark therefore preselects the original-frame Ogg transport for every maximum-block FFmpeg verification, records the raw-input outcome separately, and uses strict native-input FFmpeg verification elsewhere. It does not fall back silently after an arbitrary failure. Original FLAC always passes independent libFLAC PCM plus `flac -t` MD5/CRC. The packetizer is validation-only, removes unrelated metadata and does not implement a public Ogg encoder. Its CRC table was checked against a bitwise reference on all 65536 two-byte inputs and boundary-length payloads. The 10-second/eight-frame CLI fixture also passed this transport preflight.

`effort8-memory.json` measures actual streaming CLI working sets over four cases, with complete baseline output-byte comparison, source PCM MD5 and independent libFLAC decode/CRC checks. For block 32768, stereo16, candidate peaks were 24,424,448 / 25,001,984 B at 2 / 20 seconds (baseline 26,296,320 / 26,951,680 B). For block 65535, eight-channel32, candidate peaks were 25,440,256 / 25,837,568 B at 5 / 60 seconds (baseline 25,550,848 / 25,722,880 B). These are memory tests, not controlled timing comparisons. Scratch is confined to one subframe invocation; no persistent encoder state changed, so this follow-up does not repeat or replace the previously accepted 86-minute/hour-scale campaign.

### Paired core results (complete)

Core fixtures request one-second contiguous prefixes, except the complete speech utterance and at least two full maximum blocks. CLI fixtures request ten-second contiguous prefixes (bounded by the original recording length), again preserving the full speech utterance. The two modes therefore use different fixed input sets; their percentage difference cannot be attributed solely to startup or I/O. Baseline and candidate always receive identical bytes within each mode.

One external warmup plus six balanced measured rounds per case; every MoonBit process also warms once, then times a fixed common batch. Batch sizes were calibrated from both codecs (1–211 calls here, none capped). Only encode_pcm is timed; input reading/unpacking, comparisons and output writing are excluded. All original rounds, including timing spikes, remain in `effort8-core-benchmark.json`.

| Case | Bits/channels | Baseline median ± MAD (s) | Candidate median ± MAD (s) | Median reduction | Improved paired rounds |
|---|---|---:|---:|---:|---:|
| noise-16-2 | 16/2 | 0.691768 ± 0.008337 | 0.373958 ± 0.002242 | 45.94% | 6/6 |
| noise-32-2 | 32/2 | 0.173631 ± 0.003546 | 0.112452 ± 0.002447 | 35.24% | 6/6 |
| ar-24-2 | 24/2 | 1.020846 ± 0.012808 | 0.531990 ± 0.003844 | 47.89% | 6/6 |
| ar-32-2 | 32/2 | 1.054963 ± 0.013061 | 0.609997 ± 0.013015 | 42.18% | 5/6 |
| ar-24-6 | 24/6 | 1.547727 ± 0.030068 | 0.810249 ± 0.007879 | 47.65% | 6/6 |
| silence-16-2 | 16/2 | 0.006353 ± 0.000177 | 0.006601 ± 0.000151 | -3.91% | 2/6 |
| maximum-block-32-8 | 32/8 | 0.486436 ± 0.010248 | 0.492355 ± 0.006776 | -1.22% | 2/6 |
| recording-1 | 16/2 | 0.894438 ± 0.036994 | 0.456905 ± 0.002632 | 48.92% | 6/6 |
| recording-28 | 24/2 | 3.799409 ± 0.388544 | 1.270142 ± 0.077812 | 66.57% | 6/6 |
| recording-39 | 16/4 | 0.008577 ± 0.000174 | 0.008509 ± 0.000496 | 0.79% | 4/6 |
| recording-60 | 16/1 | 0.002134 ± 0.000065 | 0.002041 ± 0.000041 | 4.36% | 3/6 |
| speech-voices | 16/1 | 0.310800 ± 0.003054 | 0.158723 ± 0.002547 | 48.93% | 6/6 |

Fixed-set sum of medians: 9.997083 → 4.833922 s (51.65% reduction). This is a fixed benchmark aggregate, not universal throughput. Worst median regression was 3.91% on silence; maximum blocks were 1.22% slower. Light recording-39/60 and silence do not establish a repeatable benefit: paired differences are small relative to dispersion. The eight ordinary search-heavy cases improve in five or six of six pairs. The ar-32-2 candidate has one large adverse timing outlier, retained in the report. No outliers were removed. The libFLAC entries in this core report are explicitly CLI wall times and are not compared as core-to-core speed ratios.

### Paired CLI results (complete)

One warmup and six measured rounds use all six codec orderings, balancing baseline/candidate precedence and rotating libFLAC through every position. Times include process startup, file I/O and streaming encoding. No builds or pressure jobs ran alongside the final controlled benchmarks. Raw timings, every paired difference, host-load snapshots, encoded sizes, throughput and process peaks are retained in `effort8-cli-benchmark.json`.

| Case | Input seconds | Baseline median ± MAD (s) | Candidate median ± MAD (s) | libFLAC median (s) | Reduction | Improved pairs |
|---|---:|---:|---:|---:|---:|---:|
| noise-16-2 | 10.000 | 11.634424 ± 0.542387 | 4.680418 ± 0.232385 | 0.082852 | 59.77% | 6/6 |
| noise-32-2 | 10.000 | 1.810676 ± 0.015346 | 1.083457 ± 0.010797 | 0.084521 | 40.16% | 6/6 |
| ar-24-2 | 10.000 | 12.882678 ± 0.249784 | 5.909826 ± 0.200962 | 0.079547 | 54.13% | 6/6 |
| ar-32-2 | 10.000 | 14.102733 ± 0.239162 | 6.693064 ± 0.193430 | 0.134845 | 52.54% | 6/6 |
| ar-24-6 | 10.000 | 23.314928 ± 0.155614 | 11.106599 ± 0.087787 | 0.118524 | 52.36% | 6/6 |
| silence-16-2 | 10.000 | 0.122741 ± 0.002470 | 0.124501 ± 0.003176 | 0.043890 | -1.43% | 3/6 |
| maximum-block-32-8 | 10.000 | 1.966751 ± 0.016023 | 1.965572 ± 0.010811 | 0.280001 | 0.06% | 3/6 |
| recording-1 | 7.000 | 8.496722 ± 0.165222 | 3.442691 ± 0.013582 | 0.061708 | 59.48% | 6/6 |
| recording-28 | 8.730 | 28.854953 ± 0.687561 | 14.696338 ± 0.320731 | 0.119639 | 49.07% | 6/6 |
| recording-39 | 5.754 | 1.004859 ± 0.016254 | 0.513940 ± 0.012053 | 0.050937 | 48.85% | 6/6 |
| recording-60 | 5.153 | 0.426453 ± 0.007229 | 0.207011 ± 0.003438 | 0.050275 | 51.46% | 6/6 |
| speech-voices | 3.400 | 0.398927 ± 0.015511 | 0.209835 ± 0.012380 | 0.046122 | 47.40% | 6/6 |

Fixed-set sum of medians: 105.016845 → 50.633253 s (51.79% reduction). libFLAC's corresponding CLI sum is 1.152863 s, so the aggregate elapsed-time ratio drops from 91.09× to 43.92×; MoonFLAC remains substantially slower. Equal effort labels do not imply equal search algorithms. All ten non-silent, non-maximum-block CLI workloads improve in all six pairs. Silence's median is 1.43% slower, but its paired median difference is near zero relative to MAD; maximum blocks are essentially unchanged (+0.06% reduction). No universal improvement is claimed.

Both final modes retain all twelve cases, including regressions. Every corresponding baseline/candidate file is byte-identical in every round; independent PCM, MD5 and CRC gates pass. The fixed-set paired total differences are positive at all six round indices in both modes (these are sums across separately measured cases, not simultaneous full-suite runs). Final source/binary/report identities and limitations are indexed in `effort8-final.json`. Windows and WSL2 each pass 103/103 on native/JS/wasm-gc; 328 native / 327 audio FFmpeg cases, 137 forced representations, 828 cross-backend streams, and 24 additional Linux CLI cases pass. All 828 Windows streams retain the accepted pre-follow-up hashes and all WSL streams match them. Independent review passed.

Reproduction (prepare fixtures once from the existing documented cache):

```sh
python scripts/profile_effort8.py freeze --historical --name reconstructed
# Build reconstructed and current validation/benchmark8 with the same pinned toolchain.
python scripts/benchmark_effort8.py prepare --seconds 1 --manifest validation/cache/effort8-benchmark/core-inputs.json
python scripts/benchmark_effort8.py prepare --seconds 10 --manifest validation/cache/effort8-benchmark/cli-inputs.json
python scripts/benchmark_effort8.py run --core --manifest validation/cache/effort8-benchmark/core-inputs.json --baseline <baseline-benchmark8> --candidate <candidate-benchmark8> --baseline-identity <baseline-source-identity.json> --candidate-identity <candidate-acceptance.json> --report <new-core-report.json>
python scripts/benchmark_effort8.py run --manifest validation/cache/effort8-benchmark/cli-inputs.json --baseline <baseline-cli> --candidate <candidate-cli> --baseline-identity <baseline-source-identity.json> --candidate-identity <candidate-acceptance.json> --report <new-cli-report.json>
python scripts/validate_effort8.py
wsl -d Ubuntu-22.04 -- python3 /mnt/c/Users/<user>/Desktop/Project/mb/moonflac/scripts/validate_effort8_linux.py
python scripts/memory_effort8.py --baseline <baseline-cli> --candidate <candidate-cli> --report <new-memory-report.json>
```

Existing evidence is preserved: use new benchmark report names and a fresh checkout/cache for full validation reruns. WSL requires the pinned SDK/library preparation already documented for the prior phase; this command is not a claim of a Linux installation or remote CI run. Do not run profiling/builds/stress concurrently with the paired benchmarks. The validation-only packetizer and its raw-input limitation reproduction are in `scripts/packetized_flac.py`.

Final independent review `high-effort-optimization-20260929-independent-01` confirms these bounded results. Its untouched report, mathematical proof, extra source/tests/CLI evidence and independent packet-transport reproduction are archived under `validation/evidence/effort8-review/`. The review recomputed the retained benchmark samples rather than rerunning the full controlled timing campaign. Historical paths inside archived review files are provenance, not dependencies of the project's primary reproducible validation scripts. No production code changed during closeout.

## Speed-first encoder follow-up (local gates passed; review pending)

The prior effort-8 exact-search optimization is independently accepted. The newly authorized speed-first phase may trade bounded measured size for speed, while PCM remains exactly lossless. Its contract and empirical 1% aggregate / 3% per-case size gates are recorded in ACCEPTANCE.md. Original twelve CLI inputs, reference parameters and historical results remain unchanged. New variants, holdouts and silence/maximum-block groups will use separate evidence.

The new baseline is the accepted CLI `e6817e77aafaa124a30d4e75b9a5f73beca10f0b0da967ddcc2e97c3397fe743`; its source/input/build inventory is `speed-first-baseline.json`. Current-baseline instrumentation attributes roughly 59–65% of ordinary-case CLI execution to Rice planning and 23–32% to predictor residuals; LPC model generation is only 1–2%. Inclusive timing categories and instrumentation overhead prohibit treating these percentages as an additive accounting or a speedup measurement. Actual MSVC command capture confirms `/O2 /MT` was already enabled. Generated C instead exposed repeat MD5 table/word allocation and a whole-frame PCM packing temporary. Reusing immutable tables and per-state words, and feeding sign-extended PCM bytes directly into the MD5 block buffer, removes those allocations without skipping integrity work. A Python `hashlib` oracle covers 232 depth/channel formats, interleaved states and digest/continue boundaries.

Exploratory one-pass runs on the unchanged twelve CLI inputs retained four LPC shortlist/partition variants: 2/6, 4/8, 8/8 and 4/15. Each passed original-set size budgets and independent PCM; observed sums were 6.05, 7.55, 9.59 and 14.99 seconds respectively. These shared-host measurements are strategy diagnostics, **not controlled timing acceptance**. The full-file total for 4/8 was 22,813,564 versus 22,809,925 baseline bytes (+0.016%). No production path encodes with both old and new policies and chooses the smaller file.

The first sealed 17-case holdout rejected that initial policy: the partition-order-15 conformance signal grew 7.603%, and a noisy impulse signal grew 5.119%. Both decoded exactly. All failed observations remain in `speed-first-holdout-gate.json`. Diagnosis separated two general causes: alternating zeros need finer partitions, and sampled-valid LPC candidates can fail complete residual legality at an unsampled extreme. Revision 3 retains every legal partition level when at least a quarter of residuals are zero and backfills invalid ranked LPC candidates until four complete legal residuals have been evaluated. The intermediate revision evaluating every partition for fixed order zero is retained as a slower diagnostic point; it was not selected.

All original 17 holdout cases remain regression gates after their use in diagnosis; revision 3 passes them with total 18,909,970 versus 18,887,413 bytes (+0.1194%). A separately sealed 14-case second holdout was prepared before encoding the revised policy, with its selection, PCM hashes and generators in `speed-first-holdout2-manifest.json`. The first set includes two complete new LibriVox voices, while public conformance files do not prove independent recording provenance. The second set uses four previously unselected public PCM excerpts and ten new synthetic formula/format combinations; it is not described as fourteen independent recordings. General-depth FFmpeg checks use signed 32-bit output, verify zero padding bits and shift back to the original integer domain; the original unsupported `pcm_s20le` harness failure is retained. Final repeated measurements passed; paired independent review is pending. See [the complete executed tables and limitations](SPEED-FIRST-EVIDENCE.md) and `speed-first-final.json`.

The added 32768-sample case exposed the same class of native FFmpeg input limitation as the earlier maximum-frame case. Independent reproduction with the accepted MoonFLAC baseline, revised MoonFLAC and official libFLAC `-8` produced zero native-input FFmpeg PCM for all three files, while libFLAC decoded them completely. Official frame analysis followed by unchanged-frame Ogg wrapping allowed FFmpeg to reproduce all 15,360,000 PCM bytes in each case. `speed-first-ffmpeg-32768.json` preserves commands, versions, raw results and output hashes. The original failed benchmark remains intact; a separately named retry explicitly passes `--large-frame-transport`, records native results every round, and does not alter production encoding or silently retry arbitrary failures.

### Revision4 independent-review fixes

Independent review `speed-first-encoder-20260929-independent-01` found five additional 37-sample inputs over the intended per-case size budget despite exact PCM, and a misleading core/CLI ratio in the generated report. The original review and failing artifacts are preserved. Actual blocks <=256 now bypass the proxy shortlist and evaluate all LPC models in their original order. All five cases regain exact baseline bytes; 145 independent review/neighbor cases pass, including 54 neighboring configurations. Current Windows/WSL tests are117/117 per backend, and affected block256 streaming-memory checks pass.

Fresh revision4 original12 measurements: CLI46.764060 ->7.691795 seconds (6.080x, same-round libFLAC CLI1.123970 seconds, ratio6.843x); core4.949322 ->0.927363 seconds (5.337x). Core is compared only with baseline MoonFLAC core. The old mixed-domain ratio is removed from the derived JSON and Markdown. Current files on all31 retained quality cases are byte-identical to revision3, and both per-set/per-case size gates pass. Earlier17/32768/reference timing tables remain explicitly labelled revision3 history, not inferred timings of the new artifact. See [the final measured tables](SPEED-FIRST-EVIDENCE.md) and `speed-first-revision4-final.json`. Both old holdouts are now regression sets; no fresh unseen revision4 holdout is claimed. Final independent verdict remains pending.


### Revision 7: exact partition pruning and irregular-block LPC search

The subsequent independent review exposed two small-nonzero-background pulse inputs above the empirical size budget. Counting exact zeros was insufficient to identify useful fine partitions. Revision 7 therefore keeps the exact partition optimum: establish a cost through order 8, compute optimistic costs for deeper orders, then refine through the highest order that could still win. For folded residual `u` with bit length `w`, every Rice parameter obeys `(u >> k) + k + 1 >= w + 1`. Summing this plus four parameter bits bounds both Rice and Rice2; taking the minimum with legal escape cost preserves the bound. Equality cannot replace the existing lower-order winner. `scripts/prove_partition_bound.py` records the algebra and 4,066,022 scalar checks, 4,905 partitions and 189 warm-up/order cases; four MoonBit regressions separately exercise the production implementation and complete-plan identity.

The frozen 32-case nonzero-background matrix also exposed LPC ranking loss in a 257-sample final frame. Revision 7 evaluates the full original model pool for blocks not divisible by 256 and when the winning fixed candidate partitions contain at most eight samples, in addition to the previous short-block rule. The remaining LPC shortlist is still heuristic; there is no universal compression-size guarantee or hidden baseline double encode. Intermediate revision 5/6 failures remain in the evidence directory. All 32 pulse cases and the prior 145+31 regression cases now pass the declared quality/independent PCM gates. Windows/WSL three-backend tests each pass121/121, and all three affected memory groups remain below the8MiB duration-growth gate. Fresh controlled original12 CLI medians sum49.101317 ->10.169248s (4.828x baseline speedup;8.709x same-round libFLAC CLI1.167634s). Core4.957022 ->1.376529s gives3.601x versus MoonFLAC baseline core only. Original CLI file bytes22,809,925 ->22,813,547 (+0.015879%). The CLI targets are met; core speedup is3.60x and is not substituted with the CLI value. Revision4 and prior secondary timing numbers above remain historical. Final independent review `speed-first-encoder-20260929-independent-03` passed. See `validation/evidence/speed-first-completion.json` and the archived review for its actual independent execution and limits.


## Faster than libFLAC (active, new acceptance threshold)

The accepted revision7 result is now the performance baseline, not the final target: original12 CLI10.169248150s versus libFLAC-8 1.167633500s (8.709x slower). New work must beat optimized libFLAC separately in single-thread CLI and equivalent truecore timing on original12 and a newly preregistered representative long-audio set, in two independent10-round balanced blocks. Full-file quality budgets retain the originale681 anchor (+1% aggregate/+3% case), including all existing31/145/32 cases. See the active contract in ACCEPTANCE.md.

Earlier candidate attribution was revision3 and cannot describe revision7. A new bound profiler will count coarse/deep/refine work, full-pool/shortlist/backfill residual passes and concrete allocations/copies; generated-C text alone is not evidence of machine-code cost. Earlier libFLAC entries in core reports were CLI wall times; a new test-only native library harness will time equivalent prepared-PCM-to-owned-FLAC lifecycles with full MD5/finish, preserving ordinary compiler/SIMD settings. Neither measurement gap will be hidden by reusing historical numbers. Current work and all new evidence use the `faster-than-libflac` prefix; all accepted earlier data remains intact.


### Active-task diagnostics and structural candidates

`faster-than-libflac/revision7-corrected-coarse.json` profiles the frozen accepted revision7 with nonempty original/instrumented source maps saved before compilation and verified afterward. Earlier profiler manifests had an absolute-path filtering bug; their JSON is preserved and supplementary source inventories are explicitly marked as captured after those runs. The corrected profile, rather than stale revision3 percentages, is the current attribution baseline. Residual planning remains roughly40–60% exclusive attribution on representative active inputs. Candidate3 coarse profiling places CRC at0.60–6.61% on these cases, so CRC alone cannot close the remaining performance gap. Profiling remains shared-host attribution, not uncontended speed evidence.

Candidate1 replaces repeated coarse/refine planning with exact best-relative candidate budgets, shared width statistics and lazily computed quotient prefix columns. The proven Rice optimum lies in at most three parameters, with one extra clipped column when Rice/Rice2 differ. Candidate2 removes bounds checks only where private-loop invariants prove every index, and directly accumulates the single-partition case without N-sized prefixes. Actual .obj disassembly confirms eliminated checks and guarded SIMD code; a matching CRT/CPUID probe establishes hardware eligibility, not a dynamic branch trace. Candidate3 reuses residual scratch while copying winning results, and replaces per-probe division with an exact quotient/remainder position recurrence. Candidate4 shares Q0 sums, omits tree levels whose headers alone cannot win, avoids repeated owned-PCM staging copies, and removes redundant validation only on an internal path reached after validated ingestion.

Candidates1/2 preserved all31+32 quality outputs byte-for-byte. Their unpaired CLI diagnostics7.8447s/9.2036s are not a reliable relative-speed conclusion; a separate CPU8 three-pair core diagnostic showed candidate2 faster in every noise16/AR24 pair. Candidate4 passes all128 tests on all three backends, format/check gates and the retained31/145/32 quality sets. Its one-round original12 diagnostic remains 5.1439 times libFLAC CLI time and 7.7571 times actual native-library core time. Every case still loses. These are diagnostic measurements, not the two-block acceptance gate; the goal remains active.

### Isolated component experiments after stage1 review

The component reports `faster-than-libflac-c4-*-core-ab.json` use CPU8, four balanced A/B rounds, a common batch of three and an internal warmup per process. Builds, validation and other agent CPU work were paused during each measurement sequence. Every output matched the independently validated candidate4 bytes. These small engineering experiments compare against candidate4, not libFLAC, and do not replace final calibrated ten-round blocks.

The proven histogram lower bound was rejected for integration: the order8 version took 1.136 times candidate4 time on recording28; reducing histogram granularity to order4 still took 1.092 times. Both continue to search all legal partition orders; the regression comes from the extra bound machinery, not a quality cap. Original failed/slow results remain available.

The leaf-boundary prefix prototype retains exact costs while storing only partition boundaries and collecting up to three needed quotient columns in one scan. It passes 130 tests on each backend and the 31 independent quality cases with byte identity. Its five-case diagnostic ratios to candidate4 were 0.977 (noise16), 0.785 (AR24), 1.010 (silence), 0.991 (maximum block), and 0.987 (recording28). Small differences are not treated as robust wins.

Fixed predictor specialization uses literal orders1–4 only when `depth + order <= 32`, preserving the generic path elsewhere. It passed 7,040 comparisons per backend and original12 byte identity. Its corresponding ratios were 0.864, 0.958, 1.043, 1.007, and 0.973. The isolated candidate6 combines exact LPC loop interchange with unrolled, fixed-buffer MD5 feed; it passes 128 tests per backend and the 31/32 independent cases with unchanged bytes. Its ratios were 1.002, 0.989, 0.874, 0.846, and 0.923. Production remains candidate4 while further structural experiments are evaluated.

Analytical LPC variance ranking is also experimental. Although the 31 and 32 case sets passed, the retained 145-case matrix found a 4-bit sparse stereo case growing from 480 to 520 bytes (+8.33%). All 145 independent PCM/integrity checks passed, but the single-case size gate failed. This variant is not accepted or integrated; the failed report is retained for diagnosis.

### Stage8: exact wide fixed prediction

C52 replaces the wide-input fixed-order0–4 generic coefficient loop with literal Int64 finite differences, computed in128-value tiles and validated in ascending order. Signed33-bit inputs keep every intermediate within2^36. The first illegal residual, committed prefix, untouched suffix, predictor order, partition search and ties remain unchanged. This revisits the earlier C15 tiled integer approach on current C41 and additionally handles order0; it does not introduce a new compression policy. The private reusable tile adds1024 payload bytes per encoder, excluding allocation overhead. Actual Clang code inspection finds scalar arithmetic, **not SIMD**; the measured result must not be attributed to vectorization.

The selected variant and the actual delivery directory both pass native/JS/wasm-gc check, tests (174 each), release builds and formatting. The retained31/32/145/original12 independent cases remain byte-identical to C41, and both fresh CLI contract suites pass. Public API is unchanged and Encoder remains opaque. Root and frozen CLI/core generated C match after universal newline and physical `#line` normalization only. Root native MSVC artifacts and frozen Clang artifacts remain separately identified; this is not a binary-hash identity claim.

Long8 CLI/core outputs independently pass libFLAC/FFmpeg PCM, CRC/MD5 and byte equality with C41. Their aggregate size remains50,641,622 bytes versus the fixed e681 anchor50,640,556 (ratio1.00002105). Native CLI memory probes retain exact C41 output: stereo16/block32768 peaks are12,873,728 and12,754,944 bytes at2/20 seconds; eight-channel32/block65535 peaks are26,165,248 and26,230,784 bytes at5/60 seconds. Duration growth passes the existing8MiB allowance. The added tile raises the theoretical scratch payload ceiling to10,225,900 bytes; object overhead, other buffers and OS working set are separate. These four probes do not replace the final current-version hour stress or cross-system acceptance. Reports: `faster-than-libflac-c52-long-quality.json`, `faster-than-libflac-c52-memory.json` and `faster-than-libflac-c52-memory-gates.json`.

Serialized CPU8 original12 engineering comparisons retain four balanced rounds (core batch16; CLI includes process and I/O). C52/C41 is **0.976866 core** and **0.979149 CLI**. Maximum-block32/8 is0.935603 core and0.887206 CLI in those respective blocks. All other cases and regressions remain in the reports. These measurements select an incremental optimization; they do not satisfy the final normal-libFLAC-8, two-independent-block acceptance gate.

A fresh one-round diagnostic against normal official single-thread libFLAC-8 measures C52/reference **2.194487 core** and **1.770546 CLI** on their separately frozen original12 domains. Real-audio subsets are4.554953 core and1.626644 CLI. Candidate PCM/integrity/size gates pass and core calibration targets100ms; both speed gates fail. One observed round cannot establish dispersion or final acceptance, and these ratios are not extrapolated from the C41 comparison. The final two independent blocks of at least10 balanced rounds, long-set speed gate, remaining reference curves, current cross-system/hour stress and final independent review remain outstanding. Diagnostic records are `faster-than-libflac-c52-clang-core-diagnostic.json` and `faster-than-libflac-c52-clang-cli-diagnostic.json`.

Other investigations were closed without integration:

| Direction | Evidence and decision |
|---|---|
| C45 typed32-bit input validation | Three-backend175 tests and220 independent cases pass; short screen has no clear benefit. Keep the existing input validation. |
| C46–C49 LPC numerical analysis | Exact reference coefficients demonstrate usable higher-order models missing from the original pool. C47 independently reproduces accumulation-sensitive recursion termination. C48/C49 compensated reductions improve original12 compression; C49 emits packed arithmetic. Both representative speed screens regress, so neither changes the delivered model generator. |
| C50 stronger exact Rice bound | Uses existing sum/count/width statistics, with all-k and exhaustive-plan checks. A sparse-pulse witness avoids all prefix allocation, but the four-case screen regresses2.66–9.65%; not selected. |
| C51/C53 direct MD5 words/interleaved feed | Independent hashlib fixtures and all three backends pass. C53's short screen is promising, but combined C54/C52 original12 core is1.006892. C54/C41 core0.980775 and CLI0.994471 do not justify the extra change; keep delivered MD5 unchanged. |

The core A/B helper now accepts a separately bound complete independent oracle for each role when compressed bytes differ. Schema/negative checks and actual C48/C49 comparisons exercise that path; it still requires PCM, CRC/MD5, format and fixed size-budget verification. One C49 invocation accidentally used the historical default A oracle and correctly stopped on C41's AR24 output; the corrected invocation is a separate retained report. Test-command/count assertion failures are preserved alongside their corrections. The full C52 acceptance process disappeared during a goal-turn transition; the resume verified unchanged source/prebuild manifests and completed-command hashes, then ran only remaining commands. No partial run is represented as a successful complete run.

Primary records: `faster-than-libflac-candidate52-fixed-integer-tiles-acceptance1-acceptance.json`, `faster-than-libflac-candidate52-root-integration.json`, `faster-than-libflac-root-c52-generated-c-comparison.json`, and the `faster-than-libflac-stage8-*-all12.json` comparisons under `validation/evidence`. Candidate-specific numeric, codegen, failed-attempt and selection evidence is grouped under `validation/evidence/faster-than-libflac/candidate45..54-*`.

### Stage7 integrated C41 and reference curve

C41 combines C38's exact unfinished-partition lower bound with C40's caller-side ready guards. Actual root format/check/test/release gates pass on native, JS and wasm-gc (172 tests each), and both fresh native CLI contract suites pass. The retained 220 independent cases remain byte-identical to C34/C10. Long8 independently passes libFLAC/FFmpeg PCM, CRC/MD5 and CLI/core byte identity: 50,641,622 bytes versus the unchanged 50,640,556-byte anchor.

Serialized original12 engineering comparisons use four balanced rounds, CPU8 and batch16 for core. C41/C34 is 0.987324 core and 0.970558 CLI; a direct C41/C40 core comparison is 0.977570. These are observed component/composition comparisons, not a libFLAC victory. Per-case regressions remain in the reports. The root integration changes one private planner module and adds two regression files. A preflight raw-hash difference in `encoder_frame.mbt` was solely CRLF normalization; the root file was preserved. Fresh root and frozen C41 generated C match after removing physical `#line` directives, including indented directives; no C statements were rewritten.

The first full reference curve covers original-core12, normal libFLAC levels0–8, 18 balanced rounds and actual common-batch calibration to at least100ms for every level. Every timed output is independently verified outside timing. Calibration samples met100ms, but75 of1944 later timing batches were below that target; all observations are retained. This is a calibration target, not a guarantee for every later batch. All rounds and calibrations complete, but **no level satisfies both the fixed aggregate+1% and every-file+3% budgets**. Levels6–8 beat the aggregate size anchor, yet the three small silence-containing files fail the per-file gate. For level8, these have42-byte C41 metadata versus86-byte libFLAC metadata (including a40-byte Vorbis-comment payload plus its header); libFLAC's audio frames are smaller. Full-file budgets remain unchanged: metadata and cases are not removed. Normal `-8` remains the mandatory speed reference. This curve measures reference levels only; it supplies no new candidate/reference paired win.

The curve helper now confirms the common batch against all nine levels instead of relying only on a single warmup estimate. Insufficient calibration or smoke/subset rounds cannot produce an eligible reference selection. The original helper is archived; nineteen existing helper checks and an actual deliberately underfilled batch smoke pass. CLI and long reference curves, two independent winning ten-round candidate blocks, final-current cross-system/hour stress and final review remain outstanding.

Official subframe analysis finds a272,780-byte audio-frame gap between C41 and libFLAC-8 on the maximum-block case. C44's test-only full original LPC-pool evaluation on that case and recording1 produces byte-identical C41 output, with independent PCM/MD5/CRC verification. Thus shortlist exclusion does not explain these two outputs; it does not prove which model-generation choice causes the gap. Reference-coefficient evaluation is the next diagnostic. C44 has no timing or production-validation claim. Its initial root-inventory and missing-native-stub harness failures are retained, followed by a clean, source-bound retry. C45's typed32-bit input-check optimization is prepared source only, outside current C41.

Stereo observations are analysis only. C42 keeps all four representation searches and verifies171 newly generated fixtures against frozen C34 and libFLAC, with an independent integer-moment descriptor oracle. Its preregistered low-correlation LR shortcut has four inferred full-file regressions above3%, worst19.962758%; it is rejected. C43's twelve predictable/noisy-channel counterexamples also reject the high-correlation MS shortcut: inferred full-file increases82.19–92.44%. Alternative modes were not emitted; these sizes are inferred from observed exact subframe costs and frame padding. Neither shortcut is in C41. Evidence entry: `validation/evidence/faster-than-libflac-stage7.json`.

### Stage4 integrated C34 (2026-09-30; acceptance remains open)

At stage4, delivered runtime was C34. It combines C24 with C26's word writer, C27's persistent planning scratch and C29's full-container PCM loads. All 220 retained outputs match C10, and actual root tests pass 169/169 on each backend. The stage index is `validation/evidence/faster-than-libflac-stage4.json`.

Serialized original12 engineering measurements use four balanced AB/BA rounds and CPU8. Combined C34/C24 time is 0.902197 for genuine core (common batch16) and 0.871984 for complete CLI process execution. All cases, including regressions, are retained; these component comparisons do not establish superiority to libFLAC. C28's register-resident autocorrelation grouping measured 1.022392 and was rejected. C30 wide fixed Double reuse measured 1.002830; C31 prefix rejection measured 1.004047 on its batch16 repeat. Neither was integrated. C25 remained scalar and stopped at its conditional native gate. C33/C35/C37 are source-only proposals with no validation or speed claim.

Fresh root Clang AVX2 one-round diagnostics bind generated C and original MoonBit sources before/after execution. Core takes 0.217344833s versus libFLAC 0.097223529s (2.235517 times); CLI takes 1.922884200s versus 1.043241800s (1.843182 times). Calibration and quality gates pass, but `acceptance_eligible` is false. The final repeated two-block performance gate remains unmet.

The matched C34 profile is `faster-than-libflac/candidate34-clang-avx2-coarse-profile.json`. Both timing and separate event wrappers explicitly forward shared `plan_scratch`; configuration/source checks and output bytes pass. Planner exclusive instrumented time is 32.07% noise16, 16.22% AR24 and 24.70% recording28. CRC and reserve-copy counters cover the word writer; legacy snapshot counters are not instrumented. `finish` may call the instrumented reserve to shrink storage, then detaches it before returning immutable output. Reserve counts are not a claim about every allocation or copy elsewhere. Attribution is not throughput.

Long8 quality and four affected memory cases pass (`faster-than-libflac-c34-long-quality.json`, `faster-than-libflac-c34-memory.json`). They do not replace final-current hour/RF64 stress, cross-system checks, qualifying libFLAC0–8 comparisons or independent final review.

### Stage5 rejected or neutral follow-ups

Root runtime remains C34. C37 skips exact-zero coefficient products while preserving predictor order and integer results; C35 uses literal exact-Double wide fixed-predictor tiles. C37 passes 163 tests per backend and C35 passes 165, with check/format/release gates. Each passes the retained 220 independent cases with unchanged C34/C10 bytes. Matching Clang core builds pass all12 MSVC-byte/libFLAC checks.

Four-round, batch16, CPU8 original12 core comparisons against C24 give C35 0.992918 and C37 0.999091. Neither establishes a clear improvement, so neither is integrated. C37's earlier default-five diagnostic (1.018388) is also retained; it was not a complete original12 run. The helper now selects all frozen cases by default and explicitly records subsets. These remain engineering measurements, not final libFLAC comparisons.

C31 events-only instrumentation passes all12 byte/configuration/source checks. Completed eligible calls produced 1,294,869 samples, versus 1,956,390 in rejected calls. Broad C36 statistics fusion is deferred because it would add discarded statistics to the latter samples, and C31 already measured neutral. Operation counts are not timing estimates. C33 remains source-only. Evidence: `validation/evidence/faster-than-libflac-stage5.json`.

### Stage6 exact planner candidates

Stage6 kept root C34. C33's sixteen-lag autocorrelation accumulators pass all three backends (163 tests each) and the 220 independent cases, but original12 core AB takes 1.020074 times C24, so it is rejected. Actual assembly keeps the floating accumulators in YMM registers while some integer indices are loaded from the stack; register residency alone did not produce a speedup.

C38 reuses the already-computed lower bound for unfinished partitions when abandoning a losing partition order. An explicit abandoned-level branch prevents incomplete choices from becoming a plan. C39 skips single-partition Rice scanning only when the exact escape cost strictly dominates every Rice parameter; ties retain the old path. C40 avoids the large prefix-builder call when every required positive quotient column is already ready. The original builder, cache invalidation and candidate search remain unchanged.

C38/C39/C40 pass 170/170/171 tests respectively on each backend, all build/check/format gates, and 220 independent cases with unchanged C34/C10 bytes. Matching Clang core builds pass twelve MSVC-byte/libFLAC checks each. C38's initial inventory assertion detected 159 newly materialized SDK files, not changed project source; the original failure and an explicitly after-build dependency inventory are retained. No failed product check was relabelled as passing.

Serialized CPU8 original12, four balanced rounds, batch16 yield C38/C34 0.982913, C39/C34 1.006842 and C40/C34 0.971767. C39 is not integrated: avoiding scans did not improve overall time. C38 and C40 remain isolated pending combined validation. Their ratios must not be multiplied. C41 is a prepared source-only composition; it has no build or timing result yet.

C39's separate event build verifies 151 eligible strict-escape calls covering 1,662,354 of 5,220,402 scanned residuals, with all12 output/source/configuration checks passing. These are frozen core12 inputs encoded by the CLI, not complete CLI-set frequency or throughput. The proposed zero-window branch had no hits and was not implemented. Evidence entry: `validation/evidence/faster-than-libflac-stage6.json`. No new libFLAC timing, final speed acceptance or root integration is claimed.

### Stage3 isolated experiments (2026-09-30; acceptance remains open)

The delivered runtime is now C10; references to production C4 above describe the earlier stage. Independent stage2 review passed C10 correctness and identified documentation corrections, now applied. C10's one-round diagnostics remain 2.753215 times libFLAC CLI time and 3.614815 times libFLAC core time. No faster-than-libFLAC result is claimed.

A new profile binds the frozen C11 source to its actual Clang AVX2 CLI build: `validation/evidence/faster-than-libflac/candidate11-clang-avx2-coarse-profile.json`. Residual planning accounts for 30.20%, 34.28%, and 43.48% exclusive instrumented time on noise16, AR24, and recording28. The accompanying counter-scope supplement distinguishes regular LPC shortlist counters from irregular Rice ranking. These are attribution measurements, not throughput results.

Serialized engineering comparisons use all original12 core inputs, CPU8, four balanced AB/BA rounds, common batch3 and independently validated C10 output hashes. The table reports the sum of per-case median times relative to C11 AVX2; it does not compare against libFLAC or establish final acceptance.

| Isolated change | Time / C11 AVX2 | Decision |
| --- | ---: | --- |
| C14 local quotient cache | 1.13481 | Reject extra work and memory |
| C15 literal wide fixed predictor | 0.98319 | Small measured change |
| C16 readiness bit mask | 0.98610 | Small measured change |
| C17 monotone statistics early exit | 0.98125 | Small measured change |
| C18 UInt64 word writer | 0.96939 | Retain for combined evaluation |
| C20 LPC window cache | 0.99267 | No clear benefit for added state |
| C21 fixed predictor evaluation ordering | 0.81594 | Evaluate combined |
| C22 exact order0 plan before grid refinement | 0.79810 | Evaluate combined |
| C23 FixedArray planner scratch | 1.01537 | No demonstrated benefit |

C21 evaluates every fixed predictor and explicitly restores ascending-order tie priority. C22 uses an exact feasible order0 cost to tighten the existing proven depth bound; it introduces no partition cap. Each listed variant passed its three-backend suite and retained 31/32/145 independent quality gates. C18/C20/C21/C22/C23 additionally passed original12 byte comparisons. The matching identities and per-case observations are in `validation/evidence/faster-than-libflac-stage3-*.json` and the candidate reports. AVX512 experiments showed no stable gain over AVX2. Individual speed ratios cannot be multiplied to predict a combined result.

C24 combines C11, C21 and C22 in an isolated source tree. Its three backends pass 160/160 tests, checks, release builds and formatting; all 220 outputs from 31/32/145 plus original12 match C10 bytes. Its combined four-round core ratio is 0.77776 relative to C11 AVX2, with per-case observations in `faster-than-libflac-stage3-c11-vs-c24-avx2.json`. Root runtime remains C10. Final original12/long8 CLI and core ten-round blocks, the qualifying libFLAC0–8 curve, and final-artifact cross-system/stress checks remain outstanding.

Fresh C24 single-round same-scope diagnostics remain slower than normally optimized libFLAC-8: CLI 2.189360s versus 1.066141s (2.05354 times), genuine core 0.229830s versus 0.089580s (2.56563 times). Independent PCM/CRC/MD5 and size gates pass; both reports explicitly set `acceptance_eligible:false`. These observations establish the remaining gap, not a completed speed gate. Stage evidence: `validation/evidence/faster-than-libflac-stage3.json`.

Independent stage3 review found no confirmed defect in the isolated C24 stage. It verified 136 new CLI cases against C10, fresh MSVC and submitted Clang output, integer libFLAC PCM, hashlib MD5 and `flac -t`; 134 nonmaximum-block cases also passed native FFmpeg checks. Its reports and mathematical oracles are archived under `validation/evidence/faster-than-libflac-review/independent-stage3/`. This is a continue verdict, not final performance acceptance.

The subsequent matched C24 Clang AVX2 profile, `validation/evidence/faster-than-libflac/candidate24-clang-avx2-coarse-profile.json`, binds unchanged source, compiler configuration and two independent instrumentation builds; all ten measured outputs match the frozen CLI. Planner exclusive attribution is 29.37% noise16, 16.22% AR24 and 23.11% recording28. LPC model generation accounts for about 16% on each of these cases. The extracted single-partition helper is included in planner time and must not be added again. Regular shortlist counters remain distinct from irregular Rice ranking. Attribution is not throughput or a controlled speedup measurement.

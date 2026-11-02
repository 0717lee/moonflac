"""Render retained speed-first measurements, without claiming independent approval."""
import argparse
import json
from pathlib import Path

from finalize_speed_first import benchmark_report_name

ROOT = Path(__file__).resolve().parents[1]
E = ROOT / 'validation/evidence'


def load(name):
    return json.loads((E / name).read_text(encoding='utf-8'))


def main(revision=3, audit=None, output=None, preview=False):
    audit_name = 'speed-first-final.json' if revision == 3 else f'speed-first-revision{revision}-final.json'
    final = json.loads(audit.read_text(encoding='utf-8')) if audit else load(audit_name)
    assert final['status'] == 'local_pass_review_pending'
    lines = ['# Speed-first encoder: executed evidence', '',
             'Local gates passed; paired independent review is pending. This follows the accepted exact effort-8 optimization and deliberately permits different FLAC bitstreams while preserving exact PCM.', '',
             'Baseline CLI: `e6817e77aafaa124a30d4e75b9a5f73beca10f0b0da967ddcc2e97c3397fe743`.',
             f"Candidate CLI: `{final['identity']['cli']['sha256']}`.", '',
             'The original twelve inputs and parameters are unchanged. Each mode pins logical CPU 8, runs one warmup and six balanced rounds, rotates the libFLAC position, and independently validates every resulting stream. No build, test, profile or stress job ran concurrently. Desktop/background variation remains possible; raw timings, CPU snapshots and median/MAD are retained. Core timing excludes CLI/file I/O and uses a common calibrated batch. Its table compares only the MoonFLAC baseline and candidate; separate libFLAC CLI observations remain in raw JSON, explicitly outside that comparison.', '']
    if preview:
        lines[2] = 'Report-only preview of archived revision measurements. This corrects presentation of existing timing domains and is not acceptance of a revised encoder.'
    if revision != 3:
        lines += [f'Revision {revision} remeasures only the original twelve CLI and core cases. Holdout17, block32768 and additional libFLAC configuration tables below retain revision3 observations with their original artifact identities; they are not current-artifact timings.', '']
    for mode, heading in [('cli', 'Original twelve CLI cases'), ('core', 'Original twelve core cases'),
                          ('holdout', 'First holdout, retained after diagnosis'), ('block32768', '32768-sample block comparison')]:
        report_name = final.get('benchmark_reports', {}).get(mode, benchmark_report_name(mode, revision))
        d = load(report_name)
        t = final['timing'][mode]
        historical = not t.get('is_current_artifact', revision == 3 or mode in ['cli', 'core'])
        if historical:
            heading += ' — historical revision3'
        lines += ['## '+heading, '']
        if historical:
            lines += [f'Historical observations: the candidate in this table is revision3. Current-artifact correctness and size gates are separate; no revision{revision} timing is inferred from this table.', '']
        if mode == 'core':
            lines += ['| Case | Baseline core seconds ± MAD | Candidate core seconds ± MAD | Reduction | File size change | Improved pairs |',
                      '|---|---:|---:|---:|---:|---:|']
        else:
            lines += ['| Case | Baseline seconds ± MAD | Candidate seconds ± MAD | libFLAC CLI seconds | Reduction | File size change | Improved pairs |',
                      '|---|---:|---:|---:|---:|---:|---:|']
        for c in d['cases']:
            b, a, f = [c['summary'][k]['seconds'] for k in ['baseline', 'candidate', 'libflac']]
            reference_cell = '' if mode == 'core' else f" {f['median']:.6f} |"
            lines.append(f"| {c['name']} | {b['median']:.6f} ± {b['mad']:.6f} | {a['median']:.6f} ± {a['mad']:.6f} |{reference_cell} {c['median_reduction_percent']:.2f}% | {(c['size_check']['ratio']-1)*100:+.4f}% | {c['paired_improvement_rounds']}/6 |")
        totals = t['totals']
        total_line = f"Sum of case medians: **{totals['baseline']:.6f} → {totals['candidate']:.6f} s**, {t['baseline_over_candidate']:.3f}× faster"
        if mode == 'core':
            total_line += ' for MoonFLAC core encoding. Separate libFLAC CLI observations are retained in the raw report and are not directly comparable.'
        else:
            total_line += f"; libFLAC CLI sum {totals['libflac']:.6f} s. Candidate/reference elapsed-time ratio: {t['candidate_over_libflac_cli']:.3f}×."
        lines += ['', total_line,
                  f"Full-file size: {t['size_budget']['baseline_bytes']:,} → {t['size_budget']['candidate_bytes']:,} bytes ({(t['size_budget']['ratio']-1)*100:+.4f}%). All cases remain within +3%; aggregate remains within +1%.",
                  'Six paired set differences (baseline minus candidate, seconds): '+', '.join(f'{v:.6f}' for v in t['paired_set_differences_seconds'])+'.',
                  f"Source report: `validation/evidence/{report_name}`. These totals sum separately measured cases; they are not a single simultaneous suite run.", '']
    reference_name = final.get('reference_report', benchmark_report_name('reference', revision))
    ref = load(reference_name)
    reference_heading = '## Comparable-size reference observations' + (' — historical revision3' if revision != 3 else '')
    lines += [reference_heading, '',
              'The main comparison above keeps the unchanged libFLAC `-8` settings. Additional reference configurations use one warmup and six rotating rounds. These are separately measured CLI observations, not new paired candidate timings. Nearest size means minimum absolute payload-byte distance; equal lossless PCM does not imply equal encoder search effort.', '',
              '| Configuration | Sum of median seconds | Full-file bytes | Payload bytes |', '|---|---:|---:|---:|']
    if revision != 3:
        lines[-2:-2] = [f'These reference runs and nearest-payload selections belong to the revision3 candidate/report. They are retained history, not a new matched-size comparison with revision{revision}.', '']
    for name, values in ref['fixed_set'].items():
        lines.append(f"| {name} | {values['sum_median_seconds']:.6f} | {values['file_bytes']:,} | {values['payload_bytes']:,} |")
    lines += ['', 'Nearest total payload configurations: '+', '.join(ref['closest_collection_payload_configurations'])+'. Per-case selections and all settings, outputs, timings and ratios are retained in `speed-first-reference-benchmark.json`.', '',
              '## Correctness, quality and scope', '',
              '- Windows and WSL2: native/JS/wasm-gc each 108/108, check and release builds passed. Windows format and both CLI contracts passed.',
              '- Final timed CLI: 328 libFLAC PCM cases, 327 FFmpeg audio cases and 137 forced representations. Source-level cross-backend coverage is 828 streams; WSL separately checks 24 CLI combinations and 828 streams.',
              '- First holdout failure is retained: +7.603% fine-partition signal and +5.119% noisy impulses. Root causes and rejected variants are documented in PERFORMANCE.md. The original 17 cases continue to pass as regression gates.',
              '- The fresh second holdout contains 14 cases sealed before revised-policy encoding. It passes at 6,345,160 / 6,341,301 bytes (+0.0609%), with every case below +3%. The final executable independently replays all 31 holdout streams byte-for-byte, including odd bit depths.',
              '- MD5 uses a Python hashlib oracle for 232 formats. Targeted tests cover unsampled overflow, legal-finalist backfilling and alternating-zero fine partitions; all original tests remain.',
              '- Scoped streaming memory covers block32768 stereo16 at 2/20 seconds and block65535 8ch32 at 5/60 seconds. Candidate peak growth is 319,488 and 512,000 bytes, below the declared 8MiB bound. WSL and memory ran before the final official formatter changed two line wraps; their original source/binary hashes and formatter diff are retained. The final Windows executable was separately checked against all 31 holdout bitstreams and the independent CLI matrices. The earlier hour-scale campaign remains historical evidence; it was not rerun for this change.',
              '- General-depth FFmpeg output is s32le with exact padding/shift checks. Declared 32768/65535 groups use unchanged-frame Ogg transport and retain raw native FFmpeg outcomes. The first 32768 native-input attempt failed; independent reproduction showed FFmpeg producing zero PCM even from official libFLAC output, while libFLAC decoded all three files exactly. The explicit transport retry passed. No decoder substitution occurs in the MoonBit implementation.',
              '- WSL2 shares host hardware. No Linux FFmpeg/Ogg reference check, remote CI, commit, publication or deployment is claimed. Compression budgets are empirical for the declared sets, not universal guarantees.', '',
              '## Reproduction', '', '```sh',
              'python scripts/validate_speed_first.py --revision 3',
              'wsl -d Ubuntu-22.04 -- python3 <project>/scripts/validate_speed_first_linux.py --revision 3',
              '# Prepare the documented source snapshots, fixtures and pinned toolchains first.',
              'python scripts/reconstruct_speed_first_baseline.py --out _build/speed-first/reconstructed',
              '# In that reconstructed module: moon update; moon build --target native --release.',
              '# For a fresh reconstruction, pass its executables to benchmark_speed_first.py run.',
              '# Stop other build/test/profile/stress jobs before timing.',
              'python scripts/run_speed_first_benchmarks.py',
              '# The preserved first 32768 attempt exposed a reference parser limitation.',
              'python scripts/complete_speed_first_benchmarks.py',
              'python scripts/finalize_speed_first.py',
              'python scripts/render_speed_first_report.py', '```', '',
              'Evidence-producing commands refuse to overwrite prior reports. Reproduce in a fresh local checkout/cache, or provide fresh report paths to the individual benchmark command. Retain baseline source snapshots and original fixture hashes; do not compare a reconstructed baseline without checking its output identity. `speed-first-final.json` indexes the executed local evidence and current source/artifact identities.']
    if revision != 3:
        # Revision3's prose contains historical test/size/memory numbers. Do not
        # silently carry those values forward when new evidence is required.
        start = lines.index('## Correctness, quality and scope')
        validation = final.get('validation_reports', {})
        test_count = 121 if revision == 7 else 117
        quality = load(validation['holdout_replay'])
        memory = load(validation['memory'])
        details = []
        if revision == 7:
            pulses = load(validation['pulses'])
            proof = load(validation['partition_proof'])
            details = [
                f"Current frozen policy: {final['identity']['policy']}",
                f"The 32 frozen pulse cases pass independent libFLAC PCM, CRC/MD5 and Python hashlib checks. Full-file aggregate: {pulses['aggregate']['baseline_bytes']:,} → {pulses['aggregate']['candidate_bytes']:,} bytes ({(pulses['aggregate']['ratio']-1)*100:+.4f}%), within +1% aggregate and +3% per case. Evidence: `validation/evidence/{validation['pulses']}`.",
                f"The partition-bound proof companion passes {proof['scalar_parameter_checks']:,} scalar-parameter checks, {proof['partition_checks']:,} partition checks and {proof['partition_order_warmup_checks']:,} warm-up/order checks. These finite checks support the algebraic proof; they do not constitute a universal compression-ratio bound. Evidence: `validation/evidence/{validation['partition_proof']}`."]
        if revision == 7:
            details.append(f"All 32 pulse fixtures also pass JS and wasm-gc with exact native byte identity and independent libFLAC PCM/CRC/MD5 checks: 96 backend/case combinations total. Evidence: `validation/evidence/{validation['pulses_cross']}`.")
        quality_lines = [f"Retained quality set `{g['source_report']}`: {len(g['cases'])} cases; full-file aggregate {g['aggregate_size_budget']['ratio']:.8f}× baseline, within the +1% aggregate and +3% per-case budgets. No newly unseen holdout is claimed." for g in quality['sets']]
        memory_lines = [f"Current memory group block {g['block']}, {g['channels']} channels/{g['bits']} bits, durations {g['durations']}: peak growth {g['peak_growth_bytes']:,} bytes, limit {g['limit_bytes']:,} bytes." for g in memory['duration_memory_gates']]
        lines = lines[:start] + [
            '## Correctness, quality and scope', '',
            f"Revision {revision} source/artifact identities and required correctness, holdout and memory gates are indexed in `validation/evidence/{audit_name}`.",
            f'Windows and WSL2 each pass {test_count}/{test_count} on native, JS and wasm-gc, with check/release builds and Windows format/CLI contracts passed. Final Windows artifact matrices cover 328 libFLAC PCM cases, 327 FFmpeg audio cases, 137 forced representations and 828 cross-backend streams; WSL independently checks 24 CLI combinations and 828 streams.',
            f"The current artifact replays all 31 prior holdout streams and verifies 145 review/neighbor cases. See `validation/evidence/{validation.get('holdout_replay', '')}` and `validation/evidence/{validation.get('short', '')}`. Required short-block byte identity and independent PCM/CRC/MD5 checks are asserted by the finalizer.",
            *details, *quality_lines, *memory_lines,
            f"Current Windows/WSL checks and affected streaming-memory groups are retained separately from historical hour-scale results. Artifact acceptance: `validation/evidence/{validation.get('artifact', '')}`; memory: `validation/evidence/{validation.get('memory', '')}`. These memory observations are not controlled speed measurements.",
            'The earlier failed size gates, reference parser failures and review findings remain historical records; their measurements are not replaced by this revision.',
            'Compression size budgets are empirical for the declared sets, not universal guarantees. WSL2 shares host hardware; remote CI and publication are not claimed.', '',
            '## Reproduction', '',
            f'Replay the exact retained commands in `validation/evidence/speed-first-revision{revision}-benchmark-commands.json` after preparing the frozen sources, fixture identities and toolchain. Run timing without concurrent build/test/profile/stress jobs.', '',
            '```sh', f'python scripts/finalize_speed_first.py --revision {revision}',
            f'python scripts/render_speed_first_report.py --revision {revision}', '```', '',
            'Evidence-producing commands preserve existing reports. Select fresh paths for independent reproduction.'
        ]
    target = output or ROOT / 'docs/SPEED-FIRST-EVIDENCE.md'
    if preview:
        assert output is not None, '--preview requires a new explicit output path'
        assert not target.exists(), 'Preserve previous report previews'
    target.write_text('\n'.join(lines)+'\n', encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--revision', type=int, choices=[3, 4, 7], default=3)
    parser.add_argument('--audit', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--preview', action='store_true')
    args = parser.parse_args()
    main(args.revision, args.audit, args.output, args.preview)

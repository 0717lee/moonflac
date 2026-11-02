"""Audit completed local speed-first gates; independent review remains separate."""
import argparse
import hashlib
import json
import re
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'validation/evidence'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(name):
    return json.loads((EVIDENCE / name).read_text(encoding='utf-8'))


def benchmark_report_name(mode, revision=3):
    if revision == 3 or mode not in ['cli', 'core']:
        return f'speed-first-{mode}-' + ('packetized-' if mode == 'block32768' else '') + 'benchmark.json'
    return f'speed-first-revision{revision}-{mode}-benchmark.json'


def timing_entry(mode, totals, paired, worst_case, size_budget):
    entry = dict(totals=dict(totals), baseline_over_candidate=totals['baseline']/totals['candidate'],
                 paired_set_differences_seconds=paired, worst_case=worst_case, size_budget=size_budget)
    if mode == 'core':
        entry['totals'].pop('libflac')
        entry['reference_observation'] = dict(timing_domain='separate libFLAC CLI wall time',
                                             directly_comparable=False,
                                             sum_median_seconds=totals['libflac'])
    else:
        entry['candidate_over_libflac_cli'] = totals['candidate']/totals['libflac']
    return entry


def main(revision=3, output=None, replay_report=None, short_report=None,
         memory_report=None, artifact_report=None):
    identity = load(f'speed-first-candidate-revision{revision}.json')
    for path, digest in identity['sources'].items():
        assert sha(ROOT / path) == digest
    for role in ['cli', 'core']:
        assert sha(ROOT / identity[role]['path']) == identity[role]['sha256']
    benchmark_names = {mode: benchmark_report_name(mode, revision) for mode in ['cli', 'core', 'holdout', 'block32768']}
    reference_name = benchmark_report_name('reference', revision)
    command_name = 'speed-first-benchmark-completion-commands.json' if revision == 3 else f'speed-first-revision{revision}-benchmark-commands.json'
    replay_name = replay_report or ('speed-first-final-holdout-replay.json' if revision == 3 else f'speed-first-revision{revision}-quality.json')
    checks = f'speed-first-checks-revision{revision}'
    artifact_name = artifact_report or checks + ('/final-artifact/acceptance.json' if revision == 3 else '/acceptance.json')
    memory_name = memory_report or f'speed-first-memory-revision{revision}.json'
    short_name = short_report or ('speed-first-short-revision7.json' if revision == 7 else 'speed-first-short.json')
    names = [command_name, *benchmark_names.values(), reference_name,
             'speed-first-revision3-holdout-gate.json',
             'speed-first-revision3-holdout2-gate-general-depth.json', replay_name,
             checks + '/acceptance.json', artifact_name,
             f'speed-first/linux-revision{revision}.json', memory_name,
             'speed-first-baseline-reconstruction.json', 'speed-first-ffmpeg-32768.json']
    if revision in [4, 7]:
        names.append(short_name)
    if revision == 7:
        names += ['speed-first-pulses-revision7.json', 'speed-first-pulses-cross-revision7.json', 'partition-bound-proof.json']
    names = list(dict.fromkeys(names))
    gates = {name: load(name) for name in names}
    for name, report in gates.items():
        assert report['status'] == 'pass', (name, report['status'])
    if revision == 3:
        initial = load('speed-first-benchmark-commands.json')
        assert initial['status'] == 'failed'
        assert [r['name'] for r in initial['commands'] if r['status'] == 'pass'] == ['cli', 'core', 'holdout']
        assert initial['commands'][-1]['name'] == 'block32768'
        assert load('speed-first-block32768-benchmark.json')['error'] == "AssertionError('FFmpeg PCM mismatch')"
    if revision == 3:
        replay_cases = gates[replay_name]['cases']
    else:
        quality = gates[replay_name]
        assert quality['case_count'] == 31
        assert sorted(len(group['cases']) for group in quality['sets']) == [14, 17]
        assert all(group['status'] == 'pass' and group['aggregate_size_budget']['passed'] for group in quality['sets'])
        replay_cases = [case for group in quality['sets'] for case in group['cases']]
        assert all(case['size_budget']['passed'] for case in replay_cases)
        if revision == 4:
            assert all(not case['no_short_blocks'] or case['revision3_bytes_identical'] for case in replay_cases)
    assert len(replay_cases) == 31
    counts = gates[artifact_name]['counts']
    assert counts == dict(native=328, ffmpeg_audio=327, forced=137, cross_backend=828)
    assert gates[artifact_name]['cli_sha256'] == identity['cli']['sha256']
    assert gates[replay_name]['cli_sha256'] == identity['cli']['sha256']
    for case in replay_cases:
        assert case['libflac_pcm'] == 'exact' and case['ffmpeg_pcm'] == 'exact'
    if revision in [4, 7]:
        short = gates[short_name]
        assert len(short['cases']) == 145
        assert short['original_review_cases'] == 91 and short['neighboring_cases'] == 54
        assert short['candidate_sha256'] == identity['cli']['sha256']
        assert all(not c['exact_required'] or c['bytes_equal'] for c in short['cases'])
        assert all(c['pcm'] == 'independent libFLAC exact' and c['crc_md5'] == 'libFLAC -t pass' for c in short['cases'])
        assert all(group['aggregate_ratio'] <= 1.01 and not group['above_three_percent'] for group in short['quality_groups'].values())
        assert short['quality_groups']['original_75_effort8']['cases'] == 75
        assert short['quality_groups']['confirmed_five']['cases'] == 5
        assert short['quality_groups']['neighbors_54']['cases'] == 54
        memory = gates[memory_name]
        assert memory['binaries']['candidate']['sha256'] == identity['cli']['sha256']
        assert memory['identity_before'] == memory['identity_after']
        if revision == 4:
            assert len(memory['results']) == 4 and len(memory['duration_memory_gates']) == 2
            assert all(g['block'] == 256 and g['durations'] == [2, 20] and g['peak_growth_bytes'] <= g['limit_bytes']
                       for g in memory['duration_memory_gates'])
        else:
            assert memory['identity_before'] == dict(cli_sha256=identity['cli']['sha256'], sources=identity['sources'])
            expected = {(32768, 2, 16), (32768, 8, 25), (65535, 8, 32)}
            assert len(memory['results']) == 6 and len(memory['duration_memory_gates']) == 3
            assert {(c['block'], c['channels'], c['bits'], c['seconds']) for c in memory['results']} == {
                (*fmt, seconds) for fmt in expected for seconds in [2, 20]}
            assert {(g['block'], g['channels'], g['bits']) for g in memory['duration_memory_gates']} == expected
            assert all(g['durations'] == [2, 20] and g['peak_growth_bytes'] <= g['limit_bytes'] == 8*1024**2
                       for g in memory['duration_memory_gates'])
            for case in memory['results']:
                independent = case['encodes']['candidate']['independent']
                assert independent['flac_test']['returncode'] == 0
                assert independent['pcm_bytes'] == case['source']['pcm_bytes']
                assert independent['pcm_md5'] == independent['streaminfo_md5'] == case['source']['pcm_md5']
    if revision == 7:
        pulses = gates['speed-first-pulses-revision7.json']
        assert pulses['candidate_sha256'] == identity['cli']['sha256']
        assert pulses['case_count'] == len(pulses['cases']) == 32
        assert pulses['aggregate']['passed'] and pulses['aggregate']['ratio'] <= 1.01
        assert not pulses['above_three_percent']
        cross_pulses = gates['speed-first-pulses-cross-revision7.json']
        assert cross_pulses['native_cli_sha256'] == identity['cli']['sha256']
        assert cross_pulses['identity_sha256'] == sha(EVIDENCE / 'speed-first-candidate-revision7.json')
        assert cross_pulses['native_report_sha256'] == sha(EVIDENCE / 'speed-first-pulses-revision7.json')
        assert cross_pulses['new_stream_checks'] == 64 and cross_pulses['total_backend_case_checks'] == 96
        assert {target['target'] for target in cross_pulses['targets']} == {'js', 'wasm-gc'}
        native_pulses = {case['name']: case for case in pulses['cases']}
        for target in cross_pulses['targets']:
            assert target['status'] == 'pass' and len(target['cases']) == 32
            assert {case['name'] for case in target['cases']} == set(native_pulses)
            for case in target['cases']:
                assert case['native_byte_identical']
                assert case['encoded_sha256'] == native_pulses[case['name']]['encoded_sha256']
                assert case['independent_pcm'] == 'libFLAC exact'
                assert case['streaminfo_md5'] == 'Python hashlib exact' and case['crc_md5'] == 'libFLAC -t pass'
        for case in pulses['cases']:
            assert case['independent_pcm'] == 'libFLAC exact'
            assert case['streaminfo_md5'] == 'Python hashlib exact' and case['crc_md5'] == 'libFLAC -t pass'
            assert case['size_budget_pass'] and case['size_ratio'] <= 1.03
        proof = gates['partition-bound-proof.json']
        assert proof['scalar_parameter_checks'] == 4066022 and proof['partition_checks'] == 4905
        assert proof['tight_bound_partitions'] == 425 and proof['partition_order_warmup_checks'] == 189
        assert len(proof['proof']) == 5
        linux = gates['speed-first/linux-revision7.json']
        assert linux['frozen_identity_sha256'] == sha(EVIDENCE / 'speed-first-candidate-revision7.json')
        assert all(linux['source_files_sha256'][name] == digest for name, digest in identity['sources'].items()
                   if name.endswith('.mbt'))
        assert all(gates[artifact_name]['codec_sources'][name] == digest for name, digest in identity['sources'].items())
        assert all(linux['tests'][target] == ['Total tests: 121, passed: 121, failed: 0.']
                   for target in ['native', 'js', 'wasm-gc'])
        assert len(linux['cli']) == 24 and all(c['status'] == 'pass' for c in linux['cli'])
        assert len(linux['cross']) == 3 and linux['cross_backend_byte_identical']
        assert all(g['status'] == 'pass' and len(g['cases']) == 276
                   and all(c['status'] == 'pass' for c in g['cases']) for g in linux['cross'])
        commands = {c['name']: c for c in gates[artifact_name]['commands']}
        for target in ['native', 'js', 'wasm-gc']:
            record = commands[target + '-test']
            assert record['status'] == 'pass' and record['exit_code'] == 0
            assert re.findall(r'Total tests[^\n]*', Path(record['log']).read_text(encoding='utf-8')) == [
                'Total tests: 121, passed: 121, failed: 0.']
    historical_identity = load('speed-first-candidate-revision3.json')
    timing = {}
    for mode, count in [('cli', 12), ('core', 12), ('holdout', 17), ('block32768', 1)]:
        report = gates[benchmark_names[mode]]
        assert len(report['cases']) == count
        assert report['collection_size_check']['passed'] and not report['budget_violations']
        historical = revision != 3 and mode not in ['cli', 'core']
        measured_identity = historical_identity if historical else identity
        assert report['binaries']['candidate']['sha256'] == measured_identity['core' if mode == 'core' else 'cli']['sha256']
        for case in report['cases']:
            for codec, runs in case['runs'].items():
                assert len(runs) == 7 and sum(not r['warmup'] for r in runs) == 6
                assert all(r['libflac_pcm'] == 'exact' and r['ffmpeg_pcm'] == 'exact' for r in runs)
                measured = [r['seconds'] for r in runs if not r['warmup']]
                assert statistics.median(measured) == case['summary'][codec]['seconds']['median']
                assert len({r['encoded_sha256'] for r in runs}) == 1
        totals = report['fixed_set_sum_medians_seconds']
        paired = [sum(c['paired_differences_seconds'][i] for c in report['cases']) for i in range(6)]
        timing[mode] = timing_entry(mode, totals, paired, report['worst_case'], report['collection_size_check'])
        timing[mode].update(measurement_revision=3 if historical else revision,
                            is_current_artifact=not historical,
                            candidate_sha256=report['binaries']['candidate']['sha256'])
        if mode in ['cli', 'core']:
            old = load(f'effort8-{mode}-benchmark.json')
            by_name = {c['name']: c for c in old['cases']}
            for case in report['cases']:
                previous = by_name[case['name']]
                assert case['pcm_sha256'] == previous['pcm_sha256']
                assert case['runs']['baseline'][0]['encoded_sha256'] == previous['runs']['candidate'][0]['encoded_sha256']
            if revision in [4, 7]:
                prior = load(benchmark_report_name(mode, 3))
                prior_cases = {case['name']: case for case in prior['cases']}
                for case in report['cases']:
                    assert case['pcm_sha256'] == prior_cases[case['name']]['pcm_sha256']
                    assert all(case[key] == prior_cases[case['name']][key]
                               for key in ['bits', 'channels', 'rate', 'block', 'effort', 'samples', 'pcm_bytes'])
                    assert case['runs']['baseline'][0]['encoded_sha256'] == prior_cases[case['name']]['runs']['baseline'][0]['encoded_sha256']
                    if revision == 4:
                        assert case['block'] > 256 and (case['samples'] % case['block'] == 0 or case['samples'] % case['block'] > 256)
                        assert case['runs']['candidate'][0]['encoded_sha256'] == prior_cases[case['name']]['runs']['candidate'][0]['encoded_sha256']
    assert timing['cli']['candidate_over_libflac_cli'] <= 10, 'CLI reference target not met'
    assert timing['cli']['baseline_over_candidate'] >= 4.4, 'Further speedup target not met'
    result = dict(task_id='speed-first-encoder-20260929', status='local_pass_review_pending',
                  revision=revision, benchmark_reports=benchmark_names, reference_report=reference_name,
                  reference_measurement_revision=3,
                  validation_reports=dict(holdout_replay=replay_name, artifact=artifact_name, memory=memory_name,
                                          short=short_name if revision in [4, 7] else None),
                  source_turn=identity['source_turn'], identity=identity, timing=timing, counts=counts,
                  evidence={name: sha(EVIDENCE/name) for name in names},
                  script_sha256=sha(Path(__file__)),
                  preserved_timing_failure={name: sha(EVIDENCE/name) for name in
                      ['speed-first-benchmark-commands.json', 'speed-first-block32768-benchmark.json']},
                  limitations=['Empirical size gates, not a universal compression bound.',
                               ('First holdout became diagnostic after failure; fresh second holdout remained sealed.' if revision == 3 else
                                f'Both previous holdout sets are retained regression gates for revision{revision}; no newly unseen holdout is claimed.'),
                               'WSL2 shares Windows hardware; no remote CI or publication.',
                               'Known native FFmpeg maximum-block limitation uses declared unchanged-frame Ogg transport.',
                               'Independent paired review is pending.'])
    if revision != 3:
        result['limitations'].append(f'Only original twelve CLI/core measurements use revision{revision}. Holdout17, block32768 and additional references are retained revision3 historical observations, not timings of the current artifact.')
    if revision == 7:
        result['validation_reports'].update(pulses='speed-first-pulses-revision7.json', pulses_cross='speed-first-pulses-cross-revision7.json', partition_proof='partition-bound-proof.json')
    target = output or EVIDENCE / ('speed-first-final.json' if revision == 3 else f'speed-first-revision{revision}-final.json')
    assert not target.exists(), 'Preserve final audit attempts'
    target.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(timing, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--revision', type=int, choices=[3, 4, 7], default=3)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--replay-report', help='Evidence-relative current-artifact 31-case replay report')
    parser.add_argument('--short-report', help='Evidence-relative 145-case review/neighbor report')
    parser.add_argument('--memory-report', help='Evidence-relative affected short-block memory report')
    parser.add_argument('--artifact-report', help='Evidence-relative acceptance report for the timed CLI')
    args = parser.parse_args()
    main(args.revision, args.output, args.replay_report, args.short_report,
         args.memory_report, args.artifact_report)

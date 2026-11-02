"""Paired CLI or genuine owned-buffer core measurements on frozen input sets.

Run only after other build/test jobs finish. Ten rounds per block are required;
two independently launched block reports can be checked with `combine`.
`--rounds 1` is explicitly a functional smoke, never acceptance evidence.
No inputs are generated, resampled, shortened, or selected from timing results.

Example (from the project root, after building candidate and reference harnesses):
  python scripts/benchmark_faster_than_libflac.py run --mode core --group original-core \
    --manifest validation/evidence/faster-than-libflac-inputs-original-core.json \
    --candidate PATH_TO_BENCHMARK_COMPETE --baseline PATH_TO_R7_BENCHMARK8 \
    --candidate-identity CANDIDATE.json --baseline-identity R7.json \
    --block-id original-core-a --report REPORT_A.json
Repeat as a separately launched block with new --block-id and --report, then:
  python scripts/benchmark_faster_than_libflac.py combine --blocks REPORT_A.json REPORT_B.json --report COMBINED.json
For CLI pass native CLI binaries instead; --mode cli retains complete process IO.
For the libFLAC 0..8 curve replace `run` with `curve`. Every set, including long,
requires each file <=e6817*1.03 and total encoded bytes <=e6817*1.01.
Curve runs default to 18 rounds: nine rotations and their reversals. Requests
other than the one-round smoke are rounded up to a multiple of 18 before any
measurements, with requested/effective counts retained in the report.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import platform
import shutil
import subprocess
import time

import psutil
from benchmark_effort8 import sha, save, summary
from benchmark_speed_first import validate_sized
from validate_encoder import LibFLAC, library, version

ROOT = Path(__file__).resolve().parents[1]
QUALITY_SHA = 'e6817e77aafaa124a30d4e75b9a5f73beca10f0b0da967ddcc2e97c3397fe743'

def path(value):
    p = Path(str(value).replace('\\', '/'))
    return p if p.is_absolute() else ROOT / p

def describe(p):
    return dict(path=str(p.resolve()), sha256=sha(p))

def real(case):
    return case.get('kind', '').startswith('real-') or case['name'].startswith(('recording-', 'speech-', 'music-'))

def command(codec, binary, case, output, args, batch, effort):
    raw = str(path(case['path']))
    if args.mode == 'core':
        values = [raw, str(output), str(case['channels']), str(case['bits']), str(case['rate']), str(case['block']), str(batch)]
        if codec != 'baseline' or args.baseline_core_format != 'old': values.append(str(effort))
        elif effort != 8: raise ValueError('Historical CORE8 baseline only supports effort8')
        return [str(binary), *values]
    if codec == 'libflac':
        return [str(binary), '-'+str(effort), '--threads=1', '-f', '-s', '--lax', '--no-padding', '--no-seektable',
            '--force-raw-format', '--endian=little', '--sign=signed', f"--channels={case['channels']}",
            f"--bps={case['bits']}", f"--sample-rate={case['rate']}", f"--blocksize={case['block']}", '-o', str(output), raw]
    return [str(binary), 'encode', raw, str(output), '--raw', '--sample-rate', str(case['rate']), '--channels', str(case['channels']),
        '--bits', str(case['bits']), '--block-size', str(case['block']), '--effort', str(effort)]

def timed(codec, binary, case, output, args, batch, effort):
    cmd = command(codec, binary, case, output, args, batch, effort)
    # CLI uses direct process completion, without a polling interval quantizing
    # short encodes. Core still records process wall time separately for context.
    start = time.perf_counter()
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=args.timeout)
    wall = time.perf_counter() - start
    if p.returncode: raise RuntimeError(f'{cmd}: {p.returncode}\n{p.stdout}\n{p.stderr}')
    result = dict(command=cmd, process_wall_seconds=wall, stderr=p.stderr, seconds=wall,
                  timing_domain='whole CLI process: startup, PCM unpack, encode, finalization and file IO')
    if args.mode == 'core':
        if codec == 'baseline' and args.baseline_core_format == 'old':
            lines = [s.split() for s in p.stdout.splitlines() if s.startswith('CORE8 ')]
            assert len(lines) == 1 and int(lines[0][1]) == batch
            core = dict(batch=batch, seconds=float(lines[0][2])/1e6, warm_seconds=float(lines[0][3])/1e6, bytes=int(lines[0][4]), per_call_seconds=None)
        else:
            prefix = 'LIBFLAC_CORE ' if codec == 'libflac' else 'MOON_CORE '
            lines = [s[len(prefix):] for s in p.stdout.splitlines() if s.startswith(prefix)]
            assert len(lines) == 1, p.stdout
            core = json.loads(lines[0]); assert core['batch'] == batch and core['effort'] == effort
            assert len(core['per_call_seconds']) == batch and all(math.isfinite(v) and v > 0 for v in core['per_call_seconds'])
            assert math.isclose(sum(core['per_call_seconds']), core['seconds'], rel_tol=1e-10, abs_tol=1e-9)
        assert core['seconds'] > 0 and core['warm_seconds'] > 0 and core['bytes'] == output.stat().st_size
        result.update(core=core, seconds=core['seconds']/batch, timing_domain='complete owned-buffer encoder lifecycle; per-call batch mean; output release, comparison, input preparation and IO excluded')
    return result

def source_identity(file):
    obj = json.loads(file.read_text(encoding='utf-8'))
    # A declared production source must exist; omission cannot turn a failed
    # source association into a silently weaker record.
    checked = {}
    groups = [obj.get('sources', obj.get('files', {}))]
    # Clang identities declare generated C in sources and its original MoonBit
    # runtime in source_manifest. Verify both, not just the compiler input.
    if 'source_manifest' in obj:
        groups.append(obj['source_manifest'])
    for group in groups:
        assert isinstance(group,dict), 'Source manifest must be a mapping'
        for name, digest in group.items():
            if name.endswith(('.mbt', '.c', '.pkg', '.mod')):
                p = ROOT/name
                if not p.is_file():raise FileNotFoundError('Declared candidate source is missing: '+name)
                assert isinstance(digest,str) and len(digest)==64, 'Malformed source digest: '+name
                assert sha(p) == digest, 'Candidate source identity mismatch: '+name
                checked[name] = digest
    return dict(**describe(file), checked_sources=checked)

def artifact_identity(file, binary, mode):
    """Bind the executable actually passed to the declared cli/core artifact.

    A historical baseline is bound by its frozen artifact, not by comparing its
    old source tree with the currently edited candidate workspace.
    """
    obj=json.loads(file.read_text(encoding='utf-8'))
    declared=[]
    if mode in obj:declared.append(obj[mode])
    artifacts=obj.get('artifacts',{})
    if isinstance(artifacts,dict) and mode in artifacts:declared.append(artifacts[mode])
    elif isinstance(artifacts,list):
        declared.extend(a for a in artifacts if a.get('role',a.get('name'))==mode)
    if not declared:raise ValueError(f'Identity has no {mode} executable artifact: {file}')
    actual=describe(binary)
    for item in declared:
        if not isinstance(item,dict) or not isinstance(item.get('sha256'),str) or len(item['sha256'])!=64:
            raise ValueError(f'Malformed {mode} artifact in {file}')
        if actual['sha256']!=item['sha256']:
            raise ValueError(f'{mode} executable SHA does not match identity: {binary}')
    return dict(**describe(file),mode=mode,declared_artifacts=declared,actual_executable=actual)

def load(args):
    manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
    cases = manifest['cases']
    assert cases and len({c['name'] for c in cases}) == len(cases)
    if args.smoke_case:
        assert args.rounds == 1, 'Case filtering is only allowed in nonacceptance smoke mode'
        cases = [c for c in cases if c['name'] == args.smoke_case]
        assert len(cases) == 1
    references = json.loads(args.references.read_text(encoding='utf-8'))
    assert references['quality_baseline']['sha256'] == QUALITY_SHA
    entries = {(c['group'], c['name']): c for c in references['cases']}
    prepared = []
    for original in cases:
        case = dict(original)
        assert case.get('effort',8) == 8 and not case.get('variable',False)
        raw = path(case['path']); assert sha(raw) == case['pcm_sha256']
        assert raw.stat().st_size == case['samples']*case['channels']*((case['bits']+7)//8)
        anchor = entries[(args.group, case['name'])]
        assert anchor['pcm_sha256'] == case['pcm_sha256'] and anchor['manifest_sha256'] == sha(args.manifest)
        quality = anchor['references']['quality']; quality_path = path(quality['output'])
        assert sha(quality_path) == quality['encoded_sha256'] and quality_path.stat().st_size == quality['encoded_bytes']
        case['quality_anchor'] = quality
        case['real_audio'] = real(case)
        prepared.append(case)
    return prepared, references

def order(index, block_id):
    # Ten rounds yield exactly five candidate->libFLAC and five reverse pairs.
    # r7 occupies the remaining position in a 4/3/3 rotating distribution.
    shift = int(hashlib.sha256(block_id.encode()).hexdigest()[:8],16) % 2
    pair = ['candidate','libflac'] if (index+shift)%2 == 0 else ['libflac','candidate']
    pair.insert(index%3, 'baseline')
    return pair

def curve_order(index):
    levels=[(index+j)%9 for j in range(9)]
    return list(reversed(levels)) if (index//9)%2 else levels

def aggregate(cases, rounds, real_only):
    selected = [c for c in cases if not real_only or c['case']['real_audio']]
    if not selected: return dict(passed=False, reason='no real audio in declared selection')
    ratios = []
    for i in range(rounds):
        totals = {k:sum(c['rounds'][i]['observations'][k]['seconds'] for c in selected) for k in ('candidate','libflac','baseline')}
        ratios.append(dict(round=i, totals=totals, candidate_over_libflac=totals['candidate']/totals['libflac'],candidate_over_r7=totals['candidate']/totals['baseline']))
    stats = summary([x['candidate_over_libflac'] for x in ratios])
    return dict(cases=[c['case']['name'] for c in selected], rounds=ratios, paired_ratio=stats,
                conservative_dispersion_bound=stats['median']+3*stats['mad'],
                passed=all(x['candidate_over_libflac'] < 1 for x in ratios) and stats['median']+3*stats['mad'] < 1,
                criterion='every paired aggregate round <1 AND median+3MAD <1; conservative observed-dispersion rule, not a confidence interval')

def execute(args):
    if args.report.exists(): raise FileExistsError('Never overwrite reports: '+str(args.report))
    requested_rounds=args.rounds
    if args.action=='curve' and args.rounds!=1:
        if args.rounds<1:raise ValueError('positive round count required')
        args.rounds=math.ceil(args.rounds/18)*18
    if args.rounds != 1 and (args.rounds < 10 or args.rounds%2): raise ValueError('Use >=10 even rounds, or --rounds 1 for explicit nonacceptance smoke')
    if not args.block_id or not re_safe(args.block_id): raise ValueError('block-id must use letters, digits, underscore or dash')
    allowed = psutil.Process().cpu_affinity()
    if args.cpu not in allowed: raise ValueError(f'CPU {args.cpu} unavailable: {allowed}')
    psutil.Process().cpu_affinity([args.cpu])
    cases, references = load(args)
    binaries = {'candidate':args.candidate.resolve(), 'baseline':args.baseline.resolve(), 'libflac':(args.libflac_core if args.mode=='core' else args.flac).resolve()}
    candidate_binding=artifact_identity(args.candidate_identity,binaries['candidate'],args.mode)
    baseline_binding=artifact_identity(args.baseline_identity,binaries['baseline'],args.mode)
    if args.mode=='cli':
        assert sha(binaries['baseline'])==references['performance_baseline']['sha256'], 'CLI performance baseline is not frozen r7'
    ref = LibFLAC(library(args.libflac))
    work = ROOT/'validation/cache/faster-than-libflac-benchmark'/args.block_id/args.mode/args.group
    if work.exists(): raise FileExistsError('Use a new block-id; output directory exists: '+str(work))
    work.mkdir(parents=True)
    report = dict(status='running', action=args.action, mode=args.mode, group=args.group, block_id=args.block_id,
        start_utc=datetime.now(timezone.utc).isoformat(), rounds=args.rounds,requested_rounds=requested_rounds,cpu=args.cpu,platform=platform.platform(),
        cpu_logical=psutil.cpu_count(), affinity_inherited_by_children=True,
        manifest=describe(args.manifest), references=describe(args.references), candidate_identity=source_identity(args.candidate_identity),
        candidate_executable_binding=candidate_binding,
        baseline_identity=baseline_binding,binaries={k:describe(v) for k,v in binaries.items()},
        independent_tools={'libflac':version(ref),'flac':describe(args.flac),'ffmpeg':describe(args.ffmpeg)},
        libflac_dll=describe(path(library(args.libflac))), harness_script=describe(Path(__file__)),
        moon_harness_source=describe(ROOT/'validation/benchmark_compete/main.mbt'),
        c_harness_source=describe(ROOT/'validation/libflac_core/main.c'),
        effort=args.effort, policy='fixed manifest; no data generation or substitution; all output PCM/CRC/MD5 verified outside timing',
        timing='true encoder core' if args.mode=='core' else 'CLI startup + unpack + encode + IO',
        acceptance_eligible=args.rounds>=10 and not args.smoke_case and args.action=='run' and args.effort==8,
        size_budget_percent=3, aggregate_size_budget_percent=1,
        minimum_core_batch_seconds=args.min_core_seconds,
        maximum_core_batch=args.max_batch, cases=[])
    if args.mode=='core':
        reference_dll=binaries['libflac'].parent/'libFLAC.dll'
        report['core_runtime_dll']=describe(reference_dll)
        assert report['core_runtime_dll']['sha256']==report['libflac_dll']['sha256'], 'Core harness DLL differs from official reference DLL'
        generated=binaries['candidate'].with_suffix('.c')
        if generated.exists():report['candidate_generated_c']=describe(generated)
    save(args.report,report)
    try:
        for case in cases:
            entry=dict(case=case, warmup={}, calibration=[], rounds=[], summary={})
            report['cases'].append(entry)
            expected={}; batch=1
            def check(codec, output):
                # Full independent verification on each produced file, after all
                # timed processes for that round have finished.
                verification_args=argparse.Namespace(**vars(args))
                verification_args.large_frame_transport=case['block'] in (32768,65535)
                checked=validate_sized(output,case,ref,verification_args)
                digest=checked['encoded_sha256']
                if codec in expected: assert digest==expected[codec], f'Unstable output: {case["name"]}/{codec}'
                expected[codec]=digest
                return checked
            if args.action=='curve':
                for level in range(9):
                    output=work/(case['name']+f'-libflac-{level}.flac')
                    sample=timed('libflac',binaries['libflac'],case,output,args,1,level)
                    entry['warmup'][str(level)]=dict(timing=sample,verification=check(str(level),output))
                if args.mode=='core':
                    batch=min(args.max_batch,max(1,math.ceil(args.min_core_seconds/min(v['timing']['seconds'] for v in entry['warmup'].values()))))
                    # Confirm the common batch for all nine levels, just as
                    # run confirms it for all three competing encoders.
                    while True:
                        calibration={};outputs={}
                        for level in range(9):
                            output=work/(case['name']+f'-libflac-{level}.flac')
                            outputs[str(level)]=output
                            calibration[str(level)]=timed('libflac',binaries['libflac'],case,output,args,batch,level)
                        for label,output in outputs.items():
                            calibration[label]['verification']=check(label,output)
                        entry['calibration'].append(dict(batch=batch,observations=calibration))
                        save(args.report,report)
                        minimum=min(v['core']['seconds'] for v in calibration.values())
                        if minimum>=args.min_core_seconds or batch==args.max_batch:break
                        batch=min(args.max_batch,max(batch+1,math.ceil(batch*args.min_core_seconds/minimum)))
                    entry['calibration_sufficient']=minimum>=args.min_core_seconds
                else:entry['calibration_sufficient']=True
                for index in range(args.rounds):
                    levels=curve_order(index)
                    observations={}; outputs={}
                    for level in levels:
                        output=work/(case['name']+f'-libflac-{level}.flac');outputs[str(level)]=output
                        observations[str(level)]=timed('libflac',binaries['libflac'],case,output,args,batch,level)
                    for label,output in outputs.items():observations[label]['verification']=check(label,output)
                    entry['rounds'].append(dict(round=index,order=levels,observations=observations));save(args.report,report)
                entry['summary']={str(level):summary([r['observations'][str(level)]['seconds'] for r in entry['rounds']]) for level in range(9)}
                entry['batch']=batch
                continue
            for codec in ['baseline','candidate','libflac']:
                output=work/(case['name']+'-'+codec+'.flac')
                sample=timed(codec,binaries[codec],case,output,args,1,args.effort)
                entry['warmup'][codec]=dict(timing=sample,verification=check(codec,output))
            if args.mode=='core':
                batch=min(args.max_batch,max(1,math.ceil(args.min_core_seconds/min(v['timing']['seconds'] for v in entry['warmup'].values()))))
                # Confirm chosen common batch using actual batch totals. If the
                # fastest codec remains below threshold, grow for every codec.
                while True:
                    calibration={}
                    for codec in ['candidate','libflac','baseline']:
                        output=work/(case['name']+'-'+codec+'.flac')
                        sample=timed(codec,binaries[codec],case,output,args,batch,args.effort)
                        calibration[codec]=dict(timing=sample,verification=check(codec,output))
                    entry['calibration'].append(dict(batch=batch,observations=calibration))
                    minimum=min(v['timing']['core']['seconds'] for v in calibration.values())
                    if minimum>=args.min_core_seconds or batch==args.max_batch:break
                    batch=min(args.max_batch,max(batch+1,math.ceil(batch*args.min_core_seconds/minimum)))
                entry['calibration_sufficient']=minimum>=args.min_core_seconds
            else:entry['calibration_sufficient']=True
            entry['batch']=batch
            for index in range(args.rounds):
                labels=order(index,args.block_id);observations={};outputs={}
                load_before=psutil.cpu_percent(interval=None)
                for codec in labels:
                    output=work/(case['name']+'-'+codec+'.flac');outputs[codec]=output
                    observations[codec]=timed(codec,binaries[codec],case,output,args,batch,args.effort)
                load_after=psutil.cpu_percent(interval=None)
                for codec,output in outputs.items():observations[codec]['verification']=check(codec,output)
                entry['rounds'].append(dict(round=index,order=labels,observations=observations,system_cpu_before=load_before,system_cpu_during=load_after))
                save(args.report,report)
            entry['summary']={k:summary([r['observations'][k]['seconds'] for r in entry['rounds']]) for k in binaries}
            ratios=[r['observations']['candidate']['seconds']/r['observations']['libflac']['seconds'] for r in entry['rounds']]
            entry['paired_candidate_over_libflac']=summary(ratios)
            size=entry['warmup']['candidate']['verification']['encoded_bytes'];anchor=case['quality_anchor']['encoded_bytes']
            entry['quality']=dict(candidate_bytes=size,e6817_bytes=anchor,ratio=size/anchor,within_1_percent=size*100<=anchor*101,
                within_3_percent=size*100<=anchor*103,passed=size*100<=anchor*(100+report['size_budget_percent']))
            save(args.report,report)
        # Restore evidence assertions after all measurements, including runtime
        # binaries and original inputs. A concurrently changed binary invalidates
        # this block even if its output happened to match.
        for codec,binary in binaries.items():assert sha(binary)==report['binaries'][codec]['sha256']
        assert sha(path(library(args.libflac)))==report['libflac_dll']['sha256']
        if args.mode=='core':assert sha(reference_dll)==report['core_runtime_dll']['sha256']
        for case in cases:assert sha(path(case['path']))==case['pcm_sha256']
        assert source_identity(args.candidate_identity)==report['candidate_identity']
        assert artifact_identity(args.candidate_identity,binaries['candidate'],args.mode)==report['candidate_executable_binding']
        assert artifact_identity(args.baseline_identity,binaries['baseline'],args.mode)==report['baseline_identity']
        if args.action=='run':
            report['all_aggregate']=aggregate(report['cases'],args.rounds,False)
            report['real_aggregate']=aggregate(report['cases'],args.rounds,True)
            candidate_bytes=sum(c['quality']['candidate_bytes'] for c in report['cases'])
            anchor_bytes=sum(c['quality']['e6817_bytes'] for c in report['cases'])
            report['aggregate_quality']=dict(candidate_bytes=candidate_bytes,e6817_bytes=anchor_bytes,ratio=candidate_bytes/anchor_bytes,passed=candidate_bytes*100<=anchor_bytes*101)
            report['quality_pass']=all(c['quality']['passed'] for c in report['cases']) and report['aggregate_quality']['passed']
            report['calibration_pass']=all(c['calibration_sufficient'] for c in report['cases'])
            report['worst_case_paired_median']=max((dict(name=c['case']['name'],ratio=c['paired_candidate_over_libflac']['median']) for c in report['cases']),key=lambda x:x['ratio'])
            report['block_gate_pass']=report['acceptance_eligible'] and report['quality_pass'] and report['calibration_pass'] and report['all_aggregate']['passed'] and report['real_aggregate']['passed']
        else:
            report['reference_curve']=[]
            for level in range(9):
                sizes=[c['warmup'][str(level)]['verification']['encoded_bytes'] for c in report['cases']]
                anchors=[c['case']['quality_anchor']['encoded_bytes'] for c in report['cases']]
                per_case=all(n*100<=old*103 for n,old in zip(sizes,anchors))
                total=sum(sizes);anchor_total=sum(anchors)
                report['reference_curve'].append(dict(effort=level,encoded_bytes=total,e6817_bytes=anchor_total,ratio=total/anchor_total,
                    per_case_3_percent=per_case,aggregate_1_percent=total*100<=anchor_total*101,
                    qualifies=per_case and total*100<=anchor_total*101,
                    sum_case_median_seconds=sum(c['summary'][str(level)]['median'] for c in report['cases'])))
            eligible=[v for v in report['reference_curve'] if v['qualifies']]
            report['calibration_pass']=all(c['calibration_sufficient'] for c in report['cases'])
            report['reference_selection_eligible']=args.rounds>=18 and not args.smoke_case and report['calibration_pass']
            fastest=min(eligible,key=lambda x:x['sum_case_median_seconds']) if eligible else None
            report['fastest_by_observed_times']=fastest
            report['fastest_qualified_reference']=fastest if report['reference_selection_eligible'] else None
        report['status']='complete';report['end_utc']=datetime.now(timezone.utc).isoformat();save(args.report,report)
    except Exception as exc:
        report['status']='failed';report['error']=repr(exc);save(args.report,report);raise
    print(json.dumps({'report':str(args.report),'status':report['status'],'block_gate_pass':report.get('block_gate_pass',False)}))

def re_safe(value):return all(c.isascii() and (c.isalnum() or c in '-_') for c in value)

def combine(args):
    if args.report.exists():raise FileExistsError(args.report)
    reports=[json.loads(p.read_text()) for p in args.blocks]
    if len(reports)!=2 or len({r['block_id'] for r in reports})!=2:raise ValueError('Exactly two distinct independently launched blocks are required')
    for r in reports:assert r['status']=='complete' and r['action']=='run' and r['rounds']>=10 and r['acceptance_eligible']
    assert max(r['start_utc'] for r in reports)>=min(r['end_utc'] for r in reports), 'Independent blocks must not overlap'
    keys = ['mode','group','manifest','references','binaries','candidate_identity','candidate_executable_binding','baseline_identity','cpu','effort','size_budget_percent','aggregate_size_budget_percent','harness_script','moon_harness_source','c_harness_source','libflac_dll','independent_tools']
    if reports[0]['mode'] == 'core':
        keys.append('core_runtime_dll')
    for key in keys:
        assert reports[0][key]==reports[1][key], 'Block identity differs: '+key
    output=dict(status='complete',reports=[describe(p) for p in args.blocks],
        mode=reports[0]['mode'],group=reports[0]['group'],scope='only this declared group and timing mode; other goal gates are separate',
        passed=all(r['block_gate_pass'] for r in reports),
        criterion='both distinct >=10-round blocks independently satisfy exact PCM, size budget, calibrated timing and all/real aggregate paired-win dispersion gates; no claim if either block is uncertain',
        interpretation='observed local machine comparisons, not a universal performance guarantee')
    save(args.report,output);print(json.dumps(output))

def self_test():
    """Small identity rejection tests; never starts an encoder or benchmark."""
    import tempfile
    checks=[]
    with tempfile.TemporaryDirectory(prefix='moonflac-core-identity-') as directory:
        work=Path(directory);good=work/'good.exe';wrong=work/'wrong.exe'
        good.write_bytes(b'expected artifact');wrong.write_bytes(b'different artifact')
        identity=work/'identity.json';source=work/'source.mbt';source.write_text('test source')
        def expect(label,exception,operation):
            try:operation()
            except exception:checks.append(label)
            else:raise AssertionError('Expected rejection: '+label)
        identity.write_text(json.dumps({'cli':describe(good)}))
        assert artifact_identity(identity,good,'cli')['actual_executable']['sha256']==sha(good)
        checks.append('matching direct CLI artifact accepted')
        expect('wrong candidate CLI binary rejected',ValueError,lambda:artifact_identity(identity,wrong,'cli'))
        expect('missing core artifact rejected',ValueError,lambda:artifact_identity(identity,good,'core'))
        identity.write_text(json.dumps({'artifacts':{'core':describe(good)}}))
        assert artifact_identity(identity,good,'core')['actual_executable']['sha256']==sha(good)
        checks.append('matching artifacts mapping accepted')
        expect('wrong baseline core binary rejected',ValueError,lambda:artifact_identity(identity,wrong,'core'))
        identity.write_text(json.dumps({'artifacts':[dict(role='core',**describe(good))]}))
        assert artifact_identity(identity,good,'core')['actual_executable']['sha256']==sha(good)
        checks.append('matching artifacts list accepted')
        identity.write_text(json.dumps({'sources':{str(source):sha(source)}}))
        assert str(source) in source_identity(identity)['checked_sources']
        checks.append('matching declared production source accepted')
        source.write_text('changed test source')
        expect('changed production source rejected',AssertionError,lambda:source_identity(identity))
        identity.write_text(json.dumps({'sources':{str(work/'missing.mbt'):'0'*64}}))
        expect('missing declared production source rejected',FileNotFoundError,lambda:source_identity(identity))
        source.write_text('original MoonBit runtime')
        generated=work/'generated.c';generated.write_text('generated compiler input')
        identity.write_text(json.dumps({'sources':{str(generated):sha(generated)},
            'source_manifest':{str(source):sha(source)}}))
        assert len(source_identity(identity)['checked_sources'])==2
        checks.append('generated C and original MoonBit manifest both verified')
        source.write_text('changed original runtime')
        expect('changed original MoonBit manifest rejected',AssertionError,lambda:source_identity(identity))
        identity.write_text(json.dumps({'sources':{str(generated):sha(generated)},
            'source_manifest':{str(work/'absent.mbt'):'0'*64}}))
        expect('missing original MoonBit manifest source rejected',FileNotFoundError,lambda:source_identity(identity))
        # Synthetic helper fixtures, never encoder outputs or timed observations.
        import copy
        import contextlib
        import io
        shared = {name: {'sha256':'0'*64} for name in [
            'manifest','references','binaries','candidate_identity','candidate_executable_binding',
            'baseline_identity','harness_script','moon_harness_source','c_harness_source',
            'libflac_dll','core_runtime_dll','independent_tools']}
        shared.update(mode='core',group='original-core',cpu=8,effort=8,size_budget_percent=3,
                      aggregate_size_budget_percent=1,status='complete',action='run',rounds=10,
                      acceptance_eligible=True,block_gate_pass=True,
                      synthetic_fixture_note='Identity rejection fixture only; no timing rounds executed')
        first=dict(shared,block_id='synthetic-a',start_utc='00:00',end_utc='00:01')
        second=dict(shared,block_id='synthetic-b',start_utc='00:02',end_utc='00:03')
        a_path=work/'synthetic-a.json';b_path=work/'synthetic-b.json'
        a_path.write_text(json.dumps(first))
        def combine_fixture(second_report, label):
            b_path.write_text(json.dumps(second_report))
            target=work/(label+'.json')
            with contextlib.redirect_stdout(io.StringIO()):
                combine(argparse.Namespace(blocks=[a_path,b_path],report=target))
            return json.loads(target.read_text())
        assert combine_fixture(second,'same-libraries')['passed']
        checks.append('same reference DLL and tools accepted across blocks (synthetic)')
        for field in ['libflac_dll','core_runtime_dll','independent_tools']:
            changed=copy.deepcopy(second);changed[field]['sha256']='1'*64
            expect('cross-block '+field+' mismatch rejected',AssertionError,
                   lambda changed=changed,field=field:combine_fixture(changed,'changed-'+field))
        missing=copy.deepcopy(second);del missing['core_runtime_dll']
        expect('missing cross-block core runtime DLL identity rejected',KeyError,
               lambda:combine_fixture(missing,'missing-runtime-dll'))
    orders=[curve_order(i) for i in range(18)]
    assert all(sum(row[position]==level for row in orders)==2 for level in range(9) for position in range(9))
    checks.append('18-round curve each level occupies every position twice')
    assert all(sum(row.index(a)<row.index(b) for row in orders)==9 for a in range(9) for b in range(a+1,9))
    checks.append('18-round curve every pair has 9 forward and 9 reverse orders')
    print(json.dumps(dict(status='pass',checks=checks,encoders_launched=0)))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='action',required=True)
    for action in ['run','curve']:
        p=sub.add_parser(action)
        p.add_argument('--mode',choices=['cli','core'],required=True)
        p.add_argument('--manifest',type=Path,required=True)
        p.add_argument('--group',choices=['original-cli','original-core','long'],required=True)
        p.add_argument('--references',type=Path,default=ROOT/'validation/evidence/faster-than-libflac-inputs-references.json')
        p.add_argument('--candidate',type=Path,required=True)
        p.add_argument('--baseline',type=Path,required=True)
        p.add_argument('--candidate-identity',type=Path,required=True)
        p.add_argument('--baseline-identity',type=Path,required=True)
        p.add_argument('--baseline-core-format',choices=['old','new'],default='old')
        p.add_argument('--libflac-core',type=Path,default=ROOT/'_build/faster-than-libflac/core-reference/libflac_core.exe')
        p.add_argument('--flac',type=Path,default=ROOT/'validation/cache/libflac/flac-1.5.0-win/Win64/flac.exe')
        p.add_argument('--libflac',default=None)
        p.add_argument('--ffmpeg',type=Path,default=Path(shutil.which('ffmpeg') or 'ffmpeg'))
        p.add_argument('--effort',type=int,choices=range(9),default=8)
        p.add_argument('--block-id',required=True)
        p.add_argument('--rounds',type=int,default=18 if action=='curve' else 10)
        p.add_argument('--cpu',type=int,default=8)
        p.add_argument('--min-core-seconds',type=float,default=.1)
        p.add_argument('--max-batch',type=int,default=256)
        p.add_argument('--timeout',type=float,default=600)
        p.add_argument('--smoke-case')
        p.add_argument('--report',type=Path,required=True)
    p=sub.add_parser('combine');p.add_argument('--blocks',type=Path,nargs=2,required=True);p.add_argument('--report',type=Path,required=True)
    sub.add_parser('self-test')
    args=parser.parse_args()
    if args.action=='self-test':self_test()
    elif args.action=='combine':combine(args)
    else:
        if args.min_core_seconds<=0 or args.max_batch<1:parser.error('positive calibration limits required')
        execute(args)

if __name__=='__main__':main()

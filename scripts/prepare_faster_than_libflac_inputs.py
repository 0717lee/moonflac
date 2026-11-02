"""Freeze original inputs and a separately reported continuous long-audio set.

prepare downloads only the pinned public-domain music recording if absent,
preserves original manifest bytes, and freezes all selection/PCM/provenance.
references encodes only the two accepted frozen baselines, not a new candidate;
existing original-set outputs are reused after identity and independent checks.
No wall-clock benchmark or selection tuning is performed here.
"""
import argparse
import hashlib
import json
import random
import shutil
import subprocess
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / 'validation/cache/faster-than-libflac'
E = ROOT / 'validation/evidence'
QUALITY_SHA = 'e6817e77aafaa124a30d4e75b9a5f73beca10f0b0da967ddcc2e97c3397fe743'
PERFORMANCE_SHA = '71be364ccf233d29d5a3327ddd78ba7ad076bdb4c6fcc34b11a00d0a482041a9'
MUSIC_SHA = '41b9b2021e6f9d7f8b4c32aca20fdbbb84f774c01db2be448b348604c5ec6344'
MUSIC_URL = 'https://upload.wikimedia.org/wikipedia/commons/f/f5/Moonlight_Sonata_Allegretto.ogg'
MUSIC_PAGE = 'https://commons.wikimedia.org/w/index.php?title=File:Moonlight_Sonata_Allegretto.ogg&oldid=642750009'
PLAN = [
    dict(name='music-pitman-allegretto', kind='real-music', seconds=60, bits=16, channels=2, rate=44100, block=4096),
    dict(name='speech-america-beautiful', kind='real-speech', seconds=60, bits=16, channels=1, rate=44100, block=4096),
    dict(name='speech-anarchy', kind='real-speech', seconds=60, bits=24, channels=1, rate=44100, block=4096),
    dict(name='noise16-stereo', kind='synthetic-noise', seconds=30, bits=16, channels=2, rate=48000, block=4096, seed=202609300001),
    dict(name='noise32-stereo-block32768', kind='synthetic-noise', seconds=30, bits=32, channels=2, rate=48000, block=32768, seed=202609300002),
    dict(name='correlated24-six-channel', kind='synthetic-correlated', seconds=30, bits=24, channels=6, rate=48000, block=4096),
    dict(name='silence16-stereo', kind='synthetic-silence', seconds=60, bits=16, channels=2, rate=48000, block=4096),
    dict(name='correlated32-eight-channel-block65535', kind='synthetic-correlated', seconds=30, bits=32, channels=8, rate=48000, block=65535),
]


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for data in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(data)
    return digest.hexdigest()


def relative(path):
    return path.relative_to(ROOT).as_posix()


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')


def sealed_bytes(path, data):
    if path.exists():
        assert path.read_bytes() == data, 'sealed evidence differs: ' + str(path)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def fetch(url, path):
    if not path.exists():
        request = urllib.request.Request(url, headers={'User-Agent': 'MoonFLAC-local-validation/1.0'})
        with urllib.request.urlopen(request, timeout=120) as source, path.open('wb') as target:
            shutil.copyfileobj(source, target)


def original_sets():
    result = {}
    for mode in ['cli', 'core']:
        old = ROOT / f'validation/cache/effort8-benchmark/{mode}-inputs.json'
        copied = E / f'faster-than-libflac-inputs-original-{mode}.json'
        sealed_bytes(copied, old.read_bytes())
        manifest = json.loads(old.read_text(encoding='utf-8'))
        assert len(manifest['cases']) == 12
        for case in manifest['cases']:
            assert sha(ROOT / case['path']) == case['pcm_sha256']
        result[mode] = dict(source_manifest=relative(old), copied_manifest=relative(copied),
                            manifest_sha256=sha(old), exact_original_bytes_and_settings=True, case_count=12)
    return result


def synthetic(case, path):
    bits, channels = case['bits'], case['channels']
    width, frames = bits // 8, case['seconds'] * case['rate']
    rng = random.Random(case.get('seed', 0))
    hi = (1 << (bits - 1)) - 1
    with path.open('wb') as output:
        for start in range(0, frames, 4096):
            chunk = bytearray()
            for i in range(start, min(frames, start + 4096)):
                for channel in range(channels):
                    if case['kind'] == 'synthetic-silence':
                        value = 0
                    elif case['kind'] == 'synthetic-noise':
                        value = rng.getrandbits(bits) - (1 << (bits - 1))
                    else:
                        # Integer-only two-period triangle mixture; no sampled
                        # recording, no claim of realism, no floating-point drift.
                        t = i + channel * 19
                        a = abs(t % 1998 - 999) * 2 - 999
                        b = abs(t % 4062 - 2031) * 2 - 2031
                        value = (a * hi * 3 // 999 + b * hi // 2031) // 5
                    chunk.extend(value.to_bytes(width, 'little', signed=True))
            output.write(chunk)


def prepare():
    CACHE.mkdir(parents=True, exist_ok=True)
    selection = dict(task='faster-than-libflac-20260929', new_set=PLAN, quality_baseline_sha256=QUALITY_SHA,
                     performance_baseline_sha256=PERFORMANCE_SHA, music_url=MUSIC_URL, music_sha256=MUSIC_SHA,
                     selection_policy='Fixed before any candidate encoding or results on this new long-audio set; concurrent candidate development on previously existing regression fixtures is not excluded. Original sets remain unchanged and separate.',
                     repetitions_later='10 paired rounds in two separate blocks; this preparation performs no timing')
    sealed_bytes(E / 'faster-than-libflac-inputs-selection.json',
                 (json.dumps(selection, indent=2) + '\n').encode())
    originals = original_sets()
    music, page = CACHE / 'moonlight-allegretto.ogg', CACHE / 'music-source.html'
    fetch(MUSIC_URL, music)
    fetch(MUSIC_PAGE, page)
    assert sha(music) == MUSIC_SHA
    page_text = page.read_text(encoding='utf-8')
    assert 'Paul Pitman' in page_text and 'public domain' in page_text
    ffmpeg, ffprobe = shutil.which('ffmpeg'), shutil.which('ffprobe')
    assert ffmpeg and ffprobe
    music_info = json.loads(subprocess.check_output([ffprobe, '-v', 'error', '-show_streams', '-of', 'json', str(music)], text=True))['streams'][0]
    assert int(music_info['sample_rate']) == 44100 and music_info['channels'] == 2
    speech_manifest_path = E / 'speed-first-holdout-manifest.json'
    speech_manifest = json.loads(speech_manifest_path.read_text(encoding='utf-8'))
    cases = []
    for selected in PLAN:
        case = dict(selected, effort=8, variable=False, samples=selected['seconds'] * selected['rate'],
                    sample_offset=0, file_and_core_input_identical=True)
        path = CACHE / (case['name'] + '.raw')
        if case['kind'] == 'real-music':
            command = [ffmpeg, '-v', 'error', '-y', '-i', str(music), '-map', '0:a:0',
                       '-af', f"atrim=start_sample=0:end_sample={case['samples']},aresample=dither_method=none",
                       '-c:a', 'pcm_s16le', '-f', 's16le', str(path)]
            if not path.exists():
                subprocess.run(command, capture_output=True, check=True, timeout=180)
            case.update(source=relative(music), source_sha256=MUSIC_SHA, source_page=MUSIC_PAGE,
                        source_page_snapshot=relative(page), source_page_snapshot_sha256=sha(page),
                        download_url=MUSIC_URL, composer='Ludwig van Beethoven', performer='Paul Pitman', publisher='Musopen / Wikimedia Commons',
                        title='Piano Sonata No. 14, Op. 27 No. 2: Allegretto',
                        license='Recording dedicated to public domain by Paul Pitman; Wikimedia permission ticket 2008012110017088',
                        source_duration_seconds=float(music_info['duration']), source_codec='Vorbis', conversion_command=command,
                        provenance='First 60 continuous seconds, no repetition, splice, resampling or channel conversion. Lossy-source decoded PCM is the exact lossless target, not an original recording master.')
        elif case['kind'] == 'real-speech':
            old_name = 'holdout-recording-' + case['name'].removeprefix('speech-')
            old = next(row for row in speech_manifest['cases'] if row['name'] == old_name)
            source = ROOT / old['path']
            assert sha(source) == old['pcm_sha256'] and sha(ROOT / old['source']) == old['source_sha256']
            length = case['samples'] * case['channels'] * (case['bits'] // 8)
            with source.open('rb') as stream:
                raw = stream.read(length)
            assert len(raw) == length
            sealed_bytes(path, raw)
            case.update({k: old[k] for k in ['source', 'source_sha256', 'source_page', 'download_url', 'license', 'author', 'reader', 'title', 'source_duration_seconds', 'source_codec', 'conversion_command']})
            case.update(parent_pcm=old['path'], parent_pcm_sha256=old['pcm_sha256'],
                        parent_manifest=relative(speech_manifest_path), parent_manifest_sha256=sha(speech_manifest_path),
                        provenance='First 60 continuous seconds of cached complete LibriVox reading PCM; no repetition, splice, resampling or channel conversion. Source MP3 is lossy; target is the frozen integer PCM.')
        else:
            if not path.exists():
                synthetic(case, path)
            case['provenance'] = 'Deterministic synthetic integer PCM generated continuously for the declared duration; not a recording or repeated short clip.'
            case['generator'] = relative(Path(__file__)) + ':synthetic'
        expected_length = case['samples'] * case['channels'] * (case['bits'] // 8)
        assert path.stat().st_size == expected_length
        case.update(path=relative(path), pcm_bytes=expected_length, pcm_sha256=sha(path), duration_seconds=case['samples'] / case['rate'])
        if case['block'] in [32768, 65535]:
            case['ffmpeg_validation_transport'] = 'predeclared unchanged-frame Ogg if FFmpeg is used; native libFLAC exact remains mandatory'
        cases.append(case)
    manifest = dict(cases=cases, case_count=8, total_duration_seconds=sum(c['duration_seconds'] for c in cases),
                    selection_sha256=sha(E / 'faster-than-libflac-inputs-selection.json'), original_sets=originals,
                    generator_sha256=sha(Path(__file__)), ffmpeg_version=subprocess.check_output([ffmpeg, '-version'], text=True).splitlines()[0],
                    ffmpeg_sha256=sha(Path(ffmpeg)), quality_budget=dict(per_case=1.03, aggregate=1.01),
                    grouping='Separate long-audio set; do not substitute for, merge into or drop cases from original12 CLI/core totals',
                    memory_contract='Same PCM and parameters for file CLI and in-memory core; whole-buffer APIs may hold this input, streaming bounds are separate gates')
    sealed_bytes(E / 'faster-than-libflac-inputs-long.json', (json.dumps(manifest, indent=2) + '\n').encode())
    gates = ['speed-first-revision7-quality.json', 'speed-first-short-revision7.json', 'speed-first-pulses-revision7.json', 'speed-first-pulses-cross-revision7.json']
    pointers = {name: dict(path=relative(E / name), sha256=sha(E / name)) for name in gates}
    index = dict(status='frozen', originals=originals, long_manifest=relative(E / 'faster-than-libflac-inputs-long.json'),
                 long_manifest_sha256=sha(E / 'faster-than-libflac-inputs-long.json'), retained_quality_gates=pointers,
                 quality_roles='31 retained audio, 145 review/neighbor, 32 pulse cases (all previously observed, not unseen holdouts)',
                 provenance_scope_note='No new-candidate results on the new long set were observed during selection; this is not a claim that no candidate binary or prior-fixture development existed globally.',
                 new_candidate_measurements_performed=False)
    sealed_bytes(E / 'faster-than-libflac-inputs.json', (json.dumps(index, indent=2) + '\n').encode())
    print('FROZEN: original12 CLI + original12 core unchanged; long8, 360 seconds', flush=True)


def exact_files(left, right):
    with left.open('rb') as a, right.open('rb') as b:
        while True:
            x, y = a.read(1048576), b.read(1048576)
            assert x == y, 'Independent libFLAC PCM differs'
            if not x:
                break


def validate(case, output, flac, decoded):
    source = ROOT / case['path']
    assert sha(source) == case['pcm_sha256']
    check = [str(flac), '-t', '-s', str(output)]
    subprocess.run(check, capture_output=True, check=True, timeout=600)
    command = [str(flac), '-d', '-f', '-s', '--force-raw-format', '--endian=little', '--sign=signed', '-o', str(decoded), str(output)]
    subprocess.run(command, capture_output=True, check=True, timeout=600)
    exact_files(source, decoded)
    digest = hashlib.md5()
    with source.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1048576), b''):
            digest.update(chunk)
    with output.open('rb') as stream:
        header = stream.read(42)
    assert header[:4] == b'fLaC' and header[4] & 127 == 0 and header[26:42] == digest.digest()
    return dict(encoded_bytes=output.stat().st_size, encoded_sha256=sha(output),
                independent_pcm='official libFLAC complete signed integer bytes exact',
                crc_md5='flac -t pass; STREAMINFO matches Python hashlib over original PCM',
                verification_commands=[check, command], pcm_md5=digest.hexdigest())


def references():
    target = E / 'faster-than-libflac-inputs-references.json'
    assert not target.exists(), 'Preserve baseline reference evidence'
    quality = ROOT / '_build/speed-first/accepted-baseline.exe'
    performance = ROOT / '_build/speed-first/revision7/native/release/build/cmd/moonflac/moonflac.exe'
    assert sha(quality) == QUALITY_SHA and sha(performance) == PERFORMANCE_SHA
    flac = ROOT / 'validation/cache/libflac/flac-1.5.0-win/Win64/flac.exe'
    report = dict(status='running', quality_baseline=dict(path=relative(quality), sha256=QUALITY_SHA),
                  performance_baseline=dict(path=relative(performance), sha256=PERFORMANCE_SHA),
                  libflac=dict(path=relative(flac), sha256=sha(flac), version=subprocess.check_output([str(flac), '--version'], text=True).strip()),
                  cases=[], no_new_candidate=True, no_timing_claim=True, script_sha256=sha(Path(__file__)))
    try:
        for group in ['original-cli', 'original-core', 'long']:
            manifest_path = E / f'faster-than-libflac-inputs-{group}.json'
            manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
            history = None
            if group.startswith('original-'):
                mode = group.removeprefix('original-')
                history_path = E / f'speed-first-revision7-{mode}-benchmark.json'
                history = json.loads(history_path.read_text(encoding='utf-8'))
                assert history['status'] == 'pass'
                previous = {case['name']: case for case in history['cases']}
            for case in manifest['cases']:
                row = dict(group=group, name=case['name'], manifest_sha256=sha(manifest_path), pcm_sha256=case['pcm_sha256'], references={})
                report['cases'].append(row)
                for label, cli, historical_label in [('quality', quality, 'baseline'), ('performance', performance, 'candidate')]:
                    if history:
                        old_case = previous[case['name']]
                        assert old_case['pcm_sha256'] == case['pcm_sha256']
                        old = old_case['runs'][historical_label][0]
                        output = Path(old['command'][2 if group == 'original-core' else 3])
                        assert sha(output) == old['encoded_sha256']
                        command = None
                    else:
                        output = CACHE / (case['name'] + '-' + label + '.flac')
                        command = [str(cli), 'encode', str(ROOT / case['path']), str(output), '--raw',
                                   '--sample-rate', str(case['rate']), '--channels', str(case['channels']),
                                   '--bits', str(case['bits']), '--block-size', str(case['block']), '--effort', '8']
                        subprocess.run(command, capture_output=True, check=True, timeout=1800)
                    checked = validate(case, output, flac, CACHE / 'independent-decoded.raw')
                    row['references'][label] = dict(output=str(output), encode_command=command,
                        reused_verified_original_output=bool(history),
                        original_report=relative(history_path) if history else None,
                        original_report_sha256=sha(history_path) if history else None, **checked)
                    save(target, report)
                print(group, case['name'], 'two baselines independently exact', flush=True)
        assert sha(quality) == QUALITY_SHA and sha(performance) == PERFORMANCE_SHA
        report.update(status='pass', fixture_checks=len(report['cases']), encoded_reference_checks=2 * len(report['cases']))
    except BaseException as error:
        report.update(status='fail', error=repr(error))
        raise
    finally:
        save(target, report)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'references'])
    args = parser.parse_args()
    (prepare if args.action == 'prepare' else references)()

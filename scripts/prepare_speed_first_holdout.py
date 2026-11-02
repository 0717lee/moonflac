"""Freeze and prepare a local speed-first holdout without running any encoder.

Run from the MoonFLAC root: python scripts/prepare_speed_first_holdout.py
Only libFLAC decodes public source files. Synthetic samples use integer formulas.
An existing manifest is verified rather than silently replaced.
"""
import hashlib
import json
import shutil
import subprocess
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / 'validation/cache/flac-test-files'
CACHE = ROOT / 'validation/cache/speed-first-holdout'
MANIFEST = ROOT / 'validation/evidence/speed-first-holdout-manifest.json'
FLAC = ROOT / 'validation/cache/libflac/flac-1.5.0-win/Win64/flac.exe'
SELECTED = [('subset', n) for n in (11, 17, 24, 47, 56, 64)] + [('uncommon', n) for n in (5, 8, 9)]
EXCLUDED = [('subset', n) for n in (1, 28, 39, 60)]
SPEECH = [
    ('america-beautiful', 'spc228_americabeautiful_bv_128kb.mp3',
     '4bb81a824534351993359bd839278b9a8600a11cd86c51c728f1121e55361d9a',
     'America The Beautiful', 'Katharine Lee Bates', 'Bvince', 16),
    ('anarchy', 'spc228_anarchy_mlm_128kb.mp3',
     '015205b61df3de47d0739ce04e753b2f1578825776f8f07c76570756ea4b4666',
     'Anarchy', 'John McCrae', 'mleigh', 24),
]


def prepare_speech():
    ffmpeg, ffprobe = shutil.which('ffmpeg'), shutil.which('ffprobe')
    assert ffmpeg and ffprobe
    license_snapshot = CACHE / 'speech-license.html'
    if not license_snapshot.exists():
        with urllib.request.urlopen('https://librivox.org/short-poetry-collection-228-by-various/', timeout=90) as response:
            license_snapshot.write_bytes(response.read())
    cases = []
    for name, filename, identity, title, author, reader, bits in SPEECH:
        path = CACHE / (name + '.mp3')
        url = 'https://archive.org/download/spc228_2206_librivox/' + filename
        if not path.exists():
            with urllib.request.urlopen(url, timeout=90) as response:
                path.write_bytes(response.read())
        assert sha(path.read_bytes()) == identity
        stream = json.loads(subprocess.check_output([ffprobe, '-v', 'error', '-show_streams', '-of', 'json', str(path)], text=True))['streams'][0]
        output = CACHE / ('holdout-recording-' + name + '.raw')
        command = [ffmpeg, '-v', 'error', '-y', '-i', str(path), '-map', '0:a:0',
                   '-af', 'aresample=dither_method=none', '-c:a', f'pcm_s{bits}le', '-f', f's{bits}le', str(output)]
        subprocess.run(command, check=True, capture_output=True, timeout=180)
        pcm = output.read_bytes()
        frame_bytes = stream['channels'] * (bits // 8)
        assert len(pcm) % frame_bytes == 0
        cases.append({'name': 'holdout-recording-' + name, 'path': relative(output),
                      'kind': 'real-speech-recording', 'title': title, 'author': author, 'reader': reader,
                      'source': relative(path), 'source_sha256': identity, 'download_url': url,
                      'source_page': 'https://librivox.org/short-poetry-collection-228-by-various/',
                      'license': 'LibriVox recordings are Public Domain in the USA (publisher statement); no worldwide public-domain claim.',
                      'source_codec': stream['codec_name'], 'source_rate': int(stream['sample_rate']),
                      'source_channels': stream['channels'], 'source_duration_seconds': stream.get('duration'),
                      'bits': bits, 'channels': stream['channels'], 'rate': int(stream['sample_rate']),
                      'samples': len(pcm) // frame_bytes, 'sample_offset': 0, 'block': 4096, 'effort': 8,
                      'pcm_bytes': len(pcm), 'pcm_sha256': sha(pcm), 'conversion_command': command,
                      'provenance': 'Complete continuous human reading from the official LibriVox download. Different reader and text from the other new recording. MP3 is lossy; the exact lossless target is the frozen FFmpeg integer PCM, not reconstruction of a recording master. No resampling, repetition, splicing or channel conversion.'})
    freeze = CACHE / 'frozen-recording-selection.json'
    selection = [{k: v for k, v in entry.items() if k not in ('conversion_command',)} for entry in cases]
    data = json.dumps(selection, indent=2, sort_keys=True).encode() + b'\n'
    if freeze.exists():
        assert freeze.read_bytes() == data, 'Recording holdout identity changed'
    else:
        freeze.write_bytes(data)
    return cases, {'ffmpeg_version': subprocess.check_output([ffmpeg, '-version'], text=True).splitlines()[0],
                   'ffmpeg_binary_sha256': sha(Path(ffmpeg).read_bytes()),
                   'license_page_snapshot': relative(license_snapshot),
                   'license_page_snapshot_sha256': sha(license_snapshot.read_bytes()),
                   'selection_sha256': sha(data)}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def relative(path):
    return path.relative_to(ROOT).as_posix()


def source_path(group, number):
    paths = list((CORPUS / group).glob(f'{number:02d} - *.flac'))
    assert len(paths) == 1
    return paths[0]


def info(path):
    with path.open('rb') as file:
        header = file.read(42)
    assert header[:4] == b'fLaC' and header[4] & 127 == 0
    field = int.from_bytes(header[18:26], 'big')
    return {'rate': field >> 44, 'channels': ((field >> 41) & 7) + 1,
            'bits': ((field >> 36) & 31) + 1, 'total_samples': field & ((1 << 36) - 1)}


def decode(path):
    command = [str(FLAC), '-d', '-c', '--force-raw-format', '--endian=little', '--sign=signed', str(path)]
    result = subprocess.run(command, capture_output=True, timeout=180)
    assert result.returncode == 0, result.stderr.decode(errors='replace')
    return result.stdout, {'command': [relative(FLAC), *command[1:-1], relative(path)],
                           'exit': result.returncode, 'stderr': result.stderr.decode('utf-8', errors='replace')}


def synthetic(kind, bits, channels, count, seed):
    state = seed
    out = bytearray()
    scale = 1 << (bits - 1)
    for i in range(count):
        for channel in range(channels):
            state = (state * 1664525 + 1013904223) & 0xFFFFFFFF
            noise = (state >> (32 - bits)) - scale
            ramp = ((i * (channel * 2 + 17)) % 4096 - 2048) * (scale // 2048)
            if kind == 'silence':
                value = 0
            elif kind == 'nonstationary':
                mode = (i // 1537) % 4
                value = [0, ramp // 4, noise, noise // 256][mode]
            elif kind == 'impulses':
                value = (scale - 1 if channel % 2 == 0 else -scale) if i % (997 + channel) == 0 else noise // 8192
            elif kind == 'correlated':
                value = (((i * 29) % 8192) - 4096) * (scale // 8192) + noise // 4096
            elif kind == 'ramp-reversals':
                value = ramp if (i // 8191) % 2 == 0 else -1 - ramp
            else:
                value = noise if (i // 4093) % 3 == 0 else ramp // 2
            assert -scale <= value < scale
            out += value.to_bytes(bits // 8, 'little', signed=True)
    return bytes(out)


def main():
    CACHE.mkdir(parents=True, exist_ok=True)
    sources = []
    decoded = {}
    # Freeze source identity and selection before any encoder sees these cases.
    for group, number in SELECTED:
        path = source_path(group, number)
        fmt = info(path)
        name = f'holdout-{group}-{number:02d}'
        start = 0
        count = min(fmt['total_samples'], fmt['rate'] * 4)
        assert count > 0 and fmt['bits'] in (16, 24, 32)
        sources.append({'name': name, 'path': relative(CACHE / (name + '.raw')),
                        'source': relative(path), 'source_sha256': sha(path.read_bytes()),
                        **fmt, 'samples': count, 'sample_offset': start,
                        'block': 65535 if (group, number) == ('uncommon', 8) else 4096,
                        'effort': 8, 'kind': 'public-conformance-audio',
                        'provenance': 'CC0 FLAC decoder testbench; README describes format feature, not recording provenance. Continuous original PCM, no channel conversion/resampling/repetition.'})
    groups = [('silence', 16, 3, 48000), ('nonstationary', 24, 4, 96000),
              ('impulses', 32, 5, 96000), ('correlated', 16, 6, 96000),
              ('ramp-reversals', 24, 7, 96000), ('maximum-block', 32, 8, 131070)]
    generated = []
    for index, (kind, bits, channels, count) in enumerate(groups):
        name = f'holdout-generated-{kind}'
        generated.append({'name': name, 'path': relative(CACHE / (name + '.raw')),
                          'kind': 'synthetic', 'generator': kind, 'seed': 29092026 + index * 101,
                          'bits': bits, 'channels': channels, 'rate': 48000, 'samples': count,
                          'sample_offset': 0, 'block': 65535 if kind == 'maximum-block' else 4096,
                          'effort': 8, 'provenance': 'Deterministic integer stress signal; not a real recording. Formula and PRNG are fixed in the identified preparation script.'})
    selection = {'sources': sources, 'generated': generated}
    selection_file = CACHE / 'frozen-selection.json'
    serialized = json.dumps(selection, sort_keys=True, indent=2).encode() + b'\n'
    if selection_file.exists():
        assert selection_file.read_bytes() == serialized, 'Frozen selection changed; do not silently retune holdout.'
    else:
        selection_file.write_bytes(serialized)
    commands = []
    for entry in sources:
        full, command = decode(ROOT / entry['source'])
        commands.append(command)
        frame_bytes = entry['channels'] * (entry['bits'] // 8)
        assert len(full) == entry['total_samples'] * frame_bytes
        decoded[entry['name']] = (entry, full)
        pcm = full[:entry['samples'] * frame_bytes]
        (ROOT / entry['path']).write_bytes(pcm)
        entry.update(pcm_bytes=len(pcm), pcm_sha256=sha(pcm), full_source_pcm_sha256=sha(full))
    for entry in generated:
        pcm = synthetic(entry['generator'], entry['bits'], entry['channels'], entry['samples'], entry['seed'])
        (ROOT / entry['path']).write_bytes(pcm)
        entry.update(pcm_bytes=len(pcm), pcm_sha256=sha(pcm))
    comparisons = dict(decoded)
    for group, number in EXCLUDED:
        path = source_path(group, number)
        pcm, command = decode(path)
        commands.append(command)
        comparisons[f'excluded-{group}-{number:02d}'] = (info(path), pcm)
    overlap = []
    for name, (fmt, pcm) in decoded.items():
        width = fmt['channels'] * (fmt['bits'] // 8)
        for other, (other_fmt, other_pcm) in comparisons.items():
            if other == name or (other in decoded and other < name):
                continue
            if any(fmt[k] != other_fmt[k] for k in ('rate', 'channels', 'bits')):
                continue
            # Selected full-source anchors allow shifted offsets in the other
            # source. Avoid treating silence as proof of shared recording.
            for start in range(0, len(pcm) - 1024 * width + 1, max(1024, fmt['rate'] // 2) * width):
                anchor = pcm[start:start + 1024 * width]
                if len(set(anchor)) < 8:
                    continue
                found = other_pcm.find(anchor)
                if found >= 0 and found % width == 0:
                    overlap.append({'source': name, 'other': other, 'sample_offset': start // width,
                                    'other_sample_offset': found // width, 'samples': 1024})
                    break
    readmes = [CORPUS / 'README.txt', CORPUS / 'subset/README.txt', CORPUS / 'uncommon/README.txt']
    recordings, recording_environment = prepare_speech()
    report = {'task_id': 'speed-first-encoder-20260929', 'purpose': 'Untuned final validation gate, not performance/search feedback.',
              'selection_sha256': sha(serialized), 'script': relative(Path(__file__)),
              'script_sha256': sha(Path(__file__).read_bytes()),
              'libflac_version': subprocess.check_output([str(FLAC), '--version'], text=True).strip(),
              'libflac_sha256': sha(FLAC.read_bytes()),
              'readmes': [{'path': relative(p), 'sha256': sha(p.read_bytes())} for p in readmes],
              'excluded': ['subset 01-10 blocksize variants', 'subset 28-37 high-resolution/resampled variants',
                           'subset 38-44 related surround voice family', 'subset 60-63 mono/overflow family', 'VOiCES speech'],
              'cases': sources + generated + recordings, 'decode_commands': commands,
              'new_recordings': recording_environment,
              'exact_non_silent_anchor_overlap': overlap,
              'independence_limits': ['README does not establish independent recording sessions or music provenance for selected public sources.',
                                     'Exact 1024-frame anchors detect some duplicate continuous PCM at matching formats, not resampled, altered, or disjoint segments from the same recording.',
                                     'Public conformance sources were used in previous correctness validation. This is a holdout from the current speed-first tuning/benchmark set, not unseen project-wide data.',
                                     'Six generated families are synthetic stress signals. They are not counted as independent real recordings.',
                                     'Two newly acquired human readings have distinct named readers/texts, from the same LibriVox collection. They do not prove broad speaker/genre generalization.',
                                     'A separately licensed Musopen/Paul Pitman Moonlight Sonata music source was investigated, but the original Wikimedia media returned HTTP 429 then 403. No audio was acquired or included; the cached licensing page is not music evidence.',
                                     'New speech sources are lossy MP3; exact integer PCM targets are frozen after FFmpeg conversion. A 24-bit target does not imply a 24-bit recording master.'],
              'size_budget': {'aggregate_ratio_max': 1.01, 'each_case_ratio_max': 1.03},
              'reproduce': 'python scripts/prepare_speed_first_holdout.py',
              'encoding_or_performance_measurements_performed': False}
    encoded = json.dumps(report, indent=2, ensure_ascii=False).encode('utf-8') + b'\n'
    if MANIFEST.exists():
        old = json.loads(MANIFEST.read_text(encoding='utf-8'))
        assert old['selection_sha256'] == report['selection_sha256']
        old_cases = [(c['name'], c['pcm_sha256']) for c in old['cases']]
        assert old_cases == [(c['name'], c['pcm_sha256']) for c in report['cases'][:len(old_cases)]]
    MANIFEST.write_bytes(encoded)
    print(json.dumps({'cases': len(report['cases']), 'selection_sha256': report['selection_sha256'],
                      'anchor_overlaps': overlap, 'encoding_performed': False}))


if __name__ == '__main__':
    main()

"""Prepare a second sealed holdout, without reading encoder outputs or encoding.

Run from the project root: python scripts/prepare_speed_first_holdout2.py
The first 17-case holdout remains diagnostic and must still pass the final gate.
"""
import hashlib
import json
import math
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / 'validation/cache/speed-first-holdout2'
REPORT = ROOT / 'validation/evidence/speed-first-holdout2-manifest.json'
CORPUS = ROOT / 'validation/cache/flac-test-files'
FLAC = ROOT / 'validation/cache/libflac/flac-1.5.0-win/Win64/flac.exe'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def rel(path):
    return path.relative_to(ROOT).as_posix()


def generated(kind, bits, channels, count, seed):
    scale = 1 << (bits - 1)
    old = [0] * channels
    older = [0] * channels
    state = seed
    result = bytearray()
    for i in range(count):
        for ch in range(channels):
            state = (state * 1103515245 + 12345) & 0x7FFFFFFF
            centered = state - (1 << 30)
            noise = centered * scale // (1 << 30)
            if kind == 'chirp':
                # Independently synthesized sweep, including phase differences.
                phase = 2 * math.pi * ((17 + ch * 11) * i / 48000 + 5000 * (i / 48000) ** 2 / 2)
                value = round(math.sin(phase) * (scale - 1) * 0.7)
            elif kind == 'ar-roots':
                # Three stable real/complex-root recurrences with integer math.
                coefficients = [(31, 0, 32), (7, -3, 4), (7, -7, 8)]
                a, b, denominator = coefficients[ch % 3]
                value = (a * old[ch] + b * older[ch]) // denominator + noise // 32
            elif kind == 'alternating-magnitudes':
                magnitude = (scale - 1) >> ((i // 113 + ch * 3) % bits)
                value = magnitude if i % 2 else -magnitude - 1
            elif kind == 'bursts':
                period = 701 + ch * 43
                value = noise if i % period < 97 else (old[ch] * 15 // 16 if i % period < 193 else 0)
            else:
                period = 127 + ch * 18
                value = noise // 8 + (((i % period) * 2 * scale // period) - scale) // 2
            value = max(-scale, min(scale - 1, value))
            older[ch], old[ch] = old[ch], value
            result.extend(value.to_bytes((bits + 7) // 8, 'little', signed=True))
    return bytes(result)


def main():
    CACHE.mkdir(parents=True, exist_ok=True)
    cases = []
    for number in [12, 16, 18, 58]:
        source = next((CORPUS / 'subset').glob(f'{number:02d} - *.flac'))
        content = source.read_bytes()
        field = int.from_bytes(content[18:26], 'big')
        rate, channels, bits, total = field >> 44, ((field >> 41) & 7) + 1, ((field >> 36) & 31) + 1, field & ((1 << 36) - 1)
        start, count = rate, min(rate * 2, total - rate)
        name = f'holdout2-corpus-{number:02d}'
        cases.append(dict(name=name, source=rel(source), source_sha256=sha(content),
                          path=rel(CACHE / (name + '.raw')), bits=bits, channels=channels,
                          rate=rate, sample_offset=start, samples=count, total_samples=total,
                          block=4096 if number % 2 == 0 else 4095, effort=8,
                          kind='public-conformance-source',
                          provenance='CC0 FLAC testbench, previously unselected file. README describes codec/metadata features only; independent recording identity and authenticity are not established. Original continuous samples, no resampling/channel changes.'))
    specs = [('chirp', 16, 1, 4096), ('chirp', 24, 3, 4095),
             ('ar-roots', 32, 2, 8192), ('ar-roots', 20, 6, 257),
             ('alternating-magnitudes', 4, 4, 256), ('alternating-magnitudes', 31, 8, 65535),
             ('bursts', 24, 5, 4096), ('bursts', 32, 7, 1023),
             ('ramp-noise', 12, 2, 2048), ('ramp-noise', 7, 1, 511)]
    for index, (kind, bits, channels, block) in enumerate(specs):
        name = f'holdout2-generated-{index:02d}-{kind}'
        cases.append(dict(name=name, path=rel(CACHE / (name + '.raw')), kind='synthetic',
                          generator=kind, bits=bits, channels=channels, rate=48000,
                          samples=block * 2 + 37 if block == 65535 else 48037,
                          sample_offset=0, block=block, effort=8, seed=7129639 + index * 7919,
                          provenance='New synthetic family/parameters; not an independent real recording. Integer AR/burst/ramp formulas or Python sin chirp; frozen PCM SHA is authoritative across math-library differences.'))
    selection = {'cases': cases, 'preparation_script_sha256': sha(Path(__file__).read_bytes())}
    encoded_selection = json.dumps(selection, sort_keys=True, indent=2).encode() + b'\n'
    frozen = CACHE / 'frozen-selection.json'
    if frozen.exists():
        assert frozen.read_bytes() == encoded_selection, 'Second holdout selection is frozen'
    else:
        frozen.write_bytes(encoded_selection)
    # Selection is fixed on disk before decode/generation, and before encoding.
    for case in cases:
        if case['kind'] == 'synthetic':
            pcm = generated(case['generator'], case['bits'], case['channels'], case['samples'], case['seed'])
        else:
            command = [str(FLAC), '-d', '-c', '--force-raw-format', '--endian=little', '--sign=signed', str(ROOT / case['source'])]
            run = subprocess.run(command, capture_output=True, timeout=120)
            assert run.returncode == 0, run.stderr.decode(errors='replace')
            width = case['channels'] * ((case['bits'] + 7) // 8)
            assert len(run.stdout) == case['total_samples'] * width
            start = case['sample_offset'] * width
            pcm = run.stdout[start:start + case['samples'] * width]
            case['decode_command'] = [rel(FLAC), *command[1:-1], case['source']]
            case['full_source_pcm_sha256'] = sha(run.stdout)
        case.update(pcm_bytes=len(pcm), pcm_sha256=sha(pcm))
        output = ROOT / case['path']
        if output.exists():
            assert output.read_bytes() == pcm, 'Frozen PCM changed'
        else:
            output.write_bytes(pcm)
    report = dict(task_id='speed-first-encoder-20260929', role='second sealed holdout; first holdout remains required diagnostic gate',
                  selection_sha256=sha(encoded_selection), preparation_script=rel(Path(__file__)),
                  script_sha256=sha(Path(__file__).read_bytes()), cases=cases,
                  libflac_sha256=sha(FLAC.read_bytes()),
                  readme_sha256=sha((CORPUS / 'subset/README.txt').read_bytes()),
                  budgets=dict(aggregate_max_ratio=1.01, per_case_max_ratio=1.03),
                  limitations=['No new network assets or dependencies acquired.',
                               'Four public file selections are distinct from the first holdout and original benchmark. Neither filenames nor metadata prove independently recorded content; codec variants or related source excerpts may remain.',
                               'First-holdout LibriVox files were used in full; no unused segment of those recordings is represented as new material.',
                               'Ten synthetic cases provide deterministic new signals and stress shapes, not real-world recording diversity.',
                               'All candidate outputs and encoding/performance results were uninspected during selection.'],
                  encoding_performed=False, reproduce='python scripts/prepare_speed_first_holdout2.py')
    payload = json.dumps(report, indent=2).encode() + b'\n'
    if REPORT.exists():
        assert REPORT.read_bytes() == payload, 'Second holdout manifest is frozen'
    else:
        REPORT.write_bytes(payload)
    print(json.dumps({'cases': len(cases), 'selection_sha256': report['selection_sha256'], 'encoding_performed': False}))


if __name__ == '__main__':
    main()

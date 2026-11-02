"""Diagnose FFmpeg raw-FLAC parsing using independently located, unchanged frames.

Run from the project root: python scripts/packetized_flac.py
This validation-only Ogg mapper uses official libFLAC analysis, not MoonFLAC.
"""
import argparse
import hashlib
import json
import re
import shutil
import struct
import subprocess
from pathlib import Path


def digest(data):
    return hashlib.sha256(data).hexdigest()


def crc_bitwise(data):
    result = 0
    for byte in data:
        result ^= byte << 24
        for _ in range(8):
            result = ((result << 1) ^ (0x04C11DB7 if result & 0x80000000 else 0)) & 0xFFFFFFFF
    return result


CRC_TABLE = tuple(crc_bitwise(bytes([value])) for value in range(256))


def crc(data):
    result = 0
    for byte in data:
        result = ((result << 8) & 0xFFFFFFFF) ^ CRC_TABLE[(result >> 24) ^ byte]
    return result


def packetize(streaminfo, frames, comments=True):
    packets = [b'\x7fFLAC\x01\x00' + (b'\x00\x01fLaC\x00' if comments else b'\x00\x00fLaC\x80') + b'\x00\x00\x22' + streaminfo]
    if comments:
        packets.append(b'\x84\x00\x00\x08' + bytes(8))
    header_count = len(packets)
    packets.extend(frame['data'] for frame in frames)
    output = bytearray()
    sequence = 0
    samples = 0
    pages = []
    for index, packet in enumerate(packets):
        segments = [255] * (len(packet) // 255) + [len(packet) % 255]
        consumed = 0
        if index >= header_count:
            samples += frames[index - header_count]['blocksize']
        for start in range(0, len(segments), 255):
            lace = segments[start:start + 255]
            complete = start + len(lace) == len(segments)
            flags = (2 if sequence == 0 else 0) | (1 if start else 0)
            if complete and index == len(packets) - 1:
                flags |= 4
            granule = samples if complete else 0xFFFFFFFFFFFFFFFF
            payload = packet[consumed:consumed + sum(lace)]
            consumed += len(payload)
            page = bytearray(b'OggS\x00' + bytes([flags]) + struct.pack('<QIII', granule, 9639, sequence, 0))
            page += bytes([len(lace)]) + bytes(lace) + payload
            checksum = crc(page)
            page[22:26] = struct.pack('<I', checksum)
            output += page
            pages.append({'sequence': sequence, 'flags': flags, 'granule': granule,
                          'segments': len(lace), 'payload_bytes': len(payload), 'crc': checksum})
            sequence += 1
        assert consumed == len(packet)
    return bytes(output), pages


def run(command):
    result = subprocess.run([str(x) for x in command], capture_output=True, timeout=180)
    return {'command': [str(x) for x in command], 'exit': result.returncode,
            'stderr': result.stderr.decode('utf-8', errors='replace')}


def analyze_frames(source, analysis, flac):
    analysis_run = run([flac, '-a', '-f', '-o', analysis, source])
    assert analysis_run['exit'] == 0, analysis_run
    data = source.read_bytes()
    assert data[:8] == b'fLaC\x00\x00\x00\x22' or data[:8] == b'fLaC\x80\x00\x00\x22'
    records = []
    for match in re.finditer(r'^frame=(\d+)\s+offset=(\d+)\s+bits=(\d+)\s+blocksize=(\d+)', analysis.read_text(), re.M):
        number, offset, count, blocksize = map(int, match.groups())
        assert count % 8 == 0
        records.append({'frame': number, 'offset': offset, 'bytes': count // 8,
                        'blocksize': blocksize, 'data': data[offset:offset + count // 8]})
    assert records and records[-1]['offset'] + records[-1]['bytes'] == len(data)
    for left, right in zip(records, records[1:]):
        assert left['offset'] + left['bytes'] == right['offset']
    return data, records, analysis_run


def wrap_file(source: Path, wrapped: Path, flac: Path):
    """Wrap unchanged frames using official analysis; perform no decoder trials.

    Writes the Ogg file and an adjacent .ana analysis artifact. Returns only
    JSON-serializable source, STREAMINFO, frame, page, and analysis identities.
    """
    wrapped.parent.mkdir(parents=True, exist_ok=True)
    data, records, analysis_run = analyze_frames(source, wrapped.with_suffix('.ana'), flac)
    ogg, pages = packetize(data[8:42], records)
    wrapped.write_bytes(ogg)
    return {'input': str(source), 'input_sha256': digest(data), 'ogg': str(wrapped),
            'ogg_sha256': digest(ogg), 'streaminfo_hex': data[8:42].hex(),
            'analysis': analysis_run,
            'frames': [{**{k: v for k, v in r.items() if k != 'data'}, 'sha256': digest(r['data'])} for r in records],
            'frame_bytes_unchanged': True, 'header_packets': 2, 'pages': pages}


def examine(source, pcm, flac, ffmpeg, cache, label, bits, channels):
    wrapped = cache / (label + '.oga')
    proof = wrap_file(source, wrapped, flac)
    data = source.read_bytes()
    records = [{**r, 'data': data[r['offset']:r['offset'] + r['bytes']]} for r in proof['frames']]
    expected = pcm.read_bytes()
    assert len(expected) == sum(r['blocksize'] for r in records) * channels * (bits // 8)
    runs = {}
    no_comment, _ = packetize(data[8:42], records, comments=False)
    no_comment_file = cache / (label + '-no-comment.oga')
    no_comment_file.write_bytes(no_comment)
    runs['ffmpeg_no_comment_header_exploration'] = run([ffmpeg, '-hide_banner', '-loglevel', 'warning', '-i', no_comment_file, '-f', 'null', '-'])
    for name, file in [('raw', source), ('ogg', wrapped)]:
        decoded = cache / (label + '-' + name + '.pcm')
        entry = run([ffmpeg, '-hide_banner', '-loglevel', 'warning', '-y', '-i', file,
                     '-map', '0:a:0', '-c:a', f'pcm_s{bits}le', '-f', f's{bits}le', decoded])
        actual = decoded.read_bytes() if decoded.exists() else b''
        entry.update(bytes=len(actual), sha256=digest(actual), exact_pcm=actual == expected)
        runs['ffmpeg_' + name] = entry
    independent = cache / (label + '-libflac.pcm')
    entry = run([flac, '-d', '-f', '--force-raw-format', '--endian=little', '--sign=signed', '-o', independent, wrapped])
    actual = independent.read_bytes() if independent.exists() else b''
    entry.update(bytes=len(actual), sha256=digest(actual), exact_pcm=actual == expected)
    runs['libflac_ogg'] = entry
    assert runs['ffmpeg_ogg']['exit'] == 0 and runs['ffmpeg_ogg']['exact_pcm'], runs
    assert entry['exit'] == 0 and entry['exact_pcm'], entry
    return {**proof, 'pcm': str(pcm), 'pcm_sha256': digest(expected),
            'pcm_bytes': len(expected), 'decoders': runs}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, default=Path('validation/evidence/effort8-ffmpeg-parser.json'))
    args = parser.parse_args()
    crc_lengths = [0, 1, 2, 255, 256, 65025, 65536]
    for length in crc_lengths:
        payload = bytes((i * 17 + i // 251) % 256 for i in range(length))
        assert crc(payload) == crc_bitwise(payload)
    for value in range(65536):
        payload = value.to_bytes(2, 'little')
        assert crc(payload) == crc_bitwise(payload)
    cache = Path('validation/cache/packetized-flac')
    cache.mkdir(parents=True, exist_ok=True)
    flac = Path('validation/cache/libflac/flac-1.5.0-win/Win64/flac.exe').resolve()
    ffmpeg = shutil.which('ffmpeg')
    assert ffmpeg
    manifest = json.loads(Path('validation/cache/effort8-benchmark/core-inputs.json').read_text())
    case = next(c for c in manifest['cases'] if c['name'] == 'maximum-block-32-8')
    pcm = Path(case['path'])
    assert digest(pcm.read_bytes()) == case['pcm_sha256']
    baseline = Path('validation/cache/effort8-benchmark/effort8-core-benchmark-maximum-block-32-8-baseline.flac')
    results = [examine(baseline, pcm, flac, ffmpeg, cache, 'moon-baseline', case['bits'], case['channels'])]
    reference = cache / 'libflac-source.flac'
    encode = run([flac, '-f', '-8', '--lax', '--blocksize=65535', '--force-raw-format',
                  '--endian=little', '--sign=signed', '--bps=32', '--channels=8', '--sample-rate=48000',
                  '-o', reference, pcm])
    assert encode['exit'] == 0, encode
    results.append(examine(reference, pcm, flac, ffmpeg, cache, 'libflac-source', 32, 8))
    report = {'purpose': 'Independent demux/parser diagnostic; original frame bytes are never re-encoded by the mapper.',
              'crc_table_validation': {'exhaustive_two_byte_inputs': 65536, 'long_payload_lengths': crc_lengths, 'matches_bitwise_reference': True},
              'script_sha256': digest(Path(__file__).read_bytes()),
              'ffmpeg_binary_sha256': digest(Path(ffmpeg).read_bytes()),
              'libflac_binary_sha256': digest(flac.read_bytes()),
              'ffmpeg_version': subprocess.check_output([ffmpeg, '-version'], text=True).splitlines()[0],
              'libflac_version': subprocess.check_output([str(flac), '--version'], text=True).strip(),
              'mapping': 'Ogg FLAC 1.0; one following header packet; copied STREAMINFO not marked last; empty VORBIS_COMMENT marked last; one original FLAC frame per packet; continuation pages at 255 laces; final EOS and cumulative sample granules. A zero-following-header/no-comment exploratory variant is recorded separately and is not used as successful conformance evidence.',
              'reference_encode': encode, 'cases': results,
              'conclusion': 'Successful unchanged-frame Ogg decoding isolates the observed failure to the raw-input path, rather than inability of the FFmpeg FLAC decoder to decode these frames. A particular raw-parser heuristic is an inference requiring separate source inspection, not established by this experiment alone.',
              'limitations': 'Single FFmpeg Windows 9.0.1 build and this finite two-frame input; no claim that all large raw FLAC frames fail. FFmpeg DLL identities are not captured, only the executable hash and reported version. This is a validation mapper, not a production feature. Original metadata other than STREAMINFO is replaced with an empty comment for the transport experiment; audio frame bytes remain identical.'}
    args.report.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps([{'input': r['input'], 'raw_bytes': r['decoders']['ffmpeg_raw']['bytes'],
                       'ogg_exact': r['decoders']['ffmpeg_ogg']['exact_pcm']} for r in results]))


if __name__ == '__main__':
    main()

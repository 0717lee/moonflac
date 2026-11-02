"""Add stratified Rice ranking for irregular blocks to candidate9."""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / '_build/faster-than-libflac'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace_once(text, old, new):
    assert text.count(old) == 1, old
    return text.replace(old, new)


def main():
    parents = []
    for name in ['faster-than-libflac-candidate9.json',
                 'faster-than-libflac/rice-ranked-irregular/identity.json']:
        path = ROOT / 'validation/evidence' / name
        record = json.loads(path.read_text())
        for source, digest in record['sources'].items():
            assert sha(ROOT / source) == digest, source
        parents.append(dict(path=str(path.relative_to(ROOT)), sha256=sha(path)))
    destination = BASE / 'candidate10-source'
    assert not destination.exists()
    shutil.copytree(BASE / 'candidate9-source', destination,
                    ignore=shutil.ignore_patterns('_build', '.git', '__pycache__'))
    donor = BASE / 'rice-ranked-irregular-source'
    text = (donor / 'encoder_search.mbt').read_text(encoding='utf8')
    begin = text.index('///|\nfn encoder_rice_probe_positions')
    end = text.index('///|\n/// log2(x)', begin)
    path = destination / 'encoder_search.mbt'
    original = path.read_text(encoding='utf8')
    original = replace_once(original, '///|\n/// log2(x)',
                            text[begin:end] + '///|\n/// log2(x)')
    path.write_text(original, encoding='utf8')
    shutil.copy2(donor / 'encoder_rice_rank_wbtest.mbt',
                 destination / 'encoder_rice_rank_wbtest.mbt')
    path = destination / 'encoder_frame.mbt'
    text = path.read_text(encoding='utf8')
    text = replace_once(text,
        '    // An irregular block cannot support the coarse partition grid. Shared\n'
        '    // Rice costs then couple many values, including outliers near warm-ups.\n',
        '    // Irregular blocks rank stratified exact integer residual probes by\n'
        '    // shared Rice costs, including all edge samples around warm-ups.\n'
        '    let rice_irregular = effort == 8 && size > ENCODER_LPC_PROBES &&\n'
        '      size % (1 << ENCODER_PARTITION_CAP) != 0 && !deep_partitions\n')
    text = replace_once(text, '    let candidates = if shortlist {',
        '    let candidates = if rice_irregular {\n'
        '      encoder_lpc_rice_ranking(shifted, models, depth)\n'
        '    } else if shortlist {')
    text = replace_once(text,
        '      if shortlist && valid_candidates >= ENCODER_LPC_SHORTLIST {',
        '      if (shortlist || rice_irregular) && valid_candidates >= ENCODER_LPC_SHORTLIST {')
    path.write_text(text, encoding='utf8')
    with (BASE / 'candidate10-format.log').open('w', encoding='utf8') as log:
        for command in [['moon', 'fmt'],
                        ['moonfmt', '-w', 'encoder_rice_rank_wbtest.mbt'],
                        ['moon', 'fmt', '--check']]:
            subprocess.run(command, cwd=destination, stdout=log,
                           stderr=subprocess.STDOUT, check=True)
    files = {str(p.relative_to(destination)): sha(p)
             for p in destination.rglob('*') if p.is_file()
             and not any(part in {'_build', '.git', '.mooncakes'}
                         for part in p.relative_to(destination).parts)}
    report = dict(status='prepared_before_build', parents=parents,
                  source=str(destination.relative_to(ROOT)), files=files,
                  generator_sha256=sha(Path(__file__)),
                  policy='Candidate9 regular/short/deep/effort0-7 policy retained; '
                         'irregular effort8 blocks above256 rank stratified Rice '
                         'costs with four legal finalists and exact full planner.')
    path = ROOT / 'validation/evidence/faster-than-libflac-candidate10-source.json'
    assert not path.exists()
    path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf8')


if __name__ == '__main__':
    main()

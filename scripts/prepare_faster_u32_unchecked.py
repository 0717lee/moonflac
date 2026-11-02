"""Remove only proven private scratch indexing checks in an isolated planner."""
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / '_build/faster-than-libflac'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parent_path = ROOT / 'validation/evidence/faster-than-libflac-u32-plan-identity.json'
    parent = json.loads(parent_path.read_text())
    for path, digest in parent['sources'].items():
        assert sha(ROOT / path) == digest
    destination = BASE / 'u32-unchecked-source'
    assert not destination.exists()
    shutil.copytree(BASE / 'u32-plan-source', destination,
                    ignore=shutil.ignore_patterns('_build', '.git', '__pycache__'))
    path = destination / 'encoder_budget_plan.mbt'
    lines = path.read_text().splitlines()
    fields = 'prefixes|ready|folded|widths|width_sums|sums|choices0|choices1'
    assignment = re.compile(r'^(\s*)scratch\.(' + fields + r')\[([^\]]+)\] = (.*)$')
    reads = re.compile(r'(scratch\.(?:' + fields + r')|samples|choices)\[([^\[\]\n]+)\]')
    output = []
    writes = 0
    index = 0
    while index < len(lines):
        line = lines[index]
        match = assignment.match(line)
        if match:
            indent, field, subscript, rhs = match.groups()
            # The frozen parent's only continued assignment is a binary sum.
            while rhs.rstrip().endswith('+'):
                index += 1
                rhs += '\n' + lines[index].strip()
            assert rhs.count('(') == rhs.count(')')
            assert rhs.count('{') == rhs.count('}')
            line = f'{indent}scratch.{field}.unsafe_set({subscript}, {rhs})'
            writes += 1
        if not line.lstrip().startswith('//'):
            line = reads.sub(lambda m: f'{m[1]}.unsafe_get({m[2]})', line)
        output.append(line)
        index += 1
    assert writes == 22, writes
    proof = '''// Private indexing invariants: 0<=predictor<size<=65535; every legal
// partition divides size and has step>predictor. Collection ends at size.
// Width/sum trees are allocated to at least 2*leaves together; choices have
// at least leaves entries. All visited levels have parts<=leaves; children
// of node<leaves are below 2*leaves. Ready/prefix-column arrays have 31 entries
// and all requested parameters are in 0..30. Prefix storage is separately
// ensured to have leaves+1 entries before any query. These arrays are private
// scratch, never exposed to callers; winners own scalar copies.

'''
    path.write_text(proof + '\n'.join(output) + '\n', encoding='utf8')
    with (BASE / 'u32-unchecked-format.log').open('w', encoding='utf8') as log:
        subprocess.run(['moonfmt', '-w', path.name], cwd=destination,
                       stdout=log, stderr=subprocess.STDOUT, check=True)
    sources = {str((destination / Path(p).name).relative_to(ROOT)): sha(destination / Path(p).name)
               for p in parent['sources']}
    record = dict(status='prepared_before_build', parent=dict(path=str(parent_path.relative_to(ROOT)),
                  sha256=sha(parent_path)), sources=sources, transformed_assignments=writes,
                  generator_sha256=sha(Path(__file__)))
    target = ROOT / 'validation/evidence/faster-than-libflac-u32-unchecked-prebuild.json'
    assert not target.exists()
    target.write_text(json.dumps(record, indent=2) + '\n')


if __name__ == '__main__':
    main()

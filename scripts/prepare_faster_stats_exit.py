"""Stop subframe statistics once both monotone answers are determined."""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / '_build/faster-than-libflac'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    identity_path = ROOT / 'validation/evidence/faster-than-libflac-candidate11-double.json'
    identity = json.loads(identity_path.read_text())
    for name, digest in identity['sources'].items():
        assert sha(ROOT / name) == digest, name
    source = BASE / 'candidate11-double-source'
    destination = BASE / 'candidate17-stats-exit-source'
    assert not destination.exists()
    shutil.copytree(source, destination,
                    ignore=shutil.ignore_patterns('_build', '.git', '__pycache__', 'checks', 'evidence'))
    path = destination / 'encoder_frame.mbt'
    text = path.read_text(encoding='utf8')
    old = '''      if zeros < wasted {
        wasted = zeros
      }
    }
  }
  let mut best : EncoderSubframe = {'''
    new = '''      if zeros < wasted {
        wasted = zeros
      }
    }
    // Both facts are monotone: a differing sample cannot become constant,
    // and common trailing-zero count cannot decrease below zero. Public PCM
    // validation already covers the entire accepted input before this search.
    if wasted == 0 && !constant_input {
      break
    }
  }
  let mut best : EncoderSubframe = {'''
    assert text.count(old) == 1
    path.write_text(text.replace(old, new), encoding='utf8')
    with (BASE / 'candidate17-stats-exit-format.log').open('w', encoding='utf8') as log:
        for command in [['moon', 'fmt'], ['moon', 'fmt', '--check']]:
            subprocess.run(command, cwd=destination, stdout=log,
                           stderr=subprocess.STDOUT, check=True)
    files = {str(p.relative_to(destination)): sha(p)
             for p in destination.rglob('*') if p.is_file()
             and not any(part in {'_build', '.git', '.mooncakes'}
                         for part in p.relative_to(destination).parts)}
    report = dict(status='prepared_before_build',
                  parent=dict(path=str(identity_path.relative_to(ROOT)), sha256=sha(identity_path)),
                  source=str(destination.relative_to(ROOT)), files=files,
                  generator_sha256=sha(Path(__file__)),
                  proof='Only exits after nonconstant and minimum trailing-zero count0 '
                        'are known. Later samples cannot change either result. '
                        'Public validation and all subsequent full predictor/residual '
                        'checks are unchanged; zero/common-wasted/constant blocks '
                        'continue scanning as before.')
    path = ROOT / 'validation/evidence/faster-than-libflac-candidate17-stats-exit-source.json'
    assert not path.exists()
    path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf8')


if __name__ == '__main__':
    main()

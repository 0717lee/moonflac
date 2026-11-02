"""Run final Windows hardening correctness gates, retaining earlier evidence.

All subprocess failures propagate. Commands and full logs are preserved under
_build/hardening/checks; independent reports use validation/evidence/hardening.
"""
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
LOGS=ROOT/'_build/hardening/checks'
REPORTS=ROOT/'validation/evidence/hardening'
CLI=ROOT/'_build/hardening/candidate/native/release/build/cmd/moonflac/moonflac.exe'
FLAC=ROOT/'validation/cache/libflac/flac-1.5.0-win/Win64/flac.exe'


def main():
    LOGS.mkdir(parents=True,exist_ok=True)
    REPORTS.mkdir(parents=True,exist_ok=True)
    records=[]
    def run(name,command):
        start=time.monotonic()
        with (LOGS/(name+'.log')).open('w',encoding='utf-8') as log:
            result=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=3600)
        records.append(dict(name=name,command=[str(x) for x in command],seconds=time.monotonic()-start,exit_code=result.returncode))
        (REPORTS/'commands.json').write_text(json.dumps(records,indent=2)+'\n',encoding='utf-8')
        print(name,result.returncode,flush=True)
        result.check_returncode()
    for target in ['native','js','wasm-gc']:
        for action in ['check','test','build']:
            command=['moon',action,'--target',target,'--target-dir','_build/hardening/candidate']
            if action=='build':command.append('--release')
            run(target+'-'+action,command)
    run('format',['moon','fmt','--check'])
    run('public-api',['moon','info'])
    run('decoder-cli',[sys.executable,'cmd/test_cli.py','--cli',str(CLI),'--flac',str(FLAC)])
    run('encoder-cli',[sys.executable,'cmd/test_encoder_cli.py','--cli',str(CLI),'--flac',str(FLAC)])
    # The existing oracle script routes several action reports through EVIDENCE.
    # Override that module constant in-process to retain the accepted old reports.
    prefix="import sys;sys.path.insert(0,'scripts');import validate_encoder as v;from pathlib import Path;v.EVIDENCE=Path('validation/evidence/hardening').resolve();"
    for action,extra in [
        ('compare',['--report',str(REPORTS/'encoder-native.json'),'--ffmpeg','ffmpeg']),
        ('forced',['--log',str(LOGS/'native-test.log')]),
        ('cross',[]),('full-corpus',['--timeout','600'])]:
        run('oracle-'+action,[sys.executable,'-X','utf8','-c',prefix+'v.main()',action,'--cli',str(CLI),'--flac',str(FLAC)]+extra)
    sources={}
    for path in list(ROOT.glob('*.mbt'))+list((ROOT/'cmd/moonflac').glob('*')):
        if path.is_file() and not path.name.endswith(('_test.mbt','_wbtest.mbt')):
            sources[path.relative_to(ROOT).as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
    final=dict(status='pass',commands=records,codec_sources=sources,
               cli_sha256=hashlib.sha256(CLI.read_bytes()).hexdigest())
    (REPORTS/'acceptance.json').write_text(json.dumps(final,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':main()

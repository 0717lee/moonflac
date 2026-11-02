"""Functional-only validation of isolated table CRC; no timing comparison."""
from pathlib import Path
import hashlib,json,re,subprocess
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'_build/faster-than-libflac/crc-table-source'
BUILD=ROOT/'_build/faster-than-libflac/crc-table-build'
RESULTS=ROOT/'_build/faster-than-libflac/crc-table-smoke'
RESULTS.mkdir(parents=True,exist_ok=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
identity=json.loads((ROOT/'validation/evidence/faster-than-libflac-candidate7.json').read_text())
baseline=ROOT/identity['core']['path'];assert sha(baseline)==identity['core']['sha256']
candidate=BUILD/'native/release/build/validation/benchmark_compete/benchmark_compete.exe'
flac=ROOT/'validation/cache/libflac/flac-1.5.0-win/Win64/flac.exe'
report={'variant':'CRC8-CRC16-tables-on-frozen-C7','core':{'path':str(candidate.relative_to(ROOT)),'sha256':sha(candidate)},
 'sources':{str(p.relative_to(ROOT)):sha(p) for p in SOURCE.glob('*.mbt') if not p.name.endswith(('_wbtest.mbt','_test.mbt'))},
 'policies_unchanged':True,'performance_measured':False,'production_changed':False,
 'tests':{},
 'libflac':{'path':str(flac.relative_to(ROOT)),'sha256':sha(flac)},'cases':[]}
manifest=json.loads((ROOT/'validation/evidence/faster-than-libflac-inputs-original-core.json').read_text())
for target in ['native','js','wasm-gc']:
 log=ROOT/f'validation/results/faster-than-libflac-crc-table-{target}.log'
 match=re.search(r'Total tests: (\d+), passed: (\d+), failed: (\d+)',log.read_text(encoding='utf-8'))
 assert match and int(match[3])==0 and int(match[1])==int(match[2])
 buildlog=ROOT/f'validation/results/faster-than-libflac-crc-table-build-{target}.log'
 assert '0 errors)' in buildlog.read_text(encoding='utf-8')
 report['tests'][target]={'passed':int(match[2]),'failed':0,'log':str(log.relative_to(ROOT)),'release_build':'passed','build_log':str(buildlog.relative_to(ROOT))}
for case in manifest['cases']:
 outputs=[]
 for label,exe in [('C7',baseline),('tables',candidate)]:
  out=RESULTS/(case['name']+'-'+label+'.flac')
  cmd=[str(exe),str(ROOT/case['path']),str(out),str(case['channels']),str(case['bits']),str(case['rate']),str(case['block']),'1','8']
  p=subprocess.run(cmd,capture_output=True,text=True,timeout=180)
  assert p.returncode==0,p.stderr
  outputs.append(out)
 assert outputs[0].read_bytes()==outputs[1].read_bytes(),case['name']
 checked=subprocess.run([str(flac),'-t','-s',str(outputs[1])],capture_output=True,text=True,timeout=60)
 assert checked.returncode==0,checked.stderr
 report['cases'].append({'case':case['name'],'pcm_sha256':sha(ROOT/case['path']),'encoded_bytes':outputs[1].stat().st_size,
   'encoded_sha256':sha(outputs[1]),'C7_bytes_identical':True,'libflac_test_exit':checked.returncode})
(ROOT/'validation/evidence/faster-than-libflac-crc-table-identity.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'core':report['core'],'cases_passed':len(report['cases']),'performance_measured':False}))

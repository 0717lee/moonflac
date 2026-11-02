"""Speed-first Windows-hosted WSL correctness; reuse installed read-only SDKs.
Run with WSL python3 scripts/validate_speed_first_linux.py, never alongside benchmarks.
All outputs are under _build/speed-first/linux or validation/evidence/speed-first.
"""
import os,sys,re,json,subprocess,hashlib,random,platform,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--revision',type=int)
args=parser.parse_args()
if args.revision is not None and args.revision < 1:parser.error('revision must be positive')
suffix='' if args.revision is None else '-revision'+str(args.revision)
TOOLS=ROOT/'_build/hardening/linux-tools'
LOG=ROOT/('_build/speed-first/linux'+suffix)/'logs'
BUILD=ROOT/('_build/speed-first/linux'+suffix)/'build'
LOG.mkdir(parents=True,exist_ok=True)
BUILD.mkdir(parents=True,exist_ok=True)
FLAC=TOOLS/'flac-prefix/bin/flac'
LIB=str(TOOLS/'flac-prefix/lib/libFLAC.so')
os.environ['MOON_HOME']=str(TOOLS/'moon-home')
os.environ['PATH']=str(TOOLS/'moon-home/bin')+':'+str(TOOLS/'node-v22.23.3-linux-x64/bin')+':'+os.environ['PATH']
os.chdir(ROOT)
sys.path.insert(0,str(ROOT/'scripts'))
from validate import LibFLAC,packed
ref=LibFLAC(LIB)
report=dict(platform=platform.platform(),environment='Ubuntu 22.04.5 WSL2, shared Windows hardware; correctness only, not performance benchmark',commands=[],cli=[],cross=[],limitations=['FLAC reference built without Ogg','No Linux FFmpeg independent check; Windows FFmpeg validated separately','WSL2 is not independent Linux hardware'])
DEST=ROOT/('validation/evidence/speed-first/linux'+suffix+'.json')
DEST.parent.mkdir(parents=True,exist_ok=True)
if DEST.exists():raise FileExistsError('Preserve existing speed-first Linux report')
report['runner_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
def save(): DEST.write_text(json.dumps(report,indent=2)+'\n')
def run(cmd,name,timeout=600):
    p=subprocess.run([str(x) for x in cmd],capture_output=True,text=True,timeout=timeout)
    (LOG/(name+'.log')).write_text(p.stdout+p.stderr)
    report['commands'].append(dict(name=name,command=[str(x) for x in cmd],returncode=p.returncode,log=str((LOG/(name+'.log')).relative_to(ROOT))))
    save()
    if p.returncode: raise RuntimeError(name+' failed: '+p.stderr[-2500:])
    return p.stdout
try:
    if args.revision is not None:
        identity=ROOT/('validation/evidence/speed-first-candidate-revision'+str(args.revision)+'.json')
        frozen=json.loads(identity.read_text())
        for relative,digest in frozen['sources'].items():
            assert hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()==digest,'Frozen identity mismatch: '+relative
        report['revision']=args.revision
        report['frozen_identity']=str(identity.relative_to(ROOT))
        report['frozen_identity_sha256']=hashlib.sha256(identity.read_bytes()).hexdigest()
    report['toolchain']=run(['moon','version','--all'],'versions')
    report['node']=run(['node','--version'],'node-version').strip()
    report['flac']=run([FLAC,'--version'],'flac-version').strip()
    sources={}
    for directory,dirs,files in os.walk(ROOT):
        dirs[:]=[x for x in dirs if x not in ('_build','.mooncakes','cache','.git','isolate_build','node_modules')]
        for name in files:
            if name.endswith('.mbt'):
                p=Path(directory)/name;sources[str(p.relative_to(ROOT))]=hashlib.sha256(p.read_bytes()).hexdigest()
    report['source_files_sha256']=sources
    for target in ['native','js','wasm-gc']:
        for action in ['check','test','build']:
            cmd=['moon',action,'--target',target,'--target-dir',BUILD/target]
            if action=='build':cmd.append('--release')
            out=run(cmd,target+'-'+action)
            if action=='test':report.setdefault('tests',{})[target]=re.findall(r'Total tests[^\n]*',out)
    cli=BUILD/'native/native/release/build/cmd/moonflac/moonflac.exe'
    if not cli.exists():
        hits=list((BUILD/'native').rglob('moonflac.exe'))+list((BUILD/'native').rglob('moonflac'))
        cli=next(p for p in hits if p.is_file() and os.access(p,os.X_OK) and '/release/' in str(p))
    report['cli_path']=str(cli);report['cli_sha256']=hashlib.sha256(cli.read_bytes()).hexdigest()
    work=BUILD/'oracle';work.mkdir(exist_ok=True)
    for bits in [16,24,32]:
      for channels in [1,2,6,8]:
       rng=random.Random(9639+bits*8+channels)
       pcm=[rng.randint(-(1<<(bits-1)),(1<<(bits-1))-1) for _ in range(257*channels)]
       pcm[:4]=[-(1<<(bits-1)),(1<<(bits-1))-1,0,-1]
       raw=packed(pcm,bits);src=work/'input.raw';src.write_bytes(raw)
       for effort in [5,8]:
        name=f'cli-{bits}-{channels}-e{effort}';out=work/(name+'.flac');decoded=work/'decoded.raw'
        run([cli,'encode',src,out,'--raw','--sample-rate','48000','--channels',channels,'--bits',bits,'--effort',effort,'--block-size','256'],name+'-encode')
        props,actual=ref.decode(out);assert props==(channels,bits,48000) and actual==pcm,name
        run([FLAC,'-t','-s',out],name+'-flact')
        run([cli,'decode',out,decoded,'--raw'],name+'-decode');assert decoded.read_bytes()==raw,name
        report['cli'].append(dict(name=name,status='pass',frames=257,minimum=min(pcm),maximum=max(pcm),pcm_sha256=hashlib.sha256(raw).hexdigest()));save()
    source=(ROOT/'validation/encoder/main.mbt').read_text()
    arrays={k:[int(v) for v in re.findall(r'-?\d+',body)] for k,body in re.findall(r'let (pcm\d+|small)\s*:\s*Array\[Int\]\s*=\s*\[(.*?)\]',source,re.S)}
    configs={k:tuple(int(re.search(field+r'\s*:\s*(\d+)',body).group(1)) for field in ['channels','bits_per_sample','sample_rate']) for k,body in re.findall(r'let (config\d*).*?EncoderConfig::new\((.*?)(?=\n  (?:let |dump\())',source,re.S)}
    expected={name:(configs[config],arrays[arr]) for name,arr,config in re.findall(r'dump\("([^"\n]+)",\s*@flac.encode_pcm\((pcm\d+),\s*(config\d+)\)\)',source)}
    for name in re.findall(r'dump\("(stream-[^"\n]+)"',source):expected[name]=(configs['config'],arrays['small'])
    assert len(expected)==276,len(expected)
    allstreams={}
    for target in ['native','js','wasm-gc']:
        out=run(['moon','run','--target',target,'--target-dir',BUILD/target,'--release','validation/encoder'],target+'-encoded')
        streams={name:bytes.fromhex(data) for name,data in re.findall(r'^ENCODED (\S+) ([0-9a-f]+)$',out,re.M)}
        assert set(streams)==set(expected),(target,len(streams))
        cases=[]
        for name,data in streams.items():
            path=work/'cross.flac';path.write_bytes(data)
            props,actual=ref.decode(path);want,pcm=expected[name]
            assert props==want and actual==pcm,(target,name)
            cases.append(dict(name=name,status='pass',bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
        allstreams[target]=streams
        report['cross'].append(dict(target=target,status='pass',cases=cases));save()
    assert allstreams['native']==allstreams['js']==allstreams['wasm-gc']
    for relative,digest in sources.items():
        assert hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()==digest, 'Source changed during WSL validation: '+relative
    report['cross_backend_byte_identical']=True
    report['status']='pass';save();print('PASS: 3 backends, 24 CLI cases, 828 independent libFLAC encoded stream checks',flush=True)
except Exception as exc:
    report['status']='fail';report['error']=repr(exc);save();raise

"""Build and smoke-check the test-only official libFLAC buffer benchmark on Windows.

No controlled performance comparison is run here. Smoke timings only prove timer
plumbing. Generated files live under _build/faster-than-libflac/core-reference.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-dir', type=Path, default=ROOT/'_build/faster-than-libflac/core-reference')
    parser.add_argument('--headers', type=Path, default=ROOT/'_build/hardening/linux-tools/flac-prefix/include')
    parser.add_argument('--reference-dir', type=Path, default=ROOT/'validation/cache/libflac/flac-1.5.0-win/Win64')
    parser.add_argument('--report', type=Path, default=ROOT/'validation/evidence/faster-than-libflac-core-harness.json')
    args = parser.parse_args()
    if os.name != 'nt':
        raise SystemExit('This build script records the Windows official DLL baseline; see README for C portability.')
    if args.report.exists():
        raise SystemExit('Refusing to overwrite evidence; select a fresh --report path')
    build, headers, reference = args.build_dir.resolve(), args.headers.resolve(), args.reference_dir.resolve()
    build.mkdir(parents=True, exist_ok=True)
    source = ROOT/'validation/libflac_core/main.c'
    report = dict(status='running', purpose='correctness and harness smoke only; uncontrolled timings are not benchmark claims', commands=[], smoke=[])
    def run(command, label, env=None, encoding='utf-8'):
        proc = subprocess.run([str(x) for x in command], env=env, cwd=build, capture_output=True, timeout=180)
        text = (proc.stdout+proc.stderr).decode(encoding, errors='replace')
        (build/(label+'.log')).write_text(text, encoding='utf-8')
        report['commands'].append(dict(command=[str(x) for x in command], label=label, returncode=proc.returncode))
        if proc.returncode:
            raise RuntimeError(label+': '+text[-4000:])
        return text
    try:
        vswhere = Path(os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)'))/'Microsoft Visual Studio/Installer/vswhere.exe'
        installation = Path(run([vswhere,'-latest','-products','*','-requires','Microsoft.VisualStudio.Component.VC.Tools.x86.x64','-property','installationPath'],'vswhere').strip())
        vcvars = installation/'VC/Auxiliary/Build/vcvars64.bat'
        # Fixed tool-discovered path only; no input/output filename is shell-interpolated.
        setup=build/'setup-env.cmd'
        setup.write_text('@echo off\ncall "'+str(vcvars)+'" >nul\nif errorlevel 1 exit /b 1\nset PATH\nset INCLUDE\nset LIB\nset LIBPATH\nexit /b 0\n',encoding='ascii')
        env_out = run(['cmd.exe','/u','/d','/c',str(setup)],'vcvars',encoding='utf-16-le')
        env = dict(os.environ)
        for line in env_out.splitlines():
            if '=' in line and not line.startswith('='):
                key,value=line.split('=',1);env[key]=value
        compiler = shutil.which('cl.exe',path=env.get('Path',env.get('PATH')))
        librarian = shutil.which('lib.exe',path=env.get('Path',env.get('PATH')))
        dumpbin = shutil.which('dumpbin.exe',path=env.get('Path',env.get('PATH')))
        if not all([compiler,librarian,dumpbin]):raise RuntimeError('MSVC tools not resolved')
        report['compiler_path']=compiler
        report['compiler_sha256']=sha(Path(compiler))
        report['source_sha256']=sha(source)
        report['builder_sha256']=sha(Path(__file__))
        report['header_sha256']={str(p.relative_to(headers)):sha(p) for p in (headers/'FLAC').glob('*.h')}
        version=run([reference/'flac.exe','--version'],'reference-version').strip()
        if version != 'flac 1.5.0':raise RuntimeError('Need matching libFLAC 1.5.0 headers/library')
        report['reference_version']=version
        dll=reference/'libFLAC.dll'
        report['dll_source']=str(dll);report['dll_sha256']=sha(dll)
        report['library_build_flags']='Unknown: official Xiph 1.5.0 Win64 release binary; do not infer compiler flags from harness flags.'
        exports=sorted(set(re.findall(r'\b(FLAC__stream_encoder_\w+)\s*\(',source.read_text())))
        definition=build/'libFLAC.def'
        definition.write_text('LIBRARY libFLAC.dll\nEXPORTS\n'+'\n'.join(exports)+'\n',encoding='ascii')
        run([librarian,'/nologo','/machine:x64','/def:'+str(definition),'/out:'+str(build/'libFLAC.lib')],'import-library',env)
        shutil.copy2(dll,build/'libFLAC.dll')
        exe=build/'libflac_core.exe'
        flags=['/nologo','/O2','/MT','/std:c11','/W4','/utf-8','/D_CRT_SECURE_NO_WARNINGS']
        report['harness_flags']=flags
        run([compiler,*flags,'/I'+str(headers),str(source),'/Fo'+str(build/'libflac_core.obj'),'/Fe'+str(exe),str(build/'libFLAC.lib'),'/link','/INCREMENTAL:NO'],'compile',env)
        report['executable']=str(exe);report['executable_sha256']=sha(exe)
        report['cpu_simd_capabilities']=json.loads(run([exe,'--identity'],'cpu-identity'))
        disassembly=run([dumpbin,'/nologo','/disasm:nobytes',build/'libFLAC.dll'],'dll-disassembly',env)
        report['library_simd_evidence']={'xmm_mentions':len(re.findall(r'\bxmm\d+\b',disassembly,re.I)), 'ymm_mentions':len(re.findall(r'\bymm\d+\b',disassembly,re.I)), 'zmm_mentions':len(re.findall(r'\bzmm\d+\b',disassembly,re.I)), 'meaning':'SIMD code presence plus CPU/OS capabilities; actual runtime-dispatched branch not traced; no disable-asm control is applied.'}
        run([dumpbin,'/nologo','/headers',build/'libFLAC.dll'],'dll-headers',env)
        # Independent exact raw PCM, STREAMINFO MD5 and official flac -t (CRC/MD5).
        for bits in (16,24,32):
            for channels in (1,2,6,8):
                rng=random.Random(9639+bits*8+channels)
                pcm=[rng.randint(-(1<<(bits-1)),(1<<(bits-1))-1) for _ in range(257*channels)]
                pcm[:4]=[-(1<<(bits-1)),(1<<(bits-1))-1,0,-1]
                raw=b''.join(x.to_bytes(bits//8,'little',signed=True) for x in pcm)
                input_path=build/'input.raw';input_path.write_bytes(raw)
                for effort in (0,5,8):
                    name=f'b{bits}-c{channels}-e{effort}'
                    output=build/(name+'.flac');decoded=build/'decoded.raw'
                    timing=json.loads(run([exe,input_path,output,channels,bits,48000,256,2,effort],name).split('LIBFLAC_CORE ',1)[1])
                    assert len(timing['per_call_seconds'])==2 and all(x>0 for x in timing['per_call_seconds']) and timing['warm_seconds']>0
                    run([reference/'flac.exe','-s','-t',output],name+'-test')
                    run([reference/'flac.exe','-s','-d','-f','--force-raw-format','--endian=little','--sign=signed','-o',decoded,output],name+'-decode')
                    assert decoded.read_bytes()==raw,name+' PCM mismatch'
                    encoded=output.read_bytes()
                    assert encoded[:4]==b'fLaC' and encoded[4]&127==0
                    assert encoded[26:42]==hashlib.md5(raw).digest(),name+' MD5 mismatch'
                    report['smoke'].append(dict(name=name,status='pass',pcm_sha256=hashlib.sha256(raw).hexdigest(),flac_sha256=sha(output),bytes=len(encoded),timing_plumbing=timing))
        report['status']='pass'
    except Exception as exc:
        report['status']='fail';report['error']=repr(exc);raise
    finally:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':report['status'],'executable':report['executable'],'smoke_cases':len(report['smoke']),'report':str(args.report)}))

if __name__=='__main__':main()

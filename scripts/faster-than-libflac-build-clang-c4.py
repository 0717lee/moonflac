"""Compile explicitly supplied frozen generated C using official clang-cl.

Runtime/filesystem libraries remain byte-identical supplied MSVC artifacts;
this isolates the generated-C compiler while preserving ABI and allocator.
Functional outputs are compared; harness timing text is deliberately omitted.
"""
from pathlib import Path
import argparse,hashlib,json,os,re,shutil,subprocess

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--artifact',choices=['core','cli'],default='core')
parser.add_argument('--source-identity',type=Path,default=ROOT/'validation/evidence/faster-than-libflac-candidate4.json')
parser.add_argument('--source-root',type=Path,default=ROOT/'_build/faster-than-libflac/candidate4-source')
parser.add_argument('--generated-c',type=Path,default=ROOT/'_build/faster-than-libflac/candidate4/native/release/build/validation/benchmark_compete/benchmark_compete.c')
parser.add_argument('--runtime',type=Path,default=ROOT/'_build/faster-than-libflac/candidate4/native/release/build/libruntime.lib')
parser.add_argument('--filesystem',type=Path,default=ROOT/'_build/faster-than-libflac/candidate4/native/release/build/.mooncakes/moonbitlang/x/fs/libfs.lib')
parser.add_argument('--build-dir',type=Path,default=ROOT/'_build/faster-than-libflac/clang-c4')
parser.add_argument('--report',type=Path,default=ROOT/'validation/evidence/faster-than-libflac-clang-c4-identity.json')
isa=parser.add_mutually_exclusive_group()
isa.add_argument('--avx2',action='store_true')
isa.add_argument('--avx512',action='store_true')
parser.add_argument('--prefer-vector-width512',action='store_true')
parser.add_argument('--smoke-all',action='store_true')
parser.add_argument('--inspect',action='store_true')
args=parser.parse_args()
if args.prefer_vector_width512 and not args.avx512:
 parser.error('--prefer-vector-width512 requires --avx512')
for name in ['source_identity','source_root','generated_c','runtime','filesystem','build_dir','report']:
 setattr(args,name,getattr(args,name).resolve())
BUILD=args.build_dir
BUILD.mkdir(parents=True,exist_ok=True)
GENERATED=args.generated_c
COMPILER=ROOT/'validation/cache/llvm-23.1.2-windows/portable/bin/clang-cl.exe'
MOON=Path.home()/'.moon'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(command,label,env=None):
 p=subprocess.run([str(x) for x in command],cwd=BUILD,env=env,capture_output=True,timeout=180)
 log=(p.stdout+p.stderr).decode('utf-8',errors='replace')
 (BUILD/(label+'.log')).write_text(log,encoding='utf-8')
 if p.returncode:raise RuntimeError(label+': '+log[-3000:])
 return log
assert COMPILER.is_file()
identity=json.loads(args.source_identity.read_text())
baseline=ROOT/identity[args.artifact]['path'];assert sha(baseline)==identity[args.artifact]['sha256']
for name,digest in identity['sources'].items():
 source=ROOT/name if (ROOT/name).is_file() and ('/' in name or '\\' in name) else args.source_root/name
 assert sha(source)==digest,name
vswhere=Path(os.environ['ProgramFiles(x86)'])/'Microsoft Visual Studio/Installer/vswhere.exe'
installation=Path(run([vswhere,'-latest','-products','*','-requires','Microsoft.VisualStudio.Component.VC.Tools.x86.x64','-property','installationPath'],'vswhere').strip())
vcvars=installation/'VC/Auxiliary/Build/vcvars64.bat'
setup=BUILD/'setup-env.cmd'
setup.write_text('@echo off\ncall "'+str(vcvars)+'" >nul\nif errorlevel 1 exit /b 1\nset PATH\nset INCLUDE\nset LIB\nset LIBPATH\nexit /b 0\n',encoding='ascii')
p=subprocess.run(['cmd.exe','/u','/d','/c',str(setup)],capture_output=True,check=True)
environment=dict(os.environ)
for line in p.stdout.decode('utf-16-le').splitlines():
 if '=' in line and not line.startswith('='):
  key,value=line.split('=',1);environment[key]=value
link=Path(shutil.which('link.exe',path=environment.get('Path',environment.get('PATH'))))
runtime=args.runtime;filesystem=args.filesystem
host_probe=None
required_features=[]
if args.avx512:
 # Test-only native ISA probe. No codec operation or production source is C.
 probe_dir=BUILD/'host-isa-probe';probe_dir.mkdir(exist_ok=True)
 probe_source=probe_dir/'probe.c'
 checks={
  'MMX':('one[3]',23),'FXSR':('one[3]',24),'SSE':('one[3]',25),'SSE2':('one[3]',26),
  'SSE3':('one[2]',0),'PCLMUL':('one[2]',1),'SSSE3':('one[2]',9),'FMA':('one[2]',12),'CX16':('one[2]',13),
  'SSE4_1':('one[2]',19),'SSE4_2':('one[2]',20),'MOVBE':('one[2]',22),'POPCNT':('one[2]',23),
  'AES':('one[2]',25),'XSAVE':('one[2]',26),'OSXSAVE':('one[2]',27),'AVX':('one[2]',28),'F16C':('one[2]',29),'RDRND':('one[2]',30),
  'FSGSBASE':('seven[1]',0),'BMI1':('seven[1]',3),'AVX2':('seven[1]',5),'BMI2':('seven[1]',8),'INVPCID':('seven[1]',10),
  'AVX512F':('seven[1]',16),'AVX512DQ':('seven[1]',17),'RDSEED':('seven[1]',18),'ADX':('seven[1]',19),
  'CLFLUSHOPT':('seven[1]',23),'CLWB':('seven[1]',24),'AVX512CD':('seven[1]',28),'AVX512BW':('seven[1]',30),'AVX512VL':('seven[1]',31),
  'PKU':('seven[2]',3),'LAHF_LM':('ext[2]',0),'LZCNT':('ext[2]',5),'PRFCHW':('ext[2]',8),
  'XSAVEOPT':('save[0]',0),'XSAVEC':('save[0]',1),'XSAVES':('save[0]',3),
 }
 code=['#include <intrin.h>','#include <stdint.h>','#include <stdio.h>','int main(void) {',
       'int max[4],one[4]={0},seven[4]={0},ext[4]={0},save[4]={0},emax[4];',
       '__cpuid(max,0); if(max[0]>=1)__cpuid(one,1); if(max[0]>=7)__cpuidex(seven,7,0);',
       '__cpuid(emax,(int)0x80000000U); if((uint32_t)emax[0]>=0x80000001U)__cpuid(ext,(int)0x80000001U);',
       'if(max[0]>=13)__cpuidex(save,13,1);',
       'uint64_t xcr0=((uint32_t)one[2]&(1U<<27))?_xgetbv(0):0;',
       'printf("{\\\"xcr0\\\":%llu,\\\"features\\\":{",(unsigned long long)xcr0);']
 for index,(name,(register,bit)) in enumerate(checks.items()):
  code.append('printf("'+('' if index==0 else ',')+'\\\"'+name+'\\\":%s",((uint32_t)'+register+'&(1U<<'+str(bit)+'))?"true":"false");')
 code+=['printf(",\\\"OS_AVX512\\\":%s,\\\"OS_AVX\\\":%s}}\\n",(xcr0&0xe6)==0xe6?"true":"false",(xcr0&6)==6?"true":"false");','return 0;','}']
 probe_source.write_text('\n'.join(code)+'\n',encoding='ascii')
 probe_exe=probe_dir/'probe.exe';cl=link.parent/'cl.exe'
 probe_command=[cl,'/nologo','/O2','/MT','/arch:AVX','/Fe'+str(probe_exe),'/Fo'+str(probe_dir/'probe.obj'),probe_source]
 run(probe_command,'isa-probe-build',env=environment)
 probe_result=json.loads(run([probe_exe],'isa-probe-result',env=environment))
 # Explicitly requested supported-host target: skylake-avx512 minus PKU.
 # Keep its raw CPUID result in evidence, but never enable it in generated C.
 required_features=[name for name in checks if name!='PKU']+['OS_AVX','OS_AVX512']
 missing=[feature for feature in required_features if not probe_result['features'][feature]]
 host_probe={'source':str(probe_source.relative_to(ROOT)),'source_sha256':sha(probe_source),
  'executable_sha256':sha(probe_exe),'compiler':str(cl),'compiler_sha256':sha(cl),'command':[str(x) for x in probe_command],
  'result':probe_result,'required_features':required_features,'missing':missing}
 (probe_dir/'identity.json').write_text(json.dumps(host_probe,indent=2)+'\n',encoding='utf8')
 assert not missing,'Selected skylake-avx512 host ISA unavailable: '+','.join(missing)
if args.avx2:
 supported=subprocess.run(['pwsh','-NoProfile','-Command','[System.Runtime.Intrinsics.X86.Avx2]::IsSupported -and [System.Runtime.Intrinsics.X86.Fma]::IsSupported -and [System.Runtime.Intrinsics.X86.Bmi1]::IsSupported -and [System.Runtime.Intrinsics.X86.Bmi2]::IsSupported'],capture_output=True,text=True,check=True).stdout.strip()
 assert supported=='True','Clang /arch:AVX2 selects the Haswell feature set; AVX2/FMA/BMI1/BMI2 are required'
source_hash=sha(GENERATED)
output=BUILD/('benchmark_compete.exe' if args.artifact=='core' else 'moonflac.exe')
command=[COMPILER,'/Fe'+str(output),'/I'+str(MOON/'include'),'/Fo'+str(BUILD)+os.sep,
         '/utf-8','/wd4819','/nologo','/O2','/clang:-ffp-contract=off',
         *(['/arch:AVX2'] if args.avx2 else ['/arch:AVX512'] if args.avx512 else []),
         *(['/clang:-mno-pku'] if args.avx512 else []),
         *(['/clang:-mprefer-vector-width=512'] if args.prefer_vector_width512 else []),
         GENERATED,filesystem,runtime,'/MT','-fuse-ld=link','/link','/LIBPATH:'+str(MOON/'lib')]
driver_plan=run([command[0],'-###',*command[1:]],'driver-plan',env=environment)
target_macro_features=None
if args.avx512:
 assert re.search(r'"-target-feature"\s+"-pku"',driver_plan),'PKU disable missing in driver plan'
 macro_text=run([COMPILER,'/E','/clang:-dM','/TC','/arch:AVX512','/clang:-mno-pku','NUL'],'target-macros',env=environment)
 assert '#define __PKU__' not in macro_text
 target_macro_features=[line for line in macro_text.splitlines() if re.match(r'#define __(AVX|FMA|BMI|F16C|LZCNT|POPCNT|ADX|AES|CLFLUSH|CLWB|FSGSBASE|FXSR|INVPCID|MMX|MOVBE|PCLMUL|PKU|PRFCHW|RDRND|RDSEED|SSE|SSSE|XSAVE)',line)]
run(command,'compile',env=environment)
assert sha(GENERATED)==source_hash
report={'variant':BUILD.name,'scope':'generated C compiler only; explicitly supplied original MSVC runtime/native-support libraries reused unchanged',
 'compiler':{'path':str(COMPILER.relative_to(ROOT)),'sha256':sha(COMPILER),'version':run([COMPILER,'--version'],'version')},
 'linker':{'path':str(link),'sha256':sha(link)},'command':[str(x) for x in command],
 'sources':{str(GENERATED.relative_to(ROOT)):source_hash},
 'libraries':{str(p.relative_to(ROOT)):sha(p) for p in [runtime,filesystem]},
 'environment':{k:v for k,v in environment.items() if k.upper() in ['INCLUDE','LIB','LIBPATH']},
 args.artifact:{'path':str(output.relative_to(ROOT)),'sha256':sha(output)},
 'reference_identity':str(args.source_identity.relative_to(ROOT)),
 'source_root':str(args.source_root.relative_to(ROOT)),
 'source_manifest':identity['sources'],
 'cpu_requirement':'Skylake-AVX512 target with PKU explicitly disabled; OS XCR0 SSE/YMM/opmask/ZMM state enabled' if args.avx512 else 'Haswell-compatible x86-64 feature set selected by /arch:AVX2 (AVX2/FMA/BMI1/BMI2)' if args.avx2 else 'baseline x86-64',
 'clang_target_cpu':re.search(r'"-target-cpu"\s+"([^"]+)"',driver_plan).group(1),
 'host_features_verified':required_features if args.avx512 else ['AVX2','FMA','BMI1','BMI2'] if args.avx2 else [],
 'native_host_probe':host_probe,'prefer_vector_width512':args.prefer_vector_width512,
 'clang_target_features':re.findall(r'"-target-feature"\s+"([^"]+)"',driver_plan),
 'target_macro_features':target_macro_features,'explicitly_disabled_features':['PKU'] if args.avx512 else [],
 'avx2_host_verified':args.avx2,'fp_contract':'off; no fast-math or reassociation flags',
 'preparation_evidence':'validation/evidence/faster-than-libflac-clang-preparation.json',
 'driver_plan':str((BUILD/'driver-plan.log').relative_to(ROOT)),
 'notes':['Official LLVM23.1.2 driver defaults to lld-link; -fuse-ld=link deliberately preserves original MSVC linker.',
          'Only generated C is recompiled; runtime and native-support libraries retain original MSVC compiler identity.',
          'Functional core smoke invokes owned-buffer harness; internal timing output is discarded and no performance results are reported.' if args.artifact=='core' else 'Functional CLI smoke performs raw PCM encode; no performance measurement.'],
 'global_configuration_changed':False,'performance_measured':False,'smoke':[]}
manifest=json.loads((ROOT/'validation/evidence/faster-than-libflac-inputs-original-core.json').read_text())
for case in manifest['cases']:
 if not args.smoke_all and case['name'] not in ['noise-16-2','ar-24-2']:continue
 outputs=[]
 for label,exe in [('msvc',baseline),('clang',output)]:
  destination=BUILD/(case['name']+'-'+label+'.flac')
  if args.artifact=='core':
   smoke_command=[str(exe),str(ROOT/case['path']),str(destination),str(case['channels']),str(case['bits']),str(case['rate']),str(case['block']),'1','8']
  else:
   smoke_command=[str(exe),'encode',str(ROOT/case['path']),str(destination),'--raw','--sample-rate',str(case['rate']),'--channels',str(case['channels']),'--bits',str(case['bits']),'--block-size',str(case['block']),'--effort','8']
  result=subprocess.run(smoke_command,capture_output=True,text=True,timeout=180)
  assert result.returncode==0,result.stderr
  outputs.append(destination)
 assert outputs[0].read_bytes()==outputs[1].read_bytes(),case['name']
 flac=ROOT/'validation/cache/libflac/flac-1.5.0-win/Win64/flac.exe'
 verified=subprocess.run([str(flac),'-t','-s',str(outputs[1])],capture_output=True,text=True,timeout=60)
 assert verified.returncode==0,verified.stderr
 report['smoke'].append({'case':case['name'],'pcm_sha256':sha(ROOT/case['path']),
    'encoded_bytes':outputs[0].stat().st_size,'sha256':sha(outputs[0]),'msvc_exact_bytes':True,'libflac_test_exit':verified.returncode})
report['libflac']={'path':str(flac.relative_to(ROOT)),'sha256':sha(flac)}
if args.inspect:
 dumpbin=link.parent/'dumpbin.exe'
 object_path=BUILD/(GENERATED.stem+'.obj')
 disassembly=BUILD/'object-disassembly.txt'
 with disassembly.open('wb') as out:
  subprocess.run([str(dumpbin),'/disasm',str(object_path)],stdout=out,stderr=subprocess.PIPE,check=True)
 content=disassembly.read_text(encoding='utf-8',errors='replace')
 functions={}
 for match in re.finditer(r'^([^\s:]+):\s*$',content,re.M):
  symbol=match.group(1)
  if not any(x in symbol for x in ['encoder__lpc__models','encoder__predict__double__into','encoder__predict__into','encoder__prepare__leaf__prefixes','encoder__budget__residual__plan','encoder__single__partition__plan']):continue
  start=match.start();after=re.search(r'^\S',content[match.end():],re.M)
  body=content[start:match.end()+after.start() if after else len(content)]
  instructions=re.findall(r'^\s+[0-9A-F]+:\s+(?:[0-9A-F]{2}\s+)+([a-z][a-z0-9]+)\s',body,re.M)
  packed={op:instructions.count(op) for op in sorted(set(instructions)) if op in ['mulpd','addpd','vmulpd','vaddpd'] or 'fmadd' in op}
  scalar={op:instructions.count(op) for op in ['mulsd','addsd','vmulsd','vaddsd'] if op in instructions}
  selected=BUILD/(symbol+'.asm.txt');selected.write_text(body,encoding='utf-8')
  packed_integer={op:instructions.count(op) for op in sorted(set(instructions)) if re.fullmatch(r'v?p(?:add|sub|srl|sll|mul|min|max|and|or|xor|cmp|movzx|lzcnt)[a-z0-9]*',op)}
  functions[symbol]={'packed_float_instructions':packed,'packed_integer_instructions':packed_integer,'scalar_float_instructions':scalar,'ymm_mentions':len(re.findall(r'\bymm\d+',body)),'zmm_mentions':len(re.findall(r'\bzmm\d+',body)),'excerpt':str(selected.relative_to(ROOT)),'note':'Counts include all loops in this function; inspect excerpt to associate with the specific lag/tile loop.'}
 report['native_code_inspection']={'object':str(object_path.relative_to(ROOT)),'object_sha256':sha(object_path),'functions':functions,'all_disassembly':str(disassembly.relative_to(ROOT))}
args.report.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps({args.artifact:report[args.artifact],'smoke':report['smoke'],'performance_measured':False}))

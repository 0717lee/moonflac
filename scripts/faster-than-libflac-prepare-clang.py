"""Isolate official LLVM Windows compiler; no installer or global PATH edits.

Downloads the exact official GitHub release archive and checks its published
SHA256 before extracting only compiler executables, DLLs and builtin headers.
"""
from pathlib import Path,PurePosixPath
import hashlib,json,shutil,subprocess,tarfile,urllib.request
import zstandard

ROOT=Path(__file__).resolve().parents[1]
CACHE=ROOT/'validation/cache/llvm-23.1.2-windows'
TAG='llvmorg-23.1.2'
NAME='clang+llvm-23.1.2-x86_64-pc-windows-msvc.tar.zst'
CACHE.mkdir(parents=True,exist_ok=True)
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
 return h.hexdigest()
meta=subprocess.run(['gh','api',f'repos/llvm/llvm-project/releases/tags/{TAG}'],capture_output=True,text=True,encoding='utf-8',check=True).stdout
(CACHE/'release.json').write_text(meta,encoding='utf-8')
release=json.loads(meta);asset=next(a for a in release['assets'] if a['name']==NAME)
digest=asset['digest'].removeprefix('sha256:')
assert len(digest)==64 and asset['browser_download_url'].startswith('https://github.com/llvm/llvm-project/releases/download/')
archive=CACHE/NAME
if not archive.exists():
 partial=CACHE/(NAME+'.partial')
 subprocess.run(['curl.exe','--fail','--location','--connect-timeout','20','--max-time','180','--retry','1','--silent','--show-error',asset['browser_download_url'],'--output',str(partial)],check=True)
 assert partial.stat().st_size==asset['size']
 assert sha(partial)==digest,'Official archive digest mismatch'
 partial.replace(archive)
assert sha(archive)==digest
print('Official archive SHA256 verified',digest,flush=True)
selected=[];links=[];destination=CACHE/'portable';destination.mkdir(exist_ok=True)
with archive.open('rb') as raw,zstandard.ZstdDecompressor(max_window_size=1073741824).stream_reader(raw) as reader,tarfile.open(fileobj=reader,mode='r|') as tar:
 for member in tar:
  parts=PurePosixPath(member.name).parts
  if len(parts)<2:continue
  rel=PurePosixPath(*parts[1:]);name=str(rel)
  wanted=name in ['bin/clang.exe','bin/clang-cl.exe'] or (name.startswith('bin/') and name.endswith('.dll')) or (name.startswith('lib/clang/') and '/include/' in name) or name.endswith('LICENSE.TXT')
  if not wanted or member.isdir():continue
  target=destination.joinpath(*rel.parts).resolve()
  assert target.is_relative_to(destination.resolve())
  target.parent.mkdir(parents=True,exist_ok=True)
  if member.isfile():
   with tar.extractfile(member) as src,target.open('wb') as out:shutil.copyfileobj(src,out)
   selected.append({'path':str(target.relative_to(CACHE)),'size':target.stat().st_size,'sha256':sha(target)})
  elif member.islnk():links.append((target,member.linkname))
  else:raise RuntimeError('Unexpected archive link '+member.name)
for target,link in links:
 rel=PurePosixPath(*PurePosixPath(link).parts[1:]);origin=destination.joinpath(*rel.parts).resolve()
 assert origin.is_relative_to(destination.resolve()) and origin.is_file()
 shutil.copyfile(origin,target)
 selected.append({'path':str(target.relative_to(CACHE)),'hardlink_materialized_from':link,'sha256':sha(target)})
compiler=destination/'bin/clang-cl.exe'
assert compiler.is_file(),'Official archive did not contain clang-cl'
version=subprocess.run([str(compiler),'--version'],capture_output=True,text=True,encoding='utf-8',check=True).stdout
(CACHE/'version.txt').write_text(version,encoding='utf-8')
license_url=f'https://raw.githubusercontent.com/llvm/llvm-project/{TAG}/llvm/LICENSE.TXT'
urllib.request.urlretrieve(license_url,CACHE/'LLVM-LICENSE.TXT')
report={'release':TAG,'release_url':release['html_url'],'download_url':asset['browser_download_url'],'archive_bytes':asset['size'],'official_sha256':digest,'actual_sha256':sha(archive),'compiler':{'path':str(compiler.relative_to(ROOT)),'sha256':sha(compiler),'version':version},'license':{'url':license_url,'path':str((CACHE/'LLVM-LICENSE.TXT').relative_to(ROOT)),'sha256':sha(CACHE/'LLVM-LICENSE.TXT')},'verification':'Official GitHub release asset SHA256 matched; no independent signature claim','extracted_files':selected,'global_configuration_changed':False,'admin_installation':False,'performance_measured':False}
(ROOT/'validation/evidence/faster-than-libflac-clang-preparation.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k!='extracted_files'}),flush=True)

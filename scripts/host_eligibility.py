"""Fresh, fail-closed x64 eligibility for the C77 compiler artifacts.

This module never executes a codec. Build-time CPUID is historical evidence only.
"""
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
# CPUID fields cover the complete C77 build-time requirement declaration.
BITS = {
    'MMX': ('one[3]', 23), 'FXSR': ('one[3]', 24), 'SSE': ('one[3]', 25), 'SSE2': ('one[3]', 26),
    'SSE3': ('one[2]', 0), 'PCLMUL': ('one[2]', 1), 'SSSE3': ('one[2]', 9), 'FMA': ('one[2]', 12),
    'CX16': ('one[2]', 13), 'SSE4_1': ('one[2]', 19), 'SSE4_2': ('one[2]', 20), 'MOVBE': ('one[2]', 22),
    'POPCNT': ('one[2]', 23), 'AES': ('one[2]', 25), 'XSAVE': ('one[2]', 26), 'OSXSAVE': ('one[2]', 27),
    'AVX': ('one[2]', 28), 'F16C': ('one[2]', 29), 'RDRND': ('one[2]', 30),
    'FSGSBASE': ('seven[1]', 0), 'BMI1': ('seven[1]', 3), 'HLE': ('seven[1]', 4), 'AVX2': ('seven[1]', 5),
    'BMI2': ('seven[1]', 8), 'INVPCID': ('seven[1]', 10), 'RTM': ('seven[1]', 11),
    'AVX512F': ('seven[1]', 16), 'AVX512DQ': ('seven[1]', 17), 'RDSEED': ('seven[1]', 18),
    'ADX': ('seven[1]', 19), 'CLFLUSHOPT': ('seven[1]', 23), 'CLWB': ('seven[1]', 24),
    'AVX512CD': ('seven[1]', 28), 'SHA': ('seven[1]', 29), 'AVX512BW': ('seven[1]', 30),
    'AVX512VL': ('seven[1]', 31), 'PKU': ('seven[2]', 3),
    'LAHF_LM': ('ext[2]', 0), 'LZCNT': ('ext[2]', 5), 'PRFCHW': ('ext[2]', 8),
    'XSAVEOPT': ('save[0]', 0), 'XSAVEC': ('save[0]', 1), 'XSAVES': ('save[0]', 3),
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def declared_target(obj):
    command = obj.get('command', [])
    flags = [str(x).lower() for x in command]
    target = obj.get('clang_target_cpu')
    arch = [x for x in flags if x.startswith('/arch:')]
    extra = [x for x in flags if x.startswith(('/clang:-m', '-m'))]
    if target == 'skylake-avx512':
        if arch != ['/arch:avx512']:
            raise ValueError('Target/architecture flag mismatch')
        allowed = {'/clang:-mno-pku'}
        if set(extra) - allowed:
            raise ValueError('Unsupported target feature override: ' + repr(extra))
        if target == 'skylake-avx512' and '/clang:-mno-pku' not in flags:
            raise ValueError('Supported Skylake target must explicitly disable PKU')
        if obj.get('clang_target_features', []) != ['-pku']:
            raise ValueError('Target features disagree with compile flags')
        return target
    raise ValueError('This bounded guard supports only the C77 Skylake-AVX512 minus PKU target')


def check_features(required, current):
    missing = sorted(x for x in required if not current['features'].get(x, False))
    if 'AVX' in required or 'AVX2' in required or any(x.startswith('AVX512') for x in required):
        missing += [x for x in ['XSAVE', 'OSXSAVE', 'AVX'] if not current['features'].get(x, False)]
        if current.get('xcr0', 0) & 6 != 6:
            missing.append('XCR0_SSE_YMM')
    if any(x.startswith('AVX512') for x in required) and current.get('xcr0', 0) & 0xe6 != 0xe6:
        missing.append('XCR0_OPMASK_ZMM')
    if missing:
        raise RuntimeError('Current host cannot execute target: ' + ', '.join(sorted(set(missing))))


def _run(command, folder, label, env=None):
    p = subprocess.run([str(x) for x in command], capture_output=True, env=env, timeout=180)
    (folder / (label + '.log')).write_bytes(p.stdout + p.stderr)
    if p.returncode:
        raise RuntimeError(label + ' failed; no codec launched')
    return p.stdout.decode('utf-8', errors='replace')


def _msvc_environment(folder):
    vswhere = Path(os.environ['ProgramFiles(x86)']) / 'Microsoft Visual Studio/Installer/vswhere.exe'
    installation = _run([vswhere, '-latest', '-products', '*', '-requires', 'Microsoft.VisualStudio.Component.VC.Tools.x86.x64', '-property', 'installationPath'], folder, 'vswhere').strip()
    script = folder / 'environment.cmd'
    script.write_text('@echo off\ncall "' + str(Path(installation) / 'VC/Auxiliary/Build/vcvars64.bat') + '" >nul\nif errorlevel 1 exit /b 1\nset\n', encoding='ascii')
    p = subprocess.run(['cmd.exe', '/u', '/d', '/c', str(script)], capture_output=True, check=True)
    env = dict(os.environ)
    for line in p.stdout.decode('utf-16-le').splitlines():
        if '=' in line and not line.startswith('='):
            k, v = line.split('=', 1)
            env[k] = v
    return env


def probe_current(folder):
    if os.name != 'nt' or platform.machine().lower() not in ('amd64', 'x86_64'):
        raise RuntimeError('Specialized Windows x64 host probe unavailable on this platform')
    env = _msvc_environment(folder)
    cl = shutil.which('cl.exe', path=env.get('Path', env.get('PATH')))
    if not cl:
        raise RuntimeError('Baseline x64 probe compiler unavailable')
    source = folder / 'probe.c'
    lines = ['#include <intrin.h>', '#include <stdint.h>', '#include <stdio.h>', 'int main(void) {',
             'int m[4],one[4]={0},seven[4]={0},ext[4]={0},save[4]={0},em[4];',
             '__cpuid(m,0); if(m[0]>=1)__cpuid(one,1); if(m[0]>=7)__cpuidex(seven,7,0);',
             '__cpuid(em,(int)0x80000000U); if((uint32_t)em[0]>=0x80000001U)__cpuid(ext,(int)0x80000001U);',
             'if(m[0]>=13)__cpuidex(save,13,1);',
             'uint64_t x=0; if(((uint32_t)one[2]&(3U<<26))==(3U<<26)) x=_xgetbv(0);',
             'printf("{\\"xcr0\\":%llu,\\"features\\":{",(unsigned long long)x);']
    for i, (name, (register, bit)) in enumerate(BITS.items()):
        lines.append('printf("' + (',' if i else '') + '\\"' + name + '\\":%s",((uint32_t)' + register + '&(1U<<' + str(bit) + '))?"true":"false");')
    lines += ['printf("}}\\n"); return 0; }']
    source.write_text('\n'.join(lines), encoding='ascii')
    binary = folder / 'probe.exe'
    command = [cl, '/nologo', '/Od', '/MT', '/Fe' + str(binary), '/Fo' + str(folder / 'probe.obj'), str(source)]
    _run(command, folder, 'compile-probe', env)
    current = json.loads(_run([binary], folder, 'current-host', env))
    current['features']['OS_AVX'] = current['xcr0'] & 6 == 6
    current['features']['OS_AVX512'] = current['xcr0'] & 0xe6 == 0xe6
    return current, {'source_sha256': sha(source), 'binary_sha256': sha(binary), 'compiler_sha256': sha(cl), 'command': command}, env


def target_requirements(obj):
    declared_target(obj)
    # Exactly the full C77 builder requirement, not its historical result.
    expected = (set(BITS) - {'HLE', 'RTM', 'SHA', 'PKU'}) | {'OS_AVX', 'OS_AVX512'}
    required = obj.get('host_features_verified', [])
    recorded = obj.get('native_host_probe', {}).get('required_features', [])
    if set(required) != expected or set(recorded) != expected:
        raise ValueError('Incomplete or changed C77 CPU requirement declaration')
    if obj.get('explicitly_disabled_features') != ['PKU'] or obj.get('prefer_vector_width512'):
        raise ValueError('C77 target policy differs from the supported artifact')
    return sorted(expected)


def guard_identities(roles, folder):
    """roles maps labels to (identity_path, binary_path, cli_or_core)."""
    folder = Path(folder).resolve()
    if folder.exists():
        raise FileExistsError('Preserve host probe receipt: ' + str(folder))
    folder.mkdir(parents=True)
    receipt = {'status': 'checking', 'roles': {}, 'current_probe': None, 'module_sha256': sha(__file__)}
    try:
        objects = {}
        for label, (identity, binary, mode) in roles.items():
            if identity is None:
                raise ValueError('Executable identity required for host eligibility: ' + label)
            obj = json.loads(Path(identity).read_text(encoding='utf-8-sig'))
            artifact = obj.get(mode)
            if not artifact or artifact.get('sha256') != sha(binary):
                raise ValueError('Executable is not bound to declared ISA identity: ' + label)
            target = declared_target(obj)
            objects[label] = (obj, target_requirements(obj))
            receipt['roles'][label] = {'identity_sha256': sha(identity), 'binary_sha256': sha(binary), 'target': target}
        if platform.machine().lower() not in ('amd64', 'x86_64'):
            raise RuntimeError('x64 artifacts require an x64 host')
        current, provenance, _ = probe_current(folder)
        receipt['current_probe'] = {'result': current, **provenance}
        for label, (_, required) in objects.items():
            receipt['roles'][label]['required_features'] = required
            check_features(required, current)
        receipt['status'] = 'pass'
        return receipt
    except BaseException as error:
        receipt.update(status='rejected', error=repr(error))
        raise
    finally:
        (folder / 'receipt.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')


def guarded_dispatch(roles, folder, dispatch):
    receipt = guard_identities(roles, folder)
    return dispatch(receipt)
